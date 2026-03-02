# Release Notes

## Current baseline tag

- `v0.19.1-select-template-hotfix`

## Unreleased (current `main`)

- strict ALT shortcut reliability fix in keyboard parser (removed ALT path early-return)
- ALT diagnostics surfaced in settings diagnostics
- home header overlap reduction and tighter status text
- settings system panel now includes concise admin access instructions
- settings diagnostics expanded with camera and shortcut status lines
- camera refresh diagnostics strings added:
  - `camera_refresh_status_text`
  - `camera_last_snapshot_result`
- Theme Studio rebuilt to swatch-based workflow:
  - RGB sliders removed
  - 3 palette pages x 24 swatches
  - apply/revert by token
  - border/radius/icon controls retained
- HA add-on admin center v1 added:
  - `repository.yaml`
  - `tdeck-admin-center/*`
  - Ingress UI + discovery + YAML generation APIs
- HA add-on repo/install compatibility fix:
  - `tdeck-admin-center/config.yaml` removed `map` entirely (v1 is generate/export only)
  - removed `ports`/`i386` for cleaner ingress-only compatibility
  - `tdeck-admin-center/build.yaml` now uses HA `*-base:3.20`
  - `tdeck-admin-center/Dockerfile` now installs Python runtime on base image
- docs and README refreshed for public install/admin/camera behavior

## Tagging process

1. Merge to `main`.
2. Create new tag (recommended next: `v0.20.0-admin-addon-theme-swatch-camera-pass`).
3. Update install YAML `ref` to the release tag.
4. Publish release summary with migration notes.
