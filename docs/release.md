# Release Process

## Tags

- `v0.1.0-stable`: parity baseline milestone.
- `v0.2.0-gps-kb`: GPS + keyboard wake improvements.
- `v0.3.0-ui-pass1`: first UI redesign milestone.
- `v0.3.1-ui-pass1-hotfix`: ESP32-S3 logger linker fix.
- `v0.4.0-ui-pass2`: controller-first UX pass + keyboard shortcuts + weather robustness.
- `v0.5.0-ui-groundup`: home-menu navigation + theme system + full layout refactor.
- `v0.6.0-lvgl-beta1`: parallel LVGL interface track and migration starter.
- `v0.6.1-lvgl-beta1-hotfix`: LVGL compile fix for shared board template buttons.
- `v0.6.2-lvgl-input-parity`: LVGL input parity pass for calibration, trackball navigation, and shortcut restore.
- `v0.6.3-lvgl-calibration-overrides`: install-time touch calibration substitutions in one YAML.
- `v0.7.0-lvgl-cal9-controller-ui`: persistent live 9-point calibration + controller-first lights UI redesign.
- `v0.7.1-lvgl-modern-ui-shortcuts`: calibration regression fit, modernized home styling, and shortcuts overlay with Alt+K support.
- `v0.8.0-lvgl-groundup-ui2`: deeper LVGL layout rewrite, upgraded lights workflow, and improved 9-point edge-fit calibration.
- `v0.9.0-lvgl-controls-calreview-gpsdiag`: calibration save/retry review, richer LVGL controls, and GPS diagnostics hardening.
- `v0.9.1-lvgl-gps-hotfix`: fixes invalid `update_interval` option on template GPS binary sensor for HA compile compatibility.
- `v0.10.0-lvgl-climate-theme-fix`: display color inversion correction, slider snapping, dedicated Sensi climate page, and weather entity-state diagnostics.
- `v0.11.0-lvgl-privacy-ui-gps-pass`: private entity tokenization + templates, climate page cleanup, trackball debounce, weather attribute fallback, and keyboard/GPS hardening.
- `v0.11.1-lvgl-ref-fix`: package install ref hotfix for ESPHome package fetch compatibility (tag-based pinning).
- `v0.12.0-lvgl-alt-shortcuts-ui-pass`: ALT-only shortcut system, home launcher cleanup, icon refresh, climate spacing polish, and keyboard-backlight profile testing controls.

Unreleased on `main` (candidate next tag):

- entity restore + template split: personal easy-install entity mappings are back while public templates are retained.
- LVGL icon cleanup: replaced non-rendering icon choices with safer symbol set and icon-first launcher layout.
- screensaver reliability: added activity debounce guard and direct timeout slider in settings.
- trackball stability: stronger debounce/filtering plus keypad repeat constraint.
- theme pass: renamed/refined palette set (`Midnight`, `Slate`, `Ember`, `Moss`, `Mono`).
- ESPHome config compatibility fix: `long_press_repeat_time` now uses valid max duration (`65535ms`) instead of invalid `never`.
- Package cache hotfix: install YAMLs now include `packages.refresh: 1min` to force timely Git package updates in HA.
- Home/navigation UI pass:
  - removed top title and keys button from home
  - icon-only launcher actions
  - switched to LVGL-supported icon codepoints for improved icon reliability
- Keyboard shortcut redesign:
  - all command shortcuts now require `Alt+<key>`
  - removed dependency on punctuation shortcuts not guaranteed on compact keyboard layouts
- Keyboard backlight diagnostics:
  - added protocol profile cycling (`Normal`, `Reverse`, `LiveOnly`) in theme page
  - profile is persisted and included in live status text
- Climate page polish:
  - improved spacing hierarchy and compact control labels
- Icon reliability + launcher cleanup:
  - added explicit Font Awesome icon font mapping in `board_base.yaml`
  - corrected launcher icons to requested semantics:
    - Lights = light bulb
    - Weather = cloud
    - Climate = thermometer
    - Reader = book
    - Sleep = moon
  - applied icon font bindings to page nav/home buttons for consistent rendering
- Lights UX expansion:
  - added dedicated `light_color_page` with expanded preset color palette
  - kept main lights page focused on target selection + primary actions + sliders
  - added `Alt+A` shortcut to open color chooser directly
- Climate control UX expansion:
  - added per-degree quick adjust buttons (`+/-`) for heat and cool targets
  - retained sliders for larger adjustments
- Trackball hardening:
  - increased LVGL trackball GPIO debounce/settle filters to reduce runaway direction events

Hotfix after this pass:

- Package-asset compile fix:
  - added `esphome/assets/fa-solid-900.ttf` to install YAML `packages.files` lists so remote package installs can resolve icon font files.
- Keyboard shortcut reliability fix:
  - extended ALT pending window for ESC-prefix detection.
  - enabled plain-key shortcut fallback while preserving ALT compatibility for firmware variants where ALT is not reliably surfaced.
  - updated shortcuts overlay/help text to match runtime behavior.
- Install-parse compatibility fix:
  - added minimal local `esphome:` blocks to install entrypoints (`name`, `friendly_name`) so environments that validate before package merge do not fail with `'esphome' section missing`.
  - added minimal local `esp32:` blocks to install entrypoints (`variant: esp32s3`, `framework: esp-idf`) so pre-merge validation does not fail with `Platform missing`.
  - switched install entrypoints to list-form `packages:` syntax to avoid parser edge cases where labeled package keys are treated as components.

Post-tag note:

- `v0.6.0-lvgl-beta1` has a compile blocker in HA when using the LVGL install YAML:
  - `board_base.yaml` template buttons call `page_next`/`page_prev`
  - `ui_lvgl.yaml` did not yet define those script IDs
  - fix is to add LVGL-compatible `page_next`/`page_prev` scripts (or decouple those template buttons from LVGL profile)

`v0.6.1-lvgl-beta1-hotfix` highlights:

1. Added `page_next` and `page_prev` script IDs in `ui_lvgl.yaml`.
2. Kept `board_base` template buttons compatible with both stable and LVGL install paths.
3. Updated LVGL status docs and handoff notes.

`v0.6.2-lvgl-input-parity` highlights:

1. Replaced LVGL touch calibration no-op with a working 4-point capture assistant page.
2. Added computed `x_min/x_max/y_min/y_max` calibration suggestions and runtime logs.
3. Updated LVGL keypad mapping to `prev/next/up/down/enter` for 5-key trackball navigation.
4. Restored keyboard shortcut parity keys (`Q/E`, `K/R/C`, `WASD` focus nav, plus existing light/backlight shortcuts).
5. Added shared calibration globals for raw capture and suggested calibration values.

`v0.6.3-lvgl-calibration-overrides` highlights:

1. LVGL touch package now reads calibration from substitutions (`touch_x_min/x_max/y_min/y_max`).
2. LVGL install YAML now exposes those substitutions directly.
3. Calibration suggestions from the on-device flow can now be applied without editing package files.

`v0.7.0-lvgl-cal9-controller-ui` highlights:

1. Replaced 4-point calibration with a full-screen 9-point calibration flow.
2. Added live runtime apply using `set_calibration(...)` and persisted calibration reuse on boot.
3. Calibration values now remain active across reboot without rerunning the wizard.
4. Redesigned lights page into direct target selection + contextual controls.
5. Weather page now includes clearer hierarchy (`temp`, `condition`, `feels like`, compact metric rows).

`v0.7.1-lvgl-modern-ui-shortcuts` highlights:

1. Improved 9-point calibration calculation using linear regression across all calibration targets.
2. Preserved last known good calibration while calibration wizard is in progress.
3. Added persisted calibration re-apply on boot and robust reset-to-default flow.
4. Added in-device shortcuts page with Home entry and keyboard access (`Alt+K` and `/`).
5. Added Alt-key chord handling (`Esc` prefix + key) to support `Alt+K` popup behavior.
6. Refined LVGL styles and home/lights presentation for a less primitive, more controller-focused feel.

`v0.8.0-lvgl-groundup-ui2` highlights:

1. Reworked LVGL page layouts to a cleaner launcher + controller structure with improved hierarchy.
2. Redesigned lights page into a denser two-zone control surface:
   - left: target light selection list
   - right: contextual control pad (`Toggle`, dim/bright, prev/next light, warm/cool, quick colors, preset)
3. Reworked reader page into full-width source rows with live snippet previews.
4. Strengthened calibration output fit using averaged 9-point edge regression for better small-target hit accuracy.
5. Updated calibration page target placement to better cover practical screen edges while preserving full-screen flow.
6. Updated docs and handoff report in the same pass per repo process contract.

`v0.9.0-lvgl-controls-calreview-gpsdiag` highlights:

1. Calibration UX upgrade:
   - full-screen 9-point flow now ends with explicit `Save` or `Retry` review.
   - avoids auto-saving bad taps when a point is pressed incorrectly.
   - keyboard review shortcuts added: `Y` to save, `U` to retry.
2. Lights page control upgrade:
   - added LVGL sliders for selected-light `brightness_pct` and `color_temp_kelvin`.
   - retained quick action buttons and color chips for fast operation.
3. UI cleanup:
   - reduced duplicate utility buttons on Home/Reader pages.
   - shifted utility actions to clearer, more intentional locations.
4. Theme system expansion:
   - increased from 3 to 5 palettes (`Graphite`, `Ocean`, `Amber`, `Rose`, `Teal`).
   - added display and keyboard backlight sliders on Theme page.
5. GPS diagnostics:
   - added `gps_baud_rate` substitution (default `9600`) to install/profile entrypoints.
   - added GPS data-alive telemetry (`GPS Data Alive`, data age, status text) to distinguish no-serial-data vs no-fix.
   - Weather/Home UI now reflects GPS diagnostics more explicitly.

`v0.9.1-lvgl-gps-hotfix` highlights:

1. Removed unsupported `update_interval` from `binary_sensor.template` in `gps_uart.yaml`.
2. Restored ESPHome/HA config parsing compatibility for GPS diagnostics package.

`v0.10.0-lvgl-climate-theme-fix` highlights:

1. Display/theme correction:
   - Set LVGL display path to `invert_colors: true` to correct panel-level color inversion symptoms
   - Fixes reports where dark themes appeared light and amber accents appeared blue
2. Slider usability:
   - Added on-release snapping in scripts:
     - display brightness: nearest 5%
     - keyboard backlight: nearest 5%
     - light brightness: nearest 5%
     - color temperature: nearest 100K
3. Weather diagnostics:
   - Added `weather.openweathermap` entity state text sensor (`wx_entity_state`)
   - Surfaced weather-entity state line on weather page for easier integration debugging
4. Sensi climate integration:
   - Added climate state/attribute sensors and required numeric/switch entity mirrors
   - Added dedicated `climate_page` with:
     - HVAC mode actions (`Off/Heat/Cool/Auto`)
     - setpoint sliders (`auto cool/auto heat`)
     - offset sliders (`humidity/temperature`)
     - feature toggles (aux heat, display humidity/time, fan support, humidification, keypad lockout)
5. Navigation updates:
   - Home launcher now includes direct `Climate` entry
   - Keyboard quick-nav now maps `1..7` to `Home/Lights/Weather/Climate/Reader/Settings/Theme`
   - Shortcuts text updated accordingly

`v0.11.0-lvgl-privacy-ui-gps-pass` highlights:

1. Privacy hardening:
   - Removed hardcoded HA entity IDs from package code paths.
   - Replaced with substitution tokens (`${entity_*}`) across:
     - `ha_entities.yaml`
     - `ui_lvgl.yaml`
     - `ui_render_core.yaml`
   - Added public-safe templates:
     - `docs/entities-template.md`
     - `esphome/install/entity-overrides.template.yaml`
   - Added `.gitignore` rules for local private override files.
2. Climate page simplification:
   - Removed verbose per-toggle ON/OFF text badges to reduce clutter.
   - Kept direct action buttons only for feature toggles.
3. Slider usability:
   - Kept 5% / 100K snapping and now forces immediate slider value updates after snapping.
4. Keyboard backlight robustness:
   - Improved command write sequence with retries for better reliability.
   - Preserves user brightness memory for Alt+B default behavior.
5. Trackball stability:
   - Added debounce filters to LVGL trackball GPIO inputs to reduce runaway focus movement.
6. GPS/weather robustness:
   - Explicitly binds GPS parser to `uart_id: gps_uart`.
   - Improved no-data diagnostics to suggest trying `gps_baud_rate: 38400`.
   - Weather page now falls back to `weather.*` attributes (humidity/pressure/visibility/cloud/wind/dew/bearing) when legacy weather sensors are unavailable.
7. LVGL visual pass:
   - Added icon glyphs on core launcher actions.
   - Rebalanced theme palettes for smoother, less noisy color contrast.

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
