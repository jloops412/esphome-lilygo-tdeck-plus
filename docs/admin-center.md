# Admin Center

## Current model

Hybrid admin path is now implemented:

1. Firmware runtime admin via ESPHome `web_server` entities.
2. Home Assistant add-on (Ingress): `tdeck-admin-center`.
3. Static generator companion: `tools/admin-center/`.

## Firmware-side access

From the T-Deck device:

1. Open `Settings`.
2. `System` panel shows:
   - `Device: http://<device-ip>`
   - `HA: Add-ons -> T-Deck Admin Center`

## HA Add-on (Ingress) v1

Path: `tdeck-admin-center/`

Features:

1. Discover entities from HA (`/api/discovery/*`).
2. Generate drop-in install YAML (`/api/generate/install`).
3. Generate substitutions overrides YAML (`/api/generate/overrides`).

Scope in v1:

- Generate/export only.
- Does not auto-overwrite `/config/esphome` files.

## Static generator companion

Path: `tools/admin-center/`

This remains useful outside HA add-on runtime (local browser use).
