{
    "name": "ClinicOne - Central Reporting Engine",
    "summary": "Enterprise financial, operational and clinical reporting engine for ClinicOne.",
    "description": """
ClinicOne Central Reporting Engine
==================================
Official addon 28 of the ClinicOne 39-addon blueprint.

Blueprint responsibility:
- central reporting engine;
- financial reports;
- operational reports;
- clinical reports.

Enterprise scope:
- governed report definitions;
- reusable report runs and snapshot output;
- financial, operational and clinical engine families;
- cross-addon metrics and traceable detail lines;
- company/branch/date filtering;
- scheduled recurring report generation;
- CSV export and QWeb PDF output;
- source drill-down;
- report finalization and immutable snapshots;
- downstream-safe metric layer for future clinic_dashboard;
- Enterprise Development Guardrail and runtime contract suite.

Ownership boundaries:
- source transactions remain owned by their upstream ClinicOne modules;
- report output is read/snapshot only and never mutates source workflows;
- future clinic_dashboard, clinic_portal, clinic_quality,
  clinic_integration_api and clinic_analytics are not dependencies.
""",
    "version": "19.0.1.0.0",
    "author": "ClinicOne",
    "website": "https://clinic.one",
    "license": "LGPL-3",
    "category": "ClinicOne/Reporting",
    "application": True,
    "installable": True,
    "auto_install": False,
    "depends": [
        "base",
        "base_setup",
        "mail",
        "web",
        "contacts",
        "account",
        "stock",
        "clinic_base",
        "clinic_branch",
        "clinic_staff",
        "clinic_doctor",
        "clinic_patient",
        "clinic_treatment_catalog",
        "clinic_inventory",
        "clinic_booking",
        "clinic_queue_room",
        "clinic_room_device",
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
        "clinic_ap",
        "clinic_wallet",
        "clinic_finance",
        "clinic_accounting",
        "clinic_l10n_id",
        "clinic_insurance_authorization",
        "clinic_post_care_followup",
        "clinic_feedback"
    ],
    "data": [
        "security/clinic_reports_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "data/report_definition_data.xml",
        "data/cron_data.xml",
        "views/report_definition_views.xml",
        "views/report_run_views.xml",
        "views/report_metric_views.xml",
        "views/report_detail_views.xml",
        "views/report_schedule_views.xml",
        "wizard/report_generate_wizard_views.xml",
        "views/res_config_settings_views.xml",
        "report/report_run_templates.xml",
        "report/report_run_report.xml",
        "views/menu_views.xml"
    ],
    "demo": []
}
