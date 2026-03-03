# T-Deck Admin Center Add-on

Home Assistant add-on (Ingress) for T-Deck configuration, mapping, and managed deployment workflows.

## Version Track

- Current add-on manifest version: `0.22.0`
- API/UI model: V4 guided + advanced workflow

## V4 Capabilities

1. Discovery reliability
   - async discovery jobs (`start/status/cancel`)
   - paginated explorer with search/sort/filter
   - startup and status panel never hide discovery failures
2. Workspace model
   - multi-device workspace payload support (`schema 3.0`)
   - active-device selection and per-device validation
3. Mapping + generation
   - guided flow + advanced tabs
   - dynamic light/camera collections (add/remove/reorder)
   - template catalog apply flow
   - full install and overrides YAML generation
   - generated entities/theme/layout include file output
4. Managed apply
   - preview diffs before apply
   - apply to managed paths only:
     - `/config/esphome/tdeck/<device_slug>/tdeck-install.yaml`
     - `/config/esphome/tdeck/<device_slug>/tdeck-overrides.yaml`
     - `/config/esphome/tdeck/<device_slug>/generated/entities.generated.yaml`
     - `/config/esphome/tdeck/<device_slug>/generated/theme.generated.yaml`
     - `/config/esphome/tdeck/<device_slug>/generated/ui-layout.yaml`
   - auto backup snapshots + restore
5. Layout + theme studio
   - layout validate/save/reset endpoints
   - palette/color-picker theme preview/apply endpoints
6. Update intelligence
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
28. `GET /api/firmware/capabilities`
29. `POST /api/firmware/workflow`
30. `POST /api/firmware/update` (compat alias)
31. `GET /api/diagnostics/runtime`
32. `GET /api/meta/templates`
33. `POST /api/entities/add`
34. `POST /api/entities/update`
35. `POST /api/entities/remove`
36. `POST /api/entities/reorder`
37. `GET /api/layout/load`
38. `POST /api/layout/validate`
39. `POST /api/layout/save`
40. `POST /api/layout/reset_page`
41. `GET /api/theme/palettes`
42. `POST /api/theme/contrast_check`
43. `POST /api/theme/preview`
44. `POST /api/theme/apply`

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

## Ingress Note

`0.21.0+` uses ingress-relative API calls from the frontend (`api/...`), not absolute `/api/...`.
