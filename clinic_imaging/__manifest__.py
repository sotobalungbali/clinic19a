# -*- coding: utf-8 -*-
{
    "name": "ClinicOne - Clinical Imaging Management",
    "summary": "Enterprise clinical imaging requests, acquisition, findings, results, quality, and billing integration.",
    "version": "19.0.1.0.0",
    "category": "Clinic",
    "author": "ClinicOne Team",
    "website": "https://clinicone.example.com",
    "license": "LGPL-3",
    "description": """
ClinicOne Clinical Imaging Management
=====================================
Preserves the finished ClinicOne imaging baseline while hardening it for Odoo
19 Community Edition.  The addon covers imaging master data, devices, requests,
acquisition hierarchy, images, findings, results, structured reporting,
quality/KPI monitoring, consent, encounter, treatment, EMAR and accounting
integration.
    """,
    "depends": [
        # Odoo core — preserved from the finished baseline.
        "base", "mail", "contacts", "hr", "account", "product", "stock",
        "sale", "portal", "website", "uom", "analytic",

        # ClinicOne — preserved from the finished baseline.
        "clinic_base", "clinic_audit", "clinic_branch", "clinic_staff",
        "clinic_room_device", "clinic_treatment_catalog", "clinic_patient",
        "clinic_doctor", "clinic_queue_room", "clinic_inventory",
        "clinic_booking", "clinic_triage_vitals", "clinic_consent_legal",
        "clinic_encounter", "clinic_emar",
    ],
    "data": [
        "security/clinic_imaging_rules.xml",
        "security/ir.model.access.csv",
        "data/imaging_sequences.xml",
        "data/imaging_mail_template.xml",
        "views/imaging_master_views.xml",
        "views/imaging_operations_views.xml",
        "views/imaging_quality_views.xml",
        "views/imaging_support_views.xml",
        "views/imaging_actions.xml",
        "views/imaging_menus.xml",
        "report/imaging_result_report.xml",
        # Existing placeholder template file retained for source preservation.
        "views/templates.xml",
    ],
    "demo": ["demo/demo.xml"],
    "post_init_hook": "_post_init_hook",
    "installable": True,
    "application": True,
}
