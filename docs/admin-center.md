# Admin Center v1

## Scope

Hybrid admin model:

1. Runtime controls through ESPHome `web_server` entities.
2. Install-time config generator under `tools/admin-center/`.

## Runtime controls

Exposed template entities include:

- display brightness
- screensaver timeout/enable
- wake-on touch/keyboard/trackball
- units mode
- theme border/radius/icon mode
- camera auto-refresh + refresh button
- climate retry sync button

## Config generator

Open `tools/admin-center/index.html` in a browser.

Outputs:

1. Drop-in install YAML
2. Substitutions override block

## Future extension hooks

`tools/admin-center/schema.json` includes:

- field grouping
- component registry
- starting point for a future UI-builder/config registry

