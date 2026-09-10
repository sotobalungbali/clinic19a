# clinic_emar — Runtime Repair 2026-08-18 / Release 19.0.3.0.0

## Runtime evidence

The user-supplied `odoo(2).log` shows the current HTTP 500 is caused by:

`psycopg2.errors.UndefinedColumn: column res_company.emar_default_warehouse_id does not exist`

The failure occurs while `website.layout` reads `res.company`. Because Odoo fetches
stored company fields as part of a normal company record read, one missing eMAR
column prevents unrelated Website/QWeb requests from rendering.

This is a source/database schema drift problem with an unnecessarily global blast
radius.

## Root cause in the supplied source

`models/integrations/res_config_settings.py` added six stored operational fields
directly to `res.company`:

- `emar_default_warehouse_id`
- `emar_auto_generate_schedules`
- `emar_require_patient_scan`
- `emar_require_product_scan`
- `emar_require_double_check_high_alert`
- `emar_overdue_grace_minutes`

The Python registry can know those fields before a successful module upgrade has
created their PostgreSQL columns. Since `res.company` is a high-frequency global
model, this can make the whole web client unavailable before the operator can
perform the repair from Apps.

A prior runtime log also evidenced a missing
`clinic_emar_reschedule_wizard` table during the same source/schema transition.

## Full-corrected design

Release `19.0.3.0.0` preserves all six public field names and all business-code
contracts while removing the global schema bomb:

1. The six `res.company.emar_*` fields are now `store=False` computed proxies.
2. Values are persisted in company-scoped `ir.config_parameter` keys.
3. `res.config.settings` explicitly reads/writes those values.
4. `migrations/19.0.3.0.0/pre-10-preserve_company_settings.py` migrates values
   from legacy physical company columns when they exist; it is a no-op when the
   columns never existed.
5. `post-90-verify_schema.py` asserts all eight owned eMAR tables exist after an
   upgrade and that the company proxy fields remain non-stored.
6. The reschedule wizard contains missing-table autovacuum SQL inside a database
   savepoint during the source→upgrade transition.
7. The schedule cron checks its owned tables with PostgreSQL `to_regclass()`
   before searching them, avoiding background SQL failures before schema sync.
8. All XML files are normalized so the XML declaration begins at byte/character
   zero; the supplied baseline had leading blank lines before declarations.
9. The ACL CSV and static guardrail are normalized/hardened against leading
   blank lines/BOM.

## Preservation

No owned eMAR model, clinical workflow, state guard, patient-safety gate,
prescriber governance, inventory integration, account/stock traceability,
security rule, view, smart button, action button, schedule logic, alert logic,
or downstream model contract was removed.

The configuration storage mechanism changed; the public field API did not.

## Acceptance

Runtime PASS still requires target-PC proof:

1. Replace the whole `clinic_emar` folder with release `19.0.3.0.0`.
2. Restart Odoo so the schema-safe company proxies are loaded.
3. Upgrade `clinic_emar` (UI or controlled CLI `-u clinic_emar --stop-after-init`).
4. Confirm the upgrade log has no `UndefinedColumn`, `UndefinedTable`,
   registry-layout traceback, XML `ParseError`, or missing-model error.
5. Restart normally and verify Web/Apps opens.
6. Smoke: Settings → Prescription → safety/prescriber gate → Order → Schedule →
   Administration → Inventory → Alert.
7. Only then freeze the addon.

