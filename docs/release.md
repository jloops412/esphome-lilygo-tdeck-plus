# Release Notes

## Baseline

- Current add-on manifest version in repo: `0.20.6`
- Public install templates now track `stable`.

## Unreleased (Current `main`)

### Admin Center V3 reliability + direct-apply foundation

1. Discovery hardening:
   - health no longer blocks on full discovery fetch
   - async discovery jobs (`start/status/cancel`)
   - stale-cache + duration + last-error metadata
   - paginated entity API remains in place
2. Explorer UX hardening:
   - explicit discovery status panel
   - startup flow no longer masks discovery failures
   - debounced search + in-flight cancellation preserved
3. Workspace/profile system:
   - workspace schema `2.0` with `devices[]`
   - active-device selection and per-device validation reporting
   - compatibility path for legacy profile payloads
4. Generator and apply expansion:
   - full substitution contract coverage
   - workspace/device-aware install and overrides generation
   - managed apply preview and commit endpoints
   - auto backup snapshot + restore endpoints
5. Contracts/meta endpoint:
   - `/api/meta/contracts` for frontend-driven form rendering
6. Mapping API:
   - `/api/mapping/suggest` for ranked entity suggestions
7. Update intelligence (unchanged flow, integrated into V3 UI):
   - latest stable release endpoint (`/api/update/latest`)
   - HA update package generator endpoint (`/api/generate/ha_update_package`)
   - Updates tab with release status and package output remains
8. Add-on update visibility + firmware pending flow:
   - add-on runtime version state persisted in `/data/runtime_state.json`
   - `GET /api/firmware/status` and `POST /api/firmware/update`
   - Overview now shows “Add-on updated” vs “Firmware pending” state
   - default update action is `Backup + Update Firmware` with managed-file scope

### Add-on manifest/runtime

1. Add-on now declares config map access:
   - `map: [config:rw]`
2. Add-on options schema added:
   - `managed_root`
   - `backup_keep_count`
3. Default managed root:
   - `/config/esphome/tdeck`

### Firmware/public contract updates

1. Added public substitution keys:
   - `app_release_channel`
   - `app_release_version`
   - `ui_show_*`
   - `home_tile_show_*`
   - `theme_token_*`
   - `theme_border_width`, `theme_radius`, `theme_icon_mode`
2. Added firmware metadata exposure:
   - `esphome.project.version` from `${app_release_version}`
   - HA diagnostic text sensors for app version/channel
3. Public install refs switched from `main` to `stable`.
4. Home tile visibility now honors UI/home toggle substitutions in LVGL dynamic updates.
5. Settings system panel includes concise admin access instructions.

### Docs/template updates

1. Updated:
   - `README.md`
   - `docs/admin-center.md`
   - `docs/architecture.md`
   - `docs/entities-template.md`
   - `docs/ha-element-framework.md`
2. Updated mapping template:
   - `esphome/install/entity-overrides.template.yaml`

## Next tag recommendation

1. `v0.20.6-admin-update-visibility`
   - add-on version visibility fix + in-app firmware pending prompt + backup-first firmware update action
2. `v0.21.0-admin-apply-backup`
   - managed apply + backup/restore + workspace multi-device foundation
3. follow with firmware modularization tag after validation:
   - `v0.23.0-firmware-modular-ui`

## Tagging flow

1. Merge to `main`.
2. Create release tag.
3. Move `stable` branch to the tested release tag.
4. Bump `app_release_version` to the new tag value.
5. Rebuild and validate ESPHome package pull from `stable`.
