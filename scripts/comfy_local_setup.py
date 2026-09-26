#!/usr/bin/env python3
"""Local configuration UI for the Comfy Design plugin (stitch-pattern).

Serves a small loopback-only web form where the user fills in:
  - the ComfyUI target host (default http://127.0.0.1:8188, LAN hosts welcome)
  - an OPTIONAL Comfy Cloud API key (escalation path / future local API nodes)

Values are stored in a per-user restricted config file (never printed, never
committed) and the ComfyUI target is applied to the vendored server's .env so
the bootstrap picks it up on the next start. Mirrors stitch-design-plugin's
setup flow: `check` for read-only status, `ui` to serve the form.

Usage:
    python3 scripts/comfy_local_setup.py check
    python3 scripts/comfy_local_setup.py ui [--port 8192] [--no-open]
"""
from __future__ import annotations

import argparse
import json
import os
import secrets as pysecrets
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = PLUGIN_ROOT / "vendor" / "comfyui-mcp-server"
ASSETS_DIR = PLUGIN_ROOT / "assets" / "setup"
ENV_PATH = SERVER_DIR / ".env"
DEFAULT_TARGET = "http://127.0.0.1:8188"

if os.name == "nt":
    CONFIG_PATH = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) \
        / "comfy-design-plugin" / "config.json"
else:
    CONFIG_PATH = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) \
        / "comfy-design-plugin" / "config.json"

ENV_TARGET_KEYS = ("COMFY_UI_SERVER_IP", "COMFY_UI_SERVER_HOST", "COMFY_UI_SERVER_PORT")


# ----------------------------- config storage -----------------------------

def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(values: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    # Restricted per-user file: create-with-0600 where the platform allows it.
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(values, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)
    if os.name != "nt":
        os.chmod(CONFIG_PATH, 0o600)


def _split_target(target: str) -> dict:
    parts = urllib.parse.urlsplit(target)
    host = parts.hostname or "127.0.0.1"
    port = str(parts.port or (443 if parts.scheme == "https" else 80))
    return {
        "COMFY_UI_SERVER_IP": f"{parts.scheme}://{parts.netloc}",
        "COMFY_UI_SERVER_HOST": host,
        "COMFY_UI_SERVER_PORT": port,
    }


def _read_env_file() -> dict:
    values = {}
    try:
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        pass
    return values


LOCALE_CHOICES = {"zh-CN", "en"}
SYNC_MODE_CHOICES = {"manual", "timed", "push"}


def apply_settings_to_env(target: str | None = None, locale: str | None = None, sync_mode: str | None = None) -> None:
    """Update the vendored server's .env (target and/or behaviour), preserving the rest.

    ``target=None`` performs a settings-only update (LOCALE / SYNC_MODE) without
    touching the COMFY_UI_* connection lines.
    """
    lines: list[str] = []
    if ENV_PATH.is_file():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    values = _split_target(target) if target else {}
    if locale in LOCALE_CHOICES:
        values["LOCALE"] = locale
    if sync_mode in SYNC_MODE_CHOICES:
        values["SYNC_MODE"] = sync_mode
    seen = set()
    out = []
    for line in lines:
        stripped = line.strip()
        key = stripped.split("=", 1)[0] if "=" in stripped and not stripped.startswith("#") else None
        if key in values:
            out.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, value in values.items():
        if key not in seen:
            out.append(f"{key}={value}")
    # Keep the plugin's recommended defaults present even on a fresh .env.
    for key, value in (("LOCALE", "zh-CN"), ("SYNC_MODE", "manual")):
        if not any(l.strip().startswith(f"{key}=") for l in out):
            out.append(f"{key}={value}")
    if out and out[-1].strip():
        out.append("")
    ENV_PATH.write_text("\n".join(out), encoding="utf-8", newline="\n")


def probe_target(target: str, timeout: float = 4.0) -> dict:
    try:
        url = target.rstrip("/") + "/system_stats"
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        devices = data.get("devices") or [{}]
        gpu = str(devices[0].get("name", "?"))
        # "cuda:0 NVIDIA GeForce RTX 3060 : cudaMallocAsync" → "NVIDIA GeForce RTX 3060"
        if gpu.startswith("cuda:") and " " in gpu:
            gpu = gpu.split(" ", 1)[1]
        gpu = gpu.split(" : ")[0].strip() or "?"
        vram = devices[0].get("vram_total", 0)
        return {
            "ok": True,
            "comfyui_version": data.get("system", {}).get("comfyui_version"),
            "gpu": gpu,
            "vram_gb": round(vram / (1024 ** 3), 1) if vram else None,
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def venv_ready() -> bool:
    exe = SERVER_DIR / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return exe.is_file()


# ----------------------------- check command -----------------------------

def cmd_check() -> int:
    cfg = load_config()
    target = cfg.get("comfyui_target") or _env_target() or DEFAULT_TARGET
    print(f"target: {target} ({'reachable' if probe_target(target)['ok'] else 'UNREACHABLE'})")
    print(f"venv: {'ready' if venv_ready() else 'missing -> python3 scripts/setup_comfy_mcp.py'}")
    print(f"cloud key: {'configured' if cfg.get('comfy_cloud_api_key') else 'not set (optional)'}")
    return 0


def _env_target() -> str | None:
    value = os.environ.get("COMFY_UI_SERVER_IP")
    if value:
        return value.rstrip("/")
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.is_file() else []:
        if line.strip().startswith("COMFY_UI_SERVER_IP="):
            return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    return None


# ----------------------------- ui server -----------------------------

CSRF = pysecrets.token_urlsafe(24)


class SetupHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence default stderr access log
        pass

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _check_csrf(self, payload: dict) -> bool:
        return payload.get("csrfToken") == CSRF

    def do_GET(self):  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path
        files = {"/": "index.html", "/app.js": "app.js", "/styles.css": "styles.css",
                 "/logo.png": "logo.png", "/official-logo.png": "official-logo.png"}
        name = files.get(path)
        if not name or not (ASSETS_DIR / name).is_file():
            self._json({"ok": False, "error": "not found"}, 404)
            return
        raw = (ASSETS_DIR / name).read_bytes()
        if name.endswith(".html"):
            ctype = "text/html; charset=utf-8"
        elif name.endswith(".js"):
            ctype = "text/javascript; charset=utf-8"
        elif name.endswith(".css"):
            ctype = "text/css; charset=utf-8"
        elif name.endswith(".png"):
            ctype = "image/png"
        else:
            ctype = "application/octet-stream"
        if name == "index.html":
            raw = raw.replace(b"__CSRF_TOKEN__", CSRF.encode())
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except (ValueError, json.JSONDecodeError):
            self._json({"ok": False, "error": "bad request"}, 400)
            return
        if not self._check_csrf(payload):
            self._json({"ok": False, "error": "csrf"}, 403)
            return
        path = urllib.parse.urlsplit(self.path).path

        if path == "/api/status":
            cfg = load_config()
            env_file = _read_env_file()
            target = cfg.get("comfyui_target") or _env_target() or DEFAULT_TARGET
            probe = probe_target(target)
            self._json({
                "ok": True,
                "target": target,
                "reachable": probe.get("ok", False),
                "probe": probe,
                "venv_ready": venv_ready(),
                "cloud_key_set": bool(cfg.get("comfy_cloud_api_key")),
                "locale": env_file.get("LOCALE", "zh-CN"),
                "sync_mode": env_file.get("SYNC_MODE", "manual"),
            })
        elif path == "/api/test":
            target = str(payload.get("target", "")).strip().rstrip("/")
            if not urllib.parse.urlsplit(target).scheme:
                self._json({"ok": False, "error": "需要 http(s):// 开头的完整地址"}, 400)
                return
            self._json(probe_target(target))
        elif path == "/api/settings":
            # Immediate-save endpoint for the low-risk behaviour switches.
            locale = payload.get("locale")
            sync_mode = payload.get("sync_mode")
            if locale is not None and locale not in LOCALE_CHOICES:
                self._json({"ok": False, "error": f"locale 仅支持 {sorted(LOCALE_CHOICES)}"}, 400)
                return
            if sync_mode is not None and sync_mode not in SYNC_MODE_CHOICES:
                self._json({"ok": False, "error": f"sync_mode 仅支持 {sorted(SYNC_MODE_CHOICES)}"}, 400)
                return
            if locale is None and sync_mode is None:
                self._json({"ok": False, "error": "没有可保存的设置"}, 400)
                return
            try:
                apply_settings_to_env(locale=locale, sync_mode=sync_mode)
                env_file = _read_env_file()
                self._json({"ok": True, "locale": env_file.get("LOCALE", "zh-CN"),
                            "sync_mode": env_file.get("SYNC_MODE", "manual")})
            except OSError as e:
                self._json({"ok": False, "error": f"写入 .env 失败：{e}"}, 500)
        elif path == "/api/save":
            target = str(payload.get("comfyui_target", "")).strip().rstrip("/")
            cloud_key = str(payload.get("comfy_cloud_api_key", "")).strip()
            locale = payload.get("locale")
            sync_mode = payload.get("sync_mode")
            if not urllib.parse.urlsplit(target).scheme:
                self._json({"ok": False, "error": "需要 http(s):// 开头的完整地址"}, 400)
                return
            if locale is not None and locale not in LOCALE_CHOICES:
                self._json({"ok": False, "error": f"locale 仅支持 {sorted(LOCALE_CHOICES)}"}, 400)
                return
            if sync_mode is not None and sync_mode not in SYNC_MODE_CHOICES:
                self._json({"ok": False, "error": f"sync_mode 仅支持 {sorted(SYNC_MODE_CHOICES)}"}, 400)
                return
            cfg = load_config()
            cfg["comfyui_target"] = target
            if cloud_key:
                cfg["comfy_cloud_api_key"] = cloud_key
            elif "comfy_cloud_api_key" in cfg and payload.get("clear_cloud_key"):
                del cfg["comfy_cloud_api_key"]
            save_config(cfg)
            apply_settings_to_env(target, locale=locale, sync_mode=sync_mode)
            self._json({"ok": True, "target": target,
                        "cloud_key_set": bool(cfg.get("comfy_cloud_api_key"))})
        elif path == "/api/setup_venv":
            if venv_ready():
                self._json({"ok": True, "already": True})
                return
            script = PLUGIN_ROOT / "scripts" / "setup_comfy_mcp.py"
            creationflags = 0x00000008 if os.name == "nt" else 0  # DETACHED_PROCESS
            subprocess.Popen([sys.executable, str(script)], cwd=str(PLUGIN_ROOT),
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, creationflags=creationflags)
            self._json({"ok": True, "started": True})
        else:
            self._json({"ok": False, "error": "not found"}, 404)


def cmd_ui(port: int, open_browser: bool) -> int:
    if not ASSETS_DIR.is_dir():
        print(f"✗ 缺少 {ASSETS_DIR}", file=sys.stderr)
        return 1
    httpd = ThreadingHTTPServer(("127.0.0.1", port), SetupHandler)
    url = f"http://127.0.0.1:{port}/"
    print(f"Comfy Design 本地配置页：{url}（仅本机可访问，Ctrl+C 退出）")
    if open_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Comfy Design 本地配置器")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="只读状态检查")
    ui = sub.add_parser("ui", help="启动本地配置页面")
    ui.add_argument("--port", type=int, default=8192)
    ui.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    if args.cmd == "check":
        return cmd_check()
    return cmd_ui(args.port, not args.no_open)


if __name__ == "__main__":
    sys.exit(main())
