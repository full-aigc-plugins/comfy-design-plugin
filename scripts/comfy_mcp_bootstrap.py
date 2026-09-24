#!/usr/bin/env python3
"""Default Comfy connection: launch the local ComfyUI MCP server (comfy-mcp).

The host spawns this script instead of ``comfy-mcp`` directly so that a missing
local toolchain produces one actionable diagnostic instead of a bare
``command not found``. When the toolchain is ready, this process hands its stdio
over to ``comfy-mcp`` and exits with its status.

The hosted ``comfy-cloud`` MCP is declared alongside and stays reachable: it is
the escalation path for the cloud-only tool surface (``partner_generate``,
``upload_file``, ``run_template``, ...). Routing policy lives in the
``comfy-harness`` skill.

Only comfy-mcp availability gates startup. comfy-cli and the ComfyUI workspace
are reported but never block: comfy-mcp starts fine without a running ComfyUI
(it exposes ``launch_comfyui``), and PATH-based detection of ``comfy`` can
false-negative across virtualenvs.

Deliberately: no logging to disk, no network access, no retries.
"""
from __future__ import annotations

import importlib.metadata
import os
import shutil
import subprocess
import sys

DIST = "comfy-mcp"
MODULE = "comfy_mcp"
CONSOLE = "comfy-mcp"


def _dist_version():
    # type: () -> str | None
    try:
        return importlib.metadata.version(DIST)
    except importlib.metadata.PackageNotFoundError:
        return None


def _comfy_mcp_argv():
    # type: () -> list[str] | None
    """Resolve how to start comfy-mcp: PATH console script, else module form."""
    script = shutil.which(CONSOLE)
    if script:
        return [script]
    if _dist_version() is not None:
        return [sys.executable, "-m", MODULE]
    return None


def _report(ready):
    # type: (bool) -> None
    comfy = shutil.which("comfy")
    version = _dist_version()
    lines = ["Comfy 本地 MCP（默认连接）预检："]
    if ready:
        lines.append("  \u2713 {}{}".format(CONSOLE, " " + version if version else ""))
    else:
        lines.append('  \u2717 {} 未安装 \u2192 pip install "{}"'.format(CONSOLE, DIST))
    if comfy:
        lines.append("  \u2713 comfy-cli \u2192 " + comfy)
    else:
        lines.append(
            '  \u2717 comfy-cli 不在 PATH \u2192 pip install "comfy-cli>=1.14.0"'
        )
    lines.append(
        "  ? ComfyUI 工作区 \u2192 comfy install && comfy set-default <path>"
    )
    lines.append(
        "  （仅第一项决定能否启动；工作区缺失由 comfy-mcp 的 launch_comfyui 处理）"
    )
    if not ready:
        lines.append(
            "云端 comfy-cloud 仍连接，可用作升级路径（partner_generate / upload_file 等）。"
        )
    print("\n".join(lines), file=sys.stderr)


def main():
    # type: () -> int
    argv = _comfy_mcp_argv()
    _report(argv is not None)
    if argv is None:
        return 1
    if "COMFY_BIN" not in os.environ:
        comfy = shutil.which("comfy")
        if comfy:
            os.environ["COMFY_BIN"] = comfy
    return subprocess.call(argv)


if __name__ == "__main__":
    sys.exit(main())
