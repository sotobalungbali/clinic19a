{
    "name": "ClinicOne - Accounting",
    "summary": "Enterprise accounting governance, clinic ledgers, journal adjustments, period close, and financial statements.",
    "description": """
ClinicOne Accounting
====================
Accounting governance layer for ClinicOne on Odoo 19 Community Edition.

The addon integrates Clinic Finance with the standard Odoo accounting ledger rather
than creating a parallel accounting engine.

Enterprise scope:
- Clinic accounting ledgers built as reporting/control scopes over account.journal,
  account.account, account.move, and account.move.line;
- governed adjustment journal vouchers with Submit / Approve / Post workflow;
- reverse source classification for Billing, AR, AP, Wallet, Finance, and manual
  accounting adjustments;
- period-close preflight and controlled integration with Odoo 19 native fiscal lock date;
- persistent Trial Balance, General Ledger, Profit & Loss, Balance Sheet,
  Journal Audit, and Clinic Source Summary statements;
- source drill-down, PDF reporting, multi-company and multi-branch filters;
- optional automated prior-month Trial Balance snapshots.

Ownership boundary:
- Odoo account.move / account.move.line remain the legal accounting ledger;
- clinic_finance remains owner of treasury and internal finance operations;
- clinic_billing / clinic_ar / clinic_ap / clinic_wallet remain owners of their
  operational financial documents;
- clinic_l10n_id remains downstream for Indonesian localization and tax rules.
""",
    "version": "19.0.1.0.0",
    "author": "ClinicOne",
    "website": "https://clinic.one",
    "license": "LGPL-3",
    "category": "ClinicOne/Accounting",
    "application": True,
    "installable": True,
    "auto_install": False,
    "depends": [
        "base",
        "base_setup",
        "mail",
        "web",
        "contacts",
        "account",
        "analytic",
        "clinic_base",
        "clinic_audit",
        "clinic_branch",
        "clinic_billing",
        "clinic_ar",
        "clinic_ap",
        "clinic_wallet",
        "clinic_finance"
    ],
    "data": [
        "security/clinic_accounting_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "data/cron_data.xml",
        "views/accounting_ledger_views.xml",
        "views/accounting_adjustment_views.xml",
        "views/accounting_close_views.xml",
        "views/accounting_statement_views.xml",
        "views/account_move_views.xml",
        "views/res_config_settings_views.xml",
        "report/accounting_statement_templates.xml",
        "report/accounting_statement_report.xml",
        "report/accounting_close_templates.xml",
        "report/accounting_close_report.xml",
        "views/menu_views.xml"
    ],
    "demo": [],
}
