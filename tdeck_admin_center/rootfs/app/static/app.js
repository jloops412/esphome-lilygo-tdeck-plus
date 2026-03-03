
const state = {
  contracts: null,
  workspace: null,
  activeDeviceIndex: 0,
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

function e(id) {
  return document.getElementById(id);
}

function deepClone(v) {
  return JSON.parse(JSON.stringify(v));
}

function asBool(value) {
  if (typeof value === "boolean") return value;
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
  if (!out) return;
  out.textContent = text;
  out.style.color = isError ? "#ffb4c0" : "";
}

function setDiscoveryStatus(text, isError = false) {
  const out = e("discovery_status");
  if (!out) return;
  out.textContent = text;
  out.style.color = isError ? "#ffb4c0" : "";
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
      schema_version: "2.0",
      workspace_name: "default",
      active_device_index: 0,
      devices: [deepClone(fallbackProfile)],
      templates: {},
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

async function apiGet(path, signal = undefined) {
  const res = await fetch(path, { signal });
  let data = {};
  try {
    data = await res.json();
  } catch (_err) {
    data = {};
  }
  if (!res.ok || !data.ok) {
    throw new Error(data.error || `${res.status} ${res.statusText}`);
  }
  return data;
}

async function apiPost(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data = {};
  try {
    data = await res.json();
  } catch (_err) {
    data = {};
  }
  if (!res.ok || !data.ok) {
    throw new Error(data.error || `${res.status} ${res.statusText}`);
  }
  return data;
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
  const defaultVersion = state.contracts?.defaults?.app_release_version || "v0.20.6";
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

function buildCountSelect(id, min, max, value) {
  const select = e(id);
  select.innerHTML = "";
  for (let i = min; i <= max; i += 1) {
    const opt = document.createElement("option");
    opt.value = String(i);
    opt.textContent = String(i);
    if (String(i) === String(value)) opt.selected = true;
    select.appendChild(opt);
  }
}

function markActiveInput(input) {
  state.activeMappingInput = input;
}

function renderLightSlots() {
  const p = currentProfile();
  const host = e("light_slots_container");
  const count = Number(p.slots.light_slot_count || 1);
  host.innerHTML = "";
  for (let i = 0; i < 8; i += 1) {
    const slot = p.slots.lights[i] || { name: `Light ${i + 1}`, entity: "" };
    const hidden = i >= count ? "style='opacity:.45;'" : "";
    host.insertAdjacentHTML(
      "beforeend",
      `<div class="card" ${hidden}>
        <h4>Light Slot ${i + 1}</h4>
        <label>Name <input id="light_slot_name_${i}" value="${safeText(slot.name)}" /></label>
        <label>Entity <input id="light_slot_entity_${i}" value="${safeText(slot.entity)}" /></label>
      </div>`
    );
    e(`light_slot_name_${i}`).addEventListener("input", (ev) => {
      p.slots.lights[i].name = ev.target.value;
    });
    e(`light_slot_entity_${i}`).addEventListener("input", (ev) => {
      p.slots.lights[i].entity = ev.target.value;
    });
    e(`light_slot_entity_${i}`).addEventListener("focus", (ev) => markActiveInput(ev.target));
  }
}

function renderCameraSlots() {
  const p = currentProfile();
  const host = e("camera_slots_container");
  const count = Number(p.slots.camera_slot_count || 0);
  host.innerHTML = "";
  for (let i = 0; i < 2; i += 1) {
    const slot = p.slots.cameras[i] || { name: `Camera ${i + 1}`, entity: "" };
    const hidden = i >= count ? "style='opacity:.45;'" : "";
    host.insertAdjacentHTML(
      "beforeend",
      `<div class="card" ${hidden}>
        <h4>Camera Slot ${i + 1}</h4>
        <label>Name <input id="camera_slot_name_${i}" value="${safeText(slot.name)}" /></label>
        <label>Entity <input id="camera_slot_entity_${i}" value="${safeText(slot.entity)}" /></label>
      </div>`
    );
    e(`camera_slot_name_${i}`).addEventListener("input", (ev) => {
      p.slots.cameras[i].name = ev.target.value;
    });
    e(`camera_slot_entity_${i}`).addEventListener("input", (ev) => {
      p.slots.cameras[i].entity = ev.target.value;
    });
    e(`camera_slot_entity_${i}`).addEventListener("focus", (ev) => markActiveInput(ev.target));
  }
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

function syncProfileToForm() {
  const p = currentProfile();
  if (!p) return;
  applyProfileBasicsToForm();
  renderFeatureToggles();
  renderUiToggles();

  buildCountSelect("light_slot_count", 1, 8, p.slots.light_slot_count);
  buildCountSelect("camera_slot_count", 0, 2, p.slots.camera_slot_count);

  e("ha_base_url").value = p.settings.ha_base_url || "";
  e("camera_refresh_interval_s").value = p.settings.camera_refresh_interval_s || "60";
  e("camera_snapshot_dir").value = p.settings.camera_snapshot_dir || "/config/www/tdeck";
  e("camera_snapshot_enable").checked = asBool(p.settings.camera_snapshot_enable);

  renderLightSlots();
  renderCameraSlots();
  renderFieldGroup("weather_fields", WEATHER_FIELDS, "entities");
  renderFieldGroup("climate_fields", CLIMATE_FIELDS, "entities");
  renderFieldGroup("reader_fields", READER_FIELDS, "entities");
  renderFieldGroup("theme_fields", THEME_FIELDS, "theme");
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
  p.settings.app_release_version = e("app_release_version").value.trim() || (state.contracts?.defaults?.app_release_version || "v0.20.6");
  p.slots.light_slot_count = Number(e("light_slot_count").value || "6");
  p.slots.camera_slot_count = Number(e("camera_slot_count").value || "0");
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

  e("light_slot_count").addEventListener("change", () => {
    updateProfileFromTopFields();
    renderLightSlots();
  });
  e("camera_slot_count").addEventListener("change", () => {
    updateProfileFromTopFields();
    renderCameraSlots();
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
  const pct = Number(job.progress || 0);
  const rows = Number(job.rows || 0);
  const total = Number(job.total || 0);
  const duration = Number(job.duration_ms || 0);
  const err = job.error ? ` | error: ${job.error}` : "";
  return `Discovery ${status} | ${pct}% | rows ${rows}${total ? `/${total}` : ""} | ${duration}ms${err}`;
}

async function startDiscoveryJob(force = false, options = {}) {
  const waitForCompletion = asBool(options.wait_for_completion, false);
  const data = await apiPost("/api/discovery/jobs/start", { force });
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
      const data = await apiGet(`/api/discovery/jobs/${encodeURIComponent(jobId)}`);
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
  const data = await apiPost(`/api/discovery/jobs/${encodeURIComponent(jobId)}/cancel`, {});
  const job = data.job || null;
  if (job && ["cancelled", "completed", "failed"].includes(job.status || "")) {
    state.entities.jobId = "";
  }
  setDiscoveryStatus(formatJobText(job), (job?.status || "") === "failed");
  setStatus(`Discovery job ${job?.status || "updated"}`);
  await Promise.all([loadDomains(), refreshEntities({ resetPage: false }), refreshHealth()]);
}

async function refreshHealth() {
  const data = await apiGet("/api/health");
  const cache = data.cache || {};
  const haStatus = data.ha_connected ? "connected" : `error (${data.ha_error || "unreachable"})`;
  e("health_summary").textContent =
    `Addon version: ${data.addon_version || "--"}\n` +
    `Addon updated flag: ${data.addon_updated_since_last_run ? "yes" : "no"}\n` +
    `Firmware summary: ${data.firmware_status_summary || "--"}\n` +
    `HA: ${haStatus}\n` +
    `Entities cached: ${cache.entities || 0}\n` +
    `Domains: ${cache.domains || 0}\n` +
    `Cache age: ${cache.cache_age_ms || 0} ms\n` +
    `Last fetch duration: ${cache.last_duration_ms || 0} ms\n` +
    `Profiles: ${data.profiles?.count || 0} | Workspaces: ${data.workspaces?.count || 0}`;
  if (data.discovery_job) setDiscoveryStatus(formatJobText(data.discovery_job), data.discovery_job.status === "failed");
}

function firmwareStatusQuery() {
  const p = currentProfile();
  const slug = getDeviceSlug();
  const targetVersion = encodeURIComponent(p?.settings?.app_release_version || (state.contracts?.defaults?.app_release_version || "v0.20.6"));
  const nativeEntity = encodeURIComponent((p?.settings?.ha_native_firmware_entity || "").trim());
  const appVersionEntity = encodeURIComponent((p?.settings?.ha_app_version_entity || "").trim());
  return `/api/firmware/status?device_slug=${encodeURIComponent(slug)}&target_version=${targetVersion}&native_firmware_entity=${nativeEntity}&app_version_entity=${appVersionEntity}`;
}

async function refreshFirmwareStatus() {
  const data = await apiGet(firmwareStatusQuery());
  state.firmwareStatus = data;
  const lines = [
    `Status: ${data.status_text || "--"}`,
    `Target: ${data.target_version || "--"}`,
    `Installed: ${data.installed_version || "--"}`,
    `Native Entity: ${data.native_firmware_entity || "--"} (${data.native_state || "--"})`,
    `Version Entity: ${data.app_version_entity || "--"}`,
    `Addon Updated Flag: ${data.runtime?.addon_updated_since_last_run ? "yes" : "no"}`,
  ];
  if (Array.isArray(data.issues) && data.issues.length > 0) {
    lines.push(`Issues: ${data.issues.join(" | ")}`);
  }
  e("firmware_status_summary").textContent = lines.join("\n");

  const banner = e("firmware_pending_banner");
  if (data.firmware_pending) {
    banner.textContent = "Add-on updated and firmware is pending. Update firmware to align with the current app release.";
    banner.style.color = "#ffd38a";
  } else {
    banner.textContent = "Firmware is up to date with the selected app release target.";
    banner.style.color = "";
  }

  const withBackup = e("fw_update_backup_btn");
  const noBackup = e("fw_update_no_backup_btn");
  const canAttempt = !!data.native_firmware_entity;
  withBackup.disabled = !canAttempt;
  noBackup.disabled = !canAttempt;
}

async function triggerFirmwareUpdate(backupFirst = true) {
  const promptText = backupFirst
    ? "Run managed backup and trigger firmware update?"
    : "Trigger firmware update without backup?";
  if (!window.confirm(promptText)) return;
  const body = profilePayload();
  body.device_slug = getDeviceSlug();
  body.backup_first = !!backupFirst;
  body.native_firmware_entity = e("ha_native_firmware_entity")?.value?.trim() || "";
  body.app_version_entity = e("ha_installed_version_entity")?.value?.trim() || "";
  body.target_version = e("app_release_version")?.value?.trim() || (state.contracts?.defaults?.app_release_version || "v0.20.6");

  const data = await apiPost("/api/firmware/update", body);
  const resultLines = [
    `Action: ${data.action || "update.install"}`,
    `Device: ${data.device_slug || "--"}`,
    `Entity: ${data.native_firmware_entity || "--"}`,
    `Backup: ${data.backup?.id || "none"}`,
  ];
  e("firmware_update_result").textContent = resultLines.join("\n");
  setStatus(`Firmware update requested for ${data.device_slug}${data.backup?.id ? ` (backup ${data.backup.id})` : ""}`);
  await Promise.all([refreshFirmwareStatus(), refreshBackups()]);
}

async function loadDomains() {
  const jobParam = state.entities.jobId ? `?job_id=${encodeURIComponent(state.entities.jobId)}` : "";
  const data = await apiGet(`/api/discovery/domains${jobParam}`);
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
      `/api/discovery/entities?job_id=${jobId}&domain=${domain}&q=${q}&page=${state.entities.page}&page_size=${pageSize}&sort=${sort}&only_mappable=${onlyMappable}`,
      state.entities.controller.signal
    );
    state.entities.pages = data.pages || 1;
    state.entities.total = data.total || 0;
    renderEntities(data.entities || []);
    e("page_label").textContent = `Page ${data.page || 1} / ${data.pages || 1}`;
    const job = data.job || null;
    e("explorer_meta").textContent = `Loaded ${data.count || 0} of ${data.total || 0} | cache ${data.cache_age_ms || 0}ms${data.stale ? " | STALE" : ""}${job ? ` | job ${job.status}` : ""}`;
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
  const [install, overrides] = await Promise.all([apiPost("/api/generate/install", body), apiPost("/api/generate/overrides", body)]);
  e("install_out").value = install.yaml || "";
  e("overrides_out").value = overrides.yaml || "";
  const validation = install.validation || overrides.validation || {};
  const errCount = (validation.errors || []).length;
  const warnCount = (validation.warnings || []).length;
  setStatus(`Generated YAML (${errCount} errors, ${warnCount} warnings)`, errCount > 0);
}

async function previewApply() {
  const data = await apiPost("/api/apply/preview", profilePayload());
  const preview = data.preview || {};
  e("apply_preview_install_diff").value = preview.install?.diff || "No install changes";
  e("apply_preview_overrides_diff").value = preview.overrides?.diff || "No overrides changes";
  const validation = data.validation || {};
  const errCount = (validation.errors || []).length;
  const warnCount = (validation.warnings || []).length;
  setStatus(`Apply preview ready for ${preview.device_slug || "device"} (${errCount} errors, ${warnCount} warnings)`, errCount > 0);
}

async function commitApply() {
  if (!window.confirm("Apply generated config to managed files with automatic backup?")) return;
  const data = await apiPost("/api/apply/commit", profilePayload());
  setStatus(`Applied to ${data.device_slug}. Backup ${data.backup?.id || "created"}`);
  await refreshBackups();
}

async function refreshBackups() {
  const slug = getDeviceSlug();
  const data = await apiGet(`/api/backups/list?device_slug=${encodeURIComponent(slug)}`);
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
  const data = await apiPost("/api/backups/restore", { device_slug: slug, backup_id: backupId });
  setStatus(`Restored backup ${data.restored?.backup_id || backupId} for ${slug}`);
}
async function refreshLatestRelease() {
  const channel = e("update_channel").value || "stable";
  const data = await apiGet(`/api/update/latest?channel=${encodeURIComponent(channel)}`);
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
  const data = await apiPost("/api/generate/ha_update_package", body);
  e("ha_update_package_out").value = data.yaml || "";
  setStatus(`Generated HA update package (latest stable: ${data.latest?.version || "unknown"})`);
}

async function loadProfiles() {
  const data = await apiGet("/api/profile/list");
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
  const data = await apiPost("/api/profile/save", payload);
  await loadProfiles();
  setStatus(`Saved workspace ${data.workspace_name || data.profile_name}`);
}

async function loadSelectedProfile() {
  const selected = e("profile_list").value;
  if (!selected) return;
  const data = await apiGet(`/api/profile/load?name=${encodeURIComponent(selected)}`);
  state.workspace = ensureWorkspace(data.workspace || data.profile, state.contracts.defaults || {});
  state.activeDeviceIndex = Number(data.active_device_index || state.workspace.active_device_index || 0);
  syncProfileToForm();
  setStatus(`Loaded workspace ${selected}`);
}

async function deleteSelectedProfile() {
  const selected = e("profile_list").value;
  if (!selected) return;
  if (!window.confirm(`Delete workspace/profile '${selected}'?`)) return;
  await apiPost("/api/profile/delete", { name: selected });
  await loadProfiles();
  setStatus(`Deleted ${selected}`);
}

async function renameSelectedProfile() {
  const selected = e("profile_list").value;
  const target = e("profile_rename_to").value.trim();
  if (!selected || !target) return;
  const data = await apiPost("/api/profile/rename", { old_name: selected, new_name: target });
  await loadProfiles();
  e("workspace_name").value = data.workspace_name || data.profile_name;
  state.workspace.workspace_name = data.workspace_name || data.profile_name;
  setStatus(`Renamed to ${data.workspace_name || data.profile_name}`);
}

async function validateProfile() {
  const data = await apiPost("/api/profile/validate", profilePayload());
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
}

function bindProfileEvents() {
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
  e("fw_update_backup_btn").addEventListener("click", () => {
    triggerFirmwareUpdate(true).catch((err) => {
      e("firmware_update_result").textContent = `Update failed: ${err.message}`;
      setStatus(`Firmware update failed: ${err.message}`, true);
    });
  });
  e("fw_update_no_backup_btn").addEventListener("click", () => {
    triggerFirmwareUpdate(false).catch((err) => {
      e("firmware_update_result").textContent = `Update failed: ${err.message}`;
      setStatus(`Firmware update failed: ${err.message}`, true);
    });
  });
}

async function bootstrap() {
  bindTabs();
  bindExplorerEvents();
  bindProfileEvents();

  const meta = await apiGet("/api/meta/contracts");
  state.contracts = meta.contracts || {};
  state.workspace = ensureWorkspace(meta.default_workspace || meta.default_profile, meta.default_profile || {});
  state.activeDeviceIndex = Number(state.workspace.active_device_index || 0);
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
  await runStep("Firmware status", refreshFirmwareStatus);
  await runStep("Profile list", loadProfiles);
  await runStep("Discovery start", () => startDiscoveryJob(false, { wait_for_completion: false }));
  await runStep("Latest release", refreshLatestRelease);
  await runStep("YAML generation", generate);
  await runStep("Apply preview", previewApply);
  await runStep("Backup list", refreshBackups);
  await runStep("HA update package generation", generateHaUpdatePackage);

  if (state.bootErrors.length > 0) {
    setStatus(`Admin Center ready with issues (${state.bootErrors.length}). Check status/details.`, true);
  } else {
    setStatus("Admin Center ready");
  }
}

bootstrap().catch((err) => setStatus(`Startup error: ${err.message}`, true));
