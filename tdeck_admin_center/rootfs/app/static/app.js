
const state = {
  contracts: null,
  workspace: null,
  activeDeviceIndex: 0,
  transport: {
    api_base_resolved: "",
    last_api_error: "",
    last_status_code: 0,
    last_path: "",
    attempts: 0,
  },
  entities: {
    page: 1,
    page_size: 100,
    pages: 1,
    total: 0,
    sort: "entity_id",
    controller: null,
    selected: "",
    jobId: "",
    jobPolling: false,
    jobPollId: "",
    jobStartedAt: 0,
  },
  activeMappingInput: null,
  searchDebounce: null,
  latestRelease: null,
  firmwareStatus: null,
  bootErrors: [],
  uiMode: "guided",
  guidedStep: 0,
  layoutPages: {},
  themePalettes: [],
  templateCatalog: {},
  dashboardSummary: null,
  cameraAutodetect: null,
  additionalCollection: "weather_metrics",
};

const WEATHER_FIELDS = [
  ["entity_wx_main", "Main Weather Entity"],
  ["entity_wx_condition_sensor", "Condition Sensor"],
  ["entity_wx_weather_sensor", "Weather Text Sensor"],
  ["entity_wx_temp_sensor", "Temperature Sensor"],
  ["entity_wx_feels_sensor", "Feels-Like Sensor"],
  ["entity_wx_humidity_sensor", "Humidity Sensor"],
  ["entity_wx_clouds_sensor", "Clouds Sensor"],
  ["entity_wx_pressure_sensor", "Pressure Sensor"],
  ["entity_wx_uv_sensor", "UV Sensor"],
  ["entity_wx_visibility_sensor", "Visibility Sensor"],
  ["entity_wx_wind_speed_sensor", "Wind Speed Sensor"],
  ["entity_wx_apparent_sensor", "Apparent Temp Sensor"],
  ["entity_wx_dew_point_sensor", "Dew Point Sensor"],
  ["entity_wx_precip_kind_sensor", "Precip Kind Sensor"],
  ["entity_wx_rain_intensity_sensor", "Rain Intensity Sensor"],
  ["entity_wx_snow_intensity_sensor", "Snow Intensity Sensor"],
  ["entity_wx_weather_code_sensor", "Weather Code Sensor"],
  ["entity_wx_wind_direction_sensor", "Wind Direction Sensor"],
  ["entity_wx_wind_gust_sensor", "Wind Gust Sensor"],
  ["entity_wx_today_high_sensor", "Today High Sensor"],
  ["entity_wx_today_low_sensor", "Today Low Sensor"],
  ["entity_ha_unit_system", "HA Unit System Sensor"],
];

const CLIMATE_FIELDS = [
  ["entity_sensi_climate", "Climate Entity"],
  ["entity_sensi_temperature_sensor", "Indoor Temperature Sensor"],
  ["entity_sensi_humidity_sensor", "Indoor Humidity Sensor"],
  ["entity_sensi_auto_cool_number", "Auto Cool Number"],
  ["entity_sensi_auto_heat_number", "Auto Heat Number"],
  ["entity_sensi_humidity_offset_number", "Humidity Offset Number"],
  ["entity_sensi_temperature_offset_number", "Temperature Offset Number"],
  ["entity_sensi_aux_heat_switch", "Aux Heat Switch"],
  ["entity_sensi_display_humidity_switch", "Display Humidity Switch"],
  ["entity_sensi_display_time_switch", "Display Time Switch"],
  ["entity_sensi_fan_support_switch", "Fan Support Switch"],
  ["entity_sensi_humidification_switch", "Humidification Switch"],
  ["entity_sensi_keypad_lockout_switch", "Keypad Lockout Switch"],
];

const READER_FIELDS = [
  ["entity_word_of_day_sensor", "Word Of Day Sensor"],
  ["entity_quote_of_hour_sensor", "Quote Of Hour Sensor"],
  ["entity_feed_bbc", "BBC Feed Entity"],
  ["entity_feed_dc", "DC Feed Entity"],
  ["entity_feed_loudoun", "Loudoun Feed Entity"],
];

const THEME_FIELDS = [
  ["theme_token_screen_bg", "Screen BG"],
  ["theme_token_surface", "Surface"],
  ["theme_token_surface_alt", "Surface Alt"],
  ["theme_token_action", "Action"],
  ["theme_token_action_soft", "Action Soft"],
  ["theme_token_text_primary", "Text Primary"],
  ["theme_token_text_dim", "Text Dim"],
  ["theme_token_ok", "Success"],
  ["theme_token_warn", "Warning"],
  ["theme_border_width", "Border Width"],
  ["theme_radius", "Radius"],
  ["theme_icon_mode", "Icon Mode"],
];

const FEATURE_KEYS = ["lights", "weather", "climate", "cameras", "reader", "gps"];
const COLLECTION_KEYS = ["lights", "cameras", "weather_metrics", "climate_controls", "reader_feeds", "system_entities"];
const COLLECTION_META = {
  lights: { label: "Lights", role: "light_slot", limitKey: "lights_max", defaultMax: 24 },
  cameras: { label: "Cameras", role: "camera_slot", limitKey: "cameras_max", defaultMax: 8 },
  weather_metrics: { label: "Weather Metrics", role: "", limitKey: "weather_metrics_max", defaultMax: 32 },
  climate_controls: { label: "Climate Controls", role: "", limitKey: "climate_controls_max", defaultMax: 24 },
  reader_feeds: { label: "Reader Feeds", role: "", limitKey: "reader_feeds_max", defaultMax: 16 },
  system_entities: { label: "System Entities", role: "", limitKey: "system_entities_max", defaultMax: 24 },
};
const THEME_TOKEN_KEYS = [
  "theme_token_screen_bg",
  "theme_token_surface",
  "theme_token_surface_alt",
  "theme_token_action",
  "theme_token_action_soft",
  "theme_token_text_primary",
  "theme_token_text_dim",
  "theme_token_ok",
  "theme_token_warn",
];

const DEFAULT_LAYOUT_PAGES = ["home", "lights", "weather", "climate", "reader", "cameras", "settings", "theme"];

function e(id) {
  return document.getElementById(id);
}

function deepClone(v) {
  return JSON.parse(JSON.stringify(v));
}

function asBool(value, fallback = false) {
  if (typeof value === "boolean") return value;
  if (value === undefined || value === null || value === "") return fallback;
  const s = String(value || "").toLowerCase();
  return ["1", "true", "yes", "on"].includes(s);
}

function safeText(v) {
  return String(v ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function clampInt(v, min, max) {
  const n = Number(v);
  if (!Number.isFinite(n)) return min;
  return Math.max(min, Math.min(max, Math.round(n)));
}

function colorToHex(value, fallback = "#4f8fe6") {
  const raw = String(value || "").trim().toLowerCase();
  if (!raw) return fallback;
  if (/^#[0-9a-f]{6}$/i.test(raw)) return raw;
  if (/^0x[0-9a-f]{6}$/i.test(raw)) return `#${raw.slice(2)}`;
  return fallback;
}

function hexToToken(value, fallback = "0x4F8FE6") {
  const raw = String(value || "").trim();
  if (/^#[0-9a-f]{6}$/i.test(raw)) return `0x${raw.slice(1).toUpperCase()}`;
  if (/^0x[0-9a-f]{6}$/i.test(raw)) return `0x${raw.slice(2).toUpperCase()}`;
  return fallback;
}

function setTransportStatus() {
  const out = e("transport_status");
  if (!out) return;
  const t = state.transport || {};
  const lines = [
    `API Base: ${t.api_base_resolved || "--"}`,
    `Last Path: ${t.last_path || "--"}`,
    `Last Status: ${t.last_status_code || "--"}`,
    `Attempts: ${t.attempts || 0}`,
  ];
  if (t.last_api_error) lines.push(`Last Error: ${t.last_api_error}`);
  out.textContent = lines.join("\n");
  out.style.color = t.last_api_error ? "#ffb4c0" : "";
}

function normalizeApiPath(path) {
  let p = String(path || "").trim();
  if (!p) return "api/health";
  p = p.replace(/^https?:\/\/[^/]+/i, "");
  p = p.replace(/^\.\//, "");
  p = p.replace(/^\/+/, "");
  if (!p.startsWith("api/")) p = `api/${p}`;
  return p;
}

function ingressBasePath() {
  const path = String(window.location.pathname || "/");
  if (path.endsWith("/")) return path;
  const idx = path.lastIndexOf("/");
  return idx >= 0 ? path.slice(0, idx + 1) : "/";
}

function buildApiCandidates(path) {
  const normalized = normalizeApiPath(path);
  const joined = `${ingressBasePath().replace(/\/+$/, "")}/${normalized}`.replace(/\/{2,}/g, "/");
  const candidates = [normalized, `./${normalized}`, joined];
  return Array.from(new Set(candidates));
}

function slugify(raw) {
  return String(raw || "tdeck")
    .toLowerCase()
    .replace(/-/g, "_")
    .replace(/[^a-z0-9_]/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "") || "tdeck";
}

function setStatus(text, isError = false) {
  const out = e("status_line");
  if (out) {
    out.textContent = text;
    out.style.color = isError ? "#ffb4c0" : "";
  }
  const strip = e("global_status_strip");
  if (strip) {
    const t = state.transport || {};
    const fw = state.firmwareStatus || {};
    strip.textContent =
      `Status: ${text}\n` +
      `Mode: ${state.uiMode}\n` +
      `API: ${t.last_status_code || "--"} ${t.last_path || "--"}\n` +
      `FW: ${fw.status_text || "--"} (${fw.method || "--"})`;
    strip.style.color = isError ? "#ffb4c0" : "";
  }
}

function setDiscoveryStatus(text, isError = false) {
  const out = e("discovery_status");
  if (!out) return;
  out.textContent = text;
  out.style.color = isError ? "#ffb4c0" : "";
}

function guidedStepFromDashboardAction(action) {
  const map = {
    connect_device: 0,
    map_entities: 2,
    theme: 3,
    layout: 4,
    deploy: 5,
    recover: 5,
  };
  return Number.isFinite(map[action]) ? map[action] : null;
}

function renderCameraAutodetect(cad) {
  const meta = e("camera_autodetect_meta");
  const list = e("camera_autodetect_list");
  const data = cad && typeof cad === "object" ? cad : {};
  const detected = Array.isArray(data.detected) ? data.detected : [];
  const accepted = Array.isArray(data.accepted) ? data.accepted : [];
  const ignored = Array.isArray(data.ignored) ? data.ignored : [];

  if (meta) {
    const scanAt = Number(data.last_scan_at || 0);
    const scanText = scanAt > 0 ? new Date(scanAt * 1000).toLocaleString() : "--";
    meta.textContent =
      `Enabled: ${asBool(data.enabled, true) ? "yes" : "no"}\n` +
      `Last scan: ${scanText}\n` +
      `Detected: ${detected.length} | Accepted: ${accepted.length} | Ignored: ${ignored.length}`;
  }

  if (list) {
    if (!detected.length) {
      list.textContent = "No camera candidates detected yet.";
      return;
    }
    const lines = detected.map((row, idx) => {
      const entity = row?.entity_id || "--";
      const name = row?.friendly_name || entity;
      const score = Number(row?.score || 0);
      const stateText = row?.state || "";
      const acceptedMark = accepted.includes(entity) ? " [accepted]" : "";
      const ignoredMark = ignored.includes(entity) ? " [ignored]" : "";
      return `${idx + 1}. ${name} -> ${entity} | score ${score}${stateText ? ` | state ${stateText}` : ""}${acceptedMark}${ignoredMark}`;
    });
    list.textContent = lines.join("\n");
  }
}

function renderDashboardSummary(summary) {
  const data = summary && typeof summary === "object" ? summary : {};
  const health = data.health || {};
  const validation = data.validation || {};
  const firmware = data.firmware_capabilities || {};
  const landing = data.landing_state || {};

  const summaryOut = e("dashboard_summary");
  if (summaryOut) {
    summaryOut.textContent =
      `Workspace: ${data.workspace_name || state.workspace?.workspace_name || "default"}\n` +
      `Device: ${data.device_slug || getDeviceSlug()}\n` +
      `HA Connected: ${health.ha_connected ? "yes" : "no"}\n` +
      `Discovery: ${health.discovery?.status || "--"} / ${health.discovery?.stage || "--"}\n` +
      `Onboarding Step: ${Number(landing.onboarding_step || 0) + 1}\n` +
      `Last Action: ${landing.last_action || "--"}`;
  }

  const valOut = e("dashboard_validation");
  if (valOut) {
    valOut.textContent = `Validation: ${validation.ok ? "PASS" : "FAIL"} | errors ${(validation.errors || []).length} | warnings ${(validation.warnings || []).length}`;
    valOut.style.color = validation.ok ? "" : "#ffb4c0";
  }

  const fwOut = e("dashboard_fw");
  if (fwOut) {
    fwOut.textContent =
      `Firmware method: ${firmware.recommended_method || "--"}\n` +
      `Build/install available: ${firmware.esphome_build_install_available ? "yes" : "no"}\n` +
      `Native update available: ${firmware.native_update_available ? "yes" : "no"}`;
  }

  state.cameraAutodetect = data.camera_autodetect || {};
  renderCameraAutodetect(state.cameraAutodetect);
}

async function refreshDashboardSummary() {
  const workspaceName = encodeURIComponent(state.workspace?.workspace_name || "default");
  const data = await apiGet(`api/dashboard/summary?workspace=${workspaceName}`);
  state.dashboardSummary = data;
  renderDashboardSummary(data);
}

async function runDashboardAction(action) {
  if (!action) return;
  const body = profilePayload();
  body.action = action;
  body.persist = true;
  const data = await apiPost("api/dashboard/action", body);
  state.workspace = ensureWorkspace(data.workspace || state.workspace, state.contracts.defaults || {});
  state.activeDeviceIndex = Number(data.active_device_index || state.workspace.active_device_index || 0);
  const step = guidedStepFromDashboardAction(action);
  if (step !== null) setGuidedStep(step);
  syncProfileToForm();
  await refreshDashboardSummary();
  setStatus(`Dashboard action '${action}' updated workspace${data.saved_workspace ? ` (${data.saved_workspace})` : ""}`);
}

async function scanCameraAutodetect() {
  const body = profilePayload();
  body.limit = 16;
  const data = await apiPost("api/cameras/autodetect", body);
  state.workspace = ensureWorkspace(data.workspace || state.workspace, state.contracts.defaults || {});
  state.activeDeviceIndex = Number(data.active_device_index || state.workspace.active_device_index || 0);
  state.cameraAutodetect = data.camera_autodetect || {};
  syncProfileToForm();
  renderCameraAutodetect(state.cameraAutodetect);
  setStatus(`Camera autodetect found ${data.detected_count || 0} candidates`);
}

async function acceptDetectedCameras() {
  const body = profilePayload();
  const data = await apiPost("api/cameras/accept_detected", body);
  state.workspace = ensureWorkspace(data.workspace || state.workspace, state.contracts.defaults || {});
  state.activeDeviceIndex = Number(data.active_device_index || state.workspace.active_device_index || 0);
  state.cameraAutodetect = data.camera_autodetect || {};
  syncProfileToForm();
  setStatus("Accepted detected cameras into camera collection");
}

async function ignoreDetectedCameras() {
  const body = profilePayload();
  const data = await apiPost("api/cameras/ignore_detected", body);
  state.workspace = ensureWorkspace(data.workspace || state.workspace, state.contracts.defaults || {});
  state.activeDeviceIndex = Number(data.active_device_index || state.workspace.active_device_index || 0);
  state.cameraAutodetect = data.camera_autodetect || {};
  syncProfileToForm();
  setStatus("Ignored currently detected camera candidates");
}

function currentProfile() {
  if (!state.workspace || !Array.isArray(state.workspace.devices) || state.workspace.devices.length === 0) {
    return null;
  }
  const idx = Math.max(0, Math.min(state.activeDeviceIndex, state.workspace.devices.length - 1));
  state.activeDeviceIndex = idx;
  state.workspace.active_device_index = idx;
  return state.workspace.devices[idx];
}

function ensureWorkspace(ws, fallbackProfile) {
  if (!ws || typeof ws !== "object") {
    ws = {
      schema_version: "4.0",
      workspace_name: "default",
      active_device_index: 0,
      devices: [deepClone(fallbackProfile)],
      mode_ui: { mode: "guided", guided_step: 0, show_advanced_diagnostics: false },
      templates: {},
      entity_collections: {},
      layout_pages: {},
      theme_studio: {},
      landing_state: {},
      camera_autodetect: {},
      deployment_workflow: {},
      bindings: {},
      layout: {},
      theme: {},
      deployment: {},
    };
  }
  if (!Array.isArray(ws.devices) || ws.devices.length === 0) {
    ws.devices = [deepClone(fallbackProfile)];
  }
  if (typeof ws.active_device_index !== "number") ws.active_device_index = 0;
  if (typeof ws.workspace_name !== "string" || !ws.workspace_name.trim()) ws.workspace_name = "default";
  if (!ws.deployment || typeof ws.deployment !== "object") ws.deployment = {};
  if (!ws.mode_ui || typeof ws.mode_ui !== "object") ws.mode_ui = { mode: "guided", guided_step: 0, show_advanced_diagnostics: false };
  if (!ws.layout_pages || typeof ws.layout_pages !== "object") ws.layout_pages = {};
  if (!ws.theme_studio || typeof ws.theme_studio !== "object") ws.theme_studio = {};
  if (!ws.landing_state || typeof ws.landing_state !== "object") ws.landing_state = {};
  if (!ws.camera_autodetect || typeof ws.camera_autodetect !== "object") ws.camera_autodetect = {};
  return ws;
}

function bindTabs() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      const panel = e(`tab-${tab}`);
      if (panel) panel.classList.add("active");
    });
  });
}

function setMode(mode) {
  state.uiMode = mode === "advanced" ? "advanced" : "guided";
  const guided = e("guided_shell");
  const advanced = e("advanced_shell");
  if (guided) guided.classList.toggle("hidden", state.uiMode !== "guided");
  if (advanced) advanced.classList.toggle("hidden", state.uiMode !== "advanced");
  e("mode_guided_btn")?.classList.toggle("active", state.uiMode === "guided");
  e("mode_advanced_btn")?.classList.toggle("active", state.uiMode === "advanced");
  if (state.workspace) {
    state.workspace.mode_ui = state.workspace.mode_ui || {};
    state.workspace.mode_ui.mode = state.uiMode;
  }
  try {
    window.localStorage.setItem("tdeck_admin_mode", state.uiMode);
  } catch (_err) {}
  setStatus(`Switched to ${state.uiMode} mode`);
}

function setGuidedStep(step) {
  const max = 5;
  state.guidedStep = Math.max(0, Math.min(max, Number(step || 0)));
  document.querySelectorAll(".guided-step-btn").forEach((btn, idx) => {
    btn.classList.toggle("active", idx === state.guidedStep);
  });
  document.querySelectorAll(".guided-panel").forEach((panel, idx) => {
    panel.classList.toggle("active", idx === state.guidedStep);
  });
  const ind = e("guided_step_indicator");
  if (ind) ind.textContent = `Step ${state.guidedStep + 1} of 6`;
  if (state.workspace) {
    state.workspace.mode_ui = state.workspace.mode_ui || {};
    state.workspace.mode_ui.guided_step = state.guidedStep;
  }
}

function bindModeControls() {
  e("mode_guided_btn")?.addEventListener("click", () => setMode("guided"));
  e("mode_advanced_btn")?.addEventListener("click", () => setMode("advanced"));
  document.querySelectorAll(".guided-step-btn").forEach((btn, idx) => {
    btn.addEventListener("click", () => setGuidedStep(idx));
  });
  e("guided_prev_btn")?.addEventListener("click", () => setGuidedStep(state.guidedStep - 1));
  e("guided_next_btn")?.addEventListener("click", () => setGuidedStep(state.guidedStep + 1));
}

async function apiRequest(method, path, body = undefined, signal = undefined) {
  const candidates = buildApiCandidates(path);
  let lastErr = null;
  state.transport.attempts = candidates.length;

  for (let idx = 0; idx < candidates.length; idx += 1) {
    const candidate = candidates[idx];
    const options = {
      method,
      signal,
      headers: {},
    };
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    try {
      const res = await fetch(candidate, options);
      let data = {};
      try {
        data = await res.json();
      } catch (_err) {
        data = {};
      }
      state.transport.last_path = candidate;
      state.transport.last_status_code = res.status;
      if (!res.ok || !data.ok) {
        const err = new Error(`${method} ${candidate} -> ${data.error || `${res.status} ${res.statusText}`}`);
        err.status = res.status;
        lastErr = err;
        state.transport.last_api_error = err.message;
        if (res.status === 404 && idx < candidates.length - 1) {
          continue;
        }
        throw err;
      }
      state.transport.last_api_error = "";
      const marker = "api/";
      const idx = candidate.lastIndexOf(marker);
      state.transport.api_base_resolved = idx >= 0 ? candidate.slice(0, idx + marker.length) : candidate;
      setTransportStatus();
      return data;
    } catch (err) {
      if (err?.name === "AbortError") throw err;
      lastErr = err;
      state.transport.last_path = candidate;
      state.transport.last_api_error = `${method} ${candidate} -> ${err?.message || "request_failed"}`;
      state.transport.last_status_code = Number(err?.status || 0);
      if (idx < candidates.length - 1) {
        continue;
      }
    }
  }

  setTransportStatus();
  throw lastErr || new Error("API request failed");
}

async function apiGet(path, signal = undefined) {
  return apiRequest("GET", path, undefined, signal);
}

async function apiPost(path, body) {
  return apiRequest("POST", path, body);
}
function renderDeviceSelector() {
  const select = e("device_select");
  if (!select) return;
  select.innerHTML = "";
  state.workspace.devices.forEach((deviceProfile, idx) => {
    const opt = document.createElement("option");
    const name = deviceProfile?.device?.friendly_name || deviceProfile?.device?.name || `Device ${idx + 1}`;
    opt.value = String(idx);
    opt.textContent = `${idx + 1}. ${name}`;
    if (idx === state.activeDeviceIndex) opt.selected = true;
    select.appendChild(opt);
  });
}

function applyProfileBasicsToForm() {
  const p = currentProfile();
  if (!p) return;
  const defaultVersion = state.contracts?.defaults?.app_release_version || "v0.23.0";
  e("workspace_name").value = state.workspace.workspace_name || "default";
  renderDeviceSelector();
  e("profile_name").value = p.profile_name || `device_${state.activeDeviceIndex + 1}`;
  e("device_name").value = p.device?.name || "";
  e("device_friendly_name").value = p.device?.friendly_name || "";
  e("git_ref").value = p.device?.git_ref || state.workspace.deployment?.git_ref || "stable";
  e("git_url").value = p.device?.git_url || state.workspace.deployment?.git_url || "https://github.com/jloops412/esphome-lilygo-tdeck-plus.git";
  e("app_release_version").value = p.settings?.app_release_version || state.workspace.deployment?.app_release_version || defaultVersion;
}

function renderFeatureToggles() {
  const p = currentProfile();
  const host = e("feature_toggles");
  host.innerHTML = "";
  FEATURE_KEYS.forEach((key) => {
    const id = `feature_${key}`;
    const checked = asBool(p.features?.[key]);
    host.insertAdjacentHTML("beforeend", `<label class="checkbox-row"><input type="checkbox" id="${id}" ${checked ? "checked" : ""}/> ${key}</label>`);
    e(id).addEventListener("change", (ev) => {
      p.features[key] = ev.target.checked;
    });
  });
}

function renderUiToggles() {
  const p = currentProfile();
  const keys = state.contracts?.ui_keys || [];
  const host = e("ui_toggles");
  host.innerHTML = "";
  keys.forEach((key) => {
    const id = `ui_toggle_${key}`;
    const checked = asBool(p.ui?.[key]);
    host.insertAdjacentHTML("beforeend", `<label class="checkbox-row"><input type="checkbox" id="${id}" ${checked ? "checked" : ""}/> ${key}</label>`);
    e(id).addEventListener("change", (ev) => {
      p.ui[key] = ev.target.checked;
    });
  });
}

function getTemplateCatalog() {
  if (state.templateCatalog && Object.keys(state.templateCatalog).length > 0) return state.templateCatalog;
  if (state.contracts?.templates && typeof state.contracts.templates === "object") return state.contracts.templates;
  return {};
}

function selectedTemplateDomain() {
  return (e("template_domain_select")?.value || "").trim();
}

function selectedTemplateItem() {
  return (e("template_item_select")?.value || "").trim();
}

function renderTemplateItems() {
  const catalog = getTemplateCatalog();
  const domain = selectedTemplateDomain();
  const rows = Array.isArray(catalog[domain]) ? catalog[domain] : [];
  const itemSelect = e("template_item_select");
  if (!itemSelect) return;
  itemSelect.innerHTML = "";
  rows.forEach((row, idx) => {
    const opt = document.createElement("option");
    opt.value = String(idx);
    opt.textContent = row?.name || `${domain} template ${idx + 1}`;
    itemSelect.appendChild(opt);
  });
  if (rows.length === 0) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "No templates available";
    itemSelect.appendChild(opt);
  }
  renderTemplatePreview();
}

function renderTemplateDomains() {
  const catalog = getTemplateCatalog();
  const select = e("template_domain_select");
  if (!select) return;
  const domains = Object.keys(catalog).sort();
  select.innerHTML = "";
  domains.forEach((domain) => {
    const opt = document.createElement("option");
    opt.value = domain;
    opt.textContent = domain;
    select.appendChild(opt);
  });
  if (!domains.length) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "No template domains";
    select.appendChild(opt);
  }
  renderTemplateItems();
}

function renderTemplatePreview() {
  const out = e("template_preview");
  if (!out) return;
  const catalog = getTemplateCatalog();
  const domain = selectedTemplateDomain();
  const itemIndex = Number(selectedTemplateItem());
  const rows = Array.isArray(catalog[domain]) ? catalog[domain] : [];
  const item = Number.isFinite(itemIndex) ? rows[itemIndex] : null;
  if (!item) {
    out.textContent = "No template selected.";
    return;
  }
  const lines = [`Template: ${item.name || `${domain} template`}`];
  const mappings = item.mappings && typeof item.mappings === "object" ? item.mappings : {};
  Object.keys(mappings).forEach((key) => {
    lines.push(`- ${key}: ${mappings[key]}`);
  });
  const slots = item.slots && typeof item.slots === "object" ? item.slots : {};
  if (Array.isArray(slots.lights) && slots.lights.length) lines.push(`- lights slots: ${slots.lights.length}`);
  if (Array.isArray(slots.cameras) && slots.cameras.length) lines.push(`- cameras slots: ${slots.cameras.length}`);
  out.textContent = lines.join("\n");
}

function applySelectedTemplate() {
  const p = currentProfile();
  if (!p) return;
  const catalog = getTemplateCatalog();
  const domain = selectedTemplateDomain();
  const itemIndex = Number(selectedTemplateItem());
  const rows = Array.isArray(catalog[domain]) ? catalog[domain] : [];
  const item = Number.isFinite(itemIndex) ? rows[itemIndex] : null;
  if (!item) {
    setStatus("No template selected", true);
    return;
  }
  const mappings = item.mappings && typeof item.mappings === "object" ? item.mappings : {};
  p.features = p.features || {};
  if (FEATURE_KEYS.includes(domain)) p.features[domain] = true;
  p.entities = p.entities || {};
  Object.keys(mappings).forEach((key) => {
    p.entities[key] = String(mappings[key] || "");
  });
  if (item.slots && typeof item.slots === "object") {
    if (Array.isArray(item.slots.lights)) {
      ensureCollections(p);
      p.entity_collections.lights = item.slots.lights.map((slot, idx) => ({
        id: `light_${idx + 1}`,
        name: slot?.name || `Light ${idx + 1}`,
        entity_id: slot?.entity || "",
        enabled: true,
      }));
    }
    if (Array.isArray(item.slots.cameras)) {
      ensureCollections(p);
      p.entity_collections.cameras = item.slots.cameras.map((slot, idx) => ({
        id: `camera_${idx + 1}`,
        name: slot?.name || `Camera ${idx + 1}`,
        entity_id: slot?.entity || "",
        enabled: true,
      }));
    }
  }
  if (["weather_metrics", "climate_controls", "reader_feeds", "system_entities"].includes(domain)) {
    ensureCollections(p);
    const entries = Object.entries(mappings).filter(([, v]) => String(v || "").trim());
    p.entity_collections[domain] = entries.map(([role, entityId], idx) => ({
      id: `${domain}_${idx + 1}`,
      name: role,
      role,
      entity_id: String(entityId || ""),
      enabled: true,
    }));
  }
  syncSlotsFromCollections(p);
  syncProfileToForm();
  setStatus(`Applied template '${item.name || domain}'`);
}

function markActiveInput(input) {
  state.activeMappingInput = input;
}

function ensureCollections(profile) {
  if (!profile.entity_collections || typeof profile.entity_collections !== "object") {
    profile.entity_collections = {
      lights: [],
      cameras: [],
      weather_metrics: [],
      climate_controls: [],
      reader_feeds: [],
      system_entities: [],
      limits: {},
    };
  }
  COLLECTION_KEYS.forEach((key) => {
    if (!Array.isArray(profile.entity_collections[key])) profile.entity_collections[key] = [];
  });
  if (!profile.entity_collections.limits || typeof profile.entity_collections.limits !== "object") {
    profile.entity_collections.limits = {};
  }
  Object.entries(COLLECTION_META).forEach(([key, meta]) => {
    const limitKey = meta.limitKey;
    const current = Number(profile.entity_collections.limits[limitKey] || meta.defaultMax);
    profile.entity_collections.limits[limitKey] = Number.isFinite(current) ? current : meta.defaultMax;
  }
  if (!profile.entity_collections.lights.length && Array.isArray(profile.slots?.lights)) {
    profile.slots.lights.forEach((slot, idx) => {
      profile.entity_collections.lights.push({
        id: `light_${idx + 1}`,
        name: slot.name || `Light ${idx + 1}`,
        entity_id: slot.entity || "",
        role: "light_slot",
        enabled: idx < Number(profile.slots?.light_slot_count || 0),
      });
    });
  }
  if (!profile.entity_collections.cameras.length && Array.isArray(profile.slots?.cameras)) {
    profile.slots.cameras.forEach((slot, idx) => {
      profile.entity_collections.cameras.push({
        id: `camera_${idx + 1}`,
        name: slot.name || `Camera ${idx + 1}`,
        entity_id: slot.entity || "",
        role: "camera_slot",
        enabled: idx < Number(profile.slots?.camera_slot_count || 0),
      });
    });
  }
}

function syncSlotsFromCollections(profile) {
  ensureCollections(profile);
  const enabledLights = profile.entity_collections.lights.filter((x) => asBool(x.enabled));
  const enabledCameras = profile.entity_collections.cameras.filter((x) => asBool(x.enabled));
  profile.slots = profile.slots || {};
  profile.slots.light_slot_count = Math.max(1, Math.min(8, enabledLights.length || 1));
  profile.slots.camera_slot_count = Math.max(0, Math.min(2, enabledCameras.length || 0));
  profile.slots.lights = [];
  profile.slots.cameras = [];
  for (let i = 0; i < 8; i += 1) {
    const item = enabledLights[i] || {};
    profile.slots.lights.push({
      name: item.name || `Light ${i + 1}`,
      entity: item.entity_id || `light.replace_me_slot_${i + 1}`,
    });
  }
  for (let i = 0; i < 2; i += 1) {
    const item = enabledCameras[i] || {};
    profile.slots.cameras.push({
      name: item.name || `Camera ${i + 1}`,
      entity: item.entity_id || `camera.replace_me_${i + 1}`,
    });
  }
}

function renderCollectionRows(collectionName, bodyId) {
  const p = currentProfile();
  if (!p) return;
  ensureCollections(p);
  const body = e(bodyId);
  if (!body) return;
  body.innerHTML = "";
  const rows = p.entity_collections?.[collectionName] || [];
  rows.forEach((item, idx) => {
    const rid = `${collectionName}_${idx}`;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><input id="${rid}_name" value="${safeText(item.name || "")}" /></td>
      <td><input id="${rid}_entity" value="${safeText(item.entity_id || "")}" /></td>
      <td><input type="checkbox" id="${rid}_enabled" ${asBool(item.enabled) ? "checked" : ""} /></td>
      <td>
        <button class="btn-soft" id="${rid}_up">Up</button>
        <button class="btn-soft" id="${rid}_down">Down</button>
        <button class="btn-warn" id="${rid}_del">Del</button>
      </td>
    `;
    body.appendChild(tr);
    e(`${rid}_name`)?.addEventListener("input", (ev) => {
      item.name = ev.target.value;
      syncSlotsFromCollections(p);
    });
    e(`${rid}_entity`)?.addEventListener("input", (ev) => {
      item.entity_id = ev.target.value;
      syncSlotsFromCollections(p);
    });
    e(`${rid}_entity`)?.addEventListener("focus", (ev) => markActiveInput(ev.target));
    e(`${rid}_enabled`)?.addEventListener("change", (ev) => {
      item.enabled = ev.target.checked;
      syncSlotsFromCollections(p);
    });
    e(`${rid}_up`)?.addEventListener("click", () => {
      if (idx <= 0) return;
      const temp = rows[idx - 1];
      rows[idx - 1] = rows[idx];
      rows[idx] = temp;
      syncSlotsFromCollections(p);
      renderCollections();
    });
    e(`${rid}_down`)?.addEventListener("click", () => {
      if (idx >= rows.length - 1) return;
      const temp = rows[idx + 1];
      rows[idx + 1] = rows[idx];
      rows[idx] = temp;
      syncSlotsFromCollections(p);
      renderCollections();
    });
    e(`${rid}_del`)?.addEventListener("click", () => {
      rows.splice(idx, 1);
      syncSlotsFromCollections(p);
      renderCollections();
    });
  });
}

function renderCollections() {
  const p = currentProfile();
  if (!p) return;
  ensureCollections(p);
  if (e("lights_max")) e("lights_max").value = String(p.entity_collections.limits?.lights_max || 24);
  if (e("cameras_max")) e("cameras_max").value = String(p.entity_collections.limits?.cameras_max || 8);
  renderCollectionRows("lights", "lights_collection_body");
  renderCollectionRows("cameras", "cameras_collection_body");
  renderAdditionalCollectionRows();
  const summaryNode = e("advanced_collection_summary");
  if (summaryNode) {
    summaryNode.textContent =
      `Lights: ${p.entity_collections.lights.length}\n` +
      `Cameras: ${p.entity_collections.cameras.length}\n` +
      `Weather Metrics: ${(p.entity_collections.weather_metrics || []).length}\n` +
      `Climate Controls: ${(p.entity_collections.climate_controls || []).length}\n` +
      `Reader Feeds: ${(p.entity_collections.reader_feeds || []).length}\n` +
      `System Entities: ${(p.entity_collections.system_entities || []).length}\n` +
      `Mapped to FW slots: lights=${p.slots?.light_slot_count || 0}/8 cameras=${p.slots?.camera_slot_count || 0}/2`;
  }
  const health = e("collections_summary");
  if (health) {
    health.textContent =
      `lights=${p.entity_collections.lights.length} | cameras=${p.entity_collections.cameras.length}\n` +
      `weather_metrics=${(p.entity_collections.weather_metrics || []).length} | climate_controls=${(p.entity_collections.climate_controls || []).length}\n` +
      `reader_feeds=${(p.entity_collections.reader_feeds || []).length} | system_entities=${(p.entity_collections.system_entities || []).length}`;
  }
}

function currentAdditionalCollection() {
  const selected = (e("additional_collection_select")?.value || state.additionalCollection || "weather_metrics").trim();
  if (!COLLECTION_KEYS.includes(selected) || selected === "lights" || selected === "cameras") return "weather_metrics";
  state.additionalCollection = selected;
  return selected;
}

function renderAdditionalCollectionRows() {
  const p = currentProfile();
  if (!p) return;
  ensureCollections(p);
  const body = e("additional_collection_body");
  if (!body) return;
  const collectionName = currentAdditionalCollection();
  const rows = p.entity_collections?.[collectionName] || [];
  const meta = COLLECTION_META[collectionName] || { label: collectionName, role: "", limitKey: `${collectionName}_max`, defaultMax: 24 };
  const maxNode = e("additional_collection_max");
  if (maxNode) maxNode.value = String(p.entity_collections?.limits?.[meta.limitKey] || meta.defaultMax);
  const metaNode = e("additional_collection_meta");
  if (metaNode) {
    metaNode.textContent = `${meta.label} | rows ${rows.length} | max ${p.entity_collections?.limits?.[meta.limitKey] || meta.defaultMax}`;
  }

  body.innerHTML = "";
  rows.forEach((item, idx) => {
    const rid = `${collectionName}_${idx}`;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><input id="${rid}_name" value="${safeText(item.name || "")}" /></td>
      <td><input id="${rid}_entity" value="${safeText(item.entity_id || "")}" /></td>
      <td><input id="${rid}_role" value="${safeText(item.role || "")}" placeholder="entity_* substitution key" /></td>
      <td><input type="checkbox" id="${rid}_enabled" ${asBool(item.enabled) ? "checked" : ""} /></td>
      <td>
        <button class="btn-soft" id="${rid}_up">Up</button>
        <button class="btn-soft" id="${rid}_down">Down</button>
        <button class="btn-warn" id="${rid}_del">Del</button>
      </td>
    `;
    body.appendChild(tr);
    e(`${rid}_name`)?.addEventListener("input", (ev) => {
      item.name = ev.target.value;
    });
    e(`${rid}_entity`)?.addEventListener("input", (ev) => {
      item.entity_id = ev.target.value;
    });
    e(`${rid}_entity`)?.addEventListener("focus", (ev) => markActiveInput(ev.target));
    e(`${rid}_role`)?.addEventListener("input", (ev) => {
      item.role = ev.target.value;
    });
    e(`${rid}_enabled`)?.addEventListener("change", (ev) => {
      item.enabled = ev.target.checked;
    });
    e(`${rid}_up`)?.addEventListener("click", () => {
      if (idx <= 0) return;
      const temp = rows[idx - 1];
      rows[idx - 1] = rows[idx];
      rows[idx] = temp;
      renderAdditionalCollectionRows();
    });
    e(`${rid}_down`)?.addEventListener("click", () => {
      if (idx >= rows.length - 1) return;
      const temp = rows[idx + 1];
      rows[idx + 1] = rows[idx];
      rows[idx] = temp;
      renderAdditionalCollectionRows();
    });
    e(`${rid}_del`)?.addEventListener("click", () => {
      rows.splice(idx, 1);
      renderAdditionalCollectionRows();
    });
  });
}

function addCollectionItem(collectionName) {
  const p = currentProfile();
  if (!p) return;
  ensureCollections(p);
  const meta = COLLECTION_META[collectionName] || { role: "", limitKey: `${collectionName}_max`, defaultMax: 24 };
  const limits = p.entity_collections?.limits || {};
  const max = Number(limits[meta.limitKey] || meta.defaultMax);
  const rows = p.entity_collections[collectionName];
  if (rows.length >= max) {
    setStatus(`${collectionName} reached configured max ${max}`, true);
    return;
  }
  const idx = rows.length + 1;
  rows.push({
    id: `${collectionName.slice(0, -1)}_${idx}`,
    name: `${collectionName.slice(0, -1).toUpperCase()} ${idx}`,
    entity_id: "",
    role: meta.role || "",
    enabled: true,
  });
  syncSlotsFromCollections(p);
  renderCollections();
}

function ensureLayoutPages() {
  if (!state.workspace) return;
  const defaults = state.contracts?.layout_defaults || {};
  if (!state.workspace.layout_pages || typeof state.workspace.layout_pages !== "object") {
    state.workspace.layout_pages = deepClone(defaults);
  }
  DEFAULT_LAYOUT_PAGES.forEach((pageId) => {
    if (!state.workspace.layout_pages[pageId]) {
      state.workspace.layout_pages[pageId] = deepClone(defaults[pageId] || {
        grid: { cols: 4, rows: 6 },
        sections: [
          { id: "header", x: 0, y: 0, w: 4, h: 1 },
          { id: "content", x: 0, y: 1, w: 4, h: 4 },
          { id: "footer", x: 0, y: 5, w: 4, h: 1 },
        ],
      });
    }
    if (!Array.isArray(state.workspace.layout_pages[pageId].sections)) {
      state.workspace.layout_pages[pageId].sections = [];
    }
  });
}

function currentLayoutPageId() {
  return (e("layout_page_select")?.value || "home").trim().toLowerCase() || "home";
}

function currentLayoutPageModel() {
  ensureLayoutPages();
  const pageId = currentLayoutPageId();
  return state.workspace.layout_pages[pageId];
}

function renderLayoutSections() {
  const body = e("layout_sections_body");
  if (!body) return;
  const pageId = currentLayoutPageId();
  const pageModel = currentLayoutPageModel() || { grid: { cols: 4, rows: 6 }, sections: [] };
  const grid = pageModel.grid || { cols: 4, rows: 6 };
  const sections = Array.isArray(pageModel.sections) ? pageModel.sections : [];
  body.innerHTML = "";

  sections.forEach((section, idx) => {
    const rid = `layout_${pageId}_${idx}`;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><input id="${rid}_id" value="${safeText(section.id || `section_${idx + 1}`)}" /></td>
      <td><input id="${rid}_x" type="number" min="0" max="${Math.max(0, Number(grid.cols || 4) - 1)}" value="${safeText(section.x ?? 0)}" /></td>
      <td><input id="${rid}_y" type="number" min="0" max="${Math.max(0, Number(grid.rows || 6) - 1)}" value="${safeText(section.y ?? 0)}" /></td>
      <td><input id="${rid}_w" type="number" min="1" max="${safeText(grid.cols || 4)}" value="${safeText(section.w ?? 1)}" /></td>
      <td><input id="${rid}_h" type="number" min="1" max="${safeText(grid.rows || 6)}" value="${safeText(section.h ?? 1)}" /></td>
      <td>
        <button class="btn-soft" id="${rid}_up">Up</button>
        <button class="btn-soft" id="${rid}_down">Down</button>
        <button class="btn-warn" id="${rid}_del">Del</button>
      </td>
    `;
    body.appendChild(tr);

    e(`${rid}_id`)?.addEventListener("input", (ev) => {
      section.id = String(ev.target.value || "").trim() || `section_${idx + 1}`;
    });
    e(`${rid}_x`)?.addEventListener("input", (ev) => {
      section.x = clampInt(ev.target.value, 0, Math.max(0, Number(grid.cols || 4) - 1));
      ev.target.value = String(section.x);
    });
    e(`${rid}_y`)?.addEventListener("input", (ev) => {
      section.y = clampInt(ev.target.value, 0, Math.max(0, Number(grid.rows || 6) - 1));
      ev.target.value = String(section.y);
    });
    e(`${rid}_w`)?.addEventListener("input", (ev) => {
      section.w = clampInt(ev.target.value, 1, Number(grid.cols || 4));
      ev.target.value = String(section.w);
    });
    e(`${rid}_h`)?.addEventListener("input", (ev) => {
      section.h = clampInt(ev.target.value, 1, Number(grid.rows || 6));
      ev.target.value = String(section.h);
    });

    e(`${rid}_up`)?.addEventListener("click", () => {
      if (idx <= 0) return;
      const temp = sections[idx - 1];
      sections[idx - 1] = sections[idx];
      sections[idx] = temp;
      renderLayoutSections();
    });
    e(`${rid}_down`)?.addEventListener("click", () => {
      if (idx >= sections.length - 1) return;
      const temp = sections[idx + 1];
      sections[idx + 1] = sections[idx];
      sections[idx] = temp;
      renderLayoutSections();
    });
    e(`${rid}_del`)?.addEventListener("click", () => {
      sections.splice(idx, 1);
      renderLayoutSections();
    });
  });

  const meta = e("layout_validation_meta");
  if (meta) meta.textContent = `Page ${pageId} grid ${grid.cols || 4}x${grid.rows || 6} | sections ${sections.length}`;
}

function addLayoutSection() {
  const pageModel = currentLayoutPageModel();
  const sections = Array.isArray(pageModel.sections) ? pageModel.sections : [];
  const idx = sections.length + 1;
  sections.push({
    id: `section_${idx}`,
    x: 0,
    y: Math.min(idx, Number(pageModel.grid?.rows || 6) - 1),
    w: Math.min(4, Number(pageModel.grid?.cols || 4)),
    h: 1,
  });
  pageModel.sections = sections;
  renderLayoutSections();
}

async function validateLayout() {
  const data = await apiPost("api/layout/validate", { layout_pages: state.workspace.layout_pages });
  const val = data.validation || {};
  const lines = [
    `Layout OK: ${val.ok}`,
    `Errors: ${(val.errors || []).length}`,
    ...(val.errors || []).map((x) => `- ${x}`),
    `Warnings: ${(val.warnings || []).length}`,
    ...(val.warnings || []).map((x) => `- ${x}`),
  ];
  const out = e("layout_validation_meta");
  if (out) out.textContent = lines.join("\n");
  setStatus(val.ok ? "Layout validation passed" : "Layout validation has errors", !val.ok);
}

async function saveLayout() {
  const body = profilePayload();
  body.layout_pages = state.workspace.layout_pages;
  const data = await apiPost("api/layout/save", body);
  state.workspace = ensureWorkspace(data.workspace || state.workspace, state.contracts.defaults || {});
  state.activeDeviceIndex = Number(data.active_device_index || state.workspace.active_device_index || 0);
  syncProfileToForm();
  setStatus(`Layout saved${data.saved_workspace ? ` (${data.saved_workspace})` : ""}`);
}

async function resetLayoutPage() {
  const page = currentLayoutPageId();
  if (!window.confirm(`Reset layout page '${page}' to defaults?`)) return;
  const body = profilePayload();
  body.page = page;
  const data = await apiPost("api/layout/reset_page", body);
  state.workspace = ensureWorkspace(data.workspace || state.workspace, state.contracts.defaults || {});
  state.activeDeviceIndex = Number(data.active_device_index || state.workspace.active_device_index || 0);
  syncProfileToForm();
  renderLayoutSections();
  setStatus(`Layout page '${page}' reset`);
}

function renderFieldGroup(containerId, fields, sourceObjName) {
  const p = currentProfile();
  const host = e(containerId);
  host.innerHTML = "";
  fields.forEach(([key, label]) => {
    const value = p[sourceObjName]?.[key] ?? "";
    const id = `${containerId}_${key}`;
    host.insertAdjacentHTML("beforeend", `<label>${label}<input id="${id}" value="${safeText(value)}" /></label>`);
    e(id).addEventListener("input", (ev) => {
      p[sourceObjName][key] = ev.target.value;
    });
    if (sourceObjName === "entities") {
      e(id).addEventListener("focus", (ev) => markActiveInput(ev.target));
    }
  });
}

function ensureThemeStudio(profile) {
  if (!profile.theme_studio || typeof profile.theme_studio !== "object") {
    profile.theme_studio = {};
  }
  if (!profile.theme || typeof profile.theme !== "object") {
    profile.theme = {};
  }
  if (!profile.theme_studio.custom_tokens || typeof profile.theme_studio.custom_tokens !== "object") {
    profile.theme_studio.custom_tokens = {};
  }
}

function getActiveThemeTokenKey() {
  const key = e("theme_token_select")?.value || THEME_TOKEN_KEYS[0];
  return THEME_TOKEN_KEYS.includes(key) ? key : THEME_TOKEN_KEYS[0];
}

function renderThemePalettes() {
  const select = e("theme_palette_select");
  if (!select) return;
  select.innerHTML = "";
  const rows = Array.isArray(state.themePalettes) ? state.themePalettes : [];
  rows.forEach((row) => {
    const opt = document.createElement("option");
    opt.value = row.id;
    opt.textContent = row.name || row.id;
    select.appendChild(opt);
  });
  if (!rows.length) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "No palettes";
    select.appendChild(opt);
  }
}

function selectedPaletteTokens() {
  const paletteId = (e("theme_palette_select")?.value || "").trim();
  const row = (state.themePalettes || []).find((x) => String(x.id || "") === paletteId);
  return row?.tokens && typeof row.tokens === "object" ? row.tokens : {};
}

function currentThemeTokensForPreview() {
  const p = currentProfile();
  if (!p) return {};
  ensureThemeStudio(p);
  const base = selectedPaletteTokens();
  const merged = {};
  THEME_TOKEN_KEYS.forEach((key) => {
    const fromCustom = p.theme_studio.custom_tokens?.[key];
    const fromTheme = p.theme?.[key];
    const fromBase = base?.[key];
    if (fromCustom) merged[key] = fromCustom;
    else if (fromTheme) merged[key] = fromTheme;
    else if (fromBase) merged[key] = fromBase;
  });
  return merged;
}

function syncThemePickerFromToken() {
  const p = currentProfile();
  if (!p) return;
  ensureThemeStudio(p);
  const key = getActiveThemeTokenKey();
  const tokens = currentThemeTokensForPreview();
  const hex = colorToHex(tokens[key], "#4f8fe6");
  if (e("theme_color_picker")) e("theme_color_picker").value = hex;
}

function renderThemePreviewCard(tokens, metaText = "") {
  const card = e("theme_preview_card");
  const meta = e("theme_preview_meta");
  if (meta) meta.textContent = metaText;
  if (!card || !tokens || typeof tokens !== "object") return;
  const bg = colorToHex(tokens.theme_token_screen_bg, "#101826");
  const surface = colorToHex(tokens.theme_token_surface, "#1b2434");
  const action = colorToHex(tokens.theme_token_action, "#4f8fe6");
  const text = colorToHex(tokens.theme_token_text_primary, "#edf4ff");
  const textDim = colorToHex(tokens.theme_token_text_dim, "#b7c9df");
  card.style.background = `linear-gradient(150deg, ${surface}, ${bg})`;
  card.style.borderColor = colorToHex(tokens.theme_token_surface_alt, "#2b3f57");
  card.style.color = text;
  const title = card.querySelector(".theme-preview-title");
  const body = card.querySelector(".theme-preview-body");
  if (title) title.style.color = text;
  if (body) {
    body.style.color = textDim;
    body.textContent = `Action ${action} | Text ${text} | Surface ${surface}`;
  }
}

async function previewTheme() {
  const p = currentProfile();
  if (!p) return;
  ensureThemeStudio(p);
  const key = getActiveThemeTokenKey();
  const custom = { ...(p.theme_studio.custom_tokens || {}) };
  custom[key] = hexToToken(e("theme_color_picker")?.value || "#4f8fe6");
  p.theme_studio.custom_tokens = custom;
  const paletteId = (e("theme_palette_select")?.value || "").trim();
  const data = await apiPost("api/theme/preview", { palette_id: paletteId, tokens: custom });
  const tokens = data.tokens || {};
  renderThemePreviewCard(tokens, `Contrast ratio: ${(data.contrast_ratio || 0).toFixed(2)} | AA normal: ${data.wcag_aa_normal ? "pass" : "fail"}`);
}

async function applyTheme() {
  const p = currentProfile();
  if (!p) return;
  ensureThemeStudio(p);
  const key = getActiveThemeTokenKey();
  const custom = { ...(p.theme_studio.custom_tokens || {}) };
  custom[key] = hexToToken(e("theme_color_picker")?.value || "#4f8fe6");
  p.theme_studio.custom_tokens = custom;
  const paletteId = (e("theme_palette_select")?.value || "").trim();
  const body = profilePayload();
  body.palette_id = paletteId;
  body.tokens = custom;
  const data = await apiPost("api/theme/apply", body);
  state.workspace = ensureWorkspace(data.workspace || state.workspace, state.contracts.defaults || {});
  state.activeDeviceIndex = Number(data.active_device_index || state.workspace.active_device_index || 0);
  syncProfileToForm();
  const ratio = Number(data.contrast_ratio || 0).toFixed(2);
  renderThemePreviewCard(data.tokens || {}, `Applied. Contrast ratio: ${ratio} | AA normal: ${data.wcag_aa_normal ? "pass" : "fail"}`);
  setStatus("Theme applied to active device profile");
}

function syncProfileToForm() {
  const p = currentProfile();
  if (!p) return;
  ensureThemeStudio(p);
  ensureLayoutPages();
  ensureCollections(p);
  applyProfileBasicsToForm();
  renderFeatureToggles();
  renderUiToggles();

  e("ha_base_url").value = p.settings.ha_base_url || "";
  e("camera_refresh_interval_s").value = p.settings.camera_refresh_interval_s || "60";
  e("camera_snapshot_dir").value = p.settings.camera_snapshot_dir || "/config/www/tdeck";
  e("camera_snapshot_enable").checked = asBool(p.settings.camera_snapshot_enable);

  renderCollections();
  state.cameraAutodetect = p.camera_autodetect || state.workspace?.camera_autodetect || {};
  renderCameraAutodetect(state.cameraAutodetect);
  renderFieldGroup("weather_fields", WEATHER_FIELDS, "entities");
  renderFieldGroup("climate_fields", CLIMATE_FIELDS, "entities");
  renderFieldGroup("reader_fields", READER_FIELDS, "entities");
  renderFieldGroup("theme_fields", THEME_FIELDS, "theme");
  renderTemplateDomains();
  renderThemePalettes();

  const activePalette = p.theme_studio?.active_palette || (state.themePalettes?.[0]?.id || "ocean_dark");
  if (e("theme_palette_select")) e("theme_palette_select").value = activePalette;
  if (e("theme_token_select") && !THEME_TOKEN_KEYS.includes(e("theme_token_select").value)) {
    e("theme_token_select").value = THEME_TOKEN_KEYS[0];
  }
  syncThemePickerFromToken();
  renderThemePreviewCard(currentThemeTokensForPreview(), "Preview not run yet.");

  if (e("layout_page_select") && !e("layout_page_select").value) {
    e("layout_page_select").value = "home";
  }
  renderLayoutSections();
  syncUpdateDefaultsFromProfile();
  refreshFirmwareStatus().catch((err) => {
    const node = e("firmware_update_result");
    if (node) node.textContent = `Firmware status error: ${err.message}`;
  });
}

function updateProfileFromTopFields() {
  const p = currentProfile();
  if (!p) return;
  state.workspace.workspace_name = e("workspace_name").value.trim() || "default";
  p.profile_name = e("profile_name").value.trim() || `device_${state.activeDeviceIndex + 1}`;
  p.device.name = e("device_name").value.trim() || "lilygo-tdeck-plus";
  p.device.friendly_name = e("device_friendly_name").value.trim() || "LilyGO T-Deck Plus";
  p.device.git_ref = e("git_ref").value.trim() || "stable";
  p.device.git_url = e("git_url").value.trim() || "https://github.com/jloops412/esphome-lilygo-tdeck-plus.git";
  p.settings.app_release_channel = "stable";
  p.settings.app_release_version = e("app_release_version").value.trim() || (state.contracts?.defaults?.app_release_version || "v0.23.0");
  ensureCollections(p);
  if (e("lights_max")) p.entity_collections.limits.lights_max = Number(e("lights_max").value || "24");
  if (e("cameras_max")) p.entity_collections.limits.cameras_max = Number(e("cameras_max").value || "8");
  if (e("additional_collection_max")) {
    const collection = currentAdditionalCollection();
    const meta = COLLECTION_META[collection] || { limitKey: `${collection}_max`, defaultMax: 24 };
    p.entity_collections.limits[meta.limitKey] = Number(e("additional_collection_max").value || String(meta.defaultMax));
  }
  p.settings.ha_base_url = e("ha_base_url").value.trim();
  p.settings.camera_refresh_interval_s = e("camera_refresh_interval_s").value.trim();
  p.settings.camera_snapshot_dir = e("camera_snapshot_dir").value.trim();
  p.settings.camera_snapshot_enable = e("camera_snapshot_enable").checked;
  if (e("ha_native_firmware_entity")) {
    p.settings.ha_native_firmware_entity = e("ha_native_firmware_entity").value.trim();
  }
  if (e("ha_installed_version_entity")) {
    p.settings.ha_app_version_entity = e("ha_installed_version_entity").value.trim();
  }
  state.workspace.deployment.git_ref = p.device.git_ref;
  state.workspace.deployment.git_url = p.device.git_url;
  state.workspace.deployment.app_release_version = p.settings.app_release_version;
  syncSlotsFromCollections(p);
  syncUpdateDefaultsFromProfile();
}
function addDevice() {
  const base = deepClone(currentProfile());
  const idx = state.workspace.devices.length + 1;
  base.profile_name = `device_${idx}`;
  base.device.name = `lilygo-tdeck-plus-${idx}`;
  base.device.friendly_name = `LilyGO T-Deck Plus ${idx}`;
  state.workspace.devices.push(base);
  state.activeDeviceIndex = state.workspace.devices.length - 1;
  state.workspace.active_device_index = state.activeDeviceIndex;
  syncProfileToForm();
  setStatus(`Added device ${base.device.friendly_name}`);
}

function cloneDevice() {
  const src = currentProfile();
  if (!src) return;
  const clone = deepClone(src);
  const idx = state.workspace.devices.length + 1;
  clone.profile_name = `${src.profile_name || "device"}_copy_${idx}`;
  clone.device.name = `${src.device?.name || "lilygo-tdeck-plus"}-${idx}`;
  clone.device.friendly_name = `${src.device?.friendly_name || "LilyGO T-Deck Plus"} Copy ${idx}`;
  state.workspace.devices.push(clone);
  state.activeDeviceIndex = state.workspace.devices.length - 1;
  state.workspace.active_device_index = state.activeDeviceIndex;
  syncProfileToForm();
  setStatus(`Cloned device to ${clone.device.friendly_name}`);
}

function removeDevice() {
  if (state.workspace.devices.length <= 1) {
    setStatus("Workspace must keep at least one device", true);
    return;
  }
  const p = currentProfile();
  if (!window.confirm(`Remove device '${p.device?.friendly_name || p.device?.name}'?`)) return;
  state.workspace.devices.splice(state.activeDeviceIndex, 1);
  state.activeDeviceIndex = Math.max(0, state.activeDeviceIndex - 1);
  state.workspace.active_device_index = state.activeDeviceIndex;
  syncProfileToForm();
  setStatus("Device removed");
}

function bindTopFieldEvents() {
  ["workspace_name", "profile_name", "device_name", "device_friendly_name", "git_ref", "git_url", "app_release_version", "ha_base_url", "camera_refresh_interval_s", "camera_snapshot_dir", "ha_installed_version_entity", "ha_native_firmware_entity"]
    .forEach((id) => {
      const node = e(id);
      if (node) node.addEventListener("input", updateProfileFromTopFields);
    });

  e("camera_snapshot_enable").addEventListener("change", updateProfileFromTopFields);

  e("device_select").addEventListener("change", (ev) => {
    state.activeDeviceIndex = Number(ev.target.value || "0");
    state.workspace.active_device_index = state.activeDeviceIndex;
    syncProfileToForm();
  });
  e("device_add_btn").addEventListener("click", addDevice);
  e("device_clone_btn").addEventListener("click", cloneDevice);
  e("device_remove_btn").addEventListener("click", removeDevice);

  e("lights_max")?.addEventListener("input", () => {
    updateProfileFromTopFields();
    renderCollections();
  });
  e("cameras_max")?.addEventListener("input", () => {
    updateProfileFromTopFields();
    renderCollections();
  });
  e("lights_add_btn")?.addEventListener("click", () => addCollectionItem("lights"));
  e("cameras_add_btn")?.addEventListener("click", () => addCollectionItem("cameras"));
  e("additional_collection_select")?.addEventListener("change", () => {
    state.additionalCollection = currentAdditionalCollection();
    renderAdditionalCollectionRows();
  });
  e("additional_collection_max")?.addEventListener("input", () => {
    updateProfileFromTopFields();
    renderAdditionalCollectionRows();
  });
  e("additional_collection_add_btn")?.addEventListener("click", () => {
    addCollectionItem(currentAdditionalCollection());
  });
}

function getDeviceSlug() {
  const p = currentProfile();
  return slugify(p?.device?.name || "lilygo-tdeck-plus");
}

function syncUpdateDefaultsFromProfile() {
  const slug = getDeviceSlug();
  const p = currentProfile();
  const appVersionEntity = p?.settings?.ha_app_version_entity?.trim() || `sensor.${slug}_app_version`;
  const nativeEntity = p?.settings?.ha_native_firmware_entity?.trim() || `update.${slug}_firmware`;
  if (e("ha_installed_version_entity")) {
    e("ha_installed_version_entity").value = appVersionEntity;
  }
  if (e("ha_native_firmware_entity")) {
    e("ha_native_firmware_entity").value = nativeEntity;
  }
}

function renderDomains(domains) {
  const select = e("domain_filter");
  select.innerHTML = "";
  const all = document.createElement("option");
  all.value = "";
  all.textContent = "all";
  select.appendChild(all);
  domains.forEach((row) => {
    const opt = document.createElement("option");
    opt.value = row.domain;
    opt.textContent = `${row.domain} (${row.count})`;
    select.appendChild(opt);
  });
}

function renderEntities(rows) {
  const body = e("entities_body");
  body.innerHTML = "";
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><code>${safeText(row.entity_id)}</code></td>
      <td>${safeText(row.friendly_name || "")}</td>
      <td>${safeText(row.state || "")}</td>
      <td>${safeText(row.unit || "")}</td>
      <td><button class="btn-soft use-entity-btn" data-entity="${safeText(row.entity_id)}">Use</button></td>
    `;
    body.appendChild(tr);
  });
  body.querySelectorAll(".use-entity-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.entities.selected = btn.dataset.entity || "";
      applySelectedEntityToActiveField();
    });
  });
}

function applySelectedEntityToActiveField() {
  if (!state.activeMappingInput) {
    setStatus("Select a mapping input first, then click Use.", true);
    return;
  }
  if (!state.entities.selected) {
    setStatus("Select an entity row with Use first.", true);
    return;
  }
  state.activeMappingInput.value = state.entities.selected;
  state.activeMappingInput.dispatchEvent(new Event("input", { bubbles: true }));
  setStatus(`Mapped ${state.entities.selected}`);
}

function formatJobText(job) {
  if (!job) return "Discovery idle";
  const status = job.status || "unknown";
  const stage = job.stage || status;
  const pct = Number(job.progress || 0);
  const rows = Number(job.rows || 0);
  const total = Number(job.total || 0);
  const duration = Number(job.duration_ms || 0);
  const err = job.error ? ` | error: ${job.error}` : "";
  return `Discovery ${status}/${stage} | ${pct}% | rows ${rows}${total ? `/${total}` : ""} | ${duration}ms${err}`;
}

async function startDiscoveryJob(force = false, options = {}) {
  const waitForCompletion = asBool(options.wait_for_completion, false);
  const data = await apiPost("api/discovery/jobs/start", { force });
  const job = data.job || null;
  if (job?.id) state.entities.jobId = job.id;
  setDiscoveryStatus(formatJobText(job), job?.status === "failed");
  if (job && ["queued", "running"].includes(job.status)) {
    if (waitForCompletion) {
      await pollDiscoveryJob(job.id);
    } else {
      pollDiscoveryJob(job.id).catch((err) => {
        setDiscoveryStatus(`Discovery poll error: ${err.message}`, true);
      });
    }
  }
  await Promise.all([loadDomains(), refreshEntities({ resetPage: true }), refreshHealth()]);
}

async function pollDiscoveryJob(jobId) {
  if (!jobId) return;
  if (state.entities.jobPolling && state.entities.jobPollId === jobId) return;
  state.entities.jobPolling = true;
  state.entities.jobPollId = jobId;
  state.entities.jobStartedAt = Date.now();
  let terminalStateReached = false;
  try {
    while (true) {
      const data = await apiGet(`api/discovery/jobs/${encodeURIComponent(jobId)}`);
      const job = data.job || {};
      setDiscoveryStatus(formatJobText(job), job.status === "failed");
      if (["completed", "failed", "cancelled"].includes(job.status)) {
        terminalStateReached = true;
        break;
      }
      if (state.entities.jobId && state.entities.jobId !== jobId) break;
      if (Date.now() - state.entities.jobStartedAt > 90000) {
        setDiscoveryStatus("Discovery timeout after 90s", true);
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 900));
    }
  } finally {
    if (state.entities.jobPollId === jobId) {
      state.entities.jobPolling = false;
      state.entities.jobPollId = "";
    }
    if (terminalStateReached) {
      await Promise.all([loadDomains(), refreshEntities({ resetPage: false }), refreshHealth()]);
    }
  }
}

async function cancelDiscoveryJob() {
  const jobId = state.entities.jobId;
  if (!jobId) {
    setStatus("No active discovery job to cancel.");
    return;
  }
  const data = await apiPost(`api/discovery/jobs/${encodeURIComponent(jobId)}/cancel`, {});
  const job = data.job || null;
  if (job && ["cancelled", "completed", "failed"].includes(job.status || "")) {
    state.entities.jobId = "";
  }
  setDiscoveryStatus(formatJobText(job), (job?.status || "") === "failed");
  setStatus(`Discovery job ${job?.status || "updated"}`);
  await Promise.all([loadDomains(), refreshEntities({ resetPage: false }), refreshHealth()]);
}

async function refreshHealth() {
  const data = await apiGet("api/health");
  const cache = data.cache || {};
  const haStatus = data.ha_connected ? "connected" : `error (${data.ha_error || "unreachable"})`;
  const transport = data.transport || {};
  const discovery = data.discovery || {};
  const firmwareCaps = data.firmware_capability_summary || {};
  e("health_summary").textContent =
    `Addon version: ${data.addon_version || "--"}\n` +
    `Addon updated flag: ${data.addon_updated_since_last_run ? "yes" : "no"}\n` +
    `Firmware summary: ${data.firmware_status_summary || "--"}\n` +
    `Firmware method: ${firmwareCaps.recommended_method || "--"}\n` +
    `HA: ${haStatus}\n` +
    `Transport path: ${transport.request_path || "--"}\n` +
    `Transport base hint: ${transport.api_base_hint || "--"}\n` +
    `Discovery status: ${discovery.status || "--"}\n` +
    `Discovery stage: ${discovery.stage || "--"}\n` +
    `Entities cached: ${cache.entities || 0}\n` +
    `Domains: ${cache.domains || 0}\n` +
    `Cache age: ${cache.cache_age_ms || 0} ms\n` +
    `Last fetch duration: ${cache.last_duration_ms || 0} ms\n` +
    `Profiles: ${data.profiles?.count || 0} | Workspaces: ${data.workspaces?.count || 0}`;
  if (data.discovery_job) setDiscoveryStatus(formatJobText(data.discovery_job), data.discovery_job.status === "failed");
  setTransportStatus();
}

async function refreshRuntimeDiagnostics() {
  const data = await apiGet("api/diagnostics/runtime");
  const out = e("runtime_diag");
  if (!out) return;
  const lines = [
    `Selected device: ${data.selected_device_slug || "--"}`,
    `Last action: ${data.runtime_state?.last_firmware_action?.status || "--"}`,
    `Last error: ${data.runtime_state?.last_firmware_action?.error || "--"}`,
    `Discovery cache stale: ${data.discovery_cache?.stale ? "yes" : "no"}`,
    `Discovery rows: ${data.discovery_cache?.last_total || data.discovery_cache?.rows || 0}`,
  ];
  out.textContent = lines.join("\n");
}

function firmwareStatusQuery() {
  const p = currentProfile();
  const slug = getDeviceSlug();
  const targetVersion = encodeURIComponent(p?.settings?.app_release_version || (state.contracts?.defaults?.app_release_version || "v0.23.0"));
  const nativeEntity = encodeURIComponent((p?.settings?.ha_native_firmware_entity || "").trim());
  const appVersionEntity = encodeURIComponent((p?.settings?.ha_app_version_entity || "").trim());
  return `api/firmware/status?device_slug=${encodeURIComponent(slug)}&target_version=${targetVersion}&native_firmware_entity=${nativeEntity}&app_version_entity=${appVersionEntity}`;
}

function firmwareCapabilitiesQuery() {
  const p = currentProfile();
  const slug = getDeviceSlug();
  const targetVersion = encodeURIComponent(p?.settings?.app_release_version || (state.contracts?.defaults?.app_release_version || "v0.23.0"));
  const nativeEntity = encodeURIComponent((p?.settings?.ha_native_firmware_entity || "").trim());
  const appVersionEntity = encodeURIComponent((p?.settings?.ha_app_version_entity || "").trim());
  return `api/firmware/capabilities?device_slug=${encodeURIComponent(slug)}&target_version=${targetVersion}&native_firmware_entity=${nativeEntity}&app_version_entity=${appVersionEntity}`;
}

async function refreshFirmwareStatus() {
  const [data, caps] = await Promise.all([apiGet(firmwareStatusQuery()), apiGet(firmwareCapabilitiesQuery())]);
  state.firmwareStatus = data;
  const capabilities = caps.capabilities || {};
  const lines = [
    `Status: ${data.status_text || "--"}`,
    `Target: ${data.target_version || "--"}`,
    `Installed: ${data.installed_version || "--"}`,
    `Method: ${data.method || capabilities.recommended_method || "--"}`,
    `Native Entity: ${data.native_firmware_entity || "--"} (${data.native_state || "--"})`,
    `Version Entity: ${data.app_version_entity || "--"}`,
    `ESPHome Build/Install: ${capabilities.esphome_build_install_available ? "yes" : "no"}`,
    `Native Update Path: ${capabilities.native_update_available ? "yes" : "no"}`,
    `Addon Updated Flag: ${data.runtime?.addon_updated_since_last_run ? "yes" : "no"}`,
  ];
  if (Array.isArray(data.issues) && data.issues.length > 0) {
    lines.push(`Issues: ${data.issues.join(" | ")}`);
  }
  e("firmware_status_summary").textContent = lines.join("\n");

  const banner = e("firmware_pending_banner");
  if (data.status_text === "unknown_legacy") {
    banner.textContent = "Firmware version is unknown (legacy install). Use Backup + Build/Install or Backup + Install to bring this device under managed updates.";
    banner.style.color = "#ffd38a";
  } else if (data.firmware_pending) {
    banner.textContent = "Add-on updated and firmware is pending. Update firmware to align with the current app release.";
    banner.style.color = "#ffd38a";
  } else if ((data.method || capabilities.recommended_method) === "manual_fallback") {
    banner.textContent = "No automatic firmware path detected. Use Manual Next Steps for guided recovery.";
    banner.style.color = "#ffb4c0";
  } else {
    banner.textContent = "Firmware is up to date with the selected app release target.";
    banner.style.color = "";
  }

  const autoBtn = e("fw_workflow_auto_btn");
  const buildBtn = e("fw_workflow_build_btn");
  const installBtn = e("fw_workflow_install_btn");
  const manualBtn = e("fw_manual_steps_btn");
  const canBuild = !!capabilities.esphome_build_install_available;
  const canInstall = !!capabilities.native_update_available || !!capabilities.esphome_install_available;
  if (autoBtn) autoBtn.disabled = !canInstall && !canBuild;
  if (buildBtn) buildBtn.disabled = !canBuild;
  if (installBtn) installBtn.disabled = !canInstall;
  if (manualBtn) manualBtn.disabled = false;
}

async function triggerFirmwareWorkflow(mode = "auto", backupFirst = true, skipConfirm = false) {
  const promptText = backupFirst
    ? `Run managed backup and firmware workflow (${mode})?`
    : `Run firmware workflow (${mode}) without backup?`;
  if (!skipConfirm && !window.confirm(promptText)) return;
  const body = profilePayload();
  body.device_slug = getDeviceSlug();
  body.backup_first = !!backupFirst;
  body.mode = mode;
  body.native_firmware_entity = e("ha_native_firmware_entity")?.value?.trim() || "";
  body.app_version_entity = e("ha_installed_version_entity")?.value?.trim() || "";
  body.target_version = e("app_release_version")?.value?.trim() || (state.contracts?.defaults?.app_release_version || "v0.23.0");

  const data = await apiPost("api/firmware/workflow", body);
  const attempted = Array.isArray(data.actions_attempted) ? data.actions_attempted : [];
  const resultLines = [
    `Workflow: ${data.selected_method || "--"} (${data.mode || mode})`,
    `Device: ${data.device_slug || "--"}`,
    `Target: ${data.target_version || "--"}`,
    `Entity: ${data.native_firmware_entity || "--"}`,
    `Backup: ${data.backup?.id || "none"}`,
    `Result: ${data.summary || data.status?.status_text || "--"}`,
  ];
  attempted.forEach((row) => {
    resultLines.push(`- ${row.step || row.action || "step"}: ${row.status || "--"}${row.error ? ` (${row.error})` : ""}`);
  });
  if (Array.isArray(data.manual_next_steps) && data.manual_next_steps.length > 0) {
    resultLines.push("Manual next steps:");
    data.manual_next_steps.forEach((line) => resultLines.push(`- ${line}`));
  }
  e("firmware_update_result").textContent = resultLines.join("\n");
  setStatus(`Firmware workflow ${data.ok ? "completed" : "failed"} for ${data.device_slug || "--"}`, !data.ok);
  await Promise.all([refreshFirmwareStatus(), refreshBackups(), refreshRuntimeDiagnostics()]);
}

async function loadDomains() {
  const jobParam = state.entities.jobId ? `?job_id=${encodeURIComponent(state.entities.jobId)}` : "";
  const data = await apiGet(`api/discovery/domains${jobParam}`);
  renderDomains(data.domains || []);
}

async function refreshEntities({ resetPage = false } = {}) {
  if (resetPage) state.entities.page = 1;
  if (state.entities.controller) state.entities.controller.abort();
  state.entities.controller = new AbortController();

  const domain = encodeURIComponent(e("domain_filter").value || "");
  const q = encodeURIComponent(e("search_filter").value || "");
  const sort = encodeURIComponent(e("sort_filter").value || "entity_id");
  const pageSize = Number(e("page_size_filter").value || "100");
  const onlyMappable = e("only_mappable_filter").checked ? "true" : "false";
  const jobId = encodeURIComponent(state.entities.jobId || "");
  state.entities.page_size = pageSize;

  e("explorer_meta").textContent = "Loading entities...";
  try {
    const data = await apiGet(
      `api/discovery/entities?job_id=${jobId}&domain=${domain}&q=${q}&page=${state.entities.page}&page_size=${pageSize}&sort=${sort}&only_mappable=${onlyMappable}&fields=minimal`,
      state.entities.controller.signal
    );
    state.entities.pages = data.pages || 1;
    state.entities.total = data.total || 0;
    renderEntities(data.entities || []);
    e("page_label").textContent = `Page ${data.page || 1} / ${data.pages || 1}`;
    const job = data.job || null;
    e("explorer_meta").textContent =
      `Loaded ${data.returned || data.count || 0} of ${data.filtered_total || data.total || 0} | query ${data.query_time_ms || 0}ms | cache ${data.cache_age_ms || 0}ms${data.stale ? " | STALE" : ""}${job ? ` | job ${job.status}/${job.stage || "--"}` : ""}`;
    if (job) setDiscoveryStatus(formatJobText(job), job.status === "failed");
    if (data.stale && data.last_error) setStatus(`Discovery warning: ${data.last_error}`, true);
  } catch (err) {
    if (err && err.name === "AbortError") return;
    e("explorer_meta").textContent = "Entity load failed.";
    setStatus(`Entity load error: ${err.message}`, true);
  }
}

async function refreshDiscoveryCache() {
  await startDiscoveryJob(true, { wait_for_completion: false });
  setStatus("Discovery cache refresh started");
}

function bindExplorerEvents() {
  e("explorer_refresh_btn").addEventListener("click", () => refreshEntities({ resetPage: false }));
  e("domain_filter").addEventListener("change", () => refreshEntities({ resetPage: true }));
  e("sort_filter").addEventListener("change", () => refreshEntities({ resetPage: true }));
  e("page_size_filter").addEventListener("change", () => refreshEntities({ resetPage: true }));
  e("only_mappable_filter").addEventListener("change", () => refreshEntities({ resetPage: true }));
  e("search_filter").addEventListener("input", () => {
    if (state.searchDebounce) clearTimeout(state.searchDebounce);
    state.searchDebounce = setTimeout(() => refreshEntities({ resetPage: true }), 300);
  });
  e("page_prev_btn").addEventListener("click", () => {
    if (state.entities.page > 1) {
      state.entities.page -= 1;
      refreshEntities({ resetPage: false });
    }
  });
  e("page_next_btn").addEventListener("click", () => {
    if (state.entities.page < state.entities.pages) {
      state.entities.page += 1;
      refreshEntities({ resetPage: false });
    }
  });
  e("explorer_use_selected_btn").addEventListener("click", applySelectedEntityToActiveField);
}

function profilePayload() {
  updateProfileFromTopFields();
  return {
    workspace: state.workspace,
    active_device_index: state.activeDeviceIndex,
    device_slug: getDeviceSlug(),
    profile: currentProfile(),
  };
}

async function generate() {
  const body = profilePayload();
  const [install, overrides] = await Promise.all([apiPost("api/generate/install", body), apiPost("api/generate/overrides", body)]);
  e("install_out").value = install.yaml || "";
  e("overrides_out").value = overrides.yaml || "";
  e("generated_entities_out").value = install.generated?.entities || "";
  e("generated_theme_out").value = install.generated?.theme || "";
  e("generated_layout_out").value = [
    install.generated?.layout || "",
    "",
    "# home.generated.yaml",
    install.generated?.page_home || "",
    "",
    "# lights.generated.yaml",
    install.generated?.page_lights || "",
    "",
    "# weather.generated.yaml",
    install.generated?.page_weather || "",
    "",
    "# climate.generated.yaml",
    install.generated?.page_climate || "",
  ].join("\n");
  const validation = install.validation || overrides.validation || {};
  const errCount = (validation.errors || []).length;
  const warnCount = (validation.warnings || []).length;
  setStatus(`Generated YAML (${errCount} errors, ${warnCount} warnings)`, errCount > 0);
}

async function previewApply() {
  const data = await apiPost("api/apply/preview", profilePayload());
  const preview = data.preview || {};
  e("apply_preview_install_diff").value = preview.install?.diff || "No install changes";
  e("apply_preview_overrides_diff").value = preview.overrides?.diff || "No overrides changes";
  const generatedDiff = [
    preview.generated?.entities?.diff || "No generated entities changes",
    preview.generated?.theme?.diff || "No generated theme changes",
    preview.generated?.layout?.diff || "No generated layout changes",
    preview.generated?.page_home?.diff || "No generated home page changes",
    preview.generated?.page_lights?.diff || "No generated lights page changes",
    preview.generated?.page_weather?.diff || "No generated weather page changes",
    preview.generated?.page_climate?.diff || "No generated climate page changes",
  ].join("\n\n");
  e("apply_preview_generated_diff").value = generatedDiff;
  const validation = data.validation || {};
  const errCount = (validation.errors || []).length;
  const warnCount = (validation.warnings || []).length;
  setStatus(`Apply preview ready for ${preview.device_slug || "device"} (${errCount} errors, ${warnCount} warnings)`, errCount > 0);
}

async function commitApply(skipConfirm = false) {
  if (!skipConfirm && !window.confirm("Apply generated config to managed files with automatic backup?")) return;
  const data = await apiPost("api/apply/commit", profilePayload());
  setStatus(`Applied to ${data.device_slug}. Backup ${data.backup?.id || "created"}`);
  await refreshBackups();
}

async function refreshBackups() {
  const slug = getDeviceSlug();
  const data = await apiGet(`api/backups/list?device_slug=${encodeURIComponent(slug)}`);
  const select = e("backup_select");
  select.innerHTML = "";
  (data.backups || []).forEach((row) => {
    const opt = document.createElement("option");
    opt.value = row.id;
    opt.textContent = row.id;
    select.appendChild(opt);
  });
  e("backups_meta").textContent = `Device: ${data.device_slug}\nBackups: ${data.count || 0}`;
}

async function restoreBackup() {
  const slug = getDeviceSlug();
  const backupId = e("backup_select").value;
  if (!backupId) {
    setStatus("No backup selected", true);
    return;
  }
  if (!window.confirm(`Restore backup '${backupId}' for ${slug}?`)) return;
  const data = await apiPost("api/backups/restore", { device_slug: slug, backup_id: backupId });
  setStatus(`Restored backup ${data.restored?.backup_id || backupId} for ${slug}`);
}
async function refreshLatestRelease() {
  const channel = e("update_channel").value || "stable";
  const data = await apiGet(`api/update/latest?channel=${encodeURIComponent(channel)}`);
  state.latestRelease = data;
  const lines = [
    `Channel: ${data.channel || channel}`,
    `Version: ${data.version || "--"}`,
    `Published: ${data.published_at || "--"}`,
    `Cache age: ${data.cache_age_ms || 0} ms`,
    `Stale cache: ${data.stale ? "yes" : "no"}`,
  ];
  if (data.last_error) lines.push(`Last error: ${data.last_error}`);
  e("update_latest_summary").textContent = lines.join("\n");
  e("update_release_url").value = data.html_url || "";
}

async function generateHaUpdatePackage() {
  const body = profilePayload();
  body.channel = e("update_channel").value || "stable";
  body.ha_installed_version_entity = e("ha_installed_version_entity").value.trim();
  body.ha_native_firmware_entity = e("ha_native_firmware_entity").value.trim();
  const data = await apiPost("api/generate/ha_update_package", body);
  e("ha_update_package_out").value = data.yaml || "";
  setStatus(`Generated HA update package (latest stable: ${data.latest?.version || "unknown"})`);
}

async function loadProfiles() {
  const data = await apiGet("api/profile/list");
  const select = e("profile_list");
  select.innerHTML = "";
  (data.profiles || []).forEach((name) => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    select.appendChild(opt);
  });
}

async function saveProfile() {
  const payload = profilePayload();
  payload.name = state.workspace.workspace_name;
  const data = await apiPost("api/profile/save", payload);
  await loadProfiles();
  await refreshDashboardSummary().catch(() => {});
  setStatus(`Saved workspace ${data.workspace_name || data.profile_name}`);
}

async function loadSelectedProfile() {
  const selected = e("profile_list").value;
  if (!selected) return;
  const data = await apiGet(`api/profile/load?name=${encodeURIComponent(selected)}`);
  state.workspace = ensureWorkspace(data.workspace || data.profile, state.contracts.defaults || {});
  state.activeDeviceIndex = Number(data.active_device_index || state.workspace.active_device_index || 0);
  setMode(state.workspace.mode_ui?.mode || "guided");
  setGuidedStep(Number(state.workspace.mode_ui?.guided_step || 0));
  syncProfileToForm();
  await refreshDashboardSummary().catch(() => {});
  setStatus(`Loaded workspace ${selected}`);
}

async function deleteSelectedProfile() {
  const selected = e("profile_list").value;
  if (!selected) return;
  if (!window.confirm(`Delete workspace/profile '${selected}'?`)) return;
  await apiPost("api/profile/delete", { name: selected });
  await loadProfiles();
  setStatus(`Deleted ${selected}`);
}

async function renameSelectedProfile() {
  const selected = e("profile_list").value;
  const target = e("profile_rename_to").value.trim();
  if (!selected || !target) return;
  const data = await apiPost("api/profile/rename", { old_name: selected, new_name: target });
  await loadProfiles();
  e("workspace_name").value = data.workspace_name || data.profile_name;
  state.workspace.workspace_name = data.workspace_name || data.profile_name;
  setStatus(`Renamed to ${data.workspace_name || data.profile_name}`);
}

async function validateProfile() {
  const data = await apiPost("api/profile/validate", profilePayload());
  const lines = [];
  lines.push(`OK: ${data.ok}`);
  lines.push(`Errors: ${(data.errors || []).length}`);
  (data.errors || []).forEach((x) => lines.push(`- ${x}`));
  lines.push(`Warnings: ${(data.warnings || []).length}`);
  (data.warnings || []).forEach((x) => lines.push(`- ${x}`));
  if (Array.isArray(data.per_device)) {
    lines.push("Per-device:");
    data.per_device.forEach((d) => {
      lines.push(`- ${d.device_slug}: ok=${d.ok} errors=${(d.errors || []).length} warnings=${(d.warnings || []).length}`);
    });
  }
  e("validation_out").textContent = lines.join("\n");
  setStatus(data.ok ? "Workspace validation passed" : "Workspace validation has errors", !data.ok);
  return data;
}

async function guidedDeploy() {
  setStatus("Running guided deploy pipeline...");
  const validation = await validateProfile();
  if (!validation.ok) {
    setStatus("Guided deploy stopped: validation has errors", true);
    setGuidedStep(5);
    return;
  }
  await previewApply();
  await commitApply(true);
  await triggerFirmwareWorkflow("auto", true, true);
  await generate();
  setStatus("Guided deploy completed");
}

async function refreshTemplateCatalog() {
  try {
    const data = await apiGet("api/meta/templates");
    state.templateCatalog = data.templates || {};
  } catch (_err) {
    state.templateCatalog = state.contracts?.templates || {};
  }
  renderTemplateDomains();
}

async function refreshThemePalettes() {
  try {
    const data = await apiGet("api/theme/palettes");
    state.themePalettes = Array.isArray(data.palettes) ? data.palettes : [];
  } catch (_err) {
    state.themePalettes = Array.isArray(state.contracts?.theme_palettes) ? state.contracts.theme_palettes : [];
  }
  renderThemePalettes();
}

function bindProfileEvents() {
  document.querySelectorAll("[data-dashboard-action]").forEach((node) => {
    node.addEventListener("click", () => {
      const action = node.getAttribute("data-dashboard-action") || "";
      runDashboardAction(action).catch((err) => setStatus(`Dashboard action failed: ${err.message}`, true));
    });
  });
  e("camera_autodetect_scan_btn")?.addEventListener("click", () => {
    scanCameraAutodetect().catch((err) => setStatus(`Camera autodetect failed: ${err.message}`, true));
  });
  e("camera_autodetect_accept_btn")?.addEventListener("click", () => {
    acceptDetectedCameras().catch((err) => setStatus(`Accept cameras failed: ${err.message}`, true));
  });
  e("camera_autodetect_ignore_btn")?.addEventListener("click", () => {
    ignoreDetectedCameras().catch((err) => setStatus(`Ignore cameras failed: ${err.message}`, true));
  });
  e("dashboard_refresh_btn")?.addEventListener("click", () => {
    refreshDashboardSummary().catch((err) => setStatus(`Dashboard refresh failed: ${err.message}`, true));
  });

  e("profile_save_btn").addEventListener("click", saveProfile);
  e("profile_load_btn").addEventListener("click", loadSelectedProfile);
  e("profile_delete_btn").addEventListener("click", deleteSelectedProfile);
  e("profile_rename_btn").addEventListener("click", renameSelectedProfile);
  e("profile_validate_btn").addEventListener("click", validateProfile);

  e("generate_btn").addEventListener("click", generate);
  e("apply_preview_btn").addEventListener("click", previewApply);
  e("apply_commit_btn").addEventListener("click", commitApply);
  e("backups_refresh_btn").addEventListener("click", refreshBackups);
  e("backup_restore_btn").addEventListener("click", restoreBackup);

  e("update_refresh_btn").addEventListener("click", refreshLatestRelease);
  e("update_generate_package_btn").addEventListener("click", generateHaUpdatePackage);

  e("refresh_health_btn").addEventListener("click", refreshHealth);
  e("refresh_cache_btn").addEventListener("click", refreshDiscoveryCache);
  e("discovery_cancel_btn").addEventListener("click", cancelDiscoveryJob);
  e("fw_status_refresh_btn").addEventListener("click", () => {
    refreshFirmwareStatus().catch((err) => setStatus(`Firmware status error: ${err.message}`, true));
  });
  e("fw_workflow_auto_btn").addEventListener("click", () => {
    triggerFirmwareWorkflow("auto", true).catch((err) => {
      e("firmware_update_result").textContent = `Update failed: ${err.message}`;
      setStatus(`Firmware update failed: ${err.message}`, true);
    });
  });
  e("fw_workflow_build_btn").addEventListener("click", () => {
    triggerFirmwareWorkflow("build_install", true).catch((err) => {
      e("firmware_update_result").textContent = `Update failed: ${err.message}`;
      setStatus(`Firmware update failed: ${err.message}`, true);
    });
  });
  e("fw_workflow_install_btn").addEventListener("click", () => {
    triggerFirmwareWorkflow("install_only", false).catch((err) => {
      e("firmware_update_result").textContent = `Update failed: ${err.message}`;
      setStatus(`Firmware update failed: ${err.message}`, true);
    });
  });
  e("fw_manual_steps_btn").addEventListener("click", () => {
    triggerFirmwareWorkflow("manual_fallback", false).catch((err) => {
      e("firmware_update_result").textContent = `Manual flow failed: ${err.message}`;
      setStatus(`Manual flow failed: ${err.message}`, true);
    });
  });
  e("refresh_runtime_btn").addEventListener("click", () => {
    refreshRuntimeDiagnostics().catch((err) => setStatus(`Runtime diagnostics error: ${err.message}`, true));
  });

  e("template_domain_select")?.addEventListener("change", renderTemplateItems);
  e("template_item_select")?.addEventListener("change", renderTemplatePreview);
  e("template_apply_btn")?.addEventListener("click", applySelectedTemplate);

  e("theme_palette_select")?.addEventListener("change", () => {
    const p = currentProfile();
    if (p) {
      ensureThemeStudio(p);
      p.theme_studio.active_palette = e("theme_palette_select").value || "ocean_dark";
    }
    syncThemePickerFromToken();
    renderThemePreviewCard(currentThemeTokensForPreview(), "Palette changed.");
  });
  e("theme_token_select")?.addEventListener("change", syncThemePickerFromToken);
  e("theme_color_picker")?.addEventListener("input", () => {
    const p = currentProfile();
    if (!p) return;
    ensureThemeStudio(p);
    const key = getActiveThemeTokenKey();
    const custom = { ...(p.theme_studio.custom_tokens || {}) };
    custom[key] = hexToToken(e("theme_color_picker").value);
    p.theme_studio.custom_tokens = custom;
    renderThemePreviewCard(currentThemeTokensForPreview(), "Local preview (not applied).");
  });
  e("theme_preview_btn")?.addEventListener("click", () => {
    previewTheme().catch((err) => setStatus(`Theme preview failed: ${err.message}`, true));
  });
  e("theme_apply_btn")?.addEventListener("click", () => {
    applyTheme().catch((err) => setStatus(`Theme apply failed: ${err.message}`, true));
  });

  e("layout_page_select")?.addEventListener("change", renderLayoutSections);
  e("layout_add_section_btn")?.addEventListener("click", addLayoutSection);
  e("layout_validate_btn")?.addEventListener("click", () => {
    validateLayout().catch((err) => setStatus(`Layout validate failed: ${err.message}`, true));
  });
  e("layout_save_btn")?.addEventListener("click", () => {
    saveLayout().catch((err) => setStatus(`Layout save failed: ${err.message}`, true));
  });
  e("layout_reset_page_btn")?.addEventListener("click", () => {
    resetLayoutPage().catch((err) => setStatus(`Layout reset failed: ${err.message}`, true));
  });
  e("guided_deploy_btn")?.addEventListener("click", () => {
    guidedDeploy().catch((err) => setStatus(`Guided deploy failed: ${err.message}`, true));
  });
}

async function bootstrap() {
  bindTabs();
  bindModeControls();
  bindExplorerEvents();
  bindProfileEvents();

  const meta = await apiGet("api/meta/contracts");
  state.contracts = meta.contracts || {};
  state.templateCatalog = meta.templates || {};
  state.themePalettes = Array.isArray(meta.theme_palettes) ? meta.theme_palettes : [];
  state.workspace = ensureWorkspace(meta.default_workspace || meta.default_profile, meta.default_profile || {});
  state.activeDeviceIndex = Number(state.workspace.active_device_index || 0);
  try {
    const persistedMode = window.localStorage.getItem("tdeck_admin_mode");
    state.uiMode = persistedMode || state.workspace.mode_ui?.mode || "guided";
  } catch (_err) {
    state.uiMode = state.workspace.mode_ui?.mode || "guided";
  }
  state.guidedStep = Number(state.workspace.mode_ui?.guided_step || 0);
  setMode(state.uiMode);
  setGuidedStep(state.guidedStep);
  syncProfileToForm();
  bindTopFieldEvents();

  const runStep = async (label, fn) => {
    try {
      await fn();
      return true;
    } catch (err) {
      state.bootErrors.push(`${label}: ${err.message}`);
      setStatus(`${label} failed: ${err.message}`, true);
      return false;
    }
  };

  await runStep("Health", refreshHealth);
  await runStep("Dashboard", refreshDashboardSummary);
  await runStep("Firmware status", refreshFirmwareStatus);
  await runStep("Runtime diagnostics", refreshRuntimeDiagnostics);
  await runStep("Profile list", loadProfiles);
  await runStep("Template catalog", refreshTemplateCatalog);
  await runStep("Theme palettes", refreshThemePalettes);
  await runStep("Discovery start", () => startDiscoveryJob(false, { wait_for_completion: false }));
  await runStep("Latest release", refreshLatestRelease);
  await runStep("Backup list", refreshBackups);

  if (state.bootErrors.length > 0) {
    setStatus(`Admin Center ready with issues (${state.bootErrors.length}). Check status/details.`, true);
  } else {
    setStatus("Admin Center ready");
  }
}

bootstrap().catch((err) => setStatus(`Startup error: ${err.message}`, true));

