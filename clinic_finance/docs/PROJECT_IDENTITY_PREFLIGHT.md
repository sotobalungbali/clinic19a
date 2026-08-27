# Project Identity Preflight — HARD GATE 0

- PROJECT: ClinicOne, Odoo 19 Community Edition.
- ADDON: `clinic_finance`.
- AUTHORITATIVE FUNCTIONAL BLUEPRINT: ClinicOne 39 Addons specification.
- BLUEPRINT SCOPE: cash management, journals, internal clinic financial operations.
- VERIFIED UPSTREAM THROUGH: `clinic_wallet`.
- PRESERVATION RULE: Billing/AR/AP/Wallet/accounting ownership is consumed, never silently moved or duplicated.
- ALLOWED CHANGE: create a new Finance orchestration addon and safe inherited fields on standard Odoo journal/move.
- FORBIDDEN CHANGE: dependency on future `clinic_accounting`; modifications/deletions in frozen upstream addons.
- CURRENT STATUS: source/static build only; Odoo runtime install gate pending.
