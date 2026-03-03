# T-Deck Admin Center Add-on

Home Assistant add-on (Ingress) for T-Deck workspace management, entity mapping, theme/layout customization, managed file apply, and firmware workflow orchestration.

## Version Track

- Current add-on manifest version: `0.24.0`
- API/UI model: V6 dashboard + guided + advanced workflows
- Workspace/profile schema: `4.1` (legacy normalization retained)

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
16. `POST /api/entities/bulk_apply`
17. `GET /api/entities/slot_caps`
18. `POST /api/entities/auto_fit_caps`
19. `POST /api/cameras/autodetect`
20. `POST /api/cameras/accept_detected`
21. `POST /api/cameras/ignore_detected`
22. `POST /api/profile/save`
23. `GET /api/profile/load`
24. `POST /api/profile/validate`
25. `POST /api/layout/validate`
26. `POST /api/layout/save`
27. `POST /api/layout/reset_page`
28. `GET /api/theme/palettes`
29. `GET /api/theme/state`
30. `POST /api/theme/preview`
31. `POST /api/theme/apply`
32. `POST /api/theme/apply_web`
33. `POST /api/theme/apply_device_sync`
34. `POST /api/theme/resolve_conflict`
35. `POST /api/apply/preview`
36. `POST /api/apply/commit`
37. `GET /api/backups/list`
38. `POST /api/backups/restore`
39. `GET /api/firmware/status`
40. `GET /api/firmware/capabilities`
41. `POST /api/firmware/workflow`
42. `GET /api/update/latest`
43. `POST /api/generate/install`
44. `POST /api/generate/overrides`
45. `POST /api/generate/ha_update_package`

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
3. Startup UX now exposes explicit startup states and actionable retry/error diagnostics.
4. Frontend assets are versioned; index responses are no-cache to avoid stale bootstrap scripts after upgrade.

## Startup Troubleshooting

If the UI is stuck at `Status loading...` / `Initializing...`:

1. Verify add-on version is `0.24.0` or newer.
2. Click `Retry Startup` in the mode/status panel.
3. Check transport diagnostics:
   - `API Base`
   - `Ingress Hint`
   - `Last Path`
   - `Last Status`
4. If still stale, remove/re-add custom repo and restart Supervisor before reinstalling.
6. Guided Step 3 slot-management studio
   - inline smart entity comboboxes for row mapping
   - per-row controls (`select`, `clear`, `duplicate`, `move`, `delete`)
   - bulk controls (`enable all`, `disable all`, `remove disabled`, `dedupe`)
   - slot runtime controls (`slot cap`, `page size`) with auto-fit action
