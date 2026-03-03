# LilyGO T-Deck Plus Home Assistant Controller

Public ESPHome + LVGL firmware and Home Assistant Admin Center for building and managing a T-Deck app from one workflow.

## What ships

- On-device firmware UI for 320x240 T-Deck Plus
- Home Assistant add-on (`T-Deck Admin Center`) with Guided + Advanced modes
- Managed deploy pipeline (validate -> preview -> backup -> apply -> firmware workflow)
- Typed HA element model (schema `5.0`) with migration from earlier profile schemas

## Public install paths

- Firmware install template: `esphome/install/lilygo-tdeck-plus-install-lvgl.yaml`
- Override template: `esphome/install/entity-overrides.template.yaml`
- Add-on folder: `tdeck_admin_center/`

## Start from scratch (recommended)

1. Install `T-Deck Admin Center` from this repository in Home Assistant Add-ons.
2. Open Web UI and use `Guided Mode`.
3. Step 1 (`Device`): click `Start New T-Deck`.
4. Step 3 (`Entities`): add typed elements (`Light`, `Switch`, `Climate`, `Weather`, `Camera`, `Cover`, `Lock`, `Fan`, `Media Player`, `Sensor`) using inline suggestions.
5. In Step 3, set `Device Scope` to `Active Device` for cleaner dropdown results from your selected node.
5. Step 6 (`Deploy`): run guided deploy.

Guided deploy uses a safe transaction:

1. Validate profile
2. Preview managed file diffs
3. Create backup snapshot
4. Write managed files
5. Run firmware workflow with capability auto-detect + fallback

## Import existing ESPHome node

1. In Guided Step 1, click `Scan Existing Nodes`.
2. Select a discovered node.
3. Click `Import Existing Node`.
4. Click `Migrate to Managed Files` when ready.

If detection misses your node, use manual fallback fields in Step 1:

- `Manual Device Slug`, or
- `Manual Entity ID` (for example `update.<slug>_firmware`)

This migrates to managed files without mutating unrelated ESPHome YAML.

## Typed element platform (schema 5.0)

Canonical model:

- `device_workspace.devices[]`
- `type_registry`
- `entity_instances[]`
- `page_layouts[]`
- `deployment_profile`

Compatibility:

- Legacy slot/collection keys are still normalized for one transition window.
- Typed instances are now primary for new configurations.

## Managed files and safety

Managed root:

- `/config/esphome/tdeck/<device_slug>/`

Managed files:

- `tdeck-install.yaml`
- `tdeck-overrides.yaml`
- `generated/entities.generated.yaml`
- `generated/theme.generated.yaml`
- `generated/layout.generated.yaml`
- `generated/pages/home.generated.yaml`
- `generated/pages/lights.generated.yaml`
- `generated/pages/weather.generated.yaml`
- `generated/pages/climate.generated.yaml`
- plus typed metadata artifacts (`types.registry.yaml`, `entities.instances.yaml`, `layout.pages.yaml`, `theme.tokens.yaml`)

Backup root:

- `/config/esphome/tdeck/.backups/<device_slug>/<timestamp>/`

Write boundary:

- Admin Center writes only inside `/config/esphome/tdeck`.

## Firmware update behavior

- Release channel default: `stable`
- Firmware metadata is versioned through `app_release_version`
- Update workflow auto-selects:
  1. ESPHome compile/install service
  2. Native HA update entity
  3. Manual fallback steps

## Cameras

Camera UI is optional. Public default keeps cameras off until configured.

- Set `camera_slot_count` > `0` to enable camera pages in firmware.
- Admin Center supports autodetect/accept/ignore for cameras and other typed entities.

## Troubleshooting

### Add-on shows old version

1. Confirm `tdeck_admin_center/config.yaml` version on `main`.
2. In HA Add-on Store: remove repo -> restart Supervisor -> re-add repo.
3. Reopen store and install/update.

### Admin Center stuck at startup

1. Open `System Health` in Guided Step 1.
2. Use `Retry Startup`.
3. Check transport diagnostics (`API Base`, `Last Path`, `Last Status`, `Last Error`).

### Discovery feels slow on large HA instances

1. Use domain filter + search.
2. Use paged explorer results.
3. Run `Refresh Discovery Cache` and wait for stage completion.

### Deploy blocked

1. Run profile validation.
2. Resolve missing required mappings for enabled features.
3. Re-run deploy.

## Documentation

- `docs/admin-center.md`
- `docs/architecture.md`
- `docs/migration.md`
- `docs/release.md`
- `docs/handoff-context.md`
- `docs/entities-template.md`
- `docs/ha-element-framework.md`
