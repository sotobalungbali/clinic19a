# clinic_emar — Enterprise Completeness Matrix

| Model | Enterprise purpose | Search | List | Form / workflow UX | Security / integrity | Integration |
|---|---|---:|---:|---|---|---|
| `clinic.emar.medication.profile` | Product-level clinical medication policy | Yes | Yes | Master form, high-alert/controlled/dose/barcode/lot settings | Company rule; manager-only mutation; Odoo 19 constraints | product/uom/lot |
| `clinic.emar.prescription` | Clinical prescribing source | Yes | Yes | Statusbar; safety, prescriber, cosign/sign, validate/activate/cancel, generate order; medication O2M | Company rule; no normal unlink; ORM state guard + safety/prescriber gates | patient/doctor/booking/encounter/vitals/order/account |
| `clinic.emar.medication.line` | Dose/SIG/route/frequency/duration/commercial intent | Yes | Yes | Dedicated form/list and inline O2M profile button | Company rule; header XOR constraint; positive quantity/dose/duration constraints | prescription/order/profile/product/uom |
| `clinic.emar.order` | Executable medication order | Yes | Yes | Statusbar; safety/prescriber/sign; confirm/approve/activate/suspend/complete/cancel; schedule/admin/inventory/invoice smart actions | Company rule; no normal unlink; ORM state guard; completion requires terminal schedules | partner/employee + canonical patient/doctor, inventory, accounting, imaging-compatible schema |
| `clinic.emar.schedule` | Planned administration dose | Yes | Yes | Statusbar, calendar, row Administer/Reschedule actions | Company rule; no normal unlink; ORM state guard; unique order-line-datetime | order/line/room/administration/cron |
| `clinic.emar.administration` | Verified actual medication administration | Yes | Yes | Statusbar; Verify/Confirm/Start/Complete; Refuse/Skip/Missed/Cancel/Reset; separate clinical-dose and inventory-quantity capture; inventory/invoice traceability | Company rule; no normal unlink; ORM state guard; server-side patient/product/lot/double-check verification | schedule/order/patient/doctor/vitals/inventory/account |
| `clinic.emar.alert` | Medication safety/operational alerts | Yes | Yes | Acknowledge/resolve/dismiss/reopen/snooze/open-related | Company rule; no normal unlink; digest dedup constraint | all eMAR clinical records |
| `clinic.emar.reschedule.wizard` | Governed reschedule with reason | N/A | N/A | Modal form, required target time/reason | Nurse group transient ACL | schedule traceability |

## Cross-cutting completeness

- Sequences: Prescription, Order, Administration.
- Cron: due/missed schedule lifecycle with company grace period and deduplicated alert.
- Configuration: default warehouse, auto-schedule, patient/product scan requirements, high-alert double-check, overdue grace.
- Roles: eMAR User, Prescriber, Medication Administrator, Manager/Pharmacist.
- Multi-company: record rules on all seven owned persistent models.
- No legacy `<tree>`, `tree,form`, XML `attrs` or `states`.
- No forward ClinicOne dependency beyond encounter-level upstream contracts.
- Clinical dose and physical inventory quantity are separate integrity dimensions.
- Odoo 19 UoM compatibility is based on `relative_uom_id`; no legacy `reference_uom_id`/category contract is used by eMAR.

## Schema resilience — release 19.0.3.0.0

| Dimension | Enterprise requirement | Status |
|---|---|---|
| Global-model safety | eMAR must not make `res.company` unreadable during source/schema drift | PASS — six company fields are non-stored proxies |
| Multi-company configuration | settings isolated by company | PASS — company id is part of each parameter key |
| Upgrade preservation | existing stored company values retained when present | PASS — pre-migration included |
| Upgrade verification | owned eMAR tables asserted after module update | PASS — post-migration included |
| Background recovery window | cron/autovacuum must not query absent eMAR tables | PASS — schema guards included |
| Runtime target proof | actual Windows/Odoo upgrade and smoke | PENDING |

