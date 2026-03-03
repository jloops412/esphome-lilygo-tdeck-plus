# Migration Guide

## From older installs to current LVGL package path

1. Start from `esphome/install/lilygo-tdeck-plus-install-lvgl.yaml`.
2. Copy your entities into substitutions (or from `entity-overrides.template.yaml`).
3. Keep local secrets in HA.
4. Compile once over USB if needed, then OTA.

## Key behavioral changes

- ALT-only keyboard shortcuts for command actions
- keyboard ALT arm timeout is tunable (`keyboard_alt_timeout_ms`)
- app-wide units model (metric/imperial)
- climate uses optimistic local state + ack-based sync
- weather split into overview/details
- optional cameras page (off by default)
- Theme Studio uses swatch pages (RGB sliders removed)
- runtime admin controls available through ESPHome web server entities
- HA add-on admin center available via Ingress
- Admin Center V2 adds profile save/load, validation, paging, and cached entity discovery
- Admin Center V3 adds discovery jobs, workspace multi-device model, and managed apply/backup/restore
- Admin Center V4 adds Guided mode, dynamic collections, full-page layout builder, and palette-based theme workflow
- public install refs now track `stable` channel by default
- firmware publishes app release metadata (`app_version`/`app_channel`) for HA update button workflows

## Public profile cleanup

- Personal mappings moved out of main install files.
- Use personal profile path if needed:
  - `esphome/install/personal/jloops/...`

## Common issues

1. `couldn't find remote ref`: update package `ref` to a valid tag/branch.
2. old package cache: keep `refresh: 1min` while testing.
3. parser errors before package merge: keep local `esphome:` and `esp32:` blocks in install YAML.
4. screensaver not sleeping: verify wake toggles and check diagnostics activity source.
5. cameras not visible: set `camera_slot_count` to `1` or `2`.
6. ALT shortcuts not firing: verify ESC-prefix/ALT behavior and check `settings_diag_shortcut_lbl`.
7. Admin Center "loading forever": refresh discovery cache and clear domain/search filters; check stale cache error text.
9. Managed apply not writing files: ensure add-on has `config:rw` mapping and `managed_root` points to a writable path.
10. Backup restore missing entries: verify device slug matches active workspace device and click `Refresh Backups`.
8. HA update button missing: generate/apply HA update package from Admin Center `Updates` tab and verify native ESPHome firmware update entity is enabled.
