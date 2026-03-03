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

## Admin Center V3 Tabs

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
   - feature toggles
   - UI visibility toggles
   - light and camera slot editors
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

## API V3

1. `GET /api/health`
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
19. `POST /api/generate/install`
20. `POST /api/generate/overrides`
21. `GET /api/update/latest?channel=stable`
22. `POST /api/generate/ha_update_package`
23. `POST /api/apply/preview`
24. `POST /api/apply/commit`
25. `GET /api/backups/list?device_slug=`
26. `POST /api/backups/restore`
27. `GET /api/firmware/status?device_slug=&target_version=&native_firmware_entity=&app_version_entity=`
28. `POST /api/firmware/update`

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

### Add-on build failure (`/run.sh` missing)

Fixed in add-on `0.20.2` and newer (current `0.20.6`):

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

1. `Overview -> In-App Update Status` compares target release vs installed firmware entity state.
2. If pending, use `Backup + Update Firmware` to snapshot managed files before update.
3. Backup manifests include `reason: pre_firmware_update` and firmware context.
