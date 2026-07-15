from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.packs import MAX_PACK_BYTES, PackError, coerce_pack, load_pack


class PackTests(unittest.TestCase):
    def test_loads_known_fields_and_preserves_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pack.yaml"
            path.write_text(
                """name: example
detect:
  markers: [old.call, old.call]
breaking_changes:
  - pattern: old.call
    fix: use new.call
    risk: auto
custom_metadata:
  owner: platform
""",
                encoding="utf-8",
            )
            pack = load_pack(path)

        self.assertIsNotNone(pack)
        assert pack is not None
        self.assertEqual(pack.detect.markers, ["old.call"])
        self.assertEqual(pack.literals_with_risk(), [("old.call", "auto")])
        self.assertEqual(pack.model_extra["custom_metadata"]["owner"], "platform")

    def test_requires_mapping_root(self) -> None:
        with self.assertRaises(PackError):
            coerce_pack(["not", "a", "mapping"])  # type: ignore[arg-type]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.yaml"
            path.write_text("", encoding="utf-8")
            with self.assertRaises(PackError):
                load_pack(path)

    def test_rejects_unknown_risk(self) -> None:
        with self.assertRaises(PackError):
            coerce_pack({"breaking_changes": [{"pattern": "x", "risk": "hopeful"}]})

    def test_rejects_oversized_pack(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.yaml"
            path.write_bytes(b"x" * (MAX_PACK_BYTES + 1))
            with self.assertRaises(PackError):
                load_pack(path)


if __name__ == "__main__":
    unittest.main()
