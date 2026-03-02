# Handoff Context

## Repo state

- Branch: `main`
- Last released tag in docs/install before this pass: `v0.18.3-reliability-core`
- This pass is untagged local work pending validation/tag/push.

## Implemented in this pass

1. Reliability:
   - Added stale-touch guard support (`touch_last_ms` updates in touch handlers).
   - Climate adjust scripts switched to `mode: queued` for rapid tap reliability.
2. Camera feature:
   - Added camera substitutions and runtime globals.
   - Added `http_request` + `online_image` camera assets.
   - Added camera scripts (`build_urls`, snapshot trigger, refresh, page open/toggle).
   - Added `cameras_page` and `camera_detail_page`.
   - Added home camera launcher button (`home_cameras_btn`, auto-hidden when disabled).
   - Added keyboard shortcuts:
     - `Alt+5`: open Cameras
     - `Alt+6`: refresh cameras
3. UI safety/polish:
   - Added non-overlap long mode for weather detail lines.
   - Added `settings_diag_activity_lbl` and diagnostics updates.
4. Public/private profile split:
   - Public install file reset to generic defaults.
   - Personal mapping moved to:
     - `esphome/install/personal/jloops/lilygo-tdeck-plus-install-lvgl.yaml`
     - `esphome/install/personal/jloops/entity-overrides.yaml`
   - Removed `esphome/install/entity-overrides.jloops.yaml` from main install surface.
5. Admin center v1:
   - Added static generator app:
     - `tools/admin-center/index.html`
     - `tools/admin-center/app.js`
     - `tools/admin-center/styles.css`
     - `tools/admin-center/schema.json`
6. Docs refresh:
   - Rewrote README and core docs (`architecture`, `migration`, `release`).
   - Added `docs/cameras.md` and `docs/admin-center.md`.

## Known constraints

- Local environment here does not have `esphome` CLI, so no local compile gate was run in this pass.
- Keyboard backlight firmware control remains intentionally deferred (manual keyboard `Alt+B`).
- GPS fix behavior remains hardware/sky dependent.

## Next recommended steps

1. Run HA compile against updated package ref.
2. OTA flash and validate:
   - screensaver timeout behavior
   - climate `+/-` rapid taps
   - camera manual/auto refresh
3. Tag and pin release:
   - suggested tag `v0.19.0-ui-camera-admin-v1`
   - then set install YAML package `ref` to that tag.

