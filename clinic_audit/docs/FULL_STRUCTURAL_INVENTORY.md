# FULL STRUCTURAL INVENTORY — HARD GATE 4

## Authoritative evidence
- `clinic.audit.event`
- `clinic.audit.event.line`

## Governance
- `clinic.audit.policy`
- `clinic.audit.review`
- `clinic.audit.review.tag`
- `clinic.audit.review.line`
- `clinic.audit.verification`

## Legacy compatibility
- `clinic.audit.log`
- `clinic.audit.log.line`

## Abstract/runtime services
- `clinic.audit.service`
- `clinic.audit.registry.hook`

## Transient tools
- `clinic.audit.evidence.export.wizard`
- `clinic.audit.legacy.import.wizard`
- `res.config.settings` extension

## Cross-addon coverage
- Fixed catalog: 358 upstream persistent ClinicOne models discovered from addons #1–#37.
- Missing/uninstalled models are skipped safely at registry-hook time.
- No runtime model name/domain is accepted from an external API caller.
