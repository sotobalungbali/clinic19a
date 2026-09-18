# v51 verification evidence

- 190 source-contract / isolated behavioral unittest checks: PASS.
- Actor tests execute role reconciliation: Products/Create present without System Administrator; repeat is idempotent; missing role fails before partial assignment; delegated Product Template preflight and preparation order checked.
- Existing historical-checkpoint migration tests include v50-to-current adoption and the reported v45 Resources alias across the full 35-generator registry.
- Native Odoo product ACL source verified: product.group_product_manager has read/create/write for category, template and variant. Exact ACL rows and source digest included in validation_51/native_product_acl.json.
- Six static guardrails: clinic_demo, clinic_inventory, clinic_encounter, clinic_membership, clinic_wallet, clinic_dashboard: PASS.
- Entire composite: 917 Python AST parses + 516 XML parses, zero errors.
- All 41 companion manifest versions and canonical suite fingerprint: MATCH.
- Raw results in validation_51. ZIP CRC and per-file SHA-256 checked during packaging.

Authoritative source: clinic19a(20260915-034240).md; SHA-256 7d2561b386c6526edba7af76e0287d2d438dec8a7c976bff9b97bd66a1c3aafe. The supplied Odoo log confirms the four Product Category/Variant permission failures.

These are source/static and isolated behavioral checks, not 190 native Odoo transaction tests. Native upgrade, full source generation, final Validate, concurrency and disposable-database reset/regeneration were not executed here. No target runtime PASS is asserted. Earlier release reports are historical.










