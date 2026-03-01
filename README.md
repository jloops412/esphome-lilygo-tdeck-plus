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
4. Keep keyboard-backlight control deferred in firmware (manual keyboard `Alt+B` only for now).
5. Maintain a single drop-in install YAML for ESPHome/HA.

## Install

Stable install YAML:

- `esphome/install/lilygo-tdeck-plus-install.yaml`

LVGL beta install YAML (parallel track):

- `esphome/install/lilygo-tdeck-plus-install-lvgl.yaml`
- `esphome/install/lilygo-tdeck-plus-install-lvgl-template.yaml` (public tokenized template)

Each install YAML pulls modular files from this repo by configured Git ref.
Install YAMLs now set `packages.refresh: 1min` to minimize stale package-cache issues during active development.
Install YAMLs now include a minimal local `esphome:` block (`name` + `friendly_name`) for parser compatibility in environments that validate before package merge.
Install YAMLs now include a minimal local `esp32:` block (`variant: esp32s3`, `framework: esp-idf`) for platform-key validation before package merge.
Install YAMLs now use list-form `packages:` syntax to avoid parser edge cases where labeled package keys (for example `board_base:`) are misinterpreted as top-level components.
Install YAML package refs are quoted strings (for example `ref: "main"`). If pinning to a commit hash, always quote it to avoid YAML numeric coercion.

## Current UI flow

1. `Home`: balanced icon-grid launcher with fast one-tap access to Lights/Weather/Climate/Reader/Settings/Theme plus compact Sleep action.
2. `Lights`: two-zone controller layout with direct target list + richer controls:
   - power switch + direct toggle
   - LVGL arc controls for per-light brightness and color temperature
   - reliable `+/-` controls routed through explicit brightness target updates
   - quick actions (`Dim/Bright`, `Warm/Cool`, `Palette`, `Relax`, `Focus`)
   - dedicated `Color Studio` page using LVGL roller + apply action
3. `Weather`: glance dashboard with large temperature, readable condition, split metrics rows (readable at a glance), `weather.openweathermap` source line, and explicit GPS diagnostic state.
4. `Climate`: simplified primary control page with:
   - HVAC mode quick actions (`Off`, `Heat`, `Cool`, `Auto`)
   - large `+/-` target controls (`Auto Heat`, `Auto Cool`)
   - dual-path setpoint writes for stronger `+/-` reliability across HA integrations
   - fast entry into `Climate Tools` for advanced controls
5. `Climate Tools`: dedicated advanced Sensi controls:
   - offset `+/-` controls (`Humidity Offset`, `Temperature Offset`)
   - direct toggles for Sensi feature switches (aux heat, display humidity/time, fan support, humidification, keypad lockout)
   - compact live feature-state line (`Aux/Hum/Time/Fan/Humid/Lock`)
6. `Reader`: source list with live preview snippets for BBC/DC/Loudoun/Word/Quote.
7. `Settings`: wake behavior, saver timing, calibration, and reboot confirmation flow.
8. `Theme`: expanded palette set (`Midnight`, `Slate`, `Ember`, `Moss`, `Mono`, `Dusk`, `Ocean`), accent color chooser, icon color mode (`White`/`Accent`), display brightness, and shape controls (button/card border width + corner radius).
9. `Weather diagnostics`: weather page now reads both legacy weather sensors and `weather.*` attributes as fallback for richer data.
10. `Sleep/input hardening`: auto-sleep now ignores ultra-frequent input chatter and trackball repeat behavior is constrained for better stability.

## Quick keyboard shortcuts

1. All command shortcuts require `Alt`.
2. `Alt+H/L/A/W/C/R/S/T`: `Home/Lights/Colors/Weather/Climate/Reader/Settings/Theme`.
3. `Alt+Q/E`: previous/next page.
4. `Alt+K`: open shortcuts page.
5. `Alt+D/F`: previous/next selected light.
6. `Alt+G`: toggle selected light.
7. `Alt+Z/X`: dim/brighten selected light.
8. `Alt+P`: cycle light preset.
9. `Alt+3/4`: selected-light `Relax/Focus` scenes.
10. `Alt+0`: all mapped lights off.
11. `Alt+Y`: start touch calibration.
12. `Alt+V`: reset stored calibration values.
13. `Alt+J`: save calibration after 9-point capture.
14. `Alt+U`: retry calibration after 9-point capture.
15. `Alt+I`: toggle icon color mode (`White`/`Accent`).
16. `Alt+O`: toggle touch debug.

Touch calibration in LVGL mode uses a full-screen 9-point capture flow with end-of-pass review.
After point 9, calibration now enters `Save/Retry` review instead of auto-committing.
`Save` applies and persists the new calibration; `Retry` restarts capture.
The fit now uses averaged 9-point edge regression for improved real-world tap accuracy near edges and small buttons.
Sliders now snap to practical increments for easier one-handed adjustment:
- display brightness: 5%
- light brightness: 5%
- color temperature: 100K
Trackball GPIO inputs in LVGL mode now include debounce filters to reduce runaway focus movement.
LVGL keypad repeat is constrained to prevent continuous focus drift when a direction input bounces.
For ESPHome parser compatibility, this is configured using `long_press_repeat_time: 65535ms`.
Launcher and navigation icons now use package-safe `mdi:` image assets with LVGL recolor, so icon color stays theme-consistent.
Keyboard backlight firmware controls are intentionally removed in the LVGL path for now; use manual `Alt+B` at the keyboard.
Default values can still be set in one place via install YAML substitutions:
`touch_x_min`, `touch_x_max`, `touch_y_min`, `touch_y_max`.
GPS serial baud is also substitution-driven:
`gps_baud_rate` (default `9600`).

See [`docs/architecture.md`](docs/architecture.md), [`docs/migration.md`](docs/migration.md), [`docs/lvgl-plan.md`](docs/lvgl-plan.md), [`docs/release.md`](docs/release.md), and [`docs/entities-template.md`](docs/entities-template.md) for conventions, privacy mapping, and release details.
