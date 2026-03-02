# Cameras

## Goal

Optional snapshot camera support that does not affect users who do not configure cameras.

## Substitutions

- `camera_slot_count`: `0`, `1`, `2`
- `camera_slot_1_name`, `camera_slot_2_name`
- `camera_slot_1_entity`, `camera_slot_2_entity`
- `camera_refresh_interval_s`
- `camera_snapshot_enable`
- `camera_snapshot_dir` (default `/config/www/tdeck`)
- `ha_base_url` (default `http://homeassistant.local:8123`)

## Flow

1. Trigger HA service `camera.snapshot`.
2. Save snapshot to `/config/www/tdeck/cam1.jpg` and `cam2.jpg`.
3. Fetch via `online_image` from `/local/tdeck/camX.jpg`.
4. Cache-bust image URL with millis query parameter.

## UI

- Home camera launcher (hidden when disabled).
- `Cameras` page with up to two snapshot cards.
- `Camera Detail` page for focused view.
- Manual refresh + auto-refresh toggle.

