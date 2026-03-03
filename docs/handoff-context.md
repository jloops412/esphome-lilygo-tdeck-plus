# Handoff Context

## Scope Completed (This Pass)

This pass implements the `v0.23.0` Admin Center/firmware contract rebuild layer focused on reliability, usability, and managed deployment safety:

1. add-on version bumped to `0.23.0`
2. workspace/profile contract advanced to schema `4.0`
3. dashboard-first UX added with action cards + runtime summaries
4. camera auto-detect onboarding wired (scan/accept/ignore)
5. dynamic collections expanded beyond lights/cameras to all core collection groups
6. managed generated artifact contract expanded to include page files
7. apply/backup/restore paths fixed to match new generated layout/page filenames
8. install generation include hooks updated to use new generated files
9. release/version defaults aligned to `v0.23.0` in install/template/package substitutions

## Key Backend Changes

File:
- `tdeck_admin_center/rootfs/app/main.py`

Highlights:

1. fixed dashboard summary firmware capability call (`_resolve_firmware_capabilities`)
2. managed path contract now includes:
   - `generated/layout.generated.yaml`
   - `generated/pages/home.generated.yaml`
   - `generated/pages/lights.generated.yaml`
   - `generated/pages/weather.generated.yaml`
   - `generated/pages/climate.generated.yaml`
3. install YAML generator now includes generated page includes
4. apply commit now writes generated page files and reports checksums/changed state
5. backup/restore now includes generated page files and supports legacy fallback restore for `ui-layout.yaml`
6. `/api/generate/install` now returns generated page outputs (`page_home`, `page_lights`, `page_weather`, `page_climate`)
7. collection add/update now supports `role` field for dynamic substitution mapping
8. `/api/health` payload version marker updated to `4`

## Key Frontend Changes

Files:
- `tdeck_admin_center/rootfs/app/static/index.html`
- `tdeck_admin_center/rootfs/app/static/app.js`
- `tdeck_admin_center/rootfs/app/static/styles.css`

Highlights:

1. dashboard section added (status summaries + action cards)
2. camera autodetect controls and status list added to dashboard
3. guided step 2 now includes additional collection editor for:
   - `weather_metrics`
   - `climate_controls`
   - `reader_feeds`
   - `system_entities`
4. collection health summary added
5. guided/advanced mode behavior corrected so guided shell hides in advanced mode
6. generated preview output now includes page-generated diffs
7. generated output view now includes layout + generated page artifacts

## Manifest/Version

Files:
- `tdeck_admin_center/config.yaml`
- `tdeck_admin_center/Dockerfile`

Changes:

1. add-on manifest version: `0.23.0`
2. Docker build arg default: `BUILD_VERSION=0.23.0`

## Public Install/Template Version Alignment

Files:
- `esphome/install/entity-overrides.template.yaml`
- `esphome/install/lilygo-tdeck-plus-install-lvgl-template.yaml`
- `esphome/install/lilygo-tdeck-plus-install-lvgl.yaml`
- `esphome/install/lilygo-tdeck-plus-install.yaml`
- `esphome/packages/ha_entities.yaml`
- `docs/entities-template.md`

Change:

1. `app_release_version` defaults moved from `v0.20.4` to `v0.23.0`

## Docs Updated

1. `README.md`
2. `docs/admin-center.md`
3. `docs/release.md`
4. `docs/handoff-context.md`
5. `tdeck_admin_center/README.md`

## Validation Run

1. `python -m py_compile tdeck_admin_center/rootfs/app/main.py` passed.
2. Python module import smoke passed with expected route registration for:
   - `api_dashboard_summary`
   - `api_cameras_autodetect`
   - `api_generate_install`
   - `api_apply_commit`

## Not Run Here

1. Live Home Assistant Supervisor add-on install/update cycle.
2. Browser-driven ingress validation for all new dashboard and collection UX paths.
3. End-to-end ESPHome compile/flash on physical hardware for generated page include files.

## Immediate Next Steps

1. run ingress/manual QA against a large-entity HA instance to tune collection UX and discovery defaults
2. continue firmware-side modular page include extraction from monolithic `ui_lvgl.yaml`
3. wire generated page hooks into modular UI package includes for compile-time layout authority
4. complete theme dual-authority conflict UX in frontend with explicit state indicator and apply strategy
