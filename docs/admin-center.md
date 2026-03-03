# Admin Center

## Current model

Hybrid admin path is now implemented:

1. Firmware runtime admin via ESPHome `web_server` entities.
2. Home Assistant add-on (Ingress): `tdeck_admin_center`.
3. Static generator companion: `tools/admin-center/`.

## Firmware-side access

From the T-Deck device:

1. Open `Settings`.
2. `System` panel shows:
   - `Device: http://<device-ip>`
   - `HA: Add-ons -> T-Deck Admin Center`

## HA Add-on (Ingress) v1

Path: `tdeck_admin_center/`

Features:

1. Discover entities from HA (`/api/discovery/*`).
2. Generate drop-in install YAML (`/api/generate/install`).
3. Generate substitutions overrides YAML (`/api/generate/overrides`).

Scope in v1:

- Generate/export only.
- Does not auto-overwrite `/config/esphome` files.

## Troubleshooting add-on install

If HA reports:

- `... is not a valid add-on repository`
- `unknown error occurred while trying to build the image`

Use this recovery sequence:

1. Remove the custom repository from Add-on Store.
2. Restart Supervisor.
3. Re-add repository URL:
   - `https://github.com/jloops412/esphome-lilygo-tdeck-plus`
4. Confirm add-on version is `0.20.2`.
5. Install `T-Deck Admin Center` again.
6. Open logs from the add-on page if build fails again and capture the first Python/Docker error block.

Known fixed root cause in `0.20.2`:

- Dockerfile now copies `run.sh` into container root and normalizes line endings before chmod.

## Static generator companion

Path: `tools/admin-center/`

This remains useful outside HA add-on runtime (local browser use).
