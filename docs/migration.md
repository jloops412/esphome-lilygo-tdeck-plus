# Migration Guide

## Baseline

- Canonical modular baseline profile: `esphome/profiles/stable_snapshot.yaml`
- Single HA install entrypoint: `esphome/install/lilygo-tdeck-plus-install.yaml`

## What changed

1. Monolithic config split into domain packages under `esphome/packages/`.
2. Install flow now supports one YAML that fetches package files from GitHub tag.
3. GPS package added.
4. Keyboard wake flow now re-applies keyboard backlight script.
5. `millis()` ambiguity fixed by using `esphome::millis()` in lambdas.
6. Feed page no longer routes to settings from the 6th feed tile.
7. UI pass 1 adds a redesigned weather dashboard and compact feed previews.
8. Logger UART output disabled (`baud_rate: 0`) to reduce GPS UART conflicts.
9. UI pass 2 adds controller-first light interactions (prev/toggle/next + dim/bright).
10. Presets page now focuses on practical light scenes (warm/cool/relax/focus/party).
11. Settings page now includes wake-on-trackball toggle directly in UI.
12. Weather value formatting now handles invalid values more gracefully.
13. Unused gust/dew weather imports were removed to reduce `unknown` parse warnings.
14. Keyboard shortcuts now include direct page jumps (`1`..`6`) and controller actions (`[`, `]`, `-`, `+`, `T`).
15. Ground-up UI pass replaces always-visible tabs with a cleaner Home launcher and subpages.
16. New Theme page supports multi-palette switching (`Graphite`, `Ocean`, `Amber`) on-device.
17. Lights page is now a dedicated control surface with preset cycling in-page.

## Migration steps for existing HA node

1. Replace node YAML with contents of `esphome/install/lilygo-tdeck-plus-install.yaml`.
2. Keep local secrets in HA (`wifi_ssid`, `wifi_password`).
3. Install once over USB if needed, then OTA.
