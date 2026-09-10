{
    "name": "ClinicOne - Accounts Payable",
    "summary": "Enterprise supplier payables, vendor bills, 3-way match, aging, cashflow, and payment governance.",
    "description": '''
ClinicOne Accounts Payable
==========================
Enterprise Accounts Payable for ClinicOne on Odoo 19 Community Edition.

Capabilities include governed AP documents, supplier invoice creation, purchase/receipt
three-way matching, payment-term policy, vendor exposure controls, aging snapshots,
cashflow projections, Billing cost traceability, accounting settlement navigation,
multi-company security, and integration-event outbox.
''',
    "version": "19.0.3.0.3",
    "author": "ClinicOne",
    "website": "https://clinic.one",
    "license": "LGPL-3",
    "category": "ClinicOne/Finance",
    "application": True,
    "installable": True,
    "auto_install": False,
    "depends": [
        "base",
        "mail",
        "contacts",
        "uom",
        "analytic",
        "product",
        "account",
        "purchase",
        "stock",
        "stock_account",
        "clinic_base",
        "clinic_treatment_catalog",
        "clinic_billing",
        "clinic_ar",
    ],
    "data": [
        "security/clinic_ap_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "data/cron_data.xml",
        "views/ap_views.xml",
        "views/ap_line_views.xml",
        "views/aging_views.xml",
        "views/cashflow_views.xml",
        "views/integration_event_views.xml",
        "views/payment_term_views.xml",
        "views/res_config_settings_views.xml",
        "data/optional_view_bridge.xml",
        "views/menu_views.xml",
    ],
    "demo": [],
}
