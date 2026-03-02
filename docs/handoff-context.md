# Handoff Context

## Repo state

- Branch: `main`
- Last released install ref before this pass: `v0.19.1-select-template-hotfix`
- This pass is local/unreleased until tagged.

## Implemented in this pass

### 1) Keyboard strict ALT reliability fix

Files:

- `esphome/packages/input_keyboard_i2c_lvgl.yaml`
- `esphome/packages/persistence_globals.yaml`
- `esphome/install/*.yaml`

Changes:

1. Fixed root-cause bug where ALT combos were published then returned early (commands never executed).
2. Added tunable ALT arm timeout:
   - `keyboard_alt_timeout_ms` (default `900`)
3. Added diagnostics globals:
   - `kb_alt_armed`
   - `kb_alt_last_timeout_ms`
   - `kb_last_shortcut_text`

### 2) Home header overlap reduction

File:

- `esphome/packages/ui_lvgl.yaml`

Changes:

1. Tightened status/substatus text.
2. Repositioned camera/sleep controls.
3. Shifted home tile rows down for cleaner top header spacing.

### 3) Settings admin clarity + diagnostics expansion

File:

- `esphome/packages/ui_lvgl.yaml`

Changes:

1. Added `Settings -> System` admin hints:
   - `settings_admin_help_lbl`
   - `settings_admin_device_url_lbl`
   - `settings_admin_ha_addon_lbl`
2. Added diagnostics labels:
   - `settings_camera_state_lbl`
   - `settings_camera_refresh_lbl`
   - `settings_diag_shortcut_lbl`
3. Added camera refresh diagnostics globals:
   - `camera_refresh_status_text`
   - `camera_last_snapshot_result`

### 4) Theme Studio swatch rebuild

Files:

- `esphome/packages/ui_lvgl.yaml`
- `esphome/packages/persistence_globals.yaml`

Changes:

1. Removed RGB slider UI from Theme Studio.
2. Added swatch model:
   - `theme_swatch_page` (3 pages)
   - `theme_swatch_index`
   - `theme_edit_color`
3. Added scripts:
   - `theme_swatch_page_prev`
   - `theme_swatch_page_next`
   - `theme_apply_swatch`
   - `theme_render_swatch_page`
4. Added 24 swatch buttons on page, with 3 pages (72 total colors).
5. Kept token apply/revert and shape/icon controls.

### 5) HA Add-on Admin Center v1

Files added:

- `repository.yaml`
- `tdeck-admin-center/config.yaml`
- `tdeck-admin-center/Dockerfile`
- `tdeck-admin-center/run.sh`
- `tdeck-admin-center/rootfs/app/main.py`
- `tdeck-admin-center/rootfs/app/static/index.html`
- `tdeck-admin-center/rootfs/app/static/app.js`
- `tdeck-admin-center/rootfs/app/static/styles.css`
- `tdeck-admin-center/README.md`

Behavior:

1. Ingress add-on UI.
2. Discovery endpoints for HA entities/domains.
3. Install YAML and overrides YAML generation endpoints.
4. v1 is generate/export only (no automatic overwrite in `/config/esphome`).

## Docs updated in this pass

- `README.md`
- `docs/admin-center.md`
- `docs/cameras.md`
- `docs/architecture.md`
- `docs/migration.md`
- `docs/release.md`
- this handoff file

## Follow-up fix (post-pass): HA add-on repository/build errors

Files:

- `tdeck-admin-center/config.yaml`
- `tdeck-admin-center/build.yaml`
- `tdeck-admin-center/Dockerfile`
- `README.md`
- `docs/release.md`

Changes:

1. Add-on manifest compatibility updates:
   - removed `map` entirely (v1 add-on is generate/export only)
   - removed `ports` block for ingress-only add-on
   - removed `i386` from supported arch list
   - bumped add-on version to `0.20.1`
2. Build compatibility updates:
   - moved to HA `*-base:3.20` images
   - Dockerfile now installs `python3` + `py3-pip` explicitly
3. Added explicit README recovery steps for:
   - “not a valid add-on repository”
   - unknown add-on image build error

## Known constraints

1. Local environment here does not include `esphome` CLI; compile/config validation was not run locally.
2. GPS behavior still depends on hardware/antenna/sky visibility.
3. Keyboard backlight firmware control remains deferred (manual keyboard `Alt+B`).

## Next recommended steps

1. Compile in HA ESPHome add-on against this commit.
2. Validate on-device:
   - strict ALT shortcuts
   - home header layout
   - theme swatch page behavior
   - camera diagnostics lines
3. Tag and pin:
   - `v0.20.0-admin-addon-theme-swatch-camera-pass`
