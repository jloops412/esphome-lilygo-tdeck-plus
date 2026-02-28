# Handoff Context

## Repository state
1. Branch: `main`
2. Latest LVGL tag: `v0.9.1-lvgl-gps-hotfix`
3. Previous LVGL tag: `v0.9.0-lvgl-controls-calreview-gpsdiag` (`58f903e`)
4. Previous LVGL tag: `v0.8.0-lvgl-groundup-ui2` (`12bd551`)

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

## Ground-up LVGL UI pass in `v0.8.0-lvgl-groundup-ui2`
1. Home page:
   - Reworked to launcher-first layout with stronger control hierarchy.
   - Lights is now a large primary action; weather/reader/settings/theme/touchcal remain one tap away.
2. Lights page:
   - Reworked into two-zone controller layout.
   - Left rail: direct light target selection list.
   - Right panel: contextual actions (`Toggle`, `Dim`, `Bright`, `< Light`, `Light >`, `Warm`, `Cool`, quick colors, `Preset`).
3. Reader page:
   - Converted to full-width source rows with live snippet labels for BBC/DC/Loudoun/Word/Quote.
4. Calibration quality:
   - Replaced single-pass 9-point regression with averaged column/row edge-fit regression.
   - Updated calibration target geometry for edge coverage while avoiding bezel dead zones.
   - Calibration still applies live and persists across reboot.
5. Docs/process:
   - README and release docs updated in same pass.
   - Handoff context updated in same pass (this file).

## Controls + calibration review + GPS diagnostics in `v0.9.0-lvgl-controls-calreview-gpsdiag`
1. Calibration:
   - 9-point flow now ends with explicit `Save` or `Retry` prompt.
   - Prevents accidental bad capture from being auto-committed.
   - Keyboard shortcuts added for review step: `Y=Save`, `U=Retry`.
2. Lights page:
   - Added LVGL sliders for selected-light brightness and color temperature.
   - Preserved quick action keys/buttons for fast control.
3. UI cleanup:
   - Reduced duplicate utility buttons on Home and Reader.
   - Kept utility actions in Settings/Theme/Shortcuts where they are easier to find.
4. Theme controls:
   - Expanded palette set from 3 to 5 (`Graphite`, `Ocean`, `Amber`, `Rose`, `Teal`).
   - Added display and keyboard backlight sliders on Theme page.
5. GPS diagnostics:
   - Added `gps_baud_rate` substitution to install/profile entrypoints.
   - Added telemetry entities: GPS data age, GPS data alive, GPS status text.
   - Updated Home/Weather status messaging to differentiate no-data vs searching vs fix.
6. Docs/process:
   - README, release, LVGL plan, and handoff docs updated in same pass.

## GPS compile hotfix in `v0.9.1-lvgl-gps-hotfix`
1. Fixed HA compile/config parse error:
   - removed unsupported `update_interval` from `binary_sensor.template` in `gps_uart.yaml`.
2. No UI behavior changes in this hotfix.
3. Docs/handoff updated in same pass.

## Immediate validation asks
1. Flash LVGL install YAML pinned to `v0.9.1-lvgl-gps-hotfix`.
2. Verify:
   - config parse succeeds (no `binary_sensor.template update_interval` error)
   - calibration flow ends with `Save`/`Retry` and does not auto-save bad captures
   - lights sliders apply correctly to selected entity (`brightness_pct` and `color_temp_kelvin`)
   - reduced utility-button duplication still keeps navigation discoverable
   - GPS diagnostic entities update (`GPS Data Alive`, `GPS Last Data Age`, `GPS Status`)
   - keyboard shortcuts (`Q/E`, `WASD`, `Tab/Esc`, `K/R/C`, `/`, `Alt+K`)
   - trackball focus movement and click activation
   - calibration persistence across reboot

## Notes
1. Manual-rendered stable path remains functional and is the fallback.
2. LVGL path is intentionally parallel and should not overwrite stable by default.
