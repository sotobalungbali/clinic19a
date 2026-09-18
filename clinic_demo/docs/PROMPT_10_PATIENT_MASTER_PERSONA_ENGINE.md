




# MASTER PROMPT 10 — PATIENT MASTER & PERSONA ENGINE

## Build Contract

- Addon: `clinic_demo`
- Version: `19.0.1.0.8`
- Authoritative snapshot: `clinic19a(20260829-043903).md`
- Snapshot SHA-256: `d9d7cf796a4b5dfc756bcb99a73ddb9ecdba57d5a24ce196af929ecd9ec257be`
- Owner-addon patches required by Prompt 10: **none**
- Prior runtime-frozen owner versions remain: `clinic_patient 19.0.1.0.1`, `clinic_staff 19.0.1.0.1`, `clinic_doctor 19.0.1.0.2`.

## Objective

Prompt 10 creates deterministic synthetic patient masters only. It deliberately does not create downstream bookings, encounters, insurance authorizations, membership contracts, imaging orders, eMAR orders/administrations, telemedicine sessions, incidents, referrals, or treatment sessions. Those journeys are populated by their later bounded Master Prompts.

## Generator

`patient.personas` (`10_patient`, sequence 310) depends on `workforce.staff` and executes inside the standard generator savepoint/checkpoint boundary.

## Dataset Budgets

| Profile | Core personas | General cohort | Total patients |
|---|---:|---:|---:|
| Compact | 16 | 0 | 16 |
| Standard | 16 | 8 | 24 |
| Full Enterprise | 16 | 16 | 32 |

All profiles keep the same 16 stable core persona keys so later generators can resolve exact patient anchors regardless of dataset size.

## Core Persona Matrix

| Demo key | Persona | Downstream foundation |
|---|---|---|
| `DEMO-PAT-NEW-001` | New adult patient | Registration, booking, first encounter |
| `DEMO-PAT-RET-001` | Returning patient | Longitudinal encounter/history |
| `DEMO-PAT-ELDER-001` | Elderly | Long-term care |
| `DEMO-PAT-PED-001` | Pediatric | Family/pediatric scheduling |
| `DEMO-PAT-CHRON-001` | Chronic care | Care plan + medication context |
| `DEMO-PAT-FREQ-001` | High-frequency | Historical trends/reports |
| `DEMO-PAT-PKG-001` | Package | Package + treatment session |
| `DEMO-PAT-IMG-001` | Imaging | PACS/DICOM + contrast-safety context |
| `DEMO-PAT-EMAR-001` | Medication/eMAR | eMAR barcode + allergy safety |
| `DEMO-PAT-TELE-001` | Telemedicine | Portal/contact readiness |
| `DEMO-PAT-MEM-001` | Membership | Membership billing-policy foundation |
| `DEMO-PAT-INS-001` | Insurance | Synthetic BPJS + receivable-ready policy |
| `DEMO-PAT-INC-001` | Incident/quality | Future controlled exception |
| `DEMO-PAT-NOSHOW-001` | No-show/cancel | Future service-recovery journey |
| `DEMO-PAT-VIP-001` | VIP/wallet | Commercial/wallet journey |
| `DEMO-PAT-REF-001` | Referral | Referral/acquisition conversion |

## Stable Identity

Each patient has:

- ownership/reference-registry key `DEMO-PAT-*`;
- partner reference `DEMO-PAT-PARTNER-*`;
- source-generated `clinic.patient.patient_code` (never overridden by demo code);
- source-native MRN and NIK identifier rows;
- a BPJS identifier row for the insurance persona;
- synthetic `.invalid` email and synthetic contact/address values;
- `DEMO-EMAR-*` patient barcode for later medication/eMAR resolution.

Identifier types (`MRN`, `NIK`, `BPJS`) are reused if already configured. Reused non-demo masters are bound as reused and are never mutated by the generic idempotency engine.

## Demographic and Branch Design

The core set includes male/female/other gender values and adult, pediatric, elderly, chronic-care, VIP and general cohorts. Patient and partner company/branch scopes are kept aligned to the Prompt-08 demo branches. Compact uses one branch, Standard two, Full Enterprise three.

## Clinical Master Context

Prompt 10 creates only source-native master context required before later transactions:

- one synthetic chronic condition on `DEMO-PAT-CHRON-001`;
- one synthetic medication allergy on `DEMO-PAT-EMAR-001`;
- imaging identity/contrast-history fields on `DEMO-PAT-IMG-001`;
- patient tags describing persona intent.

No diagnosis claim is inferred from demographics and no real personal/medical data is used.

## Idempotency / Reset

Patient identity is registry-owned and rerunnable. Business patient codes continue to come from `clinic_patient.seq_patient_code`. Patient/identifier/condition masters are deactivated on reset; synthetic allergy/tag dependents may be removed safely. Reused identifier types are retained untouched.

## Progressive Compatibility

A Demo Run that has completed only Prompt-08/09 registered generators may adopt this Prompt-10 build using **Refresh Compatibility**. Adoption is rejected once a `patient.personas` or later checkpoint/reference exists under an older fingerprint.

## Expected Runtime Route

1. Upgrade `clinic_demo` to `19.0.1.0.8`.
2. Open the same Prompt-09-complete Demo Run.
3. Refresh Compatibility; status must be Compatible.
4. Generate Full Enterprise Dataset as System Administrator.
5. Existing four Prompt-08/09 checkpoints remain Done/reused.
6. `patient.personas` must finish Done.
7. Registered-scope completion should report five bounded generators.

Runtime PASS is granted only after the user's Odoo database completes this route without a failed checkpoint.
























