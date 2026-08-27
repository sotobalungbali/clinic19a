# ClinicOne — clinic_encounter Odoo 19 CE Review

## Scope
`clinic_encounter` is treated as a functionally finished ClinicOne baseline. This hardening preserves business depth and changes only Odoo 19 compatibility, missing runtime contracts, enterprise UI/security completeness, and documented downstream ownership reconciliation.

Files whose filename begins with digit `0` are user backups and are excluded.

## Important architectural reconciliation
`clinic.consent.template` already exists in the frozen `clinic_treatment_catalog` and is further governed by frozen `clinic_consent_legal`. The Encounter addon therefore extends that exact model in place using an explicit same-name `_name` plus list `_inherit`; it does not redefine canonical identity fields such as template name/category/company/title/validity/treatment.

Encounter retains its own consent-document execution model (`clinic.consent.document`) and only adds encounter-specific template metadata such as procedure applicability, encounter body/footer, witness/guardian policies and encounter risk items.

`clinic.audit.log` remains owned by the current finished Encounter baseline for now. Any ownership reconciliation with future addon `clinic_audit` is deferred to addon #38 and is not performed here.

## Odoo 19 compatibility corrections
- 30 active and 60 total legacy SQL constraints migrated from `_sql_constraints` to `models.Constraint`.
- Active custom naming migrated from `name_get()` to `_compute_display_name()` while preserving labels.
- Active `name_search(..., args=None, ...)` signatures migrated to `domain=None`.
- Active Python action terminology migrated from `tree` to `list`.
- Dead `stock.action_move_form` reference replaced with current `stock.stock_move_action`.
- Existing invoice-line fallback that confused a tax ID with an account ID was removed.
- No active `.read_group(`, `account.analytic.tag`, `qty_done`, or `quantity_done` remains.

## Missing baseline contracts completed
- Two operational transient wizards referenced by existing actions: Encounter Bill and Diagnosis → Procedure Plans.
- Twelve `ir.sequence` codes referenced by `next_by_code()`.
- Consent Document and Clinical Result QWeb PDF reports.
- Clinical Result Released mail template.
- Local actions for all persistent Encounter models.
- Human-friendly navigation helpers for nested One2many rows.

## Enterprise UI
41 persistent custom models have Search/List/Form coverage. Thirteen primary clinical models receive workflow-first forms with lifecycle statusbars where real states exist, action buttons, smart navigation, structured notebooks and One2many row navigation. Encounter and Procedure Session also have Calendar views.

## Security
Local persistent models and the two wizards receive internal-user ACL coverage. Company-scoped local models receive ORM company record rules. Canonical `clinic.consent.template` security remains owned upstream. No Public or Portal ACL is introduced by this addon.

## Cross-addon installation resilience
Manifest-loaded XML does not hard-reference sibling ClinicOne presentation XML-IDs. `clinic_encounter` always installs its own local root menu. A defensive `post_init_hook` reparents the root under `clinic_base.menu_root` when that XML-ID exists in the installed database revision; otherwise the Encounter root remains usable independently.

## Dependency repairs
Original dependencies are preserved. `stock` is added because active source directly creates/opens `stock.picking` and `stock.move`. `web` is added because the addon now owns QWeb report templates using the web report layout.

## Validation status
The bundled machine guardrail must report `PASS: 15 / 15 OWNER HARD GATES`. Source/static PASS is not runtime completion. Target-PC Odoo 19 install/upgrade is mandatory before the addon can be marked FROZEN.

## Runtime repair — explicit Many2many relation identifier

The Diagnosis → Procedure Plans wizard previously relied on Odoo's implicit
Many2many relation-table naming. Its effective relation name was 67 characters,
which exceeds Odoo/PostgreSQL's 63-character identifier limit.

The field now uses the explicit schema:

- `relation="clinic_diag_plan_proc_wiz_rel"`
- `column1="wizard_id"`
- `column2="procedure_id"`

The machine guardrail now audits effective Many2many relation identifiers for
the entire active addon.

