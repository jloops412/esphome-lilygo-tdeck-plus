# Migration Guide

## From older installs to current LVGL package path

1. Start from `esphome/install/lilygo-tdeck-plus-install-lvgl.yaml`.
2. Copy your entities into substitutions (or from `entity-overrides.template.yaml`).
3. Keep local secrets in HA.
4. Compile once over USB if needed, then OTA.

## Key behavioral changes

- ALT-only keyboard shortcuts for command actions
- app-wide units model (metric/imperial)
- climate uses optimistic local state + ack-based sync
- weather split into overview/details
- optional cameras page (off by default)
- runtime admin controls available through ESPHome web server entities

## Public profile cleanup

- Personal mappings moved out of main install files.
- Use personal profile path if needed:
  - `esphome/install/personal/jloops/...`

## Common issues

1. `couldn't find remote ref`: update package `ref` to a valid tag/branch.
2. old package cache: keep `refresh: 1min` while testing.
3. parser errors before package merge: keep local `esphome:` and `esp32:` blocks in install YAML.
4. screensaver not sleeping: verify wake toggles and check diagnostics activity source.

