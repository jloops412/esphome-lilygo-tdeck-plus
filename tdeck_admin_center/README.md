# T-Deck Admin Center Add-on

Home Assistant add-on (Ingress) for T-Deck provisioning, typed entity mapping, theme/layout configuration, and safe managed deployment.

## Baseline

- Add-on version: `0.25.0`
- Workspace/profile schema: `5.0`
- Canonical model: typed `entity_instances`

## Core capabilities

1. Guided onboarding:
   - Start New T-Deck
   - Import Existing ESPHome Node
   - Migrate to managed files
2. Typed entity model with first-class type registry.
3. Discovery + mapping workflows designed for large HA entity sets.
4. Managed deploy orchestration via `POST /api/deploy/run`.
5. Backup/restore for managed files.
6. Firmware workflow auto-detect + fallback.

## Primary API groups

- Health/runtime:
  - `GET /api/health`
  - `GET /api/diagnostics/runtime`
  - `GET /api/dashboard/summary`
- Onboarding:
  - `GET /api/onboarding/esphome/nodes`
  - `POST /api/onboarding/start_new`
  - `POST /api/onboarding/import_existing`
  - `POST /api/onboarding/migrate_to_managed`
- Type catalog + autodetect:
  - `GET /api/catalog/types`
  - `POST /api/catalog/autodetect`
  - `POST /api/catalog/accept_detected`
  - `POST /api/catalog/ignore_detected`
- Typed instances:
  - `GET /api/entities/instances`
  - `POST /api/entities/instances/add`
  - `POST /api/entities/instances/update`
  - `POST /api/entities/instances/remove`
  - `POST /api/entities/instances/reorder`
  - `POST /api/entities/instances/bulk`
- Layout/deploy:
  - `GET /api/layout/pages`
  - `POST /api/layout/pages/validate`
  - `POST /api/layout/pages/save`
  - `POST /api/layout/pages/reset`
  - `POST /api/deploy/run`

## Managed scope

Writes are constrained to:

- `/config/esphome/tdeck/<device_slug>/tdeck-install.yaml`
- `/config/esphome/tdeck/<device_slug>/tdeck-overrides.yaml`
- `/config/esphome/tdeck/<device_slug>/generated/*`
- `/config/esphome/tdeck/.backups/<device_slug>/<timestamp>/`

No edits are made outside the managed root.

## Runtime notes

- Ingress transport is relative (`api/...`) for HA ingress compatibility.
- Frontend startup state is explicit (`booting`, `ready`, `error`) with retry.
- Index is served no-cache; static assets are versioned.
