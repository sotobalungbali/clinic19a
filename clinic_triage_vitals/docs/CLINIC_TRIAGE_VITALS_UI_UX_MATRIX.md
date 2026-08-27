
# ClinicOne — clinic_triage_vitals UI/UX Matrix

| Model | Search | List | Form | Statusbar | Action Buttons | Smart/Navigation | One2many UX | Security |
|---|---|---|---|---|---|---|---|---|
| `clinic.triage.session` | YES | YES | YES | `state` | Start, Complete, Refer, Create Invoice, Reopen, Cancel | Invoice smart button | Vitals list + Open Session button | ACL + company rule |
| `clinic.vitals.intake` | YES | YES | YES | N/A | Open Triage Session | Parent navigation | N/A | ACL + company rule |
| `clinic.triage.level` | YES | YES | YES | N/A | N/A | routing/billing configuration | N/A | ACL + company rule |
| `clinic.triage.tag` | YES | YES | YES | N/A | View Sessions | Triage Sessions smart button | Child Tags editable list | ACL + company rule |
| `clinic.patient` extension | inherited | inherited | inherited | existing patient statusbar | New Triage Session | Triage Sessions + Latest Vitals smart buttons | Triage history read-only list | Existing patient security + triage model ACL/rules |

## Design principles

- Existing lifecycle/state values are exposed; no new business state is invented.
- UI visibility is not treated as security. ACLs and record rules remain authoritative.
- Search views are explicit for every persistent custom triage/vitals model.
- Lists emphasize operational columns, abnormal/SLA decoration, and optional secondary fields.
- Forms are split into clinically meaningful sections and notebooks.
- Buttons call existing methods or navigation-only helpers; they do not silently redesign workflows.
