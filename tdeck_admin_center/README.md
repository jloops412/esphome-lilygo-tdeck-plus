# T-Deck Admin Center Add-on

Home Assistant add-on (Ingress) for T-Deck configuration, mapping, and managed deployment workflows.

## Version Track

- Current add-on manifest version: `0.20.6`
- API/UI model: V3 foundation

## V3 Capabilities

1. Discovery reliability
   - async discovery jobs (`start/status/cancel`)
   - paginated explorer with search/sort/filter
   - startup and status panel never hide discovery failures
2. Workspace model
   - multi-device workspace payload support (`schema 2.0`)
   - active-device selection and per-device validation
3. Mapping + generation
   - feature-aware mapping forms
   - full install and overrides YAML generation
4. Managed apply
   - preview diffs before apply
   - apply to managed paths only:
     - `/config/esphome/tdeck/<device_slug>/tdeck-install.yaml`
     - `/config/esphome/tdeck/<device_slug>/tdeck-overrides.yaml`
   - auto backup snapshots + restore
5. Update intelligence
   - latest release endpoint and cache
   - HA update-package generation

## API

1. `GET /api/health`
2. `POST /api/discovery/jobs/start`
3. `GET /api/discovery/jobs/<id>`
4. `POST /api/discovery/jobs/<id>/cancel`
5. `GET /api/discovery/domains`
6. `GET /api/discovery/entities`
7. `POST /api/discovery/refresh`
8. `GET /api/profile/list`
9. `POST /api/profile/save`
10. `GET /api/profile/load`
11. `POST /api/profile/delete`
12. `POST /api/profile/rename`
13. `POST /api/profile/validate`
14. `GET /api/workspace/list`
15. `POST /api/workspace/save`
16. `GET /api/workspace/load`
17. `POST /api/mapping/suggest`
18. `GET /api/meta/contracts`
19. `POST /api/generate/install`
20. `POST /api/generate/overrides`
21. `GET /api/update/latest?channel=stable`
22. `POST /api/generate/ha_update_package`
23. `POST /api/apply/preview`
24. `POST /api/apply/commit`
25. `GET /api/backups/list`
26. `POST /api/backups/restore`
27. `GET /api/firmware/status`
28. `POST /api/firmware/update`

## Add-on Options

Configured via add-on options (`/data/options.json`):

- `managed_root` (default `/config/esphome/tdeck`)
- `backup_keep_count` (default `30`)

## Safety Model

Managed apply is intentionally constrained:

1. no in-place edits of unrelated YAML files
2. always snapshot before write
3. restore path available in UI/API

## Build Note

`/run.sh` build failure was fixed by explicitly copying `run.sh` in Docker image and normalizing CRLF before chmod.
