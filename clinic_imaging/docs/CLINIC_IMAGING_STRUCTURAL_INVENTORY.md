# ClinicOne — clinic_imaging Structural Inventory

Persistent custom models: **43**

| Model | Fields | Methods | Mail/Activity |
|---|---:|---:|---|
| `clinical.imaging.type.tag` | 5 | 0 | No |
| `clinical.imaging.type` | 33 | 10 | Yes |
| `clinical.imaging.protocol` | 9 | 1 | No |
| `clinical.imaging.type.prep` | 8 | 1 | No |
| `clinical.imaging.type.contra` | 7 | 0 | No |
| `clinical.imaging.device` | 40 | 21 | Yes |
| `clinical.imaging.device.downtime` | 12 | 6 | No |
| `clinical.imaging.device.calibration` | 11 | 1 | No |
| `clinical.imaging.device.connectivity` | 9 | 2 | No |
| `clinical.imaging` | 49 | 43 | Yes |
| `clinical.imaging.study` | 38 | 23 | Yes |
| `clinical.imaging.study.note` | 5 | 0 | No |
| `clinical.imaging.series` | 54 | 24 | Yes |
| `clinical.imaging.series.param` | 7 | 0 | No |
| `clinical.imaging.series.dose` | 7 | 1 | No |
| `clinical.imaging.image.tag` | 5 | 0 | No |
| `clinical.imaging.image` | 53 | 25 | Yes |
| `clinical.imaging.image.annotation` | 14 | 4 | No |
| `clinical.imaging.finding.tag` | 5 | 0 | No |
| `clinical.imaging.finding` | 48 | 16 | Yes |
| `clinical.imaging.finding.measure` | 10 | 1 | No |
| `clinical.imaging.report.template` | 26 | 11 | Yes |
| `clinical.imaging.report.template.section` | 8 | 1 | No |
| `clinical.imaging.report.template.variable` | 7 | 0 | No |
| `clinical.imaging.report.template.asset` | 6 | 0 | No |
| `clinical.imaging.request` | 39 | 30 | Yes |
| `clinical.imaging.request.line` | 18 | 7 | No |
| `clinical.imaging.result` | 38 | 28 | Yes |
| `clinical.imaging.result.dose` | 7 | 1 | No |
| `clinical.imaging.result.measure` | 8 | 1 | No |
| `clinical.imaging.kpi.snapshot` | 36 | 20 | Yes |
| `clinical.imaging.kpi.modality.line` | 6 | 0 | No |
| `clinical.imaging.kpi.device.line` | 8 | 0 | No |
| `clinical.imaging.kpi.radiologist.line` | 5 | 0 | No |
| `clinical.imaging.modality.tag` | 6 | 0 | No |
| `clinical.imaging.staff.credential` | 13 | 2 | No |
| `clinic.treatment.imaging.plan` | 26 | 17 | Yes |
| `clinical.imaging.encounter.screening` | 43 | 12 | Yes |
| `clinical.imaging.encounter.note` | 11 | 6 | Yes |
| `clinical.imaging.premed.protocol` | 9 | 0 | No |
| `clinical.imaging.consent.template` | 15 | 1 | Yes |
| `clinical.imaging.consent.template.question` | 12 | 0 | No |
| `clinical.imaging.consent.answer` | 14 | 2 | No |

## Active model files

- `models/clinical_imaging_type.py`
- `models/clinical_imaging_device.py`
- `models/clinical_imaging.py`
- `models/clinical_imaging_study.py`
- `models/clinical_imaging_series.py`
- `models/clinical_imaging_image.py`
- `models/clinical_imaging_finding.py`
- `models/clinical_imaging_report.py`
- `models/clinical_imaging_request.py`
- `models/clinical_imaging_result.py`
- `models/clinical_imaging_kpi.py`
- `models/res_partner_inherit.py`
- `models/hr_employee_inherit.py`
- `models/treatment_inherit.py`
- `models/encounter_inherit.py`
- `models/prescription_order_inherit.py`
- `models/consent_inherit.py`
- `models/account_move_inherit.py`

## Dormant preserved sources

- `models/models.py`
- `models/xxx_clinic_imaging.py`

These files are preserved but intentionally not imported by `models/__init__.py`.
