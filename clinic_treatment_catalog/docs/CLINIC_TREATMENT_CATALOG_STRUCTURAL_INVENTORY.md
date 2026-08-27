# ClinicOne `clinic_treatment_catalog` — Full Structural Inventory

## Scope

- Project: **ClinicOne**
- Addon: **clinic_treatment_catalog**
- Target: **Odoo 19 CE**
- Functional baseline: **FINISHED / preserved**
- Backup files whose filename begins with `0`: **excluded**
- Dormant engines/bridges remain preserved but are not activated.

## Active source inventory

### `ClinicPricelistBridge`
- File: `models/bridges/bridge_pricing.py`
- Python class: `ClinicPricelistBridge`
- Methods: `compute_treatment_price`, `compute_bundle_price`, `_base_price_treatment`, `_base_price_bundle`, `_service_product`, `_engine_order`, `_engine_flags`, `_default_priority_for_engine`, `_kind_for_engine`, `_get_engine`, `_resolve_company`, `_is_bridge_enabled`, `_resolve_pricelist`, `_assert_single`, `_ensure_float`

### `ClinicConsentTemplate`
- File: `models/bridges/integration_consent.py`
- Python class: `ClinicConsentTemplate`
- Fields: `sequence`, `name`, `code`, `active`, `scope`, `category`, `requires_guardian`, `requires_witness`, `validity_days`, `allow_reuse`, `default_item_ids`, `version_ids`, `latest_version_id`, `notes`, `treatment_id`
- Methods: `_compute_latest_version`

### `ClinicConsentTemplateItem`
- File: `models/bridges/integration_consent.py`
- Python class: `ClinicConsentTemplateItem`
- Fields: `sequence`, `template_id`, `label`, `required`, `default_value`, `notes`

### `ClinicConsentTemplateVersion`
- File: `models/bridges/integration_consent.py`
- Python class: `ClinicConsentTemplateVersion`
- Fields: `template_id`, `version`, `title`, `body_html`, `effective_from`, `effective_to`, `changelog`, `state`

### `clinic.consent.request`
- File: `models/bridges/integration_consent.py`
- Python class: `ClinicConsentRequest`
- Fields: `reference`, `display_name`, `company_id`, `branch_id`, `template_id`, `version_id`, `title`, `content_html`, `scope`, `patient_id`, `staff_assignment_id`, `created_by_id`, `requested_by_id`, `witness_staff_id`, `guardian_required`, `guardian_name`, `guardian_relation`, `guardian_id_no`, `patient_signature`, `guardian_signature`, `witness_signature`, `e_sign_provider`, `e_sign_reference`, `e_sign_url`, `e_sign_status`, `e_sign_last_sync`, `e_sign_payload`, `has_e_signature`, `signer_ip`, `signer_user_agent`, `signed_at`, `expires_at`, `revoked_at`, `revoke_reason`, `is_valid`, `validity_days`, `item_ids`, `pdf_attachment_id`, `attachment_count`, `invoice_id`, `state`, `notes`
- Methods: `_compute_scope`, `_compute_has_e_signature`, `_compute_display_name`, `_compute_is_valid`, `_compute_attachment_count`, `create`, `_onchange_template`, `_check_version_belongs_to_template`, `_calc_expires_at`, `action_request`, `action_mark_signed`, `action_revoke`, `action_expire`, `action_cancel`, `ensure_valid_consent`, `name_get`, `cron_expire_consents`

### `ClinicConsentRequestItem`
- File: `models/bridges/integration_consent.py`
- Python class: `ClinicConsentRequestItem`
- Fields: `sequence`, `request_id`, `label`, `required`, `value`, `notes`
- Methods: `_check_required_agreement`

### `ClinicStaffConsentMixin`
- File: `models/bridges/integration_consent.py`
- Python class: `ClinicStaffConsentMixin`
- Methods: `require_consent`

### `ClinicPricingMixin`
- File: `models/mixin_pricing.py`
- Python class: `ClinicPricingMixin`
- Methods: `_round_price`, `_get_settings`, `_safe_get_model`, `_format_money`, `_minutes_from_duration`, `_price_component`, `_apply_minimum`, `_compose_price_result`, `_pricelist_get_price`, `_compute_local_formula`, `_summarize_components`

### `inherit:res.company`
- File: `models/res_config_settings.py`
- Python class: `ResCompany`
- Fields: `clinic_default_pricelist_id`, `clinic_default_service_category_id`, `clinic_enable_bridge_pricing`, `clinic_rounding_policy`, `clinic_pricing_tax_included`, `clinic_default_surcharge_applicable`, `clinic_default_insurance_applicable`, `clinic_booking_price_preview`, `clinic_booking_include_insurance`, `clinic_ecom_show_disclaimer`, `clinic_ecom_disclaimer`, `clinic_membership_stacking`, `clinic_seq_treatment_code_id`, `clinic_seq_treatment_category_code_id`, `clinic_seq_treatment_tag_code_id`, `clinic_seq_treatment_bundle_code_id`, `clinic_seq_treatment_pricelist_code_id`, `clinic_seq_treatment_attribute_code_id`, `clinic_seq_treatment_attribute_value_code_id`

### `inherit:res.config.settings`
- File: `models/res_config_settings.py`
- Python class: `ResConfigSettings`
- Fields: `clinic_default_pricelist_id`, `clinic_default_service_category_id`, `clinic_enable_bridge_pricing`, `clinic_rounding_policy`, `clinic_pricing_tax_included`, `clinic_default_surcharge_applicable`, `clinic_default_insurance_applicable`, `clinic_booking_price_preview`, `clinic_booking_include_insurance`, `clinic_ecom_show_disclaimer`, `clinic_ecom_disclaimer`, `clinic_membership_stacking`, `clinic_seq_treatment_code_id`, `clinic_seq_treatment_category_code_id`, `clinic_seq_treatment_tag_code_id`, `clinic_seq_treatment_bundle_code_id`, `clinic_seq_treatment_pricelist_code_id`, `clinic_seq_treatment_attribute_code_id`, `clinic_seq_treatment_attribute_value_code_id`
- Methods: `action_open_default_pricelist`, `action_open_sequences`, `_check_disclaimer_length`, `_onchange_bridge_toggle`, `clinic_prepare_service_product_defaults`

### `clinic.treatment.catalog`
- File: `models/treatment.py`
- Python class: `ClinicTreatment`
- Fields: `name`, `code`, `sequence`, `active`, `company_id`, `currency_id`, `category_id`, `tag_ids`, `image_1920`, `description`, `duration_value`, `duration_uom`, `duration_minutes`, `allow_online_booking`, `product_tmpl_id`, `product_id`, `base_price`, `minimum_price`, `pricing_policy`, `surcharge_applicable`, `insurance_applicable`, `valid_from`, `valid_to`, `is_currently_valid`, `pricelist_item_count`, `package_item_count`
- Methods: `_compute_duration_minutes`, `_compute_is_currently_valid`, `_compute_pricelist_item_count`, `_compute_package_item_count`, `_check_prices`, `_check_duration`, `_onchange_product_tmpl_id`, `create`, `write`, `copy`, `_prepare_product_template_vals`, `_audit_event`, `get_service_product`, `get_default_price`, `get_minimum_price`, `_pricelist_fallback`, `action_open_pricelist_items`, `_clinic_display_label`, `_compute_display_name`, `name_get`, `name_search`, `prepare_invoice_line_vals`

### `clinic.treatment.attribute`
- File: `models/treatment_attribute.py`
- Python class: `ClinicTreatmentAttribute`
- Fields: `name`, `code`, `technical_name`, `sequence`, `active`, `company_id`, `value_type`, `selection_mode`, `scope`, `description`, `image_1920`, `value_ids`, `line_ids`, `value_count`, `treatment_count`
- Methods: `_compute_counts`, `_check_selection_mode`, `_check_technical_name_format`, `create`, `write`, `unlink`, `_audit_event`, `action_open_treatments`, `_clinic_display_label`, `_compute_display_name`, `name_get`, `name_search`

### `clinic.treatment.attribute.value`
- File: `models/treatment_attribute.py`
- Python class: `ClinicTreatmentAttributeValue`
- Fields: `name`, `code`, `sequence`, `active`, `color`, `attribute_id`, `company_id`, `delta_price`, `currency_id`, `delta_duration_minutes`, `treatment_count`
- Methods: `_compute_counts`, `create`, `write`, `unlink`, `_audit_event`, `action_open_treatments`, `_clinic_display_label`, `_compute_display_name`, `name_get`, `name_search`

### `ClinicTreatmentAttributeLine`
- File: `models/treatment_attribute.py`
- Python class: `ClinicTreatmentAttributeLine`
- Fields: `treatment_id`, `company_id`, `attribute_id`, `value_id`, `value_text`, `value_number`, `value_boolean`, `value_date`, `value_datetime`, `value_range_min`, `value_range_max`, `display_value`, `attribute_technical`
- Methods: `_compute_display_value`, `_onchange_attribute_id_reset_values`, `_check_company_consistency`, `_check_value_fields`, `as_kv`, `_clinic_display_label`, `_compute_display_name`, `name_get`

### `clinic.treatment.bundle`
- File: `models/treatment_bundle.py`
- Python class: `ClinicTreatmentBundle`
- Fields: `name`, `code`, `sequence`, `active`, `company_id`, `currency_id`, `image_1920`, `description`, `allow_online_sale`, `product_tmpl_id`, `product_id`, `valid_from`, `valid_to`, `is_currently_valid`, `pricing_policy`, `base_price`, `minimum_price`, `computed_sum_price`, `line_ids`, `line_count`, `treatment_count`, `total_sessions`
- Methods: `_compute_is_currently_valid`, `_compute_counters`, `_compute_computed_sum_price`, `_check_prices`, `_check_validity_range`, `_onchange_product_tmpl_id`, `create`, `write`, `copy`, `_prepare_product_template_vals`, `_audit_event`, `get_service_product`, `action_price_preview`, `prepare_sale_line_vals`, `action_open_treatments`, `_clinic_display_label`, `_compute_display_name`, `name_get`, `name_search`

### `ClinicTreatmentBundleLine`
- File: `models/treatment_bundle.py`
- Python class: `ClinicTreatmentBundleLine`
- Fields: `bundle_id`, `company_id`, `line_type`, `treatment_id`, `category_id`, `tag_ids`, `sequence`, `notes`, `quantity`, `per_visit_limit`, `allow_overage`, `overage_unit_price`, `price_policy`, `unit_price`, `currency_id`, `effective_unit_price`, `subtotal`
- Methods: `_check_quantity`, `_check_price_policy`, `_check_line_type_fields`, `_compute_effective_unit_price`, `_compute_subtotal`, `_effective_unit_price`, `_clinic_display_label`, `_compute_display_name`, `name_get`

### `clinic.treatment.category`
- File: `models/treatment_category.py`
- Python class: `ClinicTreatmentCategory`
- Fields: `name`, `complete_name`, `code`, `sequence`, `active`, `color`, `parent_id`, `child_ids`, `parent_path`, `company_id`, `image_1920`, `description`, `treatment_count`, `treatment_count_recursive`, `child_count`
- Methods: `_compute_complete_name`, `_compute_counts`, `_check_parent_company`, `_check_recursion_safe`, `create`, `write`, `unlink`, `_audit_event`, `get_descendant_ids`, `action_open_treatments`, `_clinic_display_label`, `_compute_display_name`, `name_get`, `name_search`

### `clinic.treatment.pricelist`
- File: `models/treatment_pricelist.py`
- Python class: `ClinicTreatmentPricelist`
- Fields: `name`, `code`, `sequence`, `active`, `notes`, `company_id`, `currency_id`, `valid_from`, `valid_to`, `is_currently_valid`, `channel`, `tag_ids`, `apply_membership`, `apply_promotions`, `apply_surcharge`, `apply_insurance`, `tax_included`, `rounding_policy`, `product_pricelist_id`, `item_ids`, `item_count`, `treatment_count`
- Methods: `_compute_is_currently_valid`, `_compute_counts`, `_check_validity`, `create`, `write`, `unlink`, `_audit_event`, `_ensure_product_pricelist`, `_sync_to_product_pricelist`, `action_open_items`, `action_price_preview`, `_clinic_display_label`, `_compute_display_name`, `name_get`, `name_search`

### `inherit:product.pricelist`
- File: `models/treatment_pricelist.py`
- Python class: `ProductPricelist`
- Fields: `clinic_pricelist_id`
- Methods: `_clinic_link`

### `clinic.treatment.pricelist.item`
- File: `models/treatment_pricelist_item.py`
- Python class: `ClinicTreatmentPricelistItem`
- Fields: `name`, `code`, `active`, `sequence`, `pricelist_id`, `company_id`, `currency_id`, `scope`, `treatment_id`, `category_id`, `tag_ids`, `exclude_tag_ids`, `specificity`, `channel`, `min_qty`, `max_qty`, `min_amount`, `partner_category_ids`, `valid_from`, `valid_to`, `time_from`, `time_to`, `weekdays_only`, `weekend_only`, `base`, `method`, `fixed_price`, `percent`, `amount_off`, `surcharge`, `markup_percent`, `rounding_policy`, `enforce_minimum_price`, `treatment_count`
- Methods: `_check_scope_required_fields`, `_check_time_window`, `_compute_specificity`, `_compute_treatment_count`, `create`, `write`, `_audit_event`, `evaluate_rule`, `_match_scope_and_filters`, `_channel_ok`, `_date_ok`, `_time_window_ok`, `_compute_base_price`, `_apply_method_to_base`, `_meta_block`, `to_price_component`

### `ClinicTreatmentPublic`
- File: `models/treatment_public.py`
- Python class: `ClinicTreatmentPublic`
- Fields: `catalog_id`, `company_id`, `active`
- Methods: `create`, `write`, `unlink`, `_check_company_consistency`, `message_post`, `get_service_product`, `get_default_price`, `get_minimum_price`, `prepare_invoice_line_vals`, `action_open_pricelist_items`, `action_open_catalog_record`, `_compute_display_name`, `name_get`, `name_search`

### `clinic.treatment.tag`
- File: `models/treatment_tag.py`
- Python class: `ClinicTreatmentTag`
- Fields: `name`, `code`, `sequence`, `active`, `color`, `emoji`, `company_id`, `scope`, `description`, `image_1920`, `treatment_count`
- Methods: `_check_name_not_empty`, `_compute_treatment_count`, `create`, `write`, `unlink`, `_audit_event`, `action_open_treatments`, `_clinic_display_label`, `_compute_display_name`, `name_get`, `name_search`

## Dormant preserved source

These files existed in the finished baseline but are intentionally not imported by the current `__init__.py` contract:

- `models/__init__.py`
- `models/bridges/__init__.py`
- `models/bridges/bridge_billing.py`
- `models/bridges/bridge_booking.py`
- `models/bridges/bridge_inventory.py`
- `models/bridges/bridge_reports.py`
- `models/engines/__init__.py`
- `models/engines/engine_insurance.py`
- `models/engines/engine_membership.py`
- `models/engines/engine_promotions.py`
- `models/engines/engine_surcharge.py`
- `models/models.py`

## Enterprise UI inventory

- `clinic.treatment.catalog`: form, list, search
- `clinic.treatment.category`: form, list, search
- `clinic.treatment.tag`: form, list, search
- `clinic.treatment.attribute`: form, list, search
- `clinic.treatment.attribute.value`: form, list, search
- `clinic.treatment.attribute.line`: form, list, search
- `clinic.treatment.bundle`: form, list, search
- `clinic.treatment.bundle.line`: form, list, search
- `clinic.treatment.pricelist`: form, list, search
- `clinic.treatment.pricelist.item`: form, list, search
- `clinic.treatment`: form, list, search
- `clinic.consent.template`: form, list, search
- `clinic.consent.template.item`: form, list, search
- `clinic.consent.template.version`: form, list, search
- `clinic.consent.request`: form, list, search
- `clinic.consent.request.item`: form, list, search

### Window actions
- `action_treatment_tree` — `views/treatment_views.xml`
- `action_treatment_public` — `views/treatment_views.xml`
- `action_treatment_category` — `views/treatment_master_views.xml`
- `action_treatment_tag` — `views/treatment_master_views.xml`
- `action_treatment_attribute` — `views/treatment_attribute_views.xml`
- `action_treatment_attribute_value` — `views/treatment_attribute_views.xml`
- `action_treatment_attribute_line` — `views/treatment_attribute_views.xml`
- `action_treatment_bundle` — `views/treatment_bundle_views.xml`
- `action_treatment_bundle_line` — `views/treatment_bundle_views.xml`
- `action_treatment_pricelist` — `views/treatment_pricelist_views.xml`
- `action_treatment_pricelist_item` — `views/treatment_pricelist_views.xml`
- `action_consent_template` — `views/consent_views.xml`
- `action_consent_template_item` — `views/consent_views.xml`
- `action_consent_version` — `views/consent_views.xml`
- `action_consent_request` — `views/consent_views.xml`
- `action_consent_request_item` — `views/consent_views.xml`

### Menus
- `menu_treatment_catalog` — Treatment Catalog
- `menu_treatment_catalog_services` — Services
- `menu_treatments` — Treatments
- `menu_bundles` — Bundles
- `menu_pricing` — Pricing
- `menu_pricelists` — Pricelists
- `menu_price_rules` — Price Rules
- `menu_consent` — Consent
- `menu_consent_requests` — Requests
- `menu_consent_templates` — Templates
- `menu_master_data` — Configuration
- `menu_categories` — Categories
- `menu_tags` — Tags
- `menu_attributes` — Attributes
- `menu_attribute_values` — Attribute Values

## Security inventory

- ACL rows: **16**
- Record rules: **13**
- ORM group: `base.group_user` (no invented clinical role hierarchy).
- Public/portal ACL added: **NO**


