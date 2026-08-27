# -*- coding: utf-8 -*-
{
    "name": "ClinicOne - Care Plan & Protocol Library",
    "summary": "Enterprise care-plan execution and reusable clinical protocol governance for ClinicOne.",
    "description": """
ClinicOne Care Plan & Protocol Library for Odoo 19 CE

- Care Plan lifecycle, execution progress, adherence and financial visibility
- Reusable versioned clinical protocols with ordered/dependent steps
- Reverse navigation to Patient, Doctor and Encounter
- Procedure Session and eMAR prescription bridges
- Enterprise search/list/form/calendar/kanban interfaces
- Company-aware ORM security and auditable chatter/activity support
    """,
    "version": "19.0.1.0.0",
    "category": "Clinic",
    "author": "ClinicOne",
    "maintainer": "ClinicOne Engineering",
    "website": "https://clinic.one",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "contacts",
        "hr",
        "account",
        "product",
        "stock",
        "sale",
        "portal",
        "website",
        "uom",
        "analytic",
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
    ],
    "data": [
        "security/clinic_care_plan_rules.xml",
        "security/ir.model.access.csv",
        "data/clinic_care_plan_sequences.xml",
        "views/care_plan_views.xml",
        "views/care_plan_line_views.xml",
        "views/care_protocol_views.xml",
        "views/care_protocol_step_views.xml",
        "views/clinic_care_plan_menus.xml",
        "report/care_plan_reports.xml",
    ],
    "demo": [],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
