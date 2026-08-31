
# CLINIC_DEMO_CORE_PATCH_LEDGER

## MASTER PROMPT 06

No ClinicOne core addon was modified.

Known source candidates carried forward from architecture review remain unpatched until
their assigned runtime checkpoint proves a real blocker.


## MASTER PROMPT 07

No ClinicOne core addon was modified.

`clinic_demo` itself was upgraded from 19.0.1.0.0 to 19.0.1.0.1 to add the
Enterprise Demo Control Center UI, backend action guards, navigation actions,
reset confirmation wizard and Control Center regression tests.


## clinic_demo Runtime Repair 19.0.1.0.2

No ClinicOne core addon was changed.

Runtime evidence showed `clinic_patient.menu_patient_configuration` exists in the
latest source but is absent from the installed database external-ID registry.
`clinic_demo` was repaired to load its Demo Dataset menu without a hard external
parent and reparent it through a post-load runtime-safe bridge.


## MASTER PROMPT 08

No ClinicOne core addon was modified.

The source-owned `clinic.branch` and `clinic.branch.location` contracts were sufficient
for foundation generation. Native accounting/tax creation was intentionally deferred
to Prompt 18 rather than patching or bypassing owner modules.

## MASTER PROMPT 09 — 2026-08-27
- **clinic_staff 19.0.1.0.1**: owner-addon ACL was present but manifest-disabled and referenced a scaffold model ID; runtime models also called ten missing sequences. Added runtime ACL coverage, ten owner sequences, additive `user_id`/`employee_id` Staff bridge, consistency constraints, and restored source-existing scheduling compute.
- **clinic_doctor 19.0.1.0.1**: owner-addon ACL was manifest-disabled/scaffolded and `clinic.appointment` called a missing sequence. Added runtime ACL coverage, appointment sequence, and additive Staff/branch Doctor bridge with identity consistency constraints.
- Patches are additive and source-driven; no workflow state, clinical business method, or demo-only fake KPI logic was introduced.


## Prompt 09 runtime repair — 27 Aug 2026

- **clinic_doctor 19.0.1.0.2**: runtime `workforce.staff` exposed a stale ownership comment in the active Doctor `res.partner` extension.  The class used `is_doctor` in its constraint/write behavior while the field declaration was commented out and `clinic_audit` did not actually own it.  Restored `res.partner.is_doctor` in `clinic_doctor`, its semantic owner.
- **clinic_demo 19.0.1.0.5**: Prompt-09 preflight now checks `res.partner.is_doctor`; compatibility expects Doctor 19.0.1.0.2; a failed `workforce.staff` run with no committed workforce references may safely adopt the repair build on Refresh Compatibility.


## clinic_demo 19.0.1.0.6 — Prompt 09 Odoo 19 API runtime repair

- Root-cause class: Odoo 19 API drift in workforce generator after the `is_doctor` schema repair.
- Replaced legacy `res.users.groups_id` writes with Odoo 19 `group_ids`.
- Replaced removed `check_access_rights()` validation with Odoo 19 `check_access()`.
- Added `res.users.group_ids` to the Prompt 09 fail-fast field contract.
- Removed explicit writes to related company fields on `clinic.staff.skill` and `clinic.staff.availability`.
- Improved Generation Paused notification to surface the failed generator key and sanitized error summary directly.
- Existing ClinicOne workflow/security semantics remain preserved; no core owner-addon patch is required for this repair.

## clinic_patient 19.0.1.0.1 + clinic_demo 19.0.1.0.7 — Odoo 19 res.users group field runtime repair

Concrete Prompt-09 runtime evidence showed `workforce.staff` failed after
`res.users.create()` with `AttributeError: 'res.users' object has no attribute
'groups_id'`.

Root cause: `clinic_patient/models/res_users_inherit.py` still used the legacy
`groups_id` API in its post-create portal/patient linking path. Odoo 19 uses
`group_ids`.

Targeted owner repair:
- `clinic_patient` active user-group references migrated to `group_ids`;
- owner guardrail rejects active `groups_id` in the patient user extension;
- `clinic_demo` compatibility now requires `clinic_patient` 19.0.1.0.1;
- failed Prompt-09 runs remain adoptable only under the existing no-workforce-
  reference safety boundary.

No patient workflow, provider workflow, ACL, record rule, or reset policy is
bypassed.

Authoritative snapshot SHA-256: `bb6f533c84b0a114d8bcc1b1bf7327ca14de0ab42f4ac7bf304bdebfd4db675f`
Expected suite fingerprint: `c2987f4afa4bee142dad4fdbace93f0b027de6708618462427cf60a300b853b2`


## MASTER PROMPT 10 — 2026-08-29

No ClinicOne owner addon patch was required. The latest `clinic_patient` source
already exposes the patient, identifier, tag, allergy, condition and eMAR identity
contracts required for a business-valid persona foundation.

`clinic_demo 19.0.1.0.8` adds only bounded orchestration:
- deterministic Patient Persona generator;
- 16/24/32 Compact/Standard/Full Enterprise patient budgets;
- stable Demo Reference identities while preserving the owner `patient_code` sequence;
- source-native MRN/NIK/BPJS identifier foundation;
- branch/demographic/persona mapping and clinical-master context;
- model-specific reset decisions;
- progressive compatibility adoption from a completed Prompt-09 run.

No downstream owner transaction is generated prematurely and no core business
workflow/security rule is bypassed.

Authoritative snapshot SHA-256: `d9d7cf796a4b5dfc756bcb99a73ddb9ecdba57d5a24ce196af929ecd9ec257be`
Expected suite fingerprint: `c2987f4afa4bee142dad4fdbace93f0b027de6708618462427cf60a300b853b2`

## MASTER PROMPT 11 — 2026-08-29

No ClinicOne owner-addon patch was required.

The authoritative source already provides the master contracts required by Prompt 11:
`treatment/service catalog`, governed consent templates, care protocols, imaging
masters, eMAR medication profiles, package policy/pricing, membership plan/benefit,
insurance plan/rule, wallet rule, and their business lifecycle methods.

`clinic_demo 19.0.1.0.9` adds only bounded orchestration, source-sequence preflight,
Demo-Safe outbox neutralization, model-specific reset decisions, and progressive
compatibility adoption from a completed Prompt-10 run. No downstream patient or
financial transaction is created prematurely.

Authoritative snapshot SHA-256: `a876d706f4cddb94caa1fdb3cc8e88b092203679e511b2dd8a5300248df0990a`
Expected suite fingerprint: `c2987f4afa4bee142dad4fdbace93f0b027de6708618462427cf60a300b853b2`

## MASTER PROMPT 12 — 2026-08-29

No ClinicOne owner-addon patch was required.

The authoritative source already exposes the required resource contracts in
`clinic_room_device` and `clinic_booking`: room/device masters, room-device assignment,
room availability, booking room/resource wrappers, weekly schedules, blackouts, provider
schedules, booking slots, treatment compatibility, and company isolation.

`clinic_demo 19.0.1.0.10` adds only bounded orchestration, sequence/model/field preflight,
branch-compatible provider/resource defaults, controlled future blackout scenarios,
model-specific reset decisions, and progressive compatibility adoption. No patient or
financial transaction is generated prematurely.

Authoritative snapshot SHA-256: `a876d706f4cddb94caa1fdb3cc8e88b092203679e511b2dd8a5300248df0990a`
Expected suite fingerprint: `c2987f4afa4bee142dad4fdbace93f0b027de6708618462427cf60a300b853b2`

## clinic_demo 19.0.1.0.11 — Prompt 11/12 functional ACL runtime repair — 2026-08-30

Concrete runtime evidence showed `master.catalog` failed while creating
`clinic.emar.medication.profile` because the executing System Administrator is not
implicitly a member of `clinic_emar.group_emar_manager`. A full ACL audit of Prompt-11
and Prompt-12 owner models also confirmed that package, membership, insurance and
wallet reusable masters require their own manager groups.

Targeted orchestration repair only; no owner-addon ACL is weakened:
- `master.catalog` resolves the demo Clinic Manager actor, grants the existing
  `clinic_emar.group_emar_manager` role, and executes eMAR medication-profile
  create/update/resolve under that actor with normal ORM ACL and record rules.
- `master.commercial` grants the same demo-owned Clinic Manager the existing Package,
  Membership, Insurance and Wallet manager groups and executes only the corresponding
  restricted owner models/events under that actor.
- `DemoReferenceService` now accepts an optional `record_user` so idempotent resolve,
  reuse, update and rebind checks can honor the same functional security context on
  reruns without `sudo()`.
- The existing failed `master.catalog` checkpoint may adopt this repair through Refresh
  Compatibility only when its generator savepoint left no Prompt-11 references committed.

No core owner module, business method, record rule, ACL row, clinical workflow, or
financial transaction contract is changed.

Authoritative snapshot SHA-256: `a876d706f4cddb94caa1fdb3cc8e88b092203679e511b2dd8a5300248df0990a`
Expected suite fingerprint: `c2987f4afa4bee142dad4fdbace93f0b027de6708618462427cf60a300b853b2`


## clinic_membership 19.0.3.0.6 + clinic_demo 19.0.1.0.12 — Prompt 11 membership ACL database-drift repair — 2026-08-30

Concrete runtime evidence: `master.commercial` failed creating `membership.plan` with
`No group currently allows this operation`. The authoritative source already declares
Membership Manager create ACL and manifest-loads `security/ir.model.access.csv`, so
the installed database ACL registry was stale relative to source.

Targeted owner repair: bump `clinic_membership` to 19.0.3.0.6 so Odoo reloads the
existing ACL declaration. The owner guardrail and post-install test now verify manager
create access for plan/benefit.

Targeted orchestration repair: `clinic_demo` 19.0.1.0.12 requires the owner version,
checks actual create access in Prompt-11 commercial preflight, and permits bounded
adoption of the same failed run only when no `master.commercial` references were
committed. No `sudo()`, direct SQL, workflow change, or broader ACL grant was added.

Authoritative snapshot SHA-256: `9408fc6d6a14539a566c77effae29ea281233a37ce46c791fbd8a18f2195c49d`
Expected suite fingerprint: `7f060941d2b09687f2e071a2375209b61725bf71e236bc6f564df15cb5847590`


## clinic_room_device 19.0.1.0.1 + clinic_demo 19.0.1.0.13 — Prompt 12 sequence database-drift repair — 2026-08-30

Concrete runtime evidence: `resources.rooms_devices` stopped in fail-fast preflight
because the installed database had no `clinic.device.code` or
`clinic.room.device.assignment` sequence.

The authoritative owner source already declares both sequence records in
`data/clinic_room_device_sequence.xml` and includes that file in the manifest.
The owner repair therefore bumps `clinic_room_device` to `19.0.1.0.1` so a normal
Odoo module upgrade reloads the source-owned sequence data. No alternate sequence,
manual SQL, or numbering bypass is introduced.

`clinic_demo` 19.0.1.0.13 requires that owner version, updates the exact suite/source
fingerprints, and permits bounded adoption of a failed `resources.rooms_devices`
checkpoint only when no Prompt-12 reference was committed by its savepoint.

Authoritative snapshot SHA-256: `03d244d5c894e69188731687aaf62cae6e586db9dc862c90235036f6da592cad`
Expected suite fingerprint: `17e98031b058cfbf57e3afa6e872a43e949b900265ce38f1109e2cefa9410689`


## 19.0.1.0.14 — Prompt 12 deterministic `booking.slot` identity repair

- Runtime evidence: `resources.rooms_devices` failed on owner constraint
  `booking_slot_name_company_unique` because Full Enterprise generated a repeated
  Treatment/Doctor combination with a different slot window but the same `name`.
- Owner addon `clinic_booking` is unchanged; its `unique(name, company_id)` and
  `unique(code, company_id)` constraints are preserved.
- Repair is orchestration-only: generated slot names now append the stable slot ordinal
  (`Slot 001`, `Slot 002`, ...), matching the already-stable `DEMO-SLOT-###` code/key.
- No `sudo()`, direct SQL, owner-constraint relaxation, or manual database cleanup.
- Failed Prompt-12 run adoption remains bounded to a rolled-back
  `resources.rooms_devices` checkpoint with no committed Prompt-12 references.
- Authoritative source fingerprint: `75fd525c05123c40c0e44a800c1d71cdd6f020cddd420c9199534cecf6692453`.

## MASTER PROMPT 14 — clinic_referral 19.0.2.0.6 + clinic_booking 19.0.1.0.2 + clinic_demo 19.0.1.0.16 — 2026-08-31

Source audit identified two owner-level gaps required for business-valid Prompt-14
front-office history/scheduling.

1. `clinic_referral 19.0.2.0.6` adds optional effective business datetime/date
   parameters to Confirm/Convert/mark_converted/Cancel/Expire. Omitted parameters
   preserve the existing current-time behavior. This allows historical referral
   lifecycle records without writing `create_date`/`write_date`.
2. `clinic_booking 19.0.1.0.2` evaluates weekly room/resource/doctor schedule
   windows in Odoo context/user local time via `fields.Datetime.context_timestamp()`
   instead of comparing UTC storage hours to local `hour_from/hour_to`. Blackout and
   overlap comparisons remain UTC.

`clinic_demo 19.0.1.0.16` registers `operations.referral` and
`operations.booking`, carries the Demo Run timezone through the booking workflow,
keeps appointment/Queue/Triage/Encounter/Treatment Session creation disabled, and
provides bounded progressive adoption from a completed Prompt-13 run.

Authoritative source fingerprint: `40feef78c53f0d3d07b7bb73148bbee90e8b10aa977dac401e22e9b7a617b426`
Expected suite fingerprint: `6b766b2aca80bc71f44edc5197dc33c04c0b253a0c71774a4813a2dfa076058d`

## MASTER PROMPT 14 Runtime Repair — clinic_booking 19.0.1.0.3 + clinic_demo 19.0.1.0.17 — 2026-08-31

Runtime `operations.booking` failed with `'list' object has no attribute 'get'`.
The exact owner defect was `booking.channel.create()` using legacy
`@api.model` + `def create(self, vals)` while the Odoo 19 create pipeline
supplied a values list. The repair converts the owner method to
`@api.model_create_multi`, preserves per-channel default-policy behavior, and
adds an owner multi-create regression test.

No ACL, business constraint, booking lifecycle, external integration behavior,
or database data was bypassed. `clinic_demo` only updates the exact owner-version
contract and adds bounded same-run adoption after an `operations.booking`
savepoint rollback with no committed booking references.

Authoritative source fingerprint: `1b91d4402f242a91bbbb7a483403187936eab960cc1b9858b059bc7987af2c7e`

Expected suite fingerprint: `58bdfcce0d5385599f06a081a21f35ecfcf298298becddf5c0a667e0154fa9f1`



## MASTER PROMPT 14 Runtime Repair — clinic_booking 19.0.1.0.4 + clinic_demo 19.0.1.0.19 — 2026-08-31

- Runtime evidence: `operations.booking` failed on invalid ORM field `clinic.appointment.start_datetime`.
- Owner root cause: `clinic_booking` soft appointment integration assumed legacy `start_datetime/end_datetime/active`, while `clinic_doctor` owns canonical `start/end/state`.
- Targeted repair: field-aware appointment overlap domain and field-aware create/link mapping, preserving booking/appointment lifecycle and security.
- `clinic_demo` exact suite contract now requires `clinic_booking 19.0.1.0.4`; same-run Prompt-14 failed checkpoint may be adopted only after the booking savepoint left no committed Prompt-14 booking references.

## MASTER PROMPT 14 Runtime Repair — clinic_treatment_session 19.0.2.0.3 + clinic_demo 19.0.1.0.19 — 2026-08-31

**Runtime evidence:** `BookingRoom.is_available() got an unexpected keyword argument 'ignore_booking_id'`.

The `clinic_booking` base room API already owns `ignore_booking_id` and
`consider_capacity`. `clinic_treatment_session 19.0.2.0.2` narrowed the
same public method to `ignore_session_ids` and did not call `super()`, thereby
shadowing Booking weekly schedule, blackout, overlap and capacity behavior.

Repair contract:
1. keep `ignore_session_ids` as the third positional parameter;
2. accept `ignore_booking_id` and `consider_capacity`;
3. call `super().is_available(...)` first;
4. apply Treatment Session overlap after Booking availability passes.

Expected suite fingerprint: `58bdfcce0d5385599f06a081a21f35ecfcf298298becddf5c0a667e0154fa9f1`.
