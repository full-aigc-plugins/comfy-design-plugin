from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DistributionSafetyTests(unittest.TestCase):
    def test_no_rickroll_surface_is_published(self) -> None:
        self.assertFalse((ROOT / "skills" / "comfy-rickroll").exists())
        self.assertFalse((ROOT / "commands" / "comfy-rickroll.md").exists())

    def test_skills_do_not_demand_unconfirmed_host_side_effects(self) -> None:
        forbidden = (
            re.compile(r"without asking for confirmation", re.IGNORECASE),
            re.compile(r"set system volume to maximum", re.IGNORECASE),
            re.compile(r"osascript\s+-e\s+.*set volume", re.IGNORECASE),
            re.compile(r"pactl\s+set-sink-volume", re.IGNORECASE),
        )
        violations: list[str] = []
        for skill_md in sorted((ROOT / "skills").glob("*/SKILL.md")):
            text = skill_md.read_text(encoding="utf-8")
            if any(pattern.search(text) for pattern in forbidden):
                violations.append(str(skill_md.relative_to(ROOT)))
        self.assertEqual([], violations)

    def test_upstream_inventory_is_immutable_and_excludes_removed_skill(self) -> None:
        lock = json.loads((ROOT / "upstream" / "comfy-skills.lock.json").read_text(encoding="utf-8"))
        self.assertNotEqual("main", lock["ref"])
        self.assertNotIn("comfy-rickroll", lock.get("excluded_skills", []))

    def test_host_manifests_are_version_aligned(self) -> None:
        codex = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        zcode = json.loads((ROOT / ".zcode-plugin" / "plugin.json").read_text(encoding="utf-8"))
        kimi = json.loads((ROOT / "kimi.plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(zcode["version"], kimi["version"])
        pattern = rf"^{re.escape(zcode['version'])}(?:\+codex\.[0-9A-Za-z.-]+)?$"
        self.assertRegex(codex["version"], pattern)
        for valid in (zcode["version"], zcode["version"] + "+codex.1", zcode["version"] + "+codex.20261031"):
            with self.subTest(valid=valid):
                self.assertRegex(valid, pattern)
        for invalid in (
            zcode["version"] + r"\codex\.1",
            zcode["version"] + "+codex.",
            zcode["version"] + "+other.1",
            zcode["version"] + ".1",
        ):
            with self.subTest(invalid=invalid):
                self.assertNotRegex(invalid, pattern)

    def test_only_declared_plugin_local_skills_escape_vendor_lock(self) -> None:
        lock = json.loads((ROOT / "skills.lock.json").read_text(encoding="utf-8"))
        local = json.loads((ROOT / "plugin-local-skills.json").read_text(encoding="utf-8"))
        managed = {name for source in lock["sources"] for name in source["skills"]}
        actual = {path.name for path in (ROOT / "skills").iterdir() if (path / "SKILL.md").is_file()}
        self.assertEqual(actual - managed, set(local["skills"]))


if __name__ == "__main__":
    unittest.main()
