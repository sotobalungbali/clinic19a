{
    "name": "ClinicOne - Insurance Authorization",
    "summary": "Enterprise insurance policies, eligibility, pre-authorization and governed claim processing.",
    "description": """
ClinicOne Insurance Authorization
=================================
Enterprise insurance coverage and payer-authorization orchestration for
ClinicOne on Odoo 19 Community Edition.

Blueprint scope:
- insurance policies;
- pre-authorization;
- claim processing.

Architecture boundary:
- clinic_billing remains owner of the already-installed
  `clinic.insurance.claim` / `clinic.insurance.claim.line` models;
- this addon extends those claim models with Policy and Authorization
  traceability rather than moving or duplicating frozen Billing ownership;
- account.move / account.move.line remain the legal accounting ledger;
- clinic_billing remains owner of claim settlement payments;
- clinic_accounting / clinic_l10n_id remain owners of accounting/tax governance.

Enterprise capabilities:
- insurer/Payer registry extension over res.partner;
- insurance plan and benefit-rule master data;
- patient insurance policies with eligibility evidence and coverage dates;
- pre-authorization requests and service-line adjudication;
- Booking / Appointment / Treatment / Encounter / Billing integration;
- approved Authorization -> Billing Insurance Claim orchestration;
- governed extension of existing Billing claim processing;
- claim Policy/Authorization linkage and payer adjudication metadata;
- multi-company and multi-branch security;
- automatic expiry housekeeping;
- authorization and claim evidence PDFs;
- enterprise Search/List/Form UI, statusbars, smart buttons and row actions.
""",
    "version": "19.0.1.0.1",
    "author": "ClinicOne",
    "website": "https://clinic.one",
    "license": "LGPL-3",
    "category": "ClinicOne/Insurance",
    "application": True,
    "installable": True,
    "auto_install": False,
    "depends": [
        "base",
        "base_setup",
        "mail",
        "web",
        "contacts",
        "product",
        "account",
        "clinic_base",
        "clinic_audit",
        "clinic_branch",
        "clinic_patient",
        "clinic_treatment_catalog",
        "clinic_booking",
        "clinic_queue_room",
        "clinic_encounter",
        "clinic_billing",
        "clinic_ar",
        "clinic_ap",
        "clinic_wallet",
        "clinic_finance",
        "clinic_accounting",
        "clinic_l10n_id"
    ],
    "data": [
        "security/clinic_insurance_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "data/cron_data.xml",
        "views/insurance_plan_views.xml",
        "views/insurance_policy_views.xml",
        "views/eligibility_views.xml",
        "views/authorization_views.xml",
        "views/claim_views.xml",
        "views/integration_views.xml",
        "views/res_config_settings_views.xml",
        "report/authorization_templates.xml",
        "report/authorization_report.xml",
        "report/claim_templates.xml",
        "report/claim_report.xml",
        "views/menu_views.xml"
    ],
    "demo": [],
}

