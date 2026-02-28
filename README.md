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

1. `Home`: launcher-first layout with a large `Lights Controller` entry and quick links to `Weather`, `Reader`, `Settings`, `Themes`, and `TouchCal`.
2. `Lights`: two-zone controller layout with direct light target list + contextual controls (`Toggle`, `Dim`, `Bright`, `Warm`, `Cool`, quick colors, preset cycle).
3. `Weather`: glance dashboard with large temperature, readable condition, feels-like, and compact metrics.
4. `Reader`: source list with live preview snippets for BBC/DC/Loudoun/Word/Quote.
5. `Settings`: wake behavior, saver timing, keyboard backlight, plus direct shortcuts/theme/calibration access.
6. `Theme`: theme cycling, display brightness, debug toggle, and full calibration launch.

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
15. `C`: toggle touch debug.

Touch calibration in LVGL mode uses a full-screen 9-point capture flow.
Captured calibration is applied live and persisted across reboot.
The fit now uses averaged 9-point edge regression for improved real-world tap accuracy near edges and small buttons.
Default values can still be set in one place via install YAML substitutions:
`touch_x_min`, `touch_x_max`, `touch_y_min`, `touch_y_max`.

See [`docs/architecture.md`](docs/architecture.md), [`docs/migration.md`](docs/migration.md), [`docs/lvgl-plan.md`](docs/lvgl-plan.md), and [`docs/release.md`](docs/release.md) for conventions and release details.
