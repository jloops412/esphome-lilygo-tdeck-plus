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

1. `Home`: clean launcher page (`Lights`, `Weather`, `Reader`, `Settings`, `Themes`, `Sleep`).
2. `Lights`: controller-only page (prev/next light, toggle, dim, brighten, preset-cycle).
3. `Weather`: dashboard page with resilient value formatting for missing data.
4. `Reader`: feed/source launcher into full detail reader.
5. `Settings`: wake and timeout controls plus keyboard-backlight toggle.
6. `Theme`: on-device theme presets and display brightness tuning.

## Quick keyboard shortcuts

1. `1`..`6`: jump directly to pages `Home/Lights/Weather/Reader/Settings/Theme`.
2. `[` / `]`: previous/next selected light.
3. `-` / `+`: dim/brighten selected light.
4. `T`: toggle selected light.
5. `B`: keyboard backlight toggle.
6. `N` / `M`: keyboard backlight down/up.
7. `H`: jump to Home page.
8. `K`: start touch calibration.

See [`docs/architecture.md`](docs/architecture.md), [`docs/migration.md`](docs/migration.md), and [`docs/release.md`](docs/release.md) for conventions and release details.
