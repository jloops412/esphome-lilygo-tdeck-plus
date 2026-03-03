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
5. Public defaults must remain generic (`replace_me_*`); personal mappings stay under `esphome/install/personal/*`.

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

## Update Metadata Pattern

1. Firmware always publishes:
   - `app_release_channel`
   - `app_release_version`
2. `esphome.project.version` is set from `${app_release_version}`.
3. HA diagnostic text sensors expose installed app version/channel for template update workflows.

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

## Admin Center V2 Profile Contract

The HA add-on `T-Deck Admin Center` now generates config from a profile schema.

Top-level sections:
1. `schema_version`
2. `profile_name`
3. `device` (`name`, `friendly_name`, `git_ref`, `git_url`)
4. `features` (`lights`, `weather`, `climate`, `cameras`, `reader`, `gps`)
5. `slots` (`light_slot_count`, `camera_slot_count`, slot arrays)
6. `entities` (`entity_*` mappings)
7. `ui` (`ui_show_*`, `home_tile_show_*`)
8. `theme` (`theme_token_*`, `theme_border_width`, `theme_radius`, `theme_icon_mode`)
9. `settings` (camera and reliability knobs)

Generated outputs:
1. drop-in install YAML (`/api/generate/install`)
2. substitutions overrides YAML (`/api/generate/overrides`)

## Template Pack
Use reusable snippets under:
- `esphome/templates/ha-elements/`

These include patterns for sensor/text/binary mirrors, action services, weather adapters, and camera snapshot bridges.
