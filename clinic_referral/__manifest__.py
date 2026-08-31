# -*- coding: utf-8 -*-
{
    "name": "ClinicOne Referral Management",
    "summary": "Enterprise referral acquisition, program governance, conversion tracking, and cross-ClinicOne attribution.",
    "description": """
ClinicOne Referral Management
=============================
Source-actual ClinicOne addon #40 / 41 for Odoo 19 Community Edition.

This release rebuilds the historical referral draft while preserving the
public Referral / Program / Source contracts and adding branch-aware security,
booking attribution, conversion evidence, reward workflow, enterprise UI and
Odoo 19 ORM hardening.

clinic_treatment_session and clinic_membership are downstream consumers of
clinic_referral and are intentionally not hard dependencies here.
""",
    "version": "19.0.2.0.6",
    "category": "ClinicOne/Referral",
    "author": "ClinicOne Dev Team",
    "license": "LGPL-3",
    "depends": [
        "base", "web", "mail", "contacts", "uom", "product", "utm", "crm",
        "clinic_base", "clinic_audit", "clinic_branch", "clinic_staff",
        "clinic_room_device", "clinic_treatment_catalog", "clinic_patient",
        "clinic_doctor", "clinic_queue_room", "clinic_inventory",
        "clinic_booking", "clinic_triage_vitals", "clinic_consent_legal",
        "clinic_encounter", "clinic_emar", "clinic_imaging",
        "clinic_care_plan", "clinic_package"
    ],
    "data": [
        "security/clinic_referral_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "data/cron_data.xml",
        "views/referral_views.xml",
        "views/referral_program_views.xml",
        "views/referral_source_views.xml",
        "views/referral_integration_views.xml",
        "views/res_config_settings_views.xml",
        "views/referral_menus.xml",
        "data/optional_ui_bridge.xml"
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}

