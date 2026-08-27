{
    "name": "ClinicOne - Patient Portal",
    "summary": "Secure patient web portal for bookings, invoices, and treatment history.",
    "description": """
ClinicOne Patient Portal
========================
Official addon 31 of the ClinicOne 39-addon blueprint.

Official blueprint responsibility:
- provides a web portal for patients to view bookings;
- provides a web portal for patients to view invoices;
- provides a web portal for patients to view treatment history.

Architecture:
- extends Odoo 19 Customer Portal instead of replacing it;
- uses the existing clinic.patient <-> res.partner <-> res.users linkage;
- keeps Booking ownership in clinic_booking;
- keeps Clinic Billing ownership in clinic_billing and native invoice/payment
  ownership in Odoo Accounting Portal;
- keeps Encounter/Procedure ownership in clinic_encounter;
- reuses existing Wallet and Consent portal pages as linked companion services;
- reuses native Odoo /my/orders and Clinic eCommerce storefront links;
- never exposes clinical SOAP notes, diagnoses, vitals, internal comments, or
  unpublished clinical documents merely because a portal user exists.

Enterprise controls:
- staff-governed patient Portal Profile;
- Active/Suspended/Archived access lifecycle;
- exact patient ownership checks on every route;
- current-company isolation;
- feature-level access policy;
- safe, explicit sudo only after partner/company/profile scope is established;
- native Odoo portal access-management wizard;
- portal counters, pagination, filters, breadcrumbs, and responsive pages;
- backend Search/List/Form and smart/action/body buttons;
- 16-hard-gate Enterprise Development Guardrail including explicit Database
  Identifier & ORM Naming Safety (Hard Gate 11).
""",
    "version": "19.0.1.0.0",
    "author": "ClinicOne",
    "website": "https://clinic.one",
    "license": "LGPL-3",
    "category": "ClinicOne/Portal",
    "application": True,
    "installable": True,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
    "depends": [
        "base",
        "base_setup",
        "mail",
        "web",
        "portal",
        "website",
        "account",
        "sale",
        "clinic_base",
        "clinic_branch",
        "clinic_patient",
        "clinic_booking",
        "clinic_billing",
        "clinic_encounter",
        "clinic_wallet",
        "clinic_consent_legal",
        "clinic_ecommerce"
    ],
    "data": [
        "security/clinic_portal_security.xml",
        "security/ir.model.access.csv",
        "views/portal_profile_views.xml",
        "views/res_config_settings_views.xml",
        "views/portal_templates.xml",
        "views/menu_views.xml"
    ],
    "assets": {
        "web.assets_frontend": [
            "clinic_portal/static/src/scss/portal.scss"
        ]
    },
    "demo": []
}
