function v(id) {
  const el = document.getElementById(id);
  return el ? el.value.trim() : "";
}

function el(id) {
  return document.getElementById(id);
}

function payload() {
  return {
    git_ref: v("git_ref") || "main",
    git_url: v("git_url") || "https://github.com/jloops412/esphome-lilygo-tdeck-plus.git",
    substitutions: {
      name: v("name") || "lilygo-tdeck-plus",
      friendly_name: v("friendly_name") || "LilyGO T-Deck Plus",
      camera_slot_count: v("camera_slot_count") || "0",
      camera_slot_1_entity: v("camera_slot_1_entity") || "camera.replace_me_front_door",
      camera_slot_2_entity: v("camera_slot_2_entity") || "camera.replace_me_outdoor",
      light_slot_count: v("light_slot_count") || "6",
      ha_base_url: v("ha_base_url") || "http://homeassistant.local:8123",
      keyboard_alt_timeout_ms: v("keyboard_alt_timeout_ms") || "900",
    },
  };
}

async function postJson(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok || !data.ok) {
    throw new Error(data.error || `${res.status} ${res.statusText}`);
  }
  return data;
}

async function generate() {
  const body = payload();
  const [install, overrides] = await Promise.all([
    postJson("/api/generate/install", body),
    postJson("/api/generate/overrides", body),
  ]);
  el("install_out").value = install.yaml;
  el("overrides_out").value = overrides.yaml;
}

function domainOptions(domains) {
  const select = el("domain_filter");
  select.innerHTML = "";
  const all = document.createElement("option");
  all.value = "";
  all.textContent = "all";
  select.appendChild(all);
  for (const row of domains) {
    const opt = document.createElement("option");
    opt.value = row.domain;
    opt.textContent = `${row.domain} (${row.count})`;
    select.appendChild(opt);
  }
}

function renderEntities(rows) {
  const body = el("entities_body");
  body.innerHTML = "";
  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><code>${row.entity_id}</code></td>
      <td>${row.friendly_name || ""}</td>
      <td>${row.state || ""}</td>
      <td>${row.unit || ""}</td>
    `;
    body.appendChild(tr);
  }
}

async function refreshEntities() {
  const domain = encodeURIComponent(v("domain_filter"));
  const q = encodeURIComponent(v("search_filter"));
  el("status_line").textContent = "Loading entities...";
  const res = await fetch(`/api/discovery/entities?domain=${domain}&q=${q}`);
  const data = await res.json();
  if (!res.ok || !data.ok) {
    el("status_line").textContent = `Discovery error: ${data.error || "unknown error"}`;
    return;
  }
  renderEntities(data.entities || []);
  el("status_line").textContent = `Loaded ${data.count || 0} entities`;
}

async function loadDomains() {
  const res = await fetch("/api/discovery/domains");
  const data = await res.json();
  if (!res.ok || !data.ok) {
    el("status_line").textContent = `Domain load error: ${data.error || "unknown error"}`;
    return;
  }
  domainOptions(data.domains || []);
}

document.getElementById("generate_btn").addEventListener("click", async () => {
  try {
    await generate();
  } catch (err) {
    el("status_line").textContent = `Generate error: ${err.message}`;
  }
});

document.getElementById("refresh_entities_btn").addEventListener("click", async () => {
  await refreshEntities();
});

document.getElementById("domain_filter").addEventListener("change", async () => {
  await refreshEntities();
});

document.getElementById("search_filter").addEventListener("input", async () => {
  await refreshEntities();
});

(async () => {
  await loadDomains();
  await generate();
  await refreshEntities();
})();
