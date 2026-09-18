




# CLINIC_DEMO_CORE_PATCH_LEDGER

## clinic_demo 19.0.1.0.44 + clinic_dashboard 19.0.1.0.1 + clinic_analytics 19.0.1.0.1 — MASTER PROMPT 22

- Adds explicit `management.dashboard` and `management.analytics` generators.
- Creates six Dashboard snapshots from the 19 governed Prompt-21 reports, then
  three anchor-relative Analytics snapshots and one transparent 12+3 booking forecast.
- Extends `_refresh_snapshot()` with optional `snapshot_name`; existing callers
  retain `/` and production sequence behavior, while demo calls use stable
  `DEMO-DASH-SNAPSHOT-*` identities without consuming that sequence.
- Keeps Analytics child ACLs read-only and routes snapshot-line and forecast-point
  mutations through the owning workflow's explicit internal context with bounded
  elevation, without exposing child mutation operations over RPC.
- Preflights models, methods, all six boards, 17 KPI adapters, actor ACLs,
  company scope, Safe Mode, and disabled integration-event publication before
  business evidence is generated.

## clinic_demo 19.0.1.0.41 — MASTER PROMPT 21 reports

- Adds one `management.reports` checkpoint and executes all 19 native ClinicOne
  report definitions through `clinic.report.run.action_generate()`.
- Uses fixed `DEMO-REPORT-*` identities and an anchor-relative reporting window;
  no mutable Report Run sequence is consumed by the demo generator.
- Preflights report models, 19 definition XML IDs, engine methods, actor ACLs,
  company scope, and owner workflow before creating the first report run.
- Metrics/details remain owned by `clinic_reports`; the generator validates
  source provenance, CSV output, and non-zero primary metrics only where an
  actual upstream transaction is part of the registered dataset.

## clinic_demo 19.0.1.0.40 — MASTER PROMPT 20 future pipeline

- Adds one bounded `operations.future_pipeline` checkpoint with explicit
  dependencies on the existing Booking, advanced-clinical, and Prompt-19 owners.
- Preflights the complete Booking/Care/Post-Care/Telemedicine contract before
  creating six internal follow-up tasks at T+1/+7/+14/+30/+60/+90.
- Uses explicit `DEMO-FUT-FOLLOWUP-*` references and disables outbound delivery;
  no production sequence, wall-clock schedule, `sudo()`, SQL, or commit is used.

## clinic_demo 19.0.1.0.39 — MASTER PROMPT 19 exception closure

- Registers three bounded generators in explicit order: Feedback service
  recovery → Quality nonconformity/Incident investigation → isolated synthetic
  API failure evidence.
- Uses stable `DEMO-*` document names before owner create hooks, avoiding every
  mutable production document sequence.
- Runs a single whole-path field/method/comodel/ACL/company/branch preflight
  before Prompt-19 business mutation.
- Requires Demo Safe Mode and never invokes webhook queue, delivery, email,
  marketing dispatch, portal invitation, or another external side effect.
- Adds progressive and failed-prefix contract adoption after the frozen
  Prompt-18 boundary without resetting completed data.

## clinic_demo 19.0.1.0.38 + clinic_ap 19.0.3.0.3 — Odoo 19 purchase-UoM closure

- Removes every Prompt-18/AP runtime dependency on the retired
  `product.product.uom_po_id` field.
- Uses the native Odoo 19 `product.uom_id` contract consistently in the demo
  AP line and the AP owner's interactive onchange path.
- Adds whole-path preflight coverage for `product.product.uom_id → uom.uom`
  before vendor/AP/accounting records are mutated.
- Keeps the explicit `DEMO-AP-001` business key, so the production AP sequence
  remains unused by the demo journey.

## clinic_demo 19.0.1.0.37 + clinic_billing 19.0.3.0.5 — accounting-line relation closure

- Replaces the invalid cross-model inverse `move_line_ids` relation with the
  read-only related mirror `move_id.line_ids`.
- Prevents ORM inverse-cache `KeyError` while the Billing owner creates and
  posts its authoritative `account.move`.
- Re-fingerprints the complete installed-suite contract; Prompt-18 checkpoint
  adoption remains deterministic and posted ledgers remain immutable.

## clinic_demo 19.0.1.0.36 — Prompt-18 Contact actor closure

- Adds Odoo's least-privilege `base.group_partner_manager` (`Contact/Creation`)
  entitlement to the synthetic enterprise manager before the whole-path ACL
  preflight.
- Keeps Contact access operation-exact: the AP journey reads Contacts and creates
  one dedicated synthetic vendor; it does not rewrite an existing Contact.
- Preserves the exact failed `commercial.billing` checkpoint adoption and every
  Prompt 1–17 completed checkpoint on the same Demo Run.

## clinic_demo 19.0.1.0.35 + clinic_billing 19.0.3.0.4 — Prompt-18 whole-path closure

- Resolves every Prompt-18 business record through the functional manager in an
  explicit company/branch context; the technical operator is never the hidden
  business actor.
- Reconciles all generated demo branches onto the synthetic enterprise manager
  from exact provenance IDs before reading branch-protected records.
- Completes Prompt-16's exact deferred Treatment Session billing line from the
  Treatment owner's service-product and price APIs.
- Replaces Clinic Billing's zero-value accounting placeholder with a complete
  mapping of real Billing lines, quantities, effective prices, taxes, UoM, and
  income accounts.
- Expands whole-path preflight through Session/Line ACL, membership, journals,
  and income/expense/receivable/payable account availability.

## clinic_demo 19.0.1.0.34 + clinic_ar 19.0.3.0.3 — Prompt-18 deterministic finance

- Adds three ordered generators for Treatment Session billing, billing-owned AR,
  and supplier AP, sharing one whole-path runtime preflight.
- Uses official owner lifecycles and Odoo posting; no ledger is hardcoded and no
  posted financial document is deleted by Reset.
- Adds exact progressive and failed-prefix adoption on the same Demo Run.
- Adds a narrow owner context for deterministic synthetic AR identity while
  ordinary production AR numbering remains unchanged.

## clinic_demo 19.0.1.0.33 — Prompt-17 semantic prerequisite closure

- Adds a deterministic, signed general-care consent before the confidential
  Care Plan is created and activated; the consent is retained on the plan.
- Extends whole-path preflight beyond model shape and ACL into record semantics:
  published consent templates and care protocol, protocol steps, actor company
  alignment, Doctor user identity, and Telemedicine eligibility.
- Makes the Telemedicine session company-scoped without a Branch, eliminating
  hidden dependence on mutable production branch-policy configuration.
- Retains stage-aware continuation on the same Demo Run. Prompt 1–16, Imaging,
  and eMAR remain frozen; no Reset or production sequence is used.

## clinic_demo 19.0.1.0.32 — eMAR medication-line ownership closure

- Enforces the owner addon's explicit XOR contract for every synthetic
  medication line: a line belongs to one Prescription or one Order, never both.
- Keeps Prescription provenance on `clinic.emar.order.prescription_id`; the
  execution Order line carries only `order_id`, avoiding duplicate ownership.
- Adds an AST regression gate over every `_line_values` call in the Prompt-17
  eMAR generator so a zero-header or dual-header line cannot pass packaging.
- Preserves the same Demo Run and the completed Prompt 1–16 / imaging prefix;
  no Reset and no mutable production sequence are required.

## clinic_demo 19.0.1.0.31 + clinic_emar 19.0.3.0.3 — temporal API closure

- Replaces the nonexistent `fields.Date.timedelta` call in the eMAR
  prescription-expiry compute with `datetime.timedelta` without bypassing the
  stored compute or changing its default 30-day validity.
- Adds an AST hard gate over all six Prompt-17 owner addons. Unknown
  `fields.Date` / `fields.Datetime` helpers now fail packaging before runtime.
- Updates the exact suite version vector and fingerprint so compatibility
  requires the repaired eMAR source and installed database version together.

## clinic_demo 19.0.1.0.30 — Prompt 17 field-level actor closure

- Closes the Odoo 19 field-security boundary exposed when owner imaging logic
  reads `doctor_id.work_contact_id` as the synthetic Doctor.
- All Prompt-17 functional-actor recordsets now use explicit no-bulk-prefetch
  context, preventing unrelated private `hr.employee` fields from being read.
- Adds exact actor/reference/field read probes to the whole-path preflight, so
  downstream field-level drift is rejected before the first business write.
- Does not widen employee-field permissions, use `sudo()`, or modify any
  ClinicOne production addon.

## clinic_demo 19.0.1.0.29 — Prompt 17 stage-aware deterministic resumption

- Runs the identical whole-path runtime preparation at the start of every
  Prompt-17 generator, including when a run resumes after an earlier checkpoint.
- Replaces the imaging-only failed-run exception with an explicit ordered
  Prompt-17 stage contract. Adoption requires an exact completed prefix, one
  failed stage, and no committed references in the failed-or-later suffix.
- Preserves completed Prompt 1–16 and earlier Prompt-17 checkpoints on the same
  Demo Run; no mutable production sequence or implicit process history decides
  the resume point.

## clinic_demo 19.0.1.0.28 — Prompt 17 whole-path runtime closure

- Corrected the installed eMAR compatibility schema to
  `patient_id=res.partner` / `doctor_id=hr.employee`, retaining canonical
  ClinicOne identities in `clinic_patient_id` / `clinic_doctor_id`.
- Replaced blanket ACL probing with an exact actor/model/operation matrix,
  including owner-method side effects and immutable evidence semantics.
- Reconciles source-declared eMAR Manager access only on the synthetic manager,
  allowing deterministic order confirmation whether auto-scheduling is enabled
  or disabled.
- Creates the Secure Thread with its final deterministic identity before the
  Session workflow, eliminating hidden production-sequence consumption.

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


## MASTER PROMPT 15 — clinic_demo 19.0.1.0.20

No ClinicOne owner addon is modified.

The active Queue/Token/Triage/Vitals contracts already expose the lifecycle and
computed abnormality APIs required by Prompt 15. `clinic_demo` adds only bounded
orchestration, stable references, source-valid identity bridges, model-specific
reset policies and progressive adoption from a completed Prompt-14 Demo Run.

No `sudo()` is added by the Prompt-15 generator, no direct SQL is used, no
technical audit timestamp is backdated, and no computed abnormal-vital flag is
written directly.


## clinic_demo 19.0.1.0.21 — Prompt 15 Appointment schema runtime repair

Concrete runtime evidence: `MASTER PROMPT 15 preflight failed: clinic.appointment
missing fields treatment_id`.

Root cause is confined to `clinic_demo`: Prompt-15 preflight inherited a dormant /
legacy Appointment assumption even though `clinic_doctor` owns the canonical active
`clinic.appointment` contract. No owner addon patch is required.

Corrections remove `clinic.appointment.treatment_id`, assert canonical relational
comodels, compare Appointment/Triage patients in the same `clinic.patient` identity
domain, retain treatment on Booking/Queue contracts, and permit repair adoption only
for a failed `operations.queue_triage` checkpoint with no Prompt-15 references.

No `sudo()`, direct SQL, terminal-state bypass, audit-timestamp backdating, ACL
weakening, or owner schema change is introduced.


## clinic_booking 19.0.1.0.5 + clinic_demo 19.0.1.0.22 — Prompt 15 patient identity bridge repair

Concrete runtime failure:
`operations.queue_triage: 'res.partner' object has no attribute 'partner_id'`.

Root cause:
`booking.booking.patient_id` is `res.partner`, while canonical
`clinic.appointment` owns both `partner_id -> res.partner` (required contact)
and `patient_id -> clinic.patient` (optional clinical profile). The old
Booking->Appointment bridge dereferenced `rec.patient_id.partner_id` and also
copied a raw `res.partner` integer into the `clinic.patient` comodel.

Targeted owner correction:
- Booking partner maps directly to Appointment `partner_id`;
- exact same-company `clinic.patient` is resolved by `partner_id` for
  Appointment `patient_id`;
- ambiguous multiple clinical profiles fail explicitly;
- no Queue/Triage owner change, ACL weakening, SQL, or direct state bypass.

`clinic_demo` only advances its cumulative build/version compatibility contract
to expect `clinic_booking 19.0.1.0.5`.


## clinic_queue_room 19.0.1.0.1 + clinic_demo 19.0.1.0.23 — Prompt 15 Odoo 19 Domain repair

Concrete runtime failure:
`operations.queue_triage: 'tuple' object has no attribute 'lower'`.

Root cause:
`clinic.queue._find_stage_by_mapped_state()` used a malformed nested domain
shape where `"|"` and two conditions were wrapped as one three-item tuple.
Odoo 19 parsed that outer tuple as a simple condition and attempted `.lower()`
on its second item, which was another tuple.

Targeted owner repair:
use the normal prefix OR token followed by the two stage conditions.

No Queue lifecycle semantics, ACL, record rule, direct SQL, direct state bypass,
or Prompt-01 through Prompt-14 data is changed. `clinic_demo` only synchronizes
its owner-version compatibility contract.


## clinic_treatment_session 19.0.2.0.4 + clinic_demo 19.0.1.0.25 — Prompt 16 Treatment Session business-API ACL repair

Concrete runtime failure:
`operations.treatment_session` was denied read access to `ir.actions.act_window`
while the Booking owner action ran under the linked clinician.

Targeted repair:
- owner business-only `generate_treatment_sessions()`;
- existing UI action wrapper preserved;
- Prompt 16 calls the business API;
- no ACL expansion, `sudo()` bypass, state bypass, direct SQL, or prior-Prompt data change;
- same Failed Demo Run adoption is allowed only when Encounter is Done,
  Treatment Session is Failed, and no Treatment Session references committed.


## clinic_demo 19.0.1.0.27 — MASTER PROMPT 17 Advanced Clinical Workflows

Four bounded generators implement the source-owned advanced journeys:
`clinical.imaging`, `clinical.emar`, `clinical.care_postcare`, and
`clinical.telemedicine`. They use production workflow methods, deterministic
business dates, explicit actor users, provenance bindings, and non-destructive
clinical/legal reset policies. Billing remains owned by MASTER PROMPT 18.


















