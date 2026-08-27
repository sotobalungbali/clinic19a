# -*- coding: utf-8 -*-
{
    "name": "ClinicOne Treatment Session Management",
    "summary": "Enterprise treatment delivery, consumption, billing, and clinical session orchestration.",
    "description": """
ClinicOne Treatment Session Management
======================================
Source-actual ClinicOne addon #41 / 41 for Odoo 19 Community Edition.

This full-corrected release preserves the historical Treatment Session,
Session Line, Session Stage and Booking/Patient/Doctor/Room extension
contracts while hardening workflow, stock consumption, billing, security,
multi-company/branch scope and enterprise UI.

Dependency direction is intentionally bounded. Downstream addons such as
clinic_membership, clinic_ar, clinic_wallet, clinic_reports,
clinic_dashboard and clinic_analytics are NOT hard dependencies because they
already consume clinic_treatment_session.
""",
    "version": "19.0.2.0.2",
    "category": "ClinicOne/Clinical Operations",
    "author": "ClinicOne Dev Team",
    "license": "AGPL-3",
    "depends": [
        "base",
        "base_setup",
        "web",
        "mail",
        "contacts",
        "uom",
        "product",
        "utm",
        "crm",
        "hr",
        "stock",
        "account",
        "sale",
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
        "clinic_referral",
        "clinic_billing"
    ],
    "data": [
        "security/clinic_treatment_session_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "data/session_stage_data.xml",
        "data/mail_template_data.xml",
        "data/cron_data.xml",
        "views/treatment_session_views.xml",
        "views/treatment_session_line_views.xml",
        "views/session_stage_views.xml",
        "views/res_config_settings_views.xml",
        "views/treatment_session_menus.xml",
        "data/optional_ui_bridge.xml"
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
