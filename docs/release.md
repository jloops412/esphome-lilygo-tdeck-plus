# Release Notes

## Baseline

- Current add-on manifest version in repo: `0.23.1`
- Public install templates now track `stable`.

## Unreleased (Current `main`)

### Admin Center v0.23.1 robust startup hotfix

1. Fixed frontend bootstrap regression in `ensureCollections()` (missing `);`) that could block app initialization.
2. Added explicit startup state machine in UI:
   - `booting`
   - `ready`
   - `error`
3. Added startup failure banner with actionable diagnostics:
   - failing endpoint/path
   - HTTP status
   - resolved transport base
4. Added `Retry Startup` action for single-shot startup retry.
5. Added versioned static asset contract:
   - `styles.css?v=<addon_version>`
   - `app.js?v=<addon_version>`
6. Added script-load fallback banner (`onerror`) when frontend assets fail to load.
7. Added backend health metadata:
   - `frontend_asset_version`
   - `ingress_expected_prefix`
8. Added no-cache semantics for `index.html` and long-cache headers for versioned static assets.
9. Added local JS parse gate script:
   - `tdeck_admin_center/tools/check_js_syntax.py`
10. Bumped add-on release metadata to `0.23.1`:
    - `tdeck_admin_center/config.yaml`
    - `tdeck_admin_center/Dockerfile`

### Admin Center v0.23.0 mega dashboard + schema 4.0 pass

1. Dashboard-first UX:
   - action cards (`Connect Device`, `Map Entities`, `Theme`, `Layout`, `Deploy`, `Recover`)
   - workspace summary + validation + firmware capability strip
   - camera auto-detect scan/accept/ignore controls
2. Workspace/profile model upgraded:
   - schema constants moved to `4.0`
   - frontend fallback workspace schema moved to `4.0`
   - landing and camera autodetect states normalized
3. Dynamic collections expanded in frontend/backend:
   - `lights`, `cameras`, `weather_metrics`, `climate_controls`, `reader_feeds`, `system_entities`
   - role-aware mapping rows for non-slot collections
4. Managed generated artifact contract expanded:
   - `generated/layout.generated.yaml` (replaces `generated/ui-layout.yaml`)
   - `generated/pages/home.generated.yaml`
   - `generated/pages/lights.generated.yaml`
   - `generated/pages/weather.generated.yaml`
   - `generated/pages/climate.generated.yaml`
5. Apply/backup/restore parity fixed:
   - commit now writes page generated files
   - backup manifests/checksums include page generated files
   - restore now restores layout + page generated files (with legacy `ui-layout.yaml` fallback)
6. Health/dashboard reliability fixes:
   - fixed dashboard firmware-capability function call
   - health payload version updated to `4`
7. Install generation includes the new generated page include hooks.
8. Release metadata defaults aligned to `v0.23.0` in install/template/package substitutions.

### Admin Center v0.22.0 mega UX/configuration upgrade

1. Guided + Advanced dual-mode UX:
   - Guided default: Device -> Features -> Entities -> Theme -> Layout -> Deploy
   - Advanced tabs kept for power users and raw outputs
2. Workspace schema upgraded to `3.0` with compatibility migration for older payloads.
3. Dynamic collection model:
   - lights/cameras add/remove/reorder in UI
   - template catalog apply flow for rapid mapping bootstrap
4. Full layout workflow added:
   - layout load/validate/save/reset endpoints
   - grid+sections editor with overlap/bounds validation
5. Theme Studio modernization:
   - palette discovery endpoint
   - token-focused color picker workflow
   - preview/apply/contrast-check endpoints
6. Managed apply now previews and writes generated artifacts:
   - `generated/entities.generated.yaml`
   - `generated/theme.generated.yaml`
   - `generated/layout.generated.yaml`
7. Startup behavior simplified:
   - no heavy generation/apply calls during boot
   - health/runtime/discovery readiness first
8. Generated files hardened for compile safety:
   - removed risky inline lambda summaries from generated package files
   - generated theme file now emits canonical `theme_token_*` substitutions.

### Admin Center v0.21.0 recovery + robust workflow

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
8. Ingress 404 fix:
   - frontend transport moved to ingress-relative API calls (`api/...`)
   - added transport diagnostics strip in Overview
   - startup now reports actionable `method/path/status/error` on API failures
9. Firmware workflow hardening:
   - new endpoints:
     - `GET /api/firmware/capabilities`
     - `POST /api/firmware/workflow`
     - `GET /api/diagnostics/runtime`
   - `POST /api/firmware/update` kept as compatibility alias
   - auto-detect + fallback method selection (`esphome_service`, `native_update_entity`, `manual_fallback`)
   - legacy firmware status surfaced as `unknown_legacy`
10. Discovery API scale metadata:
   - stage reporting (`queued`, `loading_states`, `indexing`, `completed`, `failed`, `cancelled`)
   - response metadata: `filtered_total`, `returned`, `query_time_ms`
   - optional `fields=minimal` mode for Explorer performance

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

1. `v0.23.1-admin-startup-hotfix`
   - startup bootstrap fix + ingress/cache hardening + startup diagnostics UX
2. next:
   - `v0.23.2-admin-guided-flow-polish`
   - `v0.24.0-canvas-advanced-layout-constraints`

## Tagging flow

1. Merge to `main`.
2. Create release tag.
3. Move `stable` branch to the tested release tag.
4. Bump `app_release_version` to the new tag value.
5. Rebuild and validate ESPHome package pull from `stable`.
