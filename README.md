# LilyGO T-Deck Plus HA Controller

This repo tracks the ESPHome controller work for LilyGO T-Deck Plus.

Current priorities:

1. Preserve the known-good manual-rendered baseline.
2. Improve UI/UX without destabilizing display/touch/input.
3. Add GPS entity support.
4. Improve keyboard backlight wake behavior while preserving manual `Alt+B`.
5. Maintain a single drop-in install YAML for ESPHome/HA.

## Install

Use one install YAML in HA/ESPHome:

- `esphome/install/lilygo-tdeck-plus-install.yaml`

It pulls modular files from this repo by release tag.

## Current UI flow

1. `LST`: Light list page.
2. `CTRL`: Single-flow light controller (prev/toggle/next + dim/bright + presets).
3. `PSET`: Light presets page (warm/cool/relax/focus/party).
4. `WX`: Weather dashboard.
5. `READ`: Feed/reader launcher with compact previews.
6. `SET`: Device settings and calibration.

## Quick keyboard shortcuts

1. `1`..`6`: jump directly to tabs `LST/CTRL/PSET/WX/READ/SET`.
2. `[` / `]`: previous/next selected light.
3. `-` / `+`: dim/brighten selected light.
4. `T`: toggle selected light.
5. `B`: keyboard backlight toggle.
6. `N` / `M`: keyboard backlight down/up.
7. `K`: start touch calibration.

See [`docs/architecture.md`](docs/architecture.md), [`docs/migration.md`](docs/migration.md), and [`docs/release.md`](docs/release.md) for conventions and release details.
