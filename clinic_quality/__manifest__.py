{
    "name": "ClinicOne - Quality Management",
    "summary": "SOP governance, compliance quality checks, quality evidence, and Incident escalation.",
    "description": """
ClinicOne Quality Management
============================
Official ClinicOne addon 35 of 39.

Official responsibility
-----------------------
Documents standard operating procedures and compliance quality checks.

Enterprise scope
----------------
- governed SOP master records and immutable approved versions;
- Staff SOP acknowledgement evidence;
- reusable compliance-check templates and weighted controls;
- executable quality checks with evidence and reviewer approval;
- scheduled recurring quality checks;
- branch/company isolation;
- quality-scope links to Room, Staff, Doctor, Treatment and Inventory Lot;
- explicit escalation of failed controls into addon-34 Incident cases;
- QWeb SOP and Quality Check evidence reports;
- enterprise Search/List/Form/Kanban/Pivot/Graph UX;
- Enterprise Development Guardrail and regression contracts.

Ownership boundaries
--------------------
`clinic_incident_event` remains owner of Incident/Investigation/CAPA.
`clinic_inventory` remains owner of stock-lot quality disposition.
Quality checks do not silently mutate Room, Staff, Doctor, Treatment, Inventory,
Encounter, eMAR, Feedback or Telemedicine workflows.

No hard dependency is introduced on future `clinic_integration_api`,
`clinic_audit`, or `clinic_analytics`.
""",
    "version": "19.0.1.0.0",
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
        "stock",
        "clinic_base",
        "clinic_branch",
        "clinic_staff",
        "clinic_doctor",
        "clinic_treatment_catalog",
        "clinic_inventory",
        "clinic_room_device",
        "clinic_incident_event"
    ],
    "data": [
        "security/clinic_quality_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "data/cron_data.xml",
        "views/sop_views.xml",
        "views/sop_version_views.xml",
        "views/sop_acknowledgement_views.xml",
        "views/check_template_views.xml",
        "views/check_template_line_views.xml",
        "views/quality_check_views.xml",
        "views/check_line_views.xml",
        "views/schedule_views.xml",
        "views/res_config_settings_views.xml",
        "report/sop_report.xml",
        "report/quality_check_report.xml",
        "views/menu_views.xml"
    ],
    "demo": []
}
