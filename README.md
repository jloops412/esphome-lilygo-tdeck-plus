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
6. Keep app-wide units user-selectable with first-boot HA unit-system bootstrap.

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
   - slot-based light model (`light_slot_count`, `light_slot_1..8_name/entity`) for easier add/remove without package edits
   - selected-light target resolves centrally (`selected_light_name` + `selected_light_entity`) to reduce duplicated mapping logic
   - power cluster: switch + `On` / `Tgl` / `Off`
   - brightness cluster: explicit one-press steps only (`-10%`, `+10%`)
   - no scenes or preset-cycle controls
   - color cluster: `Warm`, `Cool`, and `Color Studio`
   - `Color Studio` now uses a modern swatch matrix + selection ring + apply action + Kelvin slider (commit on release)
3. `Weather`: rebuilt two-page LVGL flow:
   - `Weather` overview card with local mapped condition icons, current temp/condition/feels/H-L, compact metric chips, and unit/GPS status
   - weather source diagnostics are now hidden from weather pages and surfaced under `Settings > Diagnostics`
   - `Weather Details` page uses a scroll-safe metrics container (no overlapping lines) for dew, precip, weather code, gust, direction, pressure, visibility, rain/snow intensity, etc.
   - hybrid data adapter keeps `weather.openweathermap` primary while falling back to dedicated sensors/attributes
4. `Climate Controller`: full rebuild with controller-first layout:
   - top status chips (`Mode`, `Action`, `Fan`) + large indoor readout card
   - segmented HVAC mode row (`Off`, `Heat`, `Cool`, `Auto`)
   - mode-aware target zone:
     - `Heat/Cool/Off`: single large target with reliable hold-repeat `- / +`
     - `Auto`: dual target cards (`Heat` + `Cool`) with independent hold-repeat `- / +`
   - bottom rail focused on high-frequency actions only (`Tools`, `Aux`)
5. `Climate Tools`: compact advanced controls page:
   - offset `+/-` controls (`Humidity Offset`, `Temperature Offset`) with hold-repeat
   - feature toggles (aux heat, display humidity/time, fan support, humidification, keypad lockout)
   - diagnostics lines for feature-state summary and climate commit status
6. `Reader`: source list with live preview snippets for BBC/DC/Loudoun/Word/Quote.
7. `Settings`: rebuilt to a category `List + Detail` layout:
   - categories: `System`, `Display`, `Input`, `Units`, `Diagnostics`
   - includes unit toggle/source, sleep/brightness controls, wake/calibration controls, and diagnostics-only weather source visibility toggle
8. `Theme`: rebuilt to a token-based `Theme Studio`:
   - no preset-cycle UI
   - editable tokens: `Screen BG`, `Surface`, `Surface Alt`, `Action`, `Action Soft`, `Text Primary`, `Text Dim`, `Success`, `Warning`
   - per-token RGB editor with live swatch, HEX readout, apply/revert
   - keeps shape controls (border width/radius) and icon color mode toggle
9. `Weather diagnostics`: weather model now normalizes hybrid weather inputs, handles unknown values safely, and maps condition icons locally (no remote icon URLs).
10. `Sleep/input hardening`: auto-sleep now ignores ultra-frequent input chatter and trackball repeat behavior is constrained for better stability.
11. `LVGL sync hardening`: periodic UI updates are label-only; control widgets sync through guarded scripts to avoid script-loop contention.
12. `Climate reliability model`: optimistic local setpoints + mode-aware HA commits + debounced hold-repeat commits to avoid stale HA mirror tap misses.
13. `Climate +/- click reliability`: climate controller and climate tools `+/-` controls now use `on_click` + long-press repeat for more deterministic tap handling on this target.

## Quick keyboard shortcuts

1. All command shortcuts require `Alt`.
2. `Alt+H/L/A/W/C/R/S/T`: `Home/Lights/Colors/Weather/Climate/Reader/Settings/Theme`.
3. `Alt+Q/E`: previous/next page.
4. `Alt+K`: open shortcuts page.
5. `Alt+1/2/3/4`: climate `Heat-/Heat+/Cool-/Cool+`.
6. `Alt+D/F`: previous/next selected light.
7. `Alt+G`: toggle selected light.
8. `Alt+Z/X`: dim/brighten selected light.
9. `Alt+N/M`: warm/cool selected light.
10. `Alt+P`: open Color Studio.
11. `Alt+0`: all mapped slot lights off.
12. `Alt+Y`: start touch calibration.
13. `Alt+V`: reset stored calibration values.
14. `Alt+J`: save calibration after 9-point capture.
15. `Alt+U`: retry calibration after 9-point capture.
16. `Alt+I`: toggle icon color mode (`White`/`Accent`).
17. `Alt+O`: toggle touch debug.

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

See [`docs/architecture.md`](docs/architecture.md), [`docs/migration.md`](docs/migration.md), [`docs/lvgl-plan.md`](docs/lvgl-plan.md), [`docs/release.md`](docs/release.md), [`docs/entities-template.md`](docs/entities-template.md), [`docs/ha-element-framework.md`](docs/ha-element-framework.md), and [`docs/component-reference-checklist.md`](docs/component-reference-checklist.md) for conventions, framework contracts, and release details.
