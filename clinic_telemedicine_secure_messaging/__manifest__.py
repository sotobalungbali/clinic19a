{
    "name": "ClinicOne - Telemedicine & Secure Messaging",
    "summary": "Enterprise teleconsultation, secure doctor-patient messaging, and governed file sharing.",
    "description": """
ClinicOne Telemedicine & Secure Messaging
=========================================
Official addon 33 of the ClinicOne 39-addon blueprint.

Official responsibility:
- teleconsultation;
- secure doctor-patient chat;
- governed file sharing.

Architecture:
- `clinic.telemedicine.session` owns teleconsultation lifecycle and meeting provenance;
- `clinic.telemedicine.thread` owns secure doctor-patient conversation scope;
- `clinic.telemedicine.message` stores immutable plain-text message evidence;
- `clinic.telemedicine.attachment` owns secure file-sharing evidence;
- `clinic_staff` historical `clinic.telemedicine.thread` / `handler_id` contract is fulfilled;
- patient access is delivered through the existing `clinic_portal` exact-patient security boundary;
- Booking, Appointment, Patient, Doctor, Staff, Queue, Encounter, Consent, and Portal ownership stay in their existing addons;
- no external video provider is fabricated: manual HTTPS meeting URLs are supported now and a provider-neutral provisioning hook is available for future `clinic_integration_api`;
- secure messaging does not claim end-to-end encryption. Confidentiality depends on Odoo authentication, exact-patient authorization, database/filestore controls, and HTTPS/TLS deployment.

Enterprise features:
- provider-neutral teleconsultation lifecycle;
- doctor eligibility and source-record consistency checks;
- active Clinic Portal profile + explicit Telemedicine/Messaging feature grants;
- patient-initiated secure threads;
- exact patient/company record intersection for every portal record ID;
- immutable messages;
- PDF/JPEG/PNG file sharing with size, MIME, extension, checksum, and secure download controls;
- first-response SLA evidence;
- staff handler integration;
- Booking/Appointment/Queue/Encounter reverse navigation;
- Search/List/Form for every owned persistent model;
- Session/Thread Kanban;
- advanced statusbars, smart buttons, body actions, and One2many row actions;
- executable Enterprise Development Guardrail including HARD GATE 11.
""",
    "version": "19.0.1.0.1",
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
        "portal",
        "website",
        "clinic_base",
        "clinic_branch",
        "clinic_staff",
        "clinic_doctor",
        "clinic_patient",
        "clinic_booking",
        "clinic_queue_room",
        "clinic_consent_legal",
        "clinic_encounter",
        "clinic_portal"
    ],
    "data": [
        "security/clinic_telemedicine_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "views/telemedicine_session_views.xml",
        "views/telemedicine_thread_views.xml",
        "views/telemedicine_message_views.xml",
        "views/telemedicine_attachment_views.xml",
        "views/portal_access_views.xml",
        "views/res_config_settings_views.xml",
        "views/integration_views.xml",
        "views/portal_templates.xml",
        "views/menu_views.xml"
    ],
    "assets": {
        "web.assets_frontend": [
            "clinic_telemedicine_secure_messaging/static/src/scss/telemedicine_portal.scss"
        ]
    },
    "demo": []
}

