# -*- coding: utf-8 -*-
{
    "name": "ClinicOne - Patient Management",
    "version": "19.0.1.0.0",
    "category": "ClinicOne",
    "summary": "Patient Management for ClinicOne Beauty Clinic Application",
    "description": """
ClinicOne - Patient Management
==============================
Enterprise patient registry for ClinicOne on Odoo 19 Community Edition.

Preserved business scope:
- Patient registration and identity
- Contact linkage and patient history
- Patient identifiers
- Allergies and reactions
- Conditions and episodes
- Lightweight patient vitals
- Optional integration hooks for downstream ClinicOne modules
    """,
    "author": "IG @odoocamp",
    "website": "https://www.247opensource.com",

    # Keep hard dependencies narrow. Downstream ClinicOne integrations remain optional.
    "depends": [
        "base",
        "mail",
        "contacts",
        "uom",
        "product",
        "clinic_base",
    ],

    # Security is loaded before the views that expose medical records.
    "data": [
        "security/clinic_patient_security.xml",
        "security/ir.model.access.csv",
        "data/patient_sequence.xml",
        "data/patient_stage_data.xml",
        "views/patient_views.xml",
        "views/patient_identifier_views.xml",
        "views/patient_allergy_views.xml",
        "views/patient_condition_views.xml",
        "views/patient_vital_views.xml",
        "views/res_partner_views.xml",
        "views/res_users_views.xml",
        "report/patient_card_report.xml",
        "views/clinic_patient_menus.xml",
        "views/templates.xml",
    ],

    "demo": [
        "demo/demo.xml",
    ],

    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
