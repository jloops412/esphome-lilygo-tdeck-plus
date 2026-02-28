# Handoff Context

## Repository state
1. Branch: `main`
2. Latest LVGL tag: `v0.7.1-lvgl-modern-ui-shortcuts`
3. Previous LVGL tag: `v0.7.0-lvgl-cal9-controller-ui` (`f6f4d22`)
4. Previous LVGL tag: `v0.6.3-lvgl-calibration-overrides` (`58aed5a`)

## Process Contract
1. Every code change must update documentation files in Git in the same iteration.
2. Every code change must update `docs/handoff-context.md` in the same iteration.
3. Never close a work pass without docs + handoff parity.

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

## Calibration + UI update in `v0.7.0-lvgl-cal9-controller-ui`
1. Touch calibration:
   - Upgraded to a full-screen 9-point flow.
   - Captured values are applied live via `id(tdeck_touch).set_calibration(...)`.
   - Suggested values persist (`restore_value: yes`) and are re-applied on boot.
2. Calibration persistence behavior:
   - Starting calibration no longer clears existing saved calibration values.
   - Reset calibration restores install-default substitution values and reapplies immediately.
3. LVGL lights page redesign:
   - Direct light target selection buttons (6 lights).
   - Contextual action column (`Toggle`, `Dim`, `Bright`, `Warm`, `Cool`, `Preset Cycle`).
   - Active light summary and state shown in-page.
4. Weather page update:
   - Added `Feels` row and denser metric formatting for quick glance readability.

## UX + calibration polish in `v0.7.1-lvgl-modern-ui-shortcuts`
1. Calibration quality:
   - 9-point calibration fitting now uses regression across all targets.
   - This improves stability vs edge-only averaging.
2. Shortcuts discoverability:
   - Added dedicated `shortcuts_page`.
   - Added keyboard open actions:
     - `Alt+K` via ESC-prefix chord handling.
     - `/` or `?` direct open.
3. Home polish:
   - Home layout now uses stronger visual hierarchy and action grouping.
   - Added `Keys` button and top-level quick access to shortcuts + touch calibration.
4. Light controller polish:
   - Refined list/control style contrast using soft/action/success styles.
5. Process:
   - Added explicit process policy to docs to enforce docs/handoff updates every pass.

## Immediate validation asks
1. Flash LVGL install YAML pinned to `v0.7.1-lvgl-modern-ui-shortcuts`.
2. Verify:
   - trackball focus movement and center click activation
   - keyboard shortcuts (`Q/E`, `WASD`, `Tab/Esc`, `K/R/C`, `/`, `Alt+K`)
   - touch calibration 9-point flow applies live and still works after reboot
   - lights page direct-selection flow is responsive with touch/trackball/keyboard

## Notes
1. Manual-rendered stable path remains functional and is the fallback.
2. LVGL path is intentionally parallel and should not overwrite stable by default.
