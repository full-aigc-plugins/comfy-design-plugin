#!/usr/bin/env python3
"""Default Comfy connection: launch the vendored ComfyUI MCP server (MetaBrain fusion).

The host spawns this script instead of the server directly so that a missing
toolchain produces one actionable diagnostic instead of a bare ``command not
found``. When everything is ready, this process hands its stdio over to the
vendored server (``python -m src``) and exits with its status.

The local server is a patched vendor of MetaBrain-Labs/ComfyUI-MCP-Server-Python
("workflows as tools"): 13 tools, workflow catalog/mounting, raw JSON submission,
cancel, uploads, asset download. See ``vendor/comfyui-mcp-server/PATCHES.md``
for the fusion patch list (background first-scan, dual transport, /mcp redirect
fix) and the mcp==1.9.4 dependency pin.

The hosted ``comfy-cloud`` MCP is declared alongside and stays reachable: it is
the escalation path for the cloud-only tool surface (``partner_generate``,
registry template/node search, ...). Routing policy lives in the
``comfy-harness`` skill.

Prechecks (fail fast, actionable):
  1. vendored venv exists            -> else "run scripts/setup_comfy_mcp.py"
  2. ComfyUI reachable at the target -> the server connects at startup and
     cannot launch ComfyUI itself; start ComfyUI first (or fix COMFY_UI_* in
     vendor/comfyui-mcp-server/.env)

Deliberately: no logging to disk, no network access beyond the one reachability
probe, no retries.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.request

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_DIR = os.path.join(PLUGIN_ROOT, "vendor", "comfyui-mcp-server")
ENV_PATH = os.path.join(SERVER_DIR, ".env")
DEFAULT_TARGET = "http://127.0.0.1:8188"

if os.name == "nt":
    _CONFIG_DIR = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~/AppData/Local")),
        "comfy-design-plugin")
else:
    _CONFIG_DIR = os.path.join(
        os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
        "comfy-design-plugin")
CONFIG_PATH = os.path.join(_CONFIG_DIR, "config.json")

_ENV_DEFAULTS = {
    "LOCALE": "zh-CN",
    "COMFY_UI_SERVER_IP": DEFAULT_TARGET,
    "COMFY_UI_SERVER_HOST": "127.0.0.1",
    "COMFY_UI_SERVER_PORT": "8188",
    "SYNC_MODE": "manual",
}


def _venv_python() -> str | None:
    # type: () -> str | None
    if os.name == "nt":
        candidate = os.path.join(SERVER_DIR, ".venv", "Scripts", "python.exe")
    else:
        candidate = os.path.join(SERVER_DIR, ".venv", "bin", "python")
    return candidate if os.path.isfile(candidate) else None


def _ensure_env_file() -> None:
    """Create a default .env on first run; never overwrite a user-edited one."""
    if os.path.isfile(ENV_PATH):
        return
    example = os.path.join(SERVER_DIR, ".env.example")
    lines = []
    if os.path.isfile(example):
        with open(example, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    if not lines:
        lines = ["# ComfyUI MCP Server configuration\n"]
    # Apply plugin defaults over the example values.
    out = []
    seen = set()
    for line in lines:
        stripped = line.strip()
        key = stripped.split("=", 1)[0] if "=" in stripped and not stripped.startswith("#") else None
        if key in _ENV_DEFAULTS:
            out.append(f"{key}={_ENV_DEFAULTS[key]}\n")
            seen.add(key)
        else:
            out.append(line)
    for key, value in _ENV_DEFAULTS.items():
        if key not in seen:
            out.append(f"{key}={value}\n")
    with open(ENV_PATH, "w", encoding="utf-8", newline="\n") as fh:
        fh.writelines(out)


def _env_value(name: str) -> str:
    # Real environment wins (host-injected COMFY_UI_* overrides); then .env file.
    if os.environ.get(name):
        return os.environ[name]
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith(f"{name}=") and not line.startswith("#"):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return _ENV_DEFAULTS.get(name, "")


def _config_target() -> str | None:
    """Target host saved by the local setup UI (scripts/comfy_local_setup.py ui)."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            value = json.load(fh).get("comfyui_target")
        return str(value).rstrip("/") if value else None
    except (OSError, ValueError):
        return None


def _probe_comfyui(url: str) -> bool:
    # type: (str) -> bool
    try:
        req = urllib.request.Request(url.rstrip("/") + "/system_stats", method="GET")
        with urllib.request.urlopen(req, timeout=4) as resp:
            return resp.status == 200
    except Exception:
        return False


def _report(venv_ok: bool, target: str, comfy_ok: bool) -> None:
    # type: (bool, str, bool) -> None
    lines = ["Comfy 本地 MCP（MetaBrain 融合版）预检："]
    if venv_ok:
        lines.append("  ✓ vendored venv 已就绪")
    else:
        lines.append("  ✗ venv 缺失 → python3 scripts/setup_comfy_mcp.py")
    lines.append(f"  ? ComfyUI 目标 → {target}" + ("（✓ 可达）" if comfy_ok else "（✗ 不可达）"))
    if not comfy_ok:
        lines.append("    本服务无法自行拉起 ComfyUI：请先启动 ComfyUI，")
        lines.append("    或修改目标主机（python3 scripts/comfy_local_setup.py ui 打开配置页）")
    lines.append(
        "  （venv 决定能否启动；ComfyUI 不可达时启动会在连接阶段失败）"
    )
    if not venv_ok or not comfy_ok:
        lines.append(
            "云端 comfy-cloud 仍连接，可用作升级路径（partner_generate / 注册表检索等）。"
        )
    print("\n".join(lines), file=sys.stderr)


def main():
    # type: () -> int
    python = _venv_python()
    _ensure_env_file()
    # Target resolution priority: host env > setup-UI config > .env > default.
    target = (os.environ.get("COMFY_UI_SERVER_IP")
              or _config_target()
              or _env_value("COMFY_UI_SERVER_IP")
              or DEFAULT_TARGET)
    comfy_ok = _probe_comfyui(target)
    _report(python is not None, target, comfy_ok)
    if python is None:
        return 1
    if not comfy_ok:
        return 2

    import urllib.parse as _up
    env = dict(os.environ)
    # Host-injected target wins over .env (python-dotenv does not override).
    parts = _up.urlsplit(target)
    resolved = {
        "COMFY_UI_SERVER_IP": f"{parts.scheme}://{parts.netloc}",
        "COMFY_UI_SERVER_HOST": parts.hostname or "127.0.0.1",
        "COMFY_UI_SERVER_PORT": str(parts.port or (443 if parts.scheme == "https" else 80)),
    }
    for name, value in resolved.items():
        env[name] = value

    return subprocess.call([python, "-m", "src"], cwd=SERVER_DIR, env=env)


if __name__ == "__main__":
    sys.exit(main())
