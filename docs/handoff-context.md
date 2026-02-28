# Handoff Context

## Repository state
1. Branch: `main`
2. Latest LVGL tag: `v0.6.1-lvgl-beta1-hotfix`
3. Latest commit at tag: `463c855`
4. Previous LVGL beta tag: `v0.6.0-lvgl-beta1` (`f11fad2`)

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

## Confirmed blocker (resolved in hotfix)
1. HA compile failed on LVGL install due to missing script IDs:
   - `page_next`
   - `page_prev`
2. Error source:
   - `esphome/packages/board_base.yaml` template buttons (`Next Page`, `Previous Page`) call these IDs.
3. Hotfix status:
   - `ui_lvgl.yaml` now defines `page_next` and `page_prev` scripts mapped to LVGL page navigation.

## Immediate fix path
1. Keep stable install path unchanged.
2. Tag and pin LVGL install YAML to hotfix release.
3. Re-test compile in HA with LVGL install entrypoint.

## Notes
1. Manual-rendered stable path remains functional and is the fallback.
2. LVGL path is intentionally parallel and should not overwrite stable by default.
