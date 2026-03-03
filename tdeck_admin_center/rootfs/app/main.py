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
ADDON_VERSION = os.getenv("ADDON_VERSION", os.getenv("BUILD_VERSION", "0.25.2")) or "0.25.2"
DEFAULT_APP_RELEASE_VERSION = os.getenv("APP_RELEASE_VERSION", "v0.25.2") or "v0.25.2"

CACHE_TTL_SECONDS = 15
RELEASE_CACHE_TTL_SECONDS = 900
SERVICE_CACHE_TTL_SECONDS = 20
DISCOVERY_JOB_POLL_TTL_SECONDS = 180
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500
PROFILE_SCHEMA_VERSION = "5.0"
WORKSPACE_SCHEMA_VERSION = "5.0"
ENTITY_COLLECTION_LIMITS = {
    "lights": {"default_max": 24, "hard_max": 64},
    "cameras": {"default_max": 8, "hard_max": 24},
    "weather_metrics": {"default_max": 32, "hard_max": 64},
    "climate_controls": {"default_max": 24, "hard_max": 64},
    "reader_feeds": {"default_max": 16, "hard_max": 32},
    "system_entities": {"default_max": 24, "hard_max": 64},
}
SLOT_RUNTIME_LIMITS = {
    "lights": {"default_cap": 24, "min_cap": 8, "max_cap": 48, "default_page_size": 6, "min_page_size": 4, "max_page_size": 8},
    "cameras": {"default_cap": 8, "min_cap": 2, "max_cap": 16, "default_page_size": 4, "min_page_size": 2, "max_page_size": 6},
}
FEATURE_PAGE_POLICY: Dict[str, Dict[str, List[str]]] = {
    "lights": {"required": ["ui_show_lights"], "optional": ["home_tile_show_lights"]},
    "weather": {"required": ["ui_show_weather"], "optional": ["home_tile_show_weather"]},
    "climate": {"required": ["ui_show_climate"], "optional": ["home_tile_show_climate"]},
    "cameras": {"required": ["ui_show_cameras"], "optional": ["home_tile_show_cameras"]},
    "reader": {"required": ["ui_show_reader"], "optional": ["home_tile_show_reader"]},
    "gps": {"required": [], "optional": []},
}
ONBOARDING_PRESETS: Dict[str, Dict[str, bool]] = {
    "blank": {"lights": False, "weather": False, "climate": False, "cameras": False, "reader": False, "gps": False},
    "controller": {"lights": True, "weather": True, "climate": True, "cameras": False, "reader": False, "gps": True},
    "weather_climate": {"lights": False, "weather": True, "climate": True, "cameras": False, "reader": False, "gps": True},
    "security": {"lights": True, "weather": False, "climate": False, "cameras": True, "reader": False, "gps": False},
    "media": {"lights": False, "weather": False, "climate": False, "cameras": False, "reader": True, "gps": False},
}
NODE_KEYWORDS = ("tdeck", "t-deck", "t deck", "lilygo", "deckplus", "deck plus")
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

TYPE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "light": {
        "label": "Light",
        "domains": ["light"],
        "icon": "lightbulb",
        "controls": ["toggle", "brightness", "color_temp", "color"],
        "collection": "lights",
    },
    "switch": {
        "label": "Switch",
        "domains": ["switch"],
        "icon": "toggle",
        "controls": ["toggle"],
        "collection": "system_entities",
    },
    "climate": {
        "label": "Climate",
        "domains": ["climate"],
        "icon": "thermostat",
        "controls": ["mode", "target", "fan"],
        "collection": "climate_controls",
    },
    "weather": {
        "label": "Weather",
        "domains": ["weather"],
        "icon": "weather-partly-cloudy",
        "controls": ["current", "details"],
        "collection": "weather_metrics",
    },
    "camera": {
        "label": "Camera",
        "domains": ["camera"],
        "icon": "cctv",
        "controls": ["snapshot", "refresh"],
        "collection": "cameras",
    },
    "cover": {
        "label": "Cover",
        "domains": ["cover"],
        "icon": "garage",
        "controls": ["open_close", "position"],
        "collection": "system_entities",
    },
    "lock": {
        "label": "Lock",
        "domains": ["lock"],
        "icon": "lock",
        "controls": ["lock_unlock"],
        "collection": "system_entities",
    },
    "fan": {
        "label": "Fan",
        "domains": ["fan"],
        "icon": "fan",
        "controls": ["toggle", "speed", "direction"],
        "collection": "system_entities",
    },
    "media_player": {
        "label": "Media Player",
        "domains": ["media_player"],
        "icon": "play-box",
        "controls": ["playback", "volume", "source"],
        "collection": "system_entities",
    },
    "sensor": {
        "label": "Sensor",
        "domains": ["sensor", "binary_sensor"],
        "icon": "gauge",
        "controls": ["read"],
        "collection": "system_entities",
    },
}

CORE_TYPE_IDS: List[str] = [
    "light",
    "switch",
    "climate",
    "weather",
    "camera",
    "cover",
    "lock",
    "fan",
    "media_player",
    "sensor",
]
_SERVICE_LOCK = threading.Lock()
_SERVICE_CACHE: Dict[str, Any] = {
    "fetched_at": 0.0,
    "services": {},
    "last_error": "",
}
_APPLY_LOCKS: Dict[str, threading.Lock] = {}
_RUNTIME_STATE_LOCK = threading.Lock()
_DEPLOY_PREFLIGHT_LOCK = threading.Lock()
_DEPLOY_PREFLIGHT_TOKENS: Dict[str, Dict[str, Any]] = {}
DEPLOY_PREFLIGHT_TTL_SECONDS = 900


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
        "last_deploy_run": {},
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
        return "owner/repository"
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
    return "owner/repository"


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
            "last_deploy_run": _RUNTIME_STATE.get("last_deploy_run", {}),
        }


def _save_last_deploy_run(result: Dict[str, Any]) -> None:
    with _RUNTIME_STATE_LOCK:
        _RUNTIME_STATE["last_deploy_run"] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "ok": _as_bool(result.get("ok"), False),
            "device_slug": _as_str(result.get("device_slug"), ""),
            "error": _as_str(result.get("error"), ""),
            "validation_ok": _as_bool(result.get("validation", {}).get("ok"), False),
            "apply_backup_id": _as_str(result.get("apply", {}).get("backup", {}).get("id"), ""),
            "firmware_method": _as_str(result.get("firmware", {}).get("selected_method"), ""),
            "firmware_ok": _as_bool(result.get("firmware", {}).get("ok"), False),
            "pipeline": result.get("pipeline", {}),
        }
        _save_runtime_state(_RUNTIME_STATE)


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
    out = {
        "name": "lilygo-tdeck-plus",
        "friendly_name": "LilyGO T-Deck Plus",
        "git_url": ADDON_GITHUB_REPO_URL,
        "repo_url": ADDON_GITHUB_REPO_URL,
        "app_release_channel": DEFAULT_RELEASE_CHANNEL,
        "app_release_version": DEFAULT_APP_RELEASE_VERSION,
        "generated_light_slot_cap": str(SLOT_RUNTIME_LIMITS["lights"]["default_cap"]),
        "generated_camera_slot_cap": str(SLOT_RUNTIME_LIMITS["cameras"]["default_cap"]),
        "generated_light_page_size": str(SLOT_RUNTIME_LIMITS["lights"]["default_page_size"]),
        "generated_camera_page_size": str(SLOT_RUNTIME_LIMITS["cameras"]["default_page_size"]),
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
    for idx in range(9, SLOT_RUNTIME_LIMITS["lights"]["max_cap"] + 1):
        out[f"light_slot_{idx}_name"] = f"Spare {idx}"
        out[f"light_slot_{idx}_entity"] = f"light.replace_me_slot_{idx}"
    for idx in range(3, SLOT_RUNTIME_LIMITS["cameras"]["max_cap"] + 1):
        out[f"camera_slot_{idx}_name"] = f"Camera {idx}"
        out[f"camera_slot_{idx}_entity"] = f"camera.replace_me_{idx}"
    return out


def _required_by_feature() -> Dict[str, List[str]]:
    return {
        "lights": ["light_slot_count", "light_slot_1_entity"],
        "weather": ["entity_wx_main", "entity_wx_temp_sensor"],
        "climate": ["entity_sensi_climate", "entity_sensi_temperature_sensor"],
        "cameras": ["camera_slot_count", "camera_slot_1_entity", "ha_base_url"],
        "reader": ["entity_feed_bbc", "entity_feed_dc", "entity_feed_loudoun"],
        "gps": ["gps_rx_pin", "gps_tx_pin", "gps_baud_rate"],
    }


def _required_binding_templates() -> Dict[str, Dict[str, Any]]:
    return {
        "entity_wx_main": {"type": "weather", "tokens": ["weather", "forecast"], "domains": ["weather"]},
        "entity_wx_temp_sensor": {"type": "sensor", "tokens": ["temp", "temperature", "outdoor"], "domains": ["sensor"]},
        "entity_sensi_climate": {"type": "climate", "tokens": ["climate", "thermostat", "hvac"], "domains": ["climate"]},
        "entity_sensi_temperature_sensor": {"type": "sensor", "tokens": ["temp", "temperature", "indoor"], "domains": ["sensor"]},
        "entity_feed_bbc": {"type": "sensor", "tokens": ["bbc", "news"], "domains": ["event", "sensor"]},
        "entity_feed_dc": {"type": "sensor", "tokens": ["dc", "news"], "domains": ["event", "sensor"]},
        "entity_feed_loudoun": {"type": "sensor", "tokens": ["loudoun", "news"], "domains": ["event", "sensor"]},
    }


def _best_instance_match(
    profile: Dict[str, Any],
    type_id: str,
    tokens: List[str] | None = None,
    domains: List[str] | None = None,
) -> Tuple[str, str]:
    p = _normalize_profile(profile)
    instances = p.get("entity_instances", []) if isinstance(p.get("entity_instances"), list) else []
    token_list = [t.lower() for t in (tokens or []) if _as_str(t, "")]
    domain_list = [d.lower() for d in (domains or []) if _as_str(d, "")]
    scored: List[Tuple[int, str, str]] = []
    for idx, inst in enumerate(instances):
        if not isinstance(inst, dict):
            continue
        if not _as_bool(inst.get("enabled"), True):
            continue
        entity_id = _as_str(inst.get("entity_id"), "").strip().lower()
        if not entity_id:
            continue
        inst_type = _as_str(inst.get("type"), "").strip().lower()
        domain = entity_id.split(".", 1)[0] if "." in entity_id else ""
        name = _as_str(inst.get("name"), "").strip()
        blob = f"{entity_id} {name}".lower()
        score = 0
        reason_bits: List[str] = []
        if inst_type == type_id:
            score += 80
            reason_bits.append(f"type={type_id}")
        elif type_id == "sensor" and domain in {"sensor", "binary_sensor"}:
            score += 60
            reason_bits.append(f"domain={domain}")
        if domain_list and domain in domain_list:
            score += 30
            reason_bits.append("domain_hint")
        for t in token_list:
            if t and t in blob:
                score += 12
                reason_bits.append(f"token:{t}")
        score += max(0, 10 - idx)
        if score <= 0:
            continue
        scored.append((score, entity_id, ",".join(sorted(set(reason_bits)))))
    scored.sort(key=lambda x: (-x[0], x[1]))
    if not scored:
        return "", ""
    top = scored[0]
    return top[1], top[2]


def _infer_required_binding_values(profile: Dict[str, Any], substitutions: Dict[str, str] | None = None) -> Dict[str, Dict[str, str]]:
    p = _normalize_profile(profile)
    subs = substitutions if isinstance(substitutions, dict) else _profile_to_substitutions(p)
    out: Dict[str, Dict[str, str]] = {}
    features = p.get("features", {}) if isinstance(p.get("features"), dict) else {}
    collections = p.get("entity_collections", {}) if isinstance(p.get("entity_collections"), dict) else {}
    lights = collections.get("lights", []) if isinstance(collections.get("lights"), list) else []
    cameras = collections.get("cameras", []) if isinstance(collections.get("cameras"), list) else []
    enabled_lights = [x for x in lights if isinstance(x, dict) and _as_bool(x.get("enabled"), True)]
    enabled_cameras = [x for x in cameras if isinstance(x, dict) and _as_bool(x.get("enabled"), True)]

    if _as_bool(features.get("lights"), False):
        if enabled_lights:
            out["light_slot_1_entity"] = {
                "value": _as_str(enabled_lights[0].get("entity_id"), ""),
                "reason": "first_enabled_light_collection_row",
            }
            out["light_slot_count"] = {
                "value": str(len(enabled_lights)),
                "reason": "enabled_light_collection_count",
            }
        else:
            ent, why = _best_instance_match(p, "light", tokens=["light"], domains=["light"])
            if ent:
                out["light_slot_1_entity"] = {"value": ent, "reason": why or "typed_instance_match"}
                out["light_slot_count"] = {"value": "1", "reason": "typed_instance_match"}

    if _as_bool(features.get("cameras"), False):
        if enabled_cameras:
            out["camera_slot_1_entity"] = {
                "value": _as_str(enabled_cameras[0].get("entity_id"), ""),
                "reason": "first_enabled_camera_collection_row",
            }
            out["camera_slot_count"] = {
                "value": str(len(enabled_cameras)),
                "reason": "enabled_camera_collection_count",
            }
        else:
            ent, why = _best_instance_match(p, "camera", tokens=["camera", "door", "outdoor"], domains=["camera"])
            if ent:
                out["camera_slot_1_entity"] = {"value": ent, "reason": why or "typed_instance_match"}
                out["camera_slot_count"] = {"value": "1", "reason": "typed_instance_match"}

    templates = _required_binding_templates()
    for key, template in templates.items():
        ent, why = _best_instance_match(
            p,
            _as_str(template.get("type"), "sensor"),
            tokens=template.get("tokens") if isinstance(template.get("tokens"), list) else [],
            domains=template.get("domains") if isinstance(template.get("domains"), list) else [],
        )
        if ent:
            out[key] = {"value": ent, "reason": why or "typed_instance_match"}

    if _as_bool(features.get("cameras"), False) and _is_placeholder(subs.get("ha_base_url", "")):
        out["ha_base_url"] = {"value": _default_substitutions().get("ha_base_url", "http://homeassistant.local:8123"), "reason": "default_ha_base_url"}

    return out


def _required_bindings_snapshot(profile: Dict[str, Any], substitutions: Dict[str, str] | None = None) -> List[Dict[str, Any]]:
    p = _normalize_profile(profile)
    subs = substitutions if isinstance(substitutions, dict) else _profile_to_substitutions(p)
    suggestions = _infer_required_binding_values(p, subs)
    features = p.get("features", {}) if isinstance(p.get("features"), dict) else {}
    rows: List[Dict[str, Any]] = []
    for feature, keys in _required_by_feature().items():
        if not _as_bool(features.get(feature), False):
            continue
        for key in keys:
            value = _as_str(subs.get(key), "")
            placeholder = _is_placeholder(value)
            suggestion = suggestions.get(key, {})
            rows.append(
                {
                    "feature": feature,
                    "key": key,
                    "value": value,
                    "resolved": not placeholder,
                    "placeholder": placeholder,
                    "suggested_value": _as_str(suggestion.get("value"), ""),
                    "suggestion_reason": _as_str(suggestion.get("reason"), ""),
                }
            )
    return rows

def _default_feature_flags(preset: str = "blank") -> Dict[str, bool]:
    resolved = _as_str(preset, "blank").strip().lower()
    base = ONBOARDING_PRESETS.get(resolved) or ONBOARDING_PRESETS["blank"]
    out: Dict[str, bool] = {}
    for key in ["lights", "weather", "climate", "cameras", "reader", "gps"]:
        out[key] = _as_bool(base.get(key), False)
    return out


def _apply_feature_page_policy(profile: Dict[str, Any]) -> None:
    profile["features"] = profile.get("features", {}) if isinstance(profile.get("features"), dict) else {}
    profile["ui"] = profile.get("ui", {}) if isinstance(profile.get("ui"), dict) else {}
    for feature, policy in FEATURE_PAGE_POLICY.items():
        enabled = _as_bool(profile["features"].get(feature), False)
        required = policy.get("required", []) if isinstance(policy.get("required"), list) else []
        optional = policy.get("optional", []) if isinstance(policy.get("optional"), list) else []
        for key in required:
            profile["ui"][key] = enabled
        for key in optional:
            if not enabled:
                profile["ui"][key] = False
            elif key not in profile["ui"]:
                profile["ui"][key] = True

    # Core pages remain visible to guarantee recoverability.
    profile["ui"]["ui_show_settings"] = True
    profile["ui"]["ui_show_theme"] = True


def _contracts() -> Dict[str, Any]:
    defaults = _default_substitutions()
    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "workspace_schema_version": WORKSPACE_SCHEMA_VERSION,
        "canonical_model": "entity_instances",
        "required_by_feature": _required_by_feature(),
        "required_binding_templates": _required_binding_templates(),
        "domain_hints": DOMAIN_HINTS,
        "type_registry": _default_type_registry(),
        "core_type_ids": CORE_TYPE_IDS,
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
        "slot_runtime_limits": SLOT_RUNTIME_LIMITS,
        "slot_runtime_defaults": _default_slot_runtime(),
        "feature_page_policy": FEATURE_PAGE_POLICY,
        "onboarding_presets": ONBOARDING_PRESETS,
        "entity_collections_meta_defaults": _default_entity_collections_meta(),
        "layout_pages": list(_default_layout_pages().keys()),
        "generated_files": [
            "generated/types.registry.yaml",
            "generated/entities.instances.yaml",
            "generated/layout.pages.yaml",
            "generated/theme.tokens.yaml",
            "generated/bindings.report.yaml",
        ],
        "deploy_preflight_actions": [
            "auto_resolve_required_mappings",
            "auto_disable_unmapped_features",
            "auto_fit_slot_caps",
        ],
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


def _default_slot_runtime() -> Dict[str, int]:
    return {
        "light_slot_cap": SLOT_RUNTIME_LIMITS["lights"]["default_cap"],
        "camera_slot_cap": SLOT_RUNTIME_LIMITS["cameras"]["default_cap"],
        "light_page_size": SLOT_RUNTIME_LIMITS["lights"]["default_page_size"],
        "camera_page_size": SLOT_RUNTIME_LIMITS["cameras"]["default_page_size"],
    }


def _normalize_slot_runtime(slot_runtime: Any) -> Dict[str, int]:
    incoming = slot_runtime if isinstance(slot_runtime, dict) else {}
    return {
        "light_slot_cap": _as_int(
            incoming.get("light_slot_cap"),
            SLOT_RUNTIME_LIMITS["lights"]["default_cap"],
            SLOT_RUNTIME_LIMITS["lights"]["min_cap"],
            SLOT_RUNTIME_LIMITS["lights"]["max_cap"],
        ),
        "camera_slot_cap": _as_int(
            incoming.get("camera_slot_cap"),
            SLOT_RUNTIME_LIMITS["cameras"]["default_cap"],
            SLOT_RUNTIME_LIMITS["cameras"]["min_cap"],
            SLOT_RUNTIME_LIMITS["cameras"]["max_cap"],
        ),
        "light_page_size": _as_int(
            incoming.get("light_page_size"),
            SLOT_RUNTIME_LIMITS["lights"]["default_page_size"],
            SLOT_RUNTIME_LIMITS["lights"]["min_page_size"],
            SLOT_RUNTIME_LIMITS["lights"]["max_page_size"],
        ),
        "camera_page_size": _as_int(
            incoming.get("camera_page_size"),
            SLOT_RUNTIME_LIMITS["cameras"]["default_page_size"],
            SLOT_RUNTIME_LIMITS["cameras"]["min_page_size"],
            SLOT_RUNTIME_LIMITS["cameras"]["max_page_size"],
        ),
    }


def _default_entity_collections_meta() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for key in ENTITY_COLLECTION_LIMITS.keys():
        out[key] = {
            "sort": "name",
            "show_disabled": False,
            "last_query": "",
            "draft_dirty": False,
        }
    return out


def _normalize_entity_collections_meta(meta: Any) -> Dict[str, Dict[str, Any]]:
    incoming = meta if isinstance(meta, dict) else {}
    defaults = _default_entity_collections_meta()
    out: Dict[str, Dict[str, Any]] = {}
    for key in ENTITY_COLLECTION_LIMITS.keys():
        raw = incoming.get(key) if isinstance(incoming.get(key), dict) else {}
        out[key] = _deep_merge(defaults[key], raw)
        out[key]["sort"] = _as_str(out[key].get("sort"), "name") or "name"
        out[key]["show_disabled"] = _as_bool(out[key].get("show_disabled"), False)
        out[key]["last_query"] = _as_str(out[key].get("last_query"), "")
        out[key]["draft_dirty"] = _as_bool(out[key].get("draft_dirty"), False)
    return out


def _profile_collections_default(profile: Dict[str, Any]) -> Dict[str, Any]:
    lights: List[Dict[str, Any]] = []
    cameras: List[Dict[str, Any]] = []
    weather_metrics: List[Dict[str, Any]] = []
    climate_controls: List[Dict[str, Any]] = []
    reader_feeds: List[Dict[str, Any]] = []
    system_entities: List[Dict[str, Any]] = []
    slots = profile.get("slots", {}) if isinstance(profile.get("slots"), dict) else {}
    slot_runtime = _normalize_slot_runtime(profile.get("slot_runtime"))
    light_cap = _as_int(slot_runtime.get("light_slot_cap"), SLOT_RUNTIME_LIMITS["lights"]["default_cap"], SLOT_RUNTIME_LIMITS["lights"]["min_cap"], SLOT_RUNTIME_LIMITS["lights"]["max_cap"])
    camera_cap = _as_int(slot_runtime.get("camera_slot_cap"), SLOT_RUNTIME_LIMITS["cameras"]["default_cap"], SLOT_RUNTIME_LIMITS["cameras"]["min_cap"], SLOT_RUNTIME_LIMITS["cameras"]["max_cap"])
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
                "enabled": idx < _as_int(slots.get("light_slot_count"), 6, 1, light_cap),
            }
        )
    for idx, item in enumerate(slot_cameras):
        cameras.append(
            {
                "id": f"camera_{idx+1}",
                "name": _as_str(item.get("name"), f"Camera {idx+1}"),
                "entity_id": _as_str(item.get("entity"), ""),
                "enabled": idx < _as_int(slots.get("camera_slot_count"), 0, 0, camera_cap),
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
    profile["slot_runtime"] = _normalize_slot_runtime(profile.get("slot_runtime"))
    light_cap = _as_int(
        profile["slot_runtime"].get("light_slot_cap"),
        SLOT_RUNTIME_LIMITS["lights"]["default_cap"],
        SLOT_RUNTIME_LIMITS["lights"]["min_cap"],
        SLOT_RUNTIME_LIMITS["lights"]["max_cap"],
    )
    camera_cap = _as_int(
        profile["slot_runtime"].get("camera_slot_cap"),
        SLOT_RUNTIME_LIMITS["cameras"]["default_cap"],
        SLOT_RUNTIME_LIMITS["cameras"]["min_cap"],
        SLOT_RUNTIME_LIMITS["cameras"]["max_cap"],
    )
    lights = collections["lights"]
    cameras = collections["cameras"]
    enabled_lights = [x for x in lights if _as_bool(x.get("enabled"), True)]
    enabled_cameras = [x for x in cameras if _as_bool(x.get("enabled"), True)]
    slots = profile.get("slots", {}) if isinstance(profile.get("slots"), dict) else {}
    slot_lights: List[Dict[str, Any]] = []
    slot_cameras: List[Dict[str, Any]] = []
    for idx in range(light_cap):
        item = enabled_lights[idx] if idx < len(enabled_lights) else {}
        slot_lights.append(
            {
                "name": _as_str(item.get("name"), f"Light {idx+1}"),
                "entity": _as_str(item.get("entity_id"), f"light.replace_me_slot_{idx+1}"),
            }
        )
    for idx in range(camera_cap):
        item = enabled_cameras[idx] if idx < len(enabled_cameras) else {}
        slot_cameras.append(
            {
                "name": _as_str(item.get("name"), f"Camera {idx+1}"),
                "entity": _as_str(item.get("entity_id"), f"camera.replace_me_{idx+1}"),
            }
        )
    slots["lights"] = slot_lights
    slots["cameras"] = slot_cameras
    slots["light_slot_count"] = _as_int(min(len(enabled_lights), light_cap), 0, 1, light_cap)
    slots["camera_slot_count"] = _as_int(min(len(enabled_cameras), camera_cap), 0, 0, camera_cap)
    # Transition compatibility for legacy fixed-slot consumers.
    slots["legacy_lights"] = slot_lights[:8]
    slots["legacy_cameras"] = slot_cameras[:2]
    profile["slots"] = slots


def _default_type_registry() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for type_id in CORE_TYPE_IDS:
        item = TYPE_REGISTRY.get(type_id, {})
        out[type_id] = {
            "id": type_id,
            "label": _as_str(item.get("label"), type_id.title()),
            "domains": item.get("domains", []),
            "icon": _as_str(item.get("icon"), "shape"),
            "controls": item.get("controls", []),
            "collection": _as_str(item.get("collection"), "system_entities"),
        }
    return out


def _infer_type_id(entity_id: str, role: str = "", collection: str = "") -> str:
    role_low = _as_str(role, "").strip().lower()
    collection_low = _as_str(collection, "").strip().lower()
    if role_low.startswith("entity_wx_") or collection_low == "weather_metrics":
        return "weather"
    if role_low.startswith("entity_sensi_") or collection_low == "climate_controls":
        return "climate"
    if collection_low == "lights":
        return "light"
    if collection_low == "cameras":
        return "camera"
    if collection_low == "reader_feeds":
        return "sensor"
    domain = _as_str(entity_id, "").split(".", 1)[0].lower()
    if domain in {"light", "switch", "climate", "weather", "camera", "cover", "lock", "fan", "media_player"}:
        return domain
    if domain in {"sensor", "binary_sensor"}:
        return "sensor"
    return "sensor"


def _collection_for_type(type_id: str, role: str = "") -> str:
    role_low = _as_str(role, "").strip().lower()
    if role_low.startswith("entity_feed_"):
        return "reader_feeds"
    if role_low.startswith("entity_wx_"):
        return "weather_metrics"
    if role_low.startswith("entity_sensi_"):
        return "climate_controls"
    if type_id in TYPE_REGISTRY:
        return _as_str(TYPE_REGISTRY[type_id].get("collection"), "system_entities")
    return "system_entities"


def _normalize_entity_instance(item: Dict[str, Any], idx: int, collection_hint: str = "") -> Dict[str, Any]:
    entity_id = _as_str(item.get("entity_id") or item.get("entity"), "").strip()
    role = _as_str(item.get("role"), "").strip()
    type_id_raw = _as_str(item.get("type"), "").strip().lower()
    type_id = type_id_raw if type_id_raw in TYPE_REGISTRY else _infer_type_id(entity_id, role, collection_hint)
    collection = _collection_for_type(type_id, role) or collection_hint or "system_entities"
    name_default = entity_id or f"{type_id.title()} {idx + 1}"
    name = _as_str(item.get("name"), name_default).strip() or name_default
    instance_id = _slugify(item.get("id"), f"{type_id}_{idx + 1}")
    page = _as_str(item.get("page"), "").strip().lower()
    if not page:
        if collection in {"lights", "cameras", "weather_metrics", "climate_controls", "reader_feeds"}:
            page = {
                "weather_metrics": "weather",
                "climate_controls": "climate",
                "reader_feeds": "reader",
            }.get(collection, collection)
        else:
            page = "home"
    return {
        "id": instance_id,
        "type": type_id,
        "name": name,
        "entity_id": entity_id,
        "role": role,
        "enabled": _as_bool(item.get("enabled"), True),
        "icon": _as_str(item.get("icon"), _as_str(TYPE_REGISTRY.get(type_id, {}).get("icon"), "shape")),
        "page": page,
        "section": _as_str(item.get("section"), "content"),
        "group": _as_str(item.get("group"), collection),
        "meta": item.get("meta", {}) if isinstance(item.get("meta"), dict) else {},
    }


def _entity_instances_from_collections(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    collections = _normalize_profile_collections(profile)
    out: List[Dict[str, Any]] = []
    for collection in ENTITY_COLLECTION_LIMITS.keys():
        rows = collections.get(collection, []) if isinstance(collections.get(collection), list) else []
        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            normalized = _normalize_entity_instance(row, idx, collection_hint=collection)
            normalized["group"] = collection
            out.append(normalized)
    return out


def _sync_collections_from_entity_instances(profile: Dict[str, Any]) -> None:
    collections = _normalize_profile_collections(profile)
    for key in ENTITY_COLLECTION_LIMITS.keys():
        collections[key] = []
    instances = profile.get("entity_instances", []) if isinstance(profile.get("entity_instances"), list) else []
    for idx, instance in enumerate(instances):
        if not isinstance(instance, dict):
            continue
        normalized = _normalize_entity_instance(instance, idx)
        collection = _collection_for_type(_as_str(normalized.get("type"), "sensor"), _as_str(normalized.get("role"), ""))
        collections.setdefault(collection, [])
        collections[collection].append(
            {
                "id": _as_str(normalized.get("id"), f"{collection[:-1]}_{len(collections[collection]) + 1}"),
                "name": _as_str(normalized.get("name"), ""),
                "entity_id": _as_str(normalized.get("entity_id"), ""),
                "role": _as_str(normalized.get("role"), ""),
                "enabled": _as_bool(normalized.get("enabled"), True),
            }
        )
    profile["entity_collections"] = collections


def _normalize_entity_instances(profile: Dict[str, Any], incoming_has_instances: bool = False) -> None:
    source = profile.get("entity_instances") if isinstance(profile.get("entity_instances"), list) else []
    if incoming_has_instances:
        out: List[Dict[str, Any]] = []
        for idx, item in enumerate(source):
            if not isinstance(item, dict):
                continue
            out.append(_normalize_entity_instance(item, idx))
        profile["entity_instances"] = out
    else:
        profile["entity_instances"] = _entity_instances_from_collections(profile)
    profile["type_registry"] = _default_type_registry()
    if isinstance(profile.get("page_layouts"), list):
        # keep existing provided page layouts
        pass
    else:
        profile["page_layouts"] = []
    _sync_collections_from_entity_instances(profile)


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
        "integration": _as_str(attrs.get("integration")) or _as_str(attrs.get("platform")),
        "device_name": _as_str(attrs.get("device_name")),
        "attribution": _as_str(attrs.get("attribution")),
        "entity_category": _as_str(attrs.get("entity_category")),
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
        "onboarding_preset": "blank",
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
    entity_instances: List[Dict[str, Any]] = []
    for idx, row in enumerate(lights):
        entity_instances.append(
            _normalize_entity_instance(
                {
                    "id": f"light_{idx + 1}",
                    "type": "light",
                    "name": row.get("name"),
                    "entity_id": row.get("entity"),
                    "enabled": False,
                    "role": "light_slot",
                    "page": "lights",
                    "group": "lights",
                },
                idx,
                collection_hint="lights",
            )
        )
    for idx, row in enumerate(cameras):
        entity_instances.append(
            _normalize_entity_instance(
                {
                    "id": f"camera_{idx + 1}",
                    "type": "camera",
                    "name": row.get("name"),
                    "entity_id": row.get("entity"),
                    "enabled": False,
                    "role": "camera_slot",
                    "page": "cameras",
                    "group": "cameras",
                },
                idx,
                collection_hint="cameras",
            )
        )
    for key in ["entity_wx_main", "entity_sensi_climate", "entity_feed_bbc", "entity_ha_unit_system"]:
        entity_instances.append(
            _normalize_entity_instance(
                {
                    "id": key,
                    "type": _infer_type_id(defaults.get(key, ""), key),
                    "name": key,
                    "entity_id": defaults.get(key, ""),
                    "enabled": False,
                    "role": key,
                    "page": "home",
                    "group": _collection_for_type(_infer_type_id(defaults.get(key, ""), key), key),
                },
                len(entity_instances),
            )
        )
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
        "features": _default_feature_flags("blank"),
        "slots": {
            "light_slot_count": _as_int(defaults["light_slot_count"], 6, 1, SLOT_RUNTIME_LIMITS["lights"]["max_cap"]),
            "lights": lights,
            "camera_slot_count": _as_int(defaults["camera_slot_count"], 0, 0, SLOT_RUNTIME_LIMITS["cameras"]["max_cap"]),
            "cameras": cameras,
        },
        "slot_runtime": _default_slot_runtime(),
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
        "entity_collections_meta": _default_entity_collections_meta(),
        "type_registry": _default_type_registry(),
        "entity_instances": entity_instances,
        "page_layouts": [],
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
        "deployment_profile": {
            "git_ref": ADDON_GITHUB_REF,
            "git_url": ADDON_GITHUB_REPO_URL,
            "app_release_channel": DEFAULT_RELEASE_CHANNEL,
            "app_release_version": DEFAULT_APP_RELEASE_VERSION,
            "build_settings": {"mode": "auto"},
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
        "type_registry": _default_type_registry(),
        "entity_collections": {},
        "entity_instances": {},
        "layout_pages": _default_layout_pages(),
        "page_layouts": [],
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
        "device_workspace": {
            "devices": [profile],
        },
        "migration": {"from_schema": "", "applied": False, "timestamp": int(_now())},
        "deployment": {
            "git_ref": ADDON_GITHUB_REF,
            "git_url": ADDON_GITHUB_REPO_URL,
            "app_release_channel": DEFAULT_RELEASE_CHANNEL,
            "app_release_version": DEFAULT_APP_RELEASE_VERSION,
        },
        "deployment_profile": {
            "git_ref": ADDON_GITHUB_REF,
            "git_url": ADDON_GITHUB_REPO_URL,
            "app_release_channel": DEFAULT_RELEASE_CHANNEL,
            "app_release_version": DEFAULT_APP_RELEASE_VERSION,
            "build_settings": {"mode": "auto"},
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
    merged["type_registry"] = _default_type_registry()
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
    if not isinstance(merged.get("entity_instances"), dict):
        merged["entity_instances"] = {}
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
        merged["entity_instances"][dslug] = _copy_obj(profile.get("entity_instances", []))

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
    if not isinstance(merged.get("deployment_profile"), dict):
        merged["deployment_profile"] = {}
    merged["deployment_profile"]["git_ref"] = _as_str(merged["deployment_profile"].get("git_ref"), merged["deployment"]["git_ref"])
    merged["deployment_profile"]["git_url"] = _as_str(merged["deployment_profile"].get("git_url"), merged["deployment"]["git_url"])
    merged["deployment_profile"]["app_release_channel"] = _as_str(
        merged["deployment_profile"].get("app_release_channel"),
        merged["deployment"]["app_release_channel"],
    )
    merged["deployment_profile"]["app_release_version"] = _as_str(
        merged["deployment_profile"].get("app_release_version"),
        merged["deployment"]["app_release_version"],
    )
    if not isinstance(merged["deployment_profile"].get("build_settings"), dict):
        merged["deployment_profile"]["build_settings"] = {"mode": "auto"}
    merged["device_workspace"] = {"devices": _copy_obj(merged["devices"])}
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
    incoming_has_instances = isinstance(profile, dict) and isinstance(profile.get("entity_instances"), list)
    merged = _deep_merge(json.loads(json.dumps(_default_profile())), profile or {})

    merged["schema_version"] = PROFILE_SCHEMA_VERSION
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
        merged["features"][key] = _as_bool(merged["features"].get(key), False)

    merged["slot_runtime"] = _normalize_slot_runtime(merged.get("slot_runtime"))
    light_cap = _as_int(
        merged["slot_runtime"].get("light_slot_cap"),
        SLOT_RUNTIME_LIMITS["lights"]["default_cap"],
        SLOT_RUNTIME_LIMITS["lights"]["min_cap"],
        SLOT_RUNTIME_LIMITS["lights"]["max_cap"],
    )
    camera_cap = _as_int(
        merged["slot_runtime"].get("camera_slot_cap"),
        SLOT_RUNTIME_LIMITS["cameras"]["default_cap"],
        SLOT_RUNTIME_LIMITS["cameras"]["min_cap"],
        SLOT_RUNTIME_LIMITS["cameras"]["max_cap"],
    )

    slots = merged["slots"]
    slots["light_slot_count"] = _as_int(slots.get("light_slot_count"), 6, 1, light_cap)
    slots["camera_slot_count"] = _as_int(slots.get("camera_slot_count"), 0, 0, camera_cap)

    lights = slots.get("lights") if isinstance(slots.get("lights"), list) else []
    while len(lights) < light_cap:
        idx = len(lights) + 1
        lights.append({"name": f"Light {idx}", "entity": f"light.replace_me_slot_{idx}"})
    slots["lights"] = lights[:light_cap]

    cameras = slots.get("cameras") if isinstance(slots.get("cameras"), list) else []
    while len(cameras) < camera_cap:
        idx = len(cameras) + 1
        cameras.append({"name": f"Camera {idx}", "entity": f"camera.replace_me_{idx}"})
    slots["cameras"] = cameras[:camera_cap]

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
    merged["type_registry"] = _default_type_registry()
    merged["entity_collections_meta"] = _normalize_entity_collections_meta(merged.get("entity_collections_meta"))

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
    merged["settings"]["onboarding_preset"] = _as_str(merged["settings"].get("onboarding_preset"), "blank")
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
    if not isinstance(merged.get("page_layouts"), list):
        merged["page_layouts"] = []
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
    if not isinstance(merged.get("deployment_profile"), dict):
        merged["deployment_profile"] = _default_profile().get("deployment_profile", {})
    else:
        merged["deployment_profile"] = _deep_merge(_default_profile().get("deployment_profile", {}), merged["deployment_profile"])
    merged["entity_collections"] = _normalize_profile_collections(merged)
    _normalize_entity_instances(merged, incoming_has_instances=incoming_has_instances)
    _sync_slots_from_collections(merged)
    _apply_feature_page_policy(merged)
    return merged


def _profile_to_substitutions(profile: Dict[str, Any], overrides: Dict[str, Any] | None = None) -> Dict[str, str]:
    p = _normalize_profile(profile)
    substitutions = _default_substitutions()

    substitutions["name"] = _as_str(p["device"].get("name"), substitutions["name"])
    substitutions["friendly_name"] = _as_str(p["device"].get("friendly_name"), substitutions["friendly_name"])

    for key, value in p.get("entities", {}).items():
        if key in substitutions:
            substitutions[key] = _as_str(value, substitutions[key])

    slot_runtime = _normalize_slot_runtime(p.get("slot_runtime"))
    light_cap = _as_int(
        slot_runtime.get("light_slot_cap"),
        SLOT_RUNTIME_LIMITS["lights"]["default_cap"],
        SLOT_RUNTIME_LIMITS["lights"]["min_cap"],
        SLOT_RUNTIME_LIMITS["lights"]["max_cap"],
    )
    camera_cap = _as_int(
        slot_runtime.get("camera_slot_cap"),
        SLOT_RUNTIME_LIMITS["cameras"]["default_cap"],
        SLOT_RUNTIME_LIMITS["cameras"]["min_cap"],
        SLOT_RUNTIME_LIMITS["cameras"]["max_cap"],
    )
    light_page_size = _as_int(
        slot_runtime.get("light_page_size"),
        SLOT_RUNTIME_LIMITS["lights"]["default_page_size"],
        SLOT_RUNTIME_LIMITS["lights"]["min_page_size"],
        SLOT_RUNTIME_LIMITS["lights"]["max_page_size"],
    )
    camera_page_size = _as_int(
        slot_runtime.get("camera_page_size"),
        SLOT_RUNTIME_LIMITS["cameras"]["default_page_size"],
        SLOT_RUNTIME_LIMITS["cameras"]["min_page_size"],
        SLOT_RUNTIME_LIMITS["cameras"]["max_page_size"],
    )
    light_count = _as_int(p["slots"].get("light_slot_count"), 6, 1, light_cap)
    camera_count = _as_int(p["slots"].get("camera_slot_count"), 0, 0, camera_cap)
    substitutions["light_slot_count"] = str(light_count)
    substitutions["camera_slot_count"] = str(camera_count)
    substitutions["generated_light_slot_cap"] = str(light_cap)
    substitutions["generated_camera_slot_cap"] = str(camera_cap)
    substitutions["generated_light_page_size"] = str(light_page_size)
    substitutions["generated_camera_page_size"] = str(camera_page_size)

    lights = p["slots"].get("lights", [])
    for idx in range(1, light_cap + 1):
        entry = lights[idx - 1] if idx - 1 < len(lights) else {}
        substitutions[f"light_slot_{idx}_name"] = _as_str(entry.get("name"), substitutions.get(f"light_slot_{idx}_name", f"Light {idx}"))
        substitutions[f"light_slot_{idx}_entity"] = _as_str(entry.get("entity"), substitutions.get(f"light_slot_{idx}_entity", f"light.replace_me_slot_{idx}"))

    cameras = p["slots"].get("cameras", [])
    for idx in range(1, camera_cap + 1):
        entry = cameras[idx - 1] if idx - 1 < len(cameras) else {}
        substitutions[f"camera_slot_{idx}_name"] = _as_str(entry.get("name"), substitutions.get(f"camera_slot_{idx}_name", f"Camera {idx}"))
        substitutions[f"camera_slot_{idx}_entity"] = _as_str(entry.get("entity"), substitutions.get(f"camera_slot_{idx}_entity", f"camera.replace_me_{idx}"))

    for key in _contracts()["ui_keys"]:
        if key in p.get("ui", {}):
            substitutions[key] = _bool_str(p["ui"][key])

    features = p.get("features", {})
    if not _as_bool(features.get("lights"), False):
        substitutions["ui_show_lights"] = "false"
        substitutions["home_tile_show_lights"] = "false"
    if not _as_bool(features.get("weather"), False):
        substitutions["ui_show_weather"] = "false"
        substitutions["home_tile_show_weather"] = "false"
    if not _as_bool(features.get("climate"), False):
        substitutions["ui_show_climate"] = "false"
        substitutions["home_tile_show_climate"] = "false"
    if not _as_bool(features.get("reader"), False):
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
    required_bindings = _required_bindings_snapshot(p, substitutions)
    errors: List[str] = []
    warnings: List[str] = []
    collections = p.get("entity_collections", {}) if isinstance(p.get("entity_collections"), dict) else {}
    slot_runtime = _normalize_slot_runtime(p.get("slot_runtime"))
    light_cap = _as_int(
        slot_runtime.get("light_slot_cap"),
        SLOT_RUNTIME_LIMITS["lights"]["default_cap"],
        SLOT_RUNTIME_LIMITS["lights"]["min_cap"],
        SLOT_RUNTIME_LIMITS["lights"]["max_cap"],
    )
    camera_cap = _as_int(
        slot_runtime.get("camera_slot_cap"),
        SLOT_RUNTIME_LIMITS["cameras"]["default_cap"],
        SLOT_RUNTIME_LIMITS["cameras"]["min_cap"],
        SLOT_RUNTIME_LIMITS["cameras"]["max_cap"],
    )
    lights = collections.get("lights", []) if isinstance(collections.get("lights"), list) else []
    cameras = collections.get("cameras", []) if isinstance(collections.get("cameras"), list) else []
    instances = p.get("entity_instances", []) if isinstance(p.get("entity_instances"), list) else []

    if _as_str(p.get("schema_version"), "") != PROFILE_SCHEMA_VERSION:
        warnings.append(
            f"schema_version '{p.get('schema_version')}' differs from expected '{PROFILE_SCHEMA_VERSION}'."
        )
    if not instances:
        warnings.append("entity_instances is empty; no typed elements are configured yet.")
    app_release_version = _as_str(substitutions.get("app_release_version"), "").strip()
    app_release_channel = _as_str(substitutions.get("app_release_channel"), "").strip().lower()
    if not app_release_version:
        errors.append("app_release_version is required.")
    elif not re.match(r"^v\d+\.\d+\.\d+([\-+].+)?$", app_release_version):
        warnings.append("app_release_version should follow semantic tag style (for example v0.25.0).")
    if app_release_channel not in {"stable", "beta", "dev"}:
        warnings.append("app_release_channel should be stable, beta, or dev.")

    features = p.get("features", {})
    if _as_bool(features.get("lights"), False):
        light_count = _as_int(substitutions.get("light_slot_count"), 6, 1, light_cap)
        enabled_lights = [x for x in lights if _as_bool(x.get("enabled"), True)]
        if len(enabled_lights) == 0:
            warnings.append("lights feature enabled but no enabled lights in dynamic collections.")
        if len(enabled_lights) > light_cap:
            errors.append(
                f"enabled lights ({len(enabled_lights)}) exceed light_slot_cap ({light_cap}). Run auto-fit caps or disable rows."
            )
        if len(lights) > ENTITY_COLLECTION_LIMITS["lights"]["hard_max"]:
            errors.append(f"lights collection exceeds hard limit {ENTITY_COLLECTION_LIMITS['lights']['hard_max']}.")
        for idx in range(1, light_count + 1):
            key = f"light_slot_{idx}_entity"
            if _is_placeholder(substitutions.get(key, "")):
                errors.append(f"{key} is required when lights feature is enabled.")
    if _as_bool(features.get("weather"), False):
        for key in ["entity_wx_main", "entity_wx_temp_sensor"]:
            if _is_placeholder(substitutions.get(key, "")):
                errors.append(f"{key} is required when weather feature is enabled.")
    if _as_bool(features.get("climate"), False):
        for key in ["entity_sensi_climate", "entity_sensi_temperature_sensor"]:
            if _is_placeholder(substitutions.get(key, "")):
                errors.append(f"{key} is required when climate feature is enabled.")
    if _as_bool(features.get("cameras"), False):
        camera_count = _as_int(substitutions.get("camera_slot_count"), 0, 0, camera_cap)
        enabled_cameras = [x for x in cameras if _as_bool(x.get("enabled"), True)]
        if len(cameras) > ENTITY_COLLECTION_LIMITS["cameras"]["hard_max"]:
            errors.append(f"cameras collection exceeds hard limit {ENTITY_COLLECTION_LIMITS['cameras']['hard_max']}.")
        if len(enabled_cameras) == 0:
            warnings.append("cameras feature enabled but no enabled cameras in dynamic collections.")
        if len(enabled_cameras) > camera_cap:
            errors.append(
                f"enabled cameras ({len(enabled_cameras)}) exceed camera_slot_cap ({camera_cap}). Run auto-fit caps or disable rows."
            )
        if camera_count <= 0:
            warnings.append("Cameras feature is enabled but camera_slot_count is 0.")
        for idx in range(1, camera_count + 1):
            key = f"camera_slot_{idx}_entity"
            if _is_placeholder(substitutions.get(key, "")):
                errors.append(f"{key} is required when cameras feature is enabled.")
    if _as_bool(features.get("reader"), False):
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

    seen_instance_ids: set[str] = set()
    for idx, inst in enumerate(instances):
        if not isinstance(inst, dict):
            errors.append(f"entity_instances[{idx}] is not an object.")
            continue
        inst_id = _slugify(inst.get("id"), "")
        if not inst_id:
            errors.append(f"entity_instances[{idx}] missing id.")
            continue
        if inst_id in seen_instance_ids:
            warnings.append(f"entity_instances duplicate id '{inst_id}'.")
        seen_instance_ids.add(inst_id)
        type_id = _as_str(inst.get("type"), "").strip().lower()
        if type_id not in TYPE_REGISTRY:
            warnings.append(f"entity_instances[{idx}] uses unsupported type '{type_id}', expected one of core registry types.")
        entity_id = _as_str(inst.get("entity_id"), "").strip()
        if _as_bool(inst.get("enabled"), True) and _is_placeholder(entity_id):
            warnings.append(f"entity_instances[{idx}] enabled but entity_id is placeholder.")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "required_bindings": required_bindings,
        "required_bindings_summary": {
            "total": len(required_bindings),
            "resolved": len([x for x in required_bindings if _as_bool(x.get("resolved"), False)]),
            "unresolved": len([x for x in required_bindings if not _as_bool(x.get("resolved"), False)]),
        },
        "profile": p,
        "substitutions": substitutions,
    }


def _mapping_suggestions(
    key: str,
    query: str = "",
    limit: int = 12,
    collection: str = "",
    role: str = "",
    domain_hint: str = "",
    type_id: str = "",
    device_slug: str = "",
    exclude_entities: set[str] | None = None,
) -> List[Dict[str, Any]]:
    key = _as_str(key).strip()
    query = _as_str(query).strip().lower()
    role = _as_str(role).strip()
    collection = _as_str(collection).strip().lower()
    hint_domain = _as_str(domain_hint).strip().lower()
    hints = [x.lower() for x in DOMAIN_HINTS.get(key, [])]
    if role and role in DOMAIN_HINTS:
        hints.extend([x.lower() for x in DOMAIN_HINTS.get(role, [])])
    if collection == "lights":
        hints.append("light")
    elif collection == "cameras":
        hints.append("camera")
    elif collection == "climate_controls":
        hints.append("climate")
    elif collection == "weather_metrics":
        hints.extend(["weather", "sensor"])
    if hint_domain:
        hints.append(hint_domain)
    type_id = _as_str(type_id).strip().lower()
    scope_slug = _slugify(device_slug, "")
    scope_token = re.sub(r"[^a-z0-9]", "", scope_slug)
    if type_id in TYPE_REGISTRY:
        type_hints = TYPE_REGISTRY.get(type_id, {}).get("domains", [])
        if isinstance(type_hints, list):
            hints.extend([_as_str(x, "").lower() for x in type_hints if _as_str(x, "")])
    if not hints and key.startswith("entity_"):
        tail = key.replace("entity_", "", 1)
        if tail.startswith("wx_"):
            hints.extend(["weather", "sensor"])
        elif tail.startswith("sensi_"):
            hints.extend(["climate", "sensor", "number", "switch"])
    hints = sorted(set([h for h in hints if h]))
    cache = _discovery_cache_snapshot()
    rows = cache.get("rows", [])
    excluded = exclude_entities or set()

    scored: List[Tuple[int, str, Dict[str, Any]]] = []
    for row in rows:
        entity_id = _as_str(row.get("entity_id"))
        domain = _as_str(row.get("domain"))
        friendly = _as_str(row.get("friendly_name"))
        device_name = _as_str(row.get("device_name"))
        if entity_id and entity_id.lower() in excluded:
            continue
        row_blob = f"{entity_id} {friendly} {device_name}".lower()
        row_token = re.sub(r"[^a-z0-9]", "", row_blob)
        scope_match = not scope_token or scope_token in row_token
        if scope_token and not scope_match:
            continue
        score = 0
        reasons: List[str] = []
        if hints and domain in hints:
            score += 40
            reasons.append("domain-match")
        if query:
            if query in entity_id.lower():
                score += 35
                reasons.append("id-match")
            if query in friendly.lower():
                score += 25
                reasons.append("name-match")
        if role and role.lower() in entity_id.lower():
            score += 10
            reasons.append("role-hint")
        if "replace_me" in entity_id.lower():
            score -= 100
        if row.get("mappable"):
            score += 5
        if scope_token and scope_match:
            score += 18
            reasons.append("device-scope")
        if not query and hints:
            # Keep good-domain options even without text query.
            score += 3
        if score > 0:
            scored.append((score, ",".join(reasons) if reasons else "ranked", row))

    scored.sort(key=lambda x: (-x[0], _as_str(x[2].get("entity_id"))))
    out: List[Dict[str, Any]] = []
    for score, reason, row in scored[:limit]:
        out.append(
            {
                "score": score,
                "entity_id": _as_str(row.get("entity_id")),
                "friendly_name": _as_str(row.get("friendly_name")),
                "domain": _as_str(row.get("domain")),
                "state": _as_str(row.get("state")),
                "reason": reason,
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
    if not isinstance(ws.get("entity_instances"), dict):
        ws["entity_instances"] = {}
    ws["entity_collections"][slug] = _copy_obj(p.get("entity_collections", {}))
    ws["entity_instances"][slug] = _copy_obj(p.get("entity_instances", []))
    ws["device_workspace"] = {"devices": _copy_obj(ws.get("devices", []))}
    if not isinstance(ws.get("deployment_profile"), dict):
        ws["deployment_profile"] = _copy_obj(p.get("deployment_profile", {}))
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
        "generated_types_registry": g / "types.registry.yaml",
        "generated_entities_instances": g / "entities.instances.yaml",
        "generated_layout_pages": g / "layout.pages.yaml",
        "generated_theme_tokens": g / "theme.tokens.yaml",
        "generated_bindings_report": g / "bindings.report.yaml",
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


def _profile_signature(profile: Dict[str, Any]) -> str:
    try:
        normalized = _normalize_profile(profile)
    except Exception:
        normalized = profile if isinstance(profile, dict) else {}
    blob = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return _sha256_text(blob)


def _cleanup_preflight_tokens(now_ts: float | None = None) -> None:
    ts = now_ts if now_ts is not None else _now()
    stale: List[str] = []
    for token, row in _DEPLOY_PREFLIGHT_TOKENS.items():
        expires_at = float(row.get("expires_at", 0.0) or 0.0)
        if expires_at <= 0 or expires_at <= ts:
            stale.append(token)
    for token in stale:
        _DEPLOY_PREFLIGHT_TOKENS.pop(token, None)


def _issue_preflight_token(device_slug: str, profile_signature: str) -> str:
    safe_slug = _slugify(device_slug, "tdeck")
    nonce = f"{safe_slug}:{profile_signature}:{_now()}:{os.urandom(8).hex()}"
    token = hashlib.sha256(nonce.encode("utf-8")).hexdigest()
    with _DEPLOY_PREFLIGHT_LOCK:
        _cleanup_preflight_tokens(_now())
        _DEPLOY_PREFLIGHT_TOKENS[token] = {
            "device_slug": safe_slug,
            "profile_signature": profile_signature,
            "issued_at": _now(),
            "expires_at": _now() + DEPLOY_PREFLIGHT_TTL_SECONDS,
        }
    return token


def _verify_preflight_token(token: str, device_slug: str, profile_signature: str) -> Tuple[bool, str]:
    raw = _as_str(token, "").strip()
    if not raw:
        return False, "missing_preflight_token"
    safe_slug = _slugify(device_slug, "tdeck")
    with _DEPLOY_PREFLIGHT_LOCK:
        _cleanup_preflight_tokens(_now())
        row = _DEPLOY_PREFLIGHT_TOKENS.get(raw)
        if not isinstance(row, dict):
            return False, "invalid_or_expired_preflight_token"
        if _slugify(row.get("device_slug"), "tdeck") != safe_slug:
            return False, "preflight_token_device_mismatch"
        if _as_str(row.get("profile_signature"), "") != _as_str(profile_signature, ""):
            return False, "preflight_token_profile_changed"
    return True, ""

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


def _build_generated_types_registry_yaml(profile: Dict[str, Any]) -> str:
    p = _normalize_profile(profile)
    registry = p.get("type_registry", {}) if isinstance(p.get("type_registry"), dict) else _default_type_registry()
    lines: List[str] = [
        "# Auto-generated by T-Deck Admin Center. Do not hand-edit.",
        "type_registry:",
    ]
    for type_id in CORE_TYPE_IDS:
        item = registry.get(type_id, {}) if isinstance(registry.get(type_id), dict) else {}
        domains = item.get("domains", []) if isinstance(item.get("domains"), list) else []
        controls = item.get("controls", []) if isinstance(item.get("controls"), list) else []
        lines.append(f"  {type_id}:")
        lines.append(f"    label: {_q(_as_str(item.get('label'), type_id.title()))}")
        lines.append(f"    icon: {_q(_as_str(item.get('icon'), 'shape'))}")
        lines.append(f"    collection: {_q(_as_str(item.get('collection'), 'system_entities'))}")
        lines.append(f"    domains: [{', '.join(_q_single(x) for x in domains)}]")
        lines.append(f"    controls: [{', '.join(_q_single(x) for x in controls)}]")
    return "\n".join(lines)


def _build_generated_entities_instances_yaml(profile: Dict[str, Any]) -> str:
    p = _normalize_profile(profile)
    instances = p.get("entity_instances", []) if isinstance(p.get("entity_instances"), list) else []
    lines: List[str] = [
        "# Auto-generated by T-Deck Admin Center. Do not hand-edit.",
        f"generated_entities_instances_revision: {_q(str(int(_now())))}",
        "entity_instances:",
    ]
    for row in instances:
        if not isinstance(row, dict):
            continue
        lines.append("  -")
        lines.append(f"    id: {_q(_as_str(row.get('id'), ''))}")
        lines.append(f"    type: {_q(_as_str(row.get('type'), 'sensor'))}")
        lines.append(f"    name: {_q(_as_str(row.get('name'), ''))}")
        lines.append(f"    entity_id: {_q(_as_str(row.get('entity_id'), ''))}")
        lines.append(f"    role: {_q(_as_str(row.get('role'), ''))}")
        lines.append(f"    enabled: {'true' if _as_bool(row.get('enabled'), True) else 'false'}")
        lines.append(f"    page: {_q(_as_str(row.get('page'), 'home'))}")
        lines.append(f"    section: {_q(_as_str(row.get('section'), 'content'))}")
        lines.append(f"    icon: {_q(_as_str(row.get('icon'), 'shape'))}")
    return "\n".join(lines)


def _build_generated_layout_pages_yaml(profile: Dict[str, Any], workspace: Dict[str, Any]) -> str:
    val = _validate_layout_pages(workspace.get("layout_pages", {}))
    lines: List[str] = [
        "# Auto-generated by T-Deck Admin Center. Do not hand-edit.",
        f"generated_layout_pages_revision: {_q(str(int(_now())))}",
        "layout_pages:",
    ]
    for page_id, page in (val.get("pages", {}) or {}).items():
        if not isinstance(page, dict):
            continue
        grid = page.get("grid", {}) if isinstance(page.get("grid"), dict) else {}
        sections = page.get("sections", []) if isinstance(page.get("sections"), list) else []
        lines.append(f"  {page_id}:")
        lines.append(f"    grid:")
        lines.append(f"      cols: {_as_int(grid.get('cols'), LAYOUT_GRID_DEFAULTS['cols'], 1, 12)}")
        lines.append(f"      rows: {_as_int(grid.get('rows'), LAYOUT_GRID_DEFAULTS['rows'], 1, 20)}")
        lines.append("    sections:")
        for sec in sections:
            if not isinstance(sec, dict):
                continue
            lines.append("      -")
            lines.append(f"        id: {_q(_as_str(sec.get('id'), 'section'))}")
            lines.append(f"        x: {_as_int(sec.get('x'), 0, 0, None)}")
            lines.append(f"        y: {_as_int(sec.get('y'), 0, 0, None)}")
            lines.append(f"        w: {_as_int(sec.get('w'), 1, 1, None)}")
            lines.append(f"        h: {_as_int(sec.get('h'), 1, 1, None)}")
    if not val.get("ok"):
        lines.append("# validation_errors:")
        for err in val.get("errors", []):
            lines.append(f"# - {err}")
    return "\n".join(lines)


def _build_generated_theme_tokens_yaml(profile: Dict[str, Any]) -> str:
    p = _normalize_profile(profile)
    theme = p.get("theme", {}) if isinstance(p.get("theme"), dict) else {}
    defaults = _default_substitutions()
    lines: List[str] = [
        "# Auto-generated by T-Deck Admin Center. Do not hand-edit.",
        "theme_tokens:",
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
    ]:
        lines.append(f"  {key}: {_q(_as_str(theme.get(key), defaults.get(key, '0x000000')))}")
    lines.append(f"  theme_border_width: {_q(_as_str(theme.get('theme_border_width'), defaults.get('theme_border_width', '2')))}")
    lines.append(f"  theme_radius: {_q(_as_str(theme.get('theme_radius'), defaults.get('theme_radius', '10')))}")
    lines.append(f"  theme_icon_mode: {_q(_as_str(theme.get('theme_icon_mode'), defaults.get('theme_icon_mode', '0')))}")
    return "\n".join(lines)


def _build_generated_bindings_report_yaml(profile: Dict[str, Any]) -> str:
    p = _normalize_profile(profile)
    subs = _profile_to_substitutions(p)
    required = _required_bindings_snapshot(p, subs)
    features = p.get("features", {}) if isinstance(p.get("features"), dict) else {}
    lines: List[str] = [
        "# Auto-generated by T-Deck Admin Center. Do not hand-edit.",
        "bindings_report:",
        f"  generated_at_epoch: {_q(str(int(_now())))}",
        f"  schema_version: {_q(PROFILE_SCHEMA_VERSION)}",
        f"  device_slug: {_q(_managed_device_slug(p))}",
        "  enabled_features:",
    ]
    enabled_features = [k for k in sorted(features.keys()) if _as_bool(features.get(k), False)]
    if enabled_features:
        for key in enabled_features:
            lines.append(f"    - {_q(key)}")
    else:
        lines.append(f"    - {_q('none')}")
    lines.append("  required_bindings:")
    for row in required:
        lines.extend(
            [
                f"    - feature: {_q(_as_str(row.get('feature'), ''))}",
                f"      key: {_q(_as_str(row.get('key'), ''))}",
                f"      resolved: {_bool_str(row.get('resolved'))}",
                f"      value: {_q(_as_str(row.get('value'), ''))}",
                f"      suggested_value: {_q(_as_str(row.get('suggested_value'), ''))}",
                f"      suggestion_reason: {_q(_as_str(row.get('suggestion_reason'), ''))}",
            ]
        )
    return "\n".join(lines)


def _build_generated_entities_yaml(profile: Dict[str, Any]) -> str:
    p = _normalize_profile(profile)
    collections = p.get("entity_collections", {}) if isinstance(p.get("entity_collections"), dict) else {}
    lights = collections.get("lights", []) if isinstance(collections.get("lights"), list) else []
    cameras = collections.get("cameras", []) if isinstance(collections.get("cameras"), list) else []
    slot_runtime = _normalize_slot_runtime(p.get("slot_runtime"))
    lines: List[str] = [
        "# Auto-generated by T-Deck Admin Center. Do not hand-edit.",
        "substitutions:",
        f"  generated_entities_revision: {_q(str(int(_now())))}",
        f"  generated_light_count_total: {_q(str(len(lights)))}",
        f"  generated_camera_count_total: {_q(str(len(cameras)))}",
        f"  generated_light_slot_cap: {_q(str(slot_runtime.get('light_slot_cap', SLOT_RUNTIME_LIMITS['lights']['default_cap'])))}",
        f"  generated_camera_slot_cap: {_q(str(slot_runtime.get('camera_slot_cap', SLOT_RUNTIME_LIMITS['cameras']['default_cap'])))}",
        f"  generated_light_page_size: {_q(str(slot_runtime.get('light_page_size', SLOT_RUNTIME_LIMITS['lights']['default_page_size'])))}",
        f"  generated_camera_page_size: {_q(str(slot_runtime.get('camera_page_size', SLOT_RUNTIME_LIMITS['cameras']['default_page_size'])))}",
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
    generated_types_registry_new = _build_generated_types_registry_yaml(profile)
    generated_entities_instances_new = _build_generated_entities_instances_yaml(profile)
    generated_layout_pages_new = _build_generated_layout_pages_yaml(profile, workspace)
    generated_theme_tokens_new = _build_generated_theme_tokens_yaml(profile)
    generated_bindings_report_new = _build_generated_bindings_report_yaml(profile)
    generated_entities_new = _build_generated_entities_yaml(profile)
    generated_theme_new = _build_generated_theme_yaml(profile)
    generated_layout_new = _build_generated_layout_yaml(profile, workspace)
    generated_page_home_new = _build_generated_page_yaml("home", workspace, profile)
    generated_page_lights_new = _build_generated_page_yaml("lights", workspace, profile)
    generated_page_weather_new = _build_generated_page_yaml("weather", workspace, profile)
    generated_page_climate_new = _build_generated_page_yaml("climate", workspace, profile)

    install_cur = _read_text(paths["install"])
    overrides_cur = _read_text(paths["overrides"])
    generated_types_registry_cur = _read_text(paths["generated_types_registry"])
    generated_entities_instances_cur = _read_text(paths["generated_entities_instances"])
    generated_layout_pages_cur = _read_text(paths["generated_layout_pages"])
    generated_theme_tokens_cur = _read_text(paths["generated_theme_tokens"])
    generated_bindings_report_cur = _read_text(paths["generated_bindings_report"])
    generated_entities_cur = _read_text(paths["generated_entities"])
    generated_theme_cur = _read_text(paths["generated_theme"])
    generated_layout_cur = _read_text(paths["generated_layout"])
    generated_page_home_cur = _read_text(paths["generated_page_home"])
    generated_page_lights_cur = _read_text(paths["generated_page_lights"])
    generated_page_weather_cur = _read_text(paths["generated_page_weather"])
    generated_page_climate_cur = _read_text(paths["generated_page_climate"])

    install_changed = install_cur != install_new
    overrides_changed = overrides_cur != overrides_new
    generated_types_registry_changed = generated_types_registry_cur != generated_types_registry_new
    generated_entities_instances_changed = generated_entities_instances_cur != generated_entities_instances_new
    generated_layout_pages_changed = generated_layout_pages_cur != generated_layout_pages_new
    generated_theme_tokens_changed = generated_theme_tokens_cur != generated_theme_tokens_new
    generated_bindings_report_changed = generated_bindings_report_cur != generated_bindings_report_new
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
            "types_registry": {
                "path": str(paths["generated_types_registry"]),
                "changed": generated_types_registry_changed,
                "checksum_current": _sha256_text(generated_types_registry_cur) if generated_types_registry_cur else "",
                "checksum_new": _sha256_text(generated_types_registry_new),
                "diff": _unified_diff(generated_types_registry_cur, generated_types_registry_new, f"{paths['generated_types_registry']} (current)", f"{paths['generated_types_registry']} (new)") if generated_types_registry_changed else "",
                "content_new": generated_types_registry_new,
            },
            "entities_instances": {
                "path": str(paths["generated_entities_instances"]),
                "changed": generated_entities_instances_changed,
                "checksum_current": _sha256_text(generated_entities_instances_cur) if generated_entities_instances_cur else "",
                "checksum_new": _sha256_text(generated_entities_instances_new),
                "diff": _unified_diff(generated_entities_instances_cur, generated_entities_instances_new, f"{paths['generated_entities_instances']} (current)", f"{paths['generated_entities_instances']} (new)") if generated_entities_instances_changed else "",
                "content_new": generated_entities_instances_new,
            },
            "layout_pages": {
                "path": str(paths["generated_layout_pages"]),
                "changed": generated_layout_pages_changed,
                "checksum_current": _sha256_text(generated_layout_pages_cur) if generated_layout_pages_cur else "",
                "checksum_new": _sha256_text(generated_layout_pages_new),
                "diff": _unified_diff(generated_layout_pages_cur, generated_layout_pages_new, f"{paths['generated_layout_pages']} (current)", f"{paths['generated_layout_pages']} (new)") if generated_layout_pages_changed else "",
                "content_new": generated_layout_pages_new,
            },
            "theme_tokens": {
                "path": str(paths["generated_theme_tokens"]),
                "changed": generated_theme_tokens_changed,
                "checksum_current": _sha256_text(generated_theme_tokens_cur) if generated_theme_tokens_cur else "",
                "checksum_new": _sha256_text(generated_theme_tokens_new),
                "diff": _unified_diff(generated_theme_tokens_cur, generated_theme_tokens_new, f"{paths['generated_theme_tokens']} (current)", f"{paths['generated_theme_tokens']} (new)") if generated_theme_tokens_changed else "",
                "content_new": generated_theme_tokens_new,
            },
            "bindings_report": {
                "path": str(paths["generated_bindings_report"]),
                "changed": generated_bindings_report_changed,
                "checksum_current": _sha256_text(generated_bindings_report_cur) if generated_bindings_report_cur else "",
                "checksum_new": _sha256_text(generated_bindings_report_new),
                "diff": _unified_diff(generated_bindings_report_cur, generated_bindings_report_new, f"{paths['generated_bindings_report']} (current)", f"{paths['generated_bindings_report']} (new)") if generated_bindings_report_changed else "",
                "content_new": generated_bindings_report_new,
            },
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


def _commit_managed_preview(
    preview: Dict[str, Any],
    profile: Dict[str, Any],
    workspace: Dict[str, Any],
    reason: str = "apply_commit",
    context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    device_slug = _as_str(preview.get("device_slug"), "").strip()
    if not device_slug:
        raise ValueError("preview.device_slug is required")
    backup = _backup_files(
        device_slug,
        preview,
        profile,
        workspace,
        reason=reason,
        context=context if isinstance(context, dict) else {},
    )
    install_path = Path(_as_str(preview.get("install", {}).get("path"), ""))
    overrides_path = Path(_as_str(preview.get("overrides", {}).get("path"), ""))
    if not install_path or not overrides_path:
        raise ValueError("preview install/overrides paths are required")

    generated_types_registry_raw = _as_str(preview.get("generated", {}).get("types_registry", {}).get("path", ""))
    generated_entities_instances_raw = _as_str(preview.get("generated", {}).get("entities_instances", {}).get("path", ""))
    generated_layout_pages_raw = _as_str(preview.get("generated", {}).get("layout_pages", {}).get("path", ""))
    generated_theme_tokens_raw = _as_str(preview.get("generated", {}).get("theme_tokens", {}).get("path", ""))
    generated_bindings_report_raw = _as_str(preview.get("generated", {}).get("bindings_report", {}).get("path", ""))
    generated_entities_raw = _as_str(preview.get("generated", {}).get("entities", {}).get("path", ""))
    generated_theme_raw = _as_str(preview.get("generated", {}).get("theme", {}).get("path", ""))
    generated_layout_raw = _as_str(preview.get("generated", {}).get("layout", {}).get("path", ""))
    generated_page_home_raw = _as_str(preview.get("generated", {}).get("page_home", {}).get("path", ""))
    generated_page_lights_raw = _as_str(preview.get("generated", {}).get("page_lights", {}).get("path", ""))
    generated_page_weather_raw = _as_str(preview.get("generated", {}).get("page_weather", {}).get("path", ""))
    generated_page_climate_raw = _as_str(preview.get("generated", {}).get("page_climate", {}).get("path", ""))

    generated_types_registry_path = Path(generated_types_registry_raw) if generated_types_registry_raw else None
    generated_entities_instances_path = Path(generated_entities_instances_raw) if generated_entities_instances_raw else None
    generated_layout_pages_path = Path(generated_layout_pages_raw) if generated_layout_pages_raw else None
    generated_theme_tokens_path = Path(generated_theme_tokens_raw) if generated_theme_tokens_raw else None
    generated_bindings_report_path = Path(generated_bindings_report_raw) if generated_bindings_report_raw else None
    generated_entities_path = Path(generated_entities_raw) if generated_entities_raw else None
    generated_theme_path = Path(generated_theme_raw) if generated_theme_raw else None
    generated_layout_path = Path(generated_layout_raw) if generated_layout_raw else None
    generated_page_home_path = Path(generated_page_home_raw) if generated_page_home_raw else None
    generated_page_lights_path = Path(generated_page_lights_raw) if generated_page_lights_raw else None
    generated_page_weather_path = Path(generated_page_weather_raw) if generated_page_weather_raw else None
    generated_page_climate_path = Path(generated_page_climate_raw) if generated_page_climate_raw else None

    install_path.parent.mkdir(parents=True, exist_ok=True)
    overrides_path.parent.mkdir(parents=True, exist_ok=True)
    install_path.write_text(_as_str(preview.get("install", {}).get("content_new"), ""), encoding="utf-8")
    overrides_path.write_text(_as_str(preview.get("overrides", {}).get("content_new"), ""), encoding="utf-8")

    write_pairs: List[Tuple[Path | None, str]] = [
        (generated_types_registry_path, _as_str(preview.get("generated", {}).get("types_registry", {}).get("content_new"), "")),
        (generated_entities_instances_path, _as_str(preview.get("generated", {}).get("entities_instances", {}).get("content_new"), "")),
        (generated_layout_pages_path, _as_str(preview.get("generated", {}).get("layout_pages", {}).get("content_new"), "")),
        (generated_theme_tokens_path, _as_str(preview.get("generated", {}).get("theme_tokens", {}).get("content_new"), "")),
        (generated_bindings_report_path, _as_str(preview.get("generated", {}).get("bindings_report", {}).get("content_new"), "")),
        (generated_entities_path, _as_str(preview.get("generated", {}).get("entities", {}).get("content_new"), "")),
        (generated_theme_path, _as_str(preview.get("generated", {}).get("theme", {}).get("content_new"), "")),
        (generated_layout_path, _as_str(preview.get("generated", {}).get("layout", {}).get("content_new"), "")),
        (generated_page_home_path, _as_str(preview.get("generated", {}).get("page_home", {}).get("content_new"), "")),
        (generated_page_lights_path, _as_str(preview.get("generated", {}).get("page_lights", {}).get("content_new"), "")),
        (generated_page_weather_path, _as_str(preview.get("generated", {}).get("page_weather", {}).get("content_new"), "")),
        (generated_page_climate_path, _as_str(preview.get("generated", {}).get("page_climate", {}).get("content_new"), "")),
    ]
    for path, content in write_pairs:
        if path is None:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    return {
        "device_slug": device_slug,
        "managed_root": str(MANAGED_ROOT),
        "paths": {
            "install": str(install_path),
            "overrides": str(overrides_path),
            "generated_types_registry": str(generated_types_registry_path) if generated_types_registry_path else "",
            "generated_entities_instances": str(generated_entities_instances_path) if generated_entities_instances_path else "",
            "generated_layout_pages": str(generated_layout_pages_path) if generated_layout_pages_path else "",
            "generated_theme_tokens": str(generated_theme_tokens_path) if generated_theme_tokens_path else "",
            "generated_bindings_report": str(generated_bindings_report_path) if generated_bindings_report_path else "",
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
            "generated_types_registry": _sha256_file(generated_types_registry_path),
            "generated_entities_instances": _sha256_file(generated_entities_instances_path),
            "generated_layout_pages": _sha256_file(generated_layout_pages_path),
            "generated_theme_tokens": _sha256_file(generated_theme_tokens_path),
            "generated_bindings_report": _sha256_file(generated_bindings_report_path),
            "generated_entities": _sha256_file(generated_entities_path),
            "generated_theme": _sha256_file(generated_theme_path),
            "generated_layout": _sha256_file(generated_layout_path),
            "generated_page_home": _sha256_file(generated_page_home_path),
            "generated_page_lights": _sha256_file(generated_page_lights_path),
            "generated_page_weather": _sha256_file(generated_page_weather_path),
            "generated_page_climate": _sha256_file(generated_page_climate_path),
        },
        "backup": backup,
        "changed": {
            "install": _as_bool(preview.get("install", {}).get("changed"), False),
            "overrides": _as_bool(preview.get("overrides", {}).get("changed"), False),
            "generated_types_registry": _as_bool(preview.get("generated", {}).get("types_registry", {}).get("changed"), False),
            "generated_entities_instances": _as_bool(preview.get("generated", {}).get("entities_instances", {}).get("changed"), False),
            "generated_layout_pages": _as_bool(preview.get("generated", {}).get("layout_pages", {}).get("changed"), False),
            "generated_theme_tokens": _as_bool(preview.get("generated", {}).get("theme_tokens", {}).get("changed"), False),
            "generated_bindings_report": _as_bool(preview.get("generated", {}).get("bindings_report", {}).get("changed"), False),
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
    generated_types_registry_file = paths["generated_types_registry"]
    generated_entities_instances_file = paths["generated_entities_instances"]
    generated_layout_pages_file = paths["generated_layout_pages"]
    generated_theme_tokens_file = paths["generated_theme_tokens"]
    generated_bindings_report_file = paths["generated_bindings_report"]
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
    if generated_types_registry_file.exists():
        shutil.copy2(generated_types_registry_file, snapshot / "types.registry.yaml")
    if generated_entities_instances_file.exists():
        shutil.copy2(generated_entities_instances_file, snapshot / "entities.instances.yaml")
    if generated_layout_pages_file.exists():
        shutil.copy2(generated_layout_pages_file, snapshot / "layout.pages.yaml")
    if generated_theme_tokens_file.exists():
        shutil.copy2(generated_theme_tokens_file, snapshot / "theme.tokens.yaml")
    if generated_bindings_report_file.exists():
        shutil.copy2(generated_bindings_report_file, snapshot / "bindings.report.yaml")
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
            "generated_types_registry_before": preview.get("generated", {}).get("types_registry", {}).get("checksum_current", ""),
            "generated_entities_instances_before": preview.get("generated", {}).get("entities_instances", {}).get("checksum_current", ""),
            "generated_layout_pages_before": preview.get("generated", {}).get("layout_pages", {}).get("checksum_current", ""),
            "generated_theme_tokens_before": preview.get("generated", {}).get("theme_tokens", {}).get("checksum_current", ""),
            "generated_bindings_report_before": preview.get("generated", {}).get("bindings_report", {}).get("checksum_current", ""),
            "generated_entities_before": preview.get("generated", {}).get("entities", {}).get("checksum_current", ""),
            "generated_theme_before": preview.get("generated", {}).get("theme", {}).get("checksum_current", ""),
            "generated_layout_before": preview.get("generated", {}).get("layout", {}).get("checksum_current", ""),
            "generated_entities_after": preview.get("generated", {}).get("entities", {}).get("checksum_new", ""),
            "generated_theme_after": preview.get("generated", {}).get("theme", {}).get("checksum_new", ""),
            "generated_layout_after": preview.get("generated", {}).get("layout", {}).get("checksum_new", ""),
            "generated_types_registry_after": preview.get("generated", {}).get("types_registry", {}).get("checksum_new", ""),
            "generated_entities_instances_after": preview.get("generated", {}).get("entities_instances", {}).get("checksum_new", ""),
            "generated_layout_pages_after": preview.get("generated", {}).get("layout_pages", {}).get("checksum_new", ""),
            "generated_theme_tokens_after": preview.get("generated", {}).get("theme_tokens", {}).get("checksum_new", ""),
            "generated_bindings_report_after": preview.get("generated", {}).get("bindings_report", {}).get("checksum_new", ""),
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
            "generated_types_registry": str(generated_types_registry_file),
            "generated_entities_instances": str(generated_entities_instances_file),
            "generated_layout_pages": str(generated_layout_pages_file),
            "generated_theme_tokens": str(generated_theme_tokens_file),
            "generated_bindings_report": str(generated_bindings_report_file),
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
                "has_generated_types_registry": (p / "types.registry.yaml").exists(),
                "has_generated_entities_instances": (p / "entities.instances.yaml").exists(),
                "has_generated_layout_pages": (p / "layout.pages.yaml").exists(),
                "has_generated_theme_tokens": (p / "theme.tokens.yaml").exists(),
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
    generated_types_registry_src = target / "types.registry.yaml"
    generated_entities_instances_src = target / "entities.instances.yaml"
    generated_layout_pages_src = target / "layout.pages.yaml"
    generated_theme_tokens_src = target / "theme.tokens.yaml"
    generated_bindings_report_src = target / "bindings.report.yaml"
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
        "generated_types_registry": False,
        "generated_entities_instances": False,
        "generated_layout_pages": False,
        "generated_theme_tokens": False,
        "generated_bindings_report": False,
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
    if generated_types_registry_src.exists():
        shutil.copy2(generated_types_registry_src, paths["generated_types_registry"])
        restored["generated_types_registry"] = True
    if generated_entities_instances_src.exists():
        shutil.copy2(generated_entities_instances_src, paths["generated_entities_instances"])
        restored["generated_entities_instances"] = True
    if generated_layout_pages_src.exists():
        shutil.copy2(generated_layout_pages_src, paths["generated_layout_pages"])
        restored["generated_layout_pages"] = True
    if generated_theme_tokens_src.exists():
        shutil.copy2(generated_theme_tokens_src, paths["generated_theme_tokens"])
        restored["generated_theme_tokens"] = True
    if generated_bindings_report_src.exists():
        shutil.copy2(generated_bindings_report_src, paths["generated_bindings_report"])
        restored["generated_bindings_report"] = True
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
            "generated_types_registry": str(paths["generated_types_registry"]),
            "generated_entities_instances": str(paths["generated_entities_instances"]),
            "generated_layout_pages": str(paths["generated_layout_pages"]),
            "generated_theme_tokens": str(paths["generated_theme_tokens"]),
            "generated_bindings_report": str(paths["generated_bindings_report"]),
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
            "generated_types_registry": _sha256_file(paths["generated_types_registry"]),
            "generated_entities_instances": _sha256_file(paths["generated_entities_instances"]),
            "generated_layout_pages": _sha256_file(paths["generated_layout_pages"]),
            "generated_theme_tokens": _sha256_file(paths["generated_theme_tokens"]),
            "generated_bindings_report": _sha256_file(paths["generated_bindings_report"]),
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
                "  # Typed generated artifacts are managed for Admin Center and backups,",
                "  # but not injected into ESPHome packages because they are not compile-schema keys.",
                "  # See generated/types.registry.yaml, generated/entities.instances.yaml,",
                "  # generated/layout.pages.yaml, generated/theme.tokens.yaml, generated/bindings.report.yaml.",
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
        "ota_supported": bool(esphome_install_available or native_available),
        "usb_required": not bool(esphome_install_available or native_available),
        "expected_usb_flow_steps": [
            "Connect T-Deck Plus via USB.",
            "Install once over serial from managed install YAML.",
            "Switch to OTA updates from Admin Center.",
        ]
        if not bool(esphome_install_available or native_available)
        else [],
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
    selected_service_refs = {
        "compile": _as_str(capabilities.get("esphome_compile_service"), ""),
        "install": _as_str(capabilities.get("esphome_install_service"), ""),
        "native_update": "update.install",
    }
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
    manual_fallback_reason = ""
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
                        manual_fallback_reason = "compile_service_failed"
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
                        manual_fallback_reason = "install_service_failed"
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
                manual_fallback_reason = "native_update_service_failed"
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
            if not manual_fallback_reason:
                manual_fallback_reason = "automatic_methods_unavailable"

        status = _firmware_status_for(
            device_slug=device_slug,
            target_version=target_version,
            native_firmware_entity=native_firmware_entity,
            app_version_entity=app_version_entity,
            capabilities=capabilities,
            selected_method=selected_method,
            legacy_imported=_as_str(settings.get("installed_version_status"), "").strip().lower() == "legacy_unknown",
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
            "attempt_matrix": actions_attempted,
            "selected_service_refs": selected_service_refs,
            "backup": backup or {},
            "status": status,
            "summary": summary,
            "manual_next_steps": manual_next_steps,
            "manual_fallback_reason": manual_fallback_reason,
            "next_steps": manual_next_steps,
            "first_flash_path": {
                "usb_required": not _as_bool(capabilities.get("has_any_automatic_method"), False),
                "expected_usb_flow_steps": [
                    "Connect T-Deck Plus over USB.",
                    "Run ESPHome install over serial for the managed install YAML.",
                    "Return to Admin Center for OTA updates.",
                ]
                if not _as_bool(capabilities.get("has_any_automatic_method"), False)
                else [],
            },
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
            "attempt_matrix": actions_attempted,
            "selected_service_refs": selected_service_refs,
            "capabilities": capabilities,
            "manual_fallback_reason": "workflow_exception",
            "next_steps": [],
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
    legacy_imported: bool = False,
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
        status_text = "unknown_legacy_imported" if legacy_imported else "unknown_legacy"
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
            "required_bindings": result.get("required_bindings", []),
            "required_bindings_summary": result.get("required_bindings_summary", {}),
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


def _ha_get_optional(path: str, timeout: int = 15) -> Any:
    try:
        return _ha_get(path, timeout=timeout)
    except Exception:
        return None


def _detect_slug_hints_from_entity(entity_id: str) -> List[Tuple[str, int, str]]:
    if "." not in entity_id:
        return []
    object_id = entity_id.split(".", 1)[1]
    hints: List[Tuple[str, int, str]] = []
    if entity_id.startswith("update.") and entity_id.endswith("_firmware"):
        hints.append((_slugify(object_id[: -len("_firmware")], ""), 95, "native_firmware_entity"))
    if entity_id.startswith("sensor.") and entity_id.endswith("_app_version"):
        hints.append((_slugify(object_id[: -len("_app_version")], ""), 90, "app_version_entity"))
    parts = [x for x in object_id.split("_") if x]
    if parts:
        first = _slugify(parts[0], "")
        if first:
            hints.append((first, 8, "object_prefix"))
        if len(parts) >= 2:
            hints.append((_slugify(f"{parts[0]}_{parts[1]}", ""), 6, "object_prefix_pair"))
    return hints


def _confidence_label(score: int) -> str:
    if score >= 120:
        return "high"
    if score >= 70:
        return "medium"
    return "low"


def _candidate_source_groups(node: Dict[str, Any]) -> List[str]:
    reasons = node.get("reasons", []) if isinstance(node.get("reasons"), list) else []
    sources: List[str] = []
    if any(str(x).startswith("device_registry:") or str(x).startswith("integration:esphome") for x in reasons):
        sources.append("device_registry_esphome")
    if _as_str(node.get("native_update_entity"), "") or any(str(x) == "native_firmware_entity" for x in reasons):
        sources.append("update_entity_pattern")
    if _as_str(node.get("app_version_entity"), "") or any(str(x) == "app_version_entity" for x in reasons):
        sources.append("app_version_sensor_pattern")
    if node.get("matched_entities") and isinstance(node.get("matched_entities"), list):
        sources.append("entity_registry_linked")
    if not sources:
        sources.append("heuristic")
    return sorted(set(sources))


def _group_candidates_by_source(nodes: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    groups: Dict[str, List[Dict[str, Any]]] = {
        "device_registry_esphome": [],
        "update_entity_pattern": [],
        "app_version_sensor_pattern": [],
        "entity_registry_linked": [],
        "heuristic": [],
    }
    for row in nodes:
        if not isinstance(row, dict):
            continue
        for source in _candidate_source_groups(row):
            groups.setdefault(source, [])
            groups[source].append(
                {
                    "device_slug": _as_str(row.get("device_slug"), ""),
                    "friendly_name": _as_str(row.get("friendly_name"), ""),
                    "confidence": _as_str(row.get("confidence"), "low"),
                    "confidence_score": _as_int(row.get("confidence_score"), 0, 0, None),
                }
            )
    return groups


def _manual_candidate_from_input(device_slug: str, entity_id: str) -> Dict[str, Any]:
    slug = _slugify(device_slug, "")
    ent = _as_str(entity_id, "").strip().lower()
    if not slug and ent and "." in ent:
        object_id = ent.split(".", 1)[1]
        if object_id.endswith("_firmware"):
            slug = _slugify(object_id[: -len("_firmware")], "")
        elif object_id.endswith("_app_version"):
            slug = _slugify(object_id[: -len("_app_version")], "")
        else:
            parts = [x for x in object_id.split("_") if x]
            if len(parts) >= 2:
                slug = _slugify(f"{parts[0]}_{parts[1]}", "")
            elif parts:
                slug = _slugify(parts[0], "")
    slug = _slugify(slug, "lilygo-tdeck-plus")
    native = f"update.{slug}_firmware"
    app_ver = f"sensor.{slug}_app_version"
    reasons = ["manual_fallback"]
    matched: List[str] = []
    if ent:
        matched.append(ent)
        if ent.startswith("update.") and ent.endswith("_firmware"):
            native = ent
            if "native_firmware_entity" not in reasons:
                reasons.append("native_firmware_entity")
        if ent.startswith("sensor.") and ent.endswith("_app_version"):
            app_ver = ent
            if "app_version_entity" not in reasons:
                reasons.append("app_version_entity")
    return {
        "device_slug": slug,
        "native_update_entity": native,
        "app_version_entity": app_ver,
        "friendly_name": f"T-Deck ({slug})",
        "entities_count": 1 if ent else 0,
        "confidence_score": 52 if ent else 45,
        "confidence": "medium",
        "reasons": reasons,
        "matched_entities": matched,
        "source_groups": ["heuristic"],
    }


def _detect_esphome_nodes(force_refresh: bool = False) -> List[Dict[str, Any]]:
    cache = _refresh_discovery_cache(force=force_refresh)
    rows = cache.get("rows", []) if isinstance(cache.get("rows"), list) else []
    entity_registry = _ha_get_optional("/config/entity_registry/list", timeout=25)
    device_registry = _ha_get_optional("/config/device_registry/list", timeout=25)
    config_entries = _ha_get_optional("/config/config_entries/entry", timeout=25)
    by_entity: Dict[str, Dict[str, Any]] = {}
    by_device_entities: Dict[str, List[str]] = {}
    if isinstance(entity_registry, list):
        for row in entity_registry:
            if not isinstance(row, dict):
                continue
            entity_id = _as_str(row.get("entity_id"), "")
            if entity_id:
                by_entity[entity_id] = row
            device_id = _as_str(row.get("device_id"), "")
            if device_id and entity_id:
                by_device_entities.setdefault(device_id, []).append(entity_id)
    by_device: Dict[str, Dict[str, Any]] = {}
    if isinstance(device_registry, list):
        for row in device_registry:
            if not isinstance(row, dict):
                continue
            did = _as_str(row.get("id"), "")
            if did:
                by_device[did] = row
    by_entry: Dict[str, Dict[str, Any]] = {}
    if isinstance(config_entries, list):
        for row in config_entries:
            if not isinstance(row, dict):
                continue
            eid = _as_str(row.get("entry_id"), "")
            if eid:
                by_entry[eid] = row
    esphome_entry_ids: set[str] = set()
    for eid, entry in by_entry.items():
        if _as_str(entry.get("domain"), "").strip().lower() == "esphome":
            esphome_entry_ids.add(eid)

    stoplist = {
        "sensor",
        "switch",
        "binary",
        "button",
        "number",
        "select",
        "text",
        "input",
        "weather",
        "climate",
        "media",
        "camera",
        "cover",
        "light",
        "fan",
        "lock",
        "home",
        "assistant",
    }
    found: Dict[str, Dict[str, Any]] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue
        entity_id = _as_str(row.get("entity_id"), "")
        if not entity_id:
            continue
        friendly = _as_str(row.get("friendly_name"), entity_id)
        lower_blob = f"{entity_id} {friendly} {_as_str(row.get('device_name'), '')}".lower()
        mentions_tdeck = any(k in lower_blob for k in NODE_KEYWORDS)
        attrs_integration = _as_str(row.get("integration"), "").strip().lower()
        reg = by_entity.get(entity_id, {})
        config_entry = by_entry.get(_as_str(reg.get("config_entry_id"), ""), {})
        config_domain = _as_str(config_entry.get("domain"), "").strip().lower()
        did = _as_str(reg.get("device_id"), "")
        dev = by_device.get(did, {})
        manufacturer = _as_str(dev.get("manufacturer"), "")
        model = _as_str(dev.get("model"), "")
        dev_name = _as_str(dev.get("name_by_user"), "") or _as_str(dev.get("name"), "")
        device_blob = f"{manufacturer} {model} {dev_name}".lower()
        device_mentions_tdeck = any(k in device_blob for k in NODE_KEYWORDS)
        is_esphome = attrs_integration == "esphome" or config_domain == "esphome"

        slug_hints = _detect_slug_hints_from_entity(entity_id)
        if (mentions_tdeck or device_mentions_tdeck or is_esphome) and "." in entity_id:
            object_id = entity_id.split(".", 1)[1]
            object_slug = _slugify(object_id, "")
            if object_slug:
                slug_hints.append((object_slug, 12, "keyword_object"))
            if "_" in object_id:
                slug_hints.append((_slugify(object_id.split("_", 1)[0], ""), 15, "keyword_prefix"))
        if device_mentions_tdeck and dev_name:
            slug_hints.append((_slugify(dev_name, ""), 24, "device_name"))

        for slug, base_score, reason in slug_hints:
            if not slug or len(slug) < 3 or slug in stoplist:
                continue
            node = found.get(
                slug,
                {
                    "device_slug": slug,
                    "native_update_entity": "",
                    "app_version_entity": "",
                    "friendly_name": "",
                    "entities_count": 0,
                    "confidence_score": 0,
                    "confidence": "low",
                    "reasons": [],
                    "matched_entities": [],
                },
            )
            node["entities_count"] = _as_int(node.get("entities_count"), 0, 0, None) + 1
            node["confidence_score"] = _as_int(node.get("confidence_score"), 0, 0, None) + base_score
            reasons = node.get("reasons", [])
            if reason not in reasons:
                reasons.append(reason)
            if mentions_tdeck and "keyword:tdeck" not in reasons:
                reasons.append("keyword:tdeck")
                node["confidence_score"] = _as_int(node.get("confidence_score"), 0, 0, None) + 25
            if device_mentions_tdeck and "device:tdeck" not in reasons:
                reasons.append("device:tdeck")
                node["confidence_score"] = _as_int(node.get("confidence_score"), 0, 0, None) + 35
            if is_esphome and "integration:esphome" not in reasons:
                reasons.append("integration:esphome")
                node["confidence_score"] = _as_int(node.get("confidence_score"), 0, 0, None) + 20
            if entity_id.startswith("update.") and entity_id.endswith("_firmware"):
                node["native_update_entity"] = entity_id
            if entity_id.startswith("sensor.") and entity_id.endswith("_app_version"):
                node["app_version_entity"] = entity_id
            if entity_id not in node.get("matched_entities", []):
                node["matched_entities"].append(entity_id)
            if not _as_str(node.get("friendly_name"), ""):
                preferred_name = dev_name or friendly
                node["friendly_name"] = preferred_name
            node["reasons"] = reasons
            found[slug] = node

    # Secondary path: include all ESPHome devices from device registry even when
    # state rows are sparse or don't include T-Deck keyword hints yet.
    for did, dev in by_device.items():
        if not isinstance(dev, dict):
            continue
        device_entries = dev.get("config_entries") if isinstance(dev.get("config_entries"), list) else []
        is_esphome_device = any(_as_str(x, "") in esphome_entry_ids for x in device_entries)
        if not is_esphome_device:
            continue
        name_by_user = _as_str(dev.get("name_by_user"), "")
        name = _as_str(dev.get("name"), "")
        model = _as_str(dev.get("model"), "")
        manufacturer = _as_str(dev.get("manufacturer"), "")
        identifiers = dev.get("identifiers") if isinstance(dev.get("identifiers"), list) else []
        slug_candidates: List[str] = []
        for raw in [name_by_user, name, model]:
            s = _slugify(raw, "")
            if s and len(s) >= 3:
                slug_candidates.append(s)
        for ident in identifiers:
            if isinstance(ident, (list, tuple)) and len(ident) >= 2:
                ident_value = _as_str(ident[1], "")
                s = _slugify(ident_value, "")
                if s and len(s) >= 3:
                    slug_candidates.append(s)
        if not slug_candidates:
            continue
        slug = slug_candidates[0]
        node = found.get(
            slug,
            {
                "device_slug": slug,
                "native_update_entity": "",
                "app_version_entity": "",
                "friendly_name": "",
                "entities_count": 0,
                "confidence_score": 0,
                "confidence": "low",
                "reasons": [],
                "matched_entities": [],
            },
        )
        reasons = node.get("reasons", []) if isinstance(node.get("reasons"), list) else []
        if "device_registry:esphome" not in reasons:
            reasons.append("device_registry:esphome")
            node["confidence_score"] = _as_int(node.get("confidence_score"), 0, 0, None) + 60
        device_blob = f"{manufacturer} {model} {name_by_user or name}".lower()
        if any(k in device_blob for k in NODE_KEYWORDS) and "device:tdeck" not in reasons:
            reasons.append("device:tdeck")
            node["confidence_score"] = _as_int(node.get("confidence_score"), 0, 0, None) + 30
        node["friendly_name"] = _as_str(node.get("friendly_name"), "") or _as_str(name_by_user or name, f"T-Deck Candidate ({slug})")
        linked_entities = by_device_entities.get(did, [])
        if linked_entities:
            node["entities_count"] = max(_as_int(node.get("entities_count"), 0, 0, None), len(linked_entities))
            matched = node.get("matched_entities", []) if isinstance(node.get("matched_entities"), list) else []
            merged = sorted(set([_as_str(x, "") for x in (matched + linked_entities) if _as_str(x, "")]))
            node["matched_entities"] = merged[:16]
            for ent in linked_entities:
                ent_l = ent.lower()
                if not _as_str(node.get("native_update_entity"), "") and ent_l.startswith("update.") and ent_l.endswith("_firmware"):
                    node["native_update_entity"] = ent_l
                if not _as_str(node.get("app_version_entity"), "") and ent_l.startswith("sensor.") and ent_l.endswith("_app_version"):
                    node["app_version_entity"] = ent_l
        node["reasons"] = reasons
        found[slug] = node

    out: List[Dict[str, Any]] = []
    for slug, node in found.items():
        score = _as_int(node.get("confidence_score"), 0, 0, None)
        has_strong = bool(_as_str(node.get("native_update_entity"), "") or _as_str(node.get("app_version_entity"), ""))
        reasons = node.get("reasons", []) if isinstance(node.get("reasons"), list) else []
        if not has_strong and score < 35:
            continue
        node["confidence_score"] = score
        node["confidence"] = _confidence_label(score)
        node["reasons"] = sorted(set([_as_str(x, "") for x in reasons if _as_str(x, "")]))
        matched = node.get("matched_entities", []) if isinstance(node.get("matched_entities"), list) else []
        node["matched_entities"] = sorted(set([_as_str(x, "") for x in matched if _as_str(x, "")]))[:16]
        node["source_groups"] = _candidate_source_groups(node)
        if not _as_str(node.get("friendly_name"), ""):
            node["friendly_name"] = f"T-Deck Candidate ({slug})"
        out.append(node)

    out.sort(key=lambda x: (-_as_int(x.get("confidence_score"), 0, 0, None), _as_str(x.get("device_slug"), "")))
    return out[:80]


@app.get("/api/onboarding/candidates")
def api_onboarding_candidates() -> Any:
    try:
        force = _as_bool(request.args.get("refresh"), False)
        nodes = _detect_esphome_nodes(force_refresh=force)
        grouped = _group_candidates_by_source(nodes)
        cache = _discovery_cache_snapshot()
        return jsonify(
            {
                "ok": True,
                "nodes": nodes,
                "count": len(nodes),
                "grouped": grouped,
                "groups_order": [
                    "device_registry_esphome",
                    "update_entity_pattern",
                    "app_version_sensor_pattern",
                    "entity_registry_linked",
                    "heuristic",
                ],
                "discovery": {
                    "cache_age_ms": cache.get("cache_age_ms", 0),
                    "last_error": _as_str(cache.get("last_error"), ""),
                    "last_total": _as_int(cache.get("last_total"), 0, 0, None),
                    "last_duration_ms": _as_int(cache.get("last_duration_ms"), 0, 0, None),
                    "stale": _as_bool(cache.get("stale"), False),
                },
            }
        )
    except Exception as err:
        return jsonify({"ok": False, "error": str(err), "nodes": [], "count": 0, "grouped": {}}), 500


@app.get("/api/onboarding/esphome/nodes")
def api_onboarding_esphome_nodes() -> Any:
    # Backward-compatible alias.
    return api_onboarding_candidates()


def _provisioning_modes_for(
    device_slug: str,
    settings: Dict[str, Any] | None = None,
    native_firmware_entity: str = "",
    app_version_entity: str = "",
    target_version: str = "",
) -> Dict[str, Any]:
    safe_slug = _slugify(device_slug, "lilygo-tdeck-plus")
    settings = settings if isinstance(settings, dict) else {}
    caps = _resolve_firmware_capabilities(
        device_slug=safe_slug,
        settings=settings,
        native_firmware_entity=native_firmware_entity,
        app_version_entity=app_version_entity,
        target_version=target_version or _as_str(settings.get("app_release_version"), DEFAULT_APP_RELEASE_VERSION),
    )
    ota_supported = _as_bool(caps.get("has_any_automatic_method"), False)
    usb_required = not ota_supported
    return {
        "device_slug": safe_slug,
        "ota_supported": ota_supported,
        "esphome_services_available": _as_bool(caps.get("esphome_install_available"), False),
        "native_update_available": _as_bool(caps.get("native_update_available"), False),
        "usb_required": usb_required,
        "recommended_method": _as_str(caps.get("recommended_method"), "manual_fallback"),
        "capabilities": caps,
        "expected_usb_flow_steps": [
            "Connect T-Deck Plus to host via USB.",
            "Open ESPHome dashboard and select the managed install YAML path.",
            "Run install over serial once, then return to OTA updates from Admin Center.",
        ]
        if usb_required
        else [],
    }


def _onboarding_import_recommendation(candidate: Dict[str, Any]) -> Dict[str, Any]:
    slug = _slugify(candidate.get("device_slug"), "lilygo-tdeck-plus")
    return {
        "workspace_name": f"imported_{slug}",
        "device_slug": slug,
        "friendly_name": _as_str(candidate.get("friendly_name"), f"T-Deck ({slug})"),
        "native_firmware_entity": _as_str(candidate.get("native_update_entity"), f"update.{slug}_firmware"),
        "app_version_entity": _as_str(candidate.get("app_version_entity"), f"sensor.{slug}_app_version"),
    }


@app.post("/api/onboarding/probe_entity")
def api_onboarding_probe_entity() -> Any:
    payload = request.get_json(silent=True) or {}
    entity_id = _as_str(payload.get("entity_id"), "").strip().lower()
    if not entity_id or "." not in entity_id:
        return jsonify({"ok": False, "error": "entity_id is required"}), 400
    force = _as_bool(payload.get("refresh"), False)
    nodes = _detect_esphome_nodes(force_refresh=force)
    selected: Dict[str, Any] | None = None
    for row in nodes:
        if not isinstance(row, dict):
            continue
        matched = row.get("matched_entities", []) if isinstance(row.get("matched_entities"), list) else []
        matched_lower = [str(x).lower() for x in matched]
        if entity_id in matched_lower:
            selected = row
            break
        if entity_id == _as_str(row.get("native_update_entity"), "").lower():
            selected = row
            break
        if entity_id == _as_str(row.get("app_version_entity"), "").lower():
            selected = row
            break
    if selected is None:
        selected = _manual_candidate_from_input("", entity_id)
    selected["source_groups"] = _candidate_source_groups(selected)
    modes = _provisioning_modes_for(
        _as_str(selected.get("device_slug"), ""),
        settings={},
        native_firmware_entity=_as_str(selected.get("native_update_entity"), ""),
        app_version_entity=_as_str(selected.get("app_version_entity"), ""),
    )
    return jsonify(
        {
            "ok": True,
            "entity_id": entity_id,
            "candidate": selected,
            "confidence": {
                "label": _as_str(selected.get("confidence"), "low"),
                "score": _as_int(selected.get("confidence_score"), 0, 0, None),
                "reasons": selected.get("reasons", []),
            },
            "recommended_import": _onboarding_import_recommendation(selected),
            "provisioning_modes": modes,
        }
    )


@app.post("/api/onboarding/probe_host")
def api_onboarding_probe_host() -> Any:
    payload = request.get_json(silent=True) or {}
    host = _as_str(payload.get("host"), "").strip()
    node_name = _as_str(payload.get("node_name"), "").strip()
    hint = host or node_name
    if not hint:
        return jsonify({"ok": False, "error": "host or node_name is required"}), 400
    hint_slug = _slugify(hint.split(".", 1)[0], "")
    nodes = _detect_esphome_nodes(force_refresh=_as_bool(payload.get("refresh"), False))
    selected: Dict[str, Any] | None = None
    for row in nodes:
        slug = _slugify(row.get("device_slug"), "")
        blob = f"{_as_str(row.get('device_slug'), '')} {_as_str(row.get('friendly_name'), '')}".lower()
        if hint_slug and (hint_slug == slug or hint_slug in blob.replace("-", "_")):
            selected = row
            break
    if selected is None:
        # fallback to a manual candidate so Guided flow can proceed deterministically.
        selected = _manual_candidate_from_input(hint_slug or "lilygo-tdeck-plus", "")
        selected.setdefault("reasons", [])
        reasons = selected.get("reasons", []) if isinstance(selected.get("reasons"), list) else []
        if "host_probe_manual" not in reasons:
            reasons.append("host_probe_manual")
        selected["reasons"] = reasons
    selected["source_groups"] = _candidate_source_groups(selected)
    modes = _provisioning_modes_for(
        _as_str(selected.get("device_slug"), ""),
        settings={},
        native_firmware_entity=_as_str(selected.get("native_update_entity"), ""),
        app_version_entity=_as_str(selected.get("app_version_entity"), ""),
    )
    return jsonify(
        {
            "ok": True,
            "probe": {"host": host, "node_name": node_name, "hint_slug": hint_slug},
            "candidate": selected,
            "migration_feasible": True,
            "recommended_import": _onboarding_import_recommendation(selected),
            "provisioning_modes": modes,
        }
    )


@app.get("/api/onboarding/provisioning_modes")
def api_onboarding_provisioning_modes() -> Any:
    workspace_name = _safe_profile_name(request.args.get("workspace"), "default")
    ws = _load_workspace_or_default(workspace_name)
    profile, idx = _workspace_active_profile(ws, ws.get("active_device_index", 0), _as_str(request.args.get("device_slug"), ""))
    settings = profile.get("settings", {}) if isinstance(profile.get("settings"), dict) else {}
    slug = _as_str(request.args.get("device_slug"), _managed_device_slug(profile)).strip() or _managed_device_slug(profile)
    modes = _provisioning_modes_for(
        slug,
        settings=settings,
        native_firmware_entity=_as_str(request.args.get("native_firmware_entity"), _as_str(settings.get("ha_native_firmware_entity"), "")),
        app_version_entity=_as_str(request.args.get("app_version_entity"), _as_str(settings.get("ha_app_version_entity"), "")),
        target_version=_as_str(request.args.get("target_version"), _as_str(settings.get("app_release_version"), DEFAULT_APP_RELEASE_VERSION)),
    )
    return jsonify(
        {
            "ok": True,
            "workspace_name": ws.get("workspace_name", workspace_name),
            "active_device_index": idx,
            "device_slug": slug,
            **modes,
        }
    )


@app.post("/api/onboarding/verify_candidate")
def api_onboarding_verify_candidate() -> Any:
    payload = request.get_json(silent=True) or {}
    device_slug = _slugify(payload.get("device_slug"), "")
    entity_id = _as_str(payload.get("entity_id"), "").strip().lower()
    nodes = _detect_esphome_nodes()
    selected = None
    if device_slug:
        for row in nodes:
            if _slugify(row.get("device_slug"), "") == device_slug:
                selected = row
                break
    if not selected and entity_id:
        for row in nodes:
            matched = row.get("matched_entities", []) if isinstance(row.get("matched_entities"), list) else []
            if entity_id in [str(x).lower() for x in matched]:
                selected = row
                break
    if not selected:
        if device_slug or entity_id:
            selected = _manual_candidate_from_input(device_slug, entity_id)
        else:
            return jsonify({"ok": False, "error": "candidate_not_found", "device_slug": device_slug, "entity_id": entity_id}), 404

    matched_entities = selected.get("matched_entities", []) if isinstance(selected.get("matched_entities"), list) else []
    hints = []
    if _as_str(selected.get("native_update_entity"), ""):
        hints.append("native_firmware_update_entity detected")
    if _as_str(selected.get("app_version_entity"), ""):
        hints.append("app_version_entity detected")
    if not hints:
        hints.append("legacy node likely; firmware version sensor not detected")
    if "manual_fallback" in (selected.get("reasons") if isinstance(selected.get("reasons"), list) else []):
        hints.append("manual fallback used; candidate was created from input slug/entity")
    selected["source_groups"] = _candidate_source_groups(selected)
    modes = _provisioning_modes_for(
        _as_str(selected.get("device_slug"), ""),
        settings={},
        native_firmware_entity=_as_str(selected.get("native_update_entity"), ""),
        app_version_entity=_as_str(selected.get("app_version_entity"), ""),
    )
    return jsonify(
        {
            "ok": True,
            "candidate": selected,
            "matched_entities_sample": matched_entities[:16],
            "hints": hints,
            "recommended_import": _onboarding_import_recommendation(selected),
            "provisioning_modes": modes,
        }
    )


@app.post("/api/onboarding/start_new")
def api_onboarding_start_new() -> Any:
    payload = request.get_json(silent=True) or {}
    ws = _default_workspace()
    profile, idx = _workspace_active_profile(ws, 0)
    preset = _as_str(payload.get("preset"), "blank").strip().lower() or "blank"
    profile["device"]["name"] = _slugify(payload.get("device_name"), _as_str(profile.get("device", {}).get("name"), "lilygo-tdeck-plus"))
    profile["device"]["friendly_name"] = _as_str(payload.get("friendly_name"), _as_str(profile.get("device", {}).get("friendly_name"), "LilyGO T-Deck Plus"))
    profile["features"] = _default_feature_flags(preset)
    profile.setdefault("settings", {})
    profile["settings"]["onboarding_preset"] = preset
    _apply_feature_page_policy(profile)
    if _as_str(payload.get("app_release_version"), "").strip():
        profile["settings"]["app_release_version"] = _as_str(payload.get("app_release_version"), DEFAULT_APP_RELEASE_VERSION)
    ws["workspace_name"] = _safe_profile_name(payload.get("workspace_name"), _as_str(ws.get("workspace_name"), "default"))
    ws = _workspace_with_profile(ws, profile, idx)
    ws, saved = _maybe_persist_workspace({"persist": _as_bool(payload.get("persist"), True), "name": ws["workspace_name"]}, ws)
    paths = _managed_paths(_managed_device_slug(profile))
    modes = _provisioning_modes_for(
        _managed_device_slug(profile),
        settings=profile.get("settings", {}),
        native_firmware_entity=_as_str(profile.get("settings", {}).get("ha_native_firmware_entity"), ""),
        app_version_entity=_as_str(profile.get("settings", {}).get("ha_app_version_entity"), ""),
        target_version=_as_str(profile.get("settings", {}).get("app_release_version"), DEFAULT_APP_RELEASE_VERSION),
    )
    return jsonify(
        {
            "ok": True,
            "workspace": ws,
            "profile": profile,
            "active_device_index": idx,
            "saved_workspace": saved,
            "preset": preset,
            "managed_paths": {k: str(v) for k, v in paths.items()},
            "provisioning_modes": modes,
            "message": "Start New T-Deck workspace initialized with deploy-safe defaults.",
        }
    )


def _catalog_autodetect_rows(limit_per_type: int = 8) -> List[Dict[str, Any]]:
    cache = _refresh_discovery_cache(force=False)
    rows = cache.get("rows", []) if isinstance(cache.get("rows"), list) else []
    scored: Dict[str, List[Dict[str, Any]]] = {k: [] for k in CORE_TYPE_IDS}
    for row in rows:
        if not isinstance(row, dict):
            continue
        entity_id = _as_str(row.get("entity_id"), "")
        friendly = _as_str(row.get("friendly_name"), entity_id)
        domain = _as_str(row.get("domain"), "")
        type_id = _infer_type_id(entity_id)
        if type_id not in scored:
            continue
        score = 30
        if domain in TYPE_REGISTRY.get(type_id, {}).get("domains", []):
            score += 25
        if not _state_is_unknown(row.get("state")):
            score += 10
        lower = f"{entity_id} {friendly}".lower()
        if any(x in lower for x in ["main", "primary", "living", "front", "door", "weather", "climate", "thermostat"]):
            score += 10
        scored[type_id].append(
            {
                "id": f"{type_id}:{entity_id}",
                "type": type_id,
                "entity_id": entity_id,
                "friendly_name": friendly,
                "domain": domain,
                "score": score,
                "reason": f"domain={domain}; type={type_id}",
            }
        )
    out: List[Dict[str, Any]] = []
    for type_id in CORE_TYPE_IDS:
        items = scored.get(type_id, [])
        items.sort(key=lambda x: (-_as_int(x.get("score"), 0, 0, None), _as_str(x.get("entity_id"), "")))
        out.extend(items[: max(1, min(limit_per_type, 32))])
    return out


@app.post("/api/onboarding/import_existing")
def api_onboarding_import_existing() -> Any:
    payload = request.get_json(silent=True) or {}
    nodes = _detect_esphome_nodes()
    if not nodes:
        nodes = _detect_esphome_nodes(force_refresh=True)
    requested_slug = _slugify(payload.get("device_slug"), "")
    requested_entity = _as_str(payload.get("entity_id"), "").strip().lower()
    selected = None
    for row in nodes:
        row_slug = _slugify(row.get("device_slug"), "")
        matched = row.get("matched_entities", []) if isinstance(row.get("matched_entities"), list) else []
        matched_lower = [str(x).lower() for x in matched]
        if requested_slug and row_slug == requested_slug:
            selected = row
            break
        if requested_entity and requested_entity in matched_lower:
            selected = row
            break
    if selected is None and nodes:
        selected = nodes[0]
    if selected is None:
        if requested_slug or requested_entity:
            selected = _manual_candidate_from_input(requested_slug, requested_entity)
        else:
            cache = _discovery_cache_snapshot()
            return jsonify(
                {
                    "ok": False,
                    "error": "no_esphome_nodes_detected",
                    "discovery_last_error": _as_str(cache.get("last_error"), ""),
                    "discovery_last_total": _as_int(cache.get("last_total"), 0, 0, None),
                    "hint": "Run Scan Existing Nodes, then use manual verify by slug/entity if needed.",
                }
            ), 404

    ws = _default_workspace()
    profile, idx = _workspace_active_profile(ws, 0)
    slug = _slugify(selected.get("device_slug"), "lilygo-tdeck-plus")
    profile["device"]["name"] = slug
    profile["device"]["friendly_name"] = _as_str(selected.get("friendly_name"), f"T-Deck ({slug})")
    profile.setdefault("settings", {})
    profile["settings"]["ha_native_firmware_entity"] = _as_str(selected.get("native_update_entity"), f"update.{slug}_firmware")
    profile["settings"]["ha_app_version_entity"] = _as_str(selected.get("app_version_entity"), f"sensor.{slug}_app_version")
    profile["features"] = _default_feature_flags("controller")
    _apply_feature_page_policy(profile)
    app_state = _ha_get_state_safe(profile["settings"]["ha_app_version_entity"])
    if _as_bool(app_state.get("ok"), False):
        installed = _as_str(app_state.get("state"), "")
        if installed and not _state_is_unknown(installed):
            if not installed.lower().startswith("v"):
                installed = f"v{installed}"
            profile["settings"]["app_release_version"] = installed
        else:
            profile["settings"]["installed_version_status"] = "legacy_unknown"
    else:
        profile["settings"]["installed_version_status"] = "legacy_unknown"
    ws["workspace_name"] = _safe_profile_name(payload.get("workspace_name"), "imported")
    ws = _workspace_with_profile(ws, profile, idx)
    ws, saved = _maybe_persist_workspace({"persist": _as_bool(payload.get("persist"), True), "name": ws["workspace_name"]}, ws)
    modes = _provisioning_modes_for(
        slug,
        settings=profile.get("settings", {}),
        native_firmware_entity=_as_str(profile.get("settings", {}).get("ha_native_firmware_entity"), ""),
        app_version_entity=_as_str(profile.get("settings", {}).get("ha_app_version_entity"), ""),
        target_version=_as_str(profile.get("settings", {}).get("app_release_version"), DEFAULT_APP_RELEASE_VERSION),
    )
    return jsonify(
        {
            "ok": True,
            "workspace": ws,
            "profile": profile,
            "active_device_index": idx,
            "saved_workspace": saved,
            "imported_node": selected,
            "provisioning_modes": modes,
            "message": (
                "Existing ESPHome node imported into managed workspace. "
                "Firmware version may appear as legacy_unknown until upgraded."
                if "manual_fallback" not in (selected.get("reasons") if isinstance(selected.get("reasons"), list) else [])
                else "Manual candidate imported into managed workspace. Confirm firmware/update entities in Step 1 before deploy."
            ),
        }
    )


@app.post("/api/onboarding/migrate_to_managed")
def api_onboarding_migrate_to_managed() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, _ = _workspace_or_profile_from_payload(payload)
    deployment = workspace.get("deployment", {}) if isinstance(workspace.get("deployment"), dict) else {}
    git_ref = _as_str(payload.get("git_ref"), _as_str(deployment.get("git_ref"), _as_str(profile.get("device", {}).get("git_ref"), ADDON_GITHUB_REF)))
    git_url = _as_str(payload.get("git_url"), _as_str(deployment.get("git_url"), _as_str(profile.get("device", {}).get("git_url"), ADDON_GITHUB_REPO_URL)))
    validation = _validate_profile(profile)
    if not validation.get("ok"):
        return jsonify({"ok": False, "error": "validation_failed", "validation": validation}), 400
    preview = _preview_managed_apply(workspace, profile, git_ref or ADDON_GITHUB_REF, git_url or ADDON_GITHUB_REPO_URL)
    if not _as_bool(payload.get("commit"), False):
        return jsonify({"ok": True, "preview": preview, "validation": validation, "committed": False})
    lock = _get_apply_lock(preview["device_slug"])
    if not lock.acquire(blocking=False):
        return jsonify({"ok": False, "error": "apply_in_progress", "device_slug": preview["device_slug"]}), 409
    try:
        committed = _commit_managed_preview(
            preview,
            profile,
            workspace,
            reason="migrate_to_managed",
            context={"source": "api_onboarding_migrate_to_managed"},
        )
        return jsonify({"ok": True, "preview": preview, "validation": validation, "committed": True, "result": committed})
    finally:
        lock.release()


@app.get("/api/catalog/types")
def api_catalog_types() -> Any:
    return jsonify({"ok": True, "types": _default_type_registry(), "core_type_ids": CORE_TYPE_IDS})


@app.post("/api/catalog/autodetect")
def api_catalog_autodetect() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    limit_per_type = _as_int(payload.get("limit_per_type"), 8, 1, 32)
    detected = _catalog_autodetect_rows(limit_per_type=limit_per_type)
    profile.setdefault("autodetect", {})
    profile["autodetect"]["last_scan_at"] = int(_now())
    profile["autodetect"]["detected"] = detected
    profile["autodetect"]["ignored"] = profile.get("autodetect", {}).get("ignored", [])
    ws = _workspace_with_profile(workspace, profile, idx)
    ws, saved = _maybe_persist_workspace(payload, ws)
    return jsonify(
        {
            "ok": True,
            "workspace": ws,
            "profile": profile,
            "active_device_index": idx,
            "saved_workspace": saved,
            "detected": detected,
            "count": len(detected),
        }
    )


@app.post("/api/catalog/accept_detected")
def api_catalog_accept_detected() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    selected = payload.get("entity_ids")
    selected_set: set[str] = set()
    if isinstance(selected, list):
        for item in selected:
            val = _as_str(item, "").strip()
            if val:
                selected_set.add(val)
    profile.setdefault("autodetect", {})
    detected = profile.get("autodetect", {}).get("detected", []) if isinstance(profile.get("autodetect", {}).get("detected"), list) else []
    instances = profile.get("entity_instances", []) if isinstance(profile.get("entity_instances"), list) else []
    existing_entities = { _as_str(x.get("entity_id"), "").strip().lower() for x in instances if isinstance(x, dict) }
    added = 0
    for row in detected:
        if not isinstance(row, dict):
            continue
        entity_id = _as_str(row.get("entity_id"), "").strip()
        if not entity_id:
            continue
        if selected_set and entity_id not in selected_set:
            continue
        if entity_id.lower() in existing_entities:
            continue
        type_id = _as_str(row.get("type"), "").strip().lower()
        if type_id not in TYPE_REGISTRY:
            type_id = _infer_type_id(entity_id)
        inst = _normalize_entity_instance(
            {
                "id": f"{type_id}_{len(instances) + 1}",
                "type": type_id,
                "name": _as_str(row.get("friendly_name"), entity_id),
                "entity_id": entity_id,
                "enabled": True,
                "role": "",
                "group": _collection_for_type(type_id, ""),
            },
            len(instances),
        )
        instances.append(inst)
        existing_entities.add(entity_id.lower())
        added += 1
    profile["entity_instances"] = instances
    _normalize_entity_instances(profile, incoming_has_instances=True)
    _sync_slots_from_collections(profile)
    ws = _workspace_with_profile(workspace, profile, idx)
    ws, saved = _maybe_persist_workspace(payload, ws)
    return jsonify({"ok": True, "workspace": ws, "profile": profile, "active_device_index": idx, "saved_workspace": saved, "added": added})


@app.post("/api/catalog/ignore_detected")
def api_catalog_ignore_detected() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    selected = payload.get("entity_ids")
    selected_set: set[str] = set()
    if isinstance(selected, list):
        for item in selected:
            val = _as_str(item, "").strip()
            if val:
                selected_set.add(val)
    profile.setdefault("autodetect", {})
    detected = profile.get("autodetect", {}).get("detected", []) if isinstance(profile.get("autodetect", {}).get("detected"), list) else []
    ignored = profile.get("autodetect", {}).get("ignored", []) if isinstance(profile.get("autodetect", {}).get("ignored"), list) else []
    ignored_set = set(_as_str(x, "") for x in ignored)
    if selected_set:
        ignored_set.update(selected_set)
    else:
        for row in detected:
            if isinstance(row, dict):
                val = _as_str(row.get("entity_id"), "").strip()
                if val:
                    ignored_set.add(val)
    profile["autodetect"]["ignored"] = sorted(list(ignored_set))
    ws = _workspace_with_profile(workspace, profile, idx)
    ws, saved = _maybe_persist_workspace(payload, ws)
    return jsonify({"ok": True, "workspace": ws, "profile": profile, "active_device_index": idx, "saved_workspace": saved, "ignored": profile["autodetect"]["ignored"]})


def _instance_find_index(instances: List[Dict[str, Any]], item_id: str, at_index: int = -1) -> int:
    want = _slugify(item_id, "")
    if want:
        for i, row in enumerate(instances):
            if _slugify(row.get("id"), "") == want:
                return i
    if at_index >= 0 and at_index < len(instances):
        return at_index
    return -1


def _apply_instance_bulk(profile: Dict[str, Any], ops: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    instances = profile.get("entity_instances", []) if isinstance(profile.get("entity_instances"), list) else []
    errors: List[str] = []
    notices: List[str] = []
    for pos, op in enumerate(ops):
        if not isinstance(op, dict):
            errors.append(f"op[{pos}] is not an object")
            continue
        action = _as_str(op.get("op"), "").strip().lower()
        if action == "add":
            item = op.get("item") if isinstance(op.get("item"), dict) else {}
            instances.append(_normalize_entity_instance(item, len(instances)))
        elif action == "update":
            idx = _instance_find_index(instances, _as_str(op.get("item_id"), ""), _as_int(op.get("index"), -1, -1, None))
            if idx < 0:
                errors.append(f"op[{pos}] item not found")
                continue
            patch = op.get("patch") if isinstance(op.get("patch"), dict) else {}
            merged = dict(instances[idx])
            merged.update(patch)
            instances[idx] = _normalize_entity_instance(merged, idx)
        elif action == "remove":
            idx = _instance_find_index(instances, _as_str(op.get("item_id"), ""), _as_int(op.get("index"), -1, -1, None))
            if idx < 0:
                errors.append(f"op[{pos}] item not found")
                continue
            instances.pop(idx)
        elif action == "reorder":
            from_idx = _as_int(op.get("from_index"), -1, -1, None)
            to_idx = _as_int(op.get("to_index"), -1, -1, None)
            if from_idx < 0 or from_idx >= len(instances) or to_idx < 0 or to_idx >= len(instances):
                errors.append(f"op[{pos}] from_index/to_index out of range")
                continue
            row = instances.pop(from_idx)
            instances.insert(to_idx, row)
        elif action in {"enable_all", "disable_all"}:
            enabled = action == "enable_all"
            for row in instances:
                if isinstance(row, dict):
                    row["enabled"] = enabled
        elif action == "remove_disabled":
            before = len(instances)
            instances = [row for row in instances if _as_bool(row.get("enabled"), True)]
            notices.append(f"remove_disabled removed {before - len(instances)} rows")
        elif action == "dedupe":
            seen: set[str] = set()
            deduped: List[Dict[str, Any]] = []
            removed = 0
            for row in instances:
                entity_id = _as_str(row.get("entity_id"), "").strip().lower()
                if entity_id and entity_id in seen:
                    removed += 1
                    continue
                if entity_id:
                    seen.add(entity_id)
                deduped.append(row)
            instances = deduped
            notices.append(f"dedupe removed {removed} duplicate entity instances")
        else:
            errors.append(f"op[{pos}] unsupported action '{action}'")
    profile["entity_instances"] = instances
    _normalize_entity_instances(profile, incoming_has_instances=True)
    _sync_slots_from_collections(profile)
    return errors, notices


@app.get("/api/entities/instances")
def api_entities_instances() -> Any:
    workspace_name = _safe_profile_name(request.args.get("workspace"), "default")
    ws = _load_workspace_or_default(workspace_name)
    profile, idx = _workspace_active_profile(ws, ws.get("active_device_index", 0), _as_str(request.args.get("device_slug"), ""))
    profile = _normalize_profile(profile)
    return jsonify(
        {
            "ok": True,
            "workspace_name": ws.get("workspace_name", workspace_name),
            "active_device_index": idx,
            "device_slug": _managed_device_slug(profile),
            "type_registry": _default_type_registry(),
            "entity_instances": profile.get("entity_instances", []),
            "page_layouts": profile.get("page_layouts", []),
        }
    )


@app.post("/api/entities/instances/add")
def api_entities_instances_add() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    item = payload.get("item") if isinstance(payload.get("item"), dict) else {}
    instances = profile.get("entity_instances", []) if isinstance(profile.get("entity_instances"), list) else []
    instances.append(_normalize_entity_instance(item, len(instances)))
    profile["entity_instances"] = instances
    _normalize_entity_instances(profile, incoming_has_instances=True)
    _sync_slots_from_collections(profile)
    workspace = _workspace_with_profile(workspace, profile, idx)
    workspace, saved = _maybe_persist_workspace(payload, workspace)
    return jsonify({"ok": True, "workspace": workspace, "profile": profile, "active_device_index": idx, "saved_workspace": saved})


@app.post("/api/entities/instances/update")
def api_entities_instances_update() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    instances = profile.get("entity_instances", []) if isinstance(profile.get("entity_instances"), list) else []
    item_id = _as_str(payload.get("item_id"), "")
    at_index = _as_int(payload.get("index"), -1, -1, None)
    patch = payload.get("patch") if isinstance(payload.get("patch"), dict) else {}
    i = _instance_find_index(instances, item_id, at_index)
    if i < 0:
        return jsonify({"ok": False, "error": "item_not_found"}), 404
    merged = dict(instances[i])
    merged.update(patch)
    instances[i] = _normalize_entity_instance(merged, i)
    profile["entity_instances"] = instances
    _normalize_entity_instances(profile, incoming_has_instances=True)
    _sync_slots_from_collections(profile)
    workspace = _workspace_with_profile(workspace, profile, idx)
    workspace, saved = _maybe_persist_workspace(payload, workspace)
    return jsonify({"ok": True, "workspace": workspace, "profile": profile, "active_device_index": idx, "saved_workspace": saved})


@app.post("/api/entities/instances/remove")
def api_entities_instances_remove() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    instances = profile.get("entity_instances", []) if isinstance(profile.get("entity_instances"), list) else []
    i = _instance_find_index(instances, _as_str(payload.get("item_id"), ""), _as_int(payload.get("index"), -1, -1, None))
    if i < 0:
        return jsonify({"ok": False, "error": "item_not_found"}), 404
    instances.pop(i)
    profile["entity_instances"] = instances
    _normalize_entity_instances(profile, incoming_has_instances=True)
    _sync_slots_from_collections(profile)
    workspace = _workspace_with_profile(workspace, profile, idx)
    workspace, saved = _maybe_persist_workspace(payload, workspace)
    return jsonify({"ok": True, "workspace": workspace, "profile": profile, "active_device_index": idx, "saved_workspace": saved})


@app.post("/api/entities/instances/reorder")
def api_entities_instances_reorder() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    instances = profile.get("entity_instances", []) if isinstance(profile.get("entity_instances"), list) else []
    from_idx = _as_int(payload.get("from_index"), -1, -1, None)
    to_idx = _as_int(payload.get("to_index"), -1, -1, None)
    if from_idx < 0 or from_idx >= len(instances) or to_idx < 0 or to_idx >= len(instances):
        return jsonify({"ok": False, "error": "from_index/to_index_out_of_range"}), 400
    row = instances.pop(from_idx)
    instances.insert(to_idx, row)
    profile["entity_instances"] = instances
    _normalize_entity_instances(profile, incoming_has_instances=True)
    _sync_slots_from_collections(profile)
    workspace = _workspace_with_profile(workspace, profile, idx)
    workspace, saved = _maybe_persist_workspace(payload, workspace)
    return jsonify({"ok": True, "workspace": workspace, "profile": profile, "active_device_index": idx, "saved_workspace": saved})


@app.post("/api/entities/instances/bulk")
def api_entities_instances_bulk() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    ops = payload.get("ops") if isinstance(payload.get("ops"), list) else []
    if not ops:
        return jsonify({"ok": False, "error": "ops[] is required"}), 400
    errors, notices = _apply_instance_bulk(profile, ops)
    validation = _validate_profile(profile)
    workspace = _workspace_with_profile(workspace, profile, idx)
    workspace, saved = _maybe_persist_workspace(payload, workspace)
    return jsonify(
        {
            "ok": len(errors) == 0,
            "errors": errors,
            "notices": notices,
            "validation": {
                "ok": validation["ok"],
                "errors": validation["errors"],
                "warnings": validation["warnings"],
            },
            "workspace": workspace,
            "profile": profile,
            "active_device_index": idx,
            "saved_workspace": saved,
        }
    ), (200 if len(errors) == 0 else 400)


@app.post("/api/mapping/suggest")
def api_mapping_suggest() -> Any:
    payload = request.get_json(silent=True) or {}
    key = _as_str(payload.get("key"), "")
    query = _as_str(payload.get("q"), "")
    limit = _as_int(payload.get("limit"), 12, 1, 50)
    collection = _as_str(payload.get("collection"), "").strip().lower()
    role = _as_str(payload.get("role"), "")
    type_id = _as_str(payload.get("type"), "")
    domain_hint = _as_str(payload.get("domain_hint"), "")
    exclude_assigned = _as_bool(payload.get("exclude_assigned"), False)
    active_device_slug = _as_str(payload.get("active_device_slug"), "")
    scope_device_slug = _as_str(payload.get("device_slug"), "").strip() or active_device_slug
    exclude_entities: set[str] = set()
    if exclude_assigned:
        ws = _load_workspace_or_default(_safe_profile_name(payload.get("workspace"), "default"))
        profile, _ = _workspace_active_profile(ws, ws.get("active_device_index", 0), active_device_slug)
        collections = profile.get("entity_collections", {}) if isinstance(profile.get("entity_collections"), dict) else {}
        for rows in collections.values():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if isinstance(row, dict):
                    entity_id = _as_str(row.get("entity_id"), "").strip().lower()
                    if entity_id:
                        exclude_entities.add(entity_id)
        instances = profile.get("entity_instances", []) if isinstance(profile.get("entity_instances"), list) else []
        for row in instances:
            if isinstance(row, dict):
                entity_id = _as_str(row.get("entity_id"), "").strip().lower()
                if entity_id:
                    exclude_entities.add(entity_id)
    suggestions = _mapping_suggestions(
        key,
        query,
        limit=limit,
        collection=collection,
        role=role,
        domain_hint=domain_hint,
        type_id=type_id,
        device_slug=scope_device_slug,
        exclude_entities=exclude_entities,
    )
    return jsonify(
        {
            "ok": True,
            "key": key,
            "collection": collection,
            "role": role,
            "type": type_id,
            "domain_hint": domain_hint,
            "device_slug": scope_device_slug,
            "count": len(suggestions),
            "suggestions": suggestions,
        }
    )


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
            "slot_runtime": _normalize_slot_runtime(profile.get("slot_runtime")),
            "entity_collections_meta": _normalize_entity_collections_meta(profile.get("entity_collections_meta")),
            "contracts": {
                "entity_collection_limits": ENTITY_COLLECTION_LIMITS,
                "slot_runtime_limits": SLOT_RUNTIME_LIMITS,
            },
        }
    )


def _collection_rows(profile: Dict[str, Any], collection: str) -> List[Dict[str, Any]]:
    profile["entity_collections"] = _normalize_profile_collections(profile)
    return profile["entity_collections"].get(collection, [])


def _find_collection_index(rows: List[Dict[str, Any]], item_id: str, fallback_index: int = -1) -> int:
    if item_id:
        want = _slugify(item_id, "")
        for idx, row in enumerate(rows):
            if _slugify(row.get("id"), "") == want:
                return idx
    if fallback_index >= 0 and fallback_index < len(rows):
        return fallback_index
    return -1


def _apply_collection_op(profile: Dict[str, Any], op: Dict[str, Any], notices: List[str]) -> Tuple[bool, str]:
    collection = _as_str(op.get("collection"), "").strip().lower()
    if collection not in ENTITY_COLLECTION_LIMITS:
        return False, f"collection must be one of: {', '.join(sorted(ENTITY_COLLECTION_LIMITS.keys()))}"
    rows = _collection_rows(profile, collection)
    action = _as_str(op.get("op"), "").strip().lower()
    hard_max = _as_int(ENTITY_COLLECTION_LIMITS.get(collection, {}).get("hard_max"), 64, 1, 4096)

    if action == "add":
        if len(rows) >= hard_max:
            return False, f"{collection} reached hard limit {hard_max}"
        item = op.get("item") if isinstance(op.get("item"), dict) else {}
        next_idx = len(rows) + 1
        rows.append(
            {
                "id": _slugify(item.get("id"), f"{collection[:-1]}_{next_idx}"),
                "name": _as_str(item.get("name"), f"{collection[:-1].title()} {next_idx}"),
                "entity_id": _as_str(item.get("entity_id") or item.get("entity"), ""),
                "role": _as_str(item.get("role"), ""),
                "enabled": _as_bool(item.get("enabled"), True),
            }
        )
    elif action == "update":
        item_id = _slugify(op.get("item_id"), "")
        at_index = _as_int(op.get("index"), -1, -1, None)
        patch = op.get("patch") if isinstance(op.get("patch"), dict) else {}
        idx = _find_collection_index(rows, item_id, at_index)
        if idx < 0:
            return False, f"item not found for update in {collection}"
        row = rows[idx]
        if "id" in patch:
            row["id"] = _slugify(patch.get("id"), row.get("id"))
        if "name" in patch:
            row["name"] = _as_str(patch.get("name"), row.get("name"))
        if "entity_id" in patch or "entity" in patch:
            row["entity_id"] = _as_str(patch.get("entity_id") or patch.get("entity"), row.get("entity_id"))
        if "role" in patch:
            row["role"] = _as_str(patch.get("role"), row.get("role"))
        if "enabled" in patch:
            row["enabled"] = _as_bool(patch.get("enabled"), True)
    elif action == "remove":
        item_id = _slugify(op.get("item_id"), "")
        at_index = _as_int(op.get("index"), -1, -1, None)
        idx = _find_collection_index(rows, item_id, at_index)
        if idx < 0:
            return False, f"item not found for remove in {collection}"
        rows.pop(idx)
    elif action == "reorder":
        from_index = _as_int(op.get("from_index"), -1, -1, None)
        to_index = _as_int(op.get("to_index"), -1, -1, None)
        if from_index < 0 or from_index >= len(rows) or to_index < 0 or to_index >= len(rows):
            return False, "from_index/to_index out of range"
        item = rows.pop(from_index)
        rows.insert(to_index, item)
    elif action in {"enable_all", "disable_all"}:
        enabled = action == "enable_all"
        for row in rows:
            row["enabled"] = enabled
    elif action == "dedupe":
        seen: set[str] = set()
        deduped: List[Dict[str, Any]] = []
        removed = 0
        for row in rows:
            entity_id = _as_str(row.get("entity_id"), "").strip().lower()
            if not entity_id:
                deduped.append(row)
                continue
            if entity_id in seen:
                removed += 1
                continue
            seen.add(entity_id)
            deduped.append(row)
        rows[:] = deduped
        notices.append(f"{collection}: dedupe removed {removed} duplicate rows")
    else:
        return False, f"unsupported op '{action}'"

    profile["entity_collections"][collection] = rows
    profile["entity_collections_meta"] = _normalize_entity_collections_meta(profile.get("entity_collections_meta"))
    meta = profile["entity_collections_meta"].get(collection, {})
    meta["draft_dirty"] = True
    meta["updated_at"] = int(_now())
    profile["entity_collections_meta"][collection] = meta
    return True, ""


@app.post("/api/entities/bulk_apply")
def api_entities_bulk_apply() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    ops = payload.get("ops") if isinstance(payload.get("ops"), list) else []
    if not ops:
        return jsonify({"ok": False, "error": "ops[] is required"}), 400
    errors: List[str] = []
    notices: List[str] = []
    for pos, op in enumerate(ops):
        if not isinstance(op, dict):
            errors.append(f"op[{pos}] is not an object")
            continue
        ok, err = _apply_collection_op(profile, op, notices)
        if not ok:
            errors.append(f"op[{pos}] {err}")
    _sync_slots_from_collections(profile)
    validation = _validate_profile(profile)
    workspace = _workspace_with_profile(workspace, profile, idx)
    workspace, saved = _maybe_persist_workspace(payload, workspace)
    status_code = 200 if not errors else 400
    return jsonify(
        {
            "ok": len(errors) == 0,
            "errors": errors,
            "notices": notices,
            "workspace": workspace,
            "profile": profile,
            "active_device_index": idx,
            "saved_workspace": saved,
            "validation": {
                "ok": validation["ok"],
                "errors": validation["errors"],
                "warnings": validation["warnings"],
            },
        }
    ), status_code


@app.get("/api/entities/slot_caps")
def api_entities_slot_caps() -> Any:
    workspace_name = _safe_profile_name(request.args.get("workspace"), "default")
    ws = _load_workspace_or_default(workspace_name)
    profile, idx = _workspace_active_profile(ws, ws.get("active_device_index", 0), _as_str(request.args.get("device_slug"), ""))
    profile = _normalize_profile(profile)
    collections = profile.get("entity_collections", {}) if isinstance(profile.get("entity_collections"), dict) else {}
    lights = collections.get("lights", []) if isinstance(collections.get("lights"), list) else []
    cameras = collections.get("cameras", []) if isinstance(collections.get("cameras"), list) else []
    enabled_lights = len([x for x in lights if _as_bool(x.get("enabled"), True)])
    enabled_cameras = len([x for x in cameras if _as_bool(x.get("enabled"), True)])
    slot_runtime = _normalize_slot_runtime(profile.get("slot_runtime"))
    return jsonify(
        {
            "ok": True,
            "workspace_name": ws.get("workspace_name", workspace_name),
            "active_device_index": idx,
            "device_slug": _managed_device_slug(profile),
            "slot_runtime": slot_runtime,
            "limits": SLOT_RUNTIME_LIMITS,
            "enabled_counts": {"lights": enabled_lights, "cameras": enabled_cameras},
            "overflow": {
                "lights": enabled_lights > _as_int(
                    slot_runtime.get("light_slot_cap"),
                    SLOT_RUNTIME_LIMITS["lights"]["default_cap"],
                    SLOT_RUNTIME_LIMITS["lights"]["min_cap"],
                    SLOT_RUNTIME_LIMITS["lights"]["max_cap"],
                ),
                "cameras": enabled_cameras > _as_int(
                    slot_runtime.get("camera_slot_cap"),
                    SLOT_RUNTIME_LIMITS["cameras"]["default_cap"],
                    SLOT_RUNTIME_LIMITS["cameras"]["min_cap"],
                    SLOT_RUNTIME_LIMITS["cameras"]["max_cap"],
                ),
            },
        }
    )


@app.post("/api/entities/auto_fit_caps")
def api_entities_auto_fit_caps() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    profile = _normalize_profile(profile)
    collections = profile.get("entity_collections", {}) if isinstance(profile.get("entity_collections"), dict) else {}
    lights = collections.get("lights", []) if isinstance(collections.get("lights"), list) else []
    cameras = collections.get("cameras", []) if isinstance(collections.get("cameras"), list) else []
    enabled_lights = len([x for x in lights if _as_bool(x.get("enabled"), True)])
    enabled_cameras = len([x for x in cameras if _as_bool(x.get("enabled"), True)])
    slot_runtime = _normalize_slot_runtime(profile.get("slot_runtime"))
    light_cap = _as_int(
        slot_runtime.get("light_slot_cap"),
        SLOT_RUNTIME_LIMITS["lights"]["default_cap"],
        SLOT_RUNTIME_LIMITS["lights"]["min_cap"],
        SLOT_RUNTIME_LIMITS["lights"]["max_cap"],
    )
    camera_cap = _as_int(
        slot_runtime.get("camera_slot_cap"),
        SLOT_RUNTIME_LIMITS["cameras"]["default_cap"],
        SLOT_RUNTIME_LIMITS["cameras"]["min_cap"],
        SLOT_RUNTIME_LIMITS["cameras"]["max_cap"],
    )
    changed = False
    if enabled_lights > light_cap:
        if enabled_lights > SLOT_RUNTIME_LIMITS["lights"]["max_cap"]:
            return jsonify({"ok": False, "error": f"enabled lights {enabled_lights} exceed hard cap {SLOT_RUNTIME_LIMITS['lights']['max_cap']}"}), 400
        slot_runtime["light_slot_cap"] = enabled_lights
        changed = True
    if enabled_cameras > camera_cap:
        if enabled_cameras > SLOT_RUNTIME_LIMITS["cameras"]["max_cap"]:
            return jsonify({"ok": False, "error": f"enabled cameras {enabled_cameras} exceed hard cap {SLOT_RUNTIME_LIMITS['cameras']['max_cap']}"}), 400
        slot_runtime["camera_slot_cap"] = enabled_cameras
        changed = True
    profile["slot_runtime"] = _normalize_slot_runtime(slot_runtime)
    _sync_slots_from_collections(profile)
    validation = _validate_profile(profile)
    workspace = _workspace_with_profile(workspace, profile, idx)
    workspace, saved = _maybe_persist_workspace(payload, workspace)
    return jsonify(
        {
            "ok": True,
            "changed": changed,
            "workspace": workspace,
            "profile": profile,
            "active_device_index": idx,
            "saved_workspace": saved,
            "slot_runtime": profile.get("slot_runtime", {}),
            "validation": {
                "ok": validation["ok"],
                "errors": validation["errors"],
                "warnings": validation["warnings"],
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


@app.get("/api/layout/pages")
def api_layout_pages_get() -> Any:
    workspace_name = _safe_profile_name(request.args.get("workspace"), "default")
    ws = _load_workspace_or_default(workspace_name)
    profile, idx = _workspace_active_profile(ws, ws.get("active_device_index", 0), _as_str(request.args.get("device_slug"), ""))
    pages = ws.get("layout_pages", {}) if isinstance(ws.get("layout_pages"), dict) else profile.get("layout_pages", {})
    validation = _validate_layout_pages(pages if isinstance(pages, dict) else {})
    return jsonify(
        {
            "ok": True,
            "workspace_name": ws.get("workspace_name", workspace_name),
            "active_device_index": idx,
            "device_slug": _managed_device_slug(profile),
            "layout_pages": validation.get("pages", {}),
            "validation": validation,
        }
    )


@app.post("/api/layout/pages/validate")
def api_layout_pages_validate() -> Any:
    payload = request.get_json(silent=True) or {}
    pages = payload.get("layout_pages") if isinstance(payload.get("layout_pages"), dict) else {}
    validation = _validate_layout_pages(pages)
    return jsonify({"ok": validation.get("ok", False), "layout_pages": validation.get("pages", {}), "validation": validation})


@app.post("/api/layout/pages/save")
def api_layout_pages_save() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    incoming_pages = payload.get("layout_pages") if isinstance(payload.get("layout_pages"), dict) else {}
    validation = _validate_layout_pages(incoming_pages)
    if not validation.get("ok"):
        return jsonify({"ok": False, "error": "layout_validation_failed", "validation": validation}), 400
    workspace["layout_pages"] = validation.get("pages", {})
    profile["layout_pages"] = validation.get("pages", {})
    workspace = _workspace_with_profile(workspace, profile, idx)
    workspace, saved = _maybe_persist_workspace(payload, workspace)
    return jsonify({"ok": True, "workspace": workspace, "profile": profile, "active_device_index": idx, "saved_workspace": saved, "validation": validation})


@app.post("/api/layout/pages/reset")
def api_layout_pages_reset() -> Any:
    _ = request.get_json(silent=True) or {}
    return api_layout_reset_page()


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


@app.post("/api/theme/reset_safe")
def api_theme_reset_safe() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    palette_id = _as_str(payload.get("palette_id"), "ocean_dark")
    defaults = _default_substitutions()
    tokens: Dict[str, Any] = {}
    for key in _contracts()["theme_keys"]:
        if key in defaults:
            tokens[key] = defaults[key]
    workspace, profile, meta = _apply_theme_to_workspace(workspace, profile, idx, tokens, palette_id, {}, "web")
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
    legacy_imported = _as_bool(request.args.get("legacy_imported"), False)
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
        legacy_imported=legacy_imported,
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
                "generated": [
                    "generated/types.registry.yaml",
                    "generated/entities.instances.yaml",
                    "generated/layout.pages.yaml",
                    "generated/theme.tokens.yaml",
                    "generated/bindings.report.yaml",
                    "generated/entities.generated.yaml",
                    "generated/theme.generated.yaml",
                    "generated/layout.generated.yaml",
                    "generated/pages/home.generated.yaml",
                    "generated/pages/lights.generated.yaml",
                    "generated/pages/weather.generated.yaml",
                    "generated/pages/climate.generated.yaml",
                ],
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
            "types_registry": _build_generated_types_registry_yaml(profile),
            "entities_instances": _build_generated_entities_instances_yaml(profile),
            "layout_pages": _build_generated_layout_pages_yaml(profile, workspace),
            "theme_tokens": _build_generated_theme_tokens_yaml(profile),
            "bindings_report": _build_generated_bindings_report_yaml(profile),
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
        committed = _commit_managed_preview(
            preview,
            profile,
            workspace,
            reason="apply_commit",
            context={"source": "api_apply_commit"},
        )
        return jsonify({"ok": True, **committed})
    finally:
        lock.release()


def _managed_write_check(device_slug: str) -> Dict[str, Any]:
    paths = _managed_paths(device_slug)
    probe = paths["install"].parent / ".write_probe"
    try:
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text(str(int(_now())), encoding="utf-8")
        probe.unlink(missing_ok=True)
        return {"ok": True, "path": str(paths["install"].parent)}
    except Exception as err:
        return {"ok": False, "path": str(paths["install"].parent), "error": str(err)}


def _deploy_preflight_result(
    workspace: Dict[str, Any],
    profile: Dict[str, Any],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    validation = _validate_profile(profile)
    device_slug = _managed_device_slug(profile)
    settings = profile.get("settings", {}) if isinstance(profile.get("settings"), dict) else {}
    caps = _resolve_firmware_capabilities(
        device_slug=device_slug,
        settings=settings,
        native_firmware_entity=_as_str(settings.get("ha_native_firmware_entity"), ""),
        app_version_entity=_as_str(settings.get("ha_app_version_entity"), ""),
        target_version=_as_str(settings.get("app_release_version"), DEFAULT_APP_RELEASE_VERSION),
    )
    write_check = _managed_write_check(device_slug)
    required_bindings = validation.get("required_bindings", []) if isinstance(validation.get("required_bindings"), list) else []
    unresolved_required = [x for x in required_bindings if not _as_bool(x.get("resolved"), False)]
    checks = [
        {
            "id": "device_selected",
            "name": "Device selected",
            "status": "pass" if bool(device_slug) else "fail",
            "detail": device_slug or "No active device slug.",
        },
        {
            "id": "required_bindings",
            "name": "Required bindings",
            "status": "pass" if not unresolved_required else "fail",
            "detail": f"{len(required_bindings) - len(unresolved_required)}/{len(required_bindings)} resolved",
        },
        {
            "id": "validation",
            "name": "Workspace validation",
            "status": "pass" if _as_bool(validation.get("ok"), False) else "fail",
            "detail": f"errors={len(validation.get('errors', []))} warnings={len(validation.get('warnings', []))}",
        },
        {
            "id": "managed_write",
            "name": "Managed paths writable",
            "status": "pass" if _as_bool(write_check.get("ok"), False) else "fail",
            "detail": _as_str(write_check.get("path"), "") if _as_bool(write_check.get("ok"), False) else _as_str(write_check.get("error"), "write check failed"),
        },
        {
            "id": "firmware_method",
            "name": "Firmware method available",
            "status": "pass" if _as_bool(caps.get("has_any_automatic_method"), False) else "warn",
            "detail": _as_str(caps.get("recommended_method"), "manual_fallback"),
        },
    ]
    remediation_actions: List[Dict[str, Any]] = []
    if unresolved_required:
        remediation_actions.append(
            {
                "id": "auto_resolve_required_mappings",
                "label": "Resolve Required Mappings",
                "detail": "Use typed entity inference to fill unresolved required bindings.",
            }
        )
        remediation_actions.append(
            {
                "id": "auto_disable_unmapped_features",
                "label": "Disable Unmapped Features",
                "detail": "Disable features with unresolved required bindings.",
            }
        )
    slot_runtime = _normalize_slot_runtime(profile.get("slot_runtime"))
    collections = profile.get("entity_collections", {}) if isinstance(profile.get("entity_collections"), dict) else {}
    enabled_lights = len([x for x in (collections.get("lights", []) if isinstance(collections.get("lights"), list) else []) if isinstance(x, dict) and _as_bool(x.get("enabled"), True)])
    enabled_cameras = len([x for x in (collections.get("cameras", []) if isinstance(collections.get("cameras"), list) else []) if isinstance(x, dict) and _as_bool(x.get("enabled"), True)])
    if enabled_lights > _as_int(slot_runtime.get("light_slot_cap"), SLOT_RUNTIME_LIMITS["lights"]["default_cap"], SLOT_RUNTIME_LIMITS["lights"]["min_cap"], SLOT_RUNTIME_LIMITS["lights"]["max_cap"]) or enabled_cameras > _as_int(slot_runtime.get("camera_slot_cap"), SLOT_RUNTIME_LIMITS["cameras"]["default_cap"], SLOT_RUNTIME_LIMITS["cameras"]["min_cap"], SLOT_RUNTIME_LIMITS["cameras"]["max_cap"]):
        remediation_actions.append(
            {
                "id": "auto_fit_slot_caps",
                "label": "Auto-Fit Slot Caps",
                "detail": "Increase runtime caps to fit enabled rows within allowed maximums.",
            }
        )
    blocking = [x for x in checks if _as_str(x.get("status"), "") == "fail"]
    ok = len(blocking) == 0
    profile_sig = _profile_signature(profile)
    token = _issue_preflight_token(device_slug, profile_sig) if ok else ""
    return {
        "ok": ok,
        "device_slug": device_slug,
        "checks": checks,
        "validation": {
            "ok": _as_bool(validation.get("ok"), False),
            "errors": validation.get("errors", []),
            "warnings": validation.get("warnings", []),
            "required_bindings": required_bindings,
            "required_bindings_summary": validation.get("required_bindings_summary", {}),
        },
        "remediation_actions": remediation_actions,
        "firmware_capabilities": caps,
        "preflight_token": token,
        "preflight_token_expires_in_s": DEPLOY_PREFLIGHT_TTL_SECONDS if token else 0,
        "profile_signature": profile_sig,
    }


def _deploy_remediate_apply(profile: Dict[str, Any], actions: List[str]) -> Dict[str, Any]:
    applied: List[str] = []
    notes: List[str] = []
    p = _normalize_profile(profile)
    requested = [a for a in actions if _as_str(a, "")]
    if not requested:
        requested = ["auto_resolve_required_mappings", "auto_fit_slot_caps", "auto_disable_unmapped_features"]
    requested = list(dict.fromkeys(requested))

    if "auto_resolve_required_mappings" in requested:
        subs = _profile_to_substitutions(p)
        suggestions = _infer_required_binding_values(p, subs)
        p.setdefault("entities", {})
        fill_count = 0
        for row in _required_bindings_snapshot(p, subs):
            if _as_bool(row.get("resolved"), False):
                continue
            key = _as_str(row.get("key"), "")
            suggested = suggestions.get(key, {})
            value = _as_str(suggested.get("value"), "").strip()
            if not value:
                continue
            p["entities"][key] = value
            fill_count += 1
        if fill_count:
            applied.append("auto_resolve_required_mappings")
            notes.append(f"filled_required_bindings={fill_count}")

    if "auto_fit_slot_caps" in requested:
        collections = p.get("entity_collections", {}) if isinstance(p.get("entity_collections"), dict) else {}
        lights = collections.get("lights", []) if isinstance(collections.get("lights"), list) else []
        cameras = collections.get("cameras", []) if isinstance(collections.get("cameras"), list) else []
        enabled_lights = len([x for x in lights if isinstance(x, dict) and _as_bool(x.get("enabled"), True)])
        enabled_cameras = len([x for x in cameras if isinstance(x, dict) and _as_bool(x.get("enabled"), True)])
        slot_runtime = _normalize_slot_runtime(p.get("slot_runtime"))
        changed = False
        if enabled_lights > _as_int(slot_runtime.get("light_slot_cap"), SLOT_RUNTIME_LIMITS["lights"]["default_cap"], SLOT_RUNTIME_LIMITS["lights"]["min_cap"], SLOT_RUNTIME_LIMITS["lights"]["max_cap"]) and enabled_lights <= SLOT_RUNTIME_LIMITS["lights"]["max_cap"]:
            slot_runtime["light_slot_cap"] = enabled_lights
            changed = True
        if enabled_cameras > _as_int(slot_runtime.get("camera_slot_cap"), SLOT_RUNTIME_LIMITS["cameras"]["default_cap"], SLOT_RUNTIME_LIMITS["cameras"]["min_cap"], SLOT_RUNTIME_LIMITS["cameras"]["max_cap"]) and enabled_cameras <= SLOT_RUNTIME_LIMITS["cameras"]["max_cap"]:
            slot_runtime["camera_slot_cap"] = enabled_cameras
            changed = True
        if changed:
            p["slot_runtime"] = _normalize_slot_runtime(slot_runtime)
            applied.append("auto_fit_slot_caps")
            notes.append("slot_runtime_caps_adjusted")

    _sync_slots_from_collections(p)
    if "auto_disable_unmapped_features" in requested:
        unresolved = [x for x in _required_bindings_snapshot(p) if not _as_bool(x.get("resolved"), False)]
        if unresolved:
            features = p.get("features", {}) if isinstance(p.get("features"), dict) else {}
            disabled: List[str] = []
            for row in unresolved:
                feature = _as_str(row.get("feature"), "")
                if feature and _as_bool(features.get(feature), False):
                    features[feature] = False
                    disabled.append(feature)
            if disabled:
                p["features"] = features
                _apply_feature_page_policy(p)
                applied.append("auto_disable_unmapped_features")
                notes.append("disabled_features=" + ",".join(sorted(set(disabled))))

    incoming_instances = isinstance(p.get("entity_instances"), list) and len(p.get("entity_instances", [])) > 0
    _normalize_entity_instances(p, incoming_has_instances=incoming_instances)
    _sync_slots_from_collections(p)
    return {"profile": p, "applied": applied, "notes": notes}


@app.post("/api/deploy/preflight")
def api_deploy_preflight() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    result = _deploy_preflight_result(workspace, profile, payload)
    return jsonify(
        {
            "ok": _as_bool(result.get("ok"), False),
            "workspace": workspace,
            "profile": profile,
            "active_device_index": idx,
            **result,
        }
    )


@app.post("/api/deploy/remediate")
def api_deploy_remediate() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, idx = _workspace_or_profile_from_payload(payload)
    actions_raw = payload.get("actions")
    actions = [str(x) for x in actions_raw] if isinstance(actions_raw, list) else []
    remediate = _deploy_remediate_apply(profile, actions)
    profile = remediate["profile"] if isinstance(remediate.get("profile"), dict) else profile
    workspace = _workspace_with_profile(workspace, profile, idx)
    workspace, saved = _maybe_persist_workspace(payload, workspace)
    preflight = _deploy_preflight_result(workspace, profile, payload)
    return jsonify(
        {
            "ok": True,
            "workspace": workspace,
            "profile": profile,
            "active_device_index": idx,
            "saved_workspace": saved,
            "remediation": {
                "applied": remediate.get("applied", []),
                "notes": remediate.get("notes", []),
            },
            "preflight": preflight,
        }
    )


@app.get("/api/deploy/last_run")
def api_deploy_last_run() -> Any:
    runtime = _runtime_state_snapshot()
    return jsonify(
        {
            "ok": True,
            "last_run": runtime.get("last_deploy_run", {}),
        }
    )


@app.post("/api/deploy/run")
def api_deploy_run() -> Any:
    payload = request.get_json(silent=True) or {}
    workspace, profile, _ = _workspace_or_profile_from_payload(payload)
    deployment = workspace.get("deployment", {}) if isinstance(workspace.get("deployment"), dict) else {}
    git_ref = _as_str(payload.get("git_ref"), _as_str(deployment.get("git_ref"), _as_str(profile.get("device", {}).get("git_ref"), ADDON_GITHUB_REF)))
    git_url = _as_str(payload.get("git_url"), _as_str(deployment.get("git_url"), _as_str(profile.get("device", {}).get("git_url"), ADDON_GITHUB_REPO_URL)))
    require_confirm = _as_bool(payload.get("require_confirm"), True)
    confirmed = _as_bool(payload.get("confirmed"), False)
    guided_mode = _as_bool(payload.get("guided_mode"), False)
    require_preflight_token = _as_bool(payload.get("require_preflight_token"), guided_mode)
    preflight_token = _as_str(payload.get("preflight_token"), "").strip()
    run_firmware = _as_bool(payload.get("run_firmware"), True)
    firmware_mode = _as_str(payload.get("firmware_mode"), "auto").strip().lower() or "auto"
    if firmware_mode not in {"auto", "build_install", "install_only", "manual_fallback"}:
        firmware_mode = "auto"

    validation = _validate_profile(profile)
    if not validation.get("ok"):
        result = {"ok": False, "error": "validation_failed", "validation": validation}
        _save_last_deploy_run(result)
        return jsonify(result), 400

    profile_sig = _profile_signature(profile)
    device_slug_for_token = _managed_device_slug(profile)
    if require_preflight_token:
        valid_token, token_err = _verify_preflight_token(preflight_token, device_slug_for_token, profile_sig)
        if not valid_token:
            result = {
                "ok": False,
                "error": token_err,
                "needs_preflight": True,
                "validation": validation,
                "device_slug": device_slug_for_token,
            }
            _save_last_deploy_run(result)
            return jsonify(result), 412

    preview = _preview_managed_apply(workspace, profile, git_ref or ADDON_GITHUB_REF, git_url or ADDON_GITHUB_REPO_URL)
    if require_confirm and not confirmed:
        result = {
            "ok": False,
            "error": "confirmation_required",
            "needs_confirmation": True,
            "preview": preview,
            "validation": validation,
        }
        _save_last_deploy_run(result)
        return jsonify(
            {
                **result
            }
        ), 412

    device_slug = _as_str(preview.get("device_slug"), "")
    lock = _get_apply_lock(device_slug)
    if not lock.acquire(blocking=False):
        return jsonify({"ok": False, "error": "apply_in_progress", "device_slug": device_slug}), 409
    try:
        committed = _commit_managed_preview(
            preview,
            profile,
            workspace,
            reason="deploy_run",
            context={
                "source": "api_deploy_run",
                "run_firmware": run_firmware,
                "firmware_mode": firmware_mode,
            },
        )
    finally:
        lock.release()

    firmware_result: Dict[str, Any] = {"ok": True, "skipped": True}
    firmware_status_code = 200
    if run_firmware:
        fw_payload = dict(payload)
        fw_payload["workspace"] = workspace
        fw_payload["profile"] = profile
        fw_payload["device_slug"] = device_slug
        fw_payload["mode"] = firmware_mode
        fw_payload["backup_first"] = False
        firmware_result, firmware_status_code = _execute_firmware_workflow(fw_payload)
    ok = committed is not None and _as_bool(firmware_result.get("ok"), True if not run_firmware else False)
    status_code = 200 if ok else (firmware_status_code if run_firmware else 500)
    result = {
        "ok": ok,
        "device_slug": device_slug,
        "validation": validation,
        "preview": preview,
        "apply": committed,
        "firmware": firmware_result,
        "pipeline": {
            "validate": True,
            "preview": True,
            "backup": True,
            "write_managed_files": True,
            "firmware_workflow": run_firmware,
        },
        "preflight": {
            "required": require_preflight_token,
            "token_used": bool(preflight_token),
            "token_valid": True if not require_preflight_token else True,
        },
    }
    _save_last_deploy_run(result)
    return jsonify(result), status_code


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

