




# MASTER PROMPT 09 — STAFF & CLINICAL PROVIDER DATASET

**Build:** `clinic_demo` 19.0.1.0.5  
**Authoritative snapshot:** `clinic19a(20260827-111757).md`  
**Snapshot SHA-256:** `05c1032003bf8f48890375c8bc3bda6e45c54985e6467279be0062b481408d19`

## Implemented
- Fail-fast owner-addon preflight for 20 Staff ACL rows, 6 Doctor ACL rows, 10 Staff sequences, and 1 Doctor appointment sequence.
- Presentation actors: executive/owner, clinic manager, front office, cashier/finance, quality/compliance, analytics/reporting, doctor, nurse, therapist, and reused executing System Administrator.
- One-person identity chain: `res.partner → res.users → hr.employee → clinic.staff → clinic.practitioner`, plus `clinic.doctor` for doctors.
- Branch consistency across user, employee, staff, practitioner and doctor.
- Clinical capability through source-native skill matrix + license compliance; doctor specialization through `clinic.specialty`.
- Provider availability and 90-day doctor schedule rules relative to Demo Anchor Date.
- Compact/Standard/Full Enterprise provider budgets: 1/1/1, 2/2/1, and 3/2/2 (doctor/nurse/therapist).
- Role-based model-access validation runs as the synthetic actor, without `sudo()`. Suite-level menu/action/record-rule acceptance remains Prompt 23.

## Owner patches required
1. `clinic_staff` 19.0.1.0.1 — loads corrected runtime ACL, defines all ten source-called sequences, adds user/employee identity bridge, restores `can_be_scheduled` compute.
2. `clinic_doctor` 19.0.1.0.2 — retains the Prompt-09 ACL/sequence/identity bridge and restores the active `res.partner.is_doctor` field required by its own runtime constraint/write contract.

## Runtime order
`upgrade clinic_staff → upgrade clinic_doctor → upgrade clinic_demo → Refresh Compatibility → Generate Full` as System Administrator.

The Prompt-09 preflight intentionally blocks generation if the owner patches were not upgraded first.

System Administrator is accepted by the execution engine without duplicating functional ClinicOne group memberships; normal ORM ACL and record-rule enforcement remains active.


## Runtime repair 19.0.1.0.5

Runtime evidence from `workforce.staff` revealed that the active `clinic_doctor` partner extension constrained and read `res.partner.is_doctor` while the field declaration had been commented out under a stale `clinic_audit` ownership note.  Doctor 19.0.1.0.2 restores the field in the semantic owner, and Prompt-09 preflight now fails before dataset creation if the field is absent.


## Runtime Repair 19.0.1.0.6 — Odoo 19 User/Security API

- Replaced legacy `res.users.groups_id` with Odoo 19 `group_ids`.
- Replaced legacy `check_access_rights()` validation with Odoo 19 `check_access()`.
- Workforce preflight now requires `res.users.group_ids`.
- Fail-fast notification now surfaces the first failed generator and its sanitized summary.
- Related company fields on staff skill/availability are derived from `staff_id` rather than explicitly written.

## Runtime Repair 19.0.1.0.7 — clinic_patient Odoo 19 User Group API

`workforce.staff` can create presentation users only if every inherited
`res.users.create()` path is Odoo-19 compatible. Runtime evidence identified
`clinic_patient` reading `self.groups_id`. The owner addon is repaired to
`group_ids` in clinic_patient 19.0.1.0.1. This demo build requires that owner
version through the suite compatibility contract.
























