#!/usr/bin/env python3
"""Every plugin-local skill is declared, discoverable, and within size limits."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PluginLocalSkillsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = json.loads((ROOT / "plugin-local-skills.json").read_text(encoding="utf-8"))

    def test_registry_declares_known_local_skills(self) -> None:
        self.assertEqual(["comfy-harness", "comfy-design-loop", "comfy-local-setup"], self.registry["skills"])

    def test_each_local_skill_has_valid_skill_md(self) -> None:
        for name in self.registry["skills"]:
            skill_md = ROOT / "skills" / name / "SKILL.md"
            self.assertTrue(skill_md.is_file(), f"missing {skill_md}")
            text = skill_md.read_text(encoding="utf-8")
            self.assertLess(len(text.splitlines()), 500, f"{name}/SKILL.md exceeds 500 lines")
            self.assertTrue(text.startswith("---"), f"{name}/SKILL.md lacks frontmatter")
            frontmatter = text.split("---", 2)[1]
            self.assertIn(f"name: {name}", frontmatter, f"{name}/SKILL.md name mismatch")
            description = next(
                (line for line in frontmatter.splitlines() if line.startswith("description:")),
                "",
            )
            self.assertTrue(len(description) > len("description: "), f"{name}/SKILL.md description too short")


if __name__ == "__main__":
    unittest.main()
