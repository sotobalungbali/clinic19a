# ClinicOne v48 — source journeys and readiness closure

This release supplies the five missing report-source families identified by v47. It preserves the 35-generator registry and all existing features. `management.reports` explicitly owns the supplemental demo references; the production addons retain their models and workflows.

## Upgrade the existing presentation database

1. Stop Odoo. Replace the six complete addon folders from this ZIP (do not merge individual files).
2. Start Odoo, Update Apps List, then upgrade in this order:
   - clinic_inventory 19.0.1.0.3
   - clinic_encounter 19.0.1.0.1
   - clinic_membership 19.0.3.0.7
   - clinic_wallet 19.0.3.0.6
   - clinic_dashboard 19.0.1.0.2
   - clinic_demo 19.0.1.0.48
3. Open the SAME Demo Run with the completed 35 checkpoints. Keep Demo Safe Mode enabled.
4. Click Refresh Compatibility. Recognized completed acceptance-stage runs adopt the build contract without resetting records or checkpoints.
5. Click **Complete Source Journeys**. This creates/reuses five source journeys, refreshes the 19 reports, six demo Dashboard snapshots and Analytics evidence, and automatically runs full Validate.
6. Inspect the current Validation Results. The expected successful result is **READY FOR DEMO** with current source evidence. Repeating Complete Source Journeys must reuse the source identities, posted Wallet journal and stock consumption.

Do not Reset Dataset or create a replacement presentation run. Generate Full alone skips Done checkpoints and therefore does not invoke this upgrade closure. On a genuinely new database, the regular report generator invokes the same source producer before report generation.

## Exact source evidence

| Report | Record/model | Expected business state and evidence |
|---|---|---|
| FIN-INS | DEMO-SOURCE-AUTH-001 / clinic.insurance.authorization | Prepared manual request; one positive service line; linked synthetic policy; no external payer submission |
| OPS-INV | DEMO-SOURCE-USAGE-001 / clinic.treatment.product.usage | Done; one unit consumed; explicit receipt of 10 donated zero-cost units precedes consumption |
| OPS-MEM | DEMO-SOURCE-MEMBER-001 / membership.contract | Draft paid-plan enrollment with positive contract value and explicit one-year term; awaiting operational confirmation |
| OPS-WALLET | DEMO-SOURCE-TOPUP-001 / clinic.wallet.transaction | Posted top-up 500000 in company currency; balanced journal DW48/{anchor year}/0001; dedicated accounts and journal |
| CLN-PROC | DEMO-SOURCE-PROC-001 / clinic.procedure.session | Done; positive execution window inside DEMO-ENC-LIVE-001 planned encounter window |

Membership enrollment is not a paid/active membership. Insurance Prepared is not payer approval, eligibility or claim settlement. Those distinctions are reflected in the report's separate active/approved metrics. Required primary report counts remain mandatory; they are never fabricated or waived.

## Whole-path contract

- Compatibility pins all 41 ClinicOne companions; five changed owners are bundled.
- Explicit reference keys, company/branch, actor groups, model fields/comodels, workflow methods and all consumer refresh APIs are checked before business mutation.
- Stock uses Odoo 19 origin and picked contracts. Native done workflows run before explicit business dates are applied to the newly created zero-value demo moves.
- Membership create no longer eagerly evaluates its sequence when an explicit name exists.
- Wallet owner API accepts a complete explicit posting name/date/liability account contract. It verifies Manager authority and account scope. Existing callers without these arguments retain their existing behavior.
- Dashboard owner API permits in-place reconstruction only of explicitly named DEMO snapshots belonging to the same board/company/branch. Regular production snapshots retain their normal immutable lifecycle.
- A native run row lock prevents concurrent generation/closure. A savepoint makes source creation and evidence refresh atomic; failure cannot leave a partially posted supplement committed.
- Existing posted journals and stock receipts/consumption are reused, never reset to draft. Drift from explicit source values fails closed.
- Report details must point to the exact new source record, so unrelated production transactions cannot satisfy the five source evidence checks.
- Source evidence is retained on reset. Unknown models/states still block reset; no generic destructive fallback was added.
- Native audit timestamps record execution time. Business dates, identifiers and amounts are explicit and anchor-based.

## Acceptance status

Source/static and isolated behavioral tests are recorded in TEST_REPORT_48.md. Native Odoo generation, fresh database, browser smoke, and destructive reset/regeneration have NOT been executed here. The local Odoo source checkout cannot start because its Python dependencies are incomplete (Babel unavailable). A code/static pass must not be represented as a target-database runtime pass.

The package closes the identified five report-source gaps in code. Overall enterprise acceptance remains pending target validation and the separate disposable-database acceptance rehearsals required by Master Prompt 23.

Procedure execution-log names and event dates are explicitly supplied for Create/Start/Done; related execution/follow-up activity deadlines derive from the session window. The owner retains normal defaults for existing callers.













