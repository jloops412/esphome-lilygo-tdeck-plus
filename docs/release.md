# Release Process

## Tags

- `v0.1.0-stable`: parity baseline milestone.
- `v0.2.0-gps-kb`: GPS + keyboard wake improvements.
- `v0.3.0-ui-pass1`: first UI redesign milestone.
- `v0.3.1-ui-pass1-hotfix`: ESP32-S3 logger linker fix.
- `v0.4.0-ui-pass2`: controller-first UX pass + keyboard shortcuts + weather robustness.
- `v0.5.0-ui-groundup`: home-menu navigation + theme system + full layout refactor.

`v0.5.0-ui-groundup` highlights:

1. Removed always-visible tab bar and replaced with a clean `Home` launcher + subpages.
2. Light controls are now consolidated into one dedicated controller surface.
3. Added on-device multi-theme switching (`Graphite`, `Ocean`, `Amber`).
4. Added dedicated theme/control page for display tuning and debug toggles.
5. Touch behavior updated with a consistent header `HOME` action on subpages.
6. Existing stable display/touch/trackball/keyboard architecture preserved.

## Checklist per release

1. `esphome config` passes for `esphome/profiles/stable_snapshot.yaml`.
2. HA add-on compile passes for install YAML.
3. Boot/display/touch/trackball/keyboard parity verified.
4. New features verified (GPS entities, keyboard wake behavior).
5. Tag and push release.
