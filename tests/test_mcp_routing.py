#!/usr/bin/env python3
"""Local-first MCP routing contract.

Comfy Design defaults to the local ``comfy-mcp`` server and keeps the hosted
``comfy-cloud`` server as an escalation path for the cloud-only tool surface.
These tests pin that wiring so a manifest edit cannot silently flip the default
or drop the escalation path, and they front-load two market-repo checks that
would otherwise abort ``bump-plugin.mjs`` halfway through a release.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LOCAL = "comfy-mcp"
CLOUD = "comfy-cloud"
BOOTSTRAP = "scripts/comfy_mcp_bootstrap.py"
CLOUD_URL = "https://cloud.comfy.org/mcp"

HOST_MANIFESTS = (
    ".codex-plugin/plugin.json",
    ".zcode-plugin/plugin.json",
    "kimi.plugin.json",
)

EXPECTED_COMMANDS = {
    "comfy-combine-people.md",
    "comfy-generate-3d.md",
    "comfy-generate-audio.md",
    "comfy-generate-image.md",
    "comfy-generate-video.md",
    "comfy-help.md",
    "comfy-remove-background.md",
    "comfy-search-models.md",
    "comfy-search-nodes.md",
    "comfy-search-templates.md",
    "comfy-upscale-image.md",
}


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class McpConnectionTests(unittest.TestCase):
    def test_codex_delegates_mcp_servers_to_dot_mcp_json(self) -> None:
        self.assertEqual("./.mcp.json", load(".codex-plugin/plugin.json")["mcpServers"])

    def test_dot_mcp_json_declares_local_first_then_escalation(self) -> None:
        servers = load(".mcp.json")["mcpServers"]
        self.assertEqual([LOCAL, CLOUD], list(servers))
        self.assertEqual("stdio", servers[LOCAL]["type"])
        self.assertEqual("http", servers[CLOUD]["type"])
        self.assertEqual(CLOUD_URL, servers[CLOUD]["url"])

    def test_escalation_path_keeps_paid_tools_gated(self) -> None:
        cloud = load(".mcp.json")["mcpServers"][CLOUD]
        self.assertEqual("prompt", cloud.get("default_tools_approval_mode"))

    def test_inline_manifests_declare_local_first_then_escalation(self) -> None:
        for relative in (".zcode-plugin/plugin.json", "kimi.plugin.json"):
            with self.subTest(manifest=relative):
                servers = load(relative)["mcpServers"]
                self.assertEqual([LOCAL, CLOUD], list(servers))
                self.assertEqual(CLOUD_URL, servers[CLOUD]["url"])

    def test_kimi_mcp_commands_are_path_relative(self) -> None:
        # Mirrors sync-marketplaces.mjs: command must be on PATH or start with
        # "./", and cwd must start with "./". Checked here so it fails locally
        # instead of aborting bump-plugin.mjs mid-release.
        for name, server in load("kimi.plugin.json")["mcpServers"].items():
            if "command" not in server:
                continue
            with self.subTest(server=name):
                self.assertFalse(
                    server["command"].startswith("/"),
                    "kimi MCP command must be on PATH or start with ./",
                )
                cwd = server.get("cwd")
                if cwd is not None:
                    self.assertTrue(cwd.startswith("./"), "kimi MCP cwd must start with ./")


class BootstrapLauncherTests(unittest.TestCase):
    def test_launcher_is_shipped(self) -> None:
        self.assertTrue((ROOT / BOOTSTRAP).is_file())

    def test_launcher_is_referenced_by_every_host(self) -> None:
        codex = load(".mcp.json")["mcpServers"][LOCAL]["args"]
        zcode = load(".zcode-plugin/plugin.json")["mcpServers"][LOCAL]["args"]
        kimi = load("kimi.plugin.json")["mcpServers"][LOCAL]["args"]
        self.assertEqual(["scripts/comfy_mcp_bootstrap.py"], codex)
        self.assertEqual(["${ZCODE_PLUGIN_ROOT}/scripts/comfy_mcp_bootstrap.py"], zcode)
        self.assertEqual(["./scripts/comfy_mcp_bootstrap.py"], kimi)


class DistributionShapeTests(unittest.TestCase):
    def test_commands_inventory_is_unchanged(self) -> None:
        actual = {p.name for p in (ROOT / "commands").glob("*.md")}
        self.assertEqual(EXPECTED_COMMANDS, actual)

    def test_descriptions_agree_across_the_plugin(self) -> None:
        # sync-marketplaces.mjs aborts the release unless each host manifest
        # description equals the marketplace index entry's. Compared here so a
        # mismatch surfaces before bump-plugin.mjs rewrites the version numbers.
        descriptions = {m: load(m)["description"] for m in HOST_MANIFESTS}
        index_entry = load(".agents/plugins/marketplace.json")["plugins"][0]
        descriptions[".agents/plugins/marketplace.json"] = index_entry["description"]
        self.assertEqual(1, len(set(descriptions.values())), f"description drift: {descriptions}")

    def test_short_descriptions_agree_across_the_plugin(self) -> None:
        shorts = {
            m: load(m)["interface"]["shortDescription"]
            for m in (".codex-plugin/plugin.json", "kimi.plugin.json")
        }
        index_entry = load(".agents/plugins/marketplace.json")["plugins"][0]
        shorts[".agents/plugins/marketplace.json"] = index_entry["interface"][
            "shortDescription"
        ]
        self.assertEqual(1, len(set(shorts.values())), f"shortDescription drift: {shorts}")


if __name__ == "__main__":
    unittest.main()
