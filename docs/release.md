# Release Process

## Tags

- `v0.1.0-stable`: parity baseline milestone.
- `v0.2.0-gps-kb`: GPS + keyboard wake improvements.
- `v0.3.0-ui-pass1`: first UI redesign milestone.
- `v0.3.1-ui-pass1-hotfix`: ESP32-S3 logger linker fix.
- `v0.4.0-ui-pass2`: controller-first UX pass + keyboard shortcuts + weather robustness.
- `v0.5.0-ui-groundup`: home-menu navigation + theme system + full layout refactor.
- `v0.6.0-lvgl-beta1`: parallel LVGL interface track and migration starter.

Post-tag note:

- `v0.6.0-lvgl-beta1` has a compile blocker in HA when using the LVGL install YAML:
  - `board_base.yaml` template buttons call `page_next`/`page_prev`
  - `ui_lvgl.yaml` did not yet define those script IDs
  - fix is to add LVGL-compatible `page_next`/`page_prev` scripts (or decouple those template buttons from LVGL profile)

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
