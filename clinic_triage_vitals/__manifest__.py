
{
    "name": "ClinicOne - Triage & Vitals Intake",
    "summary": "Capture triage classification and vital signs at intake; SLA tracking, queue/room hints, and billing hooks.",
    "version": "19.0.1.1.2",
    "category": "Clinic Management",
    "author": "ClinicOne",
    "website": "",
    "license": "LGPL-3",
    "application": False,
    "installable": True,
    "auto_install": False,

    # Preserve the finished ClinicOne dependency contract.
    "depends": [
        "base",
        "mail",
        "contacts",
        "hr",
        "account",
        "product",
        "sale",
        "stock",
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
    ],

    "data": [
        "security/clinic_triage_vitals_rules.xml",
        "security/ir.model.access.csv",
        "data/triage_sequence.xml",
        "views/triage_level_views.xml",
        "views/triage_tag_views.xml",
        "views/triage_session_views.xml",
        "views/vitals_intake_views.xml",
        # patient_triage_views.xml is an optional inheritance template.
        # It is installed defensively by _post_init_hook so an older
        # clinic_patient database without the expected XML-ID does not block
        # this addon's installation.
        "views/clinic_triage_vitals_menus.xml",
        "views/templates.xml",
    ],
    "demo": [
        "demo/demo.xml",
    ],

    "post_init_hook": "_post_init_hook",
}
