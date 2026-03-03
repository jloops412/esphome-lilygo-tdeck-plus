# Handoff Context

## Pass summary

This pass delivered the `v0.25.2` stabilization unblock focused on Step 1 onboarding reliability and Step 6 deploy reliability.

### Completed

1. Bumped add-on/runtime/install defaults to `0.25.2` / `v0.25.2`.
2. Added grouped onboarding candidate source reporting in `GET /api/onboarding/candidates`.
3. Added manual recovery probes:
   - `POST /api/onboarding/probe_entity`
   - `POST /api/onboarding/probe_host`
4. Added provisioning capability endpoint:
   - `GET /api/onboarding/provisioning_modes`
5. Added guided deploy safety and remediation endpoints:
   - `POST /api/deploy/preflight`
   - `POST /api/deploy/remediate`
   - `GET /api/deploy/last_run`
6. Added guided preflight token enforcement in `POST /api/deploy/run`.
7. Added required binding inference/reporting and generated bridge debug output:
   - `generated/bindings.report.yaml`
8. Added richer firmware workflow diagnostics model (`attempt_matrix`, selected service refs, fallback reason, next steps).
9. Updated guided frontend for probe controls, preflight/remediation actions, and last-run visibility.
10. Removed legacy non-public install directory from the public branch.

## Files changed in this pass

- `README.md`
- `docs/admin-center.md`
- `docs/migration.md`
- `docs/release.md`
- `docs/handoff-context.md`
- `docs/entities-template.md`
- `tdeck_admin_center/README.md`
- `tdeck_admin_center/Dockerfile`
- `tdeck_admin_center/config.yaml`
- `tdeck_admin_center/rootfs/app/main.py`
- `tdeck_admin_center/rootfs/app/static/app.js`
- `tdeck_admin_center/rootfs/app/static/index.html`
- `esphome/install/entity-overrides.template.yaml`
- `esphome/install/lilygo-tdeck-plus-install-lvgl-template.yaml`
- `esphome/install/lilygo-tdeck-plus-install-lvgl.yaml`
- `esphome/install/lilygo-tdeck-plus-install.yaml`
- `esphome/packages/ha_entities.yaml`
- removed: legacy non-public install directory

## Validation performed

1. `python -m py_compile tdeck_admin_center/rootfs/app/main.py` passed.
2. `python tdeck_admin_center/tools/check_js_syntax.py tdeck_admin_center/rootfs/app/static/app.js` passed.
3. Flask test-client smoke requests passed for:
   - `/api/health`
   - `/api/onboarding/candidates`
   - `/api/onboarding/provisioning_modes`
   - `/api/onboarding/probe_entity`
   - `/api/onboarding/probe_host`
   - `/api/deploy/preflight`
   - `/api/deploy/last_run`

## Known constraints / next pass priorities

1. Firmware runtime still includes transition slot-era compatibility paths; typed model is canonical on Admin Center side.
2. Continue Step 3/4/5 usability hardening (typed mapping templates, guided theme/layout defaults).
3. Continue legacy import scoring improvements for unusual ESPHome naming patterns.
4. Add deeper end-to-end install checks for app-first first-flash USB fallback guidance.
