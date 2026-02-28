# Architecture Notes

## Stable install path

- Keep one drop-in install YAML as the runtime source of truth for Home Assistant installs.
- The install YAML should pull modular package files from this repo by tag.
- Keep a parallel LVGL install track during migration to avoid destabilizing stable users.

## Development path

- Keep organization and documentation in repo for collaboration.
- Move functionality in phases to logical packages only after parity checks.
- Maintain two install targets during LVGL migration:
  - Stable manual-rendered UI.
  - LVGL beta UI.

## Immediate improvements in scope

1. Keep top-level navigation clean with home-menu + subpages.
2. Keep light control controller-first and fast (no page hopping).
3. Support theme variants and on-device theme switching.
4. Continue weather/feed readability and GPS diagnostics.

## Non-goals right now

- Audio/mic/voice features.
- Major display stack rewrites.
