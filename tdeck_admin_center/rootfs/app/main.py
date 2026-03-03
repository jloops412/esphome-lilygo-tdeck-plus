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
from flask import Flask, jsonify, request, send_from_directory


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
ADDON_VERSION = os.getenv("ADDON_VERSION", os.getenv("BUILD_VERSION", "0.20.6")) or "0.20.6"
DEFAULT_APP_RELEASE_VERSION = os.getenv("APP_RELEASE_VERSION", "v0.20.6") or "v0.20.6"

CACHE_TTL_SECONDS = 15
RELEASE_CACHE_TTL_SECONDS = 900
DISCOVERY_JOB_POLL_TTL_SECONDS = 180
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500
PROFILE_SCHEMA_VERSION = "1.0"
WORKSPACE_SCHEMA_VERSION = "2.0"

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
        ],
        "defaults": defaults,
    }


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
    }
    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "profile_name": "default",
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
        "devices": [profile],
        "templates": {},
        "bindings": {},
        "layout": {},
        "theme": {},
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
        merged["templates"] = {}
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

    if p.get("schema_version") != PROFILE_SCHEMA_VERSION:
        warnings.append(
            f"schema_version '{p.get('schema_version')}' differs from expected '{PROFILE_SCHEMA_VERSION}'."
        )

    features = p.get("features", {})
    if _as_bool(features.get("lights"), True):
        light_count = _as_int(substitutions.get("light_slot_count"), 6, 1, 8)
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
    return {
        "install": d / "tdeck-install.yaml",
        "overrides": d / "tdeck-overrides.yaml",
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


def _preview_managed_apply(
    workspace: Dict[str, Any],
    profile: Dict[str, Any],
    git_ref: str,
    git_url: str,
) -> Dict[str, Any]:
    device_slug = _managed_device_slug(profile)
    paths = _managed_paths(device_slug)
    substitutions = _profile_to_substitutions(profile)
    install_new = _build_install_yaml(substitutions, git_ref, git_url)
    overrides_new = _build_overrides_yaml(substitutions)

    install_cur = _read_text(paths["install"])
    overrides_cur = _read_text(paths["overrides"])

    install_changed = install_cur != install_new
    overrides_changed = overrides_cur != overrides_new
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
    if install_file.exists():
        shutil.copy2(install_file, snapshot / "tdeck-install.yaml")
    if overrides_file.exists():
        shutil.copy2(overrides_file, snapshot / "tdeck-overrides.yaml")

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
        },
        "paths": {
            "install": str(install_file),
            "overrides": str(overrides_file),
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
    restored = {"install": False, "overrides": False}
    if install_src.exists():
        shutil.copy2(install_src, paths["install"])
        restored["install"] = True
    if overrides_src.exists():
        shutil.copy2(overrides_src, paths["overrides"])
        restored["overrides"] = True
    return {
        "device_slug": device_slug,
        "backup_id": backup_id,
        "restored": restored,
        "paths": {
            "install": str(paths["install"]),
            "overrides": str(paths["overrides"]),
        },
        "checksums": {
            "install": _sha256_file(paths["install"]),
            "overrides": _sha256_file(paths["overrides"]),
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


def _build_install_yaml(substitutions: Dict[str, str], git_ref: str, git_url: str) -> str:
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
            f"  - url: {_q(git_url)}",
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


def _firmware_status_for(
    device_slug: str,
    target_version: str,
    native_firmware_entity: str,
    app_version_entity: str,
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

    status_text = "firmware_up_to_date"
    if firmware_pending:
        status_text = "firmware_pending"
    if not native_known:
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
    return jsonify(
        {
            "ok": True,
            "addon_version": ADDON_VERSION,
            "addon_updated_since_last_run": runtime.get("addon_updated_since_last_run", False),
            "firmware_status_summary": _runtime_firmware_summary(),
            "runtime_state": runtime,
            "ha_connected": ha_ok,
            "ha_error": ha_error,
            "ha": ha_info,
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
            "version": "3",
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
    job_id = _as_str(request.args.get("job_id"), "").strip()
    domain = _as_str(request.args.get("domain"), "").strip().lower()
    query = _as_str(request.args.get("q"), "").strip().lower()
    sort_key = _as_str(request.args.get("sort"), "entity_id").strip().lower()
    only_mappable = _as_bool(request.args.get("only_mappable"), False)
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
    return jsonify(
        {
            "ok": True,
            "count": len(page_rows),
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
            "sort": sort_key,
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
    return jsonify(
        {
            "ok": len(all_errors) == 0,
            "errors": all_errors,
            "warnings": all_warnings,
            "profile": result["profile"],
            "workspace": workspace,
            "active_device_index": active_idx,
            "per_device": per_device,
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
    default_native, default_app_ver = _resolve_firmware_entities(device_slug)
    status = _firmware_status_for(
        device_slug=device_slug,
        target_version=target_version,
        native_firmware_entity=native_override or default_native,
        app_version_entity=app_ver_override or default_app_ver,
    )
    return jsonify({"ok": True, **status})


@app.post("/api/firmware/update")
def api_firmware_update() -> Any:
    payload = request.get_json(silent=True) or {}
    backup_first = _as_bool(payload.get("backup_first"), True)

    workspace, profile, _ = _workspace_or_profile_from_payload(payload)
    settings = profile.get("settings", {}) if isinstance(profile.get("settings"), dict) else {}
    device_slug = _as_str(payload.get("device_slug"), _managed_device_slug(profile)).strip() or _managed_device_slug(profile)
    target_version = _as_str(payload.get("target_version"), _as_str(settings.get("app_release_version"), DEFAULT_APP_RELEASE_VERSION))
    native_default, app_ver_default = _resolve_firmware_entities(device_slug, settings)
    native_firmware_entity = _as_str(payload.get("native_firmware_entity"), native_default).strip() or native_default
    app_version_entity = _as_str(payload.get("app_version_entity"), app_ver_default).strip() or app_ver_default

    lock = _get_apply_lock(device_slug)
    if not lock.acquire(blocking=False):
        return jsonify({"ok": False, "error": "apply_in_progress", "device_slug": _slugify(device_slug, "tdeck")}), 409

    backup: Dict[str, Any] | None = None
    try:
        if backup_first:
            deployment = workspace.get("deployment", {}) if isinstance(workspace.get("deployment"), dict) else {}
            git_ref = _as_str(payload.get("git_ref"), _as_str(deployment.get("git_ref"), _as_str(profile.get("device", {}).get("git_ref"), ADDON_GITHUB_REF)))
            git_url = _as_str(payload.get("git_url"), _as_str(deployment.get("git_url"), _as_str(profile.get("device", {}).get("git_url"), ADDON_GITHUB_REPO_URL)))
            preview = _preview_managed_apply(workspace, profile, git_ref or ADDON_GITHUB_REF, git_url or ADDON_GITHUB_REPO_URL)
            backup = _backup_files(
                device_slug,
                preview,
                profile,
                workspace,
                reason="pre_firmware_update",
                context={
                    "native_firmware_entity": native_firmware_entity,
                    "app_version_entity": app_version_entity,
                    "target_version": target_version,
                    "backup_first": True,
                },
            )

        service_response = _ha_post("/services/update/install", {"entity_id": native_firmware_entity}, timeout=25)
        with _RUNTIME_STATE_LOCK:
            _RUNTIME_STATE["last_prompted_device_slug"] = _slugify(device_slug, "tdeck")
            _RUNTIME_STATE["last_firmware_action"] = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "status": "requested",
                "device_slug": _slugify(device_slug, "tdeck"),
                "native_firmware_entity": native_firmware_entity,
                "app_version_entity": app_version_entity,
                "target_version": target_version,
                "backup_id": backup.get("id", "") if isinstance(backup, dict) else "",
            }
            _save_runtime_state(_RUNTIME_STATE)

        status = _firmware_status_for(
            device_slug=device_slug,
            target_version=target_version,
            native_firmware_entity=native_firmware_entity,
            app_version_entity=app_version_entity,
        )
        return jsonify(
            {
                "ok": True,
                "action": "update.install",
                "device_slug": _slugify(device_slug, "tdeck"),
                "native_firmware_entity": native_firmware_entity,
                "app_version_entity": app_version_entity,
                "target_version": target_version,
                "backup": backup or {},
                "service_response": service_response,
                "status": status,
            }
        )
    except Exception as err:
        with _RUNTIME_STATE_LOCK:
            _RUNTIME_STATE["last_firmware_action"] = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "status": "error",
                "device_slug": _slugify(device_slug, "tdeck"),
                "native_firmware_entity": native_firmware_entity,
                "app_version_entity": app_version_entity,
                "target_version": target_version,
                "backup_id": backup.get("id", "") if isinstance(backup, dict) else "",
                "error": str(err),
            }
            _save_runtime_state(_RUNTIME_STATE)
        return jsonify(
            {
                "ok": False,
                "error": str(err),
                "device_slug": _slugify(device_slug, "tdeck"),
                "native_firmware_entity": native_firmware_entity,
                "app_version_entity": app_version_entity,
                "target_version": target_version,
                "backup": backup or {},
            }
        ), 502
    finally:
        lock.release()


@app.get("/api/meta/contracts")
def api_meta_contracts() -> Any:
    return jsonify(
        {
            "ok": True,
            "contracts": _contracts(),
            "default_profile": _default_profile(),
            "default_workspace": _default_workspace(),
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
        validation = _validate_profile(profile)
        return jsonify(
            {
                "ok": True,
                "yaml": _build_install_yaml(substitutions, git_ref, git_url),
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
        install_path.parent.mkdir(parents=True, exist_ok=True)
        overrides_path.parent.mkdir(parents=True, exist_ok=True)
        install_path.write_text(preview["install"]["content_new"], encoding="utf-8")
        overrides_path.write_text(preview["overrides"]["content_new"], encoding="utf-8")
        return jsonify(
            {
                "ok": True,
                "device_slug": device_slug,
                "managed_root": str(MANAGED_ROOT),
                "paths": {
                    "install": str(install_path),
                    "overrides": str(overrides_path),
                },
                "checksums": {
                    "install": _sha256_file(install_path),
                    "overrides": _sha256_file(overrides_path),
                },
                "backup": backup,
                "changed": {
                    "install": _as_bool(preview["install"].get("changed"), False),
                    "overrides": _as_bool(preview["overrides"].get("changed"), False),
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
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/<path:path>")
def static_proxy(path: str) -> Any:
    full_path = os.path.join(STATIC_DIR, path)
    if os.path.isfile(full_path):
        return send_from_directory(STATIC_DIR, path)
    return send_from_directory(STATIC_DIR, "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8099, debug=False)
