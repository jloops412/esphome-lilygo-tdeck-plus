# Handoff Context

## Repository state
1. Branch: `main`
2. Latest tag before hotfix: `v0.6.0-lvgl-beta1`
3. Latest commit at tag: `f11fad2`

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

## Confirmed blocker
1. HA compile fails on LVGL install due to missing script IDs:
   - `page_next`
   - `page_prev`
2. Error source:
   - `esphome/packages/board_base.yaml` template buttons (`Next Page`, `Previous Page`) call these IDs.
3. LVGL script package currently defines many UI scripts, but not those two IDs.

## Immediate fix path
1. Add script IDs `page_next` and `page_prev` to `esphome/packages/ui_lvgl.yaml`.
2. Implement them as LVGL page navigation wrappers (e.g., `lvgl.page.next` / `lvgl.page.previous`).
3. Keep stable install path unchanged.
4. Tag a hotfix release after verification.

## Notes
1. Manual-rendered stable path remains functional and is the fallback.
2. LVGL path is intentionally parallel and should not overwrite stable by default.
