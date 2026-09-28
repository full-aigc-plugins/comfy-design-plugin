#!/usr/bin/env python3
"""SessionStart hook: report Comfy readiness, local path first. Advisory only."""
from __future__ import annotations

import importlib.metadata
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = next((c for c in Path(__file__).resolve().parents if (c / "plugin.json").is_file()), Path(__file__).resolve().parents[1])


def _local_readiness() -> list[str]:
    """Readiness of the DEFAULT connection (local comfy-mcp), most important first."""
    lines: list[str] = []
    try:
        version = importlib.metadata.version("comfy-mcp")
    except importlib.metadata.PackageNotFoundError:
        version = None
    console = shutil.which("comfy-mcp")
    if console or version:
        detail = version or console
        lines.append(f"本地 comfy-mcp（默认）: 就绪 ({detail})")
    else:
        lines.append('本地 comfy-mcp（默认）: 未安装 → pip install "comfy-mcp"')

    cli = shutil.which("comfy")
    if cli:
        lines.append(f"comfy-cli: {cli}")
    else:
        lines.append('comfy-cli: 不在 PATH → pip install "comfy-cli>=1.14.0"')

    lines.append("ComfyUI 工作区: 首次执行前 comfy install && comfy set-default <path>")
    return lines


def _cloud_readiness() -> list[str]:
    """Readiness of the ESCALATION connection (hosted comfy-cloud)."""
    if os.environ.get("COMFY_API_KEY", ""):
        return ["云端 comfy-cloud（升级路径）: COMFY_API_KEY 已设置"]
    return [
        "云端 comfy-cloud（升级路径）: 未配置凭据——升级到云端时才需要"
        "（ZCode userConfig 填 comfy_api_key，或 OAuth 登录）"
    ]


def main() -> int:
    lines: list[str] = [f"python3: {sys.version.split()[0]}"]
    lines += _local_readiness()
    lines += _cloud_readiness()
    lines.append("插件: 就绪" if (ROOT / "README.md").is_file() else "插件: 异常")

    try:
        sys.stdin.read()
    except Exception:
        pass
    print("Comfy 插件环境（本地优先）：" + "；".join(lines))
    return 0


if __name__ == "__main__":
    try:
        json.load(sys.stdin)
    except Exception:
        pass
    sys.exit(main())
