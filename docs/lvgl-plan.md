# LVGL Migration Plan

## Goal
Migrate the UI layer from manual display lambda rendering to LVGL while preserving the proven board/input/HA integration path.

## Strategy
1. Keep the stable manual-rendered install path unchanged.
2. Build a parallel LVGL install profile for iterative testing.
3. Reuse existing hardware + HA entity packages; replace only display/input/UI packages that are UI-specific.
4. Validate behavior in phases before considering default promotion.

## Phase 1: Parallel LVGL Baseline
1. Create LVGL display package with the same proven `mipi_spi` + init sequence.
2. Add LVGL pages for `Home`, `Lights`, `Weather`, `Reader`, `Settings`, and `Theme`.
3. Keep wake/sleep, keyboard backlight, and light-control scripts functional.
4. Preserve trackball/touch/keyboard input paths with LVGL navigation bindings.

## Phase 2: UX Hardening
1. Tune spacing, typography hierarchy, and card/button consistency.
2. Improve light controller ergonomics (single-surface actions).
3. Improve weather and reader content density.
4. Add robust state labels and periodic UI refresh logic.

## Phase 3: Theme System
1. Ship multiple themes (`Graphite`, `Ocean`, `Amber`).
2. Add on-device theme switching and persistence.
3. Ensure all pages/buttons use style definitions for theme consistency.

## Phase 4: Promotion Criteria
1. Build compiles and flashes reliably via HA add-on.
2. Display/touch/trackball/keyboard behavior matches stable baseline expectations.
3. Light actions, feed detail, and settings behavior are stable.
4. No major regressions in wake/sleep, backlight handling, or HA entity updates.

## Rollback
If LVGL regressions appear, continue using the stable install YAML:
- `esphome/install/lilygo-tdeck-plus-install.yaml`

LVGL testing target:
- `esphome/install/lilygo-tdeck-plus-install-lvgl.yaml`

## Current status (after v0.7.1-lvgl-modern-ui-shortcuts)
1. Parallel LVGL packages and install YAML are in place.
2. Core LVGL pages are implemented and wired to existing HA actions/scripts.
3. Compile blocker was found in HA and patched in hotfix:
   - `board_base` template buttons reference `page_next`/`page_prev`.
   - LVGL package now defines those script IDs and maps them to LVGL page navigation.
4. Input parity pass added:
   - working LVGL touch calibration assistant (now upgraded to 9-point capture)
   - LVGL keypad `prev/next/up/down/enter` trackball mapping
   - restored keyboard shortcut set for navigation/calibration/debug/backlight/light control
5. Install YAML now exposes touch calibration substitutions (`touch_x_min/x_max/y_min/y_max`) for one-file updates.
6. Calibration flow now upgraded to full-screen 9-point capture and applies calibration live with persisted reuse on boot.
7. UI pass updated lights flow to direct light selection + contextual control panel.
8. Added shortcuts help overlay and Alt-key chord handling (`Alt+K`) for discoverability.
9. Next validation:
   - compile/flash with latest LVGL tag and verify improved calibration accuracy, button hit reliability, and shortcuts popup behavior.
