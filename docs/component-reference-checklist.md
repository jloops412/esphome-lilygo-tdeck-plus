# Component Reference Checklist

Use this checklist before and during feature implementation.

## Mandatory References
1. ESPHome components index:
   - https://esphome.io/components/
2. LVGL docs:
   - https://docs.lvgl.io/master/

## Implementation Checklist
1. Confirm component syntax/constraints against ESPHome docs (current release behavior).
2. Confirm widget/event semantics against LVGL docs before wiring interactions.
3. Prefer `on_release` commits for expensive/networked actions.
4. Add guard globals for programmatic UI sync paths to avoid event feedback loops.
5. Add unknown/unavailable handling for HA-derived fields.
6. Keep install contract as one drop-in YAML with package substitutions.
7. Update docs/handoff in same pass.

## Validation Checklist
1. No unresolved IDs across packages.
2. No incompatible options for selected component platform/version.
3. No recurring script contention warnings during idle.
4. UI still responsive with periodic updates.
