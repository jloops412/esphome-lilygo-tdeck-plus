function value(id) {
  const el = document.getElementById(id);
  return el ? el.value.trim() : "";
}

function toInt(v, fallback) {
  const n = parseInt(v, 10);
  return Number.isNaN(n) ? fallback : n;
}

function buildOverrides() {
  const unitsMetric = value("units_mode") === "metric";
  return [
    "substitutions:",
    `  light_slot_count: "${value("light_slot_count") || "6"}"`,
    `  light_slot_1_name: "${value("light_slot_1_name") || "Foyer"}"`,
    `  light_slot_1_entity: "${value("light_slot_1_entity") || "light.replace_me_slot_1"}"`,
    `  light_slot_2_name: "${value("light_slot_2_name") || "Vanity"}"`,
    `  light_slot_2_entity: "${value("light_slot_2_entity") || "light.replace_me_slot_2"}"`,
    `  camera_slot_count: "${value("camera_slot_count") || "0"}"`,
    `  camera_slot_1_name: "${value("camera_slot_1_name") || "Front Door"}"`,
    `  camera_slot_1_entity: "${value("camera_slot_1_entity") || "camera.replace_me_front_door"}"`,
    `  camera_slot_2_name: "${value("camera_slot_2_name") || "Outdoor"}"`,
    `  camera_slot_2_entity: "${value("camera_slot_2_entity") || "camera.replace_me_outdoor"}"`,
    `  camera_refresh_interval_s: "${value("camera_refresh_interval_s") || "60"}"`,
    `  ha_base_url: "${value("ha_base_url") || "http://homeassistant.local:8123"}"`,
    `  app_units_mode: "${unitsMetric ? "1" : "0"}"`,
  ].join("\n");
}

function buildInstallYaml() {
  const name = value("name") || "lilygo-tdeck-plus";
  const friendly = value("friendly_name") || "LilyGO T-Deck Plus";
  const ref = value("git_ref") || "main";
  const unitSensor = "sensor.unit_system";
  const cameraCount = toInt(value("camera_slot_count"), 0);

  return [
    "substitutions:",
    `  name: ${name}`,
    `  friendly_name: "${friendly}"`,
    `  entity_ha_unit_system: "${unitSensor}"`,
    `  camera_slot_count: "${cameraCount}"`,
    `  camera_slot_1_name: "${value("camera_slot_1_name") || "Front Door"}"`,
    `  camera_slot_1_entity: "${value("camera_slot_1_entity") || "camera.replace_me_front_door"}"`,
    `  camera_slot_2_name: "${value("camera_slot_2_name") || "Outdoor"}"`,
    `  camera_slot_2_entity: "${value("camera_slot_2_entity") || "camera.replace_me_outdoor"}"`,
    `  camera_refresh_interval_s: "${value("camera_refresh_interval_s") || "60"}"`,
    `  ha_base_url: "${value("ha_base_url") || "http://homeassistant.local:8123"}"`,
    "",
    "esphome:",
    "  name: ${name}",
    "  friendly_name: ${friendly_name}",
    "",
    "esp32:",
    "  variant: esp32s3",
    "  framework:",
    "    type: esp-idf",
    "",
    "packages:",
    "  - url: https://github.com/jloops412/esphome-lilygo-tdeck-plus.git",
    `    ref: "${ref}"`,
    "    refresh: 1min",
    "    files:",
    "      - esphome/packages/board_base.yaml",
    "      - esphome/packages/persistence_globals.yaml",
    "      - esphome/packages/ha_entities.yaml",
    "      - esphome/packages/gps_uart.yaml",
    "      - esphome/packages/ui_lvgl.yaml",
    "      - esphome/packages/display_mipi_lvgl.yaml",
    "      - esphome/packages/input_touch_gt911_lvgl.yaml",
    "      - esphome/packages/input_trackball_lvgl.yaml",
    "      - esphome/packages/input_keyboard_i2c_lvgl.yaml",
    "",
    "wifi:",
    "  ssid: !secret wifi_ssid",
    "  password: !secret wifi_password",
    "  ap:",
    "    ssid: \"${friendly_name} Fallback\"",
    "    password: \"esphome1234\"",
  ].join("\n");
}

function generate() {
  document.getElementById("install_out").value = buildInstallYaml();
  document.getElementById("overrides_out").value = buildOverrides();
}

document.getElementById("generate_btn").addEventListener("click", generate);
generate();

