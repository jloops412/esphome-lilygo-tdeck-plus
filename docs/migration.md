# Migration Guide

## Baseline

- Canonical modular baseline profile: `esphome/profiles/stable_snapshot.yaml`
- Stable HA install entrypoint: `esphome/install/lilygo-tdeck-plus-install.yaml`
- LVGL beta install entrypoint: `esphome/install/lilygo-tdeck-plus-install-lvgl.yaml`

## What changed

1. Monolithic config split into domain packages under `esphome/packages/`.
2. Install flow now supports one YAML that fetches package files from GitHub tag.
3. GPS package added.
4. Keyboard-backlight firmware control is currently deferred in LVGL path (manual hardware `Alt+B` remains the active method).
5. `millis()` ambiguity fixed by using `esphome::millis()` in lambdas.
6. Feed page no longer routes to settings from the 6th feed tile.
7. UI pass 1 adds a redesigned weather dashboard and compact feed previews.
8. Logger UART output disabled (`baud_rate: 0`) to reduce GPS UART conflicts.
9. UI pass 2 adds controller-first light interactions (prev/toggle/next + dim/bright).
10. Presets page now focuses on practical light scenes (warm/cool/relax/focus/party).
11. Settings page now includes wake-on-trackball toggle directly in UI.
12. Weather value formatting now handles invalid values more gracefully.
13. Unused gust/dew weather imports were removed to reduce `unknown` parse warnings.
14. Keyboard shortcuts are ALT-only command chords aligned to the compact T-Deck keyboard (`Alt+H/L/A/W/C/R/S/T`, etc.).
15. Ground-up UI pass replaces always-visible tabs with a cleaner Home launcher and subpages.
16. New Theme page supports multi-palette switching (`Graphite`, `Ocean`, `Amber`) on-device.
17. Lights page is now a dedicated control surface with preset cycling in-page.
18. Added a parallel LVGL beta package path (`display/input/ui` LVGL modules).
19. Added `lvgl_experimental` profile for local iterative testing.
20. Discovered LVGL beta compile blocker: missing `page_next` and `page_prev` scripts referenced by `board_base` template buttons.
21. LVGL hotfix added `page_next`/`page_prev` scripts so shared `board_base` buttons compile.
22. LVGL touch calibration now has a real 4-point capture workflow and reports suggested `x_min/x_max/y_min/y_max`.
23. LVGL keypad mapping now uses `prev/next/up/down/enter` for trackball navigation parity.
24. LVGL keyboard profile restored parity shortcuts (`Q/E`, `K/R/C`, and `WASD`/`Tab`/`Esc` focus navigation).
25. LVGL touch calibration values are now install-YAML substitutions (`touch_x_min/x_max/y_min/y_max`) so updates stay one-file.
26. LVGL touch calibration now runs as full-screen 9-point capture and applies live calibration with persistence across reboot.
27. Lights page moved to controller-first direct selection + contextual actions for lower navigation friction.
28. Weather page now includes `feels like` and denser compact metrics.
29. Calibration fitting now uses all 9 points (regression) for better final accuracy.
30. Added keyboard shortcuts overlay page, accessible by `Alt+K` (ESC-prefix chord) and `/`.
31. Added persistent process policy: every code change must update docs and handoff context in the same iteration.
32. Lights `+/-` controls now route through explicit target-brightness script updates for better reliability.
33. Climate `+/-` controls now use dual-path HA writes (`number.set_value` + `climate.set_temperature`) to improve cross-integration behavior.
34. Weather/climate pages received card-based LVGL layout polish for clearer hierarchy.
35. Lights page removed circular `arc` controls and now uses compact horizontal sliders plus quick-action chips.
36. Selected-light mapping is now centralized (`resolve_selected_light_target` + `selected_light_entity/name`) to reduce duplicated action logic and make light customization easier.
37. Install/template files now include per-light name substitutions (`light_name_*`) so label changes do not require package edits.
38. Main lights controller now uses explicit `-10%` / `+10%` brightness buttons (no main-page brightness slider) and removes scene-row buttons for cleaner flow.
39. Added modular slot-based light substitutions (`light_slot_count`, `light_slot_1..8_name/entity`) with one-release legacy compatibility bridge from `light_name_*` and `entity_light_*`.
40. Dynamic LVGL updates are now split:
    - `lvgl_update_labels` (labels/status only)
    - `lvgl_sync_lights_controls` (guarded widget sync)
    - `lvgl_update_dynamic` (coordinator)
41. Periodic 2s refresh now runs labels only to prevent programmatic control churn.
42. Color Studio replaced roller UX with a swatch matrix + selection indicator + apply workflow and Kelvin release-commit behavior.
43. Removed scene/preset-cycle scripts and keyboard mappings from active lights workflow.

## Migration steps for existing HA node

1. Pick install target:
   - Stable: `esphome/install/lilygo-tdeck-plus-install.yaml`
   - LVGL beta: `esphome/install/lilygo-tdeck-plus-install-lvgl.yaml`
2. Keep local secrets in HA (`wifi_ssid`, `wifi_password`).
3. Install once over USB if needed, then OTA.
