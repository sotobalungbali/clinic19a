{
    "name": "ClinicOne - Finance",
    "summary": "Enterprise treasury, cash management, internal finance operations, approvals and liquidity control.",
    "description": """
ClinicOne Finance
=================
Enterprise finance and treasury orchestration for ClinicOne on Odoo 19 Community Edition.

Scope:
- cash/bank operating-account registry mapped to standard Odoo account.journal;
- internal receipts, disbursements, reimbursements and adjustments;
- governed internal cash/bank transfers;
- employee/operational fund requests with approval and disbursement traceability;
- cash-session opening, denomination count, variance and controlled closing;
- treasury-position snapshots combining cash/bank, AR, AP, Wallet liabilities and AP cashflow forecast;
- standard Odoo account.move posting for internal finance movements;
- multi-company and multi-branch governance;
- enterprise Search/List/Form, smart buttons, statusbars, reports and cron automation.

Boundary:
Clinic Finance consumes Billing, AR, AP and Wallet operational results. It does not replace
their ledgers and it does not depend on the future clinic_accounting addon.
""",
    "version": "19.0.1.0.0",
    "author": "ClinicOne",
    "website": "https://clinic.one",
    "license": "LGPL-3",
    "category": "ClinicOne/Finance",
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
        "hr",
        "clinic_base",
        "clinic_branch",
        "clinic_staff",
        "clinic_billing",
        "clinic_ar",
        "clinic_ap",
        "clinic_wallet"
    ],
    "data": [
        "security/clinic_finance_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "data/cron_data.xml",
        "views/finance_category_views.xml",
        "views/finance_account_views.xml",
        "views/finance_transaction_views.xml",
        "views/finance_transfer_views.xml",
        "views/fund_request_views.xml",
        "views/cash_session_views.xml",
        "views/treasury_position_views.xml",
        "views/integration_views.xml",
        "views/res_config_settings_views.xml",
        "report/treasury_position_templates.xml",
        "report/treasury_position_report.xml",
        "views/menu_views.xml"
    ],
    "demo": [],
}
