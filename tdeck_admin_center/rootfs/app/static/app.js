
const state = {
  contracts: null,
  workspace: null,
  activeDeviceIndex: 0,
  eventsBound: false,
  transport: {
    api_base_resolved: "",
    ingress_hint: "",
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
  onboardingNodes: [],
  instanceDeviceScope: "active",
  catalogDetected: [],
  additionalCollection: "weather_metrics",
  startup: {
    startup_state: "booting",
    startup_error_text: "",
    in_progress: false,
  },
  rowSuggestTimers: {},
  collectionDirty: false,
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
const GUIDED_PAGE_OPTIONS = ["home", "lights", "weather", "climate", "reader", "cameras", "settings", "theme"];
const FEATURE_PAGE_POLICY_FALLBACK = {
  lights: { required: ["ui_show_lights"], optional: ["home_tile_show_lights"] },
  weather: { required: ["ui_show_weather"], optional: ["home_tile_show_weather"] },
  climate: { required: ["ui_show_climate"], optional: ["home_tile_show_climate"] },
  cameras: { required: ["ui_show_cameras"], optional: ["home_tile_show_cameras"] },
  reader: { required: ["ui_show_reader"], optional: ["home_tile_show_reader"] },
  gps: { required: [], optional: [] },
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

function metaContent(name) {
  const node = document.querySelector(`meta[name="${name}"]`);
  return node ? String(node.getAttribute("content") || "").trim() : "";
}

const INDEX_ASSET_VERSION = metaContent("tdeck-asset-version");
const INDEX_INGRESS_HINT = metaContent("tdeck-ingress-prefix");
if (INDEX_INGRESS_HINT) {
  state.transport.ingress_hint = INDEX_INGRESS_HINT;
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
    `Ingress Hint: ${t.ingress_hint || "--"}`,
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
  const normalizedTail = normalized.replace(/^api\//, "");
  const joined = `${ingressBasePath().replace(/\/+$/, "")}/${normalized}`.replace(/\/{2,}/g, "/");
  const candidates = [normalized, `./${normalized}`, joined];
  const hint = String(state.transport.ingress_hint || INDEX_INGRESS_HINT || "").trim();
  if (hint) {
    const hintBase = hint.replace(/\/+$/, "");
    if (hintBase === "api" || hintBase.endsWith("/api")) {
      candidates.push(`${hintBase}/${normalizedTail}`);
    } else {
      candidates.push(`${hintBase}/${normalized}`);
    }
  }
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
    const startup = state.startup || {};
    strip.textContent =
      `Startup: ${startup.startup_state || "--"}\n` +
      `Status: ${text}\n` +
      `Mode: ${state.uiMode}\n` +
      `API: ${t.last_status_code || "--"} ${t.last_path || "--"}\n` +
      `FW: ${fw.status_text || "--"} (${fw.method || "--"})`;
    strip.style.color = isError ? "#ffb4c0" : "";
  }
}

function formatStartupError(label, err) {
  const endpoint = state.transport.last_path || "--";
  const code = state.transport.last_status_code || "--";
  const base = state.transport.api_base_resolved || state.transport.ingress_hint || "--";
  const detail = err?.message || "unknown error";
  return `${label} failed (${detail}). endpoint=${endpoint} status=${code} base=${base}. Try Retry Startup.`;
}

function setStartupState(startupState, startupErrorText = "", isError = false) {
  state.startup.startup_state = startupState;
  state.startup.startup_error_text = startupErrorText;
  const stateLabel = e("startup_state_lbl");
  if (stateLabel) {
    stateLabel.textContent = `Startup: ${startupState}`;
    stateLabel.style.color = startupState === "error" ? "#ffb4c0" : "";
  }
  const errorLabel = e("startup_error_lbl");
  if (errorLabel) {
    if (startupErrorText) {
      errorLabel.textContent = startupErrorText;
      errorLabel.classList.remove("hidden");
      errorLabel.style.color = isError ? "#ffb4c0" : "#ffd38a";
    } else {
      errorLabel.textContent = "";
      errorLabel.classList.add("hidden");
      errorLabel.style.color = "";
    }
  }
  const retryBtn = e("retry_startup_btn");
  if (retryBtn) retryBtn.disabled = startupState === "booting";
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
  renderDeployPreflight(validation, firmware);
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
      schema_version: "5.0",
      workspace_name: "default",
      active_device_index: 0,
      devices: [deepClone(fallbackProfile)],
      mode_ui: { mode: "guided", guided_step: 0, show_advanced_diagnostics: false },
      templates: {},
      entity_collections: {},
      entity_instances: {},
      type_registry: {},
      layout_pages: {},
      page_layouts: [],
      theme_studio: {},
      landing_state: {},
      camera_autodetect: {},
      deployment_workflow: {},
      deployment_profile: {},
      device_workspace: {},
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
  if (!ws.deployment_profile || typeof ws.deployment_profile !== "object") ws.deployment_profile = {};
  if (!ws.mode_ui || typeof ws.mode_ui !== "object") ws.mode_ui = { mode: "guided", guided_step: 0, show_advanced_diagnostics: false };
  if (!ws.layout_pages || typeof ws.layout_pages !== "object") ws.layout_pages = {};
  if (!Array.isArray(ws.page_layouts)) ws.page_layouts = [];
  if (!ws.theme_studio || typeof ws.theme_studio !== "object") ws.theme_studio = {};
  if (!ws.landing_state || typeof ws.landing_state !== "object") ws.landing_state = {};
  if (!ws.camera_autodetect || typeof ws.camera_autodetect !== "object") ws.camera_autodetect = {};
  if (!ws.entity_instances || typeof ws.entity_instances !== "object") ws.entity_instances = {};
  if (!ws.type_registry || typeof ws.type_registry !== "object") ws.type_registry = {};
  if (!ws.device_workspace || typeof ws.device_workspace !== "object") ws.device_workspace = {};
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
  const defaultVersion = state.contracts?.defaults?.app_release_version || "v0.25.0";
  e("workspace_name").value = state.workspace.workspace_name || "default";
  renderDeviceSelector();
  e("profile_name").value = p.profile_name || `device_${state.activeDeviceIndex + 1}`;
  e("device_name").value = p.device?.name || "";
  e("device_friendly_name").value = p.device?.friendly_name || "";
  e("git_ref").value = p.device?.git_ref || state.workspace.deployment?.git_ref || "stable";
  const defaultGitUrl = state.contracts?.defaults?.git_url || state.contracts?.defaults?.repo_url || "https://github.com/owner/repository.git";
  e("git_url").value = p.device?.git_url || state.workspace.deployment?.git_url || defaultGitUrl;
  e("app_release_version").value = p.settings?.app_release_version || state.workspace.deployment?.app_release_version || defaultVersion;
  const presetNode = e("onboarding_preset_select");
  if (presetNode && p.settings?.onboarding_preset) {
    presetNode.value = String(p.settings.onboarding_preset);
  }
}

function featurePagePolicy() {
  return state.contracts?.feature_page_policy || FEATURE_PAGE_POLICY_FALLBACK;
}

function applyFeaturePagePolicyInProfile(profile) {
  if (!profile) return;
  profile.features = profile.features || {};
  profile.ui = profile.ui || {};
  const policy = featurePagePolicy();
  Object.entries(policy).forEach(([feature, row]) => {
    const enabled = asBool(profile.features?.[feature], false);
    const required = Array.isArray(row?.required) ? row.required : [];
    const optional = Array.isArray(row?.optional) ? row.optional : [];
    required.forEach((key) => {
      profile.ui[key] = enabled;
    });
    optional.forEach((key) => {
      if (!enabled) profile.ui[key] = false;
      else if (profile.ui[key] === undefined) profile.ui[key] = true;
    });
  });
  profile.ui.ui_show_settings = true;
  profile.ui.ui_show_theme = true;
}

function computeUiLockState(profile) {
  const locks = {};
  const policy = featurePagePolicy();
  Object.entries(policy).forEach(([feature, row]) => {
    const enabled = asBool(profile.features?.[feature], false);
    const required = Array.isArray(row?.required) ? row.required : [];
    const optional = Array.isArray(row?.optional) ? row.optional : [];
    required.forEach((key) => {
      locks[key] = {
        locked: true,
        reason: enabled ? `Locked on because feature '${feature}' is enabled.` : `Locked off because feature '${feature}' is disabled.`,
      };
    });
    optional.forEach((key) => {
      if (!enabled) {
        locks[key] = {
          locked: true,
          reason: `Locked off because feature '${feature}' is disabled.`,
        };
      } else {
        locks[key] = locks[key] || {
          locked: false,
          reason: `Optional while feature '${feature}' is enabled.`,
        };
      }
    });
  });
  locks.ui_show_settings = { locked: true, reason: "Settings is always enabled for recovery and maintenance." };
  locks.ui_show_theme = { locked: true, reason: "Theme is always enabled for readability fixes." };
  return locks;
}

function renderFeatureToggles() {
  const p = currentProfile();
  if (!p) return;
  applyFeaturePagePolicyInProfile(p);
  const host = e("feature_toggles");
  if (!host) return;
  host.innerHTML = "";
  FEATURE_KEYS.forEach((key) => {
    const id = `feature_${key}`;
    const checked = asBool(p.features?.[key]);
    host.insertAdjacentHTML("beforeend", `<label class="checkbox-row"><input type="checkbox" id="${id}" ${checked ? "checked" : ""}/> ${key}</label>`);
    e(id)?.addEventListener("change", (ev) => {
      p.features[key] = ev.target.checked;
      applyFeaturePagePolicyInProfile(p);
      renderUiToggles();
      setCollectionDirty(true);
    });
  });
}

function renderUiToggles() {
  const p = currentProfile();
  if (!p) return;
  applyFeaturePagePolicyInProfile(p);
  const keys = state.contracts?.ui_keys || [];
  const host = e("ui_toggles");
  if (!host) return;
  host.innerHTML = "";
  const locks = computeUiLockState(p);
  keys.forEach((key) => {
    const id = `ui_toggle_${key}`;
    const checked = asBool(p.ui?.[key]);
    const lockInfo = locks[key] || { locked: false, reason: "" };
    host.insertAdjacentHTML(
      "beforeend",
      `<label class="checkbox-row"><input type="checkbox" id="${id}" ${checked ? "checked" : ""} ${lockInfo.locked ? "disabled" : ""}/> ${key}</label>`
    );
    e(id)?.addEventListener("change", (ev) => {
      p.ui[key] = ev.target.checked;
      setCollectionDirty(true);
    });
  });
  const policyMeta = e("feature_policy_meta");
  if (policyMeta) {
    const lines = [];
    Object.entries(locks).forEach(([key, row]) => {
      if (row?.reason) lines.push(`${key}: ${row.reason}`);
    });
    policyMeta.textContent = lines.length ? lines.join("\n") : "No policy locks active.";
  }
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
  });
  if (!profile.slot_runtime || typeof profile.slot_runtime !== "object") {
    profile.slot_runtime = {
      light_slot_cap: 24,
      camera_slot_cap: 8,
      light_page_size: 6,
      camera_page_size: 4,
    };
  }
  profile.slot_runtime.light_slot_cap = clampInt(profile.slot_runtime.light_slot_cap || 24, 8, 48);
  profile.slot_runtime.camera_slot_cap = clampInt(profile.slot_runtime.camera_slot_cap || 8, 2, 16);
  profile.slot_runtime.light_page_size = clampInt(profile.slot_runtime.light_page_size || 6, 4, 8);
  profile.slot_runtime.camera_page_size = clampInt(profile.slot_runtime.camera_page_size || 4, 2, 6);
  if (!profile.entity_collections_meta || typeof profile.entity_collections_meta !== "object") {
    profile.entity_collections_meta = {};
  }
  COLLECTION_KEYS.forEach((key) => {
    if (!profile.entity_collections_meta[key] || typeof profile.entity_collections_meta[key] !== "object") {
      profile.entity_collections_meta[key] = {
        sort: "name",
        show_disabled: false,
        last_query: "",
        draft_dirty: false,
      };
    }
  });
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

function ensureEntityInstances(profile) {
  if (!profile || typeof profile !== "object") return;
  if (!Array.isArray(profile.entity_instances)) {
    profile.entity_instances = [];
  }
  if (!profile.type_registry || typeof profile.type_registry !== "object") {
    profile.type_registry = state.contracts?.type_registry || {};
  }
  if (profile.entity_instances.length > 0) return;
  ensureCollections(profile);
  const collectionTypeMap = {
    lights: "light",
    cameras: "camera",
    weather_metrics: "weather",
    climate_controls: "climate",
    reader_feeds: "sensor",
    system_entities: "sensor",
  };
  COLLECTION_KEYS.forEach((collectionName) => {
    const rows = Array.isArray(profile.entity_collections?.[collectionName]) ? profile.entity_collections[collectionName] : [];
    rows.forEach((row, idx) => {
      profile.entity_instances.push({
        id: slugify(row.id || `${collectionName}_${idx + 1}`),
        type: collectionTypeMap[collectionName] || "sensor",
        name: row.name || `${collectionName}_${idx + 1}`,
        entity_id: row.entity_id || "",
        role: row.role || "",
        enabled: asBool(row.enabled, true),
        page: collectionName === "weather_metrics" ? "weather" : collectionName === "climate_controls" ? "climate" : collectionName === "reader_feeds" ? "reader" : collectionName,
        section: "content",
        icon: "",
      });
    });
  });
}

function instanceCollectionHint(typeId, role = "") {
  const roleLow = String(role || "").toLowerCase();
  if (roleLow.startsWith("entity_wx_")) return "weather_metrics";
  if (roleLow.startsWith("entity_sensi_")) return "climate_controls";
  if (roleLow.startsWith("entity_feed_")) return "reader_feeds";
  if (typeId === "light") return "lights";
  if (typeId === "camera") return "cameras";
  if (typeId === "weather") return "weather_metrics";
  if (typeId === "climate") return "climate_controls";
  return "system_entities";
}

function instanceDomainHint(typeId) {
  if (typeId === "sensor") return "sensor";
  return String(typeId || "");
}

function renderOnboardingCandidates() {
  const body = e("onboarding_candidates_body");
  const meta = e("onboarding_candidates_meta");
  if (!body) return;
  body.innerHTML = "";
  const rows = Array.isArray(state.onboardingNodes) ? state.onboardingNodes : [];
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="4">No candidates found. Use manual verify fallback below.</td></tr>`;
  } else {
    rows.forEach((row, idx) => {
      const rid = `onb_${idx}`;
      const reasons = Array.isArray(row.reasons) ? row.reasons.slice(0, 4).join(", ") : "";
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${safeText(row.device_slug || "device")}<br/><small>${safeText(row.friendly_name || "Unknown")}</small></td>
        <td>${safeText(String(row.confidence || "low"))} (${safeText(String(row.confidence_score || 0))})</td>
        <td>${safeText(reasons || "n/a")}</td>
        <td class="row-actions">
          <button class="btn-soft" id="${rid}_use">Use</button>
          <button class="btn-soft" id="${rid}_verify">Verify</button>
        </td>
      `;
      body.appendChild(tr);
      e(`${rid}_use`)?.addEventListener("click", () => {
        if (e("onboarding_manual_slug")) e("onboarding_manual_slug").value = row.device_slug || "";
        onboardingImportExisting(row.device_slug || "").catch((err) => setStatus(`Import failed: ${err.message}`, true));
      });
      e(`${rid}_verify`)?.addEventListener("click", () => {
        if (e("onboarding_manual_slug")) e("onboarding_manual_slug").value = row.device_slug || "";
        onboardingVerifyCandidate().catch((err) => setStatus(`Verify failed: ${err.message}`, true));
      });
    });
  }
  if (meta) {
    meta.textContent = rows.length
      ? `Detected ${rows.length} candidate node(s). Pick the highest confidence row first.`
      : "No candidates detected yet.";
  }
}

async function refreshOnboardingNodes(force = false) {
  const data = await apiGet(`api/onboarding/candidates${force ? "?refresh=1" : ""}`);
  state.onboardingNodes = Array.isArray(data.nodes) ? data.nodes : [];
  renderOnboardingCandidates();
  renderInstanceDeviceScopeOptions();
  const out = e("onboarding_status_lbl");
  const discovery = data.discovery || {};
  if (out) {
    out.textContent = state.onboardingNodes.length
      ? `Detected ${state.onboardingNodes.length} existing node candidate(s).`
      : `No candidates found. Discovery total=${discovery.last_total || 0} error=${discovery.last_error || "none"}`;
  }
}

async function onboardingStartNew() {
  const payload = {
    workspace_name: e("workspace_name")?.value?.trim() || "default",
    device_name: e("device_name")?.value?.trim() || "lilygo-tdeck-plus",
    friendly_name: e("device_friendly_name")?.value?.trim() || "LilyGO T-Deck Plus",
    app_release_version: e("app_release_version")?.value?.trim() || (state.contracts?.defaults?.app_release_version || "v0.25.0"),
    preset: e("onboarding_preset_select")?.value?.trim() || "blank",
    persist: true,
  };
  const data = await apiPost("api/onboarding/start_new", payload);
  state.workspace = ensureWorkspace(data.workspace || state.workspace, state.contracts.defaults || {});
  state.activeDeviceIndex = Number(data.active_device_index || state.workspace.active_device_index || 0);
  syncProfileToForm();
  setStatus("Initialized new managed T-Deck workspace");
  const out = e("onboarding_status_lbl");
  if (out) out.textContent = data.message || "Start New completed.";
}

async function onboardingImportExisting(slugOverride = "") {
  const slug = slugOverride || e("onboarding_manual_slug")?.value?.trim() || "";
  const entityId = e("onboarding_manual_entity")?.value?.trim() || "";
  const payload = {
    workspace_name: e("workspace_name")?.value?.trim() || "imported",
    device_slug: slug,
    entity_id: entityId,
    persist: true,
  };
  const data = await apiPost("api/onboarding/import_existing", payload);
  state.workspace = ensureWorkspace(data.workspace || state.workspace, state.contracts.defaults || {});
  state.activeDeviceIndex = Number(data.active_device_index || state.workspace.active_device_index || 0);
  syncProfileToForm();
  setStatus("Imported existing ESPHome node into managed workspace");
  const out = e("onboarding_status_lbl");
  if (out) out.textContent = data.message || "Import completed.";
}

async function onboardingVerifyCandidate() {
  const payload = {
    device_slug: e("onboarding_manual_slug")?.value?.trim() || "",
    entity_id: e("onboarding_manual_entity")?.value?.trim() || "",
  };
  const data = await apiPost("api/onboarding/verify_candidate", payload);
  const node = data.candidate || {};
  const hints = Array.isArray(data.hints) ? data.hints : [];
  const sample = Array.isArray(data.matched_entities_sample) ? data.matched_entities_sample : [];
  const out = e("onboarding_verify_meta");
  if (out) {
    out.textContent =
      `Candidate: ${node.device_slug || "--"}\n` +
      `Confidence: ${node.confidence || "low"} (${node.confidence_score || 0})\n` +
      `Hints: ${hints.join(" | ") || "none"}\n` +
      `Entities: ${sample.slice(0, 6).join(" | ") || "none"}`;
  }
  setStatus(`Verified candidate ${node.device_slug || "--"}`);
}

async function onboardingMigrateManaged() {
  const body = profilePayload();
  body.commit = true;
  const data = await apiPost("api/onboarding/migrate_to_managed", body);
  if (!data.ok) {
    setStatus(`Migrate failed: ${data.error || "unknown error"}`, true);
    return;
  }
  setStatus("Migration to managed files completed");
  const out = e("onboarding_status_lbl");
  if (out) out.textContent = `Managed files updated for ${data.result?.device_slug || getDeviceSlug()}.`;
}

function renderInstanceTypeOptions() {
  const select = e("instance_type_select");
  if (!select) return;
  const registry = state.contracts?.type_registry || {};
  const ids = state.contracts?.core_type_ids || Object.keys(registry);
  const current = select.value || "light";
  select.innerHTML = "";
  ids.forEach((typeId) => {
    const row = registry[typeId] || {};
    const opt = document.createElement("option");
    opt.value = typeId;
    opt.textContent = row.label || typeId;
    if (typeId === current) opt.selected = true;
    select.appendChild(opt);
  });
  const pageSelect = e("instance_page_select");
  if (pageSelect && !pageSelect.value) {
    const typeId = select.value || "sensor";
    pageSelect.value =
      typeId === "weather"
        ? "weather"
        : typeId === "climate"
          ? "climate"
          : typeId === "camera"
            ? "cameras"
            : typeId === "light"
              ? "lights"
              : "home";
  }
}

async function queueInstanceSuggestions(inputNode, item, selectNode = null) {
  if ((!inputNode && !selectNode) || !item) return;
  const key = inputNode?.id || selectNode?.id || `suggest_${Date.now()}`;
  if (state.rowSuggestTimers[key]) clearTimeout(state.rowSuggestTimers[key]);
  state.rowSuggestTimers[key] = setTimeout(async () => {
    try {
      const payload = {
        key: item.role || item.id || "",
        q: inputNode?.value || "",
        limit: 40,
        collection: instanceCollectionHint(item.type, item.role),
        role: item.role || "",
        domain_hint: instanceDomainHint(item.type),
        type: item.type || "",
        device_slug: effectiveInstanceDeviceScope(),
        exclude_assigned: true,
        active_device_slug: getDeviceSlug(),
        workspace: state.workspace?.workspace_name || "default",
      };
      const data = await apiPost("api/mapping/suggest", payload);
      const suggestions = Array.isArray(data.suggestions) ? data.suggestions : [];
      if (selectNode) {
        selectNode.innerHTML = `<option value="">Pick from ranked suggestions...</option>`;
        suggestions.forEach((row) => {
          const opt = document.createElement("option");
          opt.value = row.entity_id || "";
          opt.textContent = `${row.friendly_name || row.entity_id || ""} (${row.entity_id || ""}) [${row.score || 0}]`;
          selectNode.appendChild(opt);
        });
      }
      if (inputNode) {
        const listId = `${inputNode.id}_list`;
        let datalist = e(listId);
        if (!datalist) {
          datalist = document.createElement("datalist");
          datalist.id = listId;
          inputNode.insertAdjacentElement("afterend", datalist);
          inputNode.setAttribute("list", listId);
        }
        datalist.innerHTML = "";
        suggestions.forEach((row) => {
          const opt = document.createElement("option");
          opt.value = row.entity_id || "";
          opt.label = `${row.friendly_name || row.entity_id || ""} | ${row.reason || "ranked"} | score ${row.score || 0}`;
          datalist.appendChild(opt);
        });
      }
    } catch (_err) {}
  }, 220);
}

async function applyInstanceOp(ops, successText = "") {
  const body = profilePayload();
  body.ops = Array.isArray(ops) ? ops : [];
  const data = await apiPost("api/entities/instances/bulk", body);
  state.workspace = ensureWorkspace(data.workspace || state.workspace, state.contracts.defaults || {});
  state.activeDeviceIndex = Number(data.active_device_index || state.workspace.active_device_index || 0);
  syncProfileToForm();
  setCollectionDirty(true);
  if (successText) setStatus(successText);
  return data;
}

function renderEntityInstances() {
  const p = currentProfile();
  if (!p) return;
  ensureEntityInstances(p);
  const body = e("entity_instances_body");
  const meta = e("entity_instances_meta");
  const validationNode = e("entity_instances_validation");
  if (!body) return;
  const rows = Array.isArray(p.entity_instances) ? p.entity_instances : [];
  body.innerHTML = "";
  const registry = state.contracts?.type_registry || {};
  const typeOptions = (state.contracts?.core_type_ids || Object.keys(registry)).map((typeId) => ({
    id: typeId,
    label: registry[typeId]?.label || typeId,
  }));
  rows.forEach((item, idx) => {
    const rid = `inst_${idx}`;
    const typeOptionsHtml = typeOptions
      .map((row) => `<option value="${safeText(row.id)}" ${String(item.type || "sensor") === row.id ? "selected" : ""}>${safeText(row.label)}</option>`)
      .join("");
    const pageOptionsHtml = GUIDED_PAGE_OPTIONS
      .map((pageId) => `<option value="${safeText(pageId)}" ${String(item.page || "home") === pageId ? "selected" : ""}>${safeText(pageId)}</option>`)
      .join("");
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><select id="${rid}_type">${typeOptionsHtml}</select></td>
      <td><input id="${rid}_name" value="${safeText(item.name || "")}" /></td>
      <td>
        <input id="${rid}_entity" class="entity-combo-input" value="${safeText(item.entity_id || "")}" placeholder="Type to search or pick below..." />
        <select id="${rid}_suggest" class="compact-select"><option value="">Pick from ranked suggestions...</option></select>
      </td>
      <td><input id="${rid}_role" value="${safeText(item.role || "")}" /></td>
      <td><select id="${rid}_page">${pageOptionsHtml}</select></td>
      <td><input type="checkbox" id="${rid}_enabled" ${asBool(item.enabled) ? "checked" : ""} /></td>
      <td class="row-actions">
        <button class="btn-soft" id="${rid}_dup">Dup</button>
        <button class="btn-soft" id="${rid}_up">Up</button>
        <button class="btn-soft" id="${rid}_down">Down</button>
        <button class="btn-warn" id="${rid}_del">Delete</button>
      </td>
    `;
    body.appendChild(tr);
    const updatePatch = (patch) =>
      applyInstanceOp([{ op: "update", item_id: item.id || `${item.type}_${idx + 1}`, patch }]).catch((err) =>
        setStatus(`Instance update failed: ${err.message}`, true)
      );
    e(`${rid}_type`)?.addEventListener("change", (ev) => updatePatch({ type: ev.target.value }));
    e(`${rid}_name`)?.addEventListener("change", (ev) => updatePatch({ name: ev.target.value }));
    const entityInput = e(`${rid}_entity`);
    const suggestSelect = e(`${rid}_suggest`);
    entityInput?.addEventListener("focus", () => queueInstanceSuggestions(entityInput, item, suggestSelect));
    entityInput?.addEventListener("input", () => queueInstanceSuggestions(entityInput, item, suggestSelect));
    entityInput?.addEventListener("change", (ev) => updatePatch({ entity_id: ev.target.value }));
    suggestSelect?.addEventListener("change", (ev) => {
      const picked = String(ev.target.value || "").trim();
      if (!picked) return;
      if (entityInput) entityInput.value = picked;
      updatePatch({ entity_id: picked });
    });
    e(`${rid}_role`)?.addEventListener("change", (ev) => updatePatch({ role: ev.target.value }));
    e(`${rid}_page`)?.addEventListener("change", (ev) => updatePatch({ page: ev.target.value }));
    e(`${rid}_enabled`)?.addEventListener("change", (ev) => updatePatch({ enabled: ev.target.checked }));
    e(`${rid}_dup`)?.addEventListener("click", () => {
      const copyId = `${item.type || "sensor"}_${Date.now()}`;
      applyInstanceOp(
        [
          {
            op: "add",
            item: {
              id: copyId,
              type: item.type || "sensor",
              name: `${item.name || "Element"} Copy`,
              entity_id: item.entity_id || "",
              role: item.role || "",
              enabled: asBool(item.enabled, true),
              page: item.page || "home",
            },
          },
        ],
        "Duplicated typed element"
      ).catch((err) => setStatus(`Duplicate failed: ${err.message}`, true));
    });
    e(`${rid}_up`)?.addEventListener("click", () => {
      if (idx <= 0) return;
      applyInstanceOp([{ op: "reorder", from_index: idx, to_index: idx - 1 }], "Moved typed element").catch((err) =>
        setStatus(`Reorder failed: ${err.message}`, true)
      );
    });
    e(`${rid}_down`)?.addEventListener("click", () => {
      if (idx >= rows.length - 1) return;
      applyInstanceOp([{ op: "reorder", from_index: idx, to_index: idx + 1 }], "Moved typed element").catch((err) =>
        setStatus(`Reorder failed: ${err.message}`, true)
      );
    });
    e(`${rid}_del`)?.addEventListener("click", () => {
      applyInstanceOp([{ op: "remove", item_id: item.id || `${item.type}_${idx + 1}` }], "Deleted typed element").catch((err) =>
        setStatus(`Delete failed: ${err.message}`, true)
      );
    });
  });
  if (meta) {
    const counts = {};
    rows.forEach((row) => {
      const t = row.type || "sensor";
      counts[t] = (counts[t] || 0) + 1;
    });
    const summary = Object.keys(counts).sort().map((k) => `${k}:${counts[k]}`).join(" | ");
    const scope = effectiveInstanceDeviceScope();
    meta.textContent = `Typed instances: ${rows.length}${summary ? ` | ${summary}` : ""} | Scope: ${scope || "all entities"}`;
  }
  if (validationNode) {
    const enabledRows = rows.filter((row) => asBool(row.enabled, true));
    const duplicateCheck = {};
    const duplicates = [];
    enabledRows.forEach((row) => {
      const entityId = String(row.entity_id || "").trim().toLowerCase();
      if (!entityId) return;
      if (duplicateCheck[entityId]) duplicates.push(entityId);
      duplicateCheck[entityId] = true;
    });
    const missingEntityCount = enabledRows.filter((row) => !String(row.entity_id || "").trim()).length;
    const lines = [];
    lines.push(`Enabled elements: ${enabledRows.length}`);
    lines.push(`Missing entity IDs: ${missingEntityCount}`);
    lines.push(`Duplicate mapped entities: ${duplicates.length}`);
    validationNode.textContent = lines.join(" | ");
    validationNode.classList.remove("status-ok", "status-warn", "status-error");
    if (missingEntityCount > 0 || duplicates.length > 0) validationNode.classList.add("status-warn");
    else validationNode.classList.add("status-ok");
  }
}

async function addEntityInstance() {
  const typeId = (e("instance_type_select")?.value || "light").trim();
  const pageValue = (e("instance_page_select")?.value || "").trim();
  const item = {
    id: `${typeId}_${Date.now()}`,
    type: typeId,
    name: e("instance_name_input")?.value?.trim() || `${typeId} element`,
    entity_id: e("instance_entity_input")?.value?.trim() || "",
    role: e("instance_role_input")?.value?.trim() || "",
    enabled: true,
    page:
      pageValue ||
      (typeId === "weather"
        ? "weather"
        : typeId === "climate"
          ? "climate"
          : typeId === "camera"
            ? "cameras"
            : typeId === "light"
              ? "lights"
              : "home"),
  };
  await applyInstanceOp([{ op: "add", item }], "Added typed element");
  if (e("instance_name_input")) e("instance_name_input").value = "";
  if (e("instance_entity_input")) e("instance_entity_input").value = "";
  if (e("instance_role_input")) e("instance_role_input").value = "";
  if (e("instance_entity_pick")) e("instance_entity_pick").innerHTML = `<option value="">Pick from ranked suggestions...</option>`;
}

async function refreshNewInstanceSuggestions() {
  const input = e("instance_entity_input");
  const pick = e("instance_entity_pick");
  if (!input && !pick) return;
  const item = {
    id: "new_instance",
    type: e("instance_type_select")?.value || "sensor",
    role: e("instance_role_input")?.value || "",
  };
  await queueInstanceSuggestions(input, item, pick);
}

async function catalogAutodetect() {
  const data = await apiPost("api/catalog/autodetect", profilePayload());
  state.workspace = ensureWorkspace(data.workspace || state.workspace, state.contracts.defaults || {});
  state.activeDeviceIndex = Number(data.active_device_index || state.workspace.active_device_index || 0);
  state.catalogDetected = Array.isArray(data.detected) ? data.detected : [];
  syncProfileToForm();
  const out = e("catalog_detected_meta");
  if (out) {
    out.textContent = state.catalogDetected.length
      ? `Detected ${state.catalogDetected.length} candidates. Top: ${state.catalogDetected.slice(0, 6).map((x) => `${x.type}:${x.entity_id}`).join(" | ")}`
      : "No typed candidates detected.";
  }
  setStatus(`Typed autodetect completed (${state.catalogDetected.length} candidates)`);
}

async function catalogAcceptDetected() {
  const data = await apiPost("api/catalog/accept_detected", profilePayload());
  state.workspace = ensureWorkspace(data.workspace || state.workspace, state.contracts.defaults || {});
  state.activeDeviceIndex = Number(data.active_device_index || state.workspace.active_device_index || 0);
  syncProfileToForm();
  setStatus(`Accepted detected typed elements (+${Number(data.added || 0)})`);
}

async function catalogIgnoreDetected() {
  const data = await apiPost("api/catalog/ignore_detected", profilePayload());
  state.workspace = ensureWorkspace(data.workspace || state.workspace, state.contracts.defaults || {});
  state.activeDeviceIndex = Number(data.active_device_index || state.workspace.active_device_index || 0);
  syncProfileToForm();
  setStatus(`Ignored ${Array.isArray(data.ignored) ? data.ignored.length : 0} detected entities`);
}

function syncSlotsFromCollections(profile) {
  ensureCollections(profile);
  const enabledLights = profile.entity_collections.lights.filter((x) => asBool(x.enabled));
  const enabledCameras = profile.entity_collections.cameras.filter((x) => asBool(x.enabled));
  profile.slots = profile.slots || {};
  const lightCap = clampInt(profile.slot_runtime?.light_slot_cap || 24, 8, 48);
  const cameraCap = clampInt(profile.slot_runtime?.camera_slot_cap || 8, 2, 16);
  profile.slots.light_slot_count = Math.max(1, Math.min(lightCap, enabledLights.length || 1));
  profile.slots.camera_slot_count = Math.max(0, Math.min(cameraCap, enabledCameras.length || 0));
  profile.slots.lights = [];
  profile.slots.cameras = [];
  for (let i = 0; i < lightCap; i += 1) {
    const item = enabledLights[i] || {};
    profile.slots.lights.push({
      name: item.name || `Light ${i + 1}`,
      entity: item.entity_id || `light.replace_me_slot_${i + 1}`,
    });
  }
  for (let i = 0; i < cameraCap; i += 1) {
    const item = enabledCameras[i] || {};
    profile.slots.cameras.push({
      name: item.name || `Camera ${i + 1}`,
      entity: item.entity_id || `camera.replace_me_${i + 1}`,
    });
  }
  profile.slots.legacy_lights = profile.slots.lights.slice(0, 8);
  profile.slots.legacy_cameras = profile.slots.cameras.slice(0, 2);
}

function collectionDomainHint(collectionName) {
  if (collectionName === "lights") return "light";
  if (collectionName === "cameras") return "camera";
  if (collectionName === "weather_metrics") return "sensor";
  if (collectionName === "climate_controls") return "climate";
  return "";
}

function setCollectionDirty(isDirty = true) {
  state.collectionDirty = !!isDirty;
}

function renderSlotCapsSummary() {
  const p = currentProfile();
  if (!p) return;
  ensureCollections(p);
  const out = e("slot_caps_summary");
  if (!out) return;
  const enabledLights = (p.entity_collections?.lights || []).filter((x) => asBool(x.enabled)).length;
  const enabledCameras = (p.entity_collections?.cameras || []).filter((x) => asBool(x.enabled)).length;
  const lightCap = Number(p.slot_runtime?.light_slot_cap || 24);
  const cameraCap = Number(p.slot_runtime?.camera_slot_cap || 8);
  const lightPage = Number(p.slot_runtime?.light_page_size || 6);
  const cameraPage = Number(p.slot_runtime?.camera_page_size || 4);
  out.textContent =
    `Lights enabled ${enabledLights}/${lightCap} (page ${lightPage})\n` +
    `Cameras enabled ${enabledCameras}/${cameraCap} (page ${cameraPage})\n` +
    `Profile state: ${state.collectionDirty ? "unsaved changes" : "synced"}`;
  out.style.color = (enabledLights > lightCap || enabledCameras > cameraCap) ? "#ffb4c0" : "";
}

async function bulkApplyOps(ops, successText = "") {
  const body = profilePayload();
  body.ops = Array.isArray(ops) ? ops : [];
  body.persist = false;
  const data = await apiPost("api/entities/bulk_apply", body);
  state.workspace = ensureWorkspace(data.workspace || state.workspace, state.contracts.defaults || {});
  state.activeDeviceIndex = Number(data.active_device_index || state.workspace.active_device_index || 0);
  syncProfileToForm();
  setCollectionDirty(true);
  renderSlotCapsSummary();
  if (successText) setStatus(successText);
  return data;
}

async function updateCollectionItem(collectionName, itemId, patch) {
  await bulkApplyOps([{ op: "update", collection: collectionName, item_id: itemId, patch }]);
}

async function queueEntitySuggestions(inputNode, collectionName, item) {
  if (!inputNode || !item) return;
  const key = inputNode.id;
  if (state.rowSuggestTimers[key]) clearTimeout(state.rowSuggestTimers[key]);
  state.rowSuggestTimers[key] = setTimeout(async () => {
    try {
      const payload = {
        key: item.role || item.id || "",
        q: inputNode.value || "",
        limit: 30,
        collection: collectionName,
        role: item.role || "",
        domain_hint: collectionDomainHint(collectionName),
        device_slug: effectiveInstanceDeviceScope(),
        exclude_assigned: true,
        active_device_slug: getDeviceSlug(),
        workspace: state.workspace?.workspace_name || "default",
      };
      const data = await apiPost("api/mapping/suggest", payload);
      const listId = `${inputNode.id}_list`;
      let datalist = e(listId);
      if (!datalist) {
        datalist = document.createElement("datalist");
        datalist.id = listId;
        inputNode.insertAdjacentElement("afterend", datalist);
        inputNode.setAttribute("list", listId);
      }
      datalist.innerHTML = "";
      (data.suggestions || []).forEach((row) => {
        const opt = document.createElement("option");
        opt.value = row.entity_id || "";
        opt.label = `${row.friendly_name || row.entity_id || ""} | ${row.reason || "ranked"} | score ${row.score || 0}`;
        datalist.appendChild(opt);
      });
    } catch (_err) {
      // suggestions are best-effort; field remains editable.
    }
  }, 220);
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
      <td>
        <input id="${rid}_entity" class="entity-combo-input" value="${safeText(item.entity_id || "")}" placeholder="Type or pick an entity..." />
      </td>
      <td><input type="checkbox" id="${rid}_enabled" ${asBool(item.enabled) ? "checked" : ""} /></td>
      <td class="row-actions">
        <button class="btn-soft" id="${rid}_select">Select</button>
        <button class="btn-soft" id="${rid}_clear">Clear</button>
        <button class="btn-soft" id="${rid}_dup">Duplicate</button>
        <button class="btn-soft" id="${rid}_up">Up</button>
        <button class="btn-soft" id="${rid}_down">Down</button>
        <button class="btn-warn" id="${rid}_del">Delete</button>
      </td>
    `;
    body.appendChild(tr);

    const nameNode = e(`${rid}_name`);
    const entityNode = e(`${rid}_entity`);
    const enabledNode = e(`${rid}_enabled`);

    nameNode?.addEventListener("change", (ev) => {
      updateCollectionItem(collectionName, item.id, { name: ev.target.value }).catch((err) =>
        setStatus(`Row update failed: ${err.message}`, true)
      );
    });

    entityNode?.addEventListener("focus", (ev) => {
      markActiveInput(ev.target);
      queueEntitySuggestions(entityNode, collectionName, item);
    });
    entityNode?.addEventListener("input", () => {
      queueEntitySuggestions(entityNode, collectionName, item);
    });
    entityNode?.addEventListener("change", (ev) => {
      updateCollectionItem(collectionName, item.id, { entity_id: ev.target.value }).catch((err) =>
        setStatus(`Entity update failed: ${err.message}`, true)
      );
    });

    enabledNode?.addEventListener("change", (ev) => {
      updateCollectionItem(collectionName, item.id, { enabled: ev.target.checked }).catch((err) =>
        setStatus(`Enable toggle failed: ${err.message}`, true)
      );
    });

    e(`${rid}_select`)?.addEventListener("click", async () => {
      try {
        const payload = {
          key: item.role || item.id || "",
          q: entityNode?.value || "",
          limit: 10,
          collection: collectionName,
          role: item.role || "",
          domain_hint: collectionDomainHint(collectionName),
          exclude_assigned: true,
          active_device_slug: getDeviceSlug(),
          workspace: state.workspace?.workspace_name || "default",
        };
        const data = await apiPost("api/mapping/suggest", payload);
        const top = (data.suggestions || [])[0];
        if (!top?.entity_id) {
          setStatus("No ranked suggestions found for this row", true);
          return;
        }
        await updateCollectionItem(collectionName, item.id, { entity_id: top.entity_id });
        setStatus(`Mapped ${item.name || item.id} -> ${top.entity_id}`);
      } catch (err) {
        setStatus(`Select failed: ${err.message}`, true);
      }
    });

    e(`${rid}_clear`)?.addEventListener("click", () => {
      updateCollectionItem(collectionName, item.id, { entity_id: "" }).catch((err) =>
        setStatus(`Clear failed: ${err.message}`, true)
      );
    });
    e(`${rid}_dup`)?.addEventListener("click", async () => {
      try {
        await bulkApplyOps([
          {
            op: "add",
            collection: collectionName,
            item: {
              name: `${item.name || "Copy"} Copy`,
              entity_id: item.entity_id || "",
              role: item.role || "",
              enabled: asBool(item.enabled),
            },
          },
        ], `${collectionName}: duplicated row`);
      } catch (err) {
        setStatus(`Duplicate failed: ${err.message}`, true);
      }
    });
    e(`${rid}_up`)?.addEventListener("click", () => {
      if (idx <= 0) return;
      bulkApplyOps([{ op: "reorder", collection: collectionName, from_index: idx, to_index: idx - 1 }], `${collectionName}: moved row`)
        .catch((err) => setStatus(`Reorder failed: ${err.message}`, true));
    });
    e(`${rid}_down`)?.addEventListener("click", () => {
      if (idx >= rows.length - 1) return;
      bulkApplyOps([{ op: "reorder", collection: collectionName, from_index: idx, to_index: idx + 1 }], `${collectionName}: moved row`)
        .catch((err) => setStatus(`Reorder failed: ${err.message}`, true));
    });
    e(`${rid}_del`)?.addEventListener("click", () => {
      bulkApplyOps([{ op: "remove", collection: collectionName, item_id: item.id }], `${collectionName}: row removed`)
        .catch((err) => setStatus(`Delete failed: ${err.message}`, true));
    });
  });
}

function renderCollections() {
  const p = currentProfile();
  if (!p) return;
  ensureCollections(p);
  if (e("lights_max")) e("lights_max").value = String(p.entity_collections.limits?.lights_max || 24);
  if (e("cameras_max")) e("cameras_max").value = String(p.entity_collections.limits?.cameras_max || 8);
  if (e("light_slot_cap")) e("light_slot_cap").value = String(p.slot_runtime?.light_slot_cap || 24);
  if (e("camera_slot_cap")) e("camera_slot_cap").value = String(p.slot_runtime?.camera_slot_cap || 8);
  if (e("light_page_size")) e("light_page_size").value = String(p.slot_runtime?.light_page_size || 6);
  if (e("camera_page_size")) e("camera_page_size").value = String(p.slot_runtime?.camera_page_size || 4);
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
      `Mapped to FW slots: lights=${p.slots?.light_slot_count || 0}/${p.slot_runtime?.light_slot_cap || 24} cameras=${p.slots?.camera_slot_count || 0}/${p.slot_runtime?.camera_slot_cap || 8}`;
  }
  const health = e("collections_summary");
  if (health) {
    health.textContent =
      `lights=${p.entity_collections.lights.length} | cameras=${p.entity_collections.cameras.length}\n` +
      `weather_metrics=${(p.entity_collections.weather_metrics || []).length} | climate_controls=${(p.entity_collections.climate_controls || []).length}\n` +
      `reader_feeds=${(p.entity_collections.reader_feeds || []).length} | system_entities=${(p.entity_collections.system_entities || []).length}`;
  }
  renderSlotCapsSummary();
}

async function refreshSlotCaps() {
  const data = await apiGet(`api/entities/slot_caps?workspace=${encodeURIComponent(state.workspace?.workspace_name || "default")}&device_slug=${encodeURIComponent(getDeviceSlug())}`);
  const p = currentProfile();
  if (p && data.slot_runtime) {
    p.slot_runtime = {
      ...(p.slot_runtime || {}),
      ...data.slot_runtime,
    };
    syncSlotsFromCollections(p);
  }
  renderCollections();
  const enabled = data.enabled_counts || {};
  const overflow = data.overflow || {};
  setStatus(
    `Slot caps refreshed. lights=${enabled.lights || 0}/${data.slot_runtime?.light_slot_cap || "--"} cameras=${enabled.cameras || 0}/${data.slot_runtime?.camera_slot_cap || "--"}`,
    !!(overflow.lights || overflow.cameras)
  );
}

async function autoFitSlotCaps() {
  const data = await apiPost("api/entities/auto_fit_caps", profilePayload());
  state.workspace = ensureWorkspace(data.workspace || state.workspace, state.contracts.defaults || {});
  state.activeDeviceIndex = Number(data.active_device_index || state.workspace.active_device_index || 0);
  syncProfileToForm();
  setCollectionDirty(true);
  setStatus(data.changed ? "Auto-fit increased slot caps to match enabled rows" : "Auto-fit found no cap changes");
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
      <td><input id="${rid}_entity" class="entity-combo-input" value="${safeText(item.entity_id || "")}" placeholder="Type or pick an entity..." /></td>
      <td><input id="${rid}_role" value="${safeText(item.role || "")}" placeholder="entity_* substitution key" /></td>
      <td><input type="checkbox" id="${rid}_enabled" ${asBool(item.enabled) ? "checked" : ""} /></td>
      <td>
        <button class="btn-soft" id="${rid}_select">Select</button>
        <button class="btn-soft" id="${rid}_up">Up</button>
        <button class="btn-soft" id="${rid}_down">Down</button>
        <button class="btn-warn" id="${rid}_del">Del</button>
      </td>
    `;
    body.appendChild(tr);
    e(`${rid}_name`)?.addEventListener("change", (ev) => {
      updateCollectionItem(collectionName, item.id, { name: ev.target.value }).catch((err) =>
        setStatus(`Row update failed: ${err.message}`, true)
      );
    });
    const entityNode = e(`${rid}_entity`);
    entityNode?.addEventListener("input", () => {
      queueEntitySuggestions(entityNode, collectionName, item);
    });
    entityNode?.addEventListener("focus", (ev) => {
      markActiveInput(ev.target);
      queueEntitySuggestions(entityNode, collectionName, item);
    });
    entityNode?.addEventListener("change", (ev) => {
      updateCollectionItem(collectionName, item.id, { entity_id: ev.target.value }).catch((err) =>
        setStatus(`Entity update failed: ${err.message}`, true)
      );
    });
    e(`${rid}_role`)?.addEventListener("change", (ev) => {
      updateCollectionItem(collectionName, item.id, { role: ev.target.value }).catch((err) =>
        setStatus(`Role update failed: ${err.message}`, true)
      );
    });
    e(`${rid}_enabled`)?.addEventListener("change", (ev) => {
      updateCollectionItem(collectionName, item.id, { enabled: ev.target.checked }).catch((err) =>
        setStatus(`Enable toggle failed: ${err.message}`, true)
      );
    });
    e(`${rid}_select`)?.addEventListener("click", async () => {
      try {
        const data = await apiPost("api/mapping/suggest", {
          key: item.role || item.id || "",
          q: entityNode?.value || "",
          limit: 10,
          collection: collectionName,
          role: item.role || "",
          domain_hint: collectionDomainHint(collectionName),
          exclude_assigned: true,
          active_device_slug: getDeviceSlug(),
          workspace: state.workspace?.workspace_name || "default",
        });
        const top = (data.suggestions || [])[0];
        if (!top?.entity_id) {
          setStatus("No ranked suggestions found for this row", true);
          return;
        }
        await updateCollectionItem(collectionName, item.id, { entity_id: top.entity_id });
      } catch (err) {
        setStatus(`Select failed: ${err.message}`, true);
      }
    });
    e(`${rid}_up`)?.addEventListener("click", () => {
      if (idx <= 0) return;
      bulkApplyOps([{ op: "reorder", collection: collectionName, from_index: idx, to_index: idx - 1 }]).catch((err) =>
        setStatus(`Reorder failed: ${err.message}`, true)
      );
    });
    e(`${rid}_down`)?.addEventListener("click", () => {
      if (idx >= rows.length - 1) return;
      bulkApplyOps([{ op: "reorder", collection: collectionName, from_index: idx, to_index: idx + 1 }]).catch((err) =>
        setStatus(`Reorder failed: ${err.message}`, true)
      );
    });
    e(`${rid}_del`)?.addEventListener("click", () => {
      bulkApplyOps([{ op: "remove", collection: collectionName, item_id: item.id }]).catch((err) =>
        setStatus(`Delete failed: ${err.message}`, true)
      );
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
  bulkApplyOps(
    [
      {
        op: "add",
        collection: collectionName,
        item: {
          id: `${collectionName.slice(0, -1)}_${idx}`,
          name: `${collectionName.slice(0, -1).toUpperCase()} ${idx}`,
          entity_id: "",
          role: meta.role || "",
          enabled: true,
        },
      },
    ],
    `${collectionName}: row added`
  ).catch((err) => setStatus(`Add failed: ${err.message}`, true));
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

function generateLayoutDefaultsFromFeatures() {
  ensureLayoutPages();
  const defaults = deepClone(state.contracts?.layout_defaults || {});
  const p = currentProfile();
  if (!p) return;
  const pageToFeature = {
    lights: "lights",
    weather: "weather",
    climate: "climate",
    reader: "reader",
    cameras: "cameras",
  };
  const enabledFeaturePages = Object.entries(pageToFeature)
    .filter(([, feature]) => asBool(p.features?.[feature], false))
    .map(([page]) => page);
  state.workspace.layout_pages = state.workspace.layout_pages || {};
  Object.keys(defaults).forEach((pageId) => {
    if (pageId === "home" || pageId === "settings" || pageId === "theme" || enabledFeaturePages.includes(pageId)) {
      state.workspace.layout_pages[pageId] = deepClone(defaults[pageId]);
    }
  });
  renderLayoutSections();
  const node = e("layout_preview_meta");
  if (node) node.textContent = `Generated defaults for pages: home, settings, theme${enabledFeaturePages.length ? `, ${enabledFeaturePages.join(", ")}` : ""}`;
  setStatus("Generated sensible layout defaults from enabled features");
}

function renderDeployPreflight(validation = null, caps = null) {
  const body = e("deploy_preflight_body");
  const meta = e("deploy_preflight_meta");
  if (!body) return;
  const p = currentProfile();
  const fw = caps || state.firmwareStatus?.capabilities || {};
  const val = validation || null;
  const checks = [
    {
      name: "Device selected",
      ok: !!getDeviceSlug(),
      detail: getDeviceSlug() || "No active device.",
    },
    {
      name: "Typed elements configured",
      ok: Array.isArray(p?.entity_instances) && p.entity_instances.filter((x) => asBool(x.enabled, true)).length > 0,
      detail: `${Array.isArray(p?.entity_instances) ? p.entity_instances.length : 0} total elements`,
    },
    {
      name: "Validation",
      ok: val ? asBool(val.ok, false) : null,
      detail: val ? `${(val.errors || []).length} errors, ${(val.warnings || []).length} warnings` : "Run Validate Workspace",
    },
    {
      name: "Firmware method",
      ok: asBool(fw?.has_any_automatic_method, false),
      detail: fw?.recommended_method || "manual_fallback",
    },
  ];
  body.innerHTML = "";
  checks.forEach((row) => {
    const tr = document.createElement("tr");
    const statusText = row.ok === null ? "pending" : row.ok ? "ok" : "fail";
    tr.innerHTML = `<td>${safeText(row.name)}</td><td>${safeText(statusText)}</td><td>${safeText(row.detail || "")}</td>`;
    tr.className = row.ok === null ? "status-warn" : row.ok ? "status-ok" : "status-error";
    body.appendChild(tr);
  });
  if (meta) {
    const failed = checks.filter((x) => x.ok === false).length;
    if (!failed) meta.textContent = "Preflight ready. You can run Backup + Deploy Firmware.";
    else meta.textContent = `Preflight has ${failed} blocking item(s). Resolve failures before deploy.`;
    meta.classList.remove("status-ok", "status-warn", "status-error");
    meta.classList.add(failed ? "status-error" : "status-ok");
  }
}

function renderFieldGroup(containerId, fields, sourceObjName) {
  const p = currentProfile();
  const host = e(containerId);
  if (!host || !p) return;
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

function renderThemeQuickActions() {
  const host = e("theme_quick_actions");
  if (!host) return;
  host.innerHTML = "";
  const palettes = Array.isArray(state.themePalettes) ? state.themePalettes : [];
  if (!palettes.length) return;
  palettes.slice(0, 6).forEach((palette) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn-soft";
    btn.textContent = palette?.name || palette?.id || "Palette";
    btn.addEventListener("click", () => {
      if (e("theme_palette_select")) e("theme_palette_select").value = palette.id || "";
      previewTheme().catch((err) => setStatus(`Theme preview failed: ${err.message}`, true));
    });
    host.appendChild(btn);
  });
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

async function resetThemeSafe() {
  const body = profilePayload();
  body.palette_id = e("theme_palette_select")?.value || "ocean_dark";
  const data = await apiPost("api/theme/reset_safe", body);
  state.workspace = ensureWorkspace(data.workspace || state.workspace, state.contracts.defaults || {});
  state.activeDeviceIndex = Number(data.active_device_index || state.workspace.active_device_index || 0);
  syncProfileToForm();
  renderThemePreviewCard(data.tokens || currentThemeTokensForPreview(), "Theme reset to safe defaults.");
  setStatus("Theme reset to safe defaults");
}

function syncProfileToForm() {
  const p = currentProfile();
  if (!p) return;
  setCollectionDirty(false);
  ensureThemeStudio(p);
  ensureLayoutPages();
  ensureCollections(p);
  ensureEntityInstances(p);
  applyProfileBasicsToForm();
  renderInstanceTypeOptions();
  renderInstanceDeviceScopeOptions();
  if (e("instance_page_select") && !e("instance_page_select").value) e("instance_page_select").value = "home";
  renderEntityInstances();
  renderFeatureToggles();
  renderUiToggles();

  if (e("ha_base_url")) e("ha_base_url").value = p.settings.ha_base_url || "";
  if (e("camera_refresh_interval_s")) e("camera_refresh_interval_s").value = p.settings.camera_refresh_interval_s || "60";
  if (e("camera_snapshot_dir")) e("camera_snapshot_dir").value = p.settings.camera_snapshot_dir || "/config/www/tdeck";
  if (e("camera_snapshot_enable")) e("camera_snapshot_enable").checked = asBool(p.settings.camera_snapshot_enable);
  if (e("onboarding_preset_select")) e("onboarding_preset_select").value = p.settings?.onboarding_preset || "blank";

  renderCollections();
  state.cameraAutodetect = p.camera_autodetect || state.workspace?.camera_autodetect || {};
  renderCameraAutodetect(state.cameraAutodetect);
  renderFieldGroup("weather_fields", WEATHER_FIELDS, "entities");
  renderFieldGroup("climate_fields", CLIMATE_FIELDS, "entities");
  renderFieldGroup("reader_fields", READER_FIELDS, "entities");
  renderFieldGroup("theme_fields", THEME_FIELDS, "theme");
  renderTemplateDomains();
  renderThemePalettes();
  renderThemeQuickActions();

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
  renderDeployPreflight();
  refreshNewInstanceSuggestions().catch(() => {});
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
  const defaultGitUrl = state.contracts?.defaults?.git_url || state.contracts?.defaults?.repo_url || "https://github.com/owner/repository.git";
  p.device.git_url = e("git_url").value.trim() || defaultGitUrl;
  p.settings.app_release_channel = "stable";
  p.settings.app_release_version = e("app_release_version").value.trim() || (state.contracts?.defaults?.app_release_version || "v0.25.0");
  p.settings.onboarding_preset = e("onboarding_preset_select")?.value?.trim() || p.settings.onboarding_preset || "blank";
  ensureCollections(p);
  if (e("lights_max")) p.entity_collections.limits.lights_max = Number(e("lights_max").value || "24");
  if (e("cameras_max")) p.entity_collections.limits.cameras_max = Number(e("cameras_max").value || "8");
  if (e("light_slot_cap")) p.slot_runtime.light_slot_cap = clampInt(e("light_slot_cap").value || "24", 8, 48);
  if (e("camera_slot_cap")) p.slot_runtime.camera_slot_cap = clampInt(e("camera_slot_cap").value || "8", 2, 16);
  if (e("light_page_size")) p.slot_runtime.light_page_size = clampInt(e("light_page_size").value || "6", 4, 8);
  if (e("camera_page_size")) p.slot_runtime.camera_page_size = clampInt(e("camera_page_size").value || "4", 2, 6);
  if (e("additional_collection_max")) {
    const collection = currentAdditionalCollection();
    const meta = COLLECTION_META[collection] || { limitKey: `${collection}_max`, defaultMax: 24 };
    p.entity_collections.limits[meta.limitKey] = Number(e("additional_collection_max").value || String(meta.defaultMax));
  }
  if (e("ha_base_url")) p.settings.ha_base_url = e("ha_base_url").value.trim();
  if (e("camera_refresh_interval_s")) p.settings.camera_refresh_interval_s = e("camera_refresh_interval_s").value.trim();
  if (e("camera_snapshot_dir")) p.settings.camera_snapshot_dir = e("camera_snapshot_dir").value.trim();
  if (e("camera_snapshot_enable")) p.settings.camera_snapshot_enable = e("camera_snapshot_enable").checked;
  if (e("ha_native_firmware_entity")) {
    p.settings.ha_native_firmware_entity = e("ha_native_firmware_entity").value.trim();
  }
  if (e("ha_installed_version_entity")) {
    p.settings.ha_app_version_entity = e("ha_installed_version_entity").value.trim();
  }
  state.workspace.deployment.git_ref = p.device.git_ref;
  state.workspace.deployment.git_url = p.device.git_url;
  state.workspace.deployment.app_release_version = p.settings.app_release_version;
  applyFeaturePagePolicyInProfile(p);
  syncSlotsFromCollections(p);
  setCollectionDirty(true);
  renderSlotCapsSummary();
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
  ["workspace_name", "profile_name", "device_name", "device_friendly_name", "git_ref", "git_url", "app_release_version", "onboarding_preset_select", "ha_base_url", "camera_refresh_interval_s", "camera_snapshot_dir", "ha_installed_version_entity", "ha_native_firmware_entity", "light_slot_cap", "camera_slot_cap", "light_page_size", "camera_page_size"]
    .forEach((id) => {
      const node = e(id);
      if (node) node.addEventListener("input", updateProfileFromTopFields);
      if (node && id === "onboarding_preset_select") node.addEventListener("change", updateProfileFromTopFields);
    });

  e("camera_snapshot_enable")?.addEventListener("change", updateProfileFromTopFields);

  e("device_select")?.addEventListener("change", (ev) => {
    state.activeDeviceIndex = Number(ev.target.value || "0");
    state.workspace.active_device_index = state.activeDeviceIndex;
    syncProfileToForm();
  });
  e("device_add_btn")?.addEventListener("click", addDevice);
  e("device_clone_btn")?.addEventListener("click", cloneDevice);
  e("device_remove_btn")?.addEventListener("click", removeDevice);

  e("instance_enable_all_btn")?.addEventListener("click", () => {
    applyInstanceOp([{ op: "enable_all" }], "Enabled all typed elements").catch((err) =>
      setStatus(`Enable all failed: ${err.message}`, true)
    );
  });
  e("instance_disable_all_btn")?.addEventListener("click", () => {
    applyInstanceOp([{ op: "disable_all" }], "Disabled all typed elements").catch((err) =>
      setStatus(`Disable all failed: ${err.message}`, true)
    );
  });
  e("instance_dedupe_btn")?.addEventListener("click", () => {
    applyInstanceOp([{ op: "dedupe" }], "Deduped typed elements").catch((err) =>
      setStatus(`Dedupe failed: ${err.message}`, true)
    );
  });
  e("instance_remove_disabled_btn")?.addEventListener("click", () => {
    applyInstanceOp([{ op: "remove_disabled" }], "Removed disabled typed elements").catch((err) =>
      setStatus(`Remove disabled failed: ${err.message}`, true)
    );
  });

  e("instance_type_select")?.addEventListener("change", () => {
    const typeId = e("instance_type_select")?.value || "sensor";
    if (e("instance_page_select")) {
      e("instance_page_select").value =
        typeId === "weather"
          ? "weather"
          : typeId === "climate"
            ? "climate"
            : typeId === "camera"
              ? "cameras"
              : typeId === "light"
                ? "lights"
                : "home";
    }
    refreshNewInstanceSuggestions().catch(() => {});
  });
  e("instance_role_input")?.addEventListener("input", () => {
    refreshNewInstanceSuggestions().catch(() => {});
  });
  e("instance_entity_input")?.addEventListener("focus", () => {
    refreshNewInstanceSuggestions().catch(() => {});
  });
  e("instance_entity_input")?.addEventListener("input", () => {
    refreshNewInstanceSuggestions().catch(() => {});
  });
  e("instance_entity_pick")?.addEventListener("change", (ev) => {
    const value = String(ev.target.value || "").trim();
    if (!value) return;
    if (e("instance_entity_input")) e("instance_entity_input").value = value;
  });
  e("instance_device_scope")?.addEventListener("change", () => {
    state.instanceDeviceScope = (e("instance_device_scope")?.value || "active").trim();
    refreshNewInstanceSuggestions().catch(() => {});
    renderEntityInstances();
  });
  e("slot_caps_refresh_btn")?.addEventListener("click", () => {
    refreshSlotCaps().catch((err) => setStatus(`Slot caps refresh failed: ${err.message}`, true));
  });
  e("slot_caps_fit_btn")?.addEventListener("click", () => {
    autoFitSlotCaps().catch((err) => setStatus(`Auto-fit failed: ${err.message}`, true));
  });
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

function effectiveInstanceDeviceScope() {
  const raw = (e("instance_device_scope")?.value || state.instanceDeviceScope || "active").trim();
  if (!raw || raw === "all") return "";
  if (raw === "active") return getDeviceSlug();
  return slugify(raw);
}

function renderInstanceDeviceScopeOptions() {
  const select = e("instance_device_scope");
  if (!select) return;
  const prev = (select.value || state.instanceDeviceScope || "active").trim();
  const activeSlug = getDeviceSlug();
  const options = [];
  options.push({ value: "active", label: `Active Device (${activeSlug})` });
  options.push({ value: "all", label: "All Entities" });
  const seen = new Set(["active", "all"]);
  if (activeSlug) {
    seen.add(activeSlug);
    options.push({ value: activeSlug, label: `Current Slug (${activeSlug})` });
  }
  const nodes = Array.isArray(state.onboardingNodes) ? state.onboardingNodes : [];
  nodes.forEach((row) => {
    const slug = slugify(row?.device_slug || "");
    if (!slug || seen.has(slug)) return;
    seen.add(slug);
    const friendly = String(row?.friendly_name || slug);
    options.push({ value: slug, label: `${friendly} (${slug})` });
  });
  select.innerHTML = "";
  options.forEach((row) => {
    const opt = document.createElement("option");
    opt.value = row.value;
    opt.textContent = row.label;
    select.appendChild(opt);
  });
  const restored = options.some((x) => x.value === prev) ? prev : "active";
  select.value = restored;
  state.instanceDeviceScope = restored;
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
  if (transport.api_base_hint) {
    state.transport.ingress_hint = transport.api_base_hint;
  } else if (data.ingress_expected_prefix) {
    state.transport.ingress_hint = data.ingress_expected_prefix;
  }
  const discovery = data.discovery || {};
  const firmwareCaps = data.firmware_capability_summary || {};
  e("health_summary").textContent =
    `Addon version: ${data.addon_version || "--"}\n` +
    `Frontend asset version: ${data.frontend_asset_version || INDEX_ASSET_VERSION || "--"}\n` +
    `Addon updated flag: ${data.addon_updated_since_last_run ? "yes" : "no"}\n` +
    `Firmware summary: ${data.firmware_status_summary || "--"}\n` +
    `Firmware method: ${firmwareCaps.recommended_method || "--"}\n` +
    `HA: ${haStatus}\n` +
    `Transport path: ${transport.request_path || "--"}\n` +
    `Transport base hint: ${transport.api_base_hint || "--"}\n` +
    `Ingress expected prefix: ${data.ingress_expected_prefix || "--"}\n` +
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
  const targetVersion = encodeURIComponent(p?.settings?.app_release_version || (state.contracts?.defaults?.app_release_version || "v0.25.0"));
  const nativeEntity = encodeURIComponent((p?.settings?.ha_native_firmware_entity || "").trim());
  const appVersionEntity = encodeURIComponent((p?.settings?.ha_app_version_entity || "").trim());
  return `api/firmware/status?device_slug=${encodeURIComponent(slug)}&target_version=${targetVersion}&native_firmware_entity=${nativeEntity}&app_version_entity=${appVersionEntity}`;
}

function firmwareCapabilitiesQuery() {
  const p = currentProfile();
  const slug = getDeviceSlug();
  const targetVersion = encodeURIComponent(p?.settings?.app_release_version || (state.contracts?.defaults?.app_release_version || "v0.25.0"));
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
  renderDeployPreflight(null, capabilities);
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
  body.target_version = e("app_release_version")?.value?.trim() || (state.contracts?.defaults?.app_release_version || "v0.25.0");

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
  renderDeployPreflight(data, state.firmwareStatus?.capabilities || null);
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
  const body = profilePayload();
  body.require_confirm = false;
  body.confirmed = true;
  body.run_firmware = true;
  body.firmware_mode = "auto";
  const data = await apiPost("api/deploy/run", body);
  if (!data.ok) {
    const reason = data.error || data.firmware?.error || "deploy_failed";
    throw new Error(reason);
  }
  e("apply_preview_install_diff").textContent = data.preview?.install?.diff || "No install diff.";
  e("apply_preview_overrides_diff").textContent = data.preview?.overrides?.diff || "No overrides diff.";
  e("apply_preview_generated_diff").textContent = [
    data.preview?.generated?.entities?.diff || "No generated entities diff.",
    "",
    data.preview?.generated?.theme?.diff || "No generated theme diff.",
    "",
    data.preview?.generated?.layout?.diff || "No generated layout diff.",
  ].join("\n");
  await generate();
  await refreshBackups();
  await refreshFirmwareStatus();
  renderDeployPreflight(validation, state.firmwareStatus?.capabilities || null);
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
  renderThemeQuickActions();
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
  e("onboarding_scan_nodes_btn")?.addEventListener("click", () => {
    refreshOnboardingNodes(true).catch((err) => setStatus(`Node scan failed: ${err.message}`, true));
  });
  e("onboarding_start_new_btn")?.addEventListener("click", () => {
    onboardingStartNew().catch((err) => setStatus(`Start New failed: ${err.message}`, true));
  });
  e("onboarding_import_btn")?.addEventListener("click", () => {
    onboardingImportExisting().catch((err) => setStatus(`Import failed: ${err.message}`, true));
  });
  e("onboarding_verify_btn")?.addEventListener("click", () => {
    onboardingVerifyCandidate().catch((err) => setStatus(`Verify failed: ${err.message}`, true));
  });
  e("onboarding_migrate_btn")?.addEventListener("click", () => {
    onboardingMigrateManaged().catch((err) => setStatus(`Migrate failed: ${err.message}`, true));
  });
  e("instance_add_btn")?.addEventListener("click", () => {
    addEntityInstance().catch((err) => setStatus(`Add element failed: ${err.message}`, true));
  });
  e("instance_autodetect_btn")?.addEventListener("click", () => {
    catalogAutodetect().catch((err) => setStatus(`Autodetect failed: ${err.message}`, true));
  });
  e("instance_accept_detected_btn")?.addEventListener("click", () => {
    catalogAcceptDetected().catch((err) => setStatus(`Accept detected failed: ${err.message}`, true));
  });
  e("instance_ignore_detected_btn")?.addEventListener("click", () => {
    catalogIgnoreDetected().catch((err) => setStatus(`Ignore detected failed: ${err.message}`, true));
  });
  e("instance_entity_input")?.addEventListener("focus", (ev) => {
    const typeId = e("instance_type_select")?.value || "sensor";
    queueInstanceSuggestions(
      ev.target,
      { type: typeId, role: e("instance_role_input")?.value || "", id: `new_${typeId}` },
      e("instance_entity_pick")
    );
  });
  e("instance_entity_input")?.addEventListener("input", (ev) => {
    const typeId = e("instance_type_select")?.value || "sensor";
    queueInstanceSuggestions(
      ev.target,
      { type: typeId, role: e("instance_role_input")?.value || "", id: `new_${typeId}` },
      e("instance_entity_pick")
    );
  });
  e("dashboard_refresh_btn")?.addEventListener("click", () => {
    refreshDashboardSummary().catch((err) => setStatus(`Dashboard refresh failed: ${err.message}`, true));
  });

  e("profile_save_btn")?.addEventListener("click", saveProfile);
  e("profile_load_btn")?.addEventListener("click", loadSelectedProfile);
  e("profile_delete_btn")?.addEventListener("click", deleteSelectedProfile);
  e("profile_rename_btn")?.addEventListener("click", renameSelectedProfile);
  e("profile_validate_btn")?.addEventListener("click", validateProfile);

  e("generate_btn")?.addEventListener("click", generate);
  e("apply_preview_btn")?.addEventListener("click", previewApply);
  e("apply_commit_btn")?.addEventListener("click", commitApply);
  e("backups_refresh_btn")?.addEventListener("click", refreshBackups);
  e("backup_restore_btn")?.addEventListener("click", restoreBackup);

  e("update_refresh_btn")?.addEventListener("click", refreshLatestRelease);
  e("update_generate_package_btn")?.addEventListener("click", generateHaUpdatePackage);

  e("refresh_health_btn")?.addEventListener("click", refreshHealth);
  e("refresh_cache_btn")?.addEventListener("click", refreshDiscoveryCache);
  e("discovery_cancel_btn")?.addEventListener("click", cancelDiscoveryJob);
  e("fw_status_refresh_btn")?.addEventListener("click", () => {
    refreshFirmwareStatus().catch((err) => setStatus(`Firmware status error: ${err.message}`, true));
  });
  e("fw_workflow_auto_btn")?.addEventListener("click", () => {
    triggerFirmwareWorkflow("auto", true).catch((err) => {
      if (e("firmware_update_result")) e("firmware_update_result").textContent = `Update failed: ${err.message}`;
      setStatus(`Firmware update failed: ${err.message}`, true);
    });
  });
  e("fw_workflow_build_btn")?.addEventListener("click", () => {
    triggerFirmwareWorkflow("build_install", true).catch((err) => {
      if (e("firmware_update_result")) e("firmware_update_result").textContent = `Update failed: ${err.message}`;
      setStatus(`Firmware update failed: ${err.message}`, true);
    });
  });
  e("fw_workflow_install_btn")?.addEventListener("click", () => {
    triggerFirmwareWorkflow("install_only", false).catch((err) => {
      if (e("firmware_update_result")) e("firmware_update_result").textContent = `Update failed: ${err.message}`;
      setStatus(`Firmware update failed: ${err.message}`, true);
    });
  });
  e("fw_manual_steps_btn")?.addEventListener("click", () => {
    triggerFirmwareWorkflow("manual_fallback", false).catch((err) => {
      if (e("firmware_update_result")) e("firmware_update_result").textContent = `Manual flow failed: ${err.message}`;
      setStatus(`Manual flow failed: ${err.message}`, true);
    });
  });
  e("refresh_runtime_btn")?.addEventListener("click", () => {
    refreshRuntimeDiagnostics().catch((err) => setStatus(`Runtime diagnostics error: ${err.message}`, true));
  });
  e("retry_startup_btn")?.addEventListener("click", () => {
    bootstrap({ retry: true }).catch((err) => {
      const msg = formatStartupError("Retry startup", err);
      setStartupState("error", msg, true);
      setStatus(msg, true);
    });
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
  e("theme_reset_safe_btn")?.addEventListener("click", () => {
    resetThemeSafe().catch((err) => setStatus(`Theme reset failed: ${err.message}`, true));
  });

  e("layout_page_select")?.addEventListener("change", renderLayoutSections);
  e("layout_add_section_btn")?.addEventListener("click", addLayoutSection);
  e("layout_generate_defaults_btn")?.addEventListener("click", generateLayoutDefaultsFromFeatures);
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

function bindEventsOnce() {
  if (state.eventsBound) return;
  bindTabs();
  bindModeControls();
  bindExplorerEvents();
  bindProfileEvents();
  bindTopFieldEvents();
  state.eventsBound = true;
}

async function bootstrap(options = {}) {
  const retry = asBool(options.retry, false);
  if (state.startup.in_progress) return;
  state.startup.in_progress = true;
  state.bootErrors = [];
  setStartupState("booting", retry ? "Retrying startup..." : "", false);
  setStatus(retry ? "Retrying startup..." : "Initializing...");

  try {
    bindEventsOnce();

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

    const runStep = async (label, fn) => {
      try {
        await fn();
        return true;
      } catch (err) {
        const msg = formatStartupError(label, err);
        state.bootErrors.push(msg);
        setStatus(msg, true);
        return false;
      }
    };

    await runStep("Health", refreshHealth);
    await runStep("Dashboard", refreshDashboardSummary);
    await runStep("Firmware status", refreshFirmwareStatus);
    await runStep("Runtime diagnostics", refreshRuntimeDiagnostics);
    await runStep("Onboarding nodes", refreshOnboardingNodes);
    await runStep("Profile list", loadProfiles);
    await runStep("Template catalog", refreshTemplateCatalog);
    await runStep("Theme palettes", refreshThemePalettes);
    await runStep("Discovery start", () => startDiscoveryJob(false, { wait_for_completion: false }));
    await runStep("Slot caps", refreshSlotCaps);
    await runStep("Latest release", refreshLatestRelease);
    await runStep("Backup list", refreshBackups);

    if (state.bootErrors.length > 0) {
      const warningText = `${state.bootErrors.length} startup task(s) failed. Check status and transport diagnostics.`;
      setStartupState("ready", warningText, false);
      setStatus(`Admin Center ready with issues (${state.bootErrors.length}).`, true);
    } else {
      setStartupState("ready", "", false);
      setStatus("Admin Center ready");
    }
  } catch (err) {
    const msg = formatStartupError("Bootstrap", err);
    setStartupState("error", msg, true);
    setStatus(msg, true);
  } finally {
    state.startup.in_progress = false;
    const retryBtn = e("retry_startup_btn");
    if (retryBtn) retryBtn.disabled = false;
  }
}

bootstrap().catch((err) => {
  const msg = formatStartupError("Startup", err);
  setStartupState("error", msg, true);
  setStatus(msg, true);
});


