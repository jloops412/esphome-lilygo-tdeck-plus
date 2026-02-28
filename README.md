# LilyGO T-Deck Plus HA Controller

This repo tracks the ESPHome controller work for LilyGO T-Deck Plus.

Current priorities:

1. Preserve the known-good manual-rendered baseline.
2. Improve UI/UX without destabilizing display/touch/input.
3. Add GPS entity support.
4. Improve keyboard backlight wake behavior while preserving manual `Alt+B`.
5. Maintain a single drop-in install YAML for ESPHome/HA.

## Install

Stable install YAML:

- `esphome/install/lilygo-tdeck-plus-install.yaml`

LVGL beta install YAML (parallel track):

- `esphome/install/lilygo-tdeck-plus-install-lvgl.yaml`

Each install YAML pulls modular files from this repo by release tag.

## Current UI flow

1. `Home`: clean launcher page (`Lights`, `Weather`, `Reader`, `Settings`, `Themes`, `Sleep`).
2. `Lights`: controller-first page with direct light selection and contextual actions (`Toggle`, `Dim`, `Bright`, `Warm`, `Cool`, `Preset`).
3. `Weather`: cleaner dashboard page with primary temp/condition + compact multi-metric rows.
4. `Reader`: feed/source launcher into full detail reader.
5. `Settings`: wake and timeout controls plus keyboard-backlight toggle.
6. `Theme`: on-device theme presets and display brightness tuning.

## Quick keyboard shortcuts

1. `1`..`6`: jump directly to pages `Home/Lights/Weather/Reader/Settings/Theme`.
2. `Q` / `E`: previous/next page.
3. `Tab` or `D`/`S`: move focus forward.
4. `Esc` or `A`/`W`: move focus backward.
5. `[` / `]`: previous/next selected light.
6. `-` / `+`: dim/brighten selected light.
7. `T`: toggle selected light.
8. `P`: cycle light preset.
9. `B`: keyboard backlight toggle.
10. `N` / `M`: keyboard backlight down/up.
11. `H`: jump to Home page.
12. `K`: start touch calibration.
13. `R`: reset stored calibration values.
14. `C`: toggle touch debug.

Touch calibration in LVGL mode now uses a full-screen 9-point capture flow.
Captured calibration is applied live and persisted across reboot.
Default values can still be set in one place via install YAML substitutions:
`touch_x_min`, `touch_x_max`, `touch_y_min`, `touch_y_max`.

See [`docs/architecture.md`](docs/architecture.md), [`docs/migration.md`](docs/migration.md), [`docs/lvgl-plan.md`](docs/lvgl-plan.md), and [`docs/release.md`](docs/release.md) for conventions and release details.
