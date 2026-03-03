# Handoff Context

## Scope Completed (This Pass)

This pass implements the `v0.22.0` mega-upgrade focus for Admin Center usability and managed firmware customization:

1. add-on version bumped to `0.22.0`
2. Guided + Advanced dual-mode UI finished
3. dynamic light/camera collections fully wired in frontend
4. template catalog rendering/apply added (`/api/meta/templates`)
5. layout builder workflow wired:
   - load/edit/add/remove/reorder sections
   - validate/save/reset page actions
6. theme studio workflow wired:
   - palette loading
   - token color picker
   - preview/apply with contrast feedback
7. one-click guided deploy pipeline added:
   - validate -> preview -> apply -> firmware workflow
8. startup flow simplified to avoid heavy generation on boot
9. generated managed files made compile-safe and theme-effective:
   - removed risky generated inline lambda summaries
   - generated theme emits canonical `theme_token_*` substitutions

## Key Backend Changes

File:
- `tdeck_admin_center/rootfs/app/main.py`

Changes:

1. generated file builders updated:
   - `_build_generated_entities_yaml`
   - `_build_generated_theme_yaml`
   - `_build_generated_layout_yaml`
2. generated theme now writes canonical theme substitution keys so deployed firmware styling follows Admin Center theme apply.
3. generated entities/layout files now stay metadata/comment-only where appropriate for safer compile behavior.
4. schema/version constants remain:
   - add-on `0.22.0`
   - workspace schema `3.0`

## Key Frontend Changes

Files:
- `tdeck_admin_center/rootfs/app/static/index.html`
- `tdeck_admin_center/rootfs/app/static/app.js`
- `tdeck_admin_center/rootfs/app/static/styles.css`

Changes:

1. Guided flow completed with six practical steps.
2. Advanced mode now augments guided controls (does not hide primary configuration forms).
3. template domain/item selectors + apply workflow implemented.
4. dynamic collection table actions implemented (up/down/delete/enable/edit).
5. layout section editor implemented with per-row bounds clamping.
6. theme preview/apply flow implemented with live preview card and contrast metadata.
7. apply preview now includes generated-file diffs.
8. generate now emits install + overrides + generated entities/theme/layout outputs.
9. guided deploy action added (`Validate + Apply + Auto Deploy`).

## Manifest/Version

File:
- `tdeck_admin_center/config.yaml`

Change:

1. `version: "0.22.0"`

## Docs Updated

1. `README.md`
2. `docs/admin-center.md`
3. `docs/release.md`
4. `docs/handoff-context.md`
5. `tdeck_admin_center/README.md`

## Validation Run

1. `python -m py_compile tdeck_admin_center/rootfs/app/main.py` passed.
2. Flask test-client smoke passed:
   - `GET /api/health`
   - `GET /api/meta/contracts`
   - `GET /api/meta/templates`
   - `GET /api/theme/palettes`
   - `POST /api/theme/preview`
   - `POST /api/layout/validate`
   - `POST /api/generate/install`
   - `POST /api/apply/preview`

## Not Run Here

1. Full HA Supervisor add-on install/update cycle on a live HA instance.
2. Browser UX run-through through HA Ingress with real large-entity HA data.
3. Full ESPHome compile/flash from generated managed files on hardware.

## Immediate Next Steps

1. Run live ingress smoke with a large HA entity set to tune defaults for page size/search UX.
2. Add richer section templates in layout builder (header/content/footer presets by page type).
3. Extend dynamic collections beyond lights/cameras (reader feeds and custom chips).
4. Continue firmware modular include-hook rollout in ESPHome package docs and templates.
