# LilyGO T-Deck Plus HA Controller

This repo tracks the ESPHome controller work for LilyGO T-Deck Plus.

## Process Policy

1. Every code change must include documentation updates in Git.
2. Every code change must include `docs/handoff-context.md` updates in the same iteration.

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

1. `Home`: cleaner launcher-first layout with core destinations only (`Lights`, `Weather`, `Reader`, `Settings`, `Themes`, `Sleep`).
2. `Lights`: two-zone controller layout with direct target list + richer controls:
   - quick actions (`Toggle`, `Dim`, `Bright`, `Warm`, `Cool`, color chips, preset)
   - LVGL sliders for per-light brightness and color temperature
3. `Weather`: glance dashboard with large temperature, readable condition, compact metrics, and explicit GPS diagnostic state.
4. `Reader`: source list with live preview snippets for BBC/DC/Loudoun/Word/Quote.
5. `Settings`: wake behavior, saver timing, keyboard backlight, plus direct shortcuts/theme/calibration access.
6. `Theme`: expanded palette set (`Graphite`, `Ocean`, `Amber`, `Rose`, `Teal`) and LVGL sliders for display + keyboard backlight.

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
12. `Alt+K` or `/` or `?`: open keyboard shortcuts page.
13. `K`: start touch calibration.
14. `R`: reset stored calibration values.
15. `Y`: save calibration after 9-point capture.
16. `U`: retry calibration after 9-point capture.
17. `C`: toggle touch debug.

Touch calibration in LVGL mode uses a full-screen 9-point capture flow with end-of-pass review.
After point 9, calibration now enters `Save/Retry` review instead of auto-committing.
`Save` applies and persists the new calibration; `Retry` restarts capture.
The fit now uses averaged 9-point edge regression for improved real-world tap accuracy near edges and small buttons.
Default values can still be set in one place via install YAML substitutions:
`touch_x_min`, `touch_x_max`, `touch_y_min`, `touch_y_max`.
GPS serial baud is also substitution-driven:
`gps_baud_rate` (default `9600`).

See [`docs/architecture.md`](docs/architecture.md), [`docs/migration.md`](docs/migration.md), [`docs/lvgl-plan.md`](docs/lvgl-plan.md), and [`docs/release.md`](docs/release.md) for conventions and release details.
