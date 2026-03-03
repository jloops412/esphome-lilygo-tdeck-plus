# Migration Guide

## Target baseline

- Admin Center `0.25.2`
- Schema `5.0`
- App release default `v0.25.2`

## What changed

1. Canonical config model moved to typed `entity_instances[]`.
2. Onboarding now supports:
   - `Start New T-Deck`
   - `Import Existing ESPHome Node`
3. Deploy orchestration consolidated under `POST /api/deploy/run`.
4. Generated typed metadata artifacts are now managed and backed up.

## Automatic normalization

Existing workspaces/profiles from older schema versions are normalized when loaded.

Compatibility behavior:

- Legacy slot/collection data is preserved for transition generation paths.
- Typed instances are generated from legacy rows when missing.

## Recommended migration path

1. Update add-on to `0.25.2`.
2. Load existing workspace/profile.
3. Open Guided Step 3 and review typed instances.
4. Run Guided Step 6 `Preflight`.
5. Use `Auto-Remediate` if preflight suggests supported fixes.
6. Run deploy with preview + backup.
7. Confirm on-device behavior.

## Reflash from scratch path

1. In Guided Step 1, click `Start New T-Deck`.
2. Add required typed instances.
3. Deploy.
4. First flash via USB if OTA path is unavailable.

## Import existing node path

1. Scan nodes in Guided Step 1.
2. Import selected node.
3. Migrate to managed files.
4. Validate + deploy.

If auto-detection misses your node, use manual fallback in Step 1 with device slug or firmware update entity ID.
You can also use `Probe Entity` and `Probe Host` to bootstrap legacy imports.

## Rollback

1. Open backups list.
2. Select snapshot for the device.
3. Restore managed files.
4. Re-run firmware install.

Backup scope remains managed files under `/config/esphome/tdeck` only.
