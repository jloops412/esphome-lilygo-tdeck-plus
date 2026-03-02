# Architecture

## Product path

- Primary UI path: LVGL (`ui_lvgl.yaml`)
- Deployment contract: one install YAML that imports modular packages
- Stable hardware stack: custom MIPI display + GT911 + trackball + keyboard I2C

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
2. HA Ingress add-on for discover + config generation.
3. Static generator tool in repo for offline use.
