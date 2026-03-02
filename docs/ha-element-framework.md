# HA Element Framework

## Purpose
This framework standardizes how Home Assistant entities are brought into this ESPHome/LVGL app so new features can be added quickly without breaking existing pages.

## Contract
1. All HA IDs are substitution-driven (`entity_*`) and never hardcoded in runtime package logic.
2. Every new HA data point must expose:
   - substitution key
   - mirrored runtime ID (`sensor`, `text_sensor`, or `binary_sensor`)
   - UI binding label/widget ID
3. Unknown/unavailable values must degrade to `"--"` or fallback strings without conversion warnings.
4. Physical-unit values are normalized before rendering and then converted to app-selected units for display.

## Source Priority Pattern
Use this order for robust adapters:
1. Dedicated HA sensor entity (`sensor.*`) if configured.
2. `weather.*` / `climate.*` attributes as fallback.
3. Last valid cached runtime model value.
4. Placeholder text (`"--"`).

## Units Pattern
1. Persisted app-wide unit selector:
   - `app_units_mode` (`0 imperial`, `1 metric`)
   - `app_units_initialized`
2. First-boot default from HA:
   - `entity_ha_unit_system` -> `sensor.unit_system`
3. User override in Settings persists and becomes authoritative.

## Adding a New HA Element (Checklist)
1. Add substitution key in:
   - `esphome/packages/ha_entities.yaml`
   - install/template files
2. Add mirror runtime ID in `ha_entities.yaml`.
3. Add/update normalization logic in the owning UI package (for weather: `weather_update_model`).
4. Add/update UI label/widget IDs.
5. Update docs:
   - `docs/entities-template.md`
   - `docs/handoff-context.md`
   - `docs/release.md`

## Template Pack
Use reusable snippets under:
- `esphome/templates/ha-elements/`

These include patterns for sensor/text/binary mirrors and action services.
