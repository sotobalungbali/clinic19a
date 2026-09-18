{
    "name": "ClinicOne Patient Wallet",
    "version": "19.0.3.0.6",
    "summary": "Enterprise patient prepaid wallet, reservations, settlement, controls and accounting",
    "description": """
ClinicOne Patient Wallet
========================
Enterprise patient/customer wallet for ClinicOne on Odoo 19 CE.

Key capabilities:
- one wallet per patient/contact and company;
- top-up, redeem, refund, adjustment-in and adjustment-out ledger;
- auditable reserve/release/finalize contract consumed by Clinic Billing;
- wallet usage rules, expiry controls and quota limits;
- accounting journal integration for top-up/refund/adjustments and optional redeem;
- patient/contact smart buttons and wallet summary;
- portal request approval model for top-up/refund;
- multi-company security, manager approvals and immutable posted transactions;
- wallet statement PDF, pivot/graph analysis and operational cron jobs.
""",
    "category": "ClinicOne/Finance",
    "author": "ClinicOne Team",
    "website": "https://clinic.one/",
    "license": "LGPL-3",
    "depends": [
        "base",
        "base_setup",
        "mail",
        "portal",
        "contacts",
        "uom",
        "analytic",
        "account",
        "product",
        "purchase",
        "stock",
        "stock_account",
        "clinic_base",
        "clinic_audit",
        "clinic_branch",
        "clinic_staff",
        "clinic_room_device",
        "clinic_treatment_catalog",
        "clinic_patient",
        "clinic_doctor",
        "clinic_queue_room",
        "clinic_inventory",
        "clinic_booking",
        "clinic_triage_vitals",
        "clinic_consent_legal",
        "clinic_encounter",
        "clinic_emar",
        "clinic_imaging",
        "clinic_care_plan",
        "clinic_package",
        "clinic_membership",
        "clinic_billing",
        "clinic_ar",
        "clinic_ap"
    ],
    "data": [
        "security/clinic_wallet_security.xml",
        "security/ir.model.access.csv",
        "data/wallet_sequence.xml",
        "data/wallet_cron.xml",
        "data/wallet_mail_template.xml",
        "views/wallet_views.xml",
        "views/wallet_transaction_views.xml",
        "views/wallet_rule_views.xml",
        "views/wallet_portal_views.xml",
        "views/wallet_operation_wizard_views.xml",
        "views/res_partner_views.xml",
        "views/clinic_billing_views.xml",
        "views/res_config_settings_views.xml",
        "views/portal_templates.xml",
        "report/wallet_statement_templates.xml",
        "report/wallet_statement_report.xml",
        "views/menu_views.xml"
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}




