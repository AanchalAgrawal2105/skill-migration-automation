from __future__ import annotations

import os
import unittest

from app.llm import LiveOpenAILLM
from tests.contract_fixtures import MigrationPlan


@unittest.skipUnless(
    os.getenv("REFER_LIVE_SMOKE") == "1",
    "set REFER_LIVE_SMOKE=1, REFER_MODEL, and OPENAI_API_KEY to run",
)
class LiveSmokeTests(unittest.TestCase):
    def test_live_plan_parses(self) -> None:
        adapter = LiveOpenAILLM(plan_model=MigrationPlan)
        result = adapter.create_plan(
            goal="Rename a deprecated literal in a one-file Python repository",
            profile={"language": "python", "files": ["example.py"]},
            pack={"detect": {"markers": ["deprecated_literal"]}},
        )
        self.assertTrue(result.steps)
        self.assertTrue(result.candidate_literals)


if __name__ == "__main__":
    unittest.main()
