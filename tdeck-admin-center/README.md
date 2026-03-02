# T-Deck Admin Center Add-on

Home Assistant add-on (Ingress) for:

1. discovering entities from your HA instance
2. generating a drop-in T-Deck install YAML
3. generating substitutions/overrides YAML

## Features in v1

- entity discovery by domain/search
- install YAML generation with package pin support
- overrides block generation
- camera/light slot mapping helpers

## Scope

This v1 add-on intentionally does **generate/export only**.  
It does not auto-overwrite files in `/config/esphome`.
