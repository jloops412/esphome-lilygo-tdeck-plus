# Release Notes

## Current baseline tag

- `v0.18.3-reliability-core`

## Unreleased (current `main`)

- camera snapshot subsystem (optional, slot-based)
- camera pages + detail page + refresh flow
- home camera launcher visibility when cameras enabled
- ESPHome `web_server` runtime admin controls
- screensaver hardening for stale touch-active state
- climate adjust scripts moved to queued execution for rapid tap reliability
- weather details labels set to non-overlap-safe mode
- keyboard camera shortcuts (`Alt+5`, `Alt+6`)
- public install defaults cleaned; personal mappings moved under `install/personal/jloops`
- admin-center generator scaffold in `tools/admin-center`
- docs refreshed and normalized

## Hotfix candidate after `v0.19.0-ui-camera-admin-v1`

- `select.template` compatibility fix for ESPHome 2026.2.2:
  - removed `optimistic` and `initial_option` from template selects that use `lambda`
  - affected IDs:
    - `lvgl_units_mode_select`
    - `lvgl_theme_icon_mode_select`

## Tagging process

1. Merge to `main`.
2. Create new tag (recommended next: `v0.19.0-ui-camera-admin-v1`).
3. Update install YAML `ref` to the release tag.
4. Publish release summary with migration notes.
