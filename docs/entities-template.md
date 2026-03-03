# Entity Mapping Template

Use `esphome/install/entity-overrides.template.yaml` as the baseline for local substitutions.

## Recommended workflow

1. Use Admin Center Guided Step 3 to map typed entities.
2. Deploy through managed files.
3. Use this template only when you need manual overrides.

## Minimum local block example

```yaml
substitutions:
  app_release_channel: "stable"
  app_release_version: "v0.25.2"

  # Weather
  entity_wx_main: "weather.replace_me"
  entity_wx_temp_sensor: "sensor.replace_me_weather_temperature"

  # Climate
  entity_sensi_climate: "climate.replace_me"
  entity_sensi_temperature_sensor: "sensor.replace_me_sensi_temperature"

  # Optional camera support
  camera_slot_count: "0"
  camera_slot_1_entity: "camera.replace_me_1"
  ha_base_url: "http://homeassistant.local:8123"
```

## Notes

1. Public defaults stay generic (`replace_me_*`).
2. Legacy slot substitutions still exist for transition firmware compatibility.
3. Typed `entity_instances` in Admin Center are canonical for new deployments.
4. If you deploy from Admin Center, generated managed files are preferred over manual edits.
