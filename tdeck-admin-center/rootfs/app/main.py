import os
from typing import Any, Dict, List

import requests
from flask import Flask, jsonify, request, send_from_directory


APP_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(APP_DIR, "static")

SUPERVISOR_URL = os.getenv("SUPERVISOR_URL", "http://supervisor")
SUPERVISOR_TOKEN = os.getenv("SUPERVISOR_TOKEN", "") or os.getenv("HASSIO_TOKEN", "")
ADDON_GITHUB_REF = os.getenv("ADDON_GITHUB_REF", "main")
ADDON_GITHUB_REPO_URL = os.getenv(
    "ADDON_GITHUB_REPO_URL", "https://github.com/jloops412/esphome-lilygo-tdeck-plus.git"
)

app = Flask(__name__, static_folder=STATIC_DIR)


def _ha_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if SUPERVISOR_TOKEN:
        headers["Authorization"] = f"Bearer {SUPERVISOR_TOKEN}"
    return headers


def _ha_get(path: str) -> Any:
    url = f"{SUPERVISOR_URL}/core/api{path}"
    resp = requests.get(url, headers=_ha_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()


def _as_str(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value)


def _q(value: Any) -> str:
    s = _as_str(value)
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return f"\"{s}\""


def _default_substitutions(payload: Dict[str, Any]) -> Dict[str, str]:
    substitutions = dict(payload.get("substitutions", {}))

    def _set_default(key: str, value: str) -> None:
        if key not in substitutions or substitutions[key] in ("", None):
            substitutions[key] = value

    _set_default("name", "lilygo-tdeck-plus")
    _set_default("friendly_name", "LilyGO T-Deck Plus")
    _set_default("entity_ha_unit_system", "sensor.unit_system")
    _set_default("camera_slot_count", "0")
    _set_default("camera_slot_1_name", "Front Door")
    _set_default("camera_slot_2_name", "Outdoor")
    _set_default("camera_slot_1_entity", "camera.replace_me_front_door")
    _set_default("camera_slot_2_entity", "camera.replace_me_outdoor")
    _set_default("camera_refresh_interval_s", "60")
    _set_default("camera_snapshot_enable", "true")
    _set_default("camera_snapshot_dir", "/config/www/tdeck")
    _set_default("ha_base_url", "http://homeassistant.local:8123")
    _set_default("light_slot_count", "6")
    _set_default("keyboard_alt_timeout_ms", "900")
    for i, name in enumerate(
        ["Foyer", "Vanity", "Bedroom", "Hall", "Office", "Upstairs", "Spare 7", "Spare 8"], start=1
    ):
        _set_default(f"light_slot_{i}_name", name)
        _set_default(f"light_slot_{i}_entity", f"light.replace_me_slot_{i}")
    return substitutions


def _build_install_yaml(payload: Dict[str, Any]) -> str:
    substitutions = _default_substitutions(payload)
    git_ref = _as_str(payload.get("git_ref"), ADDON_GITHUB_REF) or ADDON_GITHUB_REF
    git_url = _as_str(payload.get("git_url"), ADDON_GITHUB_REPO_URL) or ADDON_GITHUB_REPO_URL

    lines: List[str] = []
    lines.append("substitutions:")
    for key in sorted(substitutions.keys()):
        lines.append(f"  {key}: {_q(substitutions[key])}")

    lines.extend(
        [
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
            f"  - url: {git_url}",
            f"    ref: {_q(git_ref)}",
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
        ]
    )
    return "\n".join(lines)


def _build_overrides_yaml(payload: Dict[str, Any]) -> str:
    substitutions = _default_substitutions(payload)
    lines = ["substitutions:"]
    for key in sorted(substitutions.keys()):
        lines.append(f"  {key}: {_q(substitutions[key])}")
    return "\n".join(lines)


@app.get("/api/health")
def api_health() -> Any:
    try:
        info = _ha_get("/")
        return jsonify({"ok": True, "ha": info})
    except Exception as err:  # pragma: no cover
        return jsonify({"ok": False, "error": str(err)}), 500


@app.get("/api/discovery/entities")
def api_discovery_entities() -> Any:
    domain = _as_str(request.args.get("domain"), "").strip().lower()
    query = _as_str(request.args.get("q"), "").strip().lower()
    try:
        states = _ha_get("/states")
        entities: List[Dict[str, Any]] = []
        for item in states:
            entity_id = _as_str(item.get("entity_id"))
            if "." not in entity_id:
                continue
            item_domain = entity_id.split(".", 1)[0].lower()
            if domain and item_domain != domain:
                continue
            attrs = item.get("attributes", {}) or {}
            friendly = _as_str(attrs.get("friendly_name"), entity_id)
            if query:
                hay = f"{entity_id} {friendly}".lower()
                if query not in hay:
                    continue
            entities.append(
                {
                    "entity_id": entity_id,
                    "domain": item_domain,
                    "state": _as_str(item.get("state")),
                    "friendly_name": friendly,
                    "unit": _as_str(attrs.get("unit_of_measurement")),
                    "device_class": _as_str(attrs.get("device_class")),
                }
            )
        entities.sort(key=lambda e: e["entity_id"])
        return jsonify({"ok": True, "count": len(entities), "entities": entities})
    except Exception as err:  # pragma: no cover
        return jsonify({"ok": False, "error": str(err)}), 500


@app.get("/api/discovery/domains")
def api_discovery_domains() -> Any:
    try:
        states = _ha_get("/states")
        counts: Dict[str, int] = {}
        for item in states:
            entity_id = _as_str(item.get("entity_id"))
            if "." not in entity_id:
                continue
            domain = entity_id.split(".", 1)[0].lower()
            counts[domain] = counts.get(domain, 0) + 1
        rows = [{"domain": k, "count": counts[k]} for k in sorted(counts.keys())]
        return jsonify({"ok": True, "domains": rows})
    except Exception as err:  # pragma: no cover
        return jsonify({"ok": False, "error": str(err)}), 500


@app.post("/api/generate/install")
def api_generate_install() -> Any:
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify({"ok": True, "yaml": _build_install_yaml(payload)})
    except Exception as err:  # pragma: no cover
        return jsonify({"ok": False, "error": str(err)}), 400


@app.post("/api/generate/overrides")
def api_generate_overrides() -> Any:
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify({"ok": True, "yaml": _build_overrides_yaml(payload)})
    except Exception as err:  # pragma: no cover
        return jsonify({"ok": False, "error": str(err)}), 400


@app.get("/")
def root() -> Any:
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/<path:path>")
def static_proxy(path: str) -> Any:
    full_path = os.path.join(STATIC_DIR, path)
    if os.path.isfile(full_path):
        return send_from_directory(STATIC_DIR, path)
    return send_from_directory(STATIC_DIR, "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8099, debug=False)
