# Private Entity Mapping Template

Use this pattern to keep your personal Home Assistant entity IDs out of Git.

## How to use

1. Keep repo files public-safe (no real entity IDs committed).
2. In your local HA/ESPHome config, add substitution overrides.
3. Never commit local private overrides to GitHub.

## Copy/Paste Block

Add this block to your local install YAML (`lilygotdeckplus.yaml`) and set your real IDs:

```yaml
substitutions:
  entity_light_foyer: "light.replace_me_foyer"
  entity_light_vanity: "light.replace_me_vanity"
  entity_light_bedroom: "light.replace_me_bedroom"
  entity_light_hall: "light.replace_me_hall"
  entity_light_office: "light.replace_me_office"
  entity_light_upstairs: "light.replace_me_upstairs"

  entity_wx_main: "weather.replace_me"
  entity_wx_condition_sensor: "sensor.replace_me_weather_condition"
  entity_wx_weather_sensor: "sensor.replace_me_weather_text"
  entity_wx_temp_sensor: "sensor.replace_me_weather_temperature"
  entity_wx_feels_sensor: "sensor.replace_me_weather_feels_like"
  entity_wx_humidity_sensor: "sensor.replace_me_weather_humidity"
  entity_wx_clouds_sensor: "sensor.replace_me_weather_clouds"
  entity_wx_pressure_sensor: "sensor.replace_me_weather_pressure"
  entity_wx_uv_sensor: "sensor.replace_me_weather_uv"
  entity_wx_visibility_sensor: "sensor.replace_me_weather_visibility"
  entity_wx_wind_speed_sensor: "sensor.replace_me_weather_wind_speed"

  entity_word_of_day_sensor: "sensor.replace_me_word_of_day"
  entity_quote_of_hour_sensor: "sensor.replace_me_quote_of_hour"
  entity_feed_bbc: "event.replace_me_bbc"
  entity_feed_dc: "event.replace_me_dc"
  entity_feed_loudoun: "event.replace_me_loudoun"

  entity_sensi_climate: "climate.replace_me"
  entity_sensi_temperature_sensor: "sensor.replace_me_sensi_temperature"
  entity_sensi_humidity_sensor: "sensor.replace_me_sensi_humidity"
  entity_sensi_auto_cool_number: "number.replace_me_sensi_auto_cool"
  entity_sensi_auto_heat_number: "number.replace_me_sensi_auto_heat"
  entity_sensi_humidity_offset_number: "number.replace_me_sensi_humidity_offset"
  entity_sensi_temperature_offset_number: "number.replace_me_sensi_temperature_offset"
  entity_sensi_aux_heat_switch: "switch.replace_me_sensi_aux_heat"
  entity_sensi_display_humidity_switch: "switch.replace_me_sensi_display_humidity"
  entity_sensi_display_time_switch: "switch.replace_me_sensi_display_time"
  entity_sensi_fan_support_switch: "switch.replace_me_sensi_fan_support"
  entity_sensi_humidification_switch: "switch.replace_me_sensi_humidification"
  entity_sensi_keypad_lockout_switch: "switch.replace_me_sensi_keypad_lockout"
```

## Notes

1. This repo now uses substitution tokens for HA entity IDs in package files.
2. If substitutions are not overridden locally, the config will compile but controls will target placeholder entities.
3. Keep local/private files outside Git or under ignored paths.
