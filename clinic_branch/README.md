# ClinicOne Branch Management

Full corrected Odoo 19 CE addon for ClinicOne development item #36.

This build preserves the branch contracts already consumed by the ClinicOne source snapshot,
converts legacy SQL constraints to `models.Constraint`, activates branch security, and replaces
the legacy scaffold UI with enterprise branch/location operations.

Run static guardrail:

```bash
python3 tools/clinic_branch_guardrail.py
```
