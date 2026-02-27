# Architecture Notes

## Stable install path

- Keep one monolithic install YAML as the runtime source of truth for Home Assistant installs.
- Do not regress the manual display lambda architecture unless a replacement is proven stable.

## Development path

- Keep organization and documentation in repo for collaboration.
- Move functionality in phases to logical packages only after parity checks.

## Immediate improvements in scope

1. Wake flow should apply keyboard backlight policy when waking the display.
2. Feed page should no longer surface a settings shortcut tile.
3. Add GPS entities for HA visibility.

## Non-goals right now

- LVGL/card-grid redesign.
- Audio/mic/voice features.
- Major display stack rewrites.
