# Release Process

## Tags

- `v0.1.0-stable`: parity baseline milestone.
- `v0.2.0-gps-kb`: GPS + keyboard wake improvements.
- `v0.3.0-ui-pass1`: first UI redesign milestone.
- `v0.3.1-ui-pass1-hotfix`: ESP32-S3 logger linker fix.
- `v0.4.0-ui-pass2`: controller-first UX pass + keyboard shortcuts + weather robustness.

`v0.4.0-ui-pass2` highlights:

1. Light control flow now centers around `CTRL` page with `Prev/Toggle/Next` plus `Dim/Bright`.
2. Presets page changed from raw colors to practical scenes: `Warm/Cool/Relax/Focus/Party`.
3. Keyboard shortcuts added for page jumps and light control: `1`..`6`, `[`, `]`, `-`, `+`, `T`.
4. Weather formatting now handles invalid/missing values without rendering junk.
5. Settings page includes wake-on-trackball toggle and touch calibration access.
6. Removed unused gust/dew numeric imports that could spam `unknown -> number` warnings.

## Checklist per release

1. `esphome config` passes for `esphome/profiles/stable_snapshot.yaml`.
2. HA add-on compile passes for install YAML.
3. Boot/display/touch/trackball/keyboard parity verified.
4. New features verified (GPS entities, keyboard wake behavior).
5. Tag and push release.
