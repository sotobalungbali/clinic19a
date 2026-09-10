# ClinicOne Demo Final Release Manifest

## Release identity

- Addon: `clinic_demo`
- Release: `19.0.1.0.46`
- Registry: 35 bounded generators
- Runtime baseline: `19.0.1.0.45`, generation completed on the same Demo Run
- Code policy: documentation/release-only increment; generator behavior frozen

## Package inventory

- Full installable addon source: models, services, generators, wizard, views,
  security, data, tests, tools and documentation.
- 94 Python and 10 XML addon source files at release audit.
- 41 explicit ClinicOne dependencies from `__manifest__.py`.
- No numeric-prefix backups, caches, compiled Python or debug artifacts.

## Scenario matrix

| Scenario family | Representative scenario | Evidence |
|---|---|---|
| Foundation/workforce | `SCN-FOUNDATION-01`, `SCN-WORKFORCE-01` | Company, branches, users, staff, doctors |
| Patient/history | `SCN-PATIENT-NEW-01`, `SCN-PATIENT-RET-01` | Personas and longitudinal records |
| Booking/arrival | `SCN-REFERRAL-01`, `SCN-BOOKING-TODAY-01`, `SCN-QUEUE-01` | Referral, booking, appointment, queue |
| Clinical | `SCN-ENCOUNTER-01`, `SCN-SESSION-01`, `SCN-IMAGING-01`, `SCN-EMAR-01`, `SCN-CARE-01`, `SCN-TELE-01` | Core and advanced clinical journeys |
| Commercial | `SCN-BILLING-01`, `SCN-AR-01`, `SCN-AP-01` | Billing, accounting, receivable, payable |
| Exception | `SCN-FEEDBACK-01`, `SCN-INCIDENT-01`, `SCN-QUALITY-01`, `SCN-API-01` | Recovery, quality, incident, safe failure |
| Management | `SCN-REPORT-01`, `SCN-DASH-01`, `SCN-ANALYTICS-01` | Reports, KPI, dashboard, forecast |
| Acceptance | Prompt 23 validation scenarios | Structural through reset/regeneration gates |

## Dependency map

`clinic_demo` orchestrates owner APIs from 41 declared ClinicOne addons. It owns
only demo control/provenance records; clinical, operational and financial records
remain owned by their respective addons. Dependency order is enforced through
the generator registry and explicit `depends_on`, never installation order or a
mutable production sequence.

## Validation evidence

- Source-contract suite: 165 PASS.
- Enterprise guardrail: PASS.
- Composite parse: 908 Python + 516 XML, zero failures on the final source set.
- ZIP integrity and SHA-256 are verified when the distributable is built.
- Native database evidence required for final presentation: `Validate Dataset`
  must return **READY FOR DEMO**.

## Fresh-database acceptance route

1. Create a disposable database and install the full ClinicOne dependency suite.
2. Install `clinic_demo`; enable Demo Generation and Safe Mode.
3. Create one Full Enterprise run with a fixed anchor date and seed.
4. Refresh Compatibility; require Compatible.
5. Generate Full; require 35 Done checkpoints.
6. Validate; require READY FOR DEMO.
7. Browse the 14 executive chapters without manual data entry.

Runtime generation on the established database is proven. Destructive reset and
fresh-DB rehearsal remain environment-executed acceptance evidence; they are not
falsely reported as executed by static source analysis.

## Reset and regeneration

- Never reset the established presentation run.
- On a disposable run, open Reset, review Preview, type the exact confirmation,
  and execute the ownership/policy-aware plan.
- Immutable/legal evidence is retained; financial evidence uses correction or
  reversal; unknown models/states block reset.
- `Regenerate Missing` dispatches only to the generator stored on the missing
  reference. Stable `(run_id, demo_key)` identity prevents duplicate repair.

## Known limitations

- Email, WhatsApp, webhook, portal invitation and external API delivery are
  intentionally suppressed in Safe Mode.
- Production-like load, concurrency, external provider delivery and destructive
  reset proof require a disposable environment and are outside the presentation run.
- KPI/report meaning depends on the configured anchor date, company and branch scope.

## Release notes

`19.0.1.0.46` completes MASTER PROMPT 24 documentation and packaging. It adds no
generator, no production sequence and no business-data mutation. It supplies the
executive script, completeness matrix, final audit evidence and release guidance.
