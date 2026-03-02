# LilyGO T-Deck Plus Home Assistant Controller

Public-ready ESPHome + LVGL firmware for LilyGO T-Deck Plus (ESP32-S3), built around:

- stable custom MIPI display path
- GT911 touch + 9-point calibration
- trackball + keyboard navigation
- Home Assistant entity control
- modular package architecture with one install YAML

## Install (One YAML)

Use:

- `esphome/install/lilygo-tdeck-plus-install-lvgl.yaml`

This file is the public drop-in entrypoint and pulls modular package files from this repo.

### Quick steps

1. Copy `esphome/install/lilygo-tdeck-plus-install-lvgl.yaml` into your HA ESPHome instance.
2. Replace substitution placeholders (or paste values from `esphome/install/entity-overrides.template.yaml`).
3. Keep Wi-Fi secrets in HA `secrets.yaml`.
4. Compile and flash.

## Public vs Personal Profiles

Public defaults are generic and safe.

- Public install/template:
  - `esphome/install/lilygo-tdeck-plus-install-lvgl.yaml`
  - `esphome/install/lilygo-tdeck-plus-install-lvgl-template.yaml`
  - `esphome/install/entity-overrides.template.yaml`

Personal mappings live separately:

- `esphome/install/personal/jloops/lilygo-tdeck-plus-install-lvgl.yaml`
- `esphome/install/personal/jloops/entity-overrides.yaml`

## Features

- Home launcher with dynamic weather icon
- Modular lights controller (slot-based, up to 8)
- Color Studio page for light color/kelvin controls
- Weather overview + scroll-safe details page
- Climate Controller + Climate Tools pages
- Reader page (news/word/quote feeds)
- Settings with category panels
- Theme Studio (token-based RGB editor)
- Optional camera snapshots (up to 2 slots, manual + auto refresh)
- Screensaver timeout + wake-source diagnostics

## Cameras

Camera support is optional and inert by default (`camera_slot_count: "0"`).

Enable by setting substitutions:

- `camera_slot_count: "1"` or `"2"`
- `camera_slot_1_entity`, `camera_slot_2_entity`
- `ha_base_url` (for `/local/...` image fetch)

Snapshot flow:

1. Device calls `camera.snapshot` in HA to `/config/www/tdeck/cam1.jpg` and `cam2.jpg`.
2. Device loads images via `${ha_base_url}/local/tdeck/camX.jpg?...`.
3. Auto-refresh interval is configurable (`camera_refresh_interval_s`, default `60`).

## Admin Center v1

Hybrid admin is included:

1. Runtime device controls via ESPHome `web_server` entities.
2. Repo companion generator:
   - `tools/admin-center/index.html`
   - Generates install YAML + substitutions block.

## Architecture

Core packages:

- `esphome/packages/board_base.yaml`
- `esphome/packages/persistence_globals.yaml`
- `esphome/packages/ha_entities.yaml`
- `esphome/packages/ui_lvgl.yaml`
- `esphome/packages/display_mipi_lvgl.yaml`
- `esphome/packages/input_touch_gt911_lvgl.yaml`
- `esphome/packages/input_trackball_lvgl.yaml`
- `esphome/packages/input_keyboard_i2c_lvgl.yaml`

## Docs

- `docs/architecture.md`
- `docs/migration.md`
- `docs/release.md`
- `docs/handoff-context.md`
- `docs/entities-template.md`
- `docs/ha-element-framework.md`
- `docs/component-reference-checklist.md`
- `docs/cameras.md`
- `docs/admin-center.md`

## Process Contract

Every code pass updates:

1. code
2. docs
3. handoff report (`docs/handoff-context.md`)

