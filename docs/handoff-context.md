# Handoff Context

## Pass summary

This pass delivered onboarding reliability and guided UX improvements on top of the typed HA element model.

### Completed

1. Expanded onboarding candidate detection with HA device-registry ESPHome fallback.
2. Added manual fallback candidate generation for verify/import when detection misses legacy nodes.
3. Added Guided Step 3 device-scope selector for typed entity suggestions.
4. Extended suggestion payloads with device scope and stronger ranking labels.
5. Expanded compatibility slot-runtime limits (lights/cameras) for larger managed installs.
6. Removed remaining non-public wording from public docs.
7. Version baseline aligned to add-on `0.25.1` and app `v0.25.0`.

## Files changed in this pass

- `tdeck_admin_center/rootfs/app/main.py`
- `tdeck_admin_center/rootfs/app/static/app.js`
- `tdeck_admin_center/rootfs/app/static/index.html`
- `docs/release.md`
- `docs/handoff-context.md`

## Known transition constraints

1. Firmware UI is still compatibility-slot based internally; typed model is canonical in Admin Center and normalized into generated substitutions.
2. Typed generated metadata artifacts are stored/managed but intentionally excluded from package include compile path.
3. Legacy collection paths remain for transition support while Guided Step 3 uses typed instances.

## Recommended next implementation gates

1. Firmware modularization into typed component includes (replace slot-primary runtime logic).
2. Page builder V2 with typed widget placement as the compile-time authority.
3. End-to-end compile validation from generated managed files in CI.
4. Expanded autodetect ranking and conflict remediation UX for very large HA instances.
