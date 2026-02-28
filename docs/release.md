# Release Process

## Tags

- `v0.1.0-stable`: parity baseline milestone.
- `v0.2.0-gps-kb`: GPS + keyboard wake improvements.
- `v0.3.0-ui-pass1`: first UI redesign milestone.
- `v0.3.1-ui-pass1-hotfix`: ESP32-S3 logger linker fix.
- `v0.4.0-ui-pass2`: controller-first UX pass + keyboard shortcuts + weather robustness.
- `v0.5.0-ui-groundup`: home-menu navigation + theme system + full layout refactor.
- `v0.6.0-lvgl-beta1`: parallel LVGL interface track and migration starter.
- `v0.6.1-lvgl-beta1-hotfix`: LVGL compile fix for shared board template buttons.
- `v0.6.2-lvgl-input-parity`: LVGL input parity pass for calibration, trackball navigation, and shortcut restore.
- `v0.6.3-lvgl-calibration-overrides`: install-time touch calibration substitutions in one YAML.

Post-tag note:

- `v0.6.0-lvgl-beta1` has a compile blocker in HA when using the LVGL install YAML:
  - `board_base.yaml` template buttons call `page_next`/`page_prev`
  - `ui_lvgl.yaml` did not yet define those script IDs
  - fix is to add LVGL-compatible `page_next`/`page_prev` scripts (or decouple those template buttons from LVGL profile)

`v0.6.1-lvgl-beta1-hotfix` highlights:

1. Added `page_next` and `page_prev` script IDs in `ui_lvgl.yaml`.
2. Kept `board_base` template buttons compatible with both stable and LVGL install paths.
3. Updated LVGL status docs and handoff notes.

`v0.6.2-lvgl-input-parity` highlights:

1. Replaced LVGL touch calibration no-op with a working 4-point capture assistant page.
2. Added computed `x_min/x_max/y_min/y_max` calibration suggestions and runtime logs.
3. Updated LVGL keypad mapping to `prev/next/up/down/enter` for 5-key trackball navigation.
4. Restored keyboard shortcut parity keys (`Q/E`, `K/R/C`, `WASD` focus nav, plus existing light/backlight shortcuts).
5. Added shared calibration globals for raw capture and suggested calibration values.

`v0.6.3-lvgl-calibration-overrides` highlights:

1. LVGL touch package now reads calibration from substitutions (`touch_x_min/x_max/y_min/y_max`).
2. LVGL install YAML now exposes those substitutions directly.
3. Calibration suggestions from the on-device flow can now be applied without editing package files.

`v0.6.0-lvgl-beta1` highlights:

1. Added a parallel LVGL package stack (`display_mipi_lvgl`, LVGL input packages, `ui_lvgl`).
2. Added a dedicated LVGL install YAML for HA testing.
3. Added an LVGL profile for local iterative development.
4. Implemented LVGL pages for `Home`, `Lights`, `Weather`, `Reader`, `Settings`, and `Theme`.
5. Bound trackball directions/click to LVGL keypad navigation.
6. Added an LVGL migration plan document and kept stable install path intact.

## Checklist per release

1. `esphome config` passes for `esphome/profiles/stable_snapshot.yaml`.
2. HA add-on compile passes for install YAML.
3. Boot/display/touch/trackball/keyboard parity verified.
4. New features verified (GPS entities, keyboard wake behavior).
5. Tag and push release.
