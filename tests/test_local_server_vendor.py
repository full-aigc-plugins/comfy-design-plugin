#!/usr/bin/env python3
"""Vendored local MCP server (MetaBrain fusion) distribution checks.

The local ``comfy-mcp`` server is vendored source under
``vendor/comfyui-mcp-server/`` — not a PyPI install. These tests pin the
minimum distribution shape so a partial copy or an upstream refresh that drops
the fusion patches fails locally instead of at host startup.
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "vendor" / "comfyui-mcp-server"


class VendorShapeTests(unittest.TestCase):
    def test_vendored_source_is_complete(self) -> None:
        for relative in (
            "src/server.py",
            "src/__main__.py",
            "pyproject.toml",
            "LICENSE",
            ".env.example",
        ):
            with self.subTest(path=relative):
                self.assertTrue((SERVER / relative).is_file(), f"missing {relative}")

    def test_fusion_patch_markers_are_present(self) -> None:
        server_py = (SERVER / "src" / "server.py").read_text(encoding="utf-8")
        main_py = (SERVER / "src" / "__main__.py").read_text(encoding="utf-8")
        self.assertIn("FUSION PATCH #1", server_py, "background first-scan patch dropped")
        self.assertIn("both", main_py, "dual-transport patch dropped")
        self.assertIn('Mount("/", app=session_manager.handle_request)', main_py,
                      "no-redirect /mcp patch dropped")

    def test_fusion_patch3_tools_are_registered_and_dispatched(self) -> None:
        server_py = (SERVER / "src" / "server.py").read_text(encoding="utf-8")
        handlers_py = (SERVER / "src" / "handlers" / "tool_handlers.py").read_text(encoding="utf-8")
        for tool in ("TOOL_FREE_MEMORY", "TOOL_LIST_EMBEDDINGS",
                     "TOOL_LIST_LOCAL_TEMPLATES", "TOOL_UPLOAD_MASK"):
            with self.subTest(tool=tool):
                self.assertIn(tool, server_py, f"{tool} not registered")
                self.assertIn(tool, server_py.replace("settings.", ""),
                              f"{tool} not dispatched")
        for handler in ("handle_free_memory", "handle_list_embeddings",
                        "handle_list_local_templates", "handle_upload_mask"):
            self.assertIn(f"async def {handler}", handlers_py, f"{handler} missing")

    def test_mcp_sdk_is_pinned_to_compatible_line(self) -> None:
        reqs = (SERVER / "requirements-pinned.txt").read_text(encoding="utf-8")
        self.assertIn("mcp==1.9.4", reqs,
                      "unpinned mcp resolves to 2.x and crashes at import (PATCHES.md)")

    def test_patches_doc_exists(self) -> None:
        self.assertTrue((SERVER / "PATCHES.md").is_file())

    def test_runtime_state_is_gitignored(self) -> None:
        # .venv / .env are host-local runtime state; the repo must never track
        # them, but their local presence after setup is expected.
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for entry in ("vendor/comfyui-mcp-server/.venv/",
                      "vendor/comfyui-mcp-server/.env"):
            self.assertIn(entry, gitignore, f"{entry} missing from .gitignore")


class BootstrapContractTests(unittest.TestCase):
    def test_bootstrap_targets_vendored_server(self) -> None:
        bootstrap = (ROOT / "scripts" / "comfy_mcp_bootstrap.py").read_text(encoding="utf-8")
        self.assertIn("vendor", bootstrap)
        self.assertIn('"-m", "src"', bootstrap)

    def test_setup_script_installs_pinned_requirements(self) -> None:
        setup = (ROOT / "scripts" / "setup_comfy_mcp.py").read_text(encoding="utf-8")
        self.assertIn("requirements-pinned.txt", setup)


if __name__ == "__main__":
    unittest.main()
