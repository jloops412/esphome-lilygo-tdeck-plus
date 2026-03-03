# Handoff Context

## Scope Completed (This Pass)

This pass implements the `v0.23.1` startup recovery hotfix and ingress/cache hardening for Admin Center:

1. fixed frontend bootstrap syntax regression in `ensureCollections()` (missing `);`)
2. added explicit startup state model in frontend (`booting`, `ready`, `error`)
3. added startup error banner with actionable diagnostics and `Retry Startup` action
4. added versioned static asset loading in `index.html` (`app.js?v=...`, `styles.css?v=...`)
5. added script-load failure fallback banner (`onerror`) for frontend asset failures
6. added backend index no-cache semantics and cache-safe static asset headers
7. added health metadata fields for startup diagnostics:
   - `frontend_asset_version`
   - `ingress_expected_prefix`
8. bumped add-on metadata to `0.23.1`
9. added local JS syntax gate script (`tdeck_admin_center/tools/check_js_syntax.py`)

## Key Backend Changes

File:
- `tdeck_admin_center/rootfs/app/main.py`

Highlights:

1. version defaults bumped:
   - `ADDON_VERSION` fallback -> `0.23.1`
   - `DEFAULT_APP_RELEASE_VERSION` fallback -> `v0.23.1`
2. `/api/health` expanded with:
   - `frontend_asset_version`
   - `ingress_expected_prefix`
3. root/static routing hardened:
   - `index.html` rendered dynamically with `__ASSET_VERSION__` and `__INGRESS_EXPECTED_PREFIX__`
   - index responses use no-cache headers
   - static assets use long-lived cache headers (safe with versioned query strings)

## Key Frontend Changes

Files:
- `tdeck_admin_center/rootfs/app/static/index.html`
- `tdeck_admin_center/rootfs/app/static/app.js`
- `tdeck_admin_center/rootfs/app/static/styles.css`

Highlights:

1. fixed `ensureCollections()` parse break.
2. startup panel now includes:
   - `startup_state_lbl`
   - `startup_error_lbl`
   - `retry_startup_btn`
3. bootstrap flow now:
   - sets startup state to `booting`
   - surfaces explicit startup errors with path/status/base context
   - transitions to `ready` or `error` deterministically
4. transport fallback candidates now include backend ingress hint.
5. startup and transport diagnostics remain visible through `System Health`.

## New Validation Tool

File:
- `tdeck_admin_center/tools/check_js_syntax.py`

Behavior:

1. syntax-checks JS files using:
   - `node --check` when Node.js is available
   - QuickJS parse-only fallback when Node.js is unavailable
   - Esprima as secondary fallback
2. exits non-zero on syntax failure and is intended as a release gate.

## Manifest/Version

Files:
- `tdeck_admin_center/config.yaml`
- `tdeck_admin_center/Dockerfile`

Changes:

1. add-on manifest version: `0.23.1`
2. Docker build arg default: `BUILD_VERSION=0.23.1`

## Docs Updated

1. `README.md`
2. `docs/admin-center.md`
3. `docs/release.md`
4. `docs/handoff-context.md`
5. `tdeck_admin_center/README.md`

## Validation Run

1. `python -m py_compile tdeck_admin_center/rootfs/app/main.py` passed.
2. `python tdeck_admin_center/tools/check_js_syntax.py tdeck_admin_center/rootfs/app/static/app.js` passed (QuickJS parser).
3. Python import smoke passed for `main.py` route registration.

## Not Run Here

1. Live HA Supervisor install/update cycle to verify new add-on card version propagation.
2. Browser console inspection inside HA Ingress on target HA instance.
3. Physical device firmware compile/flash path in this pass.

## Immediate Next Steps

1. validate ingress startup on HA with stale-cache history to confirm no stuck `Initializing...` path.
2. continue Guided UX simplification pass for first-run mapping/deploy clarity.
3. continue firmware modular UI extraction from monolithic `ui_lvgl.yaml` while preserving reliability paths.
