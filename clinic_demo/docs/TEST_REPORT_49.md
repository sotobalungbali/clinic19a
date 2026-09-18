# v49 verification report

- 183 source-contract and isolated behavioral unittest checks: PASS.
- Seven migration checks cover lagging run versions, supported predecessor pairs, historical scenario rows, pending/failed acceptance, unknown lineage, busy checkpoints, dependency gaps, exact companion compatibility, metadata-only adoption and repeated invocation.
- Guardrails for clinic_demo and the five unchanged source-journey companion owners: PASS.
- Entire supplied composite after repair: 914 Python AST parses and 516 XML parses; zero errors.
- All 41 companion manifest versions and canonical suite fingerprint: MATCH.
- Raw results: validation_49/.
- Registry remains 35 generators. Canonical checkpoint keys and source ownership are retained.

Native Odoo install/upgrade, database migration, generation, concurrency, final Validate and reset/regeneration were not executed here. These tests use source inspection and record doubles; they are not 183 native Odoo transaction tests. The supplied log does not expose the failed run's stored source/version/checkpoint data. Detailed runtime rejection reasons are now retained in compatibility diagnostics.

ZIP file integrity and per-file SHA-256 inventory are verified during packaging. Earlier release reports in this addon are historical and do not supersede this report.

Latest input: clinic19a(20260914-082945).md, SHA-256 bfd0a2595ea03a6128bfb87d1aa129926c09414d97628ca06aefce9eef4f2cf7. Compared with the v48 baseline: all extracted files match after Python AST / harmless outer-whitespace normalization. Latest master/specification attachments are retained as governing inputs.












