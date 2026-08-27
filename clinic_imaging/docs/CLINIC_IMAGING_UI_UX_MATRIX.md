# ClinicOne — clinic_imaging UI/UX Matrix

| Model | Search | List | Form | Enterprise workflow surface |
|---|---|---|---|---|
| `clinical.imaging.type.tag` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.type` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.protocol` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.type.prep` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.type.contra` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.device` | Yes | Yes | Yes | Status/actions/smart navigation |
| `clinical.imaging.device.downtime` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.device.calibration` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.device.connectivity` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging` | Yes | Yes | Yes | Status/actions/smart navigation |
| `clinical.imaging.study` | Yes | Yes | Yes | Status/actions/smart navigation |
| `clinical.imaging.study.note` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.series` | Yes | Yes | Yes | Status/actions/smart navigation |
| `clinical.imaging.series.param` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.series.dose` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.image.tag` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.image` | Yes | Yes | Yes | Status/actions/smart navigation |
| `clinical.imaging.image.annotation` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.finding.tag` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.finding` | Yes | Yes | Yes | Status/actions/smart navigation |
| `clinical.imaging.finding.measure` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.report.template` | Yes | Yes | Yes | Status/actions/smart navigation |
| `clinical.imaging.report.template.section` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.report.template.variable` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.report.template.asset` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.request` | Yes | Yes | Yes | Status/actions/smart navigation |
| `clinical.imaging.request.line` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.result` | Yes | Yes | Yes | Status/actions/smart navigation |
| `clinical.imaging.result.dose` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.result.measure` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.kpi.snapshot` | Yes | Yes | Yes | Status/actions/smart navigation |
| `clinical.imaging.kpi.modality.line` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.kpi.device.line` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.kpi.radiologist.line` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.modality.tag` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.staff.credential` | Yes | Yes | Yes | Professional master/detail form |
| `clinic.treatment.imaging.plan` | Yes | Yes | Yes | Status/actions/smart navigation |
| `clinical.imaging.encounter.screening` | Yes | Yes | Yes | Status/actions/smart navigation |
| `clinical.imaging.encounter.note` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.premed.protocol` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.consent.template` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.consent.template.question` | Yes | Yes | Yes | Professional master/detail form |
| `clinical.imaging.consent.answer` | Yes | Yes | Yes | Professional master/detail form |

All persistent custom models receive explicit Search/List/Form views. Main workflow models expose existing lifecycle methods as header or smart buttons; no synthetic business states are invented.
