# ClinicOne — clinic_patient Full Structural Inventory

Functional baseline: **FINISHED**. This inventory is a preservation contract, not a redesign proposal.

Backup files whose filename begins with digit `0` are excluded from the active baseline.

## Source baseline
- Active baseline files: 18
- Model/inheritance classes: 18
- Custom persistent business models: 16
- Canonical Odoo model extensions: 2 (`res.partner`, `res.users`)
- Legacy `_sql_constraints` assignments: 12
- Legacy SQL constraint entries: 15

## Models, fields, and methods

### `clinic.patient.stage`
- Python class: `ClinicPatientStage`
- Owner file: `models/patient.py`
- Fields (7): `name`, `sequence`, `fold`, `is_default_new`, `is_registered`, `is_inactive`, `is_deceased`
- Methods (0): —

### `clinic.patient.tag`
- Python class: `ClinicPatientTag`
- Owner file: `models/patient.py`
- Fields (2): `name`, `color`
- Methods (0): —

### `clinic.patient`
- Python class: `ClinicPatient`
- Owner file: `models/patient.py`
- Fields (37): `company_id`, `active`, `patient_code`, `name`, `display_name`, `image_1920`, `partner_id`, `is_vip`, `tag_ids`, `gender`, `birth_date`, `age_years`, `age_display`, `blood_type`, `rh_factor`, `is_deceased`, `deceased_date`, `phone`, `email`, `mobile`, `street`, `street2`, `city`, `state_id`, `zip`, `country_id`, `emergency_contact_id`, `emergency_phone`, `stage_id`, `stage_fold`, `registered_date`, `last_seen_date`, `identifier_ids`, `allergy_ids`, `condition_ids`, `vital_ids`, `currency_id`
- Methods (16): `_default_stage()`, `_compute_display_name()`, `_compute_age()`, `_safe_domain_partner()`, `_onchange_partner_id()`, `_check_birth_date()`, `_check_deceased_date()`, `create()`, `write()`, `_action_open_generic()`, `action_open_invoices()`, `action_open_attachments()`, `action_set_registered()`, `action_print_patient_card()`, `name_get()`, `_name_search()`

### `clinic.allergen.category`
- Python class: `ClinicAllergenCategory`
- Owner file: `models/patient_allergy.py`
- Fields (4): `name`, `code`, `sequence`, `active`
- Methods (0): —

### `clinic.allergen`
- Python class: `ClinicAllergen`
- Owner file: `models/patient_allergy.py`
- Fields (7): `name`, `category_id`, `active`, `commonness`, `synonyms`, `product_id`, `barcode_symbology`
- Methods (1): `_onchange_product_id()`

### `clinic.allergy.reaction.type`
- Python class: `ClinicAllergyReactionType`
- Owner file: `models/patient_allergy.py`
- Fields (4): `name`, `code`, `sequence`, `active`
- Methods (0): —

### `clinic.patient.allergy`
- Python class: `ClinicPatientAllergy`
- Owner file: `models/patient_allergy.py`
- Fields (22): `patient_id`, `company_id`, `allergen_id`, `category_id`, `allergen_name`, `product_id`, `status`, `verification_status`, `severity`, `criticality`, `is_critical`, `reaction_summary`, `reaction_ids`, `worst_reaction`, `recorded_date`, `recorded_by`, `onset_date`, `last_occurrence_date`, `source`, `display_name`, `attachment_count`, `notes`
- Methods (15): `_compute_display_name()`, `_compute_worst_reaction()`, `_compute_is_critical()`, `_compute_attachment_count()`, `_onchange_allergen_id()`, `_onchange_product_id()`, `_check_dates()`, `_check_resolved_has_last_occurrence()`, `create()`, `write()`, `_sync_patient_flags()`, `_maybe_map_allergy_note_to_partner()`, `action_open_attachments()`, `action_mark_resolved()`, `name_get()`

### `clinic.patient.allergy.reaction`
- Python class: `ClinicPatientAllergyReaction`
- Owner file: `models/patient_allergy.py`
- Fields (14): `allergy_id`, `patient_id`, `company_id`, `reaction_type_id`, `reaction_text`, `description`, `severity`, `onset_datetime`, `exposure_route`, `exposure_dose`, `outcome`, `recorded_date`, `recorded_by`, `attachment_count`
- Methods (3): `_check_onset_datetime()`, `_compute_attachment_count()`, `action_open_attachments()`

### `clinic.condition.category`
- Python class: `ClinicConditionCategory`
- Owner file: `models/patient_condition.py`
- Fields (4): `name`, `code`, `sequence`, `active`
- Methods (0): —

### `clinic.condition`
- Python class: `ClinicCondition`
- Owner file: `models/patient_condition.py`
- Fields (7): `name`, `category_id`, `active`, `chronic`, `default_severity`, `synonyms`, `code_ids`
- Methods (0): —

### `clinic.condition.code`
- Python class: `ClinicConditionCode`
- Owner file: `models/patient_condition.py`
- Fields (4): `condition_id`, `system`, `code`, `description`
- Methods (1): `name_get()`

### `clinic.patient.condition`
- Python class: `ClinicPatientCondition`
- Owner file: `models/patient_condition.py`
- Fields (27): `patient_id`, `company_id`, `condition_id`, `category_id`, `condition_name`, `code_id`, `code_system`, `code_value`, `status`, `verification_status`, `severity`, `stage`, `stage_text`, `body_site`, `laterality`, `onset_date`, `abatement_date`, `last_review_date`, `is_chronic`, `chronic_threshold_days`, `chronic_override`, `display_name`, `notes`, `attachment_count`, `episode_ids`, `worst_episode_severity`, `active`
- Methods (16): `_compute_display_name()`, `_compute_is_chronic()`, `_compute_attachment_count()`, `_compute_worst_episode_severity()`, `_onchange_condition_id()`, `_onchange_code_id()`, `_check_dates()`, `_check_status_logic()`, `create()`, `write()`, `_map_condition_summary_to_partner()`, `_action_open_generic()`, `action_open_attachments()`, `action_mark_resolved()`, `name_get()`, `_name_search()`

### `clinic.patient.condition.episode`
- Python class: `ClinicPatientConditionEpisode`
- Owner file: `models/patient_condition.py`
- Fields (8): `condition_id`, `patient_id`, `company_id`, `episode_datetime`, `description`, `severity`, `outcome`, `attachment_count`
- Methods (2): `_compute_attachment_count()`, `action_open_attachments()`

### `clinic.patient.identifier.type`
- Python class: `ClinicPatientIdentifierType`
- Owner file: `models/patient_identifier.py`
- Fields (17): `name`, `code`, `active`, `sequence`, `validation_regex`, `validation_help`, `force_case`, `use_sequence`, `sequence_id`, `is_mrn`, `is_national_id`, `is_passport`, `is_tax_id`, `is_insurance_member`, `single_primary_per_patient`, `partner_mapping`, `barcode_symbology`
- Methods (1): `name_get()`

### `clinic.patient.identifier`
- Python class: `ClinicPatientIdentifier`
- Owner file: `models/patient_identifier.py`
- Fields (14): `patient_id`, `company_id`, `type_id`, `value`, `is_primary`, `active`, `issue_date`, `expiry_date`, `issuing_authority`, `place_of_issue`, `status`, `revoked`, `display_name`, `notes`
- Methods (16): `_compute_display_name()`, `_compute_status()`, `_onchange_type_force_case()`, `_apply_force_case()`, `_validate_against_regex()`, `_validate_known_formats()`, `_ensure_single_primary()`, `_sync_with_patient_mrn()`, `_map_to_partner_if_configured()`, `_check_dates()`, `_check_value_constraints()`, `_check_single_primary_flag()`, `create()`, `write()`, `action_set_primary()`, `name_get()`

### `clinic.patient.vital`
- Python class: `ClinicPatientVital`
- Owner file: `models/patient_vital.py`
- Fields (36): `patient_id`, `company_id`, `measured_datetime`, `measured_by`, `device_name`, `device_serial`, `device_type`, `bp_systolic`, `bp_diastolic`, `bp_map`, `heart_rate`, `respiratory_rate`, `temperature_c`, `spo2`, `height_cm`, `weight_kg`, `bmi`, `bsa`, `muac_cm`, `head_circumference_cm`, `pain_scale`, `gcs_eye`, `gcs_verbal`, `gcs_motor`, `gcs_total`, `blood_glucose_mgdl`, `is_latest`, `display_name`, `notes`, `attachment_count`, `bp_flag`, `hr_flag`, `rr_flag`, `temp_flag`, `spo2_flag`, `glucose_flag`
- Methods (13): `_compute_derivatives()`, `_compute_flags()`, `_compute_is_latest()`, `_compute_display_name()`, `_compute_attachment_count()`, `_check_plausible_ranges()`, `create()`, `write()`, `_action_open_generic()`, `action_open_patient()`, `action_open_attachments()`, `name_get()`, `_name_search()`

### `Extension: res.partner`
- Python class: `ResPartner`
- Owner file: `models/res_partner_inherit.py`
- Fields (23): `is_patient`, `patient_id`, `patient_code`, `patient_stage_id`, `patient_registered_date`, `patient_last_seen`, `is_vip_patient`, `patient_birth_date`, `patient_age_years`, `patient_age_display`, `patient_gender`, `nik`, `bpjs_no`, `medical_allergy_note`, `medical_condition_note`, `booking_count`, `encounter_count`, `invoice_count`, `attachment_count`, `coverage_count`, `wallet_balance`, `has_active_consent`, `currency_id`
- Methods (11): `_check_patient_link_consistency()`, `_onchange_is_patient()`, `create()`, `write()`, `_ensure_patient_card_created()`, `_compute_integration_counters()`, `_action_open_generic()`, `action_open_patient()`, `action_create_patient()`, `action_open_invoices()`, `action_open_attachments()`

### `Extension: res.users`
- Python class: `ResUsers`
- Owner file: `models/res_users_inherit.py`
- Fields (15): `patient_id`, `is_patient_user`, `patient_company_id`, `partner_is_patient`, `patient_code`, `patient_stage_id`, `patient_last_seen`, `wallet_balance`, `booking_count`, `encounter_count`, `invoice_count`, `coverage_count`, `attachment_count`, `has_active_consent`, `currency_id`
- Methods (13): `_compute_is_patient_user()`, `_compute_patient_company()`, `_compute_integration_counters()`, `_check_patient_partner_alignment()`, `_check_patient_company_membership()`, `create()`, `write()`, `_ensure_patient_link_post_create()`, `_ensure_patient_link_from_partner()`, `_action_open_generic()`, `action_open_patient()`, `action_open_invoices()`, `action_open_patient_attachments()`
