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

## Public/private config strategy

- Public install/template files are generic.
- Personal mappings live under `esphome/install/personal/<profile>/`.

