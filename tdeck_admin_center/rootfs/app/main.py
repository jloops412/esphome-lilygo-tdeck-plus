import json
import os
import re
import shutil
import threading
import time
import hashlib
import difflib
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import quote, urlparse

import requests
from flask import Flask, jsonify, make_response, request, send_from_directory


APP_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(APP_DIR, "static")

SUPERVISOR_URL = os.getenv("SUPERVISOR_URL", "http://supervisor")
SUPERVISOR_TOKEN = os.getenv("SUPERVISOR_TOKEN", "") or os.getenv("HASSIO_TOKEN", "")
DEFAULT_RELEASE_CHANNEL = "stable"
ADDON_GITHUB_REF = os.getenv("ADDON_GITHUB_REF", DEFAULT_RELEASE_CHANNEL) or DEFAULT_RELEASE_CHANNEL
ADDON_GITHUB_REPO_URL = (
    os.getenv("ADDON_GITHUB_REPO_URL", "https://github.com/jloops412/esphome-lilygo-tdeck-plus.git")
    or "https://github.com/jloops412/esphome-lilygo-tdeck-plus.git"
)
ADDON_VERSION = os.getenv("ADDON_VERSION", os.getenv("BUILD_VERSION", "0.23.1")) or "0.23.1"
DEFAULT_APP_RELEASE_VERSION = os.getenv("APP_RELEASE_VERSION", "v0.23.1") or "v0.23.1"

CACHE_TTL_SECONDS = 15
RELEASE_CACHE_TTL_SECONDS = 900
SERVICE_CACHE_TTL_SECONDS = 20
DISCOVERY_JOB_POLL_TTL_SECONDS = 180
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500
PROFILE_SCHEMA_VERSION = "4.0"
WORKSPACE_SCHEMA_VERSION = "4.0"
ENTITY_COLLECTION_LIMITS = {
    "lights": {"default_max": 24, "hard_max": 64},
    "cameras": {"default_max": 8, "hard_max": 24},
    "weather_metrics": {"default_max": 32, "hard_max": 64},
    "climate_controls": {"default_max": 24, "hard_max": 64},
    "reader_feeds": {"default_max": 16, "hard_max": 32},
    "system_entities": {"default_max": 24, "hard_max": 64},
}
LAYOUT_GRID_DEFAULTS = {"cols": 4, "rows": 6}
DEFAULT_LAYOUT_PAGE_IDS = ["home", "lights", "weather", "climate", "reader", "cameras", "settings", "theme"]

MAPPABLE_DOMAINS = {
    "light",
    "weather",
    "climate",
    "camera",
    "sensor",
    "binary_sensor",
    "switch",
    "number",
    "event",
    "text",
    "select",
    "button",
}

DOMAIN_HINTS: Dict[str, List[str]] = {
    "entity_wx_main": ["weather"],
    "entity_sensi_climate": ["climate"],
    "camera_slot_1_entity": ["camera"],
    "camera_slot_2_entity": ["camera"],
    "entity_feed_bbc": ["event", "sensor"],
    "entity_feed_dc": ["event", "sensor"],
    "entity_feed_loudoun": ["event", "sensor"],
}

DATA_ROOT = Path(os.getenv("ADDON_DATA_DIR", "/data"))
PROFILE_DIR = DATA_ROOT / "profiles"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)
WORKSPACE_DIR = DATA_ROOT / "workspaces"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, static_folder=STATIC_DIR)


def _enforce_frontend_api_path_guard() -> None:
    app_js = Path(STATIC_DIR) / "app.js"
    if not app_js.exists():
        return
    text = app_js.read_text(encoding="utf-8", errors="ignore")
    # Guard: frontend must not call absolute /api paths because HA ingress prefixes URLs.
    if re.search(r"fetch\(\s*['\"]\/api\/", text):
        raise RuntimeError("frontend guard failed: absolute '/api/' fetch usage detected in static/app.js")


_enforce_frontend_api_path_guard()

_DISCOVERY_LOCK = threading.Lock()
_DISCOVERY_CACHE: Dict[str, Any] = {
    "fetched_at": 0.0,
    "rows": [],
    "domains": [],
    "last_error": "",
    "last_duration_ms": 0,
    "last_total": 0,
}
_DISCOVERY_JOBS: Dict[str, Dict[str, Any]] = {}
_DISCOVERY_JOB_SEQ = 0
_DISCOVERY_ACTIVE_JOB_ID = ""
_RELEASE_LOCK = threading.Lock()
_RELEASE_CACHE: Dict[str, Any] = {
    "fetched_at": 0.0,
    "channels": {},
    "last_error": "",
}
_SERVICE_LOCK = threading.Lock()
_SERVICE_CACHE: Dict[str, Any] = {
    "fetched_at": 0.0,
    "services": {},
    "last_error": "",
}
_APPLY_LOCKS: Dict[str, threading.Lock] = {}
_RUNTIME_STATE_LOCK = threading.Lock()


def _load_addon_options() -> Dict[str, Any]:
    path = DATA_ROOT / "options.json"
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {}


_ADDON_OPTIONS = _load_addon_options()
_managed_root_raw = _ADDON_OPTIONS.get("managed_root", "/config/esphome/tdeck")
if _managed_root_raw is None:
    _managed_root_raw = "/config/esphome/tdeck"
MANAGED_ROOT = Path(str(_managed_root_raw)).resolve()
try:
    _backup_keep_raw = int(float(str(_ADDON_OPTIONS.get("backup_keep_count", 30))))
except Exception:
    _backup_keep_raw = 30
if _backup_keep_raw < 5:
    _backup_keep_raw = 5
if _backup_keep_raw > 500:
    _backup_keep_raw = 500
BACKUP_KEEP_COUNT = _backup_keep_raw


def _runtime_state_defaults() -> Dict[str, Any]:
    return {
        "last_seen_addon_version": "",
        "addon_updated_since_last_run": False,
        "last_prompted_device_slug": "",
        "last_firmware_action": {},
    }


RUNTIME_STATE_PATH = DATA_ROOT / "runtime_state.json"


def _load_runtime_state() -> Dict[str, Any]:
    state = _runtime_state_defaults()
    try:
        if RUNTIME_STATE_PATH.exists():
            incoming = json.loads(RUNTIME_STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(incoming, dict):
                state.update(incoming)
    except Exception:
        pass
    state["last_seen_addon_version"] = str(state.get("last_seen_addon_version") or "")
    _updated_raw = state.get("addon_updated_since_last_run", False)
    if isinstance(_updated_raw, bool):
        state["addon_updated_since_last_run"] = _updated_raw
    else:
        state["addon_updated_since_last_run"] = str(_updated_raw).strip().lower() in {"1", "true", "yes", "on"}
    state["last_prompted_device_slug"] = str(state.get("last_prompted_device_slug") or "")
    if not isinstance(state.get("last_firmware_action"), dict):
        state["last_firmware_action"] = {}
    return state


def _save_runtime_state(state: Dict[str, Any]) -> None:
    payload = _runtime_state_defaults()
    payload.update(state)
    tmp = RUNTIME_STATE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(RUNTIME_STATE_PATH)


_RUNTIME_STATE = _load_runtime_state()


def _init_runtime_state() -> None:
    with _RUNTIME_STATE_LOCK:
        previous = str(_RUNTIME_STATE.get("last_seen_addon_version") or "")
        changed = bool(previous and previous != ADDON_VERSION)
        if previous != ADDON_VERSION:
            _RUNTIME_STATE["last_seen_addon_version"] = ADDON_VERSION
        if changed:
            _RUNTIME_STATE["addon_updated_since_last_run"] = True
        elif "addon_updated_since_last_run" not in _RUNTIME_STATE:
            _RUNTIME_STATE["addon_updated_since_last_run"] = False
        _save_runtime_state(_RUNTIME_STATE)


_init_runtime_state()


def _now() -> float:
    return time.time()


def _ha_headers() -> Dict[str, str]:
    headers = {"Accept": "application/json"}
    if SUPERVISOR_TOKEN:
        headers["Authorization"] = f"Bearer {SUPERVISOR_TOKEN}"
    return headers


def _ha_get(path: str, timeout: int = 15) -> Any:
    url = f"{SUPERVISOR_URL}/core/api{path}"
    resp = requests.get(url, headers=_ha_headers(), timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _ha_post(path: str, payload: Dict[str, Any], timeout: int = 20) -> Any:
    url = f"{SUPERVISOR_URL}/core/api{path}"
    resp = requests.post(url, headers=_ha_headers(), json=payload, timeout=timeout)
    resp.raise_for_status()
    if not resp.text:
        return {}
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


def _service_cache_age_ms() -> int:
    fetched_at = float(_SERVICE_CACHE.get("fetched_at", 0.0) or 0.0)
    if fetched_at <= 0:
        return 0
    age = int((_now() - fetched_at) * 1000.0)
    return age if age >= 0 else 0


def _load_services_catalog(force: bool = False) -> Dict[str, Any]:
    with _SERVICE_LOCK:
        age_ms = _service_cache_age_ms()
        if not force and _SERVICE_CACHE.get("services") and age_ms < SERVICE_CACHE_TTL_SECONDS * 1000:
            return {
                "services": dict(_SERVICE_CACHE.get("services", {})),
                "cache_age_ms": age_ms,
                "stale": False,
                "last_error": _as_str(_SERVICE_CACHE.get("last_error"), ""),
            }
    try:
        raw = _ha_get("/services", timeout=20)
        services: Dict[str, Any] = {}
        if isinstance(raw, list):
            for domain_entry in raw:
                domain = _as_str(domain_entry.get("domain")).strip().lower()
                svc_map = domain_entry.get("services", {}) if isinstance(domain_entry.get("services"), dict) else {}
                for service_name in svc_map.keys():
                    full = f"{domain}.{_as_str(service_name).strip().lower()}"
                    if domain and "." in full:
                        services[full] = True
        with _SERVICE_LOCK:
            _SERVICE_CACHE["services"] = services
            _SERVICE_CACHE["fetched_at"] = _now()
            _SERVICE_CACHE["last_error"] = ""
        return {"services": services, "cache_age_ms": 0, "stale": False, "last_error": ""}
    except Exception as err:
        with _SERVICE_LOCK:
            _SERVICE_CACHE["last_error"] = str(err)
            cached = dict(_SERVICE_CACHE.get("services", {}))
        return {
            "services": cached,
            "cache_age_ms": _service_cache_age_ms(),
            "stale": True,
            "last_error": str(err),
        }


def _normalize_service_ref(value: Any) -> str:
    raw = _as_str(value).strip().lower()
    if not raw or "." not in raw:
        return ""
    domain, service = raw.split(".", 1)
    domain = domain.strip()
    service = service.strip()
    if not domain or not service:
        return ""
    return f"{domain}.{service}"


def _ha_call_service_ref(service_ref: str, payload: Dict[str, Any], timeout: int = 25) -> Any:
    normalized = _normalize_service_ref(service_ref)
    if not normalized:
        raise RuntimeError(f"invalid_service_ref:{service_ref}")
    domain, service = normalized.split(".", 1)
    return _ha_post(f"/services/{domain}/{service}", payload, timeout=timeout)


def _as_str(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value)


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    s = _as_str(value).strip().lower()
    if s in {"1", "true", "yes", "on"}:
        return True
    if s in {"0", "false", "no", "off"}:
        return False
    return default


def _as_int(value: Any, default: int, min_value: int | None = None, max_value: int | None = None) -> int:
    try:
        out = int(float(_as_str(value, str(default))))
    except Exception:
        out = default
    if min_value is not None and out < min_value:
        out = min_value
    if max_value is not None and out > max_value:
        out = max_value
    return out


def _bool_str(value: Any) -> str:
    return "true" if _as_bool(value, False) else "false"


def _safe_profile_name(value: Any, fallback: str = "default") -> str:
    raw = _as_str(value, fallback).strip()
    if not raw:
        raw = fallback
    cleaned = re.sub(r"[^A-Za-z0-9_.-]", "_", raw)
    return cleaned[:80] if cleaned else fallback


def _is_placeholder(value: Any) -> bool:
    s = _as_str(value).strip()
    if not s:
        return True
    low = s.lower()
    return "replace_me" in low or low in {"none", "null", "unknown"}


def _normalize_color(value: Any, default_hex: str) -> str:
    raw = _as_str(value).strip()
    if not raw:
        return default_hex
    try:
        if raw.startswith("#"):
            v = int(raw[1:], 16)
        elif raw.lower().startswith("0x"):
            v = int(raw[2:], 16)
        else:
            v = int(raw)
        if v < 0:
            v = 0
        if v > 0xFFFFFF:
            v = 0xFFFFFF
        return f"0x{v:06X}"
    except Exception:
        return default_hex


def _slugify(value: Any, fallback: str = "tdeck") -> str:
    raw = _as_str(value, fallback).strip().lower()
    if not raw:
        raw = fallback
    raw = raw.replace("-", "_")
    raw = re.sub(r"[^a-z0-9_]", "_", raw)
    raw = re.sub(r"_+", "_", raw).strip("_")
    return raw or fallback


def _repo_slug_from_url(repo_url: str) -> str:
    raw = _as_str(repo_url).strip()
    if not raw:
        return "jloops412/esphome-lilygo-tdeck-plus"
    raw = raw.removesuffix(".git")
    if raw.startswith("git@github.com:"):
        return raw.split("git@github.com:", 1)[1]
    parsed = urlparse(raw)
    if parsed.netloc.lower() == "github.com":
        path = parsed.path.strip("/")
        if "/" in path:
            return path
    if raw.count("/") >= 1 and "github.com" not in raw:
        # fallback for already slug-like values
        return raw.strip("/")
    return "jloops412/esphome-lilygo-tdeck-plus"


def _normalize_version_text(value: Any) -> str:
    v = _as_str(value).strip().lower()
    if not v:
        return ""
    if v.startswith("v"):
        v = v[1:]
    return v


def _state_is_unknown(value: Any) -> bool:
    return _as_str(value).strip().lower() in {"", "unknown", "unavailable", "none", "null"}


def _ha_get_state_safe(entity_id: str) -> Dict[str, Any]:
    try:
        data = _ha_get(f"/states/{quote(entity_id, safe='')}", timeout=12)
        return {
            "ok": True,
            "entity_id": entity_id,
            "state": _as_str(data.get("state"), ""),
            "attributes": data.get("attributes", {}) or {},
            "raw": data,
            "error": "",
        }
    except Exception as err:
        return {
            "ok": False,
            "entity_id": entity_id,
            "state": "",
            "attributes": {},
            "raw": {},
            "error": str(err),
        }


def _resolve_firmware_entities(device_slug: str, settings: Dict[str, Any] | None = None) -> Tuple[str, str]:
    safe_slug = _slugify(device_slug, "tdeck")
    settings = settings if isinstance(settings, dict) else {}
    native = _as_str(settings.get("ha_native_firmware_entity"), "").strip() or f"update.{safe_slug}_firmware"
    app_ver = _as_str(settings.get("ha_app_version_entity"), "").strip() or f"sensor.{safe_slug}_app_version"
    return native, app_ver


def _runtime_firmware_summary() -> str:
    with _RUNTIME_STATE_LOCK:
        pending = _as_bool(_RUNTIME_STATE.get("addon_updated_since_last_run"), False)
        slug = _as_str(_RUNTIME_STATE.get("last_prompted_device_slug"), "")
    if pending and slug:
        return f"pending:{slug}"
    if pending:
        return "pending:unresolved"
    return "up_to_date_or_not_checked"


def _runtime_state_snapshot() -> Dict[str, Any]:
    with _RUNTIME_STATE_LOCK:
        return {
            "last_seen_addon_version": _as_str(_RUNTIME_STATE.get("last_seen_addon_version"), ""),
            "addon_updated_since_last_run": _as_bool(_RUNTIME_STATE.get("addon_updated_since_last_run"), False),
            "last_prompted_device_slug": _as_str(_RUNTIME_STATE.get("last_prompted_device_slug"), ""),
            "last_firmware_action": _RUNTIME_STATE.get("last_firmware_action", {}),
        }


def _release_cache_age_ms() -> int:
    fetched_at = float(_RELEASE_CACHE.get("fetched_at", 0.0) or 0.0)
    if fetched_at <= 0:
        return 0
    age = int((_now() - fetched_at) * 1000.0)
    return age if age >= 0 else 0


def _github_latest_release(channel: str = DEFAULT_RELEASE_CHANNEL, force: bool = False) -> Dict[str, Any]:
    channel_key = _slugify(channel, DEFAULT_RELEASE_CHANNEL)
    with _RELEASE_LOCK:
        age_ms = _release_cache_age_ms()
        cached_channels = _RELEASE_CACHE.get("channels", {}) or {}
        cached = cached_channels.get(channel_key)
        if not force and cached and age_ms < RELEASE_CACHE_TTL_SECONDS * 1000:
            out = dict(cached)
            out["cache_age_ms"] = age_ms
            out["stale"] = False
            out["last_error"] = _RELEASE_CACHE.get("last_error", "")
            return out

        slug = _repo_slug_from_url(ADDON_GITHUB_REPO_URL)
        url = f"https://api.github.com/repos/{slug}/releases/latest"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "tdeck-admin-center",
        }
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json() or {}
            release = {
                "channel": channel_key,
                "version": _as_str(data.get("tag_name"), DEFAULT_APP_RELEASE_VERSION),
                "published_at": _as_str(data.get("published_at")),
                "html_url": _as_str(data.get("html_url"), f"https://github.com/{slug}/releases/latest"),
                "notes": _as_str(data.get("body")),
                "repo_slug": slug,
            }
            cached_channels[channel_key] = release
            _RELEASE_CACHE["channels"] = cached_channels
            _RELEASE_CACHE["fetched_at"] = _now()
            _RELEASE_CACHE["last_error"] = ""
            out = dict(release)
            out["cache_age_ms"] = 0
            out["stale"] = False
            out["last_error"] = ""
            return out
        except Exception as err:
            _RELEASE_CACHE["last_error"] = str(err)
            if cached:
                out = dict(cached)
                out["cache_age_ms"] = _release_cache_age_ms()
                out["stale"] = True
                out["last_error"] = str(err)
                return out
            raise


def _q(value: Any) -> str:
    s = _as_str(value)
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return f"\"{s}\""


def _q_single(value: Any) -> str:
    s = _as_str(value)
    s = s.replace("\\", "\\\\").replace("'", "''")
    return f"'{s}'"


def _default_substitutions() -> Dict[str, str]:
    return {
        "name": "lilygo-tdeck-plus",
        "friendly_name": "LilyGO T-Deck Plus",
        "app_release_channel": DEFAULT_RELEASE_CHANNEL,
        "app_release_version": DEFAULT_APP_RELEASE_VERSION,
        "gps_rx_pin": "44",
        "gps_tx_pin": "43",
        "gps_baud_rate": "9600",
        "touch_x_min": "0",
        "touch_x_max": "238",
        "touch_y_min": "16",
        "touch_y_max": "260",
        "climate_temp_min_f": "50",
        "climate_temp_max_f": "90",
        "climate_auto_band_min_delta_f": "2",
        "climate_hold_repeat_ms": "180",
        "climate_ack_timeout_ms": "12000",
        "climate_resync_guard_ms": "8000",
        "climate_tolerance_f": "1",
        "climate_tolerance_c_tenths": "5",
        "keyboard_alt_timeout_ms": "900",
        "screensaver_keyboard_repeat_suppress_ms": "1200",
        "screensaver_keyboard_activity_min_interval_ms": "250",
        "home_dynamic_weather_icon": "true",
        "camera_slot_count": "0",
        "camera_slot_1_name": "Front Door",
        "camera_slot_2_name": "Outdoor",
        "camera_slot_1_entity": "camera.replace_me_front_door",
        "camera_slot_2_entity": "camera.replace_me_outdoor",
        "camera_refresh_interval_s": "60",
        "camera_snapshot_enable": "true",
        "camera_snapshot_dir": "/config/www/tdeck",
        "ha_base_url": "http://homeassistant.local:8123",
        "light_name_foyer": "Foyer",
        "light_name_vanity": "Vanity",
        "light_name_bedroom": "Bedroom",
        "light_name_hall": "Hall",
        "light_name_office": "Office",
        "light_name_upstairs": "Upstairs",
        "entity_light_foyer": "light.replace_me_foyer",
        "entity_light_vanity": "light.replace_me_vanity",
        "entity_light_bedroom": "light.replace_me_bedroom",
        "entity_light_hall": "light.replace_me_hall",
        "entity_light_office": "light.replace_me_office",
        "entity_light_upstairs": "light.replace_me_upstairs",
        "light_slot_count": "6",
        "light_slot_1_name": "Foyer",
        "light_slot_2_name": "Vanity",
        "light_slot_3_name": "Bedroom",
        "light_slot_4_name": "Hall",
        "light_slot_5_name": "Office",
        "light_slot_6_name": "Upstairs",
        "light_slot_7_name": "Spare 7",
        "light_slot_8_name": "Spare 8",
        "light_slot_1_entity": "light.replace_me_slot_1",
        "light_slot_2_entity": "light.replace_me_slot_2",
        "light_slot_3_entity": "light.replace_me_slot_3",
        "light_slot_4_entity": "light.replace_me_slot_4",
        "light_slot_5_entity": "light.replace_me_slot_5",
        "light_slot_6_entity": "light.replace_me_slot_6",
        "light_slot_7_entity": "light.replace_me_slot_7",
        "light_slot_8_entity": "light.replace_me_slot_8",
        "entity_wx_main": "weather.replace_me",
        "entity_wx_condition_sensor": "sensor.replace_me_weather_condition",
        "entity_wx_weather_sensor": "sensor.replace_me_weather_text",
        "entity_wx_temp_sensor": "sensor.replace_me_weather_temperature",
        "entity_wx_feels_sensor": "sensor.replace_me_weather_feels_like",
        "entity_wx_humidity_sensor": "sensor.replace_me_weather_humidity",
        "entity_wx_clouds_sensor": "sensor.replace_me_weather_clouds",
        "entity_wx_pressure_sensor": "sensor.replace_me_weather_pressure",
        "entity_wx_uv_sensor": "sensor.replace_me_weather_uv",
        "entity_wx_visibility_sensor": "sensor.replace_me_weather_visibility",
        "entity_wx_wind_speed_sensor": "sensor.replace_me_weather_wind_speed",
        "entity_wx_apparent_sensor": "sensor.replace_me_weather_apparent_temperature",
        "entity_wx_dew_point_sensor": "sensor.replace_me_weather_dew_point",
        "entity_wx_precip_kind_sensor": "sensor.replace_me_weather_precipitation_kind",
        "entity_wx_rain_intensity_sensor": "sensor.replace_me_weather_rain_intensity",
        "entity_wx_snow_intensity_sensor": "sensor.replace_me_weather_snow_intensity",
        "entity_wx_weather_code_sensor": "sensor.replace_me_weather_code",
        "entity_wx_wind_direction_sensor": "sensor.replace_me_weather_wind_direction",
        "entity_wx_wind_gust_sensor": "sensor.replace_me_weather_wind_gust_speed",
        "entity_wx_today_high_sensor": "sensor.replace_me_weather_today_high",
        "entity_wx_today_low_sensor": "sensor.replace_me_weather_today_low",
        "entity_ha_unit_system": "sensor.unit_system",
        "entity_word_of_day_sensor": "sensor.replace_me_word_of_day",
        "entity_quote_of_hour_sensor": "sensor.replace_me_quote_of_hour",
        "entity_feed_bbc": "event.replace_me_bbc",
        "entity_feed_dc": "event.replace_me_dc",
        "entity_feed_loudoun": "event.replace_me_loudoun",
        "entity_sensi_climate": "climate.replace_me",
        "entity_sensi_temperature_sensor": "sensor.replace_me_sensi_temperature",
        "entity_sensi_humidity_sensor": "sensor.replace_me_sensi_humidity",
        "entity_sensi_auto_cool_number": "number.replace_me_sensi_auto_cool",
        "entity_sensi_auto_heat_number": "number.replace_me_sensi_auto_heat",
        "entity_sensi_humidity_offset_number": "number.replace_me_sensi_humidity_offset",
        "entity_sensi_temperature_offset_number": "number.replace_me_sensi_temperature_offset",
        "entity_sensi_aux_heat_switch": "switch.replace_me_sensi_aux_heat",
        "entity_sensi_display_humidity_switch": "switch.replace_me_sensi_display_humidity",
        "entity_sensi_display_time_switch": "switch.replace_me_sensi_display_time",
        "entity_sensi_fan_support_switch": "switch.replace_me_sensi_fan_support",
        "entity_sensi_humidification_switch": "switch.replace_me_sensi_humidification",
        "entity_sensi_keypad_lockout_switch": "switch.replace_me_sensi_keypad_lockout",
        "ui_show_lights": "true",
        "ui_show_weather": "true",
        "ui_show_climate": "true",
        "ui_show_reader": "true",
        "ui_show_cameras": "true",
        "ui_show_settings": "true",
        "ui_show_theme": "true",
        "home_tile_show_weather": "true",
        "home_tile_show_climate": "true",
        "home_tile_show_lights": "true",
        "home_tile_show_cameras": "true",
        "home_tile_show_reader": "true",
        "theme_token_screen_bg": "0x0B1117",
        "theme_token_surface": "0x121A23",
        "theme_token_surface_alt": "0x1A2431",
        "theme_token_action": "0x4F8FE6",
        "theme_token_action_soft": "0x3A6FAE",
        "theme_token_text_primary": "0xEDF4FF",
        "theme_token_text_dim": "0xBFD0E6",
        "theme_token_ok": "0x2F9F77",
        "theme_token_warn": "0xD88D38",
        "theme_border_width": "2",
        "theme_radius": "10",
        "theme_icon_mode": "0",
    }


def _required_by_feature() -> Dict[str, List[str]]:
    return {
        "lights": ["light_slot_count", "light_slot_1_entity"],
        "weather": ["entity_wx_main", "entity_wx_temp_sensor"],
        "climate": ["entity_sensi_climate", "entity_sensi_temperature_sensor"],
        "cameras": ["camera_slot_count", "camera_slot_1_entity", "ha_base_url"],
        "reader": ["entity_feed_bbc", "entity_feed_dc", "entity_feed_loudoun"],
        "gps": ["gps_rx_pin", "gps_tx_pin", "gps_baud_rate"],
    }


def _contracts() -> Dict[str, Any]:
    defaults = _default_substitutions()
    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "workspace_schema_version": WORKSPACE_SCHEMA_VERSION,
        "required_by_feature": _required_by_feature(),
        "domain_hints": DOMAIN_HINTS,
        "ui_keys": [
            "ui_show_lights",
            "ui_show_weather",
            "ui_show_climate",
            "ui_show_reader",
            "ui_show_cameras",
            "ui_show_settings",
            "ui_show_theme",
            "home_tile_show_weather",
            "home_tile_show_climate",
            "home_tile_show_lights",
            "home_tile_show_cameras",
            "home_tile_show_reader",
        ],
        "theme_keys": [
            "theme_token_screen_bg",
            "theme_token_surface",
            "theme_token_surface_alt",
            "theme_token_action",
            "theme_token_action_soft",
            "theme_token_text_primary",
            "theme_token_text_dim",
            "theme_token_ok",
            "theme_token_warn",
            "theme_border_width",
            "theme_radius",
            "theme_icon_mode",
        ],
        "update_keys": [
            "app_release_channel",
            "app_release_version",
            "ha_native_firmware_entity",
            "ha_app_version_entity",
            "ha_esphome_compile_service",
            "ha_esphome_install_service",
        ],
        "dashboard_actions": ["connect_device", "map_entities", "theme", "layout", "deploy", "recover"],
        "entity_collection_keys": list(ENTITY_COLLECTION_LIMITS.keys()),
        "entity_collection_limits": ENTITY_COLLECTION_LIMITS,
        "layout_pages": list(_default_layout_pages().keys()),
        "defaults": defaults,
    }


def _default_template_catalog() -> Dict[str, Any]:
    return {
        "version": "2",
        "collections": {
            "lights": [
                {"name": "Primary Lights", "items": [{"name": "Living Room", "entity_id": "light.replace_me_living_room"}]},
                {"name": "Whole Home", "items": [{"name": "All Lights", "entity_id": "light.all_lights"}]},
            ],
            "cameras": [
                {"name": "Door + Outdoor", "items": [{"name": "Front Door", "entity_id": "camera.front_door"}, {"name": "Outdoor", "entity_id": "camera.outdoor"}]},
            ],
            "weather_metrics": [
                {"name": "Core Weather Metrics", "items": [{"name": "Temperature", "role": "entity_wx_temp_sensor"}, {"name": "Humidity", "role": "entity_wx_humidity_sensor"}]},
            ],
            "climate_controls": [
                {"name": "Core Climate Control", "items": [{"name": "Thermostat", "role": "entity_sensi_climate"}, {"name": "Indoor Temp", "role": "entity_sensi_temperature_sensor"}]},
            ],
            "reader_feeds": [
                {"name": "News Trio", "items": [{"name": "BBC", "role": "entity_feed_bbc"}, {"name": "DC", "role": "entity_feed_dc"}, {"name": "Loudoun", "role": "entity_feed_loudoun"}]},
            ],
            "system_entities": [
                {"name": "System Basics", "items": [{"name": "Unit System", "role": "entity_ha_unit_system"}]},
            ],
        },
        "entities": {
            "weather": [
                {
                    "name": "OpenWeather Hybrid",
                    "mappings": {
                        "entity_wx_main": "weather.openweathermap",
                        "entity_wx_temp_sensor": "sensor.openweathermap_temperature",
                        "entity_wx_condition_sensor": "sensor.openweathermap_condition",
                    },
                }
            ],
            "climate": [
                {
                    "name": "Sensi Core",
                    "mappings": {
                        "entity_sensi_climate": "climate.sensi",
                        "entity_sensi_temperature_sensor": "sensor.sensi_temperature",
                        "entity_sensi_humidity_sensor": "sensor.sensi_humidity",
                    },
                }
            ],
            "reader": [
                {
                    "name": "Reader Core",
                    "mappings": {
                        "entity_word_of_day_sensor": "sensor.word_of_the_day",
                        "entity_quote_of_hour_sensor": "sensor.quote_of_the_hour",
                        "entity_feed_bbc": "event.bbc_top_story",
                        "entity_feed_dc": "event.dc_top_story",
                        "entity_feed_loudoun": "event.loudoun_top_story",
                    },
                }
            ],
        },
    }


def _default_theme_palettes() -> List[Dict[str, Any]]:
    return [
        {
            "id": "ocean_dark",
            "name": "Ocean Dark",
            "tokens": {
                "theme_token_screen_bg": "0x0B1117",
                "theme_token_surface": "0x121A23",
                "theme_token_surface_alt": "0x1A2431",
                "theme_token_action": "0x4F8FE6",
                "theme_token_action_soft": "0x3A6FAE",
                "theme_token_text_primary": "0xEDF4FF",
                "theme_token_text_dim": "0xBFD0E6",
                "theme_token_ok": "0x2F9F77",
                "theme_token_warn": "0xD88D38",
            },
        },
        {
            "id": "graphite_modern",
            "name": "Graphite Modern",
            "tokens": {
                "theme_token_screen_bg": "0x0E1013",
                "theme_token_surface": "0x1A1F26",
                "theme_token_surface_alt": "0x242B35",
                "theme_token_action": "0x5EA3FF",
                "theme_token_action_soft": "0x3F6C9D",
                "theme_token_text_primary": "0xF2F5FA",
                "theme_token_text_dim": "0xB0BAC8",
                "theme_token_ok": "0x37A06D",
                "theme_token_warn": "0xD98A30",
            },
        },
        {
            "id": "sand_modern",
            "name": "Sand Modern",
            "tokens": {
                "theme_token_screen_bg": "0x11100C",
                "theme_token_surface": "0x1C1A14",
                "theme_token_surface_alt": "0x2A251D",
                "theme_token_action": "0x3A8FB7",
                "theme_token_action_soft": "0x2C6D8C",
                "theme_token_text_primary": "0xF0E9DB",
                "theme_token_text_dim": "0xC8BCA6",
                "theme_token_ok": "0x4D9A63",
                "theme_token_warn": "0xD37D3A",
            },
        },
    ]


def _default_mode_ui() -> Dict[str, Any]:
    return {
        "mode": "guided",
        "guided_step": 0,
        "show_advanced_diagnostics": False,
    }


def _default_layout_pages() -> Dict[str, Any]:
    now = int(_now())
    pages = list(DEFAULT_LAYOUT_PAGE_IDS)
    out: Dict[str, Any] = {}
    for name in pages:
        out[name] = {
            "grid": dict(LAYOUT_GRID_DEFAULTS),
            "sections": [
                {"id": "header", "x": 0, "y": 0, "w": 4, "h": 1},
                {"id": "content", "x": 0, "y": 1, "w": 4, "h": 4},
                {"id": "footer", "x": 0, "y": 5, "w": 4, "h": 1},
            ],
            "updated_at": now,
        }
    return out


def _default_landing_state() -> Dict[str, Any]:
    return {
        "default_view": "dashboard",
        "dashboard_cards": ["connect", "map", "theme", "layout", "deploy", "recover"],
        "last_card": "",
        "onboarding_step": 0,
        "last_action": "",
        "last_error": "",
        "updated_at": int(_now()),
    }


def _default_theme_sync_state() -> Dict[str, Any]:
    return {
        "theme_revision_web": 0,
        "theme_revision_device": 0,
        "theme_last_writer": "web",
        "theme_conflict_policy": "manual_merge",
        "theme_conflict": False,
        "theme_last_conflict_at": 0,
        "device_snapshot": {},
    }


def _default_camera_autodetect_state() -> Dict[str, Any]:
    return {
        "enabled": True,
        "last_scan_at": 0,
        "detected": [],
        "accepted": [],
        "ignored": [],
        "last_error": "",
    }


def _profile_collections_default(profile: Dict[str, Any]) -> Dict[str, Any]:
    lights: List[Dict[str, Any]] = []
    cameras: List[Dict[str, Any]] = []
    weather_metrics: List[Dict[str, Any]] = []
    climate_controls: List[Dict[str, Any]] = []
    reader_feeds: List[Dict[str, Any]] = []
    system_entities: List[Dict[str, Any]] = []
    slots = profile.get("slots", {}) if isinstance(profile.get("slots"), dict) else {}
    slot_lights = slots.get("lights", []) if isinstance(slots.get("lights"), list) else []
    slot_cameras = slots.get("cameras", []) if isinstance(slots.get("cameras"), list) else []
    entities = profile.get("entities", {}) if isinstance(profile.get("entities"), dict) else {}
    settings = profile.get("settings", {}) if isinstance(profile.get("settings"), dict) else {}

    for idx, item in enumerate(slot_lights):
        lights.append(
            {
                "id": f"light_{idx+1}",
                "name": _as_str(item.get("name"), f"Light {idx+1}"),
                "entity_id": _as_str(item.get("entity"), ""),
                "enabled": idx < _as_int(slots.get("light_slot_count"), 6, 1, 8),
            }
        )
    for idx, item in enumerate(slot_cameras):
        cameras.append(
            {
                "id": f"camera_{idx+1}",
                "name": _as_str(item.get("name"), f"Camera {idx+1}"),
                "entity_id": _as_str(item.get("entity"), ""),
                "enabled": idx < _as_int(slots.get("camera_slot_count"), 0, 0, 2),
            }
        )
    weather_map = {
        "Main": "entity_wx_main",
        "Condition": "entity_wx_condition_sensor",
        "Weather": "entity_wx_weather_sensor",
        "Temperature": "entity_wx_temp_sensor",
        "Feels Like": "entity_wx_feels_sensor",
        "Humidity": "entity_wx_humidity_sensor",
        "Clouds": "entity_wx_clouds_sensor",
        "Pressure": "entity_wx_pressure_sensor",
        "UV": "entity_wx_uv_sensor",
        "Visibility": "entity_wx_visibility_sensor",
        "Wind Speed": "entity_wx_wind_speed_sensor",
    }
    for label, key in weather_map.items():
        weather_metrics.append(
            {
                "id": _slugify(key, key),
                "name": label,
                "entity_id": _as_str(entities.get(key), ""),
                "role": key,
                "enabled": True,
            }
        )

    climate_map = {
        "Climate": "entity_sensi_climate",
        "Indoor Temp": "entity_sensi_temperature_sensor",
        "Indoor Humidity": "entity_sensi_humidity_sensor",
        "Auto Cool Number": "entity_sensi_auto_cool_number",
        "Auto Heat Number": "entity_sensi_auto_heat_number",
        "Humidity Offset": "entity_sensi_humidity_offset_number",
        "Temp Offset": "entity_sensi_temperature_offset_number",
        "Aux Heat": "entity_sensi_aux_heat_switch",
    }
    for label, key in climate_map.items():
        climate_controls.append(
            {
                "id": _slugify(key, key),
                "name": label,
                "entity_id": _as_str(entities.get(key), ""),
                "role": key,
                "enabled": True,
            }
        )

    reader_map = {
        "Word of Day": "entity_word_of_day_sensor",
        "Quote of Hour": "entity_quote_of_hour_sensor",
        "BBC": "entity_feed_bbc",
        "DC": "entity_feed_dc",
        "Loudoun": "entity_feed_loudoun",
    }
    for label, key in reader_map.items():
        reader_feeds.append(
            {
                "id": _slugify(key, key),
                "name": label,
                "entity_id": _as_str(entities.get(key), ""),
                "role": key,
                "enabled": True,
            }
        )

    system_map = {
        "HA Unit System": "entity_ha_unit_system",
        "Native Firmware Entity": "ha_native_firmware_entity",
        "App Version Entity": "ha_app_version_entity",
    }
    for label, key in system_map.items():
        value = _as_str(settings.get(key), "") if key.startswith("ha_") else _as_str(entities.get(key), "")
        system_entities.append(
            {
                "id": _slugify(key, key),
                "name": label,
                "entity_id": value,
                "role": key,
                "enabled": True,
            }
        )

    return {
        "lights": lights,
        "cameras": cameras,
        "weather_metrics": weather_metrics,
        "climate_controls": climate_controls,
        "reader_feeds": reader_feeds,
        "system_entities": system_entities,
        "limits": {
            "lights_max": ENTITY_COLLECTION_LIMITS["lights"]["default_max"],
            "cameras_max": ENTITY_COLLECTION_LIMITS["cameras"]["default_max"],
            "weather_metrics_max": ENTITY_COLLECTION_LIMITS["weather_metrics"]["default_max"],
            "climate_controls_max": ENTITY_COLLECTION_LIMITS["climate_controls"]["default_max"],
            "reader_feeds_max": ENTITY_COLLECTION_LIMITS["reader_feeds"]["default_max"],
            "system_entities_max": ENTITY_COLLECTION_LIMITS["system_entities"]["default_max"],
        },
    }


def _normalize_collection_item(item: Dict[str, Any], prefix: str, index: int) -> Dict[str, Any]:
    return {
        "id": _slugify(item.get("id"), f"{prefix}_{index+1}"),
        "name": _as_str(item.get("name"), f"{prefix.title()} {index+1}"),
        "entity_id": _as_str(item.get("entity_id") or item.get("entity"), ""),
        "role": _as_str(item.get("role"), ""),
        "enabled": _as_bool(item.get("enabled"), True),
    }


def _normalize_profile_collections(profile: Dict[str, Any]) -> Dict[str, Any]:
    raw = profile.get("entity_collections")
    if not isinstance(raw, dict):
        raw = _profile_collections_default(profile)
    lights = raw.get("lights") if isinstance(raw.get("lights"), list) else []
    cameras = raw.get("cameras") if isinstance(raw.get("cameras"), list) else []
    weather_metrics = raw.get("weather_metrics") if isinstance(raw.get("weather_metrics"), list) else []
    climate_controls = raw.get("climate_controls") if isinstance(raw.get("climate_controls"), list) else []
    reader_feeds = raw.get("reader_feeds") if isinstance(raw.get("reader_feeds"), list) else []
    system_entities = raw.get("system_entities") if isinstance(raw.get("system_entities"), list) else []
    lights_norm = [_normalize_collection_item(item if isinstance(item, dict) else {}, "light", idx) for idx, item in enumerate(lights)]
    cameras_norm = [_normalize_collection_item(item if isinstance(item, dict) else {}, "camera", idx) for idx, item in enumerate(cameras)]
    weather_norm = [_normalize_collection_item(item if isinstance(item, dict) else {}, "weather_metric", idx) for idx, item in enumerate(weather_metrics)]
    climate_norm = [_normalize_collection_item(item if isinstance(item, dict) else {}, "climate_control", idx) for idx, item in enumerate(climate_controls)]
    reader_norm = [_normalize_collection_item(item if isinstance(item, dict) else {}, "reader_feed", idx) for idx, item in enumerate(reader_feeds)]
    system_norm = [_normalize_collection_item(item if isinstance(item, dict) else {}, "system_entity", idx) for idx, item in enumerate(system_entities)]
    limits = raw.get("limits") if isinstance(raw.get("limits"), dict) else {}
    lights_max = _as_int(limits.get("lights_max"), ENTITY_COLLECTION_LIMITS["lights"]["default_max"], 1, ENTITY_COLLECTION_LIMITS["lights"]["hard_max"])
    cameras_max = _as_int(limits.get("cameras_max"), ENTITY_COLLECTION_LIMITS["cameras"]["default_max"], 0, ENTITY_COLLECTION_LIMITS["cameras"]["hard_max"])
    weather_max = _as_int(limits.get("weather_metrics_max"), ENTITY_COLLECTION_LIMITS["weather_metrics"]["default_max"], 0, ENTITY_COLLECTION_LIMITS["weather_metrics"]["hard_max"])
    climate_max = _as_int(limits.get("climate_controls_max"), ENTITY_COLLECTION_LIMITS["climate_controls"]["default_max"], 0, ENTITY_COLLECTION_LIMITS["climate_controls"]["hard_max"])
    reader_max = _as_int(limits.get("reader_feeds_max"), ENTITY_COLLECTION_LIMITS["reader_feeds"]["default_max"], 0, ENTITY_COLLECTION_LIMITS["reader_feeds"]["hard_max"])
    system_max = _as_int(limits.get("system_entities_max"), ENTITY_COLLECTION_LIMITS["system_entities"]["default_max"], 0, ENTITY_COLLECTION_LIMITS["system_entities"]["hard_max"])
    return {
        "lights": lights_norm[: ENTITY_COLLECTION_LIMITS["lights"]["hard_max"]],
        "cameras": cameras_norm[: ENTITY_COLLECTION_LIMITS["cameras"]["hard_max"]],
        "weather_metrics": weather_norm[: ENTITY_COLLECTION_LIMITS["weather_metrics"]["hard_max"]],
        "climate_controls": climate_norm[: ENTITY_COLLECTION_LIMITS["climate_controls"]["hard_max"]],
        "reader_feeds": reader_norm[: ENTITY_COLLECTION_LIMITS["reader_feeds"]["hard_max"]],
        "system_entities": system_norm[: ENTITY_COLLECTION_LIMITS["system_entities"]["hard_max"]],
        "limits": {
            "lights_max": lights_max,
            "cameras_max": cameras_max,
            "weather_metrics_max": weather_max,
            "climate_controls_max": climate_max,
            "reader_feeds_max": reader_max,
            "system_entities_max": system_max,
        },
    }


def _sync_slots_from_collections(profile: Dict[str, Any]) -> None:
    collections = _normalize_profile_collections(profile)
    profile["entity_collections"] = collections
    lights = collections["lights"]
    cameras = collections["cameras"]
    enabled_lights = [x for x in lights if _as_bool(x.get("enabled"), True)]
    enabled_cameras = [x for x in cameras if _as_bool(x.get("enabled"), True)]
    slots = profile.get("slots", {}) if isinstance(profile.get("slots"), dict) else {}
    slot_lights: List[Dict[str, Any]] = []
    slot_cameras: List[Dict[str, Any]] = []
    for idx in range(8):
        item = enabled_lights[idx] if idx < len(enabled_lights) else {}
        slot_lights.append(
            {
                "name": _as_str(item.get("name"), f"Light {idx+1}"),
                "entity": _as_str(item.get("entity_id"), f"light.replace_me_slot_{idx+1}"),
            }
        )
    for idx in range(2):
        item = enabled_cameras[idx] if idx < len(enabled_cameras) else {}
        slot_cameras.append(
            {
                "name": _as_str(item.get("name"), f"Camera {idx+1}"),
                "entity": _as_str(item.get("entity_id"), f"camera.replace_me_{idx+1}"),
            }
        )
    slots["lights"] = slot_lights
    slots["cameras"] = slot_cameras
    slots["light_slot_count"] = _as_int(min(len(enabled_lights), 8), 0, 1, 8)
    slots["camera_slot_count"] = _as_int(min(len(enabled_cameras), 2), 0, 0, 2)
    profile["slots"] = slots


def _hex_to_rgb_int(hex_color: str) -> Tuple[int, int, int]:
    raw = _as_str(hex_color).strip().lower()
    if raw.startswith("0x"):
        raw = raw[2:]
    if raw.startswith("#"):
        raw = raw[1:]
    if len(raw) != 6:
        raw = "000000"
    val = int(raw, 16)
    return ((val >> 16) & 0xFF, (val >> 8) & 0xFF, val & 0xFF)


def _relative_luminance(rgb: Tuple[int, int, int]) -> float:
    def c(v: int) -> float:
        x = v / 255.0
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * c(r) + 0.7152 * c(g) + 0.0722 * c(b)


def _contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    fg = _relative_luminance(_hex_to_rgb_int(fg_hex))
    bg = _relative_luminance(_hex_to_rgb_int(bg_hex))
    bright = max(fg, bg)
    dark = min(fg, bg)
    return (bright + 0.05) / (dark + 0.05)


def _validate_layout_pages(layout_pages: Dict[str, Any]) -> Dict[str, Any]:
    pages = _default_layout_pages()
    if isinstance(layout_pages, dict):
        pages = _deep_merge(pages, layout_pages)
    errors: List[str] = []
    warnings: List[str] = []
    for page_id, page in pages.items():
        grid = page.get("grid", {}) if isinstance(page.get("grid"), dict) else {}
        cols = _as_int(grid.get("cols"), LAYOUT_GRID_DEFAULTS["cols"], 1, 12)
        rows = _as_int(grid.get("rows"), LAYOUT_GRID_DEFAULTS["rows"], 1, 20)
        sections = page.get("sections", []) if isinstance(page.get("sections"), list) else []
        rects: List[Tuple[str, int, int, int, int]] = []
        for idx, sec in enumerate(sections):
            if not isinstance(sec, dict):
                errors.append(f"{page_id}: section {idx} is not an object")
                continue
            sid = _as_str(sec.get("id"), f"section_{idx+1}")
            x = _as_int(sec.get("x"), 0, 0, cols - 1)
            y = _as_int(sec.get("y"), 0, 0, rows - 1)
            w = _as_int(sec.get("w"), 1, 1, cols)
            h = _as_int(sec.get("h"), 1, 1, rows)
            if x + w > cols or y + h > rows:
                errors.append(f"{page_id}:{sid} exceeds grid bounds ({cols}x{rows})")
            rects.append((sid, x, y, w, h))
        for i in range(len(rects)):
            a = rects[i]
            for j in range(i + 1, len(rects)):
                b = rects[j]
                ax1, ay1, ax2, ay2 = a[1], a[2], a[1] + a[3], a[2] + a[4]
                bx1, by1, bx2, by2 = b[1], b[2], b[1] + b[3], b[2] + b[4]
                overlap = ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1
                if overlap:
                    errors.append(f"{page_id}: overlap between '{a[0]}' and '{b[0]}'")
        if len(sections) == 0:
            warnings.append(f"{page_id}: no sections defined")
    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings, "pages": pages}


def _build_discovery_row(item: Dict[str, Any]) -> Dict[str, Any] | None:
    entity_id = _as_str(item.get("entity_id"))
    if "." not in entity_id:
        return None
    domain = entity_id.split(".", 1)[0].lower()
    attrs = item.get("attributes", {}) or {}
    return {
        "entity_id": entity_id,
        "domain": domain,
        "friendly_name": _as_str(attrs.get("friendly_name"), entity_id),
        "state": _as_str(item.get("state")),
        "unit": _as_str(attrs.get("unit_of_measurement")),
        "device_class": _as_str(attrs.get("device_class")),
        "mappable": domain in MAPPABLE_DOMAINS,
    }


def _build_domain_counts(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counts: Dict[str, int] = {}
    for row in rows:
        domain = row["domain"]
        counts[domain] = counts.get(domain, 0) + 1
    return [{"domain": k, "count": counts[k]} for k in sorted(counts.keys())]


def _cache_age_ms() -> int:
    fetched_at = float(_DISCOVERY_CACHE.get("fetched_at", 0.0) or 0.0)
    if fetched_at <= 0:
        return 0
    age = int((_now() - fetched_at) * 1000.0)
    return age if age >= 0 else 0


def _discovery_cache_snapshot() -> Dict[str, Any]:
    with _DISCOVERY_LOCK:
        rows = list(_DISCOVERY_CACHE.get("rows", []))
        domains = list(_DISCOVERY_CACHE.get("domains", []))
        fetched_at = float(_DISCOVERY_CACHE.get("fetched_at", 0.0) or 0.0)
        last_error = _as_str(_DISCOVERY_CACHE.get("last_error", ""))
        last_duration_ms = _as_int(_DISCOVERY_CACHE.get("last_duration_ms"), 0, 0, None)
        last_total = _as_int(_DISCOVERY_CACHE.get("last_total"), 0, 0, None)
    return {
        "rows": rows,
        "domains": domains,
        "fetched_at": fetched_at,
        "cache_age_ms": _cache_age_ms(),
        "stale": bool(last_error),
        "last_error": last_error,
        "last_duration_ms": last_duration_ms,
        "last_total": last_total,
    }


def _refresh_discovery_cache(force: bool = False) -> Dict[str, Any]:
    age_ms = _cache_age_ms()
    cache_is_fresh = False
    with _DISCOVERY_LOCK:
        has_rows = bool(_DISCOVERY_CACHE.get("rows"))
        if not force and has_rows and age_ms < CACHE_TTL_SECONDS * 1000:
            cache_is_fresh = True
    if cache_is_fresh:
        return _discovery_cache_snapshot()

    started = _now()
    try:
        states = _ha_get("/states", timeout=45)
        rows: List[Dict[str, Any]] = []
        for item in states:
            row = _build_discovery_row(item)
            if row:
                rows.append(row)
        rows.sort(key=lambda r: r["entity_id"])
        duration_ms = int((_now() - started) * 1000.0)
        with _DISCOVERY_LOCK:
            _DISCOVERY_CACHE["rows"] = rows
            _DISCOVERY_CACHE["domains"] = _build_domain_counts(rows)
            _DISCOVERY_CACHE["fetched_at"] = _now()
            _DISCOVERY_CACHE["last_error"] = ""
            _DISCOVERY_CACHE["last_duration_ms"] = duration_ms
            _DISCOVERY_CACHE["last_total"] = len(rows)
        return _discovery_cache_snapshot()
    except Exception as err:
        with _DISCOVERY_LOCK:
            _DISCOVERY_CACHE["last_error"] = str(err)
        return _discovery_cache_snapshot()


def _new_discovery_job(force: bool = False) -> Dict[str, Any]:
    global _DISCOVERY_JOB_SEQ
    _DISCOVERY_JOB_SEQ += 1
    now = _now()
    job_id = f"job-{int(now * 1000)}-{_DISCOVERY_JOB_SEQ}"
    return {
        "id": job_id,
        "force": bool(force),
        "status": "queued",
        "stage": "queued",
        "started_at": now,
        "updated_at": now,
        "finished_at": 0.0,
        "duration_ms": 0,
        "progress": 0,
        "total": 0,
        "rows": 0,
        "domains": 0,
        "error": "",
        "cancel_requested": False,
        "cache_fetched_at": 0.0,
    }


def _job_snapshot(job: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if not job:
        return None
    return {
        "id": _as_str(job.get("id")),
        "force": _as_bool(job.get("force"), False),
        "status": _as_str(job.get("status"), "unknown"),
        "stage": _as_str(job.get("stage"), _as_str(job.get("status"), "unknown")),
        "started_at": float(job.get("started_at", 0.0) or 0.0),
        "updated_at": float(job.get("updated_at", 0.0) or 0.0),
        "finished_at": float(job.get("finished_at", 0.0) or 0.0),
        "duration_ms": _as_int(job.get("duration_ms"), 0, 0, None),
        "progress": _as_int(job.get("progress"), 0, 0, 100),
        "total": _as_int(job.get("total"), 0, 0, None),
        "rows": _as_int(job.get("rows"), 0, 0, None),
        "domains": _as_int(job.get("domains"), 0, 0, None),
        "error": _as_str(job.get("error"), ""),
        "cancel_requested": _as_bool(job.get("cancel_requested"), False),
        "cache_fetched_at": float(job.get("cache_fetched_at", 0.0) or 0.0),
    }


def _cleanup_discovery_jobs() -> None:
    now = _now()
    stale_ids: List[str] = []
    for job_id, job in _DISCOVERY_JOBS.items():
        status = _as_str(job.get("status"))
        updated = float(job.get("updated_at", 0.0) or 0.0)
        if status in {"completed", "failed", "cancelled"} and updated > 0:
            if (now - updated) > DISCOVERY_JOB_POLL_TTL_SECONDS:
                stale_ids.append(job_id)
    for job_id in stale_ids:
        _DISCOVERY_JOBS.pop(job_id, None)


def _run_discovery_job(job_id: str) -> None:
    global _DISCOVERY_ACTIVE_JOB_ID
    started = _now()
    with _DISCOVERY_LOCK:
        job = _DISCOVERY_JOBS.get(job_id)
        if not job:
            return
        job["status"] = "running"
        job["stage"] = "loading_states"
        job["updated_at"] = _now()

    try:
        force = _as_bool(job.get("force"), False)
        age_ms = _cache_age_ms()
        cache = _discovery_cache_snapshot()
        if not force and cache.get("rows") and age_ms < CACHE_TTL_SECONDS * 1000:
            with _DISCOVERY_LOCK:
                job = _DISCOVERY_JOBS.get(job_id)
                if job:
                    job["status"] = "completed"
                    job["stage"] = "completed"
                    job["progress"] = 100
                    job["rows"] = len(cache.get("rows", []))
                    job["domains"] = len(cache.get("domains", []))
                    job["total"] = len(cache.get("rows", []))
                    job["cache_fetched_at"] = float(cache.get("fetched_at", 0.0) or 0.0)
                    job["duration_ms"] = int((_now() - started) * 1000.0)
                    job["finished_at"] = _now()
                    job["updated_at"] = _now()
            return

        states = _ha_get("/states", timeout=45)
        with _DISCOVERY_LOCK:
            job = _DISCOVERY_JOBS.get(job_id)
            if job:
                job["stage"] = "loading_states"
                job["updated_at"] = _now()
        total = len(states) if isinstance(states, list) else 0
        rows: List[Dict[str, Any]] = []
        processed = 0
        for item in states:
            with _DISCOVERY_LOCK:
                job = _DISCOVERY_JOBS.get(job_id)
                if not job:
                    return
                if _as_bool(job.get("cancel_requested"), False):
                    job["status"] = "cancelled"
                    job["stage"] = "cancelled"
                    job["updated_at"] = _now()
                    job["finished_at"] = _now()
                    job["duration_ms"] = int((_now() - started) * 1000.0)
                    return
            row = _build_discovery_row(item)
            if row:
                rows.append(row)
            processed += 1
            if processed % 250 == 0:
                pct = int((processed * 100) / total) if total > 0 else 0
                with _DISCOVERY_LOCK:
                    job = _DISCOVERY_JOBS.get(job_id)
                    if job:
                        job["stage"] = "indexing"
                        job["progress"] = pct if pct < 99 else 99
                        job["rows"] = len(rows)
                        job["total"] = total
                        job["updated_at"] = _now()

        rows.sort(key=lambda r: r["entity_id"])
        duration_ms = int((_now() - started) * 1000.0)
        with _DISCOVERY_LOCK:
            _DISCOVERY_CACHE["rows"] = rows
            _DISCOVERY_CACHE["domains"] = _build_domain_counts(rows)
            _DISCOVERY_CACHE["fetched_at"] = _now()
            _DISCOVERY_CACHE["last_error"] = ""
            _DISCOVERY_CACHE["last_duration_ms"] = duration_ms
            _DISCOVERY_CACHE["last_total"] = len(rows)

            job = _DISCOVERY_JOBS.get(job_id)
            if job:
                job["status"] = "completed"
                job["stage"] = "completed"
                job["progress"] = 100
                job["rows"] = len(rows)
                job["domains"] = len(_DISCOVERY_CACHE["domains"])
                job["total"] = total
                job["cache_fetched_at"] = _DISCOVERY_CACHE["fetched_at"]
                job["duration_ms"] = duration_ms
                job["finished_at"] = _now()
                job["updated_at"] = _now()
    except Exception as err:
        with _DISCOVERY_LOCK:
            _DISCOVERY_CACHE["last_error"] = str(err)
            job = _DISCOVERY_JOBS.get(job_id)
            if job:
                job["status"] = "failed"
                job["stage"] = "failed"
                job["error"] = str(err)
                job["finished_at"] = _now()
                job["updated_at"] = _now()
                job["duration_ms"] = int((_now() - started) * 1000.0)
    finally:
        with _DISCOVERY_LOCK:
            if _DISCOVERY_ACTIVE_JOB_ID == job_id:
                _DISCOVERY_ACTIVE_JOB_ID = ""
            _cleanup_discovery_jobs()


def _start_discovery_job(force: bool = False) -> Dict[str, Any]:
    global _DISCOVERY_ACTIVE_JOB_ID
    with _DISCOVERY_LOCK:
        _cleanup_discovery_jobs()
        if _DISCOVERY_ACTIVE_JOB_ID:
            existing = _DISCOVERY_JOBS.get(_DISCOVERY_ACTIVE_JOB_ID)
            if existing and _as_str(existing.get("status")) in {"queued", "running"}:
                return _job_snapshot(existing) or {}

        job = _new_discovery_job(force=force)
        _DISCOVERY_JOBS[job["id"]] = job
        _DISCOVERY_ACTIVE_JOB_ID = job["id"]

    worker = threading.Thread(target=_run_discovery_job, args=(job["id"],), daemon=True)
    worker.start()
    return _job_snapshot(job) or {}


def _get_discovery_job(job_id: str) -> Dict[str, Any] | None:
    with _DISCOVERY_LOCK:
        return _job_snapshot(_DISCOVERY_JOBS.get(job_id))


def _cancel_discovery_job(job_id: str) -> Dict[str, Any] | None:
    with _DISCOVERY_LOCK:
        job = _DISCOVERY_JOBS.get(job_id)
        if not job:
            return None
        status = _as_str(job.get("status"))
        if status in {"completed", "failed", "cancelled"}:
            return _job_snapshot(job)
        job["cancel_requested"] = True
        job["updated_at"] = _now()
        if status == "queued":
            job["status"] = "cancelled"
            job["stage"] = "cancelled"
            job["finished_at"] = _now()
            job["duration_ms"] = int((_now() - float(job.get("started_at", _now()))) * 1000.0)
        return _job_snapshot(job)


def _deep_merge(base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _default_profile() -> Dict[str, Any]:
    defaults = _default_substitutions()
    lights = [{"name": defaults[f"light_slot_{i}_name"], "entity": defaults[f"light_slot_{i}_entity"]} for i in range(1, 9)]
    cameras = [
        {"name": defaults["camera_slot_1_name"], "entity": defaults["camera_slot_1_entity"]},
        {"name": defaults["camera_slot_2_name"], "entity": defaults["camera_slot_2_entity"]},
    ]
    entities = {k: v for k, v in defaults.items() if k.startswith("entity_")}
    ui = {k: _as_bool(defaults[k], True) for k in _contracts()["ui_keys"]}
    theme = {k: defaults[k] for k in _contracts()["theme_keys"]}
    theme["units_mode"] = "imperial"
    settings = {
        "app_release_channel": defaults["app_release_channel"],
        "app_release_version": defaults["app_release_version"],
        "camera_refresh_interval_s": defaults["camera_refresh_interval_s"],
        "camera_snapshot_enable": defaults["camera_snapshot_enable"],
        "camera_snapshot_dir": defaults["camera_snapshot_dir"],
        "ha_base_url": defaults["ha_base_url"],
        "keyboard_alt_timeout_ms": defaults["keyboard_alt_timeout_ms"],
        "screensaver_keyboard_repeat_suppress_ms": defaults["screensaver_keyboard_repeat_suppress_ms"],
        "screensaver_keyboard_activity_min_interval_ms": defaults["screensaver_keyboard_activity_min_interval_ms"],
        "home_dynamic_weather_icon": defaults["home_dynamic_weather_icon"],
        "climate_ack_timeout_ms": defaults["climate_ack_timeout_ms"],
        "climate_resync_guard_ms": defaults["climate_resync_guard_ms"],
        "climate_tolerance_f": defaults["climate_tolerance_f"],
        "climate_tolerance_c_tenths": defaults["climate_tolerance_c_tenths"],
        "ha_native_firmware_entity": "",
        "ha_app_version_entity": "",
        "ha_esphome_compile_service": "",
        "ha_esphome_install_service": "",
    }
    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "profile_name": "default",
        "landing_state": _default_landing_state(),
        "device": {
            "name": defaults["name"],
            "friendly_name": defaults["friendly_name"],
            "git_ref": ADDON_GITHUB_REF,
            "git_url": ADDON_GITHUB_REPO_URL,
        },
        "features": {"lights": True, "weather": True, "climate": True, "cameras": False, "reader": True, "gps": True},
        "slots": {
            "light_slot_count": _as_int(defaults["light_slot_count"], 6, 1, 8),
            "lights": lights,
            "camera_slot_count": _as_int(defaults["camera_slot_count"], 0, 0, 2),
            "cameras": cameras,
        },
        "entities": entities,
        "ui": ui,
        "theme": theme,
        "settings": settings,
        "entity_collections": {
            "lights": lights,
            "cameras": cameras,
            "limits": {
                "lights_max": ENTITY_COLLECTION_LIMITS["lights"]["default_max"],
                "cameras_max": ENTITY_COLLECTION_LIMITS["cameras"]["default_max"],
            },
        },
        "layout_pages": _default_layout_pages(),
        "theme_studio": {
            "active_palette": "ocean_dark",
            "custom_tokens": {},
            "last_contrast_ratio": 0.0,
            "palettes": _default_theme_palettes(),
            "sync": _default_theme_sync_state(),
        },
        "camera_autodetect": _default_camera_autodetect_state(),
        "mode_ui": _default_mode_ui(),
        "deployment_workflow": {
            "last_action": "",
            "last_result": "",
            "last_error": "",
            "updated_at": int(_now()),
        },
    }


def _copy_obj(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _default_workspace() -> Dict[str, Any]:
    profile = _default_profile()
    profile["profile_name"] = "device_1"
    profile["device"]["name"] = "lilygo-tdeck-plus"
    profile["device"]["friendly_name"] = "LilyGO T-Deck Plus"
    return {
        "schema_version": WORKSPACE_SCHEMA_VERSION,
        "workspace_name": "default",
        "active_device_index": 0,
        "landing_state": _default_landing_state(),
        "devices": [profile],
        "mode_ui": _default_mode_ui(),
        "templates": _default_template_catalog(),
        "entity_collections": {},
        "layout_pages": _default_layout_pages(),
        "theme_studio": {
            "active_palette": "ocean_dark",
            "custom_tokens": {},
            "last_contrast_ratio": 0.0,
            "palettes": _default_theme_palettes(),
            "sync": _default_theme_sync_state(),
        },
        "camera_autodetect": _default_camera_autodetect_state(),
        "deployment_workflow": {
            "last_action": "",
            "last_result": "",
            "last_error": "",
            "updated_at": int(_now()),
        },
        "bindings": {},
        "layout": {},
        "theme": {},
        "migration": {"from_schema": "", "applied": False, "timestamp": int(_now())},
        "deployment": {
            "git_ref": ADDON_GITHUB_REF,
            "git_url": ADDON_GITHUB_REPO_URL,
            "app_release_channel": DEFAULT_RELEASE_CHANNEL,
            "app_release_version": DEFAULT_APP_RELEASE_VERSION,
        },
    }


def _normalize_workspace(workspace: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(workspace, dict):
        workspace = {}

    # Backward-compat: treat legacy single-profile payload as workspace with one device.
    if "devices" not in workspace and "device" in workspace and "features" in workspace:
        workspace = {
            "schema_version": WORKSPACE_SCHEMA_VERSION,
            "workspace_name": _as_str(workspace.get("profile_name"), "default"),
            "active_device_index": 0,
            "landing_state": _default_landing_state(),
            "devices": [workspace],
            "templates": {},
            "bindings": {},
            "layout": {},
            "theme": {},
            "deployment": {
                "git_ref": _as_str(workspace.get("device", {}).get("git_ref"), ADDON_GITHUB_REF),
                "git_url": _as_str(workspace.get("device", {}).get("git_url"), ADDON_GITHUB_REPO_URL),
                "app_release_channel": DEFAULT_RELEASE_CHANNEL,
                "app_release_version": _as_str(workspace.get("settings", {}).get("app_release_version"), DEFAULT_APP_RELEASE_VERSION),
            },
        }

    source_schema = _as_str(workspace.get("schema_version"), "")
    merged = _deep_merge(_copy_obj(_default_workspace()), workspace)
    merged["schema_version"] = WORKSPACE_SCHEMA_VERSION
    merged["workspace_name"] = _safe_profile_name(merged.get("workspace_name"), "default")
    if not isinstance(merged.get("devices"), list):
        merged["devices"] = []
    normalized_devices: List[Dict[str, Any]] = []
    for idx, device in enumerate(merged["devices"]):
        p = _normalize_profile(device if isinstance(device, dict) else {})
        p["profile_name"] = _safe_profile_name(p.get("profile_name"), f"device_{idx + 1}")
        normalized_devices.append(p)
    if not normalized_devices:
        normalized_devices = [_normalize_profile(_default_profile())]
        normalized_devices[0]["profile_name"] = "device_1"
    merged["devices"] = normalized_devices
    merged["active_device_index"] = _as_int(
        merged.get("active_device_index"),
        0,
        0,
        len(normalized_devices) - 1,
    )
    if not isinstance(merged.get("templates"), dict):
        merged["templates"] = _default_template_catalog()
    else:
        merged["templates"] = _deep_merge(_default_template_catalog(), merged["templates"])
    if not isinstance(merged.get("landing_state"), dict):
        merged["landing_state"] = _default_landing_state()
    else:
        merged["landing_state"] = _deep_merge(_default_landing_state(), merged["landing_state"])
    if not isinstance(merged.get("mode_ui"), dict):
        merged["mode_ui"] = _default_mode_ui()
    else:
        merged["mode_ui"] = _deep_merge(_default_mode_ui(), merged["mode_ui"])
    if not isinstance(merged.get("entity_collections"), dict):
        merged["entity_collections"] = {}
    if not isinstance(merged.get("layout_pages"), dict):
        merged["layout_pages"] = _default_layout_pages()
    else:
        merged["layout_pages"] = _deep_merge(_default_layout_pages(), merged["layout_pages"])
    if not isinstance(merged.get("theme_studio"), dict):
        merged["theme_studio"] = _default_workspace()["theme_studio"]
    else:
        merged["theme_studio"] = _deep_merge(_default_workspace()["theme_studio"], merged["theme_studio"])
    if not isinstance(merged.get("camera_autodetect"), dict):
        merged["camera_autodetect"] = _default_camera_autodetect_state()
    else:
        merged["camera_autodetect"] = _deep_merge(_default_camera_autodetect_state(), merged["camera_autodetect"])
    if not isinstance(merged.get("deployment_workflow"), dict):
        merged["deployment_workflow"] = _default_workspace()["deployment_workflow"]
    else:
        merged["deployment_workflow"] = _deep_merge(_default_workspace()["deployment_workflow"], merged["deployment_workflow"])
    if not isinstance(merged.get("migration"), dict):
        merged["migration"] = {"from_schema": source_schema, "applied": False, "timestamp": int(_now())}

    migrated = False
    for idx, profile in enumerate(merged["devices"]):
        profile = _normalize_profile(profile)
        _sync_slots_from_collections(profile)
        merged["devices"][idx] = profile
        dslug = _slugify(profile.get("device", {}).get("name"), f"device_{idx+1}")
        merged["entity_collections"][dslug] = _copy_obj(profile.get("entity_collections", {}))

    if source_schema and source_schema != WORKSPACE_SCHEMA_VERSION:
        migrated = True
    if not source_schema:
        migrated = source_schema != WORKSPACE_SCHEMA_VERSION
    merged["migration"] = {
        "from_schema": source_schema or "unknown",
        "applied": bool(migrated),
        "timestamp": int(_now()),
    }

    if not isinstance(merged.get("bindings"), dict):
        merged["bindings"] = {}
    if not isinstance(merged.get("layout"), dict):
        merged["layout"] = {}
    if not isinstance(merged.get("theme"), dict):
        merged["theme"] = {}
    if not isinstance(merged.get("deployment"), dict):
        merged["deployment"] = {}
    merged["deployment"]["git_ref"] = _as_str(merged["deployment"].get("git_ref"), ADDON_GITHUB_REF)
    merged["deployment"]["git_url"] = _as_str(merged["deployment"].get("git_url"), ADDON_GITHUB_REPO_URL)
    merged["deployment"]["app_release_channel"] = DEFAULT_RELEASE_CHANNEL
    merged["deployment"]["app_release_version"] = _as_str(
        merged["deployment"].get("app_release_version"),
        DEFAULT_APP_RELEASE_VERSION,
    )
    return merged


def _workspace_active_profile(
    workspace: Dict[str, Any],
    active_device_index: int | None = None,
    device_slug: str = "",
) -> Tuple[Dict[str, Any], int]:
    ws = _normalize_workspace(workspace)
    devices = ws["devices"]
    if device_slug:
        want = _slugify(device_slug, "")
        for idx, profile in enumerate(devices):
            slug = _slugify(profile.get("device", {}).get("name"), f"device_{idx + 1}")
            if slug == want:
                return profile, idx
    idx = ws.get("active_device_index", 0) if active_device_index is None else active_device_index
    idx = _as_int(idx, 0, 0, len(devices) - 1)
    return devices[idx], idx


def _normalize_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    merged = _deep_merge(json.loads(json.dumps(_default_profile())), profile or {})

    merged["schema_version"] = _as_str(merged.get("schema_version") or PROFILE_SCHEMA_VERSION)
    merged["profile_name"] = _safe_profile_name(merged.get("profile_name"), "default")
    if not isinstance(merged.get("landing_state"), dict):
        merged["landing_state"] = _default_landing_state()
    else:
        merged["landing_state"] = _deep_merge(_default_landing_state(), merged["landing_state"])
    merged["device"]["name"] = _as_str(merged["device"].get("name"), "lilygo-tdeck-plus")
    merged["device"]["friendly_name"] = _as_str(merged["device"].get("friendly_name"), "LilyGO T-Deck Plus")
    merged["device"]["git_ref"] = _as_str(merged["device"].get("git_ref"), ADDON_GITHUB_REF)
    merged["device"]["git_url"] = _as_str(merged["device"].get("git_url"), ADDON_GITHUB_REPO_URL)

    for key in ["lights", "weather", "climate", "cameras", "reader", "gps"]:
        merged["features"][key] = _as_bool(merged["features"].get(key), key != "cameras")

    slots = merged["slots"]
    slots["light_slot_count"] = _as_int(slots.get("light_slot_count"), 6, 1, 8)
    slots["camera_slot_count"] = _as_int(slots.get("camera_slot_count"), 0, 0, 2)

    lights = slots.get("lights") if isinstance(slots.get("lights"), list) else []
    while len(lights) < 8:
        idx = len(lights) + 1
        lights.append({"name": f"Light {idx}", "entity": f"light.replace_me_slot_{idx}"})
    slots["lights"] = lights[:8]

    cameras = slots.get("cameras") if isinstance(slots.get("cameras"), list) else []
    while len(cameras) < 2:
        idx = len(cameras) + 1
        cameras.append({"name": f"Camera {idx}", "entity": f"camera.replace_me_{idx}"})
    slots["cameras"] = cameras[:2]

    for item in slots["lights"]:
        item["name"] = _as_str(item.get("name"), "Light")
        item["entity"] = _as_str(item.get("entity"), "light.replace_me")
    for item in slots["cameras"]:
        item["name"] = _as_str(item.get("name"), "Camera")
        item["entity"] = _as_str(item.get("entity"), "camera.replace_me")

    if not isinstance(merged.get("entities"), dict):
        merged["entities"] = {}
    if not isinstance(merged.get("ui"), dict):
        merged["ui"] = {}
    if not isinstance(merged.get("theme"), dict):
        merged["theme"] = {}
    if not isinstance(merged.get("settings"), dict):
        merged["settings"] = {}

    for key in _contracts()["ui_keys"]:
        merged["ui"][key] = _as_bool(merged["ui"].get(key), True)

    defaults = _default_substitutions()
    for key in [
        "theme_token_screen_bg",
        "theme_token_surface",
        "theme_token_surface_alt",
        "theme_token_action",
        "theme_token_action_soft",
        "theme_token_text_primary",
        "theme_token_text_dim",
        "theme_token_ok",
        "theme_token_warn",
    ]:
        merged["theme"][key] = _normalize_color(merged["theme"].get(key), defaults[key])
    merged["theme"]["theme_border_width"] = str(_as_int(merged["theme"].get("theme_border_width"), 2, 0, 6))
    merged["theme"]["theme_radius"] = str(_as_int(merged["theme"].get("theme_radius"), 10, 0, 24))
    merged["theme"]["theme_icon_mode"] = str(_as_int(merged["theme"].get("theme_icon_mode"), 0, 0, 1))
    merged["theme"]["units_mode"] = "metric" if _as_str(merged["theme"].get("units_mode")).lower() == "metric" else "imperial"
    merged["settings"]["app_release_channel"] = DEFAULT_RELEASE_CHANNEL
    merged["settings"]["app_release_version"] = _as_str(
        merged["settings"].get("app_release_version"),
        DEFAULT_APP_RELEASE_VERSION,
    )
    merged["settings"]["ha_native_firmware_entity"] = _as_str(merged["settings"].get("ha_native_firmware_entity"), "")
    merged["settings"]["ha_app_version_entity"] = _as_str(merged["settings"].get("ha_app_version_entity"), "")
    merged["settings"]["ha_esphome_compile_service"] = _as_str(merged["settings"].get("ha_esphome_compile_service"), "")
    merged["settings"]["ha_esphome_install_service"] = _as_str(merged["settings"].get("ha_esphome_install_service"), "")
    if not isinstance(merged.get("mode_ui"), dict):
        merged["mode_ui"] = _default_mode_ui()
    else:
        merged["mode_ui"] = _deep_merge(_default_mode_ui(), merged["mode_ui"])
    if not isinstance(merged.get("layout_pages"), dict):
        merged["layout_pages"] = _default_layout_pages()
    else:
        merged["layout_pages"] = _deep_merge(_default_layout_pages(), merged["layout_pages"])
    if not isinstance(merged.get("theme_studio"), dict):
        merged["theme_studio"] = _default_profile().get("theme_studio", {})
    else:
        merged["theme_studio"] = _deep_merge(_default_profile().get("theme_studio", {}), merged["theme_studio"])
    if not isinstance(merged["theme_studio"].get("sync"), dict):
        merged["theme_studio"]["sync"] = _default_theme_sync_state()
    else:
        merged["theme_studio"]["sync"] = _deep_merge(_default_theme_sync_state(), merged["theme_studio"]["sync"])
    if not isinstance(merged.get("camera_autodetect"), dict):
        merged["camera_autodetect"] = _default_camera_autodetect_state()
    else:
        merged["camera_autodetect"] = _deep_merge(_default_camera_autodetect_state(), merged["camera_autodetect"])
    if not isinstance(merged.get("deployment_workflow"), dict):
        merged["deployment_workflow"] = _default_profile().get("deployment_workflow", {})
    else:
        merged["deployment_workflow"] = _deep_merge(_default_profile().get("deployment_workflow", {}), merged["deployment_workflow"])
    merged["entity_collections"] = _normalize_profile_collections(merged)
    _sync_slots_from_collections(merged)
    return merged


def _profile_to_substitutions(profile: Dict[str, Any], overrides: Dict[str, Any] | None = None) -> Dict[str, str]:
    p = _normalize_profile(profile)
    substitutions = _default_substitutions()

    substitutions["name"] = _as_str(p["device"].get("name"), substitutions["name"])
    substitutions["friendly_name"] = _as_str(p["device"].get("friendly_name"), substitutions["friendly_name"])

    for key, value in p.get("entities", {}).items():
        if key in substitutions:
            substitutions[key] = _as_str(value, substitutions[key])

    light_count = _as_int(p["slots"].get("light_slot_count"), 6, 1, 8)
    camera_count = _as_int(p["slots"].get("camera_slot_count"), 0, 0, 2)
    substitutions["light_slot_count"] = str(light_count)
    substitutions["camera_slot_count"] = str(camera_count)

    lights = p["slots"].get("lights", [])
    for idx in range(1, 9):
        entry = lights[idx - 1] if idx - 1 < len(lights) else {}
        substitutions[f"light_slot_{idx}_name"] = _as_str(entry.get("name"), substitutions[f"light_slot_{idx}_name"])
        substitutions[f"light_slot_{idx}_entity"] = _as_str(entry.get("entity"), substitutions[f"light_slot_{idx}_entity"])

    cameras = p["slots"].get("cameras", [])
    for idx in range(1, 3):
        entry = cameras[idx - 1] if idx - 1 < len(cameras) else {}
        substitutions[f"camera_slot_{idx}_name"] = _as_str(entry.get("name"), substitutions[f"camera_slot_{idx}_name"])
        substitutions[f"camera_slot_{idx}_entity"] = _as_str(entry.get("entity"), substitutions[f"camera_slot_{idx}_entity"])

    for key in _contracts()["ui_keys"]:
        if key in p.get("ui", {}):
            substitutions[key] = _bool_str(p["ui"][key])

    features = p.get("features", {})
    if not _as_bool(features.get("lights"), True):
        substitutions["ui_show_lights"] = "false"
        substitutions["home_tile_show_lights"] = "false"
    if not _as_bool(features.get("weather"), True):
        substitutions["ui_show_weather"] = "false"
        substitutions["home_tile_show_weather"] = "false"
    if not _as_bool(features.get("climate"), True):
        substitutions["ui_show_climate"] = "false"
        substitutions["home_tile_show_climate"] = "false"
    if not _as_bool(features.get("reader"), True):
        substitutions["ui_show_reader"] = "false"
        substitutions["home_tile_show_reader"] = "false"
    if not _as_bool(features.get("cameras"), False):
        substitutions["ui_show_cameras"] = "false"
        substitutions["home_tile_show_cameras"] = "false"
        substitutions["camera_slot_count"] = "0"

    theme = p.get("theme", {})
    for key in _contracts()["theme_keys"]:
        if key in theme:
            if key.startswith("theme_token_"):
                substitutions[key] = _normalize_color(theme[key], substitutions[key])
            else:
                substitutions[key] = _as_str(theme[key], substitutions[key])

    settings = p.get("settings", {})
    for key in [
        "app_release_channel",
        "app_release_version",
        "camera_refresh_interval_s",
        "camera_snapshot_enable",
        "camera_snapshot_dir",
        "ha_base_url",
        "keyboard_alt_timeout_ms",
        "screensaver_keyboard_repeat_suppress_ms",
        "screensaver_keyboard_activity_min_interval_ms",
        "home_dynamic_weather_icon",
        "climate_ack_timeout_ms",
        "climate_resync_guard_ms",
        "climate_tolerance_f",
        "climate_tolerance_c_tenths",
    ]:
        if key in settings:
            if key in {"camera_snapshot_enable", "home_dynamic_weather_icon"}:
                substitutions[key] = _bool_str(settings[key])
            else:
                substitutions[key] = _as_str(settings[key], substitutions[key])

    collections = p.get("entity_collections", {}) if isinstance(p.get("entity_collections"), dict) else {}
    for cname in ["weather_metrics", "climate_controls", "reader_feeds", "system_entities"]:
        rows = collections.get(cname) if isinstance(collections.get(cname), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if not _as_bool(row.get("enabled"), True):
                continue
            role = _as_str(row.get("role"), "").strip()
            entity_id = _as_str(row.get("entity_id"), "").strip()
            if not role or not entity_id:
                continue
            if role in substitutions:
                substitutions[role] = entity_id
            elif role in settings:
                settings[role] = entity_id

    if overrides:
        for key, value in overrides.items():
            if key in substitutions:
                substitutions[key] = _as_str(value, substitutions[key])
    return substitutions


def _validate_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    p = _normalize_profile(profile)
    substitutions = _profile_to_substitutions(p)
    errors: List[str] = []
    warnings: List[str] = []
    collections = p.get("entity_collections", {}) if isinstance(p.get("entity_collections"), dict) else {}
    lights = collections.get("lights", []) if isinstance(collections.get("lights"), list) else []
    cameras = collections.get("cameras", []) if isinstance(collections.get("cameras"), list) else []

    if _as_str(p.get("schema_version"), "") != PROFILE_SCHEMA_VERSION:
        warnings.append(
            f"schema_version '{p.get('schema_version')}' differs from expected '{PROFILE_SCHEMA_VERSION}'."
        )
    app_release_version = _as_str(substitutions.get("app_release_version"), "").strip()
    app_release_channel = _as_str(substitutions.get("app_release_channel"), "").strip().lower()
    if not app_release_version:
        errors.append("app_release_version is required.")
    elif not re.match(r"^v\d+\.\d+\.\d+([\-+].+)?$", app_release_version):
        warnings.append("app_release_version should follow semantic tag style (for example v0.23.1).")
    if app_release_channel not in {"stable", "beta", "dev"}:
        warnings.append("app_release_channel should be stable, beta, or dev.")

    features = p.get("features", {})
    if _as_bool(features.get("lights"), True):
        light_count = _as_int(substitutions.get("light_slot_count"), 6, 1, 8)
        enabled_lights = [x for x in lights if _as_bool(x.get("enabled"), True)]
        if len(enabled_lights) == 0:
            warnings.append("lights feature enabled but no enabled lights in dynamic collections.")
        if len(lights) > ENTITY_COLLECTION_LIMITS["lights"]["hard_max"]:
            errors.append(f"lights collection exceeds hard limit {ENTITY_COLLECTION_LIMITS['lights']['hard_max']}.")
        for idx in range(1, light_count + 1):
            key = f"light_slot_{idx}_entity"
            if _is_placeholder(substitutions.get(key, "")):
                errors.append(f"{key} is required when lights feature is enabled.")
    if _as_bool(features.get("weather"), True):
        for key in ["entity_wx_main", "entity_wx_temp_sensor"]:
            if _is_placeholder(substitutions.get(key, "")):
                errors.append(f"{key} is required when weather feature is enabled.")
    if _as_bool(features.get("climate"), True):
        for key in ["entity_sensi_climate", "entity_sensi_temperature_sensor"]:
            if _is_placeholder(substitutions.get(key, "")):
                errors.append(f"{key} is required when climate feature is enabled.")
    if _as_bool(features.get("cameras"), False):
        camera_count = _as_int(substitutions.get("camera_slot_count"), 0, 0, 2)
        enabled_cameras = [x for x in cameras if _as_bool(x.get("enabled"), True)]
        if len(cameras) > ENTITY_COLLECTION_LIMITS["cameras"]["hard_max"]:
            errors.append(f"cameras collection exceeds hard limit {ENTITY_COLLECTION_LIMITS['cameras']['hard_max']}.")
        if len(enabled_cameras) == 0:
            warnings.append("cameras feature enabled but no enabled cameras in dynamic collections.")
        if camera_count <= 0:
            warnings.append("Cameras feature is enabled but camera_slot_count is 0.")
        for idx in range(1, camera_count + 1):
            key = f"camera_slot_{idx}_entity"
            if _is_placeholder(substitutions.get(key, "")):
                errors.append(f"{key} is required when cameras feature is enabled.")
    if _as_bool(features.get("reader"), True):
        for key in ["entity_feed_bbc", "entity_feed_dc", "entity_feed_loudoun"]:
            if _is_placeholder(substitutions.get(key, "")):
                warnings.append(f"{key} is unset; reader page may be partially empty.")

    for cname, limit_meta in ENTITY_COLLECTION_LIMITS.items():
        rows = collections.get(cname, []) if isinstance(collections.get(cname), list) else []
        hard_max = _as_int(limit_meta.get("hard_max"), 64, 1, 4096)
        if len(rows) > hard_max:
            errors.append(f"{cname} collection exceeds hard limit {hard_max}.")
        seen_ids: Dict[str, int] = {}
        seen_entities: Dict[str, int] = {}
        for idx, row in enumerate(rows):
            rid = _slugify(row.get("id"), "")
            entity_id = _as_str(row.get("entity_id"), "").strip().lower()
            if rid:
                if rid in seen_ids:
                    warnings.append(f"{cname} duplicate id '{rid}' at positions {seen_ids[rid] + 1} and {idx + 1}.")
                else:
                    seen_ids[rid] = idx
            if entity_id:
                if entity_id in seen_entities:
                    warnings.append(f"{cname} duplicate entity '{entity_id}' at positions {seen_entities[entity_id] + 1} and {idx + 1}.")
                else:
                    seen_entities[entity_id] = idx

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "profile": p,
        "substitutions": substitutions,
    }


def _mapping_suggestions(key: str, query: str = "", limit: int = 12) -> List[Dict[str, Any]]:
    key = _as_str(key).strip()
    query = _as_str(query).strip().lower()
    hints = DOMAIN_HINTS.get(key, [])
    cache = _discovery_cache_snapshot()
    rows = cache.get("rows", [])

    scored: List[Tuple[int, Dict[str, Any]]] = []
    for row in rows:
        entity_id = _as_str(row.get("entity_id"))
        domain = _as_str(row.get("domain"))
        friendly = _as_str(row.get("friendly_name"))
        score = 0
        if hints and domain in hints:
            score += 40
        if query:
            if query in entity_id.lower():
                score += 35
            if query in friendly.lower():
                score += 25
        if "replace_me" in entity_id.lower():
            score -= 100
        if row.get("mappable"):
            score += 5
        if score > 0:
            scored.append((score, row))

    scored.sort(key=lambda x: (-x[0], _as_str(x[1].get("entity_id"))))
    out: List[Dict[str, Any]] = []
    for score, row in scored[:limit]:
        out.append(
            {
                "score": score,
                "entity_id": _as_str(row.get("entity_id")),
                "friendly_name": _as_str(row.get("friendly_name")),
                "domain": _as_str(row.get("domain")),
                "state": _as_str(row.get("state")),
            }
        )
    return out


def _profile_file(name: str) -> Path:
    safe = _safe_profile_name(name)
    return PROFILE_DIR / f"{safe}.json"


def _list_profiles() -> List[str]:
    names = [path.stem for path in PROFILE_DIR.glob("*.json")]
    names.sort()
    return names


def _save_profile(name: str, profile: Dict[str, Any]) -> str:
    safe = _safe_profile_name(name)
    path = _profile_file(safe)
    normalized = _normalize_profile(profile)
    normalized["profile_name"] = safe
    path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    return safe


def _load_profile(name: str) -> Dict[str, Any]:
    path = _profile_file(name)
    if not path.exists():
        raise FileNotFoundError(f"profile '{name}' not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    return _normalize_profile(data)


def _workspace_file(name: str) -> Path:
    safe = _safe_profile_name(name)
    return WORKSPACE_DIR / f"{safe}.json"


def _list_workspaces() -> List[str]:
    names = [path.stem for path in WORKSPACE_DIR.glob("*.json")]
    names.sort()
    return names


def _save_workspace(name: str, workspace: Dict[str, Any]) -> str:
    safe = _safe_profile_name(name)
    path = _workspace_file(safe)
    normalized = _normalize_workspace(workspace)
    normalized["workspace_name"] = safe
    path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    return safe


def _load_workspace(name: str) -> Dict[str, Any]:
    path = _workspace_file(name)
    if not path.exists():
        raise FileNotFoundError(f"workspace '{name}' not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    return _normalize_workspace(data)


def _load_workspace_or_default(name: str = "default") -> Dict[str, Any]:
    try:
        return _load_workspace(name)
    except Exception:
        ws = _default_workspace()
        ws["workspace_name"] = _safe_profile_name(name, "default")
        return _normalize_workspace(ws)


def _workspace_or_profile_from_payload(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], int]:
    if isinstance(payload.get("workspace"), dict):
        workspace = _normalize_workspace(payload["workspace"])
    elif isinstance(payload.get("profile"), dict):
        workspace = _normalize_workspace(payload["profile"])
    else:
        workspace = _default_workspace()

    requested_slug = _as_str(payload.get("device_slug"), "").strip()
    requested_idx = _as_int(payload.get("active_device_index"), workspace.get("active_device_index", 0), 0, None)
    profile, idx = _workspace_active_profile(workspace, requested_idx, requested_slug)
    workspace["active_device_index"] = idx
    return workspace, profile, idx


def _workspace_with_profile(workspace: Dict[str, Any], profile: Dict[str, Any], index: int) -> Dict[str, Any]:
    ws = _normalize_workspace(workspace)
    idx = _as_int(index, ws.get("active_device_index", 0), 0, len(ws.get("devices", [])) - 1)
    p = _normalize_profile(profile)
    _sync_slots_from_collections(p)
    ws["devices"][idx] = p
    ws["active_device_index"] = idx
    slug = _slugify(p.get("device", {}).get("name"), f"device_{idx+1}")
    if not isinstance(ws.get("entity_collections"), dict):
        ws["entity_collections"] = {}
    ws["entity_collections"][slug] = _copy_obj(p.get("entity_collections", {}))
    return ws


def _maybe_persist_workspace(payload: Dict[str, Any], workspace: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    persist = _as_bool(payload.get("persist"), False)
    ws = _normalize_workspace(workspace)
    if not persist:
        return ws, ""
    name = _safe_profile_name(payload.get("name") or ws.get("workspace_name") or "default")
    saved = _save_workspace(name, ws)
    ws["workspace_name"] = saved
    return ws, saved


def _managed_device_slug(profile: Dict[str, Any]) -> str:
    name = _as_str(profile.get("device", {}).get("name"), "lilygo-tdeck-plus")
    return _slugify(name, "tdeck")


def _managed_device_dir(device_slug: str) -> Path:
    slug = _slugify(device_slug, "tdeck")
    path = MANAGED_ROOT / slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def _managed_paths(device_slug: str) -> Dict[str, Path]:
    d = _managed_device_dir(device_slug)
    g = d / "generated"
    p = g / "pages"
    g.mkdir(parents=True, exist_ok=True)
    p.mkdir(parents=True, exist_ok=True)
    return {
        "install": d / "tdeck-install.yaml",
        "overrides": d / "tdeck-overrides.yaml",
        "generated_entities": g / "entities.generated.yaml",
        "generated_theme": g / "theme.generated.yaml",
        "generated_layout": g / "layout.generated.yaml",
        "generated_page_home": p / "home.generated.yaml",
        "generated_page_lights": p / "lights.generated.yaml",
        "generated_page_weather": p / "weather.generated.yaml",
        "generated_page_climate": p / "climate.generated.yaml",
    }


def _backup_root_for(device_slug: str) -> Path:
    slug = _slugify(device_slug, "tdeck")
    path = MANAGED_ROOT / ".backups" / slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(16384), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _unified_diff(old: str, new: str, old_name: str, new_name: str) -> str:
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=old_name, tofile=new_name, lineterm="")
    return "\n".join(diff)


def _build_generated_entities_yaml(profile: Dict[str, Any]) -> str:
    p = _normalize_profile(profile)
    collections = p.get("entity_collections", {}) if isinstance(p.get("entity_collections"), dict) else {}
    lights = collections.get("lights", []) if isinstance(collections.get("lights"), list) else []
    cameras = collections.get("cameras", []) if isinstance(collections.get("cameras"), list) else []
    lines: List[str] = [
        "# Auto-generated by T-Deck Admin Center. Do not hand-edit.",
        "substitutions:",
        f"  generated_entities_revision: {_q(str(int(_now())))}",
        f"  generated_light_count_total: {_q(str(len(lights)))}",
        f"  generated_camera_count_total: {_q(str(len(cameras)))}",
    ]
    lines.append("")
    lines.append("# Dynamic collection summary")
    for idx, item in enumerate(lights):
        lines.append(f"# light[{idx+1}] {_as_str(item.get('name'))} -> {_as_str(item.get('entity_id'))}")
    for idx, item in enumerate(cameras):
        lines.append(f"# camera[{idx+1}] {_as_str(item.get('name'))} -> {_as_str(item.get('entity_id'))}")
    return "\n".join(lines)


def _build_generated_theme_yaml(profile: Dict[str, Any]) -> str:
    p = _normalize_profile(profile)
    theme = p.get("theme", {}) if isinstance(p.get("theme"), dict) else {}
    defaults = _default_substitutions()
    lines: List[str] = [
        "# Auto-generated by T-Deck Admin Center. Do not hand-edit.",
        "substitutions:",
        f"  generated_theme_revision: {_q(str(int(_now())))}",
    ]
    for key in [
        "theme_token_screen_bg",
        "theme_token_surface",
        "theme_token_surface_alt",
        "theme_token_action",
        "theme_token_action_soft",
        "theme_token_text_primary",
        "theme_token_text_dim",
        "theme_token_ok",
        "theme_token_warn",
        "theme_border_width",
        "theme_radius",
        "theme_icon_mode",
    ]:
        lines.append(f"  {key}: {_q(_as_str(theme.get(key), defaults.get(key, '')))}")
    return "\n".join(lines)


def _build_generated_layout_yaml(profile: Dict[str, Any], workspace: Dict[str, Any]) -> str:
    p = _normalize_profile(profile)
    pages = workspace.get("layout_pages", {}) if isinstance(workspace.get("layout_pages"), dict) else p.get("layout_pages", {})
    val = _validate_layout_pages(pages)
    lines: List[str] = [
        "# Auto-generated by T-Deck Admin Center. Do not hand-edit.",
        "substitutions:",
        f"  generated_layout_revision: {_q(str(int(_now())))}",
        f"  generated_layout_ok: {_q('true' if val.get('ok') else 'false')}",
        f"  generated_layout_pages: {_q(str(len((val.get('pages') or {}).keys())))}",
    ]
    lines.append("")
    lines.append("# Layout validation result")
    if not val.get("ok"):
        for err in val.get("errors", []):
            lines.append(f"# layout_error: {err}")
    return "\n".join(lines)


def _build_generated_page_yaml(page_id: str, workspace: Dict[str, Any], profile: Dict[str, Any]) -> str:
    p = _normalize_profile(profile)
    pages = workspace.get("layout_pages", {}) if isinstance(workspace.get("layout_pages"), dict) else p.get("layout_pages", {})
    val = _validate_layout_pages(pages)
    page = (val.get("pages", {}) or {}).get(page_id, {})
    sections = page.get("sections", []) if isinstance(page.get("sections"), list) else []
    lines: List[str] = [
        "# Auto-generated by T-Deck Admin Center. Do not hand-edit.",
        "substitutions:",
        f"  generated_{page_id}_section_count: {_q(str(len(sections)))}",
        f"  generated_{page_id}_layout_revision: {_q(str(int(_now())))}",
        "",
        f"# {page_id} sections",
    ]
    for idx, section in enumerate(sections):
        sid = _as_str(section.get("id"), f"section_{idx+1}")
        x = _as_int(section.get("x"), 0, 0, None)
        y = _as_int(section.get("y"), 0, 0, None)
        w = _as_int(section.get("w"), 1, 1, None)
        h = _as_int(section.get("h"), 1, 1, None)
        lines.append(f"# {sid}: x={x} y={y} w={w} h={h}")
    return "\n".join(lines)


def _preview_managed_apply(
    workspace: Dict[str, Any],
    profile: Dict[str, Any],
    git_ref: str,
    git_url: str,
) -> Dict[str, Any]:
    device_slug = _managed_device_slug(profile)
    paths = _managed_paths(device_slug)
    substitutions = _profile_to_substitutions(profile)
    install_new = _build_install_yaml(substitutions, git_ref, git_url, include_generated=True)
    overrides_new = _build_overrides_yaml(substitutions)
    generated_entities_new = _build_generated_entities_yaml(profile)
    generated_theme_new = _build_generated_theme_yaml(profile)
    generated_layout_new = _build_generated_layout_yaml(profile, workspace)
    generated_page_home_new = _build_generated_page_yaml("home", workspace, profile)
    generated_page_lights_new = _build_generated_page_yaml("lights", workspace, profile)
    generated_page_weather_new = _build_generated_page_yaml("weather", workspace, profile)
    generated_page_climate_new = _build_generated_page_yaml("climate", workspace, profile)

    install_cur = _read_text(paths["install"])
    overrides_cur = _read_text(paths["overrides"])
    generated_entities_cur = _read_text(paths["generated_entities"])
    generated_theme_cur = _read_text(paths["generated_theme"])
    generated_layout_cur = _read_text(paths["generated_layout"])
    generated_page_home_cur = _read_text(paths["generated_page_home"])
    generated_page_lights_cur = _read_text(paths["generated_page_lights"])
    generated_page_weather_cur = _read_text(paths["generated_page_weather"])
    generated_page_climate_cur = _read_text(paths["generated_page_climate"])

    install_changed = install_cur != install_new
    overrides_changed = overrides_cur != overrides_new
    generated_entities_changed = generated_entities_cur != generated_entities_new
    generated_theme_changed = generated_theme_cur != generated_theme_new
    generated_layout_changed = generated_layout_cur != generated_layout_new
    generated_page_home_changed = generated_page_home_cur != generated_page_home_new
    generated_page_lights_changed = generated_page_lights_cur != generated_page_lights_new
    generated_page_weather_changed = generated_page_weather_cur != generated_page_weather_new
    generated_page_climate_changed = generated_page_climate_cur != generated_page_climate_new
    return {
        "device_slug": device_slug,
        "managed_root": str(MANAGED_ROOT),
        "install": {
            "path": str(paths["install"]),
            "changed": install_changed,
            "checksum_current": _sha256_text(install_cur) if install_cur else "",
            "checksum_new": _sha256_text(install_new),
            "diff": _unified_diff(install_cur, install_new, f"{paths['install']} (current)", f"{paths['install']} (new)") if install_changed else "",
            "content_new": install_new,
        },
        "overrides": {
            "path": str(paths["overrides"]),
            "changed": overrides_changed,
            "checksum_current": _sha256_text(overrides_cur) if overrides_cur else "",
            "checksum_new": _sha256_text(overrides_new),
            "diff": _unified_diff(overrides_cur, overrides_new, f"{paths['overrides']} (current)", f"{paths['overrides']} (new)") if overrides_changed else "",
            "content_new": overrides_new,
        },
        "generated": {
            "entities": {
                "path": str(paths["generated_entities"]),
                "changed": generated_entities_changed,
                "checksum_current": _sha256_text(generated_entities_cur) if generated_entities_cur else "",
                "checksum_new": _sha256_text(generated_entities_new),
                "diff": _unified_diff(generated_entities_cur, generated_entities_new, f"{paths['generated_entities']} (current)", f"{paths['generated_entities']} (new)") if generated_entities_changed else "",
                "content_new": generated_entities_new,
            },
            "theme": {
                "path": str(paths["generated_theme"]),
                "changed": generated_theme_changed,
                "checksum_current": _sha256_text(generated_theme_cur) if generated_theme_cur else "",
                "checksum_new": _sha256_text(generated_theme_new),
                "diff": _unified_diff(generated_theme_cur, generated_theme_new, f"{paths['generated_theme']} (current)", f"{paths['generated_theme']} (new)") if generated_theme_changed else "",
                "content_new": generated_theme_new,
            },
            "layout": {
                "path": str(paths["generated_layout"]),
                "changed": generated_layout_changed,
                "checksum_current": _sha256_text(generated_layout_cur) if generated_layout_cur else "",
                "checksum_new": _sha256_text(generated_layout_new),
                "diff": _unified_diff(generated_layout_cur, generated_layout_new, f"{paths['generated_layout']} (current)", f"{paths['generated_layout']} (new)") if generated_layout_changed else "",
                "content_new": generated_layout_new,
            },
            "page_home": {
                "path": str(paths["generated_page_home"]),
                "changed": generated_page_home_changed,
                "checksum_current": _sha256_text(generated_page_home_cur) if generated_page_home_cur else "",
                "checksum_new": _sha256_text(generated_page_home_new),
                "diff": _unified_diff(generated_page_home_cur, generated_page_home_new, f"{paths['generated_page_home']} (current)", f"{paths['generated_page_home']} (new)") if generated_page_home_changed else "",
                "content_new": generated_page_home_new,
            },
            "page_lights": {
                "path": str(paths["generated_page_lights"]),
                "changed": generated_page_lights_changed,
                "checksum_current": _sha256_text(generated_page_lights_cur) if generated_page_lights_cur else "",
                "checksum_new": _sha256_text(generated_page_lights_new),
                "diff": _unified_diff(generated_page_lights_cur, generated_page_lights_new, f"{paths['generated_page_lights']} (current)", f"{paths['generated_page_lights']} (new)") if generated_page_lights_changed else "",
                "content_new": generated_page_lights_new,
            },
            "page_weather": {
                "path": str(paths["generated_page_weather"]),
                "changed": generated_page_weather_changed,
                "checksum_current": _sha256_text(generated_page_weather_cur) if generated_page_weather_cur else "",
                "checksum_new": _sha256_text(generated_page_weather_new),
                "diff": _unified_diff(generated_page_weather_cur, generated_page_weather_new, f"{paths['generated_page_weather']} (current)", f"{paths['generated_page_weather']} (new)") if generated_page_weather_changed else "",
                "content_new": generated_page_weather_new,
            },
            "page_climate": {
                "path": str(paths["generated_page_climate"]),
                "changed": generated_page_climate_changed,
                "checksum_current": _sha256_text(generated_page_climate_cur) if generated_page_climate_cur else "",
                "checksum_new": _sha256_text(generated_page_climate_new),
                "diff": _unified_diff(generated_page_climate_cur, generated_page_climate_new, f"{paths['generated_page_climate']} (current)", f"{paths['generated_page_climate']} (new)") if generated_page_climate_changed else "",
                "content_new": generated_page_climate_new,
            },
        },
        "workspace_name": _as_str(workspace.get("workspace_name"), "default"),
        "profile_name": _as_str(profile.get("profile_name"), "device"),
    }


def _rotate_backups(device_slug: str) -> None:
    root = _backup_root_for(device_slug)
    snapshots = [p for p in root.iterdir() if p.is_dir()]
    snapshots.sort(key=lambda p: p.name, reverse=True)
    for stale in snapshots[BACKUP_KEEP_COUNT:]:
        shutil.rmtree(stale, ignore_errors=True)


def _backup_files(
    device_slug: str,
    preview: Dict[str, Any],
    profile: Dict[str, Any],
    workspace: Dict[str, Any],
    reason: str = "apply_commit",
    context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    root = _backup_root_for(device_slug)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    snapshot = root / stamp
    snapshot.mkdir(parents=True, exist_ok=True)
    paths = _managed_paths(device_slug)

    install_file = paths["install"]
    overrides_file = paths["overrides"]
    generated_entities_file = paths["generated_entities"]
    generated_theme_file = paths["generated_theme"]
    generated_layout_file = paths["generated_layout"]
    generated_page_home_file = paths["generated_page_home"]
    generated_page_lights_file = paths["generated_page_lights"]
    generated_page_weather_file = paths["generated_page_weather"]
    generated_page_climate_file = paths["generated_page_climate"]
    if install_file.exists():
        shutil.copy2(install_file, snapshot / "tdeck-install.yaml")
    if overrides_file.exists():
        shutil.copy2(overrides_file, snapshot / "tdeck-overrides.yaml")
    if generated_entities_file.exists():
        shutil.copy2(generated_entities_file, snapshot / "entities.generated.yaml")
    if generated_theme_file.exists():
        shutil.copy2(generated_theme_file, snapshot / "theme.generated.yaml")
    if generated_layout_file.exists():
        shutil.copy2(generated_layout_file, snapshot / "layout.generated.yaml")
    if generated_page_home_file.exists():
        shutil.copy2(generated_page_home_file, snapshot / "home.generated.yaml")
    if generated_page_lights_file.exists():
        shutil.copy2(generated_page_lights_file, snapshot / "lights.generated.yaml")
    if generated_page_weather_file.exists():
        shutil.copy2(generated_page_weather_file, snapshot / "weather.generated.yaml")
    if generated_page_climate_file.exists():
        shutil.copy2(generated_page_climate_file, snapshot / "climate.generated.yaml")

    manifest = {
        "timestamp": stamp,
        "reason": _as_str(reason, "apply_commit"),
        "device_slug": device_slug,
        "workspace_name": _as_str(workspace.get("workspace_name"), "default"),
        "profile_name": _as_str(profile.get("profile_name"), "device"),
        "checksums": {
            "install_before": preview["install"].get("checksum_current", ""),
            "overrides_before": preview["overrides"].get("checksum_current", ""),
            "install_after": preview["install"].get("checksum_new", ""),
            "overrides_after": preview["overrides"].get("checksum_new", ""),
            "generated_entities_before": preview.get("generated", {}).get("entities", {}).get("checksum_current", ""),
            "generated_theme_before": preview.get("generated", {}).get("theme", {}).get("checksum_current", ""),
            "generated_layout_before": preview.get("generated", {}).get("layout", {}).get("checksum_current", ""),
            "generated_entities_after": preview.get("generated", {}).get("entities", {}).get("checksum_new", ""),
            "generated_theme_after": preview.get("generated", {}).get("theme", {}).get("checksum_new", ""),
            "generated_layout_after": preview.get("generated", {}).get("layout", {}).get("checksum_new", ""),
            "generated_page_home_before": preview.get("generated", {}).get("page_home", {}).get("checksum_current", ""),
            "generated_page_lights_before": preview.get("generated", {}).get("page_lights", {}).get("checksum_current", ""),
            "generated_page_weather_before": preview.get("generated", {}).get("page_weather", {}).get("checksum_current", ""),
            "generated_page_climate_before": preview.get("generated", {}).get("page_climate", {}).get("checksum_current", ""),
            "generated_page_home_after": preview.get("generated", {}).get("page_home", {}).get("checksum_new", ""),
            "generated_page_lights_after": preview.get("generated", {}).get("page_lights", {}).get("checksum_new", ""),
            "generated_page_weather_after": preview.get("generated", {}).get("page_weather", {}).get("checksum_new", ""),
            "generated_page_climate_after": preview.get("generated", {}).get("page_climate", {}).get("checksum_new", ""),
        },
        "paths": {
            "install": str(install_file),
            "overrides": str(overrides_file),
            "generated_entities": str(generated_entities_file),
            "generated_theme": str(generated_theme_file),
            "generated_layout": str(generated_layout_file),
            "generated_page_home": str(generated_page_home_file),
            "generated_page_lights": str(generated_page_lights_file),
            "generated_page_weather": str(generated_page_weather_file),
            "generated_page_climate": str(generated_page_climate_file),
        },
        "context": context if isinstance(context, dict) else {},
    }
    (snapshot / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _rotate_backups(device_slug)
    return {
        "id": stamp,
        "path": str(snapshot),
        "manifest": manifest,
    }


def _get_apply_lock(device_slug: str) -> threading.Lock:
    slug = _slugify(device_slug, "tdeck")
    if slug not in _APPLY_LOCKS:
        _APPLY_LOCKS[slug] = threading.Lock()
    return _APPLY_LOCKS[slug]


def _list_backups(device_slug: str) -> List[Dict[str, Any]]:
    root = _backup_root_for(device_slug)
    if not root.exists():
        return []
    out: List[Dict[str, Any]] = []
    for p in sorted([x for x in root.iterdir() if x.is_dir()], key=lambda x: x.name, reverse=True):
        manifest_file = p / "manifest.json"
        manifest: Dict[str, Any] = {}
        if manifest_file.exists():
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            except Exception:
                manifest = {}
        out.append(
            {
                "id": p.name,
                "path": str(p),
                "has_install": (p / "tdeck-install.yaml").exists(),
                "has_overrides": (p / "tdeck-overrides.yaml").exists(),
                "has_generated_entities": (p / "entities.generated.yaml").exists(),
                "has_generated_theme": (p / "theme.generated.yaml").exists(),
                "has_generated_layout": (p / "layout.generated.yaml").exists() or (p / "ui-layout.yaml").exists(),
                "has_generated_page_home": (p / "home.generated.yaml").exists(),
                "has_generated_page_lights": (p / "lights.generated.yaml").exists(),
                "has_generated_page_weather": (p / "weather.generated.yaml").exists(),
                "has_generated_page_climate": (p / "climate.generated.yaml").exists(),
                "manifest": manifest,
            }
        )
    return out


def _restore_backup(device_slug: str, backup_id: str) -> Dict[str, Any]:
    backup_root = _backup_root_for(device_slug)
    target = backup_root / _safe_profile_name(backup_id, "")
    if not target.exists():
        raise FileNotFoundError(f"backup '{backup_id}' not found")
    paths = _managed_paths(device_slug)
    install_src = target / "tdeck-install.yaml"
    overrides_src = target / "tdeck-overrides.yaml"
    generated_entities_src = target / "entities.generated.yaml"
    generated_theme_src = target / "theme.generated.yaml"
    generated_layout_src = target / "layout.generated.yaml"
    # Backward-compatible fallback for earlier snapshots.
    if not generated_layout_src.exists():
        generated_layout_src = target / "ui-layout.yaml"
    generated_page_home_src = target / "home.generated.yaml"
    generated_page_lights_src = target / "lights.generated.yaml"
    generated_page_weather_src = target / "weather.generated.yaml"
    generated_page_climate_src = target / "climate.generated.yaml"
    restored = {
        "install": False,
        "overrides": False,
        "generated_entities": False,
        "generated_theme": False,
        "generated_layout": False,
        "generated_page_home": False,
        "generated_page_lights": False,
        "generated_page_weather": False,
        "generated_page_climate": False,
    }
    if install_src.exists():
        shutil.copy2(install_src, paths["install"])
        restored["install"] = True
    if overrides_src.exists():
        shutil.copy2(overrides_src, paths["overrides"])
        restored["overrides"] = True
    if generated_entities_src.exists():
        shutil.copy2(generated_entities_src, paths["generated_entities"])
        restored["generated_entities"] = True
    if generated_theme_src.exists():
        shutil.copy2(generated_theme_src, paths["generated_theme"])
        restored["generated_theme"] = True
    if generated_layout_src.exists():
        shutil.copy2(generated_layout_src, paths["generated_layout"])
        restored["generated_layout"] = True
    if generated_page_home_src.exists():
        shutil.copy2(generated_page_home_src, paths["generated_page_home"])
        restored["generated_page_home"] = True
    if generated_page_lights_src.exists():
        shutil.copy2(generated_page_lights_src, paths["generated_page_lights"])
        restored["generated_page_lights"] = True
    if generated_page_weather_src.exists():
        shutil.copy2(generated_page_weather_src, paths["generated_page_weather"])
        restored["generated_page_weather"] = True
    if generated_page_climate_src.exists():
        shutil.copy2(generated_page_climate_src, paths["generated_page_climate"])
        restored["generated_page_climate"] = True
    return {
        "device_slug": device_slug,
        "backup_id": backup_id,
        "restored": restored,
        "paths": {
            "install": str(paths["install"]),
            "overrides": str(paths["overrides"]),
            "generated_entities": str(paths["generated_entities"]),
            "generated_theme": str(paths["generated_theme"]),
            "generated_layout": str(paths["generated_layout"]),
            "generated_page_home": str(paths["generated_page_home"]),
            "generated_page_lights": str(paths["generated_page_lights"]),
            "generated_page_weather": str(paths["generated_page_weather"]),
            "generated_page_climate": str(paths["generated_page_climate"]),
        },
        "checksums": {
            "install": _sha256_file(paths["install"]),
            "overrides": _sha256_file(paths["overrides"]),
            "generated_entities": _sha256_file(paths["generated_entities"]),
            "generated_theme": _sha256_file(paths["generated_theme"]),
            "generated_layout": _sha256_file(paths["generated_layout"]),
            "generated_page_home": _sha256_file(paths["generated_page_home"]),
            "generated_page_lights": _sha256_file(paths["generated_page_lights"]),
            "generated_page_weather": _sha256_file(paths["generated_page_weather"]),
            "generated_page_climate": _sha256_file(paths["generated_page_climate"]),
        },
    }


def _resolve_generation_input(payload: Dict[str, Any]) -> Tuple[Dict[str, str], Dict[str, Any], str, str]:
    overrides = payload.get("substitutions", {}) if isinstance(payload.get("substitutions"), dict) else {}
    if isinstance(payload.get("workspace"), dict) or isinstance(payload.get("profile"), dict):
        workspace, profile, _ = _workspace_or_profile_from_payload(payload)
        substitutions = _profile_to_substitutions(profile, overrides)
        deployment = workspace.get("deployment", {}) if isinstance(workspace.get("deployment"), dict) else {}
        git_ref = _as_str(
            payload.get("git_ref"),
            _as_str(deployment.get("git_ref"), _as_str(profile.get("device", {}).get("git_ref"), ADDON_GITHUB_REF)),
        )
        git_url = _as_str(
            payload.get("git_url"),
            _as_str(deployment.get("git_url"), _as_str(profile.get("device", {}).get("git_url"), ADDON_GITHUB_REPO_URL)),
        )
        return substitutions, profile, git_ref or ADDON_GITHUB_REF, git_url or ADDON_GITHUB_REPO_URL

    substitutions = _default_substitutions()
    for key, value in overrides.items():
        if key in substitutions:
            substitutions[key] = _as_str(value)
    profile = _default_profile()
    git_ref = _as_str(payload.get("git_ref"), ADDON_GITHUB_REF) or ADDON_GITHUB_REF
    git_url = _as_str(payload.get("git_url"), ADDON_GITHUB_REPO_URL) or ADDON_GITHUB_REPO_URL
    return substitutions, profile, git_ref, git_url


def _build_install_yaml(
    substitutions: Dict[str, str],
    git_ref: str,
    git_url: str,
    include_generated: bool = False,
) -> str:
    lines: List[str] = ["substitutions:"]
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
            "  tdeck_core_remote:",
            f"    url: {_q(git_url)}",
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
        ]
    )
    if include_generated:
        lines.extend(
            [
                "  generated_entities: !include generated/entities.generated.yaml",
                "  generated_theme: !include generated/theme.generated.yaml",
                "  generated_layout: !include generated/layout.generated.yaml",
                "  generated_page_home: !include generated/pages/home.generated.yaml",
                "  generated_page_lights: !include generated/pages/lights.generated.yaml",
                "  generated_page_weather: !include generated/pages/weather.generated.yaml",
                "  generated_page_climate: !include generated/pages/climate.generated.yaml",
            ]
        )
    lines.extend(
        [
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


def _build_overrides_yaml(substitutions: Dict[str, str]) -> str:
    lines = ["substitutions:"]
    for key in sorted(substitutions.keys()):
        lines.append(f"  {key}: {_q(substitutions[key])}")
    return "\n".join(lines)


def _build_ha_update_package(
    profile: Dict[str, Any],
    latest_release: Dict[str, Any],
    installed_version_entity_override: str = "",
    native_firmware_entity_override: str = "",
) -> str:
    p = _normalize_profile(profile)
    device_name = _as_str(p.get("device", {}).get("name"), "lilygo-tdeck-plus")
    friendly_name = _as_str(p.get("device", {}).get("friendly_name"), "LilyGO T-Deck Plus")
    device_slug = _slugify(device_name, "tdeck")
    repo_slug = _repo_slug_from_url(_as_str(p.get("device", {}).get("git_url"), ADDON_GITHUB_REPO_URL))

    installed_entity = _as_str(installed_version_entity_override, f"sensor.{device_slug}_app_version").strip() or f"sensor.{device_slug}_app_version"
    channel_entity = f"sensor.{device_slug}_app_channel"
    native_firmware_entity = _as_str(native_firmware_entity_override, f"update.{device_slug}_firmware").strip() or f"update.{device_slug}_firmware"
    latest_sensor = f"sensor.tdeck_latest_stable_version_{device_slug}"
    path_status_sensor = f"sensor.tdeck_update_path_status_{device_slug}"
    last_check_sensor = f"sensor.tdeck_update_last_check_{device_slug}"
    app_update_entity = f"update.tdeck_app_update_{device_slug}"

    latest_version = _as_str(latest_release.get("version"), DEFAULT_APP_RELEASE_VERSION)
    latest_url = _as_str(latest_release.get("html_url"), f"https://github.com/{repo_slug}/releases/latest")

    lines: List[str] = [
        f"# Generated by T-Deck Admin Center for profile '{_as_str(p.get('profile_name'), 'default')}'.",
        "# Place this file under Home Assistant packages, then reload template/rest integrations.",
        "rest:",
        f"  - resource: https://api.github.com/repos/{repo_slug}/releases/latest",
        "    scan_interval: 900",
        "    timeout: 15",
        "    headers:",
        "      Accept: application/vnd.github+json",
        "      User-Agent: tdeck-ha-update-package",
        "    sensor:",
        f"      - name: {_q_single(f'T-Deck Latest Stable Version {friendly_name}')}",
        f"        unique_id: {_q_single(f'tdeck_latest_stable_version_{device_slug}')}",
        "        value_template: \"{{ value_json.tag_name | default('unknown') }}\"",
        "        attributes:",
        "          - name: published_at",
        "            value_template: \"{{ value_json.published_at | default('') }}\"",
        "          - name: html_url",
        "            value_template: \"{{ value_json.html_url | default('') }}\"",
        "          - name: body",
        "            value_template: \"{{ value_json.body | default('') }}\"",
        "",
        "template:",
        "  - sensor:",
        f"      - name: {_q_single(f'T-Deck Update Path Status {friendly_name}')}",
        f"        unique_id: {_q_single(f'tdeck_update_path_status_{device_slug}')}",
        "        state: >-",
        f"          {{% set fw = states('{native_firmware_entity}') %}}",
        "          {% if fw in ['unknown','unavailable','none',''] %}",
        "            missing_native_firmware_entity",
        "          {% else %}",
        "            ready",
        "          {% endif %}",
        f"      - name: {_q_single(f'T-Deck Update Last Check {friendly_name}')}",
        f"        unique_id: {_q_single(f'tdeck_update_last_check_{device_slug}')}",
        "        state: >-",
        f"          {{% set rel = states.sensor.tdeck_latest_stable_version_{device_slug} %}}",
        "          {{ rel.last_updated.isoformat() if rel is not none else 'unknown' }}",
        "  - update:",
        f"      - name: {_q_single(f'T-Deck App Update {friendly_name}')}",
        f"        unique_id: {_q_single(f'tdeck_app_update_{device_slug}')}",
        "        icon: mdi:package-up",
        "        device_class: firmware",
        f"        installed_version: \"{{{{ states('{installed_entity}') }}}}\"",
        f"        latest_version: \"{{{{ states('{latest_sensor}') }}}}\"",
        f"        release_url: \"{{{{ state_attr('{latest_sensor}', 'html_url') }}}}\"",
        f"        release_summary: \"{{{{ state_attr('{latest_sensor}', 'body') }}}}\"",
        "        install:",
        "          - choose:",
        "              - conditions:",
        "                  - condition: template",
        f"                    value_template: \"{{{{ states('{native_firmware_entity}') not in ['unknown','unavailable','none',''] }}}}\"",
        "                sequence:",
        "                  - service: update.install",
        "                    target:",
        f"                      entity_id: {native_firmware_entity}",
        "            default:",
        "              - service: persistent_notification.create",
        "                data:",
        "                  title: T-Deck update path missing",
        "                  message: >-",
        f"                    Native ESPHome firmware update entity '{native_firmware_entity}' was not found.",
        "                    Enable it in Home Assistant and retry.",
        "",
        "# Diagnostics references",
        f"# - Installed app version entity: {installed_entity}",
        f"# - Installed app channel entity: {channel_entity}",
        f"# - Latest release sensor: {latest_sensor}",
        f"# - Update path status sensor: {path_status_sensor}",
        f"# - Last release check sensor: {last_check_sensor}",
        f"# - Generated update entity: {app_update_entity}",
        f"# - Latest known stable at generation time: {latest_version} ({latest_url})",
    ]
    return "\n".join(lines)


def _infer_ingress_api_base() -> str:
    try:
        script_root = _as_str(request.script_root, "").rstrip("/")
        if script_root:
            return f"{script_root}/api"
        req_path = _as_str(request.path, "")
        if req_path.endswith("/api/health"):
            return req_path.rsplit("/api/health", 1)[0] + "/api"
        if req_path.endswith("/api/diagnostics/runtime"):
            return req_path.rsplit("/api/diagnostics/runtime", 1)[0] + "/api"
    except Exception:
        pass
    return "api"


def _resolve_firmware_capabilities(
    device_slug: str,
    settings: Dict[str, Any] | None = None,
    native_firmware_entity: str = "",
    app_version_entity: str = "",
    target_version: str = "",
) -> Dict[str, Any]:
    safe_slug = _slugify(device_slug, "tdeck")
    settings = settings if isinstance(settings, dict) else {}
    native_default, app_default = _resolve_firmware_entities(safe_slug, settings)
    native_entity = _as_str(native_firmware_entity, native_default).strip() or native_default
    app_entity = _as_str(app_version_entity, app_default).strip() or app_default
    target = _as_str(target_version, _as_str(settings.get("app_release_version"), DEFAULT_APP_RELEASE_VERSION)).strip() or DEFAULT_APP_RELEASE_VERSION

    services_catalog = _load_services_catalog(force=False)
    services = services_catalog.get("services", {}) if isinstance(services_catalog.get("services"), dict) else {}

    compile_override = _normalize_service_ref(settings.get("ha_esphome_compile_service"))
    install_override = _normalize_service_ref(settings.get("ha_esphome_install_service"))
    compile_candidates = [compile_override, "esphome.compile", "esphome.build"]
    install_candidates = [install_override, "esphome.install", "esphome.upload", "esphome.run"]

    compile_service = next((svc for svc in compile_candidates if svc and services.get(svc)), "")
    install_service = next((svc for svc in install_candidates if svc and services.get(svc)), "")

    native_state = _ha_get_state_safe(native_entity)
    app_state = _ha_get_state_safe(app_entity)
    native_available = bool(native_state.get("ok")) and not _state_is_unknown(native_state.get("state"))
    installed_version = _as_str(app_state.get("state"), "")
    installed_known = bool(app_state.get("ok")) and not _state_is_unknown(installed_version)
    target_norm = _normalize_version_text(target)
    installed_norm = _normalize_version_text(installed_version)
    firmware_pending = bool(target_norm) and ((not installed_known) or (installed_norm != target_norm))

    esphome_install_available = bool(install_service)
    esphome_build_install_available = bool(compile_service and install_service)
    recommended_method = "manual_fallback"
    if esphome_build_install_available:
        recommended_method = "esphome_service"
    elif native_available:
        recommended_method = "native_update_entity"
    elif esphome_install_available:
        recommended_method = "esphome_service"

    return {
        "device_slug": safe_slug,
        "target_version": target,
        "native_firmware_entity": native_entity,
        "app_version_entity": app_entity,
        "native_update_available": native_available,
        "native_update_state": _as_str(native_state.get("state"), ""),
        "esphome_compile_service": compile_service,
        "esphome_install_service": install_service,
        "esphome_install_available": esphome_install_available,
        "esphome_build_install_available": esphome_build_install_available,
        "services_cache_age_ms": services_catalog.get("cache_age_ms", 0),
        "services_stale": _as_bool(services_catalog.get("stale"), False),
        "services_last_error": _as_str(services_catalog.get("last_error"), ""),
        "installed_version": installed_version,
        "installed_version_known": installed_known,
        "firmware_pending": firmware_pending,
        "recommended_method": recommended_method,
        "methods": {
            "esphome_service": bool(esphome_install_available),
            "native_update_entity": bool(native_available),
            "manual_fallback": True,
        },
        "has_any_automatic_method": bool(esphome_install_available or native_available),
    }


def _choose_firmware_method(mode: str, capabilities: Dict[str, Any]) -> str:
    mode = _as_str(mode, "auto").strip().lower()
    can_build = _as_bool(capabilities.get("esphome_build_install_available"), False)
    can_esphome_install = _as_bool(capabilities.get("esphome_install_available"), False)
    can_native = _as_bool(capabilities.get("native_update_available"), False)
    if mode == "build_install":
        if can_build:
            return "esphome_service"
        if can_native:
            return "native_update_entity"
        return "manual_fallback"
    if mode == "install_only":
        if can_native:
            return "native_update_entity"
        if can_esphome_install:
            return "esphome_service"
        return "manual_fallback"
    if mode == "manual_fallback":
        return "manual_fallback"
    # auto
    if can_build:
        return "esphome_service"
    if can_native:
        return "native_update_entity"
    if can_esphome_install:
        return "esphome_service"
    return "manual_fallback"


def _attempt_service_call(
    service_ref: str,
    payloads: List[Dict[str, Any]],
    timeout: int = 25,
) -> Dict[str, Any]:
    errors: List[str] = []
    for payload in payloads:
        try:
            result = _ha_call_service_ref(service_ref, payload, timeout=timeout)
            return {"ok": True, "service": service_ref, "payload": payload, "response": result}
        except Exception as err:
            errors.append(str(err))
    return {"ok": False, "service": service_ref, "errors": errors}


def _execute_firmware_workflow(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    backup_first = _as_bool(payload.get("backup_first"), True)
    mode = _as_str(payload.get("mode"), "auto").strip().lower() or "auto"
    if mode not in {"auto", "build_install", "install_only", "manual_fallback"}:
        mode = "auto"

    workspace, profile, _ = _workspace_or_profile_from_payload(payload)
    settings = profile.get("settings", {}) if isinstance(profile.get("settings"), dict) else {}
    device_slug = _as_str(payload.get("device_slug"), _managed_device_slug(profile)).strip() or _managed_device_slug(profile)
    safe_slug = _slugify(device_slug, "tdeck")
    target_version = _as_str(payload.get("target_version"), _as_str(settings.get("app_release_version"), DEFAULT_APP_RELEASE_VERSION)).strip() or DEFAULT_APP_RELEASE_VERSION
    native_default, app_ver_default = _resolve_firmware_entities(device_slug, settings)
    native_firmware_entity = _as_str(payload.get("native_firmware_entity"), native_default).strip() or native_default
    app_version_entity = _as_str(payload.get("app_version_entity"), app_ver_default).strip() or app_ver_default

    capabilities = _resolve_firmware_capabilities(
        device_slug=device_slug,
        settings=settings,
        native_firmware_entity=native_firmware_entity,
        app_version_entity=app_version_entity,
        target_version=target_version,
    )
    selected_method = _choose_firmware_method(mode, capabilities)
    actions_attempted: List[Dict[str, Any]] = []

    lock = _get_apply_lock(device_slug)
    if not lock.acquire(blocking=False):
        return {
            "ok": False,
            "error": "apply_in_progress",
            "device_slug": safe_slug,
            "mode": mode,
            "selected_method": selected_method,
            "capabilities": capabilities,
        }, 409

    backup: Dict[str, Any] | None = None
    status_code = 200
    summary = ""
    manual_next_steps: List[str] = []
    try:
        preview = None
        if backup_first or selected_method == "esphome_service":
            deployment = workspace.get("deployment", {}) if isinstance(workspace.get("deployment"), dict) else {}
            git_ref = _as_str(payload.get("git_ref"), _as_str(deployment.get("git_ref"), _as_str(profile.get("device", {}).get("git_ref"), ADDON_GITHUB_REF)))
            git_url = _as_str(payload.get("git_url"), _as_str(deployment.get("git_url"), _as_str(profile.get("device", {}).get("git_url"), ADDON_GITHUB_REPO_URL)))
            preview = _preview_managed_apply(workspace, profile, git_ref or ADDON_GITHUB_REF, git_url or ADDON_GITHUB_REPO_URL)
            if backup_first:
                backup = _backup_files(
                    device_slug,
                    preview,
                    profile,
                    workspace,
                    reason="pre_build_install" if selected_method == "esphome_service" and mode == "build_install" else "pre_firmware_update",
                    context={
                        "selected_method": selected_method,
                        "mode": mode,
                        "native_firmware_entity": native_firmware_entity,
                        "app_version_entity": app_version_entity,
                        "target_version": target_version,
                    },
                )

        if selected_method == "esphome_service":
            install_file = ""
            if preview and isinstance(preview.get("install"), dict):
                install_file = _as_str(preview["install"].get("path"), "")
            compile_service = _as_str(capabilities.get("esphome_compile_service"), "")
            install_service = _as_str(capabilities.get("esphome_install_service"), "")

            if mode == "build_install" and compile_service:
                compile_attempt = _attempt_service_call(
                    compile_service,
                    [
                        {"configuration": install_file} if install_file else {},
                        {"name": safe_slug},
                        {"device": safe_slug},
                        {"node": safe_slug},
                        {},
                    ],
                    timeout=45,
                )
                actions_attempted.append(
                    {
                        "step": "compile",
                        "service": compile_service,
                        "status": "ok" if compile_attempt.get("ok") else "error",
                        "error": "; ".join(compile_attempt.get("errors", [])) if not compile_attempt.get("ok") else "",
                    }
                )
                if not compile_attempt.get("ok"):
                    if mode == "build_install":
                        selected_method = "manual_fallback"
                    summary = "Compile service failed"

            if selected_method == "esphome_service" and install_service:
                install_attempt = _attempt_service_call(
                    install_service,
                    [
                        {"name": safe_slug},
                        {"device": safe_slug},
                        {"node": safe_slug},
                        {"configuration": install_file} if install_file else {},
                        {},
                    ],
                    timeout=45,
                )
                actions_attempted.append(
                    {
                        "step": "install",
                        "service": install_service,
                        "status": "ok" if install_attempt.get("ok") else "error",
                        "error": "; ".join(install_attempt.get("errors", [])) if not install_attempt.get("ok") else "",
                    }
                )
                if install_attempt.get("ok"):
                    summary = "ESPHome service workflow requested"
                else:
                    if mode in {"auto", "install_only"} and _as_bool(capabilities.get("native_update_available"), False):
                        selected_method = "native_update_entity"
                    else:
                        selected_method = "manual_fallback"
                        summary = "ESPHome install service unavailable"

        if selected_method == "native_update_entity":
            try:
                service_response = _ha_post("/services/update/install", {"entity_id": native_firmware_entity}, timeout=25)
                actions_attempted.append(
                    {
                        "step": "update_install",
                        "service": "update.install",
                        "entity_id": native_firmware_entity,
                        "status": "ok",
                    }
                )
                summary = summary or "Native update entity install requested"
            except Exception as err:
                actions_attempted.append(
                    {
                        "step": "update_install",
                        "service": "update.install",
                        "entity_id": native_firmware_entity,
                        "status": "error",
                        "error": str(err),
                    }
                )
                summary = str(err)
                selected_method = "manual_fallback"
                status_code = 502

        if selected_method == "manual_fallback":
            manual_next_steps = [
                "Open ESPHome dashboard and run compile/install for this device.",
                "Verify the native firmware entity and app version sensor exist in Home Assistant.",
                f"Expected native update entity: {native_firmware_entity}",
                f"Expected app version sensor: {app_version_entity}",
            ]
            if preview and isinstance(preview.get("install"), dict):
                manual_next_steps.append(f"Managed install file: {preview['install'].get('path', '')}")
            actions_attempted.append({"step": "manual_fallback", "status": "required"})
            if not summary:
                summary = "Automatic firmware workflow not available"

        status = _firmware_status_for(
            device_slug=device_slug,
            target_version=target_version,
            native_firmware_entity=native_firmware_entity,
            app_version_entity=app_version_entity,
            capabilities=capabilities,
            selected_method=selected_method,
        )
        ok = selected_method != "manual_fallback" or mode == "manual_fallback"
        if selected_method == "manual_fallback" and mode in {"auto", "build_install", "install_only"}:
            ok = False
            if status_code < 400:
                status_code = 409

        with _RUNTIME_STATE_LOCK:
            _RUNTIME_STATE["last_prompted_device_slug"] = safe_slug
            _RUNTIME_STATE["last_firmware_action"] = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "status": "ok" if ok else "error",
                "device_slug": safe_slug,
                "selected_method": selected_method,
                "mode": mode,
                "target_version": target_version,
                "native_firmware_entity": native_firmware_entity,
                "app_version_entity": app_version_entity,
                "backup_id": backup.get("id", "") if isinstance(backup, dict) else "",
                "summary": summary,
                "actions_attempted": actions_attempted,
            }
            _save_runtime_state(_RUNTIME_STATE)

        return {
            "ok": ok,
            "mode": mode,
            "device_slug": safe_slug,
            "selected_method": selected_method,
            "target_version": target_version,
            "native_firmware_entity": native_firmware_entity,
            "app_version_entity": app_version_entity,
            "capabilities": capabilities,
            "actions_attempted": actions_attempted,
            "backup": backup or {},
            "status": status,
            "summary": summary,
            "manual_next_steps": manual_next_steps,
        }, status_code
    except Exception as err:
        with _RUNTIME_STATE_LOCK:
            _RUNTIME_STATE["last_firmware_action"] = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "status": "error",
                "device_slug": safe_slug,
                "selected_method": selected_method,
                "mode": mode,
                "target_version": target_version,
                "native_firmware_entity": native_firmware_entity,
                "app_version_entity": app_version_entity,
                "backup_id": backup.get("id", "") if isinstance(backup, dict) else "",
                "error": str(err),
            }
            _save_runtime_state(_RUNTIME_STATE)
        return {
            "ok": False,
            "error": str(err),
            "mode": mode,
            "device_slug": safe_slug,
            "selected_method": selected_method,
            "target_version": target_version,
            "native_firmware_entity": native_firmware_entity,
            "app_version_entity": app_version_entity,
            "backup": backup or {},
            "actions_attempted": actions_attempted,
            "capabilities": capabilities,
        }, 502
    finally:
        lock.release()


def _firmware_status_for(
    device_slug: str,
    target_version: str,
    native_firmware_entity: str,
    app_version_entity: str,
    capabilities: Dict[str, Any] | None = None,
    selected_method: str = "",
) -> Dict[str, Any]:
    safe_slug = _slugify(device_slug, "tdeck")
    target = _as_str(target_version, DEFAULT_APP_RELEASE_VERSION).strip()
    native = _ha_get_state_safe(native_firmware_entity)
    app_ver = _ha_get_state_safe(app_version_entity)

    installed_version = _as_str(app_ver.get("state"), "")
    native_state = _as_str(native.get("state"), "")
    installed_known = app_ver.get("ok") and not _state_is_unknown(installed_version)
    native_known = native.get("ok") and not _state_is_unknown(native_state)

    target_norm = _normalize_version_text(target)
    installed_norm = _normalize_version_text(installed_version)
    firmware_pending = bool(target_norm) and ((not installed_known) or (installed_norm != target_norm))
    update_available = _as_str(native_state).strip().lower() in {"on", "true", "pending"}

    issues: List[str] = []
    if not native.get("ok"):
        issues.append(f"native_update_entity_error: {native.get('error')}")
    if not app_ver.get("ok"):
        issues.append(f"app_version_entity_error: {app_ver.get('error')}")
    if not issues and firmware_pending:
        issues.append("firmware_version_mismatch")

    caps = capabilities if isinstance(capabilities, dict) else _resolve_firmware_capabilities(
        device_slug=device_slug,
        settings={},
        native_firmware_entity=native_firmware_entity,
        app_version_entity=app_version_entity,
        target_version=target,
    )
    method = selected_method or _as_str(caps.get("recommended_method"), "manual_fallback")

    status_text = "firmware_up_to_date"
    if not installed_known:
        status_text = "unknown_legacy"
    elif firmware_pending:
        status_text = "firmware_pending"
    if method == "manual_fallback":
        status_text = "manual_fallback"
    elif not native_known and not _as_bool(caps.get("esphome_install_available"), False):
        status_text = "native_update_entity_unavailable"

    runtime_before = _runtime_state_snapshot()
    with _RUNTIME_STATE_LOCK:
        dirty = False
        if firmware_pending:
            if _as_str(_RUNTIME_STATE.get("last_prompted_device_slug"), "") != safe_slug:
                _RUNTIME_STATE["last_prompted_device_slug"] = safe_slug
                dirty = True
        if runtime_before.get("addon_updated_since_last_run") and (not firmware_pending) and installed_known:
            if _as_bool(_RUNTIME_STATE.get("addon_updated_since_last_run"), False):
                _RUNTIME_STATE["addon_updated_since_last_run"] = False
                dirty = True
        if dirty:
            _save_runtime_state(_RUNTIME_STATE)
        runtime_after = {
            "last_seen_addon_version": _as_str(_RUNTIME_STATE.get("last_seen_addon_version"), ""),
            "addon_updated_since_last_run": _as_bool(_RUNTIME_STATE.get("addon_updated_since_last_run"), False),
            "last_prompted_device_slug": _as_str(_RUNTIME_STATE.get("last_prompted_device_slug"), ""),
            "last_firmware_action": _RUNTIME_STATE.get("last_firmware_action", {}),
        }

    return {
        "device_slug": safe_slug,
        "target_version": target,
        "installed_version": installed_version,
        "installed_known": bool(installed_known),
        "native_firmware_entity": native_firmware_entity,
        "native_state": native_state,
        "native_known": bool(native_known),
        "app_version_entity": app_version_entity,
        "firmware_pending": bool(firmware_pending),
        "update_available": bool(update_available),
        "method": method,
        "capabilities": caps,
        "status_text": status_text,
        "issues": issues,
        "runtime": runtime_after,
    }


@app.get("/api/health")
def api_health() -> Any:
    ha_ok = False
    ha_error = ""
    ha_info: Dict[str, Any] = {}
    try:
        ha_info = _ha_get("/", timeout=10)
        ha_ok = True
    except Exception as err:  # pragma: no cover
        ha_error = str(err)

    cache = _discovery_cache_snapshot()
    active_job = _get_discovery_job(_DISCOVERY_ACTIVE_JOB_ID) if _DISCOVERY_ACTIVE_JOB_ID else None
    runtime = _runtime_state_snapshot()
    selected_slug = _as_str(runtime.get("last_prompted_device_slug"), "lilygo-tdeck-plus") or "lilygo-tdeck-plus"
    try:
        caps = _resolve_firmware_capabilities(device_slug=selected_slug)
    except Exception as err:
        caps = {
            "recommended_method": "manual_fallback",
            "has_any_automatic_method": False,
            "services_last_error": str(err),
        }
    return jsonify(
        {
            "ok": True,
            "addon_version": ADDON_VERSION,
            "frontend_asset_version": ADDON_VERSION,
            "ingress_expected_prefix": _infer_ingress_api_base(),
            "addon_updated_since_last_run": runtime.get("addon_updated_since_last_run", False),
            "firmware_status_summary": _runtime_firmware_summary(),
            "firmware_capability_summary": {
                "device_slug": selected_slug,
                "recommended_method": caps.get("recommended_method", "manual_fallback"),
                "has_any_automatic_method": _as_bool(caps.get("has_any_automatic_method"), False),
                "native_update_available": _as_bool(caps.get("native_update_available"), False),
                "esphome_build_install_available": _as_bool(caps.get("esphome_build_install_available"), False),
                "services_last_error": _as_str(caps.get("services_last_error"), ""),
            },
            "runtime_state": runtime,
            "ha_connected": ha_ok,
            "ha_error": ha_error,
            "ha": ha_info,
            "transport": {
                "api_base_hint": _infer_ingress_api_base(),
                "request_path": _as_str(request.path, ""),
                "script_root": _as_str(request.script_root, ""),
                "host_url": _as_str(request.host_url, ""),
            },
            "cache": {
                "entities": len(cache.get("rows", [])),
                "domains": len(cache.get("domains", [])),
                "cache_age_ms": cache.get("cache_age_ms", 0),
                "stale": cache.get("stale", False),
                "last_error": cache.get("last_error", ""),
                "last_duration_ms": cache.get("last_duration_ms", 0),
                "last_total": cache.get("last_total", 0),
            },
            "discovery_job": active_job,
            "discovery": {
                "status": _as_str(active_job.get("status"), "idle") if active_job else "idle",
                "stage": _as_str(active_job.get("stage"), "idle") if active_job else "idle",
                "last_error": cache.get("last_error", ""),
                "last_duration_ms": cache.get("last_duration_ms", 0),
                "rows": len(cache.get("rows", [])),
            },
            "profiles": {
                "count": len(_list_profiles()),
                "path": str(PROFILE_DIR),
            },
            "workspaces": {
                "count": len(_list_workspaces()),
                "path": str(WORKSPACE_DIR),
            },
            "release_cache": {
                "channels": list((_RELEASE_CACHE.get("channels", {}) or {}).keys()),
                "cache_age_ms": _release_cache_age_ms(),
                "last_error": _RELEASE_CACHE.get("last_error", ""),
            },
            "managed_root": str(MANAGED_ROOT),
            "version": "4",
        }
    )


@app.get("/api/diagnostics/runtime")
def api_diagnostics_runtime() -> Any:
    runtime = _runtime_state_snapshot()
    cache = _discovery_cache_snapshot()
    active_job = _get_discovery_job(_DISCOVERY_ACTIVE_JOB_ID) if _DISCOVERY_ACTIVE_JOB_ID else None
    selected_slug = _as_str(runtime.get("last_prompted_device_slug"), "lilygo-tdeck-plus") or "lilygo-tdeck-plus"
    return jsonify(
        {
            "ok": True,
            "addon_version": ADDON_VERSION,
            "selected_device_slug": selected_slug,
            "runtime_state": runtime,
            "discovery_cache": {
                "cache_age_ms": cache.get("cache_age_ms", 0),
                "stale": cache.get("stale", False),
                "last_error": cache.get("last_error", ""),
                "last_duration_ms": cache.get("last_duration_ms", 0),
                "rows": len(cache.get("rows", [])),
                "domains": len(cache.get("domains", [])),
                "last_total": cache.get("last_total", 0),
            },
            "active_discovery_job": active_job,
            "transport": {
                "api_base_hint": _infer_ingress_api_base(),
                "request_path": _as_str(request.path, ""),
                "script_root": _as_str(request.script_root, ""),
            },
            "service_cache": {
                "cache_age_ms": _service_cache_age_ms(),
                "last_error": _as_str(_SERVICE_CACHE.get("last_error"), ""),
            },
        }
    )


@app.post("/api/discovery/jobs/start")
def api_discovery_job_start() -> Any:
    payload = request.get_json(silent=True) or {}
    force = _as_bool(payload.get("force"), False)
    job = _start_discovery_job(force=force)
    cache = _discovery_cache_snapshot()
    return jsonify(
        {
            "ok": True,
            "job": job,
            "cache": {
                "entities": len(cache.get("rows", [])),
                "domains": len(cache.get("domains", [])),
                "cache_age_ms": cache.get("cache_age_ms", 0),
                "stale": cache.get("stale", False),
                "last_error": cache.get("last_error", ""),
                "last_duration_ms": cache.get("last_duration_ms", 0),
            },
        }
    )


@app.get("/api/discovery/jobs/<job_id>")
def api_discovery_job_status(job_id: str) -> Any:
    job = _get_discovery_job(job_id)
    if not job:
        return jsonify({"ok": False, "error": f"job '{job_id}' not found"}), 404
    cache = _discovery_cache_snapshot()
    return jsonify(
        {
            "ok": True,
            "job": job,
            "cache": {
                "entities": len(cache.get("rows", [])),
                "domains": len(cache.get("domains", [])),
                "cache_age_ms": cache.get("cache_age_ms", 0),
                "stale": cache.get("stale", False),
                "last_error": cache.get("last_error", ""),
                "last_duration_ms": cache.get("last_duration_ms", 0),
            },
        }
    )


@app.post("/api/discovery/jobs/<job_id>/cancel")
def api_discovery_job_cancel(job_id: str) -> Any:
    job = _cancel_discovery_job(job_id)
    if not job:
        return jsonify({"ok": False, "error": f"job '{job_id}' not found"}), 404
    return jsonify({"ok": True, "job": job})


@app.get("/api/discovery/entities")
def api_discovery_entities() -> Any:
    query_started = _now()
    job_id = _as_str(request.args.get("job_id"), "").strip()
    domain = _as_str(request.args.get("domain"), "").strip().lower()
    query = _as_str(request.args.get("q"), "").strip().lower()
    sort_key = _as_str(request.args.get("sort"), "entity_id").strip().lower()
    only_mappable = _as_bool(request.args.get("only_mappable"), False)
    fields_mode = _as_str(request.args.get("fields"), "full").strip().lower()
    page = _as_int(request.args.get("page"), 1, 1, None)
    page_size = _as_int(request.args.get("page_size"), DEFAULT_PAGE_SIZE, 10, MAX_PAGE_SIZE)

    cache = _discovery_cache_snapshot()
    rows = list(cache.get("rows", []))
    job = _get_discovery_job(job_id) if job_id else (_get_discovery_job(_DISCOVERY_ACTIVE_JOB_ID) if _DISCOVERY_ACTIVE_JOB_ID else None)

    if domain:
        rows = [r for r in rows if r.get("domain") == domain]
    if query:
        rows = [
            r
            for r in rows
            if query in _as_str(r.get("entity_id")).lower()
            or query in _as_str(r.get("friendly_name")).lower()
            or query in _as_str(r.get("state")).lower()
        ]
    if only_mappable:
        rows = [r for r in rows if r.get("mappable", False)]

    if sort_key == "friendly_name":
        rows.sort(key=lambda r: (_as_str(r.get("friendly_name")).lower(), _as_str(r.get("entity_id")).lower()))
    elif sort_key == "domain":
        rows.sort(key=lambda r: (_as_str(r.get("domain")).lower(), _as_str(r.get("entity_id")).lower()))
    elif sort_key == "state":
        rows.sort(key=lambda r: (_as_str(r.get("state")).lower(), _as_str(r.get("entity_id")).lower()))
    else:
        rows.sort(key=lambda r: _as_str(r.get("entity_id")).lower())

    total = len(rows)
    pages = max((total + page_size - 1) // page_size, 1)
    if page > pages:
        page = pages
    start = (page - 1) * page_size
    end = start + page_size
    page_rows = rows[start:end]
    if fields_mode == "minimal":
        page_rows = [
            {
                "entity_id": _as_str(r.get("entity_id")),
                "domain": _as_str(r.get("domain")),
                "friendly_name": _as_str(r.get("friendly_name")),
                "state": _as_str(r.get("state")),
                "unit": _as_str(r.get("unit")),
                "mappable": _as_bool(r.get("mappable"), False),
            }
            for r in page_rows
        ]
    query_time_ms = int((_now() - query_started) * 1000.0)
    return jsonify(
        {
            "ok": True,
            "count": len(page_rows),
            "total": total,
            "filtered_total": total,
            "returned": len(page_rows),
            "page": page,
            "page_size": page_size,
            "pages": pages,
            "sort": sort_key,
            "fields": fields_mode,
            "query_time_ms": query_time_ms,
            "entities": page_rows,
            "cache_age_ms": cache.get("cache_age_ms", 0),
            "fetched_at": cache.get("fetched_at", 0),
            "stale": cache.get("stale", False),
            "last_error": cache.get("last_error", ""),
            "last_duration_ms": cache.get("last_duration_ms", 0),
            "job": job,
        }
    )


@app.get("/api/discovery/domains")
def api_discovery_domains() -> Any:
    job_id = _as_str(request.args.get("job_id"), "").strip()
    cache = _discovery_cache_snapshot()
    job = _get_discovery_job(job_id) if job_id else (_get_discovery_job(_DISCOVERY_ACTIVE_JOB_ID) if _DISCOVERY_ACTIVE_JOB_ID else None)
    return jsonify(
        {
            "ok": True,
            "domains": cache.get("domains", []),
            "cache_age_ms": cache.get("cache_age_ms", 0),
            "fetched_at": cache.get("fetched_at", 0),
            "stale": cache.get("stale", False),
            "last_error": cache.get("last_error", ""),
            "last_duration_ms": cache.get("last_duration_ms", 0),
            "job": job,
        }
    )


@app.post("/api/discovery/refresh")
def api_discovery_refresh() -> Any:
    job = _start_discovery_job(force=True)
    cache = _discovery_cache_snapshot()
    return jsonify(
        {
            "ok": True,
            "job": job,
            "count": len(cache.get("rows", [])),
            "domains": cache.get("domains", []),
            "cache_age_ms": cache.get("cache_age_ms", 0),
            "fetched_at": cache.get("fetched_at", 0),
            "stale": cache.get("stale", False),
            "last_error": cache.get("last_error", ""),
            "last_duration_ms": cache.get("last_duration_ms", 0),
        }
    )


@app.get("/api/profile/list")
def api_profile_list() -> Any:
    # Backward-compatible endpoint: returns workspace names when present,
    # then legacy profiles for users still on schema 1 payloads.
    workspaces = _list_workspaces()
    legacy = _list_profiles()
    out = sorted(set(workspaces + legacy))
    return jsonify({"ok": True, "profiles": out, "workspaces": workspaces, "legacy_profiles": legacy})


@app.post("/api/profile/save")
def api_profile_save() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, _ = _workspace_or_profile_from_payload(payload)
    name = _safe_profile_name(payload.get("name") or workspace.get("workspace_name") or profile.get("profile_name") or "default")
    validation = _validate_profile(profile)
    saved = _save_workspace(name, workspace)
    return jsonify(
        {
            "ok": True,
            "profile_name": saved,
            "workspace_name": saved,
            "validation": {"ok": validation["ok"], "errors": validation["errors"], "warnings": validation["warnings"]},
        }
    )


@app.get("/api/profile/load")
def api_profile_load() -> Any:
    name = _safe_profile_name(request.args.get("name"), "default")
    try:
        workspace = _load_workspace(name)
    except Exception:
        try:
            profile = _load_profile(name)
            workspace = _normalize_workspace(profile)
        except Exception as err:
            return jsonify({"ok": False, "error": str(err)}), 404
    profile, idx = _workspace_active_profile(workspace, workspace.get("active_device_index", 0))
    return jsonify({"ok": True, "workspace": workspace, "profile": profile, "active_device_index": idx})


@app.post("/api/profile/delete")
def api_profile_delete() -> Any:
    payload = request.get_json(silent=True) or {}
    name = _safe_profile_name(payload.get("name"), "")
    if not name:
        return jsonify({"ok": False, "error": "name is required"}), 400
    ws_path = _workspace_file(name)
    pf_path = _profile_file(name)
    if ws_path.exists():
        ws_path.unlink()
    if pf_path.exists():
        pf_path.unlink()
    return jsonify({"ok": True})


@app.post("/api/profile/rename")
def api_profile_rename() -> Any:
    payload = request.get_json(silent=True) or {}
    old_name = _safe_profile_name(payload.get("old_name"), "")
    new_name = _safe_profile_name(payload.get("new_name"), "")
    if not old_name or not new_name:
        return jsonify({"ok": False, "error": "old_name and new_name are required"}), 400
    old_ws_path = _workspace_file(old_name)
    old_profile_path = _profile_file(old_name)
    if old_ws_path.exists():
        new_ws_path = _workspace_file(new_name)
        if new_ws_path.exists() and new_ws_path != old_ws_path:
            return jsonify({"ok": False, "error": f"workspace '{new_name}' already exists"}), 409
        old_ws_path.rename(new_ws_path)
        ws = _load_workspace(new_name)
        ws["workspace_name"] = new_name
        _save_workspace(new_name, ws)
        return jsonify({"ok": True, "profile_name": new_name, "workspace_name": new_name})

    if old_profile_path.exists():
        new_profile_path = _profile_file(new_name)
        if new_profile_path.exists() and new_profile_path != old_profile_path:
            return jsonify({"ok": False, "error": f"profile '{new_name}' already exists"}), 409
        old_profile_path.rename(new_profile_path)
        profile = _load_profile(new_name)
        profile["profile_name"] = new_name
        _save_profile(new_name, profile)
        return jsonify({"ok": True, "profile_name": new_name, "workspace_name": new_name})
    return jsonify({"ok": False, "error": f"profile/workspace '{old_name}' not found"}), 404


@app.post("/api/profile/validate")
def api_profile_validate() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, active_idx = _workspace_or_profile_from_payload(payload)
    result = _validate_profile(profile)
    per_device: List[Dict[str, Any]] = []
    all_errors: List[str] = []
    all_warnings: List[str] = []
    for idx, device_profile in enumerate(workspace.get("devices", [])):
        v = _validate_profile(device_profile)
        slug = _managed_device_slug(device_profile)
        per_device.append(
            {
                "index": idx,
                "device_slug": slug,
                "device_name": _as_str(device_profile.get("device", {}).get("name")),
                "ok": v["ok"],
                "errors": v["errors"],
                "warnings": v["warnings"],
            }
        )
        all_errors.extend([f"[{slug}] {x}" for x in v["errors"]])
        all_warnings.extend([f"[{slug}] {x}" for x in v["warnings"]])
    layout_validation = _validate_layout_pages(workspace.get("layout_pages", {}))
    if not layout_validation.get("ok"):
        all_errors.extend([f"[layout] {x}" for x in layout_validation.get("errors", [])])
    if layout_validation.get("warnings"):
        all_warnings.extend([f"[layout] {x}" for x in layout_validation.get("warnings", [])])
    return jsonify(
        {
            "ok": len(all_errors) == 0,
            "errors": all_errors,
            "warnings": all_warnings,
            "profile": result["profile"],
            "workspace": workspace,
            "active_device_index": active_idx,
            "per_device": per_device,
            "layout_validation": layout_validation,
        }
    )


@app.get("/api/workspace/list")
def api_workspace_list() -> Any:
    return jsonify({"ok": True, "workspaces": _list_workspaces()})


@app.post("/api/workspace/save")
def api_workspace_save() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace = payload.get("workspace") if isinstance(payload.get("workspace"), dict) else payload
    ws = _normalize_workspace(workspace)
    name = _safe_profile_name(payload.get("name") or ws.get("workspace_name") or "default")
    saved = _save_workspace(name, ws)
    return jsonify({"ok": True, "workspace_name": saved})


@app.get("/api/workspace/load")
def api_workspace_load() -> Any:
    name = _safe_profile_name(request.args.get("name"), "default")
    try:
        workspace = _load_workspace(name)
    except Exception as err:
        return jsonify({"ok": False, "error": str(err)}), 404
    profile, idx = _workspace_active_profile(workspace, workspace.get("active_device_index", 0))
    return jsonify({"ok": True, "workspace": workspace, "profile": profile, "active_device_index": idx})


@app.post("/api/mapping/suggest")
def api_mapping_suggest() -> Any:
    payload = request.get_json(silent=True) or {}
    key = _as_str(payload.get("key"), "")
    query = _as_str(payload.get("q"), "")
    limit = _as_int(payload.get("limit"), 12, 1, 50)
    suggestions = _mapping_suggestions(key, query, limit=limit)
    return jsonify({"ok": True, "key": key, "count": len(suggestions), "suggestions": suggestions})


@app.get("/api/meta/templates")
def api_meta_templates() -> Any:
    return jsonify({"ok": True, "templates": _default_template_catalog()})


@app.get("/api/dashboard/summary")
def api_dashboard_summary() -> Any:
    try:
        health = api_health().get_json()  # type: ignore[union-attr]
    except Exception:
        health = {"ok": False, "ha_connected": False}
    runtime = _runtime_state_snapshot()
    workspace_name = _safe_profile_name(request.args.get("workspace"), "default")
    ws = _load_workspace_or_default(workspace_name)
    profile, idx = _workspace_active_profile(ws, ws.get("active_device_index", 0))
    validation = _validate_profile(profile)
    caps = _resolve_firmware_capabilities(
        device_slug=_managed_device_slug(profile),
        settings=profile.get("settings", {}) if isinstance(profile.get("settings"), dict) else {},
        native_firmware_entity=_as_str(profile.get("settings", {}).get("ha_native_firmware_entity"), ""),
        app_version_entity=_as_str(profile.get("settings", {}).get("ha_app_version_entity"), ""),
        target_version=_as_str(profile.get("settings", {}).get("app_release_version"), DEFAULT_APP_RELEASE_VERSION),
    )
    return jsonify(
        {
            "ok": True,
            "workspace_name": ws.get("workspace_name", workspace_name),
            "active_device_index": idx,
            "device_slug": _managed_device_slug(profile),
            "landing_state": ws.get("landing_state", _default_landing_state()),
            "health": health,
            "runtime_state": runtime,
            "validation": {"ok": validation["ok"], "errors": validation["errors"], "warnings": validation["warnings"]},
            "firmware_capabilities": caps,
            "camera_autodetect": profile.get("camera_autodetect", _default_camera_autodetect_state()),
        }
    )


@app.post("/api/dashboard/action")
def api_dashboard_action() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    action = _as_str(payload.get("action"), "").strip().lower()
    if not action:
        return jsonify({"ok": False, "error": "action is required"}), 400
    workspace.setdefault("landing_state", _default_landing_state())
    landing = workspace["landing_state"]
    landing["last_card"] = action
    landing["last_action"] = action
    landing["last_error"] = ""
    landing["updated_at"] = int(_now())
    step_map = {
        "connect_device": 0,
        "map_entities": 2,
        "theme": 3,
        "layout": 4,
        "deploy": 5,
        "recover": 5,
    }
    if action in step_map:
        landing["onboarding_step"] = step_map[action]
        workspace.setdefault("mode_ui", _default_mode_ui())
        workspace["mode_ui"]["guided_step"] = step_map[action]
    workspace = _workspace_with_profile(workspace, profile, idx)
    workspace, saved = _maybe_persist_workspace(payload, workspace)
    return jsonify({"ok": True, "action": action, "workspace": workspace, "saved_workspace": saved})


@app.get("/api/entities/collections")
def api_entities_collections() -> Any:
    workspace_name = _safe_profile_name(request.args.get("workspace"), "default")
    ws = _load_workspace_or_default(workspace_name)
    profile, idx = _workspace_active_profile(ws, ws.get("active_device_index", 0), _as_str(request.args.get("device_slug"), ""))
    collections = profile.get("entity_collections", {}) if isinstance(profile.get("entity_collections"), dict) else {}
    return jsonify(
        {
            "ok": True,
            "workspace_name": ws.get("workspace_name", workspace_name),
            "active_device_index": idx,
            "device_slug": _managed_device_slug(profile),
            "collections": collections,
            "limits": collections.get("limits", {}),
            "contracts": {
                "entity_collection_limits": ENTITY_COLLECTION_LIMITS,
            },
        }
    )


@app.post("/api/entities/add")
def api_entities_add() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    collection = _as_str(payload.get("collection"), "").strip().lower()
    if collection not in ENTITY_COLLECTION_LIMITS:
        return jsonify({"ok": False, "error": f"collection must be one of: {', '.join(sorted(ENTITY_COLLECTION_LIMITS.keys()))}"}), 400
    item = payload.get("item") if isinstance(payload.get("item"), dict) else {}
    profile["entity_collections"] = _normalize_profile_collections(profile)
    coll = profile["entity_collections"].get(collection, [])
    hard_max = ENTITY_COLLECTION_LIMITS.get(collection, {}).get("hard_max", 64)
    if len(coll) >= hard_max:
        return jsonify({"ok": False, "error": f"{collection} reached hard limit {hard_max}"}), 400
    next_idx = len(coll) + 1
    coll.append(
        {
            "id": _slugify(item.get("id"), f"{collection[:-1]}_{next_idx}"),
            "name": _as_str(item.get("name"), f"{collection[:-1].title()} {next_idx}"),
            "entity_id": _as_str(item.get("entity_id") or item.get("entity"), ""),
            "role": _as_str(item.get("role"), ""),
            "enabled": _as_bool(item.get("enabled"), True),
        }
    )
    profile["entity_collections"][collection] = coll
    _sync_slots_from_collections(profile)
    workspace = _workspace_with_profile(workspace, profile, idx)
    workspace, saved = _maybe_persist_workspace(payload, workspace)
    return jsonify({"ok": True, "workspace": workspace, "profile": profile, "active_device_index": idx, "saved_workspace": saved})


@app.post("/api/entities/update")
def api_entities_update() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    collection = _as_str(payload.get("collection"), "").strip().lower()
    item_id = _slugify(payload.get("item_id"), "")
    patch = payload.get("patch") if isinstance(payload.get("patch"), dict) else {}
    if collection not in ENTITY_COLLECTION_LIMITS or not item_id:
        return jsonify({"ok": False, "error": "collection and item_id are required"}), 400
    profile["entity_collections"] = _normalize_profile_collections(profile)
    coll = profile["entity_collections"].get(collection, [])
    updated = False
    for item in coll:
        if _slugify(item.get("id"), "") != item_id:
            continue
        if "name" in patch:
            item["name"] = _as_str(patch.get("name"), item.get("name"))
        if "entity_id" in patch or "entity" in patch:
            item["entity_id"] = _as_str(patch.get("entity_id") or patch.get("entity"), item.get("entity_id"))
        if "role" in patch:
            item["role"] = _as_str(patch.get("role"), item.get("role"))
        if "enabled" in patch:
            item["enabled"] = _as_bool(patch.get("enabled"), True)
        updated = True
        break
    if not updated:
        return jsonify({"ok": False, "error": f"item '{item_id}' not found in {collection}"}), 404
    _sync_slots_from_collections(profile)
    workspace = _workspace_with_profile(workspace, profile, idx)
    workspace, saved = _maybe_persist_workspace(payload, workspace)
    return jsonify({"ok": True, "workspace": workspace, "profile": profile, "active_device_index": idx, "saved_workspace": saved})


@app.post("/api/entities/remove")
def api_entities_remove() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    collection = _as_str(payload.get("collection"), "").strip().lower()
    item_id = _slugify(payload.get("item_id"), "")
    if collection not in ENTITY_COLLECTION_LIMITS or not item_id:
        return jsonify({"ok": False, "error": "collection and item_id are required"}), 400
    profile["entity_collections"] = _normalize_profile_collections(profile)
    coll = profile["entity_collections"].get(collection, [])
    before = len(coll)
    coll = [x for x in coll if _slugify(x.get("id"), "") != item_id]
    if len(coll) == before:
        return jsonify({"ok": False, "error": f"item '{item_id}' not found in {collection}"}), 404
    profile["entity_collections"][collection] = coll
    _sync_slots_from_collections(profile)
    workspace = _workspace_with_profile(workspace, profile, idx)
    workspace, saved = _maybe_persist_workspace(payload, workspace)
    return jsonify({"ok": True, "workspace": workspace, "profile": profile, "active_device_index": idx, "saved_workspace": saved})


@app.post("/api/entities/reorder")
def api_entities_reorder() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    collection = _as_str(payload.get("collection"), "").strip().lower()
    from_index = _as_int(payload.get("from_index"), -1, -1, None)
    to_index = _as_int(payload.get("to_index"), -1, -1, None)
    if collection not in ENTITY_COLLECTION_LIMITS:
        return jsonify({"ok": False, "error": f"collection must be one of: {', '.join(sorted(ENTITY_COLLECTION_LIMITS.keys()))}"}), 400
    profile["entity_collections"] = _normalize_profile_collections(profile)
    coll = profile["entity_collections"].get(collection, [])
    if from_index < 0 or from_index >= len(coll) or to_index < 0 or to_index >= len(coll):
        return jsonify({"ok": False, "error": "from_index/to_index out of range"}), 400
    item = coll.pop(from_index)
    coll.insert(to_index, item)
    profile["entity_collections"][collection] = coll
    _sync_slots_from_collections(profile)
    workspace = _workspace_with_profile(workspace, profile, idx)
    workspace, saved = _maybe_persist_workspace(payload, workspace)
    return jsonify({"ok": True, "workspace": workspace, "profile": profile, "active_device_index": idx, "saved_workspace": saved})


def _camera_autodetect_candidates(limit: int = 12) -> List[Dict[str, Any]]:
    snapshot = _discovery_cache_snapshot()
    rows = snapshot.get("rows", []) if isinstance(snapshot.get("rows"), list) else []
    scored: List[Tuple[int, Dict[str, Any]]] = []
    for row in rows:
        if _as_str(row.get("domain"), "").lower() != "camera":
            continue
        entity_id = _as_str(row.get("entity_id"), "")
        friendly = _as_str(row.get("friendly_name"), entity_id)
        state = _as_str(row.get("state"), "")
        lower = f"{entity_id} {friendly}".lower()
        score = 20
        if any(x in lower for x in ["front", "door", "porch", "outdoor", "driveway", "backyard", "garage"]):
            score += 30
        if any(x in lower for x in ["snapshot", "still", "motion"]):
            score += 15
        if state.lower() in {"unavailable", "unknown"}:
            score -= 20
        scored.append(
            (
                score,
                {
                    "entity_id": entity_id,
                    "friendly_name": friendly,
                    "state": state,
                    "score": score,
                },
            )
        )
    scored.sort(key=lambda x: (-x[0], _as_str(x[1].get("entity_id"), "")))
    return [item for _, item in scored[: max(1, min(limit, 64))]]


@app.post("/api/cameras/autodetect")
def api_cameras_autodetect() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    limit = _as_int(payload.get("limit"), 12, 1, 64)
    detected = _camera_autodetect_candidates(limit=limit)
    profile.setdefault("camera_autodetect", _default_camera_autodetect_state())
    cad = _deep_merge(_default_camera_autodetect_state(), profile.get("camera_autodetect", {}))
    cad["last_scan_at"] = int(_now())
    cad["detected"] = detected
    cad["last_error"] = ""
    profile["camera_autodetect"] = cad
    workspace["camera_autodetect"] = cad
    workspace = _workspace_with_profile(workspace, profile, idx)
    workspace, saved = _maybe_persist_workspace(payload, workspace)
    return jsonify(
        {
            "ok": True,
            "workspace": workspace,
            "profile": profile,
            "active_device_index": idx,
            "saved_workspace": saved,
            "camera_autodetect": cad,
            "detected_count": len(detected),
        }
    )


@app.post("/api/cameras/accept_detected")
def api_cameras_accept_detected() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    requested = payload.get("entity_ids")
    requested_set: set[str] = set()
    if isinstance(requested, list):
        for item in requested:
            entity_id = _as_str(item, "").strip()
            if entity_id:
                requested_set.add(entity_id)
    profile["entity_collections"] = _normalize_profile_collections(profile)
    cameras = profile["entity_collections"].get("cameras", [])
    cad = _deep_merge(_default_camera_autodetect_state(), profile.get("camera_autodetect", {}))
    detected = cad.get("detected", []) if isinstance(cad.get("detected"), list) else []
    accepted = cad.get("accepted", []) if isinstance(cad.get("accepted"), list) else []
    accepted_set = set(_as_str(x, "") for x in accepted)
    to_add = []
    for row in detected:
        if not isinstance(row, dict):
            continue
        entity_id = _as_str(row.get("entity_id"), "").strip()
        if not entity_id:
            continue
        if requested_set and entity_id not in requested_set:
            continue
        to_add.append(row)
    for row in to_add:
        entity_id = _as_str(row.get("entity_id"), "")
        if any(_as_str(item.get("entity_id"), "") == entity_id for item in cameras):
            accepted_set.add(entity_id)
            continue
        idx_new = len(cameras) + 1
        cameras.append(
            {
                "id": _slugify(f"camera_{idx_new}_{entity_id}", f"camera_{idx_new}"),
                "name": _as_str(row.get("friendly_name"), f"Camera {idx_new}"),
                "entity_id": entity_id,
                "role": "camera_slot",
                "enabled": True,
            }
        )
        accepted_set.add(entity_id)
    profile["entity_collections"]["cameras"] = cameras
    _sync_slots_from_collections(profile)
    cad["accepted"] = sorted(list(accepted_set))
    cad["updated_at"] = int(_now())
    profile["camera_autodetect"] = cad
    workspace["camera_autodetect"] = cad
    workspace = _workspace_with_profile(workspace, profile, idx)
    workspace, saved = _maybe_persist_workspace(payload, workspace)
    return jsonify({"ok": True, "workspace": workspace, "profile": profile, "active_device_index": idx, "saved_workspace": saved, "camera_autodetect": cad})


@app.post("/api/cameras/ignore_detected")
def api_cameras_ignore_detected() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    requested = payload.get("entity_ids")
    requested_set: set[str] = set()
    if isinstance(requested, list):
        for item in requested:
            entity_id = _as_str(item, "").strip()
            if entity_id:
                requested_set.add(entity_id)
    cad = _deep_merge(_default_camera_autodetect_state(), profile.get("camera_autodetect", {}))
    ignored = cad.get("ignored", []) if isinstance(cad.get("ignored"), list) else []
    ignored_set = set(_as_str(x, "") for x in ignored)
    detected = cad.get("detected", []) if isinstance(cad.get("detected"), list) else []
    if not requested_set:
        for row in detected:
            if isinstance(row, dict):
                entity_id = _as_str(row.get("entity_id"), "").strip()
                if entity_id:
                    ignored_set.add(entity_id)
    else:
        ignored_set.update(requested_set)
    cad["ignored"] = sorted(list(ignored_set))
    cad["updated_at"] = int(_now())
    profile["camera_autodetect"] = cad
    workspace["camera_autodetect"] = cad
    workspace = _workspace_with_profile(workspace, profile, idx)
    workspace, saved = _maybe_persist_workspace(payload, workspace)
    return jsonify({"ok": True, "workspace": workspace, "profile": profile, "active_device_index": idx, "saved_workspace": saved, "camera_autodetect": cad})


@app.get("/api/layout/load")
def api_layout_load() -> Any:
    name = _safe_profile_name(request.args.get("name"), "")
    page = _as_str(request.args.get("page"), "").strip().lower()
    workspace: Dict[str, Any]
    if name:
        try:
            workspace = _load_workspace(name)
        except Exception:
            workspace = _default_workspace()
    else:
        workspace = _default_workspace()
    pages = workspace.get("layout_pages", {}) if isinstance(workspace.get("layout_pages"), dict) else _default_layout_pages()
    payload_pages = {page: pages.get(page, _default_layout_pages().get(page, {}))} if page else pages
    validation = _validate_layout_pages(payload_pages)
    return jsonify({"ok": True, "layout_pages": payload_pages, "validation": validation, "workspace_name": workspace.get("workspace_name", "default")})


@app.post("/api/layout/validate")
def api_layout_validate() -> Any:
    payload = request.get_json(silent=True) or {}
    pages = payload.get("layout_pages") if isinstance(payload.get("layout_pages"), dict) else {}
    validation = _validate_layout_pages(pages)
    return jsonify({"ok": validation.get("ok", False), "validation": validation, "layout_pages": validation.get("pages", {})})


@app.post("/api/layout/save")
def api_layout_save() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    incoming_pages = payload.get("layout_pages") if isinstance(payload.get("layout_pages"), dict) else {}
    candidate_pages = _deep_merge(_default_layout_pages(), incoming_pages)
    validation = _validate_layout_pages(candidate_pages)
    if not validation.get("ok"):
        return jsonify({"ok": False, "error": "layout_validation_failed", "validation": validation}), 400
    workspace["layout_pages"] = validation.get("pages", {})
    profile["layout_pages"] = validation.get("pages", {})
    workspace = _workspace_with_profile(workspace, profile, idx)
    workspace, saved = _maybe_persist_workspace(payload, workspace)
    return jsonify({"ok": True, "workspace": workspace, "profile": profile, "active_device_index": idx, "saved_workspace": saved, "validation": validation})


@app.post("/api/layout/reset_page")
def api_layout_reset_page() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    page = _as_str(payload.get("page"), "").strip().lower()
    defaults = _default_layout_pages()
    if page and page not in defaults:
        return jsonify({"ok": False, "error": f"unknown page '{page}'"}), 400
    if page:
        workspace.setdefault("layout_pages", {})
        workspace["layout_pages"][page] = defaults[page]
        profile.setdefault("layout_pages", {})
        profile["layout_pages"][page] = defaults[page]
    else:
        workspace["layout_pages"] = defaults
        profile["layout_pages"] = defaults
    workspace = _workspace_with_profile(workspace, profile, idx)
    workspace, saved = _maybe_persist_workspace(payload, workspace)
    return jsonify({"ok": True, "workspace": workspace, "profile": profile, "active_device_index": idx, "saved_workspace": saved})


def _theme_tokens_from_payload(payload: Dict[str, Any], palette_fallback: str = "") -> Tuple[Dict[str, str], str, Dict[str, str]]:
    palette_id = _as_str(payload.get("palette_id"), "").strip().lower() or palette_fallback
    tokens: Dict[str, str] = {}
    for p_item in _default_theme_palettes():
        if _as_str(p_item.get("id"), "").lower() == palette_id:
            tokens = dict(p_item.get("tokens", {}))
            break
    defaults = _default_substitutions()
    if not tokens:
        tokens = {k: defaults[k] for k in defaults.keys() if k.startswith("theme_token_")}
    custom_tokens = payload.get("tokens") if isinstance(payload.get("tokens"), dict) else {}
    for k, v in custom_tokens.items():
        if k.startswith("theme_token_"):
            tokens[k] = _normalize_color(v, tokens.get(k, "0x000000"))
    return tokens, palette_id, custom_tokens


def _apply_theme_to_workspace(
    workspace: Dict[str, Any],
    profile: Dict[str, Any],
    idx: int,
    tokens: Dict[str, str],
    palette_id: str,
    custom_tokens: Dict[str, str],
    writer: str,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    for k, v in tokens.items():
        profile.setdefault("theme", {})
        profile["theme"][k] = v
    ratio = _contrast_ratio(tokens.get("theme_token_text_primary", "0xFFFFFF"), tokens.get("theme_token_screen_bg", "0x000000"))
    profile.setdefault("theme_studio", {})
    profile["theme_studio"]["active_palette"] = palette_id or _as_str(profile.get("theme_studio", {}).get("active_palette"), "ocean_dark")
    profile["theme_studio"]["custom_tokens"] = custom_tokens
    profile["theme_studio"]["last_contrast_ratio"] = ratio
    sync = _deep_merge(_default_theme_sync_state(), profile.get("theme_studio", {}).get("sync", {}))
    if writer == "device":
        sync["theme_revision_device"] = _as_int(sync.get("theme_revision_device"), 0, 0, None) + 1
        sync["device_snapshot"] = {k: v for k, v in tokens.items() if str(k).startswith("theme_token_")}
    else:
        sync["theme_revision_web"] = _as_int(sync.get("theme_revision_web"), 0, 0, None) + 1
    sync["theme_last_writer"] = writer
    sync["theme_conflict"] = _as_int(sync.get("theme_revision_web"), 0, 0, None) != _as_int(sync.get("theme_revision_device"), 0, 0, None)
    if sync["theme_conflict"]:
        sync["theme_last_conflict_at"] = int(_now())
    profile["theme_studio"]["sync"] = sync
    workspace.setdefault("theme_studio", {})
    workspace["theme_studio"] = _deep_merge(workspace.get("theme_studio", {}), profile.get("theme_studio", {}))
    workspace = _workspace_with_profile(workspace, profile, idx)
    meta = {
        "tokens": tokens,
        "contrast_ratio": ratio,
        "wcag_aa_normal": ratio >= 4.5,
        "wcag_aa_large": ratio >= 3.0,
        "theme_sync": sync,
    }
    return workspace, profile, meta


@app.get("/api/theme/palettes")
def api_theme_palettes() -> Any:
    return jsonify({"ok": True, "palettes": _default_theme_palettes()})


@app.get("/api/theme/state")
def api_theme_state() -> Any:
    workspace_name = _safe_profile_name(request.args.get("workspace"), "default")
    ws = _load_workspace_or_default(workspace_name)
    profile, idx = _workspace_active_profile(ws, ws.get("active_device_index", 0), _as_str(request.args.get("device_slug"), ""))
    sync = _deep_merge(_default_theme_sync_state(), profile.get("theme_studio", {}).get("sync", {}))
    return jsonify(
        {
            "ok": True,
            "workspace_name": ws.get("workspace_name", workspace_name),
            "active_device_index": idx,
            "device_slug": _managed_device_slug(profile),
            "theme": profile.get("theme", {}),
            "theme_studio": profile.get("theme_studio", {}),
            "theme_sync": sync,
        }
    )


@app.post("/api/theme/contrast_check")
def api_theme_contrast_check() -> Any:
    payload = request.get_json(silent=True) or {}
    fg = _as_str(payload.get("fg"), "0xFFFFFF")
    bg = _as_str(payload.get("bg"), "0x000000")
    ratio = _contrast_ratio(fg, bg)
    return jsonify({"ok": True, "ratio": ratio, "wcag_aa_normal": ratio >= 4.5, "wcag_aa_large": ratio >= 3.0})


@app.post("/api/theme/preview")
def api_theme_preview() -> Any:
    payload = request.get_json(silent=True) or {}
    tokens, _palette_id, _custom_tokens = _theme_tokens_from_payload(payload, "")
    ratio = _contrast_ratio(tokens.get("theme_token_text_primary", "0xFFFFFF"), tokens.get("theme_token_screen_bg", "0x000000"))
    return jsonify({"ok": True, "tokens": tokens, "contrast_ratio": ratio, "wcag_aa_normal": ratio >= 4.5, "wcag_aa_large": ratio >= 3.0})


@app.post("/api/theme/apply")
def api_theme_apply() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    tokens, palette_id, custom_tokens = _theme_tokens_from_payload(payload, _as_str(profile.get("theme_studio", {}).get("active_palette"), ""))
    workspace, profile, meta = _apply_theme_to_workspace(workspace, profile, idx, tokens, palette_id, custom_tokens, "web")
    workspace, saved = _maybe_persist_workspace(payload, workspace)
    return jsonify({"ok": True, "workspace": workspace, "profile": profile, "active_device_index": idx, "saved_workspace": saved, **meta})


@app.post("/api/theme/apply_web")
def api_theme_apply_web() -> Any:
    return api_theme_apply()


@app.post("/api/theme/apply_device_sync")
def api_theme_apply_device_sync() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    tokens, palette_id, custom_tokens = _theme_tokens_from_payload(payload, _as_str(profile.get("theme_studio", {}).get("active_palette"), ""))
    workspace, profile, meta = _apply_theme_to_workspace(workspace, profile, idx, tokens, palette_id, custom_tokens, "device")
    workspace, saved = _maybe_persist_workspace(payload, workspace)
    return jsonify({"ok": True, "workspace": workspace, "profile": profile, "active_device_index": idx, "saved_workspace": saved, **meta})


@app.post("/api/theme/resolve_conflict")
def api_theme_resolve_conflict() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    policy = _as_str(payload.get("policy"), "manual_merge").strip().lower()
    if policy not in {"prefer_web", "prefer_device", "manual_merge"}:
        return jsonify({"ok": False, "error": "policy must be prefer_web, prefer_device, or manual_merge"}), 400
    profile.setdefault("theme_studio", {})
    sync = _deep_merge(_default_theme_sync_state(), profile.get("theme_studio", {}).get("sync", {}))
    if policy == "prefer_device" and isinstance(sync.get("device_snapshot"), dict):
        for key, value in sync["device_snapshot"].items():
            if str(key).startswith("theme_token_"):
                profile.setdefault("theme", {})
                profile["theme"][key] = _normalize_color(value, _default_substitutions().get(key, "0x000000"))
    elif policy == "prefer_web":
        sync["device_snapshot"] = {k: v for k, v in profile.get("theme", {}).items() if str(k).startswith("theme_token_")}
    sync["theme_conflict_policy"] = policy
    sync["theme_conflict"] = False
    merged_rev = max(_as_int(sync.get("theme_revision_web"), 0, 0, None), _as_int(sync.get("theme_revision_device"), 0, 0, None))
    sync["theme_revision_web"] = merged_rev
    sync["theme_revision_device"] = merged_rev
    sync["theme_last_writer"] = "conflict_resolve"
    profile["theme_studio"]["sync"] = sync
    workspace.setdefault("theme_studio", {})
    workspace["theme_studio"] = _deep_merge(workspace.get("theme_studio", {}), profile.get("theme_studio", {}))
    workspace = _workspace_with_profile(workspace, profile, idx)
    workspace, saved = _maybe_persist_workspace(payload, workspace)
    return jsonify({"ok": True, "workspace": workspace, "profile": profile, "active_device_index": idx, "saved_workspace": saved, "theme_sync": sync})


@app.get("/api/update/latest")
def api_update_latest() -> Any:
    channel = _as_str(request.args.get("channel"), DEFAULT_RELEASE_CHANNEL).strip().lower() or DEFAULT_RELEASE_CHANNEL
    force = _as_bool(request.args.get("refresh"), False)
    try:
        release = _github_latest_release(channel=channel, force=force)
        return jsonify(
            {
                "ok": True,
                "channel": channel,
                "version": release.get("version", DEFAULT_APP_RELEASE_VERSION),
                "published_at": release.get("published_at", ""),
                "html_url": release.get("html_url", ""),
                "notes": release.get("notes", ""),
                "cache_age_ms": release.get("cache_age_ms", 0),
                "stale": release.get("stale", False),
                "last_error": release.get("last_error", ""),
                "repo_slug": release.get("repo_slug", _repo_slug_from_url(ADDON_GITHUB_REPO_URL)),
            }
        )
    except Exception as err:
        repo_slug = _repo_slug_from_url(ADDON_GITHUB_REPO_URL)
        return jsonify(
            {
                "ok": True,
                "channel": channel,
                "version": DEFAULT_APP_RELEASE_VERSION,
                "published_at": "",
                "html_url": f"https://github.com/{repo_slug}/releases/latest",
                "notes": "",
                "cache_age_ms": _release_cache_age_ms(),
                "stale": True,
                "last_error": str(err),
                "repo_slug": repo_slug,
            }
        )


@app.get("/api/firmware/status")
def api_firmware_status() -> Any:
    device_slug = _as_str(request.args.get("device_slug"), "").strip() or "lilygo-tdeck-plus"
    target_version = _as_str(request.args.get("target_version"), DEFAULT_APP_RELEASE_VERSION).strip() or DEFAULT_APP_RELEASE_VERSION
    native_override = _as_str(request.args.get("native_firmware_entity"), "").strip()
    app_ver_override = _as_str(request.args.get("app_version_entity"), "").strip()
    compile_override = _as_str(request.args.get("ha_esphome_compile_service"), "").strip()
    install_override = _as_str(request.args.get("ha_esphome_install_service"), "").strip()
    settings = {
        "ha_esphome_compile_service": compile_override,
        "ha_esphome_install_service": install_override,
    }
    default_native, default_app_ver = _resolve_firmware_entities(device_slug, settings)
    caps = _resolve_firmware_capabilities(
        device_slug=device_slug,
        settings=settings,
        native_firmware_entity=native_override or default_native,
        app_version_entity=app_ver_override or default_app_ver,
        target_version=target_version,
    )
    status = _firmware_status_for(
        device_slug=device_slug,
        target_version=target_version,
        native_firmware_entity=native_override or default_native,
        app_version_entity=app_ver_override or default_app_ver,
        capabilities=caps,
        selected_method=_as_str(caps.get("recommended_method"), ""),
    )
    return jsonify({"ok": True, **status})


@app.get("/api/firmware/capabilities")
def api_firmware_capabilities() -> Any:
    device_slug = _as_str(request.args.get("device_slug"), "").strip() or "lilygo-tdeck-plus"
    target_version = _as_str(request.args.get("target_version"), DEFAULT_APP_RELEASE_VERSION).strip() or DEFAULT_APP_RELEASE_VERSION
    native_override = _as_str(request.args.get("native_firmware_entity"), "").strip()
    app_ver_override = _as_str(request.args.get("app_version_entity"), "").strip()
    settings = {
        "ha_esphome_compile_service": _as_str(request.args.get("ha_esphome_compile_service"), "").strip(),
        "ha_esphome_install_service": _as_str(request.args.get("ha_esphome_install_service"), "").strip(),
    }
    caps = _resolve_firmware_capabilities(
        device_slug=device_slug,
        settings=settings,
        native_firmware_entity=native_override,
        app_version_entity=app_ver_override,
        target_version=target_version,
    )
    return jsonify({"ok": True, "capabilities": caps})


@app.post("/api/firmware/workflow")
def api_firmware_workflow() -> Any:
    payload = request.get_json(silent=True) or {}
    result, status_code = _execute_firmware_workflow(payload)
    return jsonify(result), status_code


@app.post("/api/firmware/update")
def api_firmware_update() -> Any:
    # Backward-compatible alias route.
    payload = request.get_json(silent=True) or {}
    if not _as_str(payload.get("mode"), "").strip():
        payload["mode"] = "install_only"
    result, status_code = _execute_firmware_workflow(payload)
    return jsonify(result), status_code


@app.get("/api/meta/contracts")
def api_meta_contracts() -> Any:
    return jsonify(
        {
            "ok": True,
            "contracts": _contracts(),
            "default_profile": _default_profile(),
            "default_workspace": _default_workspace(),
            "templates": _default_template_catalog(),
            "theme_palettes": _default_theme_palettes(),
            "layout_defaults": _default_layout_pages(),
            "update_defaults": {
                "channel": DEFAULT_RELEASE_CHANNEL,
                "version": DEFAULT_APP_RELEASE_VERSION,
                "git_ref": ADDON_GITHUB_REF,
                "repo_url": ADDON_GITHUB_REPO_URL,
            },
            "managed_files": {
                "root": str(MANAGED_ROOT),
                "backup_keep_count": BACKUP_KEEP_COUNT,
                "install_name": "tdeck-install.yaml",
                "overrides_name": "tdeck-overrides.yaml",
            },
            "schemas": {
                "profile_version": PROFILE_SCHEMA_VERSION,
                "workspace_version": WORKSPACE_SCHEMA_VERSION,
            },
        }
    )


@app.post("/api/generate/install")
def api_generate_install() -> Any:
    payload = request.get_json(silent=True) or {}
    try:
        substitutions, profile, git_ref, git_url = _resolve_generation_input(payload)
        workspace, _, _ = _workspace_or_profile_from_payload(payload)
        validation = _validate_profile(profile)
        include_generated = isinstance(payload.get("workspace"), dict) or isinstance(payload.get("profile"), dict)
        generated = {
            "entities": _build_generated_entities_yaml(profile),
            "theme": _build_generated_theme_yaml(profile),
            "layout": _build_generated_layout_yaml(profile, workspace),
            "page_home": _build_generated_page_yaml("home", workspace, profile),
            "page_lights": _build_generated_page_yaml("lights", workspace, profile),
            "page_weather": _build_generated_page_yaml("weather", workspace, profile),
            "page_climate": _build_generated_page_yaml("climate", workspace, profile),
        }
        return jsonify(
            {
                "ok": True,
                "yaml": _build_install_yaml(substitutions, git_ref, git_url, include_generated=include_generated),
                "generated": generated,
                "validation": {
                    "ok": validation["ok"],
                    "errors": validation["errors"],
                    "warnings": validation["warnings"],
                },
            }
        )
    except Exception as err:  # pragma: no cover
        return jsonify({"ok": False, "error": str(err)}), 400


@app.post("/api/generate/overrides")
def api_generate_overrides() -> Any:
    payload = request.get_json(silent=True) or {}
    try:
        substitutions, profile, _, _ = _resolve_generation_input(payload)
        validation = _validate_profile(profile)
        return jsonify(
            {
                "ok": True,
                "yaml": _build_overrides_yaml(substitutions),
                "validation": {
                    "ok": validation["ok"],
                    "errors": validation["errors"],
                    "warnings": validation["warnings"],
                },
            }
        )
    except Exception as err:  # pragma: no cover
        return jsonify({"ok": False, "error": str(err)}), 400


@app.post("/api/generate/ha_update_package")
def api_generate_ha_update_package() -> Any:
    payload = request.get_json(silent=True) or {}
    profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else _default_profile()
    profile = _normalize_profile(profile)
    channel = _as_str(payload.get("channel"), _as_str(profile.get("settings", {}).get("app_release_channel"), DEFAULT_RELEASE_CHANNEL))
    installed_entity_override = _as_str(payload.get("ha_installed_version_entity"), "")
    native_firmware_entity_override = _as_str(payload.get("ha_native_firmware_entity"), "")
    try:
        latest = _github_latest_release(channel=channel, force=False)
    except Exception:
        latest = {
            "channel": channel,
            "version": DEFAULT_APP_RELEASE_VERSION,
            "published_at": "",
            "html_url": f"https://github.com/{_repo_slug_from_url(_as_str(profile.get('device', {}).get('git_url'), ADDON_GITHUB_REPO_URL))}/releases/latest",
            "notes": "",
            "cache_age_ms": 0,
            "stale": True,
            "last_error": "latest_release_unavailable",
        }
    validation = _validate_profile(profile)
    return jsonify(
        {
            "ok": True,
            "yaml": _build_ha_update_package(
                profile,
                latest,
                installed_version_entity_override=installed_entity_override,
                native_firmware_entity_override=native_firmware_entity_override,
            ),
            "latest": latest,
            "validation": {
                "ok": validation["ok"],
                "errors": validation["errors"],
                "warnings": validation["warnings"],
            },
        }
    )


@app.post("/api/apply/preview")
def api_apply_preview() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, _ = _workspace_or_profile_from_payload(payload)
    deployment = workspace.get("deployment", {}) if isinstance(workspace.get("deployment"), dict) else {}
    git_ref = _as_str(payload.get("git_ref"), _as_str(deployment.get("git_ref"), _as_str(profile.get("device", {}).get("git_ref"), ADDON_GITHUB_REF)))
    git_url = _as_str(payload.get("git_url"), _as_str(deployment.get("git_url"), _as_str(profile.get("device", {}).get("git_url"), ADDON_GITHUB_REPO_URL)))
    validation = _validate_profile(profile)
    preview = _preview_managed_apply(workspace, profile, git_ref or ADDON_GITHUB_REF, git_url or ADDON_GITHUB_REPO_URL)
    return jsonify(
        {
            "ok": True,
            "preview": preview,
            "validation": {
                "ok": validation["ok"],
                "errors": validation["errors"],
                "warnings": validation["warnings"],
            },
        }
    )


@app.post("/api/apply/commit")
def api_apply_commit() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, _ = _workspace_or_profile_from_payload(payload)
    deployment = workspace.get("deployment", {}) if isinstance(workspace.get("deployment"), dict) else {}
    git_ref = _as_str(payload.get("git_ref"), _as_str(deployment.get("git_ref"), _as_str(profile.get("device", {}).get("git_ref"), ADDON_GITHUB_REF)))
    git_url = _as_str(payload.get("git_url"), _as_str(deployment.get("git_url"), _as_str(profile.get("device", {}).get("git_url"), ADDON_GITHUB_REPO_URL)))
    validation = _validate_profile(profile)
    if not validation["ok"] and _as_bool(payload.get("allow_with_errors"), False) is False:
        return jsonify({"ok": False, "error": "validation_failed", "validation": {"errors": validation["errors"], "warnings": validation["warnings"]}}), 400

    preview = _preview_managed_apply(workspace, profile, git_ref or ADDON_GITHUB_REF, git_url or ADDON_GITHUB_REPO_URL)
    device_slug = preview["device_slug"]
    lock = _get_apply_lock(device_slug)
    if not lock.acquire(blocking=False):
        return jsonify({"ok": False, "error": "apply_in_progress", "device_slug": device_slug}), 409
    try:
        backup = _backup_files(
            device_slug,
            preview,
            profile,
            workspace,
            reason="apply_commit",
            context={"source": "api_apply_commit"},
        )
        install_path = Path(preview["install"]["path"])
        overrides_path = Path(preview["overrides"]["path"])
        generated_entities_path_raw = _as_str(preview.get("generated", {}).get("entities", {}).get("path", ""))
        generated_theme_path_raw = _as_str(preview.get("generated", {}).get("theme", {}).get("path", ""))
        generated_layout_path_raw = _as_str(preview.get("generated", {}).get("layout", {}).get("path", ""))
        generated_page_home_path_raw = _as_str(preview.get("generated", {}).get("page_home", {}).get("path", ""))
        generated_page_lights_path_raw = _as_str(preview.get("generated", {}).get("page_lights", {}).get("path", ""))
        generated_page_weather_path_raw = _as_str(preview.get("generated", {}).get("page_weather", {}).get("path", ""))
        generated_page_climate_path_raw = _as_str(preview.get("generated", {}).get("page_climate", {}).get("path", ""))
        generated_entities_path = Path(generated_entities_path_raw) if generated_entities_path_raw else None
        generated_theme_path = Path(generated_theme_path_raw) if generated_theme_path_raw else None
        generated_layout_path = Path(generated_layout_path_raw) if generated_layout_path_raw else None
        generated_page_home_path = Path(generated_page_home_path_raw) if generated_page_home_path_raw else None
        generated_page_lights_path = Path(generated_page_lights_path_raw) if generated_page_lights_path_raw else None
        generated_page_weather_path = Path(generated_page_weather_path_raw) if generated_page_weather_path_raw else None
        generated_page_climate_path = Path(generated_page_climate_path_raw) if generated_page_climate_path_raw else None
        install_path.parent.mkdir(parents=True, exist_ok=True)
        overrides_path.parent.mkdir(parents=True, exist_ok=True)
        install_path.write_text(preview["install"]["content_new"], encoding="utf-8")
        overrides_path.write_text(preview["overrides"]["content_new"], encoding="utf-8")
        if generated_entities_path is not None:
            generated_entities_path.parent.mkdir(parents=True, exist_ok=True)
            generated_entities_path.write_text(preview.get("generated", {}).get("entities", {}).get("content_new", ""), encoding="utf-8")
        if generated_theme_path is not None:
            generated_theme_path.parent.mkdir(parents=True, exist_ok=True)
            generated_theme_path.write_text(preview.get("generated", {}).get("theme", {}).get("content_new", ""), encoding="utf-8")
        if generated_layout_path is not None:
            generated_layout_path.parent.mkdir(parents=True, exist_ok=True)
            generated_layout_path.write_text(preview.get("generated", {}).get("layout", {}).get("content_new", ""), encoding="utf-8")
        if generated_page_home_path is not None:
            generated_page_home_path.parent.mkdir(parents=True, exist_ok=True)
            generated_page_home_path.write_text(preview.get("generated", {}).get("page_home", {}).get("content_new", ""), encoding="utf-8")
        if generated_page_lights_path is not None:
            generated_page_lights_path.parent.mkdir(parents=True, exist_ok=True)
            generated_page_lights_path.write_text(preview.get("generated", {}).get("page_lights", {}).get("content_new", ""), encoding="utf-8")
        if generated_page_weather_path is not None:
            generated_page_weather_path.parent.mkdir(parents=True, exist_ok=True)
            generated_page_weather_path.write_text(preview.get("generated", {}).get("page_weather", {}).get("content_new", ""), encoding="utf-8")
        if generated_page_climate_path is not None:
            generated_page_climate_path.parent.mkdir(parents=True, exist_ok=True)
            generated_page_climate_path.write_text(preview.get("generated", {}).get("page_climate", {}).get("content_new", ""), encoding="utf-8")
        return jsonify(
            {
                "ok": True,
                "device_slug": device_slug,
                "managed_root": str(MANAGED_ROOT),
                "paths": {
                    "install": str(install_path),
                    "overrides": str(overrides_path),
                    "generated_entities": str(generated_entities_path) if generated_entities_path else "",
                    "generated_theme": str(generated_theme_path) if generated_theme_path else "",
                    "generated_layout": str(generated_layout_path) if generated_layout_path else "",
                    "generated_page_home": str(generated_page_home_path) if generated_page_home_path else "",
                    "generated_page_lights": str(generated_page_lights_path) if generated_page_lights_path else "",
                    "generated_page_weather": str(generated_page_weather_path) if generated_page_weather_path else "",
                    "generated_page_climate": str(generated_page_climate_path) if generated_page_climate_path else "",
                },
                "checksums": {
                    "install": _sha256_file(install_path),
                    "overrides": _sha256_file(overrides_path),
                    "generated_entities": _sha256_file(generated_entities_path) if generated_entities_path else "",
                    "generated_theme": _sha256_file(generated_theme_path) if generated_theme_path else "",
                    "generated_layout": _sha256_file(generated_layout_path) if generated_layout_path else "",
                    "generated_page_home": _sha256_file(generated_page_home_path) if generated_page_home_path else "",
                    "generated_page_lights": _sha256_file(generated_page_lights_path) if generated_page_lights_path else "",
                    "generated_page_weather": _sha256_file(generated_page_weather_path) if generated_page_weather_path else "",
                    "generated_page_climate": _sha256_file(generated_page_climate_path) if generated_page_climate_path else "",
                },
                "backup": backup,
                "changed": {
                    "install": _as_bool(preview["install"].get("changed"), False),
                    "overrides": _as_bool(preview["overrides"].get("changed"), False),
                    "generated_entities": _as_bool(preview.get("generated", {}).get("entities", {}).get("changed"), False),
                    "generated_theme": _as_bool(preview.get("generated", {}).get("theme", {}).get("changed"), False),
                    "generated_layout": _as_bool(preview.get("generated", {}).get("layout", {}).get("changed"), False),
                    "generated_page_home": _as_bool(preview.get("generated", {}).get("page_home", {}).get("changed"), False),
                    "generated_page_lights": _as_bool(preview.get("generated", {}).get("page_lights", {}).get("changed"), False),
                    "generated_page_weather": _as_bool(preview.get("generated", {}).get("page_weather", {}).get("changed"), False),
                    "generated_page_climate": _as_bool(preview.get("generated", {}).get("page_climate", {}).get("changed"), False),
                },
                "compile_hint": f"esphome run {install_path}",
            }
        )
    finally:
        lock.release()


@app.get("/api/backups/list")
def api_backups_list() -> Any:
    device_slug = _as_str(request.args.get("device_slug"), "").strip()
    if not device_slug:
        return jsonify({"ok": False, "error": "device_slug is required"}), 400
    backups = _list_backups(device_slug)
    return jsonify({"ok": True, "device_slug": _slugify(device_slug, "tdeck"), "count": len(backups), "backups": backups})


@app.post("/api/backups/restore")
def api_backups_restore() -> Any:
    payload = request.get_json(silent=True) or {}
    device_slug = _as_str(payload.get("device_slug"), "").strip()
    backup_id = _as_str(payload.get("backup_id"), "").strip()
    if not device_slug or not backup_id:
        return jsonify({"ok": False, "error": "device_slug and backup_id are required"}), 400
    lock = _get_apply_lock(device_slug)
    if not lock.acquire(blocking=False):
        return jsonify({"ok": False, "error": "apply_in_progress", "device_slug": _slugify(device_slug, "tdeck")}), 409
    try:
        restored = _restore_backup(device_slug, backup_id)
    except Exception as err:
        return jsonify({"ok": False, "error": str(err)}), 404
    finally:
        lock.release()
    return jsonify({"ok": True, "restored": restored})


@app.get("/")
def root() -> Any:
    return _index_response()


@app.get("/<path:path>")
def static_proxy(path: str) -> Any:
    if path.lower() == "index.html":
        return _index_response()
    full_path = os.path.join(STATIC_DIR, path)
    if os.path.isfile(full_path):
        return _static_file_response(path)
    return _index_response()


def _index_response() -> Any:
    index_path = Path(STATIC_DIR) / "index.html"
    html = index_path.read_text(encoding="utf-8")
    html = html.replace("__ASSET_VERSION__", ADDON_VERSION)
    html = html.replace("__INGRESS_EXPECTED_PREFIX__", _infer_ingress_api_base())
    response = make_response(html)
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def _static_file_response(path: str) -> Any:
    response = send_from_directory(STATIC_DIR, path)
    lowered = path.lower()
    if lowered.endswith((".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2")):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        response.headers["Cache-Control"] = "public, max-age=3600"
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8099, debug=False)
