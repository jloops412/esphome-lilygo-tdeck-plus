# Release Process

## Tags

- `v0.1.0-stable`: parity baseline milestone.
- `v0.2.0-gps-kb`: GPS + keyboard wake improvements.
- `v0.3.0-ui-pass1`: first UI redesign milestone.

`v0.3.0-ui-pass1` highlights:

1. Dark-theme and tab polish pass.
2. Lights flow updated so light selection opens controller page.
3. Weather page redesigned to dashboard metric cards.
4. Feed page now shows compact live previews per source.
5. Logger serial disabled (`baud_rate: 0`) to avoid UART contention with GPS.

## Checklist per release

1. `esphome config` passes for `esphome/profiles/stable_snapshot.yaml`.
2. HA add-on compile passes for install YAML.
3. Boot/display/touch/trackball/keyboard parity verified.
4. New features verified (GPS entities, keyboard wake behavior).
5. Tag and push release.
