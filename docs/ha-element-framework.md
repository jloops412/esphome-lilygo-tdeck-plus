# HA Element Framework

## Purpose

Define a stable, typed contract between Home Assistant entities, Admin Center configuration, and firmware rendering/actions.

## Core rules

1. Entity IDs are substitution/config driven, never hardcoded in runtime logic.
2. Canonical model is typed `entity_instances` (schema `5.0`).
3. Unknown/unavailable HA values must degrade gracefully (`--` / fallback text).
4. Generated outputs must remain compile-safe for ESPHome.
5. Public defaults remain generic placeholders.

## Typed model

Primary objects:

- `type_registry`
- `entity_instances[]`
- `page_layouts[]`
- `deployment_profile`

Supported core types:

1. light
2. switch
3. climate
4. weather
5. camera
6. cover
7. lock
8. fan
9. media_player
10. sensor

## Source priority pattern

For resilient adapters:

1. dedicated mapped entity
2. related HA attributes fallback
3. last valid cached model
4. placeholder

## Update metadata pattern

Firmware publishes:

- `app_release_channel`
- `app_release_version`

`esphome.project.version` is derived from `${app_release_version}`.

## Generated contract

Managed generated outputs include:

- compile-safe substitution artifacts used by firmware include chain
- typed metadata artifacts retained for Admin Center and backup/restore

Typed metadata files are intentionally not injected directly as ESPHome package roots.

## Add-a-type checklist

1. Add registry entry and domains/control contract.
2. Add discovery ranking and validation rules.
3. Add instance-to-firmware mapping behavior.
4. Add icon/action/state rendering contract.
5. Add docs + migration notes.
