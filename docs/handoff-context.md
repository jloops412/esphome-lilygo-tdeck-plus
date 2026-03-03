# Handoff Context

## Scope Completed (This Pass)

This pass shipped `0.21.0` recovery and robust firmware workflow hardening:

1. add-on version bumped to `0.21.0`
2. fixed HA Ingress 404 root cause by removing absolute frontend `/api/...` calls
3. added transport diagnostics in Overview (`api_base_resolved`, `last_api_error`, `last_status_code`)
4. expanded runtime diagnostics API:
   - `GET /api/diagnostics/runtime`
5. firmware workflow APIs added:
   - `GET /api/firmware/capabilities`
   - `POST /api/firmware/workflow`
   - `POST /api/firmware/update` now compatibility alias
6. discovery responses now include scale metadata (`filtered_total`, `returned`, `query_time_ms`) and staged job progress.

## Core Decisions Implemented

1. Reliability-first: discovery/startup transparency shipped before deeper UX builder features.
2. Direct apply is guarded and scoped to managed files only (`/config/esphome/tdeck`).
3. Every apply operation creates a rollback snapshot before writing.
4. Legacy profile payloads remain supported via workspace normalization.

## Key Backend Changes

File:
- `tdeck_admin_center/rootfs/app/main.py`

Added/updated:
1. discovery cache model expanded with duration/total metadata.
2. new discovery job lifecycle:
   - `POST /api/discovery/jobs/start`
   - `GET /api/discovery/jobs/<id>`
   - `POST /api/discovery/jobs/<id>/cancel`
3. discovery endpoints now consume cached data plus optional job context.
4. workspace model helpers:
   - `_default_workspace`
   - `_normalize_workspace`
   - `_workspace_active_profile`
5. managed apply + backup + restore endpoints:
   - `POST /api/apply/preview`
   - `POST /api/apply/commit`
   - `GET /api/backups/list`
   - `POST /api/backups/restore`
6. mapping suggestions endpoint:
   - `POST /api/mapping/suggest`
7. add-on options consumed from `/data/options.json`:
   - managed root
   - backup retention count

## Add-on Manifest Changes

File:
- `tdeck_admin_center/config.yaml`

Added:
1. `map: [config:rw]`
2. `options` + `schema` for:
   - `managed_root`
   - `backup_keep_count`

## Frontend Changes

Files:
- `tdeck_admin_center/rootfs/app/static/index.html`
- `tdeck_admin_center/rootfs/app/static/app.js`

Added/updated:
1. workspace/device controls in Overview.
2. explicit discovery status panel.
3. job-based discovery wiring with polling and timeout handling.
4. apply preview + apply commit actions in Generate tab.
5. backup list and restore actions.
6. bootstrap flow now reports "ready with issues" when startup steps fail.

## Docs Updated

1. `README.md`
2. `docs/admin-center.md`
3. `docs/release.md`
4. `docs/handoff-context.md`

## Validation Run

1. `python -m py_compile tdeck_admin_center/rootfs/app/main.py` passed.
2. Flask test-client smoke passed for:
   - `/api/meta/contracts`
   - `/api/profile/list`
   - `/api/workspace/list`
   - `/api/discovery/jobs/start`
   - `/api/discovery/domains`
   - `/api/discovery/entities`
   - `/api/apply/preview`

## Not Run Here

1. Full add-on install/restart cycle inside live Home Assistant Supervisor.
2. Full browser smoke on ingress UI with real HA entity volumes.
3. Full ESPHome compile/flash regression for firmware packages.

## Immediate Next Steps

1. Verify ingress UI with live HA:
   - discovery job start/poll behavior
   - entity explorer latency with large entity sets
2. Validate managed apply writes/backup restore against real `/config/esphome/tdeck`.
3. Add explicit workspace CRUD UI (`/api/workspace/*`) in a follow-up.
4. Continue Phase 4/5 from mission plan:
   - mapping ranking UX refinements
   - canvas builder foundation for Home/Lights/Climate/Weather.
