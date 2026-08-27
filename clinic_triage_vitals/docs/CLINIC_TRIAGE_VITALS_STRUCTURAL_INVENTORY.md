
# ClinicOne — clinic_triage_vitals Full Structural Inventory

Functional baseline: **FINISHED**. Inventory covers the active import graph only; `encounter_link.py` remains dormant by design.

## clinic.triage.level
- Source: `models/triage_level.py`
- Python class: `ClinicTriageLevel`
- Fields (35): `active`, `auto_escalate`, `billable`, `code`, `color`, `color_hex`, `company_id`, `currency_id`, `dbp_max_mm_hg`, `dbp_min_mm_hg`, `default_activity_type_id`, `default_fee`, `default_queue_stage_id`, `description`, `escalate_after_minutes`, `escalate_to_level_id`, `gcs_max`, `gcs_min`, `guidelines_html`, `hr_max_bpm`, `hr_min_bpm`, `name`, `product_id`, `recommended_room_type_id`, `rr_max_bpm`, `rr_min_bpm`, `rule_domain`, `sbp_max_mm_hg`, `sbp_min_mm_hg`, `sequence`, `sla_minutes`, `spo2_min_percent`, `temp_max_c`, `temp_min_c`, `weight`
- Methods (7): `_check_constraints`, `_compute_display_name`, `_onchange_code_upper`, `create`, `get_sla_minutes`, `name_get`, `write`

## clinic.triage.tag
- Source: `models/triage_tag.py`
- Python class: `ClinicTriageTag`
- Fields (24): `active`, `billable`, `child_ids`, `code`, `color`, `color_hex`, `company_id`, `currency_id`, `default_activity_type_id`, `default_fee`, `default_queue_stage_id`, `description`, `guidelines_html`, `image_128`, `last_used_on`, `name`, `parent_id`, `product_id`, `recommended_room_type_id`, `rule_domain`, `sequence`, `session_count`, `session_ids`, `tag_type`
- Methods (9): `_check_constraints`, `_compute_display_name`, `_compute_usage_metrics`, `_onchange_code_upper`, `_onchange_color_hex`, `action_view_sessions`, `create`, `name_get`, `write`

## clinic.triage.session
- Source: `models/triage_session.py`
- Python class: `ClinicTriageSession`
- Fields (31): `active`, `allergies`, `appointment_id`, `arrival_datetime`, `assigned_doctor_id`, `assigned_nurse_id`, `chief_complaint`, `company_id`, `currency_id`, `current_medications`, `end_datetime`, `has_abnormal_vitals`, `internal_notes`, `invoice_id`, `is_billable`, `name`, `patient_id`, `priority_score`, `queue_stage_id`, `reason_for_visit`, `recommended_room_type_id`, `sla_breached`, `sla_target_datetime`, `start_datetime`, `state`, `triage_duration_minutes`, `triage_fee`, `triage_level_id`, `triage_tag_ids`, `vitals_ids`, `wait_time_minutes`
- Methods (21): `_check_company_consistency`, `_check_timings`, `_compute_display_name`, `_compute_has_abnormal_vitals`, `_compute_priority_score`, `_compute_sla_fields`, `_compute_wait_and_duration`, `_get_level_defaults`, `_name_search_domain`, `_onchange_triage_level_id`, `action_cancel`, `action_complete`, `action_create_invoice`, `action_open_invoice`, `action_refer`, `action_reopen`, `action_start`, `create`, `name_get`, `name_search`, `write`

## clinic.vitals.intake
- Source: `models/vitals_intake.py`
- Python class: `ClinicVitalsIntake`
- Fields (53): `abnormal_fields`, `active`, `bmi`, `bmi_category`, `bp_arm`, `bp_method`, `bp_position`, `bsa_m2`, `company_id`, `currency_id`, `dbp_mm_hg`, `device_serial`, `gcs`, `gcs_e`, `gcs_m`, `gcs_v`, `heart_rate_bpm`, `height_cm`, `height_in`, `internal_notes`, `is_abnormal`, `is_bradycardia`, `is_bradypnea`, `is_fever`, `is_hypertensive`, `is_hypotensive`, `is_hypothermia`, `is_hypoxia`, `is_tachycardia`, `is_tachypnea`, `map_mm_hg`, `measure_datetime`, `measured_by_id`, `notes`, `o2_flow_l_min`, `on_oxygen`, `pain_score`, `patient_id`, `position`, `pulse_pressure_mm_hg`, `respiratory_rate_bpm`, `room_device_id`, `room_id`, `sbp_mm_hg`, `source`, `spo2_percent`, `temperature_c`, `temperature_f`, `temperature_method`, `triage_level_id`, `triage_session_id`, `weight_kg`, `weight_lb`
- Methods (18): `_check_value_ranges`, `_compute_abnormalities`, `_compute_bmi`, `_compute_bmi_category`, `_compute_bp_derived`, `_compute_bsa`, `_compute_display_name`, `_compute_gcs_total`, `_compute_height_in`, `_compute_temperature_f`, `_compute_weight_lb`, `_inverse_height_in`, `_inverse_temperature_f`, `_inverse_weight_lb`, `action_open_triage_session`, `create`, `name_get`, `write`

## clinic.patient
- Source: `models/patient_link.py`
- Python class: `ClinicPatient`
- Fields (16): `has_recent_abnormal_vitals`, `last_bmi`, `last_bp_diastolic`, `last_bp_systolic`, `last_hr_bpm`, `last_measure_on`, `last_rr_bpm`, `last_spo2_pct`, `last_temp_c`, `last_vitals_summary`, `latest_triage_session_id`, `latest_vitals_id`, `triage_session_count`, `triage_session_ids`, `triage_session_open_count`, `vitals_ids`
- Methods (7): `_check_company_consistency_with_sessions`, `_compute_latest_links`, `_compute_latest_vitals_snapshot`, `_compute_triage_metrics`, `action_new_triage_session`, `action_view_latest_vitals`, `action_view_triage_sessions`

## Dormant integration source
- `models/encounter_link.py` is preserved but intentionally not imported.
- `models/models.py` is preserved as the original inactive scaffold.
- No file whose basename begins with digit `0` is part of the authoritative source or distribution.
