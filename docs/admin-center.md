# Admin Center

## What It Is

`T-Deck Admin Center` is the Home Assistant add-on (Ingress UI) used to:

1. discover HA entities quickly
2. map entities to T-Deck features (lights/weather/climate/cameras/reader)
3. manage multi-device workspaces/profiles
4. generate:
   - drop-in install YAML
   - substitutions overrides YAML
5. preview/apply managed YAML files with auto backup/restore

The add-on now supports managed direct-apply in a guarded scope:

1. writes only under `/config/esphome/tdeck/*`
2. never patches unrelated user YAML files
3. creates an automatic backup snapshot before every apply

## Access Paths

1. Home Assistant:
   - `Settings -> Add-ons -> T-Deck Admin Center -> Open Web UI`
2. On-device hint:
   - `Settings -> System` shows:
     - `Device: http://<device-ip>`
     - `HA: Add-ons -> T-Deck Admin Center`

## Admin Center V5 UX (v0.23.1)

Dashboard + dual mode:

1. `Dashboard` (default landing): status summary + action cards + camera auto-detect onboarding
2. `Guided` (default workflow): `Device -> Features -> Entities -> Theme -> Layout -> Deploy`
3. `Advanced`: tabbed controls for profiles, updates, generation, and diagnostics.

Guided mode keeps primary workflows obvious for first-time users while Dashboard/Advanced expose full power controls and diagnostics.

## Admin Center Tabs

1. `Overview`
   - HA connectivity
   - discovery cache status
   - profile count
   - add-on updated vs firmware pending status
   - one-click firmware update with optional backup
2. `Entity Explorer`
   - domain filter
   - debounced search (`300ms`)
   - pagination
   - sort + mappable-only filter
   - "Use" action into active mapping field
3. `Mapping Wizard`
   - feature toggles + page visibility toggles
   - dynamic lights/cameras collections (add/remove/reorder)
   - template catalog (`lights/weather/climate/cameras/reader/system`)
   - weather/climate/reader/theme mappings
4. `Profiles`
   - save/load/rename/delete
   - validation diagnostics
5. `Generate`
   - install YAML output
   - overrides YAML output
6. `Updates`
   - latest stable release status
   - release URL and cache age
   - HA update-package YAML generation
7. `Deployment`
   - install/override output
   - apply preview diffs
   - commit managed apply
   - backup list + restore

## API V4

1. `GET /api/health`
   - includes `frontend_asset_version` and `ingress_expected_prefix`
2. `POST /api/discovery/jobs/start`
3. `GET /api/discovery/jobs/<id>`
4. `POST /api/discovery/jobs/<id>/cancel`
5. `GET /api/discovery/domains?job_id=`
6. `GET /api/discovery/entities?job_id=&domain=&q=&page=&page_size=&sort=&only_mappable=`
7. `POST /api/discovery/refresh`
8. `GET /api/profile/list`
9. `POST /api/profile/save`
10. `GET /api/profile/load?name=`
11. `POST /api/profile/delete`
12. `POST /api/profile/rename`
13. `POST /api/profile/validate`
14. `GET /api/workspace/list`
15. `POST /api/workspace/save`
16. `GET /api/workspace/load?name=`
17. `POST /api/mapping/suggest`
18. `GET /api/meta/contracts`
19. `GET /api/dashboard/summary`
20. `POST /api/dashboard/action`
21. `GET /api/entities/collections`
22. `POST /api/cameras/autodetect`
23. `POST /api/cameras/accept_detected`
24. `POST /api/cameras/ignore_detected`
25. `GET /api/theme/state`
26. `POST /api/theme/apply_web`
27. `POST /api/theme/apply_device_sync`
28. `POST /api/theme/resolve_conflict`
29. `POST /api/generate/install`
30. `POST /api/generate/overrides`
31. `GET /api/update/latest?channel=stable`
32. `POST /api/generate/ha_update_package`
33. `POST /api/apply/preview`
34. `POST /api/apply/commit`
35. `GET /api/backups/list?device_slug=`
36. `POST /api/backups/restore`
37. `GET /api/firmware/status?device_slug=&target_version=&native_firmware_entity=&app_version_entity=`
38. `GET /api/firmware/capabilities?device_slug=&target_version=&native_firmware_entity=&app_version_entity=`
39. `POST /api/firmware/workflow`
40. `POST /api/firmware/update` (compat alias to workflow install-only mode)
41. `GET /api/diagnostics/runtime`
42. `GET /api/meta/templates`
43. `POST /api/entities/add`
44. `POST /api/entities/update`
45. `POST /api/entities/remove`
46. `POST /api/entities/reorder`
47. `GET /api/layout/load`
48. `POST /api/layout/validate`
49. `POST /api/layout/save`
50. `POST /api/layout/reset_page`
51. `GET /api/theme/palettes`
52. `POST /api/theme/preview`
53. `POST /api/theme/apply`
54. `POST /api/theme/contrast_check`

## Discovery Performance Model

1. Discovery runs as explicit async jobs (`queued/running/completed/failed/cancelled`).
2. UI polls job status and never blocks page startup on full discovery.
3. Cache still uses TTL (`15s`) and paginated responses (`100` default page size).
4. Explorer keeps request cancellation and debounced search to avoid flooding.
5. Refresh action triggers forced job and preserves stale cache fallback visibility.

## Workspace Storage

Workspaces and legacy profiles are stored in add-on data:

- `/data/profiles/*.json`
- `/data/workspaces/*.json`

This survives add-on restarts/upgrades unless add-on data is removed.

## Managed Apply Storage

1. Managed output root:
   - `/config/esphome/tdeck`
2. Per-device files:
   - `/config/esphome/tdeck/<device_slug>/tdeck-install.yaml`
   - `/config/esphome/tdeck/<device_slug>/tdeck-overrides.yaml`
   - `/config/esphome/tdeck/<device_slug>/generated/entities.generated.yaml`
   - `/config/esphome/tdeck/<device_slug>/generated/theme.generated.yaml`
   - `/config/esphome/tdeck/<device_slug>/generated/layout.generated.yaml`
   - `/config/esphome/tdeck/<device_slug>/generated/pages/home.generated.yaml`
   - `/config/esphome/tdeck/<device_slug>/generated/pages/lights.generated.yaml`
   - `/config/esphome/tdeck/<device_slug>/generated/pages/weather.generated.yaml`
   - `/config/esphome/tdeck/<device_slug>/generated/pages/climate.generated.yaml`
3. Backup snapshots:
   - `/config/esphome/tdeck/.backups/<device_slug>/<timestamp>/`

## HA Update Button Workflow

1. Public install files default to `ref: stable`.
2. Firmware exposes installed app metadata:
   - `sensor.<device>_app_version`
   - `sensor.<device>_app_channel`
3. Updates tab generates a HA package creating:
   - latest stable release sensor
   - template update entity (`update.tdeck_app_update_<device>`)
   - install proxy action to native ESPHome firmware updater (`update.<device>_firmware`)
4. Update install is non-destructive to mapped entities/settings because OTA runs from the user's existing node config.
5. Save the generated YAML in your HA packages folder, then reload/restart HA to create entities.

## Troubleshooting

### Add-on repo not valid / stale store errors

1. Remove custom repo from Add-on Store.
2. Restart Supervisor.
3. Re-add:
   - `https://github.com/jloops412/esphome-lilygo-tdeck-plus`
4. Reopen Add-on Store and install `T-Deck Admin Center`.

### Ingress `404` on health/status/entities

Fixed in add-on `0.21.0`:

1. Frontend now uses ingress-relative API paths (`api/...`) instead of absolute `/api/...`.
2. Overview includes transport diagnostics (`API Base`, `Last Path`, `Last Status`, `Last Error`).
3. Health endpoint returns ingress/server diagnostics (`api_base_hint`, `request_path`, `script_root`).

### UI stuck at `Status loading... / Initializing...`

Fixed in add-on `0.23.1`:

1. Startup now exposes explicit state (`booting`, `ready`, `error`) and an inline error banner.
2. `Retry Startup` reruns startup once without page reload loops.
3. Frontend assets are versioned and `index.html` is served with no-cache headers.
4. Health now reports:
   - `frontend_asset_version`
   - `ingress_expected_prefix`

Recovery sequence:

1. Confirm add-on version `0.23.1` or newer.
2. Open `System Health` and inspect transport diagnostics (`API Base`, `Last Path`, `Last Status`).
3. Click `Retry Startup`.
4. If still failing, run add-on store repo cache refresh (remove repo, restart Supervisor, re-add repo URL).

### Add-on build failure (`/run.sh` missing)

Fixed in add-on `0.20.2` and newer:

1. Dockerfile now copies `run.sh` explicitly.
2. Dockerfile normalizes CRLF before chmod.

If you still see this error, run the same repo-cache refresh sequence above and reinstall.

### Entity loading appears stuck

1. Open `Overview` and confirm HA connectivity is `connected`.
2. Check `Discovery` status for job state/error text.
3. Click `Refresh Discovery Cache` to start a forced job.
4. If needed, click `Cancel Discovery Job` to stop a long-running fetch and continue with cached results.
5. Wait for terminal state (`completed`, `failed`, `cancelled`).
6. In `Entity Explorer`, reset:
   - domain = `all`
   - search = empty
   - page size = `100`
7. If cache is stale, check `last_error` in status line.

### Direct apply safety behavior

1. `Apply` writes only managed files under `/config/esphome/tdeck`.
2. A timestamped backup snapshot is created before each write.
3. Use backup restore endpoint/UI if a generated config is bad.

### Generated update entity does not install firmware

1. Verify native ESPHome firmware entity exists:
   - `update.<device>_firmware`
2. If it is missing, re-enable the ESPHome update entity in Home Assistant and reload.
3. Re-generate HA update package from `Updates` tab if you changed device name/entity assumptions.

### Add-on updated vs firmware pending

1. `Overview -> Firmware Workflow` compares target release vs installed firmware entity state.
2. If firmware is legacy or unknown, status shows `unknown_legacy` and still offers safe workflow actions.
3. Workflow modes:
   - `auto` (default)
   - `build_install`
   - `install_only`
   - `manual_fallback`
4. Backup manifests include `reason: pre_firmware_update` or `pre_build_install` with workflow context.

### Guided mode quick deploy

1. Complete steps 1-5.
2. Open step 6 and click `Validate + Apply + Auto Deploy`.
3. The pipeline runs:
   - profile validation
   - apply preview
   - managed backup + apply
   - firmware workflow (`auto`)
4. Generated install/override/theme/layout artifacts remain available in Advanced `Generate`.
