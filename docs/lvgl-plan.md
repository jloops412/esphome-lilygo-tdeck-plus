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

## Current status (after v0.6.0-lvgl-beta1)
1. Parallel LVGL packages and install YAML are in place.
2. Core LVGL pages are implemented and wired to existing HA actions/scripts.
3. Known compile blocker found in HA:
   - `board_base` template buttons reference `page_next`/`page_prev`.
   - LVGL package currently lacks those script IDs.
4. Immediate fix:
   - add `page_next` and `page_prev` scripts in `ui_lvgl.yaml` that map to LVGL page navigation.
