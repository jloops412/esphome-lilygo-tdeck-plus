# Cameras

## Behavior

Camera support is optional and inert by default.

- `camera_slot_count: "0"` hides camera UI.
- Set `camera_slot_count` to `1..8` to enable camera pages.

Admin Center also supports camera autodetect (`scan/accept/ignore`) and can populate camera instances from HA discovery.

## Substitutions

- `camera_slot_count` (`0..8`)
- `camera_slot_<n>_name` / `camera_slot_<n>_entity` (`n=1..8`)
- `camera_refresh_interval_s`
- `camera_snapshot_enable`
- `camera_snapshot_dir` (default `/config/www/tdeck`)
- `ha_base_url` (default `http://homeassistant.local:8123`)
- runtime paging keys: `generated_camera_slot_cap`, `generated_camera_page_size`

## Snapshot flow

1. Firmware triggers `camera.snapshot` in HA.
2. Snapshot files are written under `/config/www/tdeck/`.
3. Device renders via `online_image` from `${ha_base_url}/local/tdeck/...`.
4. URL cache busting uses a refresh timestamp query parameter.

## UI

- Home camera launcher (auto-hidden when disabled)
- Cameras list with paging
- Camera detail view for selected camera
- Manual refresh and auto-refresh controls
- Diagnostics in Settings (`camera_refresh_status_text`, `camera_last_snapshot_result`)

## Degradation behavior

Missing or unavailable camera entities must show status text and never break page rendering.
