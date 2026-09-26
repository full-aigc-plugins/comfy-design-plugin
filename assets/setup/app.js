const card = document.querySelector(".setup-card");
const csrf = card.dataset.csrf;
const targetInput = document.querySelector("#comfyui-target");
const cloudInput = document.querySelector("#cloud-key");
const testBtn = document.querySelector("#test");
const saveBtn = document.querySelector("#save");
const probeEl = document.querySelector("#probe");
const statusEl = document.querySelector("#status");
const venvLine = document.querySelector("#venv-line");
const setupVenvBtn = document.querySelector("#setup-venv");
const localeSelect = document.querySelector("#locale");
const syncModeSelect = document.querySelector("#sync-mode");
const advStatus = document.querySelector("#adv-status");

// ---- advanced settings: save immediately on change ----
let advTimer = null;
async function saveSettings(changed) {
  advStatus.className = "pill wait";
  advStatus.textContent = "保存中…";
  const data = await post("/api/settings", {
    locale: changed === "locale" ? localeSelect.value : undefined,
    sync_mode: changed === "sync-mode" ? syncModeSelect.value : undefined,
  });
  if (data.ok) {
    advStatus.className = "pill ok";
    advStatus.textContent = "已保存 ✓";
    clearTimeout(advTimer);
    advTimer = setTimeout(() => { advStatus.className = ""; advStatus.textContent = ""; }, 2500);
  } else {
    advStatus.className = "pill err";
    advStatus.textContent = "保存失败：" + (data.error || "未知错误");
  }
}
if (localeSelect) localeSelect.addEventListener("change", () => saveSettings("locale"));
if (syncModeSelect) syncModeSelect.addEventListener("change", () => saveSettings("sync-mode"));

async function post(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ csrfToken: csrf, ...body }),
  });
  try { return await response.json(); } catch { return {}; }
}

function render(el, message, state) {
  // state: "" plain muted text | "ok"/"err"/"wait" pill
  el.className = state ? `pill ${state}` : "";
  el.textContent = message;
}
const setProbe = (m, s) => render(probeEl, m, s);
const setStatus = (m, s) => render(statusEl, m, s);
const setVenv = (m, s) => render(venvLine, m, s);

// ---- on-load status ----
(async function loadStatus() {
  const data = await post("/api/status", {});
  if (!data.ok) return;
  if (!targetInput.value) targetInput.value = data.target;
  if (data.cloud_key_set) setStatus("Cloud Key 已配置 ✓ 留空保存不会清除", "ok");
  if (data.reachable) {
    const p = data.probe || {};
    setProbe(`已连接 · ComfyUI ${p.comfyui_version || "?"} · ${p.gpu || "?"}${p.vram_gb ? " · " + p.vram_gb + " GB" : ""}`, "ok");
  } else {
    setProbe("目标不可达：请确认 ComfyUI 已启动，或填写正确地址", "err");
  }
  if (data.venv_ready) {
    setVenv("运行环境已就绪 ✓", "ok");
  } else {
    setVenv("运行环境未安装：首次使用请一键安装", "wait");
  }
  setupVenvBtn.style.display = data.venv_ready ? "none" : "";
  if (localeSelect && data.locale) localeSelect.value = data.locale;
  if (syncModeSelect && data.sync_mode) syncModeSelect.value = data.sync_mode;
})();

// ---- test connection ----
testBtn.addEventListener("click", async () => {
  const target = targetInput.value.trim();
  if (!target) { setProbe("请先填写地址", "err"); return; }
  testBtn.disabled = true;
  setProbe("正在测试…", "wait");
  const data = await post("/api/test", { target });
  testBtn.disabled = false;
  if (data.ok) {
    setProbe(`连接成功 · ComfyUI ${data.comfyui_version || "?"} · ${data.gpu || "?"}${data.vram_gb ? " · " + data.vram_gb + " GB" : ""}`, "ok");
  } else {
    setProbe("连接失败：" + (data.error || "未知错误"), "err");
  }
});

// ---- save ----
saveBtn.addEventListener("click", async () => {
  const target = targetInput.value.trim();
  if (!target) { setStatus("请先填写 ComfyUI 地址", "err"); return; }
  saveBtn.disabled = true;
  setStatus("正在保存…", "wait");
  const data = await post("/api/save", {
    comfyui_target: target,
    comfy_cloud_api_key: cloudInput.value.trim(),
  });
  saveBtn.disabled = false;
  cloudInput.value = "";
  if (data.ok) {
    setStatus("保存成功 ✓ 下次启动本地 MCP 生效（" + data.target + "）", "ok");
  } else {
    setStatus("保存失败：" + (data.error || "未知错误"), "err");
  }
});

cloudInput.addEventListener("keydown", e => { if (e.key === "Enter") saveBtn.click(); });
targetInput.addEventListener("keydown", e => { if (e.key === "Enter") testBtn.click(); });

// ---- venv setup ----
setupVenvBtn.addEventListener("click", async () => {
  setupVenvBtn.disabled = true;
  setVenv("安装已启动（约 1-2 分钟）：完成后刷新本页确认", "wait");
  const data = await post("/api/setup_venv", {});
  if (!data.ok) {
    setVenv("启动失败：请手动运行 python3 scripts/setup_comfy_mcp.py", "err");
    setupVenvBtn.disabled = false;
  }
});
