# Handoff Context

## Repository state
1. Branch: `main`
2. Latest pushed LVGL tag: `v0.15.1-lvgl-lighting-gps-kb-controls`
3. Previous LVGL tag: `v0.15.0-lvgl-system-review-pass1`
4. Previous LVGL tag: `v0.14.0-lvgl-icon-theme-weather-polish`
5. Current active dev ref in install YAMLs: `main` (tracking latest pass)

## Process Contract
1. Every code change must update documentation files in Git in the same iteration.
2. Every code change must update `docs/handoff-context.md` in the same iteration.
3. Never close a work pass without docs + handoff parity.

## Current pass summary (tagged `v0.15.1-lvgl-lighting-gps-kb-controls`)
1. Icon and theme reliability:
   - Standardized MDI package icons to `GRAYSCALE` + `alpha_channel`.
   - Added explicit LVGL icon recolor style usage across launcher/navigation images.
2. Home UX redesign:
   - Replaced asymmetrical launcher with balanced icon-grid layout.
   - Added compact top sleep action while retaining fast one-tap navigation.
3. Climate UX redesign:
   - Split climate controls into:
     - `climate_page` (mode + heat/cool setpoint controls + tools entry)
     - `climate_tools_page` (offset controls + feature toggles + compact state line)
   - Reduced clutter on the primary climate screen.
4. Theme expansion:
   - Expanded to 7 themes (`Midnight`, `Slate`, `Ember`, `Moss`, `Mono`, `Dusk`, `Ocean`).
   - Added theme quick-cycle action in theme utility row.
5. Lights workflow upgrades:
   - Added direct scene scripts (`Relax`, `Focus`) and wired them into preset cycle.
   - Reworked quick-action row to make color workflow explicit (`Palette`, `Relax`, `Focus`, `Amber`, `Off`).
   - Added keyboard shortcuts:
     - `Alt+3/4` -> light `Relax/Focus`
6. Input hardening:
   - Tightened trackball GPIO filters (`delayed_on`, `delayed_off`, `settle`) to reduce noisy repeated navigation events.
7. Safety and help:
   - Kept reboot confirmation flow.
   - Updated shortcuts text/help to include new command mappings.
8. Keyboard/GPS reliability:
   - Added direct keyboard-backlight UI controls (`KB-`, `KB+`, `KB Light`) in Settings and Theme utilities.
   - Strengthened keyboard-backlight I2C apply sequence with compatibility fallback pulses.
   - Weather/Home GPS status now computes live age directly from `gps_last_update_ms` to avoid stale liveness state.
   - Confirmed board default GPS UART mapping remains `RX=44`, `TX=43` (LilyGO utility headers), and keyboard brightness command path remains `0x01/0x02` (LilyGO keyboard MCU example).

## Unreleased Main Pass (post `v0.11.0`)
1. Entity mapping restore + templates:
   - Restored full real-entity easy install mapping in:
     - `esphome/install/lilygo-tdeck-plus-install-lvgl.yaml`
     - `esphome/install/lilygo-tdeck-plus-install.yaml`
   - Added personal mapping file:
     - `esphome/install/entity-overrides.jloops.yaml`
   - Kept public-safe template path:
     - `esphome/install/lilygo-tdeck-plus-install-lvgl-template.yaml`
     - `esphome/install/entity-overrides.template.yaml`
2. Screensaver/idle hardening:
   - Added activity pulse guard in `note_activity` to ignore noisy ultra-frequent input events.
   - Added `last_activity_note_ms` global for debounce timing.
3. Trackball stability:
   - Stronger GPIO filtering (`delayed_on_off` + `settle`) in LVGL trackball package.
   - Throttled trackball activity timestamp updates while awake.
   - Added LVGL keypad long-press repeat cap (`long_press_repeat_time: 65535ms`) to reduce runaway focus drift.
4. UI pass across all major pages:
   - Home launcher redesigned with icon-first compact actions and larger lights entry.
   - Weather title/metrics formatting cleanup and clearer climate jump affordance.
   - Climate header/nav cleanup and compact metric labels.
   - Settings gained direct timeout slider (`settings_saver_slider`) for precise autosleep control.
   - Theme page naming refresh (`Midnight`, `Slate`, `Ember`, `Moss`, `Mono`) and palette tuning.
5. Icon compatibility:
   - Replaced previously failing icon codepoints with safer LVGL-compatible icon codes.
6. Compile compatibility hotfix:
   - Replaced invalid `long_press_repeat_time: never` with `long_press_repeat_time: 65535ms` for ESPHome 2026.2.2 parser compatibility.
7. Package refresh hotfix:
   - Added `refresh: 1min` to install package blocks to avoid stale cached Git packages during rapid iteration.
8. Keyboard UX and layout alignment:
   - Converted command shortcuts to `Alt+<key>` only in LVGL keyboard package.
   - Removed punctuation-heavy shortcuts to better match compact keyboard layouts.
   - Updated in-device shortcuts overlay text to the new ALT-only mapping.
9. Home/icon pass:
   - Removed home title and top shortcut button to free space.
   - Switched launcher tiles to icon-only actions.
   - Updated icon codepoints to LVGL-supported symbols (`lights/weather/reader/theme/temp` paths).
10. Keyboard backlight diagnostics:
    - Added persisted backlight protocol profile (`Normal`, `Reverse`, `LiveOnly`).
    - Added Theme page action to cycle profile and apply immediately.
11. Climate page polish:
    - Improved spacing and compacted labels for dense control areas.
    - Added icon-based weather jump on climate page top bar.
12. Icon rendering reliability + semantic icon correction:
    - Trialed explicit external icon font definitions in `esphome/packages/board_base.yaml` (later removed for package compatibility).
    - Bound launcher/nav icon labels for semantic icon correction (later reverted to LVGL-symbol-only path).
    - Corrected icon semantics per UX request:
      - Lights: bulb
      - Weather: cloud
      - Climate: thermometer
      - Reader: book
      - Sleep: moon
13. Lights UX expansion:
    - Added dedicated `light_color_page` in `ui_lvgl.yaml` with expanded color palette.
    - Kept main lights page focused and added direct `Colors` entry button.
    - Added keyboard shortcut `Alt+A` (`input_keyboard_i2c_lvgl.yaml`) to open color chooser.
14. Climate UX expansion:
    - Added quick setpoint adjust controls (`+/-`) for heat and cool targets.
    - Retained sliders for coarse movement and exact persistence through HA service calls.
15. Trackball stability tuning:
    - Increased LVGL trackball GPIO filtering (`delayed_on_off`, `settle`) to reduce runaway directional events.
16. Post-pass hotfixes:
    - Initial attempt added icon asset file to install package manifests:
      - `esphome/install/lilygo-tdeck-plus-install-lvgl.yaml`
      - `esphome/install/lilygo-tdeck-plus-install-lvgl-template.yaml`
      - `esphome/install/lilygo-tdeck-plus-install.yaml`
      This was later superseded because package `files` only supports YAML files.
    - Keyboard shortcut reliability:
      - Extended ALT ESC-prefix pending window from `260ms` to `700ms`.
      - Enabled plain-key fallback for command shortcuts while retaining ALT support.
      - Updated shortcut help text to match actual behavior.

## Install entrypoints
1. Stable install YAML:
   - `esphome/install/lilygo-tdeck-plus-install.yaml`
2. LVGL beta install YAML:
   - `esphome/install/lilygo-tdeck-plus-install-lvgl.yaml`

## LVGL beta packages
1. `esphome/packages/display_mipi_lvgl.yaml`
2. `esphome/packages/input_touch_gt911_lvgl.yaml`
3. `esphome/packages/input_trackball_lvgl.yaml`
4. `esphome/packages/input_keyboard_i2c_lvgl.yaml`
5. `esphome/packages/ui_lvgl.yaml`
6. Local profile: `esphome/profiles/lvgl_experimental.yaml`

## Input parity updates in `v0.6.2-lvgl-input-parity`
1. Touch calibration:
   - Replaced no-op calibration with a 4-point calibration capture page (`touch_cal_page`).
   - Added corner raw capture globals and computed suggested values:
     - `touch_cal_suggest_x_min`
     - `touch_cal_suggest_x_max`
     - `touch_cal_suggest_y_min`
     - `touch_cal_suggest_y_max`
   - Suggested values are shown on-device and logged via ESPHome logs.
2. Trackball navigation:
   - LVGL keypad mapping now uses `prev/next/up/down/enter` with `nav_group`.
   - Added default focus on boot (`home_lights_btn`) to ensure click/navigation has a focused target.
3. Keyboard shortcuts:
   - Restored parity keys in LVGL keyboard package:
     - `Q/E` page previous/next
     - `K/R/C` calibration start/reset/debug
     - `WASD` + `Tab/Esc` focus previous/next
     - existing light and keyboard-backlight shortcuts retained
4. Docs updated:
   - `README.md`, `docs/release.md`, `docs/migration.md`, `docs/lvgl-plan.md`, and this handoff file.

## One-YAML calibration update in `v0.6.3-lvgl-calibration-overrides`
1. `input_touch_gt911_lvgl.yaml` now reads calibration from substitutions:
   - `touch_x_min`
   - `touch_x_max`
   - `touch_y_min`
   - `touch_y_max`
2. `esphome/install/lilygo-tdeck-plus-install-lvgl.yaml` now exposes those substitutions at top level.
3. Calibration values suggested by the on-device flow can be applied in one install YAML edit.

## Calibration + UI update in `v0.7.0-lvgl-cal9-controller-ui`
1. Touch calibration:
   - Upgraded to a full-screen 9-point flow.
   - Captured values are applied live via `id(tdeck_touch).set_calibration(...)`.
   - Suggested values persist (`restore_value: yes`) and are re-applied on boot.
2. Calibration persistence behavior:
   - Starting calibration no longer clears existing saved calibration values.
   - Reset calibration restores install-default substitution values and reapplies immediately.
3. LVGL lights page redesign:
   - Direct light target selection buttons (6 lights).
   - Contextual action column (`Toggle`, `Dim`, `Bright`, `Warm`, `Cool`, `Preset Cycle`).
   - Active light summary and state shown in-page.
4. Weather page update:
   - Added `Feels` row and denser metric formatting for quick glance readability.

## UX + calibration polish in `v0.7.1-lvgl-modern-ui-shortcuts`
1. Calibration quality:
   - 9-point calibration fitting now uses regression across all targets.
   - This improves stability vs edge-only averaging.
2. Shortcuts discoverability:
   - Added dedicated `shortcuts_page`.
   - Added keyboard open actions:
     - `Alt+K` via ESC-prefix chord handling.
     - `/` or `?` direct open.
3. Home polish:
   - Home layout now uses stronger visual hierarchy and action grouping.
   - Added `Keys` button and top-level quick access to shortcuts + touch calibration.
4. Light controller polish:
   - Refined list/control style contrast using soft/action/success styles.
5. Process:
   - Added explicit process policy to docs to enforce docs/handoff updates every pass.

## Ground-up LVGL UI pass in `v0.8.0-lvgl-groundup-ui2`
1. Home page:
   - Reworked to launcher-first layout with stronger control hierarchy.
   - Lights is now a large primary action; weather/reader/settings/theme/touchcal remain one tap away.
2. Lights page:
   - Reworked into two-zone controller layout.
   - Left rail: direct light target selection list.
   - Right panel: contextual actions (`Toggle`, `Dim`, `Bright`, `< Light`, `Light >`, `Warm`, `Cool`, quick colors, `Preset`).
3. Reader page:
   - Converted to full-width source rows with live snippet labels for BBC/DC/Loudoun/Word/Quote.
4. Calibration quality:
   - Replaced single-pass 9-point regression with averaged column/row edge-fit regression.
   - Updated calibration target geometry for edge coverage while avoiding bezel dead zones.
   - Calibration still applies live and persists across reboot.
5. Docs/process:
   - README and release docs updated in same pass.
   - Handoff context updated in same pass (this file).

## Controls + calibration review + GPS diagnostics in `v0.9.0-lvgl-controls-calreview-gpsdiag`
1. Calibration:
   - 9-point flow now ends with explicit `Save` or `Retry` prompt.
   - Prevents accidental bad capture from being auto-committed.
   - Keyboard shortcuts added for review step: `Y=Save`, `U=Retry`.
2. Lights page:
   - Added LVGL sliders for selected-light brightness and color temperature.
   - Preserved quick action keys/buttons for fast control.
3. UI cleanup:
   - Reduced duplicate utility buttons on Home and Reader.
   - Kept utility actions in Settings/Theme/Shortcuts where they are easier to find.
4. Theme controls:
   - Expanded palette set from 3 to 5 (`Graphite`, `Ocean`, `Amber`, `Rose`, `Teal`).
   - Added display and keyboard backlight sliders on Theme page.
5. GPS diagnostics:
   - Added `gps_baud_rate` substitution to install/profile entrypoints.
   - Added telemetry entities: GPS data age, GPS data alive, GPS status text.
   - Updated Home/Weather status messaging to differentiate no-data vs searching vs fix.
6. Docs/process:
   - README, release, LVGL plan, and handoff docs updated in same pass.

## GPS compile hotfix in `v0.9.1-lvgl-gps-hotfix`
1. Fixed HA compile/config parse error:
   - removed unsupported `update_interval` from `binary_sensor.template` in `gps_uart.yaml`.
2. No UI behavior changes in this hotfix.
3. Docs/handoff updated in same pass.

## Climate + theme inversion + slider snap in `v0.10.0-lvgl-climate-theme-fix`
1. Display color correction:
   - `display_mipi_lvgl.yaml` now uses `invert_colors: true` to correct panel-level inversion reports.
2. Slider precision improvements:
   - Added script-level snapping:
     - display backlight: 5%
     - keyboard backlight: 5%
     - light brightness: 5%
     - light kelvin: 100K
3. Weather entity diagnostics:
   - Added `weather.openweathermap` text sensor mirror (`wx_entity_state`).
   - Weather page now shows explicit entity-state diagnostics.
4. New climate entities:
   - Added Sensi climate state/attribute mirrors.
   - Added Sensi numeric and switch mirrors for all requested controls.
5. New LVGL `climate_page`:
   - HVAC quick modes (`Off/Heat/Cool/Auto`)
   - Auto heat/cool setpoint sliders
   - Humidity/temp offset sliders
   - Direct toggle buttons for aux/display/fan/humidification/lockout switches
6. Navigation updates:
   - Home page now has direct `Climate` launcher button.
   - Keyboard page jump now maps `1..7`:
     - `1 Home`, `2 Lights`, `3 Weather`, `4 Climate`, `5 Reader`, `6 Settings`, `7 Theme`.
   - Shortcut overlay text updated to match.

## Privacy + UI + GPS pass in `v0.11.0-lvgl-privacy-ui-gps-pass`
1. Private entity hardening:
   - Replaced hardcoded HA entity IDs with substitution tokens in package code.
   - Added public-safe templates for local private overrides:
     - `docs/entities-template.md`
     - `esphome/install/entity-overrides.template.yaml`
   - Added `.gitignore` rules for local private files.
2. Climate page cleanup:
   - Removed noisy per-button ON/OFF text status badges.
   - Kept cleaner action-button-only toggle row.
3. Slider behavior:
   - Snapping kept (5% brightness, 100K kelvin).
   - Sliders now refresh immediately to snapped values after release.
4. Keyboard backlight robustness:
   - Improved I2C command retry sequence for better compatibility.
   - Kept Alt+B memory/default handling.
5. Trackball stability:
   - Added debounce filters on LVGL trackball GPIO inputs.
6. GPS/weather hardening:
   - Added explicit `uart_id: gps_uart` in GPS package.
   - Updated no-data diagnostics to suggest trying `gps_baud_rate: 38400`.
   - Weather page now falls back to weather-entity attributes for richer metrics.
7. UI pass:
   - Added icon glyphs on key launcher/actions.
   - Rebalanced theme palettes for smoother complementary color sets.

## Post `v0.12.0` Hotfixes on `main`
1. Icon asset package-load fix:
   - Initial attempt added `esphome/assets/fa-solid-900.ttf` to install YAML `packages.files` lists (later superseded by YAML-only package correction).
2. Keyboard shortcut reliability:
   - Extended ESC-prefix ALT pending window to `700ms`.
   - Enabled plain-key command fallback while preserving ALT compatibility.
   - Updated shortcuts page text to match runtime behavior.
3. Install parser compatibility:
   - Added minimal local `esphome:` blocks (`name`, `friendly_name`) in install entrypoints to avoid `'esphome' section missing` validation failures before package merge.
   - Added minimal local `esp32:` blocks (`variant: esp32s3`, `framework: esp-idf`) in install entrypoints to avoid `Platform missing` failures before package merge.
   - Converted install entrypoints to list-form `packages:` syntax to avoid parser edge cases where labeled package keys (for example `board_base`) are treated as unknown components.
   - Quoted install package refs (`ref: "main"`) to avoid `git_ref` type errors when users paste numeric-like unquoted refs.
4. YAML-only package compatibility correction:
   - Removed non-YAML asset entries from install `packages.files` lists (`fa-solid-900.ttf`), because ESPHome packages only accept YAML file entries.
   - Removed external icon-font dependency from package code and reverted icon rendering to LVGL-compatible symbol codepoints.
5. UI/control follow-up pass:
   - Reworked home and nav icons to package-safe `mdi:` image assets in `board_base.yaml`.
   - Climate page now uses larger `+/-` controls for heat/cool and humidity/temperature offsets (no climate sliders).
   - Theme page now includes persisted accent-color chooser controls (`theme_accent_index`, `theme_accent_set`, `theme_accent_next`, `apply_theme_accent`).
   - Theme page now includes persisted shape controls (`theme_border_width`, `theme_radius`) and runtime style apply (`apply_theme_shape`).
   - Keyboard shortcuts restored to strict `Alt+key` requirement and shortcut overlay text updated accordingly.
   - Added `all_lights_off` action path and `Alt+0` shortcut.
6. ESPHome parser hotfix:
   - Added explicit `type: BINARY` to all `image:` entries in `esphome/packages/board_base.yaml`.
   - Resolves ESPHome 2026.2.2 config error for image entries with only `file/id/resize`.
7. Icon/theme + app polish pass:
   - Switched icon image defaults to `GRAYSCALE` + `alpha_channel` transparency for better LVGL recolor quality.
   - Added `lv_style_icon` and applied it to all nav/home icons.
   - Added theme-controlled icon mode (`White` / `Accent`) with runtime recolor updates.
   - Improved weather readability with split metric rows and clearer source line.
   - Updated home status line to include indoor temperature when available.
   - Improved lights quick-action row (`Colors`, `Preset`, `Off`).
   - Replaced settings bottom-center action with direct `Reboot`.
8. Comprehensive review pass:
   - Adjusted icon asset format to `GRAYSCALE` + `alpha_channel` for stable recolor in LVGL.
   - Added reusable icon style (`lv_style_icon`) and applied to all home/nav icons.
   - Added icon color mode control (`White` / `Accent`) in Theme page and status.
   - Added safe reboot confirmation page instead of single-tap reboot.
   - Refined weather metric layout into two compact rows for improved readability.
   - Added `Alt+I` shortcut to toggle icon color mode.
   - Swapped Theme utility button from debug to Help to improve discoverability.

## Immediate validation asks
1. Flash LVGL install YAML from `main` for this pass (pin to `v0.15.1-lvgl-lighting-gps-kb-controls` immediately after tag creation).
2. Verify:
   - config parse succeeds
   - restored entity IDs drive the intended HA entities again
   - public template install path still compiles with placeholder entities
   - home launcher icons render (`Lights/WX/Reader/Theme/Sleep`)
   - auto-screensaver triggers after timeout while idle
   - settings timeout slider updates timeout value and persists
   - trackball right/left movement no longer runs away
   - climate page opens and Sensi actions fire correctly
   - weather metrics and GPS diagnostics still update
   - calibration persistence across reboot still holds
   - shortcuts work via ALT-only commands (`Alt+H/L/A/W/C/R/S/T`, `Alt+Q/E`, `Alt+K`, etc.)
   - theme page `KB Profile` button cycles `Normal/Reverse/LiveOnly` and changes status text

## Notes
1. Manual-rendered stable path remains functional and is the fallback.
2. LVGL path is intentionally parallel and should not overwrite stable by default.
3. Upstream hardware reference checks used for this pass:
   - T-Deck GPS UART pins in LilyGO examples: TX `43`, RX `44`.
   - LilyGO GPS example attempts recovery across `9600`/`38400` baud.
   - Keyboard controller firmware command IDs for backlight:
     - `0x01` (live brightness duty)
     - `0x02` (Alt+B default duty)
