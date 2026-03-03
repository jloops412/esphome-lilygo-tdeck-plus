# Admin Center

`T-Deck Admin Center` is the HA add-on used to configure, generate, deploy, and recover T-Deck firmware configs.

## Version baseline

- Add-on: `0.25.0`
- Workspace/profile schema: `5.0`
- Default firmware release channel: `stable`

## UX model

- `Guided` mode (default): Device -> Features -> Entities -> Theme -> Layout -> Deploy
- `Advanced` mode: full API-backed controls, generation, backup/restore, diagnostics

## Onboarding paths

### Start New T-Deck

1. Open Guided Step 1.
2. Click `Start New T-Deck`.
3. Configure typed entities in Step 3.
4. Deploy in Step 6.

### Import Existing ESPHome Node

1. Click `Scan Existing Nodes`.
2. Select a detected node.
3. Click `Import Existing Node`.
4. Optionally click `Migrate to Managed Files`.

## Canonical data model

Schema `5.0` primary structures:

- `device_workspace.devices[]`
- `type_registry`
- `entity_instances[]`
- `page_layouts[]`
- `deployment_profile`

Compatibility normalization from prior schemas is still active for one transition window.

## Core typed entity workflows

First-class types currently supported:

1. Light
2. Switch
3. Climate
4. Weather
5. Camera
6. Cover
7. Lock
8. Fan
9. Media Player
10. Sensor/Binary Sensor

Each type includes discovery hints, role mapping support, and generated firmware contract output.

## Deploy pipeline

`POST /api/deploy/run` orchestrates:

1. Validation
2. Preview
3. Backup
4. Managed file writes
5. Firmware workflow

Firmware workflow selection order:

1. ESPHome compile/install service
2. Native update entity
3. Manual fallback instructions

## Managed file boundaries

Admin Center writes only under:

- `/config/esphome/tdeck/<device_slug>/`
- `/config/esphome/tdeck/.backups/<device_slug>/<timestamp>/`

No writes are made outside the managed root.

## API groups

- Onboarding:
  - `GET /api/onboarding/esphome/nodes`
  - `POST /api/onboarding/start_new`
  - `POST /api/onboarding/import_existing`
  - `POST /api/onboarding/migrate_to_managed`
- Type catalog:
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
- Layout:
  - `GET /api/layout/pages`
  - `POST /api/layout/pages/validate`
  - `POST /api/layout/pages/save`
  - `POST /api/layout/pages/reset`
- Deploy/workflow:
  - `POST /api/deploy/run`
  - `GET /api/firmware/status`
  - `GET /api/firmware/capabilities`
  - `POST /api/firmware/workflow`

## Ingress/runtime diagnostics

Runtime diagnostics should be checked first when UI is stuck:

- `GET /api/health`
- `GET /api/diagnostics/runtime`

The frontend uses ingress-relative transport and startup state (`booting`, `ready`, `error`) with retry support.
