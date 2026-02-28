# Handoff Context

## Repository state
1. Branch: `main`
2. Latest LVGL tag: `v0.6.3-lvgl-calibration-overrides`
3. Previous LVGL tag: `v0.6.2-lvgl-input-parity` (`9f3e99e`)
4. Previous LVGL hotfix tag: `v0.6.1-lvgl-beta1-hotfix` (`463c855`)

## Install entrypoints
1. Stable install YAML:
   - `esphome/install/lilygo-tdeck-plus-install.yaml`
2. LVGL beta install YAML:
   - `esphome/install/lilygo-tdeck-plus-install-lvgl.yaml`

## LVGL beta packages
1. `esphome/packages/display_mipi_lvgl.yaml`
2. `esphome/packages/input_touch_gt911_lvgl.yaml`
3. `esphome/packages/input_trackball_lvgl.yaml`
4. `esphome/packages/input_keyboard_i2c_lvgl.yaml`
5. `esphome/packages/ui_lvgl.yaml`
6. Local profile: `esphome/profiles/lvgl_experimental.yaml`

## Input parity updates in `v0.6.2-lvgl-input-parity`
1. Touch calibration:
   - Replaced no-op calibration with a 4-point calibration capture page (`touch_cal_page`).
   - Added corner raw capture globals and computed suggested values:
     - `touch_cal_suggest_x_min`
     - `touch_cal_suggest_x_max`
     - `touch_cal_suggest_y_min`
     - `touch_cal_suggest_y_max`
   - Suggested values are shown on-device and logged via ESPHome logs.
2. Trackball navigation:
   - LVGL keypad mapping now uses `prev/next/up/down/enter` with `nav_group`.
   - Added default focus on boot (`home_lights_btn`) to ensure click/navigation has a focused target.
3. Keyboard shortcuts:
   - Restored parity keys in LVGL keyboard package:
     - `Q/E` page previous/next
     - `K/R/C` calibration start/reset/debug
     - `WASD` + `Tab/Esc` focus previous/next
     - existing light and keyboard-backlight shortcuts retained
4. Docs updated:
   - `README.md`, `docs/release.md`, `docs/migration.md`, `docs/lvgl-plan.md`, and this handoff file.

## One-YAML calibration update in `v0.6.3-lvgl-calibration-overrides`
1. `input_touch_gt911_lvgl.yaml` now reads calibration from substitutions:
   - `touch_x_min`
   - `touch_x_max`
   - `touch_y_min`
   - `touch_y_max`
2. `esphome/install/lilygo-tdeck-plus-install-lvgl.yaml` now exposes those substitutions at top level.
3. Calibration values suggested by the on-device flow can be applied in one install YAML edit.

## Immediate validation asks
1. Flash LVGL install YAML pinned to `v0.6.3-lvgl-calibration-overrides`.
2. Verify:
   - trackball focus movement and center click activation
   - keyboard shortcuts (`Q/E`, `WASD`, `Tab/Esc`, `K/R/C`)
   - touch calibration page capture flow and suggested values output

## Notes
1. Manual-rendered stable path remains functional and is the fallback.
2. LVGL path is intentionally parallel and should not overwrite stable by default.
