from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.llm import (
    FixtureLLM,
    LLMConfigurationError,
    LLMRefusalError,
    LLMResponseError,
    LiveOpenAILLM,
    TransformOutput,
    build_llm,
)
from tests.contract_fixtures import MigrationPlan


class FakeResponses:
    def __init__(self, responses: list[object]) -> None:
        self._responses = responses
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class LLMTests(unittest.TestCase):
    def test_live_requires_model(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(LLMConfigurationError):
                LiveOpenAILLM(plan_model=MigrationPlan, client=SimpleNamespace())

    def test_live_retries_missing_parsed_output_once(self) -> None:
        expected = MigrationPlan(
            steps=[{"description": "Update call sites", "risk": "review"}],
            candidate_literals=["old.call"],
        )
        responses = FakeResponses(
            [SimpleNamespace(output_parsed=None, output=[]), SimpleNamespace(output_parsed=expected, output=[])]
        )
        adapter = LiveOpenAILLM(
            plan_model=MigrationPlan,
            model="configured-model",
            client=SimpleNamespace(responses=responses),
        )

        actual = adapter.create_plan(goal="migrate", profile={}, pack=None)

        self.assertEqual(actual, expected)
        self.assertEqual(len(responses.calls), 2)
        self.assertFalse(responses.calls[0]["store"])
        self.assertIs(responses.calls[0]["text_format"], MigrationPlan)

    def test_refusal_is_not_retried(self) -> None:
        refusal = SimpleNamespace(
            output_parsed=None,
            output=[SimpleNamespace(content=[SimpleNamespace(type="refusal", refusal="no")])],
        )
        responses = FakeResponses([refusal, refusal])
        adapter = LiveOpenAILLM(
            plan_model=MigrationPlan,
            model="configured-model",
            client=SimpleNamespace(responses=responses),
        )

        with self.assertRaises(LLMRefusalError):
            adapter.create_plan(goal="migrate", profile={}, pack=None)
        self.assertEqual(len(responses.calls), 1)

    def test_transformation_is_typed(self) -> None:
        parsed = TransformOutput(modified="new.call()\n", rationale="Updated the call")
        responses = FakeResponses([SimpleNamespace(output_parsed=parsed, output=[])])
        adapter = LiveOpenAILLM(
            plan_model=MigrationPlan,
            model="configured-model",
            client=SimpleNamespace(responses=responses),
        )
        output = adapter.transform_file(
            goal="migrate",
            path="app.py",
            original="old.call()\n",
            sites=[],
            pack=None,
        )
        self.assertEqual(output.modified, "new.call()\n")

    def test_fixture_adapter_and_factory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "case-a"
            fixture.mkdir()
            (fixture / "plan.json").write_text(
                json.dumps(
                    {
                        "steps": [{"description": "Update", "risk": "auto"}],
                        "candidate_literals": ["old.call"],
                    }
                ),
                encoding="utf-8",
            )
            (fixture / "transforms.json").write_text(
                json.dumps(
                    {
                        "src/app.py": {
                            "modified": "new.call()\n",
                            "rationale": "Updated call",
                        }
                    }
                ),
                encoding="utf-8",
            )
            adapter = build_llm(
                demo_mode=True,
                plan_model=MigrationPlan,
                pack={"demo": {"fixture_id": "case-a"}},
                fixtures_root=root,
            )
            plan = adapter.create_plan(goal="anything", profile={}, pack=None)
            output = adapter.transform_file(
                goal="anything",
                path="src/app.py",
                original="old.call()\n",
                sites=[],
                pack=None,
            )

        self.assertEqual(plan.candidate_literals, ["old.call"])
        self.assertEqual(output.modified, "new.call()\n")

    def test_fixture_id_cannot_traverse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(LLMConfigurationError):
                FixtureLLM(
                    plan_model=MigrationPlan,
                    fixture_id="../escape",
                    fixtures_root=directory,
                )

    def test_invalid_fixture_output_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "case"
            fixture.mkdir()
            (fixture / "plan.json").write_text("{}", encoding="utf-8")
            (fixture / "transforms.json").write_text("[]", encoding="utf-8")
            with self.assertRaises(LLMResponseError):
                FixtureLLM(
                    plan_model=MigrationPlan,
                    fixture_id="case",
                    fixtures_root=directory,
                )


if __name__ == "__main__":
    unittest.main()
