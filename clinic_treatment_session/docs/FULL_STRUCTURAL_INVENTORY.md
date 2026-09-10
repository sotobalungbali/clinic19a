
# Full Structural Inventory

## Owned persistent models
- `clinic.treatment.session`
- `clinic.treatment.session.line`
- `clinic.treatment.session.stage`

## Extended models
- `booking.booking`
- `booking.room`
- `res.partner`
- `hr.employee`
- `clinic.patient`
- `clinic.doctor`
- `clinic.encounter`
- `clinic.branch`
- `clinic.referral`
- `res.config.settings`

## Runtime-loaded source
Core models, enterprise overlays and external-model extensions imported by
`models/__init__.py` and `models/extensions/__init__.py`.

## Manifest-loaded
Security, ACL, sequences, stage bootstrap, mail template, cron, operational
views, configuration view, menus and optional UI bridge.

## Optional / tool / test
Tests, source guardrail, docs and static description.

## Present but not imported
`models/models.py`, generic historical scaffold.

## Backup / excluded
No digit-prefixed backup basename is packaged.
