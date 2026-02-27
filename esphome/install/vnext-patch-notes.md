# VNext Patch Notes (against stable baseline)

Apply these edits to the known-good stable baseline YAML.

## 1) GPS support

Add substitutions:

```yaml
substitutions:
  gps_rx_pin: "44"
  gps_tx_pin: "43"
```

Add UART:

```yaml
uart:
  id: gps_uart
  rx_pin: ${gps_rx_pin}
  tx_pin: ${gps_tx_pin}
  baud_rate: 9600
```

Add GPS entities:

```yaml
gps:
  latitude:
    name: "${friendly_name} GPS Latitude"
  longitude:
    name: "${friendly_name} GPS Longitude"
  altitude:
    name: "${friendly_name} GPS Altitude"
  speed:
    name: "${friendly_name} GPS Speed"
  course:
    name: "${friendly_name} GPS Course"
  satellites:
    name: "${friendly_name} GPS Satellites"
  hdop:
    name: "${friendly_name} GPS HDOP"
  update_interval: 5s
```

## 2) Keyboard backlight on wake

In `script -> wake_display -> then`, add:

```yaml
      - script.execute: kb_backlight_apply
```

In keyboard read interval lambda, inside:

```cpp
if (id(screensaver_active)) {
```

add:

```cpp
id(kb_backlight_apply).execute();
```

after `call.perform();`.

## 3) Feed page cleanup

Remove settings entry from feed page tile/action logic.
Keep slot 6 as content action (e.g., open quote again or no-op), not a settings jump.
