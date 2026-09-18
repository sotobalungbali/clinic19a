# Current release 19.0.1.0.61

See docs/RELEASE_61.md; upgrade bundled clinic_reports first.

# Current release: 19.0.1.0.60

See docs/RELEASE_60.md. Upgrade bundled clinic_inventory first.

# Current release: 19.0.1.0.59

See docs/RELEASE_59.md for the anchor-relative follow-up repair and upgrade steps.

# Current release: 19.0.1.0.58

See [release 58](docs/RELEASE_58.md) for Telemedicine branch preparation and exact resume steps. Previous release notes below are historical.

# Current release: 19.0.1.0.57

Read [release 57](docs/RELEASE_57.md) for the advanced clinical actor correction and resume steps. Earlier notes below are historical.

# Current release: 19.0.1.0.56

See [release 56](docs/RELEASE_56.md) for the canonical patient bridge correction and exact resume steps. Older release notes below are historical.

# Current release: 19.0.1.0.55

See [release 55](docs/RELEASE_55.md) for state progression and Journey Progress navigation. Earlier notes below are historical.

# Current release: 19.0.1.0.54

Read [release 54](docs/RELEASE_54.md) for the reconciliation-reader correction and upgrade steps. Earlier release notes below are historical.

# Current release: 19.0.1.0.53

Read [release and migration steps](docs/RELEASE_53.md), [journey traceability](docs/JOURNEY_TRACEABILITY_53.md), and [native acceptance A–F](docs/ACCEPTANCE_A_F_53.md). Permanent execution/migration authority: [GOVERNING_MODEL_BY_MODEL.md](docs/GOVERNING_MODEL_BY_MODEL.md). The historical documentation below is retained for traceability; current behavior is governed by release 53.

# clinic_demo 19.0.1.0.52

Current instructions: docs/RELEASE_52.md. Upgrade bundled clinic_inventory 19.0.1.0.4 first, then clinic_demo 19.0.1.0.52. Same run → Refresh Compatibility → Complete Source Journeys → automatic acceptance and Validate. No reset. Native readiness pending. Older notes below are historical.

# clinic_demo 19.0.1.0.51

Current release: docs/RELEASE_51.md and docs/TEST_REPORT_51.md. Replace only clinic_demo. Same run → Refresh Compatibility → Complete Source Journeys → automatic acceptance and Validate. Do not reset. Previous companion versions remain required. Native runtime acceptance pending.

Older instructions below are historical and superseded by v51.

# ClinicOne clinic_demo 19.0.1.0.50

Current release: docs/RELEASE_50.md and docs/TEST_REPORT_50.md. Full replacement clinic_demo; same Demo Run → Refresh Compatibility → Complete Source Journeys → automatic acceptance resume and Validate. Do not reset. Companion versions remain pinned. Native readiness acceptance remains pending.

Older release instructions below are historical and superseded by v50.

# ClinicOne clinic_demo 19.0.1.0.49

Current release: **docs/RELEASE_49.md** and **docs/TEST_REPORT_49.md**. Replace and upgrade only clinic_demo, then use the same run: Refresh Compatibility → Complete Source Journeys → automatic acceptance resume and Validate. Exact companion versions from v48 remain required. Native readiness acceptance is pending.

The v49 release notes supersede older upgrade instructions below. Earlier reports and notes are retained as history.

# ClinicOne clinic_demo 19.0.1.0.48

Current release: see **docs/RELEASE_48.md** for the six-addon upgrade and **Complete Source Journeys** action on the existing run. The five report-source families are now implemented, with owner-based evidence refresh and explicit identifiers/dates. Required report metrics remain mandatory. Native runtime acceptance remains pending.

Historical notes below are retained for context and do not supersede the v48 manifest, matrix or test report.

# v47 Readiness repair — partial delivery

See docs/VALIDATION_REPAIR_47.md. Five required transaction families remain incomplete. Do not treat 35 Done checkpoints as full enterprise acceptance.






# ClinicOne Enterprise Demo Dataset (`clinic_demo`)

Odoo 19 Community Edition.

## MASTER PROMPT 06 status

This package is the first installable framework build. It provides deterministic demo
identity, ownership and idempotency foundations without generating ClinicOne business
transactions yet.

### Implemented now

- `clinic.demo.run`
- `clinic.demo.reference`
- `clinic.demo.checkpoint`
- `clinic.demo.log`
- `clinic.demo.validation.result`
- deterministic seed service
- exact ClinicOne source/version compatibility fingerprint
- stable demo-key reference service
- create-or-reuse and missing-record repair foundation
- source-driven reset-policy registry
- ownership-aware reset foundation
- Demo Safe Mode foundation
- checkpoint/logging/validation foundations
- Odoo regression tests
- static Enterprise Guardrail

### Not implemented until later prompts

- enterprise Control Center UI (Prompt 07)
- foundation through management domain generators (Prompts 08–22)
- final full reset/regeneration/validation suite (Prompt 23)
- executive demo script/release hardening (Prompt 24)

## Final release

Version `19.0.1.0.46` freezes the runtime-proven 35-generator dataset and adds
the MASTER PROMPT 24 presentation/release artifacts. Start with
`docs/CLINIC_DEMO_EXECUTIVE_DEMO_SCRIPT.md` and verify the target Demo Run shows
**READY FOR DEMO** before client presentation.

No existing ClinicOne addon is patched or replaced by this package.


## MASTER PROMPT 07 status

Version `19.0.1.0.2` adds the Enterprise Demo Control Center UI and reset
confirmation flow. Full business-data generation remains intentionally gated until
the bounded domain generators are implemented beginning with MASTER PROMPT 08.


## MASTER PROMPT 08 status

Version `19.0.1.0.3` registers the first two real domain generators:

- `foundation.native`
- `foundation.organization`

Generate Full now creates/reuses real source-valid company/branch/location foundation
records for the selected profile. The full enterprise generator registry remains
progressive and is not claimed complete until later prompts.


## MASTER PROMPT 09 status

Version `19.0.1.0.4` adds the bounded workforce/provider phase:

- `workforce.preflight` — fail-fast ACL, sequence, and identity-bridge checkpoint
- `workforce.staff` — deterministic presentation actors and clinical providers

Full Enterprise creates six non-clinical presentation personas, three doctors,
two nurses, two therapists, and reuses the executing System Administrator as the
technical-administrator actor. Clinical identities are linked through User →
Employee → Staff → Practitioner, with Doctor as an additional provider profile
for doctors. Branch, license, skill/capability, availability, specialty, and
90-day schedule contracts are validated without `sudo()` in `clinic_demo`.

Required runtime order for this build:

`clinic_staff` upgrade → `clinic_doctor` upgrade → `clinic_demo` upgrade →
**Refresh Compatibility** → **Generate Full** as System Administrator.


### Prompt 09 runtime repair 19.0.1.0.5

If a prior 19.0.1.0.4 run stopped at `workforce.staff` with missing `res.partner.is_doctor`, upgrade `clinic_doctor` to 19.0.1.0.2 and this addon to 19.0.1.0.5, then use **Refresh Compatibility** on the same failed run.  If no workforce references were committed before the failure, the run can adopt the repair build and resume safely.

### Prompt 09 runtime repair 19.0.1.0.7

Runtime evidence on 29 Aug 2026 showed that `clinic_patient` still read the
legacy Odoo user field `groups_id` inside its inherited `res.users.create()`
post-processing path. Odoo 19 uses `group_ids`.

Upgrade `clinic_patient` to **19.0.1.0.1**, then upgrade this addon to
**19.0.1.0.7**, use **Refresh Compatibility** on the same failed Prompt-09 run,
and resume/generate again. The repair is owner-addon scoped and does not change
Prompt-09 workforce business semantics.

Expected suite fingerprint: `c2987f4afa4bee142dad4fdbace93f0b027de6708618462427cf60a300b853b2`.


## MASTER PROMPT 10 status

Version `19.0.1.0.8` registers `patient.personas` after the runtime-frozen
Prompt-09 workforce scope. It generates deterministic synthetic patient masters
with stable `DEMO-PAT-*` references, source-sequenced patient codes, source-native
MRN/NIK identifiers, a synthetic BPJS identifier for the insurance persona,
branch/demographic variation, patient tags, and bounded clinical-master context
for chronic-care, imaging, medication/eMAR, telemedicine, membership, insurance,
incident, no-show/cancel, VIP/wallet, package/session and referral journeys.

Profile patient budgets are **16 Compact / 24 Standard / 32 Full Enterprise**.
Prompt 10 intentionally creates no downstream booking, encounter, authorization,
contract, imaging order, eMAR transaction, incident, referral, or treatment-session
transaction; those remain owned by later Master Prompts.

A Prompt-09-complete Demo Run can adopt this progressive build through **Refresh
Compatibility**, provided no `patient.personas` or later checkpoint/reference already
exists under the older fingerprint.

## MASTER PROMPT 11 status

Version `19.0.1.0.9` registers three bounded `11_master` generators:

- `master.catalog` — treatment/service categories and catalog, source-native clinical
  pricelist items, billable product bridges, published care-protocol masters,
  imaging type/protocol/preparation masters, and eMAR medication profiles.
- `master.consent` — governed consent templates/checklists/versions and source-valid
  publication before treatments are marked consent-required.
- `master.commercial` — package policy/pricing/package components, membership
  plans/benefits, synthetic insurer + insurance-plan/rule masters, and wallet usage-rule
  templates.

Prompt 11 creates reusable masters only. It intentionally creates no patient consent
form, package allocation/usage, membership contract, insurance policy/authorization,
wallet account/transaction, booking, encounter, imaging request, eMAR order,
billing invoice/payment or accounting entry.

Package and membership activation uses official business methods. The local outbox
records created by those methods are immediately moved to source-supported
cancelled/ignored states in Demo Safe Mode. Prompt-11 owner sequence codes are checked
before data creation to fail fast on installation/schema drift.

A Prompt-10-complete Demo Run can adopt this build through **Refresh Compatibility**
only while no Prompt-11 reference/checkpoint exists. Expected registered-scope count
after successful Full Enterprise generation is **8 bounded generators**.

## MASTER PROMPT 12 status

Version `19.0.1.0.10` registers `resources.rooms_devices` after the Prompt-11
clinical/commercial master scope. It creates deterministic room types, rooms,
medical-device categories/devices, active source-workflow room-device assignments,
booking-room wrappers, booking resources, Monday-Saturday room/resource/provider
schedules, future maintenance/cleaning blackouts, and reusable 90-day booking-slot
templates.

Prompt 12 intentionally creates **no patient booking, queue token, triage transaction,
room session, encounter, treatment session, invoice, payment, journal entry, or stock
move**. It only prepares source-valid capacity and compatibility masters that later
operational prompts consume. Treatments and demo doctors are linked to branch-compatible
rooms/resources without changing their existing demo ownership.

Profile budgets are **4/6/9 rooms**, **4/6/8 devices/resources**, and **4/8/12 booking
slot templates** for Compact/Standard/Full Enterprise. Every generated device target
room must exist in the same profile/branch; room/resource allowed doctors are branch
scoped. Room availability and booking schedules cover Monday-Saturday. Resource
exceptions use owner blackout models rather than illegal schedule conflicts.

The owner room-device assignment capacity guard is honored: the B001 imaging physical
room allows two installed devices while its booking wrapper remains capacity 1 for
single-patient concurrency. Assignment activation disables optional movement-log side
effects and does not pre-populate a supervisor, avoiding unowned activity records.

Prompt-12 reset ordering is explicitly child-first. A Prompt-11-complete Demo Run can
adopt this build through **Refresh Compatibility** while no Prompt-12 reference/checkpoint
exists. Because this is a cumulative full replacement build, the prior bounded Prompt-11
adoption route is also retained. Expected registered-scope count after successful
Prompt-12 generation is **9 bounded generators**.

## Prompt 11/12 functional ACL runtime repair

Version `19.0.1.0.11` preserves the Prompt-12 cumulative nine-generator scope and
repairs a concrete runtime security-context defect found on 30 Aug 2026. The demo is
still launched by a System Administrator, but restricted owner masters are no longer
created under an unrelated technical-user ACL context.

`master.catalog` uses the existing demo Clinic Manager actor with the owner eMAR Manager
role for `clinic.emar.medication.profile`. `master.commercial` uses the same demo-owned
manager actor with Package, Membership, Insurance and Wallet manager roles for the
corresponding restricted master/event models. Odoo ACLs and record rules remain active;
`clinic_demo` does not use `sudo()` for these operations and does not loosen owner ACLs.

The reference/idempotency service is actor-aware for these restricted records so the
same run remains rerunnable. A failed `master.catalog` checkpoint from 19.0.1.0.10 can
adopt this repair via **Refresh Compatibility** only if no Prompt-11 references were
committed by the failed savepoint.


### Prompt 11 runtime repair 19.0.1.0.12 — Membership ACL database drift

Runtime evidence showed `master.commercial` could not create `membership.plan` even
after the Demo Clinic Manager received the Membership Manager group. The owner source
already declares the correct manager create ACL, so upgrade `clinic_membership` to
**19.0.3.0.6** to reload that ACL into the database, then upgrade this addon to
**19.0.1.0.12**. Prompt-11 commercial preflight now validates actual create access
for all restricted commercial master models before generation starts.

Expected suite fingerprint: `7f060941d2b09687f2e071a2375209b61725bf71e236bc6f564df15cb5847590`.


### Prompt 12 runtime repair 19.0.1.0.14 — Room/Device owner sequence database drift

Runtime evidence showed `resources.rooms_devices` fail-fast preflight reporting
missing `clinic.device.code` and `clinic.room.device.assignment`. The owner source
already declares both in `clinic_room_device/data/clinic_room_device_sequence.xml`
and manifest-loads that file. Upgrade `clinic_room_device` to **19.0.1.0.1** to
reload the source-owned sequence data, then upgrade this addon to **19.0.1.0.14**.

This build requires the owner repair version and permits the same failed Prompt-12
run to adopt the repair through **Refresh Compatibility** only when the failed
generator savepoint left no `resources.rooms_devices` reference committed.

Expected suite fingerprint: `17e98031b058cfbf57e3afa6e872a43e949b900265ce38f1109e2cefa9410689`.


## Prompt 12 runtime repair — deterministic booking-slot names (19.0.1.0.14)

The Prompt-12 `resources.rooms_devices` generator now includes the stable slot ordinal
in every `booking.slot.name` (for example `... — Slot 001`). The owner model enforces
`unique(name, company_id)` and the Full Enterprise profile intentionally reuses some
Treatment/Doctor combinations at different weekday/hour windows. The ordinal keeps the
human-facing name deterministic and unique without changing the owner constraint or
creating patient bookings. Existing failed Prompt-12 runs may adopt this build after
Refresh Compatibility only when the failed savepoint left no Prompt-12 references.


## MASTER PROMPT 13 status

Version `19.0.1.0.15` adds the reusable `HistoricalTimelineService` and registers
`history.patient_longitudinal` after the runtime-frozen Prompt-12 resource scope.
The service defines deterministic T-365..T-1 historical bands and source-owned
business-date fields for the transaction generators implemented in Prompts 14–20.

Prompt 13 immediately creates only source-native longitudinal patient history:
24/48/72 historical vital observations for Compact/Standard/Full Enterprise,
3/4/6 chronic-condition episodes, and one recovered synthetic allergy-reaction
history. It intentionally does **not** create Booking, Encounter, Treatment Session,
Imaging, eMAR, Care Plan, Billing, Feedback, Incident or Quality transactions before
their owner prompts. Those later generators consume the same historical-time service
and official business methods.

A Prompt-12-complete Demo Run can adopt this build through **Refresh Compatibility**
while no Prompt-13 reference/checkpoint exists. Expected registered-scope count after
successful Prompt-13 generation is **10 bounded generators**.



## MASTER PROMPT 14
Referral acquisition/conversion plus historical/current/future Booking front-office operations are registered as two bounded generators.


## MASTER PROMPT 14 — Booking & Front Office Operations

Version `19.0.1.0.19` registers `operations.referral` and `operations.booking` for
source-driven referral acquisition/conversion plus historical/current/future front-office
booking. The build requires `clinic_referral 19.0.2.0.6` and
`clinic_booking 19.0.1.0.4`. Queue/Triage/Encounter/Treatment Session remain later
phases. See `docs/PROMPT_14_BOOKING_FRONT_OFFICE_OPERATIONS.md`.

Runtime repair `19.0.1.0.19` requires `clinic_treatment_session 19.0.2.0.3` so Treatment Session room availability remains API-compatible and compositional with `clinic_booking`.


## MASTER PROMPT 15 status

Version `19.0.1.0.20` registers `operations.queue_triage` after the runtime-frozen
Prompt-14 front-office scope. It creates current arrival, Queue Token, Waiting,
Called/In-Service, Completed Queue, Normal Triage and mild attention-required
abnormal-vitals scenarios through owner workflow methods. No owner addon is
patched. A Prompt-14-complete Draft Demo Run may adopt the build through Refresh
Compatibility and Generate Full Enterprise Dataset on the same run without Reset.
Existing DONE checkpoints are skipped by the execution engine.


## Prompt 15 runtime repair 19.0.1.0.21

Runtime evidence on 2 Sep 2026 showed `operations.queue_triage` stopped in its
fail-fast preflight because `clinic_demo` incorrectly required
`clinic.appointment.treatment_id`. The canonical active Appointment owner is
`clinic_doctor`; Appointment uses `clinic.patient` for `patient_id` and does not
own `treatment_id`.

This repair removes the invalid Appointment treatment-field assumption, validates
exact relational comodel contracts, fixes Triage/Appointment patient consistency
to compare `clinic.patient` to `clinic.patient`, and adds bounded same-run adoption
for a failed Prompt-15 checkpoint with zero Prompt-15 references committed.

No owner addon is changed. Upgrade `.21`, Refresh Compatibility on the same Failed
Demo Run, do not Reset, then Continue Generation.


## MASTER PROMPT 16

Adds source-driven Encounter and Treatment Session clinical journey generators. See `docs/PROMPT_16_ENCOUNTER_CORE_CLINICAL_JOURNEY.md`.























