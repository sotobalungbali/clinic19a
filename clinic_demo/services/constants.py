




"""Stable build and policy constants for ClinicOne demo orchestration."""

GENERATOR_VERSION = "19.0.1.0.46"
AUTHORITATIVE_SOURCE_FINGERPRINT = "8e0d2be47034b5841642ba056df294825f71a6040f7f27b77cd6da32ef417ab2"
EXPECTED_SUITE_FINGERPRINT = "71c781e1f6649882cc9cad4376cefa63be60134ffe98fdb91caf4b492af18439"

EXPECTED_SUITE_VERSIONS = {
    "clinic_accounting": "19.0.1.0.0",
    "clinic_analytics": "19.0.1.0.1",
    "clinic_ap": "19.0.3.0.3",
    "clinic_ar": "19.0.3.0.3",
    "clinic_audit": "19.0.2.0.3",
    "clinic_base": "19.0.1.0.0",
    "clinic_billing": "19.0.3.0.5",
    "clinic_booking": "19.0.1.0.5",
    "clinic_branch": "19.0.2.0.0",
    "clinic_care_plan": "19.0.1.0.0",
    "clinic_consent_legal": "19.0.1.1.0",
    "clinic_dashboard": "19.0.1.0.1",
    "clinic_doctor": "19.0.1.0.2",
    "clinic_ecommerce": "19.0.1.0.0",
    "clinic_emar": "19.0.3.0.3",
    "clinic_encounter": "19.0.1.0.0",
    "clinic_feedback": "19.0.1.0.0",
    "clinic_finance": "19.0.1.0.0",
    "clinic_imaging": "19.0.1.0.0",
    "clinic_incident_event": "19.0.1.0.1",
    "clinic_insurance_authorization": "19.0.1.0.1",
    "clinic_integration_api": "19.0.1.0.0",
    "clinic_inventory": "19.0.1.0.2",
    "clinic_l10n_id": "19.0.1.0.1",
    "clinic_marketing": "19.0.1.0.1",
    "clinic_membership": "19.0.3.0.6",
    "clinic_package": "19.0.3.0.0",
    "clinic_patient": "19.0.1.0.1",
    "clinic_portal": "19.0.1.0.0",
    "clinic_post_care_followup": "19.0.1.0.0",
    "clinic_quality": "19.0.1.0.0",
    "clinic_queue_room": "19.0.1.0.1",
    "clinic_referral": "19.0.2.0.6",
    "clinic_reports": "19.0.1.0.0",
    "clinic_room_device": "19.0.1.0.1",
    "clinic_staff": "19.0.1.0.1",
    "clinic_telemedicine_secure_messaging": "19.0.1.0.1",
    "clinic_treatment_catalog": "19.0.1.0.2",
    "clinic_treatment_session": "19.0.2.0.4",
    "clinic_triage_vitals": "19.0.1.1.2",
    "clinic_wallet": "19.0.3.0.5"
}

PROFILE_SELECTION = [
    ("compact", "Compact"),
    ("standard", "Standard"),
    ("full_enterprise", "Full Enterprise"),
]

RESET_DELETE_SAFE = "delete_safe"
RESET_CANCEL_THEN_DELETE = "cancel_then_delete"
RESET_REVERSE_THEN_RETAIN = "reverse_then_retain"
RESET_DEACTIVATE = "deactivate"
RESET_RETAIN_IMMUTABLE = "retain_immutable"
RESET_FRESH_DB_ONLY = "fresh_db_reset_only"

RESET_POLICY_SELECTION = [
    (RESET_DELETE_SAFE, "Delete Safe"),
    (RESET_CANCEL_THEN_DELETE, "Cancel Then Delete"),
    (RESET_REVERSE_THEN_RETAIN, "Reverse Then Retain"),
    (RESET_DEACTIVATE, "Deactivate"),
    (RESET_RETAIN_IMMUTABLE, "Retain Immutable"),
    (RESET_FRESH_DB_ONLY, "Fresh DB Reset Only"),
]

REFERENCE_OWNERSHIP_SELECTION = [
    ("created", "Created by Demo"),
    ("reused", "Reused Existing Record"),
    ("updated_demo_owned", "Updated Demo-owned Record"),
]

REFERENCE_STATUS_SELECTION = [
    ("bound", "Bound"),
    ("missing", "Missing"),
    ("reset_removed", "Reset / Removed"),
    ("reset_retained", "Reset / Retained"),
    ("error", "Error"),
]

