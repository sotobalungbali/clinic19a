{
    "name": "ClinicOne - Patient Feedback & Satisfaction",
    "summary": "Enterprise patient feedback, satisfaction surveys, NPS, service recovery and escalation workflow.",
    "description": """
ClinicOne Patient Feedback & Satisfaction
=========================================
Official addon 27 of the ClinicOne 39-addon blueprint.

Blueprint responsibility:
- collect patient feedback;
- manage satisfaction surveys;
- provide an escalation workflow for low scores, complaints and service-recovery cases.

Enterprise scope:
- reusable feedback surveys and questions;
- tokenized feedback requests;
- canonical patient feedback records and structured answers;
- 1-5 satisfaction rating, NPS 0-10 and recommendation capture;
- configurable low-score / detractor escalation;
- service-recovery escalation with accountable owner and SLA;
- Booking feedback-link integration without moving Booking ownership;
- Queue, Encounter and Post-Care source integration;
- Patient, Doctor and Staff feedback rollups;
- multi-company / branch isolation;
- public token survey page using Odoo Website;
- email invitation/reminder;
- expiry and opt-in source automation;
- Enterprise Development Guardrail and runtime contract suite.

Ownership boundaries:
- `booking.feedback.link` remains owned by clinic_booking;
- Booking / Queue / Encounter / Post-Care workflows remain owned upstream;
- Staff / Doctor / Patient masters remain owned upstream;
- future clinic_incident_event, clinic_reports, clinic_dashboard,
  clinic_marketing, clinic_portal and clinic_integration_api are not dependencies.
""",
    "version": "19.0.1.0.0",
    "author": "ClinicOne",
    "website": "https://clinic.one",
    "license": "LGPL-3",
    "category": "ClinicOne/Operations",
    "application": True,
    "installable": True,
    "auto_install": False,
    "depends": [
        "base",
        "base_setup",
        "mail",
        "web",
        "website",
        "contacts",
        "clinic_base",
        "clinic_audit",
        "clinic_branch",
        "clinic_staff",
        "clinic_doctor",
        "clinic_patient",
        "clinic_treatment_catalog",
        "clinic_booking",
        "clinic_queue_room",
        "clinic_encounter",
        "clinic_post_care_followup"
    ],
    "data": [
        "security/clinic_feedback_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "data/mail_template_data.xml",
        "data/cron_data.xml",
        "views/survey_views.xml",
        "views/request_views.xml",
        "views/feedback_views.xml",
        "views/escalation_views.xml",
        "views/integration_views.xml",
        "views/res_config_settings_views.xml",
        "views/public_feedback_templates.xml",
        "report/feedback_summary_templates.xml",
        "report/feedback_summary_report.xml",
        "views/menu_views.xml"
    ],
    "demo": []
}
