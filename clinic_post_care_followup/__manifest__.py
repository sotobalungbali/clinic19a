{
    "name": "ClinicOne - Post-Care Follow-up",
    "summary": "Enterprise post-treatment instructions, follow-up tasks, reminders, check-ins and escalation.",
    "description": """
ClinicOne Post-Care Follow-up
=============================
Addon 26 of the official ClinicOne 39-addon blueprint.

Blueprint responsibility:
- manage post-treatment care instructions;
- automate patient follow-up reminders.

Enterprise scope:
- reusable post-care protocols and timed protocol steps;
- patient post-care plans generated from Encounter, Booking or Care Plan;
- staff-assigned post-care tasks compatible with the historical
  `clinic.postcare.task` contract anticipated by clinic_staff;
- automated email reminders plus governed manual/phone/internal follow-up;
- patient check-in evidence and red-flag escalation;
- multi-company / multi-branch isolation;
- staff workload and Patient/Encounter/Booking/Care Plan traceability;
- automatic task generation and expiry/overdue processing;
- printable patient post-care instructions and follow-up summary;
- Enterprise Development Guardrail and runtime regression suite.

Ownership boundaries:
- clinic_encounter remains owner of clinical Encounter workflow;
- clinic_booking remains owner of scheduling;
- clinic_care_plan remains owner of treatment/care pathway;
- clinic_staff remains owner of staff master/roster/assignment/KPI;
- clinic_feedback remains a future addon and is not referenced;
- clinic_incident_event remains a future addon and is not referenced.
""",
    "version": "19.0.1.0.0",
    "author": "ClinicOne",
    "website": "https://clinic.one",
    "license": "LGPL-3",
    "category": "ClinicOne/Clinical",
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
        "clinic_audit",
        "clinic_branch",
        "clinic_staff",
        "clinic_doctor",
        "clinic_patient",
        "clinic_treatment_catalog",
        "clinic_booking",
        "clinic_encounter",
        "clinic_care_plan",
        "clinic_insurance_authorization"
    ],
    "data": [
        "security/clinic_postcare_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "data/mail_template_data.xml",
        "data/cron_data.xml",
        "views/protocol_views.xml",
        "views/plan_views.xml",
        "views/task_views.xml",
        "views/checkin_views.xml",
        "views/escalation_views.xml",
        "views/integration_views.xml",
        "views/res_config_settings_views.xml",
        "report/postcare_instruction_templates.xml",
        "report/postcare_instruction_report.xml",
        "report/postcare_summary_templates.xml",
        "report/postcare_summary_report.xml",
        "views/menu_views.xml"
    ],
    "demo": []
}
