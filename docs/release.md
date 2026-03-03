# Release Notes

## Current

- Add-on manifest version: `0.25.2`
- Default app release version: `v0.25.2`
- Workspace/profile schema: `5.0`

## v0.25.2 Onboarding + Deploy Hard Unblock

### Onboarding reliability

1. Upgraded `GET /api/onboarding/candidates` to return grouped candidates by source:
   - `device_registry_esphome`
   - `update_entity_pattern`
   - `app_version_sensor_pattern`
   - `entity_registry_linked`
2. Added manual probe endpoints for missed legacy nodes:
   - `POST /api/onboarding/probe_entity`
   - `POST /api/onboarding/probe_host`
3. Added provisioning capability endpoint:
   - `GET /api/onboarding/provisioning_modes`
4. Added richer import/verify payloads with recommended import profile and provisioning modes.

### Guided deploy reliability

1. Added preflight endpoint:
   - `POST /api/deploy/preflight`
2. Added safe auto-remediation endpoint:
   - `POST /api/deploy/remediate`
3. Added deploy run diagnostics endpoint:
   - `GET /api/deploy/last_run`
4. Added guided preflight token gating in `POST /api/deploy/run` to prevent unsafe launch from invalid state.

### Validation and mapping bridges

1. Added required-binding inference/reporting for typed instances.
2. Added generated debug artifact:
   - `generated/bindings.report.yaml`
3. Added richer firmware workflow result model fields:
   - `selected_service_refs`
   - `attempt_matrix`
   - `manual_fallback_reason`
   - `next_steps`

### Metadata/version alignment

1. Updated add-on and Docker build metadata to `0.25.2`.
2. Updated install template defaults to `app_release_version: v0.25.2`.

## v0.25.1 Guided UX + Onboarding Recovery

### Onboarding reliability

1. Added hybrid candidate enrichment from HA device registry for ESPHome nodes.
2. Added manual candidate fallback path for `verify_candidate` and `import_existing`.
3. Added stronger candidate diagnostics and confidence reporting.

### Guided Step 3 usability

1. Added device-scoped entity suggestion workflow in typed element manager.
2. Added scope selector (`active`, `all`, detected node slug) for inline combobox suggestions.
3. Increased suggestion depth and ranking visibility in dropdown labels.

### Runtime constraints and limits

1. Expanded slot-runtime cap limits for generated compatibility paths:
   - lights cap max `48`, page size max `8`
   - cameras cap max `16`, page size max `6`

### Public hygiene

1. Removed non-public wording from user-facing docs.
2. Kept only unavoidable repository URL references required by add-on/install metadata.

## v0.25.0 Public-Safe Reboot

### Public hygiene

1. Removed legacy install profile content from tracked branch.
2. Kept only unavoidable repository URL references required by add-on/install metadata.

### Admin Center platform upgrades

1. Added onboarding APIs and Guided actions:
   - start new device workflow
   - import existing ESPHome node
   - migrate to managed files
2. Added typed catalog APIs and typed instance CRUD/bulk APIs.
3. Added page-layout API aliases for page builder workflows.
4. Added deploy orchestrator endpoint:
   - `POST /api/deploy/run`

### Schema/model upgrades

1. Workspace/profile schema bumped to `5.0`.
2. Added canonical typed model fields:
   - `type_registry`
   - `entity_instances`
   - `page_layouts`
   - `deployment_profile`
3. Retained compatibility normalization from older schema payloads.

### Managed contract upgrades

1. Added managed typed metadata artifacts:
   - `generated/types.registry.yaml`
   - `generated/entities.instances.yaml`
   - `generated/layout.pages.yaml`
   - `generated/theme.tokens.yaml`
2. Added these files to backup/restore manifest coverage.
3. Kept compile path safe by including only ESPHome-schema-safe generated artifacts in install packages.

### Frontend upgrades

1. Guided Step 1 now exposes app-first + import onboarding controls.
2. Guided Step 3 now includes typed element manager with inline smart entity combobox suggestions.
3. Guided deploy now runs the consolidated deploy orchestrator flow.
4. Startup now fetches onboarding node status during bootstrap.

### Metadata/version alignment

1. Updated add-on and Docker build metadata to `0.25.0`.
2. Updated install template defaults to `app_release_version: v0.25.0`.

## Validation gates executed

1. Python compile gate for backend (`main.py`) passes.
2. JS syntax gate (`check_js_syntax.py`) passes.
3. Flask test-client smoke calls pass for onboarding/catalog/instances/layout/deploy APIs.
