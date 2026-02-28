# LilyGO T-Deck Plus HA Controller

This repo tracks the ESPHome controller work for LilyGO T-Deck Plus.

## Process Policy

1. Every code change must include documentation updates in Git.
2. Every code change must include `docs/handoff-context.md` updates in the same iteration.

## Privacy Policy (Entities)

1. Package files use substitution tokens for Home Assistant entity IDs.
2. Public template mapping remains available:
   - `docs/entities-template.md`
   - `esphome/install/entity-overrides.template.yaml`
3. Personal/easy mapping file is also tracked for fast install:
   - `esphome/install/entity-overrides.jloops.yaml`
4. Generic public install entrypoint:
   - `esphome/install/lilygo-tdeck-plus-install-lvgl-template.yaml`
5. Local private override filenames are still gitignored (`*-private.yaml`, `*-local.yaml`).

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
- `esphome/install/lilygo-tdeck-plus-install-lvgl-template.yaml` (public tokenized template)

Each install YAML pulls modular files from this repo by configured Git ref.

## Current UI flow

1. `Home`: launcher-first layout with a large lights controller card and compact icon actions (`Weather`, `Climate`, `Reader`, `Settings`, `Theme`, `Sleep`).
2. `Lights`: two-zone controller layout with direct target list + richer controls:
   - quick actions (`Toggle`, `Dim`, `Bright`, `Warm`, `Cool`, color chips, preset)
   - LVGL sliders for per-light brightness and color temperature
3. `Weather`: glance dashboard with large temperature, readable condition, compact metrics, `weather.openweathermap` entity-state line, and explicit GPS diagnostic state.
4. `Climate`: dedicated Sensi control page with:
   - HVAC mode quick actions (`Off`, `Heat`, `Cool`, `Auto`)
   - target sliders (`Auto Heat`, `Auto Cool`)
   - offset sliders (`Humidity Offset`, `Temperature Offset`)
   - direct toggles for Sensi feature switches (aux heat, display humidity/time, fan support, humidification, keypad lockout)
5. `Reader`: source list with live preview snippets for BBC/DC/Loudoun/Word/Quote.
6. `Settings`: wake behavior, saver timing, keyboard backlight, plus direct shortcuts/theme/calibration access.
7. `Theme`: expanded palette set (`Midnight`, `Slate`, `Ember`, `Moss`, `Mono`) and LVGL sliders for display + keyboard backlight.
8. `Weather diagnostics`: weather page now reads both legacy weather sensors and `weather.*` attributes as fallback for richer data.
9. `Sleep/input hardening`: auto-sleep now ignores ultra-frequent input chatter and trackball repeat behavior is constrained for better stability.

## Quick keyboard shortcuts

1. `1`..`7`: jump directly to pages `Home/Lights/Weather/Climate/Reader/Settings/Theme`.
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
Sliders now snap to practical increments for easier one-handed adjustment:
- display brightness: 5%
- keyboard brightness: 5%
- light brightness: 5%
- color temperature: 100K
Trackball GPIO inputs in LVGL mode now include debounce filters to reduce runaway focus movement.
LVGL keypad repeat is constrained to prevent continuous focus drift when a direction input bounces.
Default values can still be set in one place via install YAML substitutions:
`touch_x_min`, `touch_x_max`, `touch_y_min`, `touch_y_max`.
GPS serial baud is also substitution-driven:
`gps_baud_rate` (default `9600`).

See [`docs/architecture.md`](docs/architecture.md), [`docs/migration.md`](docs/migration.md), [`docs/lvgl-plan.md`](docs/lvgl-plan.md), [`docs/release.md`](docs/release.md), and [`docs/entities-template.md`](docs/entities-template.md) for conventions, privacy mapping, and release details.
