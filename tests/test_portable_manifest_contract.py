"""Portable manifest schema and Codex parity regression tests."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import validate_portable_plugin as portable  # noqa: E402


class PortableManifestContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        self.codex = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))

    def test_shipped_manifest_satisfies_closed_schema_and_codex_parity(self) -> None:
        report = portable.Report()
        plugin = portable.check_plugin_manifest(ROOT, report)
        portable.check_parity(ROOT, plugin, report)
        self.assertEqual([], report.errors)
        self.assertEqual(self.codex["interface"], plugin["extensions"]["com.openai"]["interface"])
        self.assertEqual(
            {key: self.codex[key] for key in ("displayName", "displayName_i18n", "description_i18n")},
            {key: plugin["extensions"]["ai.partme"][key] for key in ("displayName", "displayName_i18n", "description_i18n")},
        )

    def test_closed_schema_rejects_unknown_top_level_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            invalid = copy.deepcopy(self.plugin)
            invalid["displayName"] = "invalid top-level field"
            (root / "plugin.json").write_text(json.dumps(invalid), encoding="utf-8")
            report = portable.Report()
            portable.check_plugin_manifest(root, report)
            self.assertTrue(any("unknown top-level field" in error for error in report.errors), report.errors)

    def test_codex_parity_rejects_interface_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".codex-plugin").mkdir()
            (root / ".codex-plugin/plugin.json").write_text(json.dumps(self.codex), encoding="utf-8")
            invalid = copy.deepcopy(self.plugin)
            invalid["extensions"]["com.openai"]["interface"]["displayName"] += " drift"
            report = portable.Report()
            portable.check_parity(root, invalid, report)
            self.assertTrue(any("interface" in error and "drifted" in error for error in report.errors), report.errors)


if __name__ == "__main__":
    unittest.main()
