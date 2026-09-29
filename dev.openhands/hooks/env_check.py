#!/usr/bin/env python3
"""SessionStart hook: plugin self-integrity check (advisory).

Contract, identical to the sibling check_*_intent / check_closeout hooks:
only verifies files shipped with this package (and the interpreter version
the hook itself needs); external apps, third-party CLIs and credentials are
first-use setup owned by the skills. Everything intact -> print nothing,
exit 0. Something missing -> one warning line, still exit 0. Any stdin
(including malformed) is tolerated and never blocks a session.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = next((c for c in Path(__file__).resolve().parents if (c / "plugin.json").is_file()), Path(__file__).resolve().parents[1])


def main() -> int:
    problems: list[str] = []
    if not (ROOT / "scripts" / "comfy_mcp_bootstrap.py").is_file():
        problems.append("MCP bootstrap 脚本缺失（包不完整）")
    if problems:
        print("Comfy 环境告警：" + "；".join(problems))
    # Drain the hook payload so the host never sees a broken pipe.
    try:
        sys.stdin.read()
    except (OSError, ValueError, UnicodeDecodeError):
        pass
    return 0


if __name__ == "__main__":
    try:
        json.load(sys.stdin)
    except (ValueError, OSError):
        pass
    sys.exit(main())
