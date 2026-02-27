# Architecture Notes

## Stable install path

- Keep one drop-in install YAML as the runtime source of truth for Home Assistant installs.
- The install YAML should pull modular package files from this repo by tag.
- Do not regress the manual display lambda architecture unless a replacement is proven stable.

## Development path

- Keep organization and documentation in repo for collaboration.
- Move functionality in phases to logical packages only after parity checks.

## Immediate improvements in scope

1. Improve single-flow light controller UX.
2. Improve weather dashboard readability and robustness.
3. Improve feed landing and reader ergonomics.
4. Continue GPS reliability verification and diagnostics.

## Non-goals right now

- LVGL/card-grid redesign.
- Audio/mic/voice features.
- Major display stack rewrites.
