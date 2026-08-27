# ClinicOne — clinic_queue_room Full Structural Inventory

Functional baseline: **FINISHED / PRESERVED**.
Backup files whose filename begins with `0` are excluded.

## Active import graph

- `models/clinic_queue_stage.py`
- `models/clinic_queue_token.py`
- `models/clinic_queue.py`
- `models/clinic_room_assignment.py`
- `models/clinic_queue_event.py`
- `models/clinic_queue_channel.py`
- `models/clinic_queue_visit.py`
- `models/clinic_queue_ticket.py`
- `models/hr_doctor_inherit.py`

## Model / Field / Method inventory

### `clinic.queue.stage` — `models/clinic_queue_stage.py`

Class: `ClinicQueueStage`

**Fields**
- `name`
- `code`
- `mapped_state`
- `sequence`
- `active`
- `color`
- `fold`
- `company_id`
- `queue_type`
- `is_default`
- `require_room`
- `require_doctor`
- `require_treatment`
- `lock_patient_change`
- `lock_room_change_when_started`
- `room_type_id`
- `auto_assign_room`
- `auto_assign_doctor`
- `auto_create_procedure_session`
- `sla_target_wait_min`
- `sla_target_service_min`
- `activity_type_id`
- `escalate_group_ids`
- `escalate_user_ids`
- `mail_template_id`
- `mail_template_exit_id`
- `server_action_id`
- `server_action_exit_id`
- `next_stage_ids`
- `wip_limit`
- `active_queue_count`
- `is_wip_exceeded`

**Methods**
- `_compute_active_queue_count()`
- `_compute_is_wip_exceeded()`
- `_onchange_code()`
- `_onchange_is_default()`
- `validate_requirements()`
- `mapped_state_value()`
- `get_default_stage()`
- `_run_on_enter_hooks()`
- `_run_on_exit_hooks()`
- `_auto_assign_room()`
- `_auto_assign_doctor()`
- `create()`
- `write()`
- `_enforce_unique_default()`
- `_compute_display_name()`
- `name_get()`
- `name_search()`
- `_check_wip_limit()`
- `_check_unique_name_per_company_type()`
- `_check_code_mapped_alignment()`

### `clinic.room.assignment` — `models/clinic_room_assignment.py`

Class: `ClinicRoomAssignment`

**Fields**
- `name`
- `active`
- `company_id`
- `room_id`
- `queue_id`
- `room_type_id`
- `patient_id`
- `doctor_id`
- `treatment_id`
- `assigned_at`
- `assigned_by_id`
- `assigned_via`
- `service_start_at`
- `service_end_at`
- `released_at`
- `release_reason`
- `released_by_id`
- `state`
- `device_ids`
- `surcharge_product_id`
- `sale_order_id`
- `sale_line_id`
- `invoice_id`
- `analytic_account_id`
- `billable`
- `notes`
- `wait_before_service_min`
- `service_duration_min`
- `occupancy_duration_min`
- `is_active_assignment`

**Methods**
- `_compute_is_active()`
- `_compute_durations()`
- `_onchange_room_id()`
- `_check_room_capacity()`
- `_check_single_active_assignment_per_queue()`
- `_check_time_sequence()`
- `create()`
- `write()`
- `_link_queue_and_room()`
- `_active_assignment_count_for_room()`
- `_ensure_room_status_on_assign()`
- `_ensure_room_status_on_release()`
- `_auto_subscribe_partners()`
- `action_mark_service_start()`
- `action_mark_service_end()`
- `action_release()`
- `action_cancel()`
- `action_transfer()`
- `prepare_surcharge_line_vals()`
- `_compute_display_name()`
- `name_get()`
- `name_search()`

### `clinic.queue.ticket` — `models/clinic_queue_ticket.py`

Class: `ClinicQueueTicket`

**Fields**
- `name`
- `display_name`
- `company_id`
- `queue_id`
- `token_id`
- `channel_id`
- `patient_id`
- `doctor_id`
- `appointment_id`
- `visit_id`
- `room_id`
- `room_assignment_id`
- `state`
- `issue_time`
- `valid_until`
- `is_valid`
- `issued_by_user_id`
- `print_count`
- `note`

**Methods**
- `_check_doctor_flag()`
- `_compute_display_name()`
- `_compute_is_valid()`
- `_onchange_queue_fill()`
- `_onchange_token_fill()`
- `action_mark_used()`
- `action_cancel()`
- `action_reissue()`
- `action_print()`
- `create()`
- `write()`

### `clinic.queue.channel` — `models/clinic_queue_channel.py`

Class: `ClinicQueueChannel`

**Fields**
- `name`
- `code`
- `display_name`
- `sequence`
- `active`
- `description`
- `company_id`
- `is_default`
- `allow_walkin`
- `allow_booking`
- `allow_portal`
- `allow_kiosk`
- `allow_phone`
- `avg_service_time_min`
- `service_calendar_id`
- `surcharge_product_id`
- `allowed_stage_ids`
- `queue_ids`
- `queue_waiting_count`
- `queue_in_progress_count`

**Methods**
- `_compute_display_name()`
- `_compute_queue_stats()`
- `create()`
- `write()`
- `_enforce_single_default_per_company()`
- `get_default_channel()`
- `map_from_string()`
- `action_view_queues()`
- `name_get()`
- `name_search()`

### `hr.employee` — `models/hr_doctor_inherit.py`

Class: `HrEmployee`

**Fields**
- `is_doctor`
- `doctor_code`
- `license_number`
- `license_expiry_date`
- `board_certification`
- `specialty_ids`
- `skill_note`
- `availability_status`
- `max_parallel_cases`
- `is_available_for_queue`
- `allow_auto_assignment`
- `preferred_room_type_ids`
- `qualified_device_ids`
- `service_calendar_id`
- `default_appointment_slot_min`
- `queue_active_count`
- `queue_today_count`
- `queue_waiting_count`
- `assignment_active_count`
- `next_appointment_id`
- `analytic_account_id`
- `commission_percent`

**Methods**
- `_check_license_validity()`
- `_compute_is_available_for_queue()`
- `_compute_queue_stats()`
- `_compute_assignment_stats()`
- `_compute_next_appointment()`
- `can_take_new_case()`
- `action_set_on_duty()`
- `action_set_on_call()`
- `action_set_on_break()`
- `action_set_in_service()`
- `action_set_off_duty()`
- `action_view_queues()`
- `action_view_active_queues()`
- `action_view_room_assignments()`
- `action_view_next_appointment()`
- `action_open_schedule()`
- `create()`
- `write()`
- `_compute_display_name()`
- `name_get()`

### `clinic.appointment` — `models/appointment_inherit.py`

Class: `ClinicAppointment`

**Fields**
- `queue_id`
- `token_id`
- `room_id`
- `room_assignment_id`
- `queue_stage_id`
- `queue_state`
- `checkin_time`
- `clinic_service_start_at`
- `clinic_service_end_at`
- `checkout_time`
- `waiting_duration_min`
- `service_duration_min`
- `total_visit_duration_min`
- `is_checked_in`
- `has_active_queue`
- `membership_id`
- `insurance_policy_id`
- `authorization_id`
- `telemedicine_session_id`
- `patient_id`
- `doctor_id`
- `treatment_id`

**Methods**
- `_compute_queue_mirrors()`
- `_compute_durations()`
- `_compute_flags()`
- `_check_doctor_flag()`
- `_onchange_queue_id()`
- `action_check_in()`
- `action_check_out()`
- `action_issue_token()`
- `action_create_queue()`
- `_action_create_queue_from_appointment()`
- `action_assign_room()`
- `action_release_room()`
- `action_start_service()`
- `action_finish_service()`
- `action_cancel_queue()`
- `action_mark_no_show()`
- `_action_view_queue()`
- `action_view_token()`
- `action_view_room_assignment()`
- `_post_finish_feedback()`
- `write()`

### `clinic.queue.token` — `models/clinic_queue_token.py`

Class: `ClinicQueueToken`

**Fields**
- `name`
- `code`
- `series`
- `queue_type`
- `company_id`
- `token_date`
- `token_number`
- `patient_id`
- `appointment_id`
- `treatment_id`
- `priority`
- `channel`
- `queue_id`
- `stage_id`
- `doctor_id`
- `room_type_id`
- `room_id`
- `state`
- `issued_at`
- `called_at`
- `served_at`
- `cancelled_at`
- `expired_at`
- `called_by_id`
- `served_by_id`
- `printed`
- `print_count`
- `last_printed_at`
- `display_channel`
- `kiosk_ref`
- `position_in_series`
- `notes`

**Methods**
- `_default_series()`
- `_compute_position_in_series()`
- `create()`
- `write()`
- `_format_code()`
- `_lock_and_get_next_number()`
- `action_issue()`
- `action_call()`
- `action_skip()`
- `action_serve()`
- `action_cancel()`
- `action_expire()`
- `action_create_queue()`
- `_action_view_queue()`
- `_compute_display_name()`
- `name_get()`
- `name_search()`
- `_check_series()`
- `_check_token_number()`
- `as_display_payload()`

### `clinic.queue` — `models/clinic_queue.py`

Class: `ClinicQueue`

**Fields**
- `channel_id`
- `name`
- `sequence`
- `active`
- `company_id`
- `queue_type`
- `channel`
- `priority`
- `patient_id`
- `doctor_id`
- `treatment_id`
- `appointment_id`
- `token_id`
- `sale_order_id`
- `invoice_id`
- `analytic_account_id`
- `planned_product_ids`
- `room_id`
- `room_assignment_id`
- `stage_id`
- `state`
- `checkin_time`
- `start_time`
- `end_time`
- `waiting_duration_min`
- `service_duration_min`
- `total_duration_min`
- `sla_wait_target_min`
- `sla_service_target_min`
- `sla_wait_breached`
- `sla_service_breached`
- `notes`

**Methods**
- `_compute_durations()`
- `_compute_sla_targets()`
- `_compute_sla_breaches()`
- `_onchange_stage_id()`
- `create()`
- `write()`
- `_check_time_order()`
- `_find_stage_by_mapped_state()`
- `_move_to_mapped_state()`
- `action_start()`
- `action_hold()`
- `action_resume()`
- `action_done()`
- `action_cancel()`
- `action_no_show()`
- `action_assign_room()`
- `action_open_room_assignment()`
- `action_release_room()`
- `action_check_and_escalate_sla()`
- `_create_escalation_activity()`
- `_compute_display_name()`
- `name_get()`
- `name_search()`

### `clinic.treatment` — `models/treatment_inherit.py`

Class: `ClinicTreatment`

**Fields**
- `queue_id`
- `token_id`
- `room_id`
- `room_assignment_id`
- `patient_id`
- `doctor_id`
- `queue_stage_id`
- `queue_state`
- `checkin_time`
- `clinic_start_at`
- `clinic_end_at`
- `waiting_duration_min`
- `procedure_duration_min`
- `total_visit_duration_min`
- `required_device_ids`
- `optional_device_ids`
- `used_device_ids`
- `preferred_room_type_id`
- `sale_order_id`
- `sale_line_id`
- `invoice_id`
- `analytic_account_id`
- `billable`
- `planned_product_ids`
- `has_active_queue`
- `is_in_procedure`
- `membership_id`
- `insurance_policy_id`
- `authorization_id`
- `telemedicine_session_id`

**Methods**
- `_compute_queue_mirrors()`
- `_compute_durations()`
- `_compute_flags()`
- `_check_doctor_flag()`
- `_check_required_devices_present()`
- `_onchange_queue_id()`
- `action_attach_queue()`
- `action_assign_room()`
- `action_release_room()`
- `action_start_procedure()`
- `action_pause_procedure()`
- `action_resume_procedure()`
- `action_finish_procedure()`
- `action_cancel_procedure()`
- `action_log_devices_used()`
- `prepare_so_line_vals()`
- `action_view_queue()`
- `action_view_room_assignment()`
- `create()`
- `write()`

### `clinic.queue.event` — `models/clinic_queue_event.py`

Class: `ClinicQueueEvent`

**Fields**
- `name`
- `active`
- `company_id`
- `queue_id`
- `token_id`
- `room_id`
- `room_assignment_id`
- `patient_id`
- `doctor_id`
- `category`
- `event_type`
- `severity`
- `old_stage_id`
- `new_stage_id`
- `old_state`
- `new_state`
- `event_datetime`
- `waiting_duration_min_at_event`
- `service_duration_min_at_event`
- `total_duration_min_at_event`
- `actor_user_id`
- `actor_employee_id`
- `source_model`
- `source_res_id`
- `res_model_id`
- `ip_address`
- `display_channel`
- `kiosk_ref`
- `summary`
- `details`
- `payload_json`

**Methods**
- `create()`
- `write()`
- `_compute_queue_durations_snapshot()`
- `log_generic()`
- `log_stage_change()`
- `log_state_change()`
- `log_room_assignment()`
- `log_token_action()`
- `log_sla_breach()`
- `log_billing()`
- `log_feedback_requested()`
- `action_view_queue()`
- `action_view_room_assignment()`
- `_compute_display_name()`
- `name_get()`
- `name_search()`

### `clinic.queue.visit` — `models/clinic_queue_visit.py`

Class: `ClinicQueueVisit`

**Fields**
- `name`
- `display_name`
- `company_id`
- `patient_id`
- `doctor_id`
- `queue_id`
- `token_id`
- `channel_id`
- `appointment_id`
- `treatment_id`
- `room_id`
- `room_assignment_id`
- `checkin_time`
- `start_time`
- `end_time`
- `state`
- `waiting_duration_min`
- `service_duration_min`
- `total_duration_min`
- `sale_order_id`
- `sale_line_id`
- `invoice_id`
- `analytic_account_id`
- `billable`
- `used_product_ids`
- `notes`
- `internal_note`

**Methods**
- `_check_doctor_flag()`
- `_check_time_order()`
- `_compute_display_name()`
- `_compute_durations()`
- `_onchange_queue_mirrors()`
- `action_start()`
- `action_finish()`
- `action_cancel()`
- `action_no_show()`
- `action_view_queue()`
- `create()`
- `write()`

### `res.partner` — `models/res_partner_inherit.py`

Class: `ResPartner`

**Fields**
- `default_queue_type`
- `default_channel`
- `default_priority`
- `preferred_room_type_id`
- `preferred_doctor_id`
- `queue_blacklisted`
- `is_vip`
- `membership_id`
- `insurance_policy_id`
- `queue_active_count`
- `queue_total_count`
- `queue_last_id`
- `last_visit_time`
- `avg_wait_min`
- `token_today_count`
- `token_last_id`
- `next_appointment_id`
- `has_active_queue`

**Methods**
- `_compute_queue_stats()`
- `_compute_last_records()`
- `_compute_token_stats()`
- `_compute_next_appointment()`
- `_compute_flags()`
- `_check_preferred_doctor()`
- `_default_queue_vals()`
- `action_quick_issue_token()`
- `action_create_queue()`
- `action_view_queues()`
- `action_view_active_queues()`
- `action_view_tokens()`
- `action_view_room_assignments()`
- `action_view_next_appointment()`
- `_clinic_display_badges()`
