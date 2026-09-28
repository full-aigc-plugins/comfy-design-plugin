#!/usr/bin/env python3
"""UserPromptSubmit hook: point Comfy-shaped requests at the plugin commands. Advisory only."""
from __future__ import annotations

import json
import re
import sys

INTENT_RE = re.compile(
    r"comfy|comfyui|工作流生成|文生图|文生视频|图生视频|换背景|去背景|放大图|3d\s*生成",
    re.IGNORECASE,
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    prompt = str(payload.get("prompt") or "") if isinstance(payload, dict) else ""
    if prompt.strip().startswith("/"):
        return 0
    if INTENT_RE.search(prompt):
        print(
            "提示：该请求疑似 Comfy 相关。可用 /comfy-help 总览或细分命令 "
            "(/comfy-generate-image /comfy-generate-video /comfy-generate-audio "
            "/comfy-generate-3d /comfy-search-models /comfy-search-nodes "
            "/comfy-search-templates /comfy-upscale-image /comfy-remove-background)；"
            "默认走本地 comfy-mcp，本地无等价工具时"
            "（partner_generate / upload_file / run_template 等）才升级 comfy-cloud。"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
