




# MASTER PROMPT 11 — Clinical Catalog, Package & Consent Masters

## Status
Source/static implementation complete; runtime acceptance remains pending until the upgraded addon is executed in Odoo 19 CE.

## Source-driven scope
Prompt 11 registers three bounded generators in the already-governed scenario registry:

1. `master.catalog` — treatment categories/services, source-native pricing, care protocol masters, imaging types/protocol/preparation, medication/eMAR profiles and native product bridges.
2. `master.consent` — governed legal consent templates, checklist items and published versions; treatment consent requirements are enabled only after usable templates exist.
3. `master.commercial` — package policy/pricing/package components, membership plans/benefits, insurer/insurance-plan/rule masters, and wallet usage-rule templates.

## Explicit non-scope
No booking, encounter, treatment session, consent form/signature, imaging request/result, medication order/administration, package allocation/usage, membership contract, insurance policy/authorization/claim, wallet account/transaction, invoice, payment or journal entry is created by Prompt 11.

## Stable reference families
- `DEMO-CAT-*`, `DEMO-TREAT-*`, `DEMO-PRICE-RULE-*`
- `DEMO-PROTOCOL-*`, `DEMO-IMTYPE-*`, `DEMO-MED-PROFILE-*`
- `DEMO-CONSENT-TPL-*`, `DEMO-CONSENT-VERSION-*`
- `DEMO-PKG-*`, `DEMO-MEM-PLAN-*`, `DEMO-INS-PLAN-*`, `DEMO-WALLET-RULE-*`

Business numbering remains owned by the relevant ClinicOne/Odoo sequence. Demo references do not replace business numbers.

## Demo Safe Mode
Package activation and membership-plan activation use official owner business actions. Any resulting local integration/outbox events are immediately transitioned to source-supported cancelled/ignored safe states and are registered as demo-owned technical records. No external dispatcher is invoked by Prompt 11.

## Branch/company applicability
The source-actual catalog/package/membership masters are company-scoped. Prompt 11 does not invent branch fields on models that do not own them. Insurance plan masters use the source-owned `branch_id`; branch-specific operational applicability is completed by resource/booking/transaction generators in later prompts.

## Accounting boundary
Prompt 11 establishes billable service products, product mappings and price/reference masters needed by downstream billing. It deliberately does not create or post accounting documents. Journal/account/tax execution belongs to Prompt 18 and must continue using source-supported accounting workflows.

## Reset policy
Reusable masters are normally deactivated. Frozen/versioned child structures use `FRESH_DB_RESET_ONLY`. Demo-owned safe local outbox/checklist rows use child-first delete-safe handling where source semantics permit.

## Runtime acceptance target
Existing Prompt-10 run → Upgrade `clinic_demo` → Refresh Compatibility → Compatible → Generate Full as System Administrator → `master.catalog`, `master.consent`, `master.commercial` all DONE → notification reports **8 bounded generators completed**.
























