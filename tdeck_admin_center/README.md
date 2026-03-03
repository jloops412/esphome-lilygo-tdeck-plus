# T-Deck Admin Center Add-on

Home Assistant add-on (Ingress) for T-Deck workspace management, entity mapping, theme/layout customization, managed file apply, and firmware workflow orchestration.

## Version Track

- Current add-on manifest version: `0.23.0`
- API/UI model: V5 dashboard + guided + advanced workflows
- Workspace/profile schema: `4.0` (legacy normalization retained)

## V5 Capabilities

1. Dashboard-first UX
   - action cards (`Connect Device`, `Map Entities`, `Theme`, `Layout`, `Deploy`, `Recover`)
   - workspace validation and firmware capability summaries
   - camera autodetect onboarding (scan/accept/ignore)
2. Discovery reliability
   - async discovery jobs (`start/status/cancel`)
   - paginated explorer with search/sort/filter
   - startup and status panel do not hide discovery failures
3. Dynamic mapping model
   - collections for `lights`, `cameras`, `weather_metrics`, `climate_controls`, `reader_feeds`, `system_entities`
   - role-aware rows for substitution-key mapping
   - template catalog apply flow
4. Managed generation/apply
   - install + overrides generation
   - generated artifacts:
     - `generated/entities.generated.yaml`
     - `generated/theme.generated.yaml`
     - `generated/layout.generated.yaml`
     - `generated/pages/home.generated.yaml`
     - `generated/pages/lights.generated.yaml`
     - `generated/pages/weather.generated.yaml`
     - `generated/pages/climate.generated.yaml`
   - preview diffs before apply
   - managed-scope writes only
   - automatic backups + restore
5. Firmware workflow
   - capability-based auto-detect and fallback
   - legacy-safe status handling (`unknown_legacy`)
   - backup-first firmware action path

## API (Primary)

1. `GET /api/health`
2. `GET /api/diagnostics/runtime`
3. `GET /api/dashboard/summary`
4. `POST /api/dashboard/action`
5. `POST /api/discovery/jobs/start`
6. `GET /api/discovery/jobs/<id>`
7. `POST /api/discovery/jobs/<id>/cancel`
8. `GET /api/discovery/domains`
9. `GET /api/discovery/entities`
10. `POST /api/discovery/refresh`
11. `GET /api/entities/collections`
12. `POST /api/entities/add`
13. `POST /api/entities/update`
14. `POST /api/entities/remove`
15. `POST /api/entities/reorder`
16. `POST /api/cameras/autodetect`
17. `POST /api/cameras/accept_detected`
18. `POST /api/cameras/ignore_detected`
19. `POST /api/profile/save`
20. `GET /api/profile/load`
21. `POST /api/profile/validate`
22. `POST /api/layout/validate`
23. `POST /api/layout/save`
24. `POST /api/layout/reset_page`
25. `GET /api/theme/palettes`
26. `GET /api/theme/state`
27. `POST /api/theme/preview`
28. `POST /api/theme/apply`
29. `POST /api/theme/apply_web`
30. `POST /api/theme/apply_device_sync`
31. `POST /api/theme/resolve_conflict`
32. `POST /api/apply/preview`
33. `POST /api/apply/commit`
34. `GET /api/backups/list`
35. `POST /api/backups/restore`
36. `GET /api/firmware/status`
37. `GET /api/firmware/capabilities`
38. `POST /api/firmware/workflow`
39. `GET /api/update/latest`
40. `POST /api/generate/install`
41. `POST /api/generate/overrides`
42. `POST /api/generate/ha_update_package`

## Managed Scope

Managed writes are intentionally constrained:

1. `/config/esphome/tdeck/<device_slug>/tdeck-install.yaml`
2. `/config/esphome/tdeck/<device_slug>/tdeck-overrides.yaml`
3. `/config/esphome/tdeck/<device_slug>/generated/*`
4. `/config/esphome/tdeck/.backups/<device_slug>/<timestamp>/`

No in-place edits occur outside managed paths.

## Add-on Options

Configured via add-on options (`/data/options.json`):

- `managed_root` (default `/config/esphome/tdeck`)
- `backup_keep_count` (default `30`)

## Notes

1. Ingress API transport uses relative `api/...` paths (not absolute `/api/...`).
2. Docker build includes explicit `run.sh` copy and CRLF normalization.
