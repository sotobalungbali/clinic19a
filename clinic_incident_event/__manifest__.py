{
    "name": "ClinicOne - Incident & Event Management",
    "summary": "Clinical incident, adverse-event escalation, investigation, CAPA, and compliance evidence.",
    "description": """
ClinicOne Incident & Event Management
=====================================
Official ClinicOne addon 34 of 39.

Responsibility
--------------
- log clinical and operational incidents;
- link existing Adverse Events without replacing their owner;
- run structured investigation and root-cause analysis;
- govern corrective/preventive actions (CAPA);
- record regulatory-review evidence;
- preserve immutable Incident timeline evidence;
- activate historical Clinic Staff incident counters/KPI integration.

Ownership
---------
`clinic_encounter` remains owner of `clinic.adverse.event`, `clinic.ae.action`,
and `clinic.ae.followup`. Addon 34 owns the cross-functional Incident case and
its investigation/CAPA/compliance layer.

Secure Telemedicine content remains owned by addon 33. Incident links carry
provenance only; Secure Message bodies and internal secure notes are not copied.

No hard dependency is introduced on future `clinic_quality`,
`clinic_integration_api`, `clinic_audit`, or `clinic_analytics`.
""",
    "version": "19.0.1.0.1",
    "author": "ClinicOne",
    "website": "https://clinic.one",
    "license": "LGPL-3",
    "category": "ClinicOne/Quality & Compliance",
    "application": True,
    "installable": True,
    "auto_install": False,
    "depends": [
        "base",
        "base_setup",
        "mail",
        "web",
        "contacts",
        "clinic_base",
        "clinic_branch",
        "clinic_staff",
        "clinic_doctor",
        "clinic_patient",
        "clinic_booking",
        "clinic_queue_room",
        "clinic_room_device",
        "clinic_encounter",
        "clinic_emar",
        "clinic_feedback",
        "clinic_telemedicine_secure_messaging"
    ],
    "data": [
        "security/clinic_incident_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "data/category_data.xml",
        "views/category_views.xml",
        "views/incident_views.xml",
        "views/investigation_views.xml",
        "views/corrective_action_views.xml",
        "views/timeline_views.xml",
        "views/res_config_settings_views.xml",
        "views/integration_views.xml",
        "report/incident_report.xml",
        "views/menu_views.xml"
    ],
    "demo": []
}
