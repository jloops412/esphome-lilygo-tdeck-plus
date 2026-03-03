# Architecture

## Topology

This project has two coordinated surfaces:

1. Firmware packages (`esphome/packages/*`) for on-device LVGL UI + HA actions
2. HA add-on (`tdeck_admin_center`) for discovery, mapping, generation, and deployment

## Admin Center architecture

### Data model (schema 5.0)

- `device_workspace.devices[]`
- `type_registry`
- `entity_instances[]`
- `page_layouts[]`
- `deployment_profile`

Legacy slot/collection keys are normalized for migration only.

### Managed outputs

Per device under `/config/esphome/tdeck/<device_slug>/`:

- `tdeck-install.yaml`
- `tdeck-overrides.yaml`
- generated compile-safe artifacts used by firmware include chain
- generated typed metadata artifacts retained for Admin Center/runtime metadata and backup

### Deployment safety

All writes are scoped to `/config/esphome/tdeck` and guarded by:

1. validation
2. preview diff
3. backup snapshot
4. transaction lock per device

## Firmware architecture

Current firmware remains LVGL-first with modular behavior implemented through packages and generated include hooks.

Reliability paths retained:

- climate +/- deterministic adjust/commit
- thermostat ack/resync workflow
- screensaver idle clock + activity source filtering
- strict ALT-only shortcut behavior

## Discovery and mapping

Discovery is job-based and supports large HA instances with:

- cached state indexing
- filtering/pagination
- explicit progress and failure surfaces

Mapping uses typed instances as canonical representation and can still generate compatibility substitutions for transition firmware paths.
