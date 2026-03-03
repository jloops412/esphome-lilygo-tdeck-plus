# Architecture

## Product path

- Primary UI path: LVGL (`ui_lvgl.yaml`)
- Deployment contract: one install YAML that imports modular packages
- Stable hardware stack: custom MIPI display + GT911 + trackball + keyboard I2C
- Public release channel: `stable` branch ref (moving stable pointer)

## Package topology

- `board_base.yaml`: board identity, fonts/icons, connectivity, base services
- `display_mipi_lvgl.yaml`: display transport/init
- `input_touch_gt911_lvgl.yaml`: touch and calibration capture
- `input_trackball_lvgl.yaml`: trackball GPIO inputs
- `input_keyboard_i2c_lvgl.yaml`: keyboard read + ALT shortcuts
- `ha_entities.yaml`: HA mirrors and substitution interfaces
- `persistence_globals.yaml`: persisted and runtime state model
- `gps_uart.yaml`: GPS transport and sensors
- `ui_lvgl.yaml`: pages, scripts, dynamic sync, app flow

## Public substitution contract highlights

- visibility toggles:
  - `ui_show_*`
  - `home_tile_show_*`
- theme tokens:
  - `theme_token_*`
  - `theme_border_width`
  - `theme_radius`
  - `theme_icon_mode`
- optional cameras:
  - `camera_slot_count` (`0..2`)
  - `camera_slot_#_entity`
  - `camera_refresh_interval_s`

## Runtime model

1. Inputs update activity state (`activity_note`) and page actions.
2. UI scripts update model first, then commit to HA.
3. Periodic loops are split:
   - reliability checks (`screensaver_tick`, climate ack)
   - label refresh
   - weather model refresh
   - optional camera refresh
4. UI sync guards prevent script feedback loops.

## Keyboard input model

- Strict ALT-only command shortcuts (ESC-prefix arm behavior on this keyboard path).
- ALT arm window is tunable (`keyboard_alt_timeout_ms`).
- Diagnostic globals:
  - `kb_alt_armed`
  - `kb_alt_last_timeout_ms`
  - `kb_last_shortcut_text`

## Climate reliability model

- Device-led optimistic local targets
- mode-aware commit payloads
- ack window + timeout detection
- out-of-sync diagnostics + manual retry

## Camera snapshot model

- Optional feature, disabled when `camera_slot_count=0`
- HA `camera.snapshot` writes files into `/config/www/tdeck`
- `online_image` loads from `/local/tdeck/camX.jpg` with cache busting
- manual and interval-driven refresh supported
- camera diagnostics are surfaced in Settings diagnostics panel

## Theme studio model

- Token-based editor (9 theme tokens).
- Swatch-based palette workflow (3 pages, 24 swatches/page).
- Token apply/revert with immediate style refresh.
- Shape controls remain live:
  - border width
  - radius
  - icon recolor mode

## Public/private config strategy

- Public install/template files are generic.
- Personal mappings live under `esphome/install/personal/<profile>/`.

## Admin center model

1. Device runtime controls through ESPHome entities/web server.
2. HA Ingress add-on for discover + mapping studio + workspace/device management.
3. V5 UX is dashboard-first with dual-mode controls:
   - Dashboard: status/action launch and camera autodetect onboarding
   - Guided: step-by-step onboarding and deploy flow
   - Advanced: diagnostics + raw generation/update controls
4. Discovery is job-based (`start/status/cancel`) to keep UI responsive on large HA installs.
5. Managed apply writes only under `/config/esphome/tdeck` with automatic snapshot backups.
6. Generated managed files are emitted per-device:
   - `generated/entities.generated.yaml`
   - `generated/theme.generated.yaml`
   - `generated/layout.generated.yaml`
   - `generated/pages/home.generated.yaml`
   - `generated/pages/lights.generated.yaml`
   - `generated/pages/weather.generated.yaml`
   - `generated/pages/climate.generated.yaml`
7. Static generator tool in repo remains available for offline scaffolding.
8. Updates tab generates HA package for update-button flow, proxied to native ESPHome firmware updater.
