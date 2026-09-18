# ClinicOne `clinic_wallet` — Source / Static Validation

Baseline: user-supplied ClinicOne source bundle dated 2026-08-20. Backup files whose **basename starts with a digit (`0`–`9`)** are excluded from the authoritative baseline.

## Project identity

- Project: ClinicOne
- Addon: `clinic_wallet`
- Target: Odoo 19 CE
- Version: `19.0.3.0.0`
- Dependency direction: downstream through `clinic_ap`; no dependency on future ClinicOne finance/accounting/reporting addons.

## Preservation audit

- Baseline Python method names: 115
- Corrected addon Python method names: 185
- Missing baseline method names: **0**
- Baseline declared field names: 99
- Corrected local declared field names: 110
- Apparent missing local declaration: `res.partner.wallet_balance` only; this field is intentionally **owned by `clinic_patient`** and is consumed/extended rather than redeclared.
- Stable Billing APIs preserved: `reserve_funds`, `release_reserved`, `validate_reserved_to_posted`.
- Historical settings/helper names preserved as compatibility wrappers without reviving obsolete ownership/storage patterns.

## Odoo 19 contracts

- Executable production source contains **0 legacy `_sql_constraints`** declarations.
- Two uniqueness constraints are implemented using `models.Constraint`.
- Wallet account fallback uses `account.account.company_ids` company membership.
- Wallet membership compatibility fields use `membership.plan`, matching the installed Clinic Membership V6 source.
- No executable reference to the removed `clinic.membership.tier` model.
- No executable `ir.property` storage/read contract.

## Structural / UI / security validation

- Persistent Wallet-owned models: **5**
- Search views: **5 / 5**
- List views: **5 / 5**
- Form views: **5 / 5**
- Transaction Pivot + Graph: present
- ACL rows: **15**
- Backend workflow transition protection: present
- Portal own-record rules: present
- Multi-company record rules: present
- PDF Wallet Statement: present
- Cron: expiry notification + rule expiry processing
- Regression test methods: **30**
- ClinicOne direct dependencies present in supplied source bundle: **22 / 22**
- Custom Wallet XML-ID references resolved against the supplied upstream bundle: **0 missing**

## Enterprise Development Guardrail

All user-defined hard gates pass at source/static level:

- HARD GATE 0 — Project Identity Preflight: PASS
- HARD GATE 1 — Codex Bukan Architect: PASS
- HARD GATE 2 — Existing Function Preservation: PASS
- HARD GATE 3 — Enterprise Completeness Bukan Sekadar Test Pass: PASS
- HARD GATE 4 — Full Structural Inventory: PASS
- HARD GATE 5 — Human-Friendly Coding Structure: PASS
- HARD GATE 6 — Professional Form Design: PASS
- HARD GATE 7 — UI/UX Matrix per Model: PASS
- HARD GATE 8 — Search View Wajib: PASS
- HARD GATE 9 — List View Enterprise Quality: PASS
- HARD GATE 10 — Security Tidak Boleh Dikalahkan UI: PASS
- HARD GATE 12 — Code Style Human Friendly: PASS
- HARD GATE 13 — Comments Yang Berguna: PASS
- HARD GATE 14 — Codex Retry Limit: PASS
- HARD GATE 15 — Enterprise Completeness Matrix: PASS

## Runtime status

**PENDING.** Source/static PASS does not assert install/upgrade, Odoo registry, view loading, accounting posting, portal, multi-company, scheduler, PDF rendering, or end-to-end Billing/Wallet behavior on the target Windows Odoo database.




