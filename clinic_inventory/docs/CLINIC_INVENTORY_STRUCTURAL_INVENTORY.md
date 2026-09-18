# Clinic Inventory — Full Structural Inventory

Baseline: active source supplied by the user. Files beginning with digit `0` are excluded.

- Active model classes/extensions: **25**
- User-facing persistent models: **7**
- Technical/internal models: **3**
- Odoo core model extensions: **15**

## `clinic.doctor.allowed.product`
- File: `models/doctor_allowed_products.py`
- Python class: `ClinicDoctorAllowedProduct`
- Fields: `name`, `doctor_id`, `company_id`, `rule_type`, `product_id`, `category_id`, `action`, `priority`, `date_start`, `date_end`, `archived`, `is_active`, `note`
- Methods: `_compute_name()`, `_today()`, `_in_validity_window()`, `_compute_is_active()`, `_check_target_presence()`, `_check_date_range()`, `_matches_product()`, `clinic_doctor_can_use_product()`, `clinic_allowed_product_domain()`, `is_product_explicitly_allowed()`, `action_view_allowed_products()`, `name_get()`

## `EXTEND `hr.employee``
- File: `models/doctor_allowed_products.py`
- Python class: `HREmployee`
- Fields: `clinic_allowed_rule_ids`, `clinic_allowed_rules_count`
- Methods: `_compute_clinic_rules_count()`, `action_view_allowed_rules()`, `clinic_is_product_allowed()`, `clinic_allowed_product_domain()`

## `clinic.integration.mixin`
- File: `models/integration_hooks.py`
- Python class: `ClinicIntegrationMixin`
- Fields: none declared in this class
- Methods: `_clinic_model_available()`, `_clinic_method_available()`, `_clinic_call_if_available()`, `_clinic_notify_success()`, `_clinic_notify_warning()`, `_clinic_notify_danger()`, `_clinic_company_defaults()`, `_clinic_emit_event()`

## `clinic.integration.event.log`
- File: `models/integration_hooks.py`
- Python class: `ClinicIntegrationEventLog`
- Fields: `event_code`, `ctx_model`, `ctx_res_id`, `payload_json`, `handled_by`, `status`, `message`, `company_id`, `user_id`
- Methods: `set_dispatched()`, `set_error()`

## `clinic.integration.service`
- File: `models/integration_hooks.py`
- Python class: `ClinicIntegrationService`
- Fields: none declared in this class
- Methods: `register_handler()`, `unregister_handler()`, `list_handlers()`, `emit_event()`, `_dispatch_to_handler()`, `_discover_generic_handlers()`

## `clinic.integration.event.catalog`
- File: `models/integration_hooks.py`
- Python class: `ClinicIntegrationEventCatalog`
- Fields: none declared in this class
- Methods: none declared in this class

## `clinic.inventory.adjustment`
- File: `models/inventory_adjustment.py`
- Python class: `ClinicInventoryAdjustment`
- Fields: `name`, `date`, `state`, `company_id`, `warehouse_id`, `root_location_id`, `include_zero_expected`, `use_snapshot`, `snapshot_at`, `route_expired_to_quarantine`, `enforce_governance`, `line_ids`, `total_lines`, `total_diff_qty`, `move_ids`, `generated_move_count`, `responsible_id`, `note`, `lot_id`
- Methods: `_get_expiration_field_name()`, `_compute_expired_flag()`, `_compute_totals()`, `_compute_move_count()`, `create()`, `action_prepare_lines()`, `action_confirm()`, `action_cancel()`, `action_reset_to_draft()`, `action_apply()`, `_resolve_inventory_location()`, `_resolve_quarantine_location()`, `_resolve_location_policy()`, `_clinic_hook_pre_confirm()`, `_clinic_hook_post_apply()`

## `clinic.inventory.adjustment.line`
- File: `models/inventory_adjustment.py`
- Python class: `ClinicInventoryAdjustmentLine`
- Fields: `adjustment_id`, `sequence`, `product_id`, `product_uom`, `lot_id`, `location_id`, `expected_qty_current`, `snapshot_qty`, `counted_qty`, `diff_qty_current`, `diff_qty_snapshot`, `is_expired`, `note`
- Methods: `_domain_location_internal()`, `_compute_expected_current()`, `_compute_differences()`, `_get_expiration_field_name()`, `_compute_expired_flag()`, `_snapshot_expected()`, `_check_not_service()`, `_check_uom_category()`, `_check_counted_non_negative()`, `_is_lot_expired()`, `_clinic_hook_before_line_move()`

## `clinic.patient.product.history`
- File: `models/patient_product_history.py`
- Python class: `ClinicPatientProductHistory`
- Fields: `patient_id`, `product_id`, `product_tmpl_id`, `lot_id`, `date_use`, `qty`, `uom_id`, `direction`, `purpose`, `signed_qty`, `doctor_id`, `treatment_ref`, `picking_id`, `move_id`, `usage_id`, `warehouse_id`, `location_id`, `location_dest_id`, `company_id`, `responsible_id`, `note`, `display_name`
- Methods: `_compute_display_name()`, `_compute_signed_qty()`, `_check_positive_qty()`, `_check_patient_is_person()`, `action_view_picking()`, `action_view_move()`, `_clinic_treatment_reference_models()`, `log_from_move()`, `log_from_picking()`, `log_from_usage_line()`, `_infer_direction_from_locations()`, `_clinic_hook_post_create_history()`, `clinic_find_by_patient()`, `clinic_patient_product_summary()`

## `EXTEND `product.category``
- File: `models/product_category.py`
- Python class: `ProductCategory`
- Fields: `product_tmpl_ids`, `clinic_default_usage_type`, `clinic_default_has_expiration`, `clinic_default_shelf_life_days`, `clinic_default_expiration_alert_days`, `clinic_default_storage_requirement`, `clinic_default_storage_min_c`, `clinic_default_storage_max_c`, `clinic_default_tracking`, `clinic_default_regulatory_class`, `clinic_allowed_brand_ids`, `clinic_restricted_to_allowed_brands`, `clinic_replenishment_policy`, `clinic_default_min_qty`, `clinic_default_target_qty`, `clinic_consumption_location_id`, `clinic_count_products`, `clinic_count_expirable`, `clinic_has_any_expirable`
- Methods: `_compute_clinic_counts()`, `_check_default_storage_temperature()`, `_check_default_min_target_qty()`, `clinic_get_category_default_template_vals()`, `action_apply_defaults_to_products()`, `action_view_products_expiring_soon()`, `_clinic_hook_validate_brand()`, `_clinic_hook_default_consumption_location()`, `clinic_validate_brand()`, `clinic_get_default_consumption_location()`

## `EXTEND `product.product``
- File: `models/product_product.py`
- Python class: `ProductProduct`
- Fields: `usage_type`, `is_medication`, `is_cosmetic`, `is_service_flag`, `is_stockable_flag`, `brand_partner_id`, `regulatory_class`, `dosage_form`, `active_ingredients`, `dosage_strength`, `volume_ml`, `weight_g`, `has_expiration`, `shelf_life_days`, `expiration_alert_days`, `storage_requirement`, `storage_min_c`, `storage_max_c`, `contraindications`, `instructions`, `membership_pricing_policy`, `ecommerce_is_sellable`, `additional_barcodes`, `next_expiration_date_variant`, `clinic_onhand_qty`, `clinic_incoming_qty`, `clinic_outgoing_qty`, `clinic_min_qty`, `clinic_target_qty`
- Methods: `_get_expiration_field_name()`, `_compute_next_expiration_date_variant()`, `_compute_clinic_stock_metrics()`, `action_view_expiring_lots()`, `action_view_stock_moves()`, `name_get()`, `clinic_is_sellable_online()`, `clinic_get_membership_price()`, `clinic_get_pricing_context()`, `clinic_prepare_consumption_move_vals()`, `clinic_validate_usage_for_operation()`, `clinic_domain_expiring_soon_by_variant()`, `_clinic_hook_quant_location_domain()`, `_clinic_hook_move_domains_for_location_scope()`, `_clinic_hook_finalize_consumption_vals()`, `_check_min_target_qty()`, `clinic_has_sufficient_stock()`

## `EXTEND `product.template``
- File: `models/product_template.py`
- Python class: `ProductTemplate`
- Fields: `usage_type`, `is_medication`, `is_cosmetic`, `is_service_flag`, `is_stockable_flag`, `brand_partner_id`, `regulatory_class`, `dosage_form`, `active_ingredients`, `dosage_strength`, `volume_ml`, `weight_g`, `has_expiration`, `shelf_life_days`, `expiration_alert_days`, `storage_requirement`, `storage_min_c`, `storage_max_c`, `next_expiration_date`, `contraindications`, `instructions`, `membership_pricing_policy`, `ecommerce_is_sellable`, `additional_barcodes`
- Methods: `_check_usage_type_vs_type()`, `_compute_flags()`, `_get_expiration_field_name()`, `_compute_next_expiration_date()`, `_onchange_usage_type()`, `_onchange_has_expiration()`, `_check_storage_temperature()`, `_check_expiration_rules()`, `_check_usage_type_vs_product_type()`, `write()`, `action_view_expiring_lots()`, `action_view_stock_moves()`, `name_get()`, `_clinic_hook_is_doctor_allowed()`, `_clinic_hook_allowed_treatments()`, `_clinic_hook_treatment_model_name()`, `_clinic_hook_membership_price()`, `_clinic_hook_pricing_context()`, `_clinic_hook_is_sellable_online()`, `_clinic_hook_prepare_consumption_vals()`, `_clinic_hook_post_write()`, `clinic_is_sellable_online()`, `clinic_get_membership_price()`, `clinic_get_pricing_context()`, `clinic_prepare_consumption_move_vals()`, `clinic_validate_usage_for_operation()`, `clinic_domain_expiring_soon()`

## `EXTEND `res.company``
- File: `models/res_config_settings.py`
- Python class: `ResCompany`
- Fields: `clinic_inventory_default_expiry_policy`, `clinic_inventory_default_replenishment_scope`, `clinic_inventory_temperature_monitoring`, `clinic_inventory_auto_create_room_locations`, `clinic_inventory_default_warehouse_id`, `clinic_inventory_enforce_fefo`, `clinic_inventory_min_shelf_life_days`, `clinic_inventory_default_expiration_alert_days`, `clinic_inventory_reorder_buffer_percent`, `clinic_inventory_rounding_mode_default`, `clinic_inventory_enable_patient_history`, `clinic_inventory_enable_treatment_consumption`, `clinic_inventory_allow_expired_exception`
- Methods: none declared in this class

## `EXTEND `res.config.settings``
- File: `models/res_config_settings.py`
- Python class: `ResConfigSettings`
- Fields: `clinic_default_warehouse_id`, `clinic_default_expiry_policy`, `clinic_default_replenishment_scope`, `clinic_enable_temperature_monitoring`, `clinic_auto_create_room_locations`, `clinic_enforce_fefo`, `clinic_min_shelf_life_days`, `clinic_default_expiration_alert_days`, `clinic_reorder_buffer_percent`, `clinic_rounding_mode_default`, `clinic_enable_patient_history`, `clinic_enable_treatment_consumption`, `clinic_allow_expired_exception`, `clinic_block_incoming_without_temperature`, `clinic_quality_require_approval_for_scrap`, `clinic_portal_enable_inventory`, `clinic_warehouse_count`
- Methods: `_compute_clinic_warehouse_count()`, `action_apply_defaults_to_clinic_warehouses()`, `action_bootstrap_clinic_locations()`, `action_apply_product_defaults()`, `set_values()`, `clinic_get_company_defaults()`

## `EXTEND `stock.location``
- File: `models/stock_location.py`
- Python class: `StockLocation`
- Fields: `clinic_location_code`, `clinic_is_treatment_room`, `clinic_is_pharmacy`, `clinic_is_quarantine`, `clinic_room_capacity`, `clinic_room_notes`, `clinic_temperature_monitoring`, `clinic_temp_min_c`, `clinic_temp_max_c`, `clinic_expiry_policy`, `clinic_restrict_to_allowed_categories`, `clinic_allowed_categ_ids`, `clinic_warehouse_id`, `clinic_onhand_qty`, `clinic_waiting_in_moves`, `clinic_waiting_out_moves`
- Methods: `_check_internal_usage_for_roles()`, `_check_temperature_range()`, `_onchange_location_role()`, `_compute_clinic_warehouse()`, `_compute_clinic_stock_counters()`, `action_view_quants()`, `action_view_moves()`, `action_view_pickings()`, `name_get()`, `clinic_expiration_decision()`, `clinic_validate_temperature()`, `clinic_validate_product_allowed()`, `_clinic_hook_is_valid_for_operation()`, `_clinic_resolve_warehouse()`, `clinic_room_path()`

## `EXTEND `stock.lot``
- File: `models/stock_lot.py`
- Python class: `StockLot`
- Fields: `clinic_supplier_batch`, `clinic_manufacture_date`, `clinic_received_date`, `clinic_quality_state`, `clinic_quarantine_reason`, `clinic_expiration_alert_days`, `clinic_days_to_expiry`, `clinic_expiration_state`, `clinic_is_expired`, `clinic_quants_count`, `clinic_onhand_qty`, `clinic_primary_location_id`
- Methods: `_get_expiration_field_name()`, `_compute_clinic_expiry()`, `_compute_clinic_counters()`, `_check_expiration_presence_when_required()`, `_check_mfg_before_expiry()`, `_check_received_after_mfg()`, `write()`, `_clinic_resolve_location_policy()`, `action_view_quants()`, `action_view_moves()`, `action_suggest_quarantine_transfer()`, `name_get()`, `clinic_get_is_expired()`, `clinic_days_until_expiry()`, `clinic_policy_status_in_location()`, `_clinic_hook_post_write()`

## `EXTEND `stock.move``
- File: `models/stock_move.py`
- Python class: `StockMove`
- Fields: `clinic_adjustment_id`, `clinic_usage_id`, `clinic_operation_type`, `clinic_notes`, `clinic_has_expired_reserved`, `clinic_is_quarantine_move`
- Methods: `_get_expiration_field_name()`, `_compute_clinic_operation_type()`, `_compute_clinic_has_expired_reserved()`, `_compute_clinic_is_quarantine_move()`, `_check_service_product_not_moved()`, `_action_confirm()`, `_action_assign()`, `_action_done()`, `_clinic_pre_confirm_checks()`, `_clinic_pre_done_checks()`, `_clinic_check_category_governance()`, `_clinic_validate_expiration_on_reserved_lots()`, `_clinic_resolve_location_policy()`, `action_view_move_lines()`, `action_view_reserved_lots()`, `clinic_is_quarantine_related()`, `clinic_collect_reserved_expired_lots()`, `_clinic_hook_post_confirm()`, `_clinic_hook_post_done()`, `_do_unreserve()`

## `EXTEND `stock.picking``
- File: `models/stock_picking.py`
- Python class: `StockPicking`
- Fields: `clinic_operation_type`, `clinic_receipt_temperature_c`, `clinic_is_quarantine_transfer`, `clinic_notes`, `clinic_has_expired_lines`
- Methods: `_get_expiration_field_name()`, `_compute_clinic_operation_type()`, `_compute_clinic_expired_flags()`, `_check_receipt_temperature_range()`, `_check_quarantine_dest()`, `button_validate()`, `_clinic_validate_before_button_validate()`, `_clinic_check_category_governance()`, `_clinic_check_expiration_policy()`, `_clinic_check_temperature_at_receipt()`, `_clinic_resolve_location_policy()`, `_clinic_post_transfer_hook()`, `action_view_quarantine_destination()`, `name_get()`, `clinic_has_any_expired_lot()`, `_clinic_hook_pre_validate()`, `_clinic_hook_post_validate()`

## `EXTEND `stock.quant``
- File: `models/stock_quant.py`
- Python class: `StockQuant`
- Fields: `clinic_usage_type`, `clinic_has_expiration`, `clinic_expiration_alert_days`, `clinic_storage_requirement`, `clinic_storage_min_c`, `clinic_storage_max_c`, `clinic_regulatory_class`, `clinic_is_treatment_room`, `clinic_is_pharmacy`, `clinic_is_quarantine`, `clinic_days_to_expiry`, `clinic_expiration_state`, `clinic_is_policy_blocked`, `clinic_note`
- Methods: `_get_expiration_field_name()`, `_compute_clinic_expiry()`, `_compute_clinic_policy_block()`, `_check_clinic_location_governance()`, `write()`, `_clinic_resolve_location_policy()`, `action_view_moves()`, `action_view_lot()`, `action_suggest_quarantine_transfer()`, `name_get()`, `clinic_get_is_expired()`, `clinic_should_block_here()`, `clinic_validate_temperature()`, `_clinic_hook_post_write()`, `_clinic_resolve_warehouse()`, `_clinic_get_quarantine_location()`

## `EXTEND `stock.warehouse.orderpoint``
- File: `models/stock_reorderpoint.py`
- Python class: `StockWarehouseOrderpoint`
- Fields: `clinic_scope`, `clinic_min_shelf_life_days`, `clinic_buffer_percent`, `clinic_rounding_mode`, `clinic_note`, `clinic_onhand_qty`, `clinic_usable_onhand_qty`, `clinic_incoming_qty`, `clinic_outgoing_qty`, `clinic_virtual_available_qty`, `clinic_suggested_qty`, `clinic_last_suggested_on`, `clinic_last_run_by`
- Methods: `_check_buffer_percent()`, `_check_min_shelf_life()`, `_rop_field_name_min()`, `_rop_field_name_max()`, `_clinic_location_domain()`, `_clinic_move_domains()`, `_clinic_get_expiration_field()`, `_compute_clinic_metrics()`, `_compute_clinic_suggestion()`, `_clinic_apply_rounding()`, `action_view_scope_quants()`, `action_view_scope_moves()`, `action_execute_replenishment()`, `_clinic_hook_replenish_via_internal_transfer()`, `_clinic_hook_replenish_via_purchase()`, `_clinic_hook_replenish_via_manufacturing()`, `name_get()`, `clinic_get_suggestion()`

## `EXTEND `stock.rule``
- File: `models/stock_rule.py`
- Python class: `StockRule`
- Fields: `clinic_enforce_fefo`, `clinic_min_shelf_life_days`, `clinic_replenishment_scope`, `clinic_destination_policy`, `clinic_allow_expired_in_exception`, `clinic_generated_move_count`
- Methods: `_domain_recent_moves()`, `_compute_clinic_generated_move_count()`, `_check_min_shelf_life()`, `_check_destination_policy()`, `_get_stock_move_values()`, `_clinic_resolve_destination_location()`, `clinic_location_domain_for_scope()`, `action_view_recent_moves()`, `_clinic_hook_adjust_move_values()`, `clinic_should_use_fefo()`, `clinic_min_shelf_life_threshold()`, `clinic_debug_preview_move_values()`

## `EXTEND `stock.scrap``
- File: `models/stock_scrap.py`
- Python class: `StockScrap`
- Fields: `clinic_disposition`, `clinic_scrap_reason`, `clinic_notes`, `clinic_reported_by`, `clinic_reported_date`, `clinic_approved_by`, `clinic_approved_date`, `clinic_is_expired_lot`, `clinic_days_to_expiry`
- Methods: `_get_expiration_field_name()`, `_compute_clinic_expiry_flags()`, `_check_not_service()`, `_check_positive_qty()`, `_onchange_reason_default_disposition()`, `_clinic_check_category_governance()`, `_clinic_check_expiration_reason_alignment()`, `action_validate()`, `_clinic_pre_validate_checks()`, `_clinic_action_move_to_quarantine()`, `_clinic_resolve_quarantine_location_from_source()`, `_clinic_resolve_warehouse_from_location()`, `name_get()`, `_clinic_hook_pre_validate()`, `_clinic_hook_post_validate()`, `_clinic_hook_return_to_supplier()`

## `EXTEND `stock.warehouse``
- File: `models/stock_warehouse.py`
- Python class: `StockWarehouse`
- Fields: `is_clinic_warehouse`, `clinic_pharmacy_location_id`, `clinic_treatment_root_location_id`, `clinic_quarantine_location_id`, `clinic_expiry_blocking_policy`, `clinic_replenishment_scope`, `clinic_temperature_monitoring`, `clinic_auto_create_room_locations`, `clinic_count_internal_locations`, `clinic_count_treatment_rooms`, `clinic_count_quarantine_stock`
- Methods: `_compute_clinic_counts()`, `_check_locations_under_warehouse()`, `_clinic_is_child_of_view()`, `_onchange_is_clinic_warehouse()`, `action_view_internal_locations()`, `action_view_quants()`, `action_view_pickings()`, `action_view_moves()`, `_get_related_picking_type_ids()`, `clinic_compute_replenishment_suggestions()`, `clinic_should_block_expired()`, `clinic_should_warn_expired()`, `_clinic_hook_location_domain_for_replenishment()`, `_clinic_hook_validate_temperature()`, `_clinic_hook_expiration_check()`, `clinic_get_internal_location_domain()`, `clinic_get_room_location_domain()`, `clinic_validate_temperature()`, `clinic_expiration_decision()`, `clinic_location_for_consumption()`

## `clinic.treatment.product.usage`
- File: `models/treatment_product_usage.py`
- Python class: `ClinicTreatmentProductUsage`
- Fields: `name`, `date_usage`, `state`, `company_id`, `warehouse_id`, `patient_id`, `doctor_id`, `treatment_ref`, `notes`, `src_location_id`, `dest_location_id`, `line_ids`, `total_lines`, `total_qty`, `move_ids`, `responsible_id`
- Methods: `_compute_totals()`, `_onchange_warehouse_id()`, `create()`, `action_confirm()`, `action_cancel()`, `action_reset_to_draft()`, `action_consume()`, `_validate_ready()`, `_create_consumption_moves()`, `_apply_done_move_lines()`, `_clinic_treatment_reference_models()`, `_clinic_resolve_default_source_location()`, `_clinic_resolve_consumption_sink()`, `_clinic_optional_doctor_allowed_check()`, `_clinic_hook_pre_consume()`, `_clinic_hook_post_consume()`

## `clinic.treatment.product.usage.line`
- File: `models/treatment_product_usage.py`
- Python class: `ClinicTreatmentProductUsageLine`
- Fields: `usage_id`, `sequence`, `product_id`, `product_uom`, `product_uom_qty`, `lot_id`, `note`, `qty_onhand_at_source`
- Methods: `_compute_onhand_at_source()`, `_check_positive_qty()`, `_product_requires_lot()`, `_has_sufficient_stock_at_source()`, `_prepare_consumption_move_vals()`




