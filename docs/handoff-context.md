# Handoff Context

## Scope Completed (This Pass)

This pass delivers `v0.24.0` Guided Step 3 rebuild plus medium firmware slot expansion:

1. Guided Step 3 now uses inline smart entity combobox rows.
2. Added row actions (`select`, `clear`, `duplicate`, `move`, `delete`) and bulk actions (`enable all`, `disable all`, `remove disabled`, `dedupe`).
3. Added backend Step 3 transaction APIs:
   - `POST /api/entities/bulk_apply`
   - `GET /api/entities/slot_caps`
   - `POST /api/entities/auto_fit_caps`
4. Workspace/profile schema bumped to `4.1` with compatibility normalization from `4.0`.
5. Added slot runtime model:
   - `light_slot_cap` / `camera_slot_cap`
   - `light_page_size` / `camera_page_size`
6. Firmware lights page moved to paged virtual slots (6 rows + prev/next).
7. Firmware cameras page moved to paged virtual slots (4 rows + prev/next) with single detail image pipeline.
8. Expanded substitution contracts and HA mirrors for light slots to `24` and camera slots to `8`.
9. Version defaults bumped to:
   - add-on `0.24.0`
   - app release `v0.24.0`

## Key Backend Changes

File:
- `tdeck_admin_center/rootfs/app/main.py`

Highlights:

1. `PROFILE_SCHEMA_VERSION` and `WORKSPACE_SCHEMA_VERSION` moved to `4.1`.
2. Added `SLOT_RUNTIME_LIMITS` and normalization helpers.
3. Added `slot_runtime` and `entity_collections_meta` to normalized profile model.
4. Added `bulk_apply`, `slot_caps`, and `auto_fit_caps` endpoints for Guided Step 3 operations.
5. Updated substitution generation to emit:
   - `generated_light_slot_cap`
   - `generated_camera_slot_cap`
   - `generated_light_page_size`
   - `generated_camera_page_size`

## Key Frontend Changes

Files:
- `tdeck_admin_center/rootfs/app/static/index.html`
- `tdeck_admin_center/rootfs/app/static/app.js`
- `tdeck_admin_center/rootfs/app/static/styles.css`

Highlights:

1. Guided Step 3 UI rewritten around inline combobox row editing.
2. Added slot runtime controls and slot caps diagnostics summary.
3. Added one-click `Auto-Fit to Enabled Rows` action.
4. Added debounced suggestion dropdown behavior for row entity fields.
5. Updated runtime clamping to firmware-safe paging:
   - lights `4..6`
   - cameras `2..4`

## Firmware Changes

Files:
- `esphome/packages/ui_lvgl.yaml`
- `esphome/packages/ha_entities.yaml`
- `esphome/packages/persistence_globals.yaml`

Highlights:

1. Added page-state globals (`lights_page_start`, `cameras_page_start`) and camera detail URL state.
2. Added lights paging scripts:
   - `select_light_visible`
   - `lights_page_prev`
   - `lights_page_next`
   - `lights_sync_page_for_selected`
3. Updated light state resolution and control sync to support up to 24 slots.
4. Rebuilt cameras page as paged list rows with explicit previous/next controls.
5. Rebuilt camera detail page to use single `camera_detail_image` pipeline.
6. Updated dynamic labels/diagnostics to reflect paging and selected slot context.

## Manifest/Version

Files:
- `tdeck_admin_center/config.yaml`
- `tdeck_admin_center/Dockerfile`
- install/template substitution files under `esphome/install/`

Changes:

1. add-on manifest version: `0.24.0`
2. Docker build arg default: `BUILD_VERSION=0.24.0`
3. app release defaults: `v0.24.0`

## Docs Updated

1. `README.md`
2. `docs/admin-center.md`
3. `docs/architecture.md`
4. `docs/migration.md`
5. `docs/release.md`
6. `docs/handoff-context.md`
7. `tdeck_admin_center/README.md`

## Validation Run

1. `python -m py_compile tdeck_admin_center/rootfs/app/main.py` passed.
2. `python tdeck_admin_center/tools/check_js_syntax.py tdeck_admin_center/rootfs/app/static/app.js` passed.

## Not Run Here

1. `esphome config` validation (CLI not installed in this environment).
2. Live HA Supervisor add-on install/update cycle.
3. Physical device compile/flash regression run.

## Immediate Next Steps

1. Run `esphome config` and full compile against your live install YAML in HA.
2. Expand slot hard maximums beyond `24/8` only after adding matching firmware UI and entity mirrors.
3. Split monolithic `ui_lvgl.yaml` into modular page/script includes as next refactor gate.
