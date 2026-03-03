# Handoff Context

## Pass summary

This pass delivered a public-safe cleanup and schema/model pivot toward typed HA elements.

### Completed

1. Removed tracked private install profile files from public branch.
2. Removed private profile wording from public docs.
3. Upgraded Admin Center schema defaults to `5.0`.
4. Added onboarding API set (`start_new`, `import_existing`, `migrate_to_managed`, node scan).
5. Added typed catalog and typed instance API set.
6. Added page-layout API aliases and deploy orchestrator endpoint.
7. Added typed managed artifacts and backup/restore coverage.
8. Fixed compile-safety issue: typed metadata files are no longer injected as ESPHome packages.
9. Guided deploy now uses consolidated `POST /api/deploy/run` pipeline.
10. Version baseline aligned to add-on `0.25.0` and app `v0.25.0`.

## Files changed in this pass

- `tdeck_admin_center/rootfs/app/main.py`
- `tdeck_admin_center/rootfs/app/static/app.js`
- `tdeck_admin_center/rootfs/app/static/index.html`
- `tdeck_admin_center/config.yaml`
- `tdeck_admin_center/Dockerfile`
- `esphome/install/*.yaml` templates
- `esphome/packages/ha_entities.yaml`
- `repository.yaml`
- public docs (`README.md`, `docs/*`)

## Known transition constraints

1. Firmware UI is still primarily slot-era internally; typed model is canonical in Admin Center and normalized back into compatibility substitutions for current firmware.
2. Typed generated metadata artifacts are stored/managed but intentionally excluded from package include compile path.
3. Legacy collection UI remains visible for transition support.

## Recommended next implementation gates

1. Firmware modularization into typed component includes (replace slot-primary runtime logic).
2. Page builder V2 with typed widget placement as the compile-time authority.
3. End-to-end compile validation from generated managed files in CI.
4. Expanded autodetect ranking and conflict remediation UX for very large HA instances.
