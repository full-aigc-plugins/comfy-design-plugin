#!/usr/bin/env python3
"""One-shot setup for the vendored ComfyUI MCP server (MetaBrain fusion).

Creates ``vendor/comfyui-mcp-server/.venv`` and installs the pinned dependency
set (``requirements-pinned.txt`` — includes the mandatory ``mcp==1.9.4`` pin;
see vendor/comfyui-mcp-server/PATCHES.md). Cross-platform; needs any Python 3.10+.

Usage:
    python3 scripts/setup_comfy_mcp.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_DIR = os.path.join(PLUGIN_ROOT, "vendor", "comfyui-mcp-server")
REQS = os.path.join(SERVER_DIR, "requirements-pinned.txt")


def _find_python() -> str | None:
    # type: () -> str | None
    candidates = [sys.executable]
    for name in ("python3", "python", "py"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    for candidate in candidates:
        if not candidate or "WindowsApps" in candidate:  # MS Store stub
            continue
        try:
            out = subprocess.run(
                [candidate, "-c", "import sys; print(sys.version_info >= (3, 10))"],
                capture_output=True, text=True, timeout=20,
            )
            if out.stdout.strip().endswith("True"):
                return candidate
        except Exception:
            continue
    return None


def _create_venv(python: str) -> int:
    # type: (str) -> int
    rc = subprocess.call([python, "-m", "venv", os.path.join(SERVER_DIR, ".venv")])
    if rc == 0:
        return 0
    # Some distributions (e.g. embedded Python) ship without the venv module.
    # uv creates venvs natively and only needs a base interpreter — use it when
    # present instead of failing.
    uv = shutil.which("uv")
    if uv:
        print("  python -m venv 不可用，改用 uv 创建 venv ...")
        return subprocess.call([uv, "venv", "--python", python,
                                os.path.join(SERVER_DIR, ".venv")])
    return rc


def main():
    # type: () -> int
    python = _find_python()
    if python is None:
        print("✗ 找不到 Python >= 3.10（Windows 的 Microsoft Store 占位 python 不算）\n"
              "  → 安装 Python 3.10+ 后重试", file=sys.stderr)
        return 1
    if not os.path.isfile(REQS):
        print(f"✗ 缺少 {REQS}", file=sys.stderr)
        return 1

    print(f"[1/2] 创建 venv（{python}）...")
    if _create_venv(python) != 0:
        print("✗ venv 创建失败（嵌入式 Python 且无 uv 兜底；安装标准 Python 3.10+ 或 pip install uv 后重试）",
              file=sys.stderr)
        return 1

    bin_dir = "Scripts" if os.name == "nt" else "bin"
    venv_dir = os.path.join(SERVER_DIR, ".venv")
    venv_python = os.path.join(venv_dir, bin_dir,
                               "python.exe" if os.name == "nt" else "python")
    print("[2/2] 安装锁定依赖（mcp==1.9.4 等，见 PATCHES.md）...")
    # uv first: faster, and uv-created venvs ship WITHOUT pip (the pip fallback
    # below only works for stdlib-venv-created environments).
    uv = shutil.which("uv")
    rc = 0
    if uv:
        rc = subprocess.call([uv, "pip", "install", "-p", venv_dir, "-r", REQS])
    else:
        rc = subprocess.call([venv_python, "-m", "pip", "install",
                              "--disable-pip-version-check", "-r", REQS])
    if rc == 0:
        # Editable-install the vendored package (no deps — already pinned above):
        # makes `python -m src` importable. Required because embedded-Python base
        # interpreters use a ._pth file that keeps cwd OUT of sys.path.
        if uv:
            rc = subprocess.call([uv, "pip", "install", "-p", venv_dir,
                                  "--no-deps", "-e", SERVER_DIR])
        else:
            rc = subprocess.call([venv_python, "-m", "pip", "install",
                                  "--disable-pip-version-check", "--no-deps",
                                  "-e", SERVER_DIR])
    if rc != 0:
        print("✗ 依赖安装失败，检查网络/镜像后重试", file=sys.stderr)
        return 1

    print("\n✓ 就绪。宿主即可经 scripts/comfy_mcp_bootstrap.py 启动本地 ComfyUI MCP。")
    print("  目标 ComfyUI 主机在 vendor/comfyui-mcp-server/.env 配置（默认 127.0.0.1:8188）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
