# LilyGO T-Deck Plus Home Assistant Controller

Public-ready ESPHome + LVGL firmware for LilyGO T-Deck Plus (ESP32-S3), built around:

- stable custom MIPI display path
- GT911 touch + 9-point calibration
- trackball + keyboard navigation
- Home Assistant entity control
- modular package architecture with one install YAML

## Install (One YAML, Public)

Use:

- `esphome/install/lilygo-tdeck-plus-install-lvgl.yaml`

This file is the public drop-in entrypoint and pulls modular package files from this repo.
By default it tracks `ref: "stable"` so users receive tested release updates without changing their entity mappings.

### Quick Start

1. Copy `esphome/install/lilygo-tdeck-plus-install-lvgl.yaml` into your HA ESPHome instance.
2. Replace substitution placeholders (or paste values from `esphome/install/entity-overrides.template.yaml`).
3. Keep Wi-Fi secrets in HA `secrets.yaml`.
4. Compile and flash (USB first flash, OTA after).

### Required substitution groups

1. Lights:
   - `light_slot_count`, `light_slot_#_name`, `light_slot_#_entity`
2. Weather:
   - `entity_wx_main` and related weather sensors
3. Climate:
   - `entity_sensi_*` mappings
4. Optional cameras:
   - `camera_slot_count`, `camera_slot_#_entity`, `ha_base_url`
   - optional runtime paging keys: `generated_camera_slot_cap`, `generated_camera_page_size`
5. App update metadata:
   - `app_release_channel` (default `stable`)
   - `app_release_version` (set to current release tag)

### Common install errors

1. `couldn't find remote ref`:
   - update `ref:` to a valid pushed tag/branch
2. `Component not found` in packages:
   - ensure `packages` is list-form with `url/ref/files`
3. Hidden camera UI:
   - `camera_slot_count: "0"` intentionally hides cameras
4. Shortcuts not firing:
   - shortcuts are strict `ALT+key`

## Public vs Personal Profiles

Public defaults are generic and safe.

- Public install/template:
  - `esphome/install/lilygo-tdeck-plus-install-lvgl.yaml`
  - `esphome/install/lilygo-tdeck-plus-install-lvgl-template.yaml`
  - `esphome/install/entity-overrides.template.yaml`

Personal mappings live separately:

- `esphome/install/personal/jloops/lilygo-tdeck-plus-install-lvgl.yaml`
- `esphome/install/personal/jloops/entity-overrides.yaml`

## Features

- Home launcher with dynamic weather icon
- Modular lights controller (paged virtual slots, up to 24)
- Color Studio page for light color/kelvin controls
- Weather overview + scroll-safe details page
- Climate Controller + Climate Tools pages
- Reader page (news/word/quote feeds)
- Settings with category panels
- Theme Studio (token-based swatch editor, 3 palettes)
- Optional camera snapshots (paged virtual slots, up to 8, manual + auto refresh)
- Screensaver timeout + wake-source diagnostics
- Strict ALT-only keyboard shortcut model
- Admin Center `Guided` + `Advanced` dual-mode UX
- Dynamic light/camera collections (add/remove/reorder)
- Layout Builder (`Grid + Sections`) for all main pages
- Theme Studio with palettes + color picker + live contrast preview

## Cameras

Camera support is optional and inert by default (`camera_slot_count: "0"`).

Enable by setting substitutions:

- `camera_slot_count: "1"` to `"8"`
- `camera_slot_1_entity` ... `camera_slot_8_entity`
- optional paging: `generated_camera_page_size` (default `4`)
- `ha_base_url` (for `/local/...` image fetch)

Snapshot flow:

1. Device calls `camera.snapshot` in HA to `/config/www/tdeck/cam1.jpg` and `cam2.jpg`.
2. Device loads images via `${ha_base_url}/local/tdeck/camX.jpg?...`.
3. Auto-refresh interval is configurable (`camera_refresh_interval_s`, default `60`).
4. Camera diagnostics surface in `Settings -> Diag`.

## Admin Access

Firmware (on-device):

1. Settings page now includes direct admin hints:
   - `Device: http://<device-ip>`
   - `HA: Add-ons -> T-Deck Admin Center`
2. ESPHome web server (`web_server: version: 3`) exposes runtime entities.

Home Assistant add-on (Ingress):

1. Add this repo URL directly as an add-on repository.
2. Install `T-Deck Admin Center`.
3. Open Web UI from the add-on panel.
4. Use it to:
   - discover entities
   - run asynchronous discovery jobs with visible progress/error state
   - build mappings via profile wizard
   - manage multi-device workspaces
   - validate profile contracts
   - generate drop-in install YAML
   - generate overrides YAML
   - preview/apply managed config files directly under `/config/esphome/tdeck`
   - auto-snapshot backups and restore checkpoints
   - generate Home Assistant update-package YAML for app update button flow
   - run Guided flow (`Device -> Features -> Entities -> Theme -> Layout -> Deploy`)
   - use Advanced tabs for profile, update, and raw YAML workflows

Admin Center V6 (`0.24.0`) highlights:

1. Dashboard-first landing with action cards (`Connect Device`, `Map Entities`, `Theme`, `Layout`, `Deploy`, `Recover`).
2. Guided UX remains default; Advanced mode is still available for power users.
3. Dynamic entity collections now include:
   - `lights`
   - `cameras`
   - `weather_metrics`
   - `climate_controls`
   - `reader_feeds`
   - `system_entities`
4. Camera auto-detect onboarding added with scan/accept/ignore flows.
5. Workspace/profile schema moved to `4.1` with compatibility normalization.
6. Guided Step 3 rebuild:
   - inline smart entity comboboxes per row
   - add/remove/duplicate/reorder per row
   - bulk actions (`enable all`, `disable all`, `remove disabled`, `dedupe`)
   - atomic backend transaction path (`/api/entities/bulk_apply`)
7. Slot runtime controls exposed in Guided step:
   - `light_slot_cap` / `camera_slot_cap`
   - `light_page_size` / `camera_page_size`
   - one-click `Auto-Fit to Enabled Rows`
8. Firmware slot UX now uses paged virtual lists:
   - Lights page rows 1-6 + Prev/Next
   - Cameras page rows 1-4 + Prev/Next + detail preview
9. Managed generation now includes:
   - `generated/entities.generated.yaml`
   - `generated/theme.generated.yaml`
   - `generated/layout.generated.yaml`
   - `generated/pages/home.generated.yaml`
   - `generated/pages/lights.generated.yaml`
   - `generated/pages/weather.generated.yaml`
   - `generated/pages/climate.generated.yaml`
10. Apply, backup, and restore flows now preserve the expanded generated artifact set.
11. Firmware workflow still uses capability-based auto-detect + fallback with legacy-safe status handling.
12. Startup hotfix remains in place:
   - fixed frontend bootstrap syntax regression that caused stuck `Status loading... / Initializing...`
   - added explicit startup state (`booting/ready/error`) and retry button
   - added versioned static assets (`app.js?v=<version>`, `styles.css?v=<version>`) and no-cache index delivery

If HA says the repo is not valid or add-on build fails:

1. Remove the repo from Add-on Store repositories.
2. Restart Supervisor (`Settings -> System -> Restart Supervisor`).
3. Re-add: `https://github.com/jloops412/esphome-lilygo-tdeck-plus`
4. Confirm add-on appears as `T-Deck Admin Center` (`0.24.0`).
5. Install again, then open `Settings -> Add-ons -> T-Deck Admin Center -> Open Web UI`.

If build logs show `chmod: /run.sh: No such file or directory`, clear the repo cache with the same sequence above and retry install.

If entity loading looks stuck in the add-on UI:

1. Open `Overview` and check HA status.
2. Check the `Discovery` status line for running/failed job state.
3. Click `Refresh Discovery Cache` (starts forced discovery).
4. Wait for discovery to reach `completed`, `failed`, or `cancelled`.
5. Reset explorer filters (`domain=all`, clear search, page size 100).
6. Check stale-cache error text in the explorer meta line.

If HA still shows an old add-on version:

1. Confirm GitHub `main` has the new `tdeck_admin_center/config.yaml` version committed.
2. In HA Add-on Store: remove repo, restart Supervisor, re-add repo URL.
3. Reopen store and verify version `0.24.0`.

If the add-on UI is stuck at `Status loading... / Initializing...`:

1. Verify add-on version is `0.24.0` or newer.
2. Open the add-on via Ingress and click `Retry Startup`.
3. Check `System Health`:
   - `Transport base hint`
   - `Ingress expected prefix`
   - `Last Path` / `Last Status` in transport diagnostics
4. If stale frontend assets are suspected:
   - reopen the add-on page in a new tab
   - run Add-on Store cache refresh sequence (remove repo, restart Supervisor, re-add repo)

Ingress/API 404 recovery (fixed in `0.21.0`):

1. Admin Center now uses ingress-relative API transport (`api/...`) instead of absolute `/api/...`.
2. Overview shows transport diagnostics (`API Base`, `Last Path`, `Last Status`, `Last Error`).
3. If transport is failing, use `Refresh Health` and check `System Status` before retrying discovery/workflow actions.

Firmware workflow (auto-detect + fallback):

1. Open `Overview -> Firmware Workflow`.
2. Use:
   - `Backup + Auto Update` (recommended)
   - `Backup + Build/Install` (if ESPHome services are available)
   - `Install Only`
   - `Manual Next Steps` (fallback guidance)
3. Legacy firmware with no version sensor is surfaced as `unknown_legacy` (not a silent failure).
4. Backup scope remains managed files only:
   - `/config/esphome/tdeck/<device_slug>/tdeck-install.yaml`
   - `/config/esphome/tdeck/<device_slug>/tdeck-overrides.yaml`

Direct apply and backup flow:

1. Open `Generate` tab.
2. Click `Preview Apply` to inspect install/override diffs.
3. Click `Apply to Managed Files` to write:
   - `/config/esphome/tdeck/<device_slug>/tdeck-install.yaml`
   - `/config/esphome/tdeck/<device_slug>/tdeck-overrides.yaml`
4. Each apply creates a snapshot under:
   - `/config/esphome/tdeck/.backups/<device_slug>/<timestamp>/`
5. Use `Refresh Backups` and `Restore Selected Backup` to roll back.

Companion static generator (repo):

- `tools/admin-center/index.html`

## HA Update Button Flow

Goal: update firmware from HA without overwriting user mappings/settings.

1. Firmware publishes installed app metadata:
   - `sensor.<device>_app_version`
   - `sensor.<device>_app_channel`
2. Admin Center `Updates` tab fetches latest stable release from GitHub.
3. Admin Center generates a HA package YAML (save under your HA `packages` folder) that creates:
   - latest stable version sensor
   - template update entity (`update.tdeck_app_update_<device>`)
   - install action proxy to native ESPHome firmware updater (`update.<device>_firmware`)
4. Pressing update in HA triggers OTA via native ESPHome update entity.
5. User entity mappings and app settings remain intact because update runs from the user's existing ESPHome node config.
6. If the native updater entity is missing, enable the ESPHome firmware update entity in HA and re-run package generation.

## Architecture

Core packages:

- `esphome/packages/board_base.yaml`
- `esphome/packages/persistence_globals.yaml`
- `esphome/packages/ha_entities.yaml`
- `esphome/packages/ui_lvgl.yaml`
- `esphome/packages/display_mipi_lvgl.yaml`
- `esphome/packages/input_touch_gt911_lvgl.yaml`
- `esphome/packages/input_trackball_lvgl.yaml`
- `esphome/packages/input_keyboard_i2c_lvgl.yaml`

## Docs

- `docs/architecture.md`
- `docs/admin-center.md`
- `docs/cameras.md`
- `docs/migration.md`
- `docs/release.md`
- `docs/handoff-context.md`
- `docs/entities-template.md`
- `docs/ha-element-framework.md`
- `docs/component-reference-checklist.md`

## Process Contract

Every code pass updates:

1. code
2. docs
3. handoff report (`docs/handoff-context.md`)
