from lxml import etree

from odoo.tests.common import TransactionCase


class TestClinicMarketingEnterprise(TransactionCase):

    def test_001_model_clinic_marketing_preference(self):
        self.assertIn("clinic.marketing.preference", self.env.registry)

    def test_002_clinic_marketing_preference_field_name(self):
        self.assertIn("name", self.env["clinic.marketing.preference"]._fields)

    def test_003_clinic_marketing_preference_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.marketing.preference"]._fields)

    def test_004_clinic_marketing_preference_field_partner_id(self):
        self.assertIn("partner_id", self.env["clinic.marketing.preference"]._fields)

    def test_005_clinic_marketing_preference_field_patient_id(self):
        self.assertIn("patient_id", self.env["clinic.marketing.preference"]._fields)

    def test_006_clinic_marketing_preference_field_branch_id(self):
        self.assertIn("branch_id", self.env["clinic.marketing.preference"]._fields)

    def test_007_clinic_marketing_preference_field_email_consent(self):
        self.assertIn("email_consent", self.env["clinic.marketing.preference"]._fields)

    def test_008_clinic_marketing_preference_field_whatsapp_consent(self):
        self.assertIn("whatsapp_consent", self.env["clinic.marketing.preference"]._fields)

    def test_009_clinic_marketing_preference_field_do_not_contact(self):
        self.assertIn("do_not_contact", self.env["clinic.marketing.preference"]._fields)

    def test_010_clinic_marketing_preference_field_consent_source(self):
        self.assertIn("consent_source", self.env["clinic.marketing.preference"]._fields)

    def test_011_clinic_marketing_preference_field_consent_note(self):
        self.assertIn("consent_note", self.env["clinic.marketing.preference"]._fields)

    def test_012_clinic_marketing_preference_field_consent_updated_at(self):
        self.assertIn("consent_updated_at", self.env["clinic.marketing.preference"]._fields)

    def test_013_clinic_marketing_preference_field_consent_updated_by_id(self):
        self.assertIn("consent_updated_by_id", self.env["clinic.marketing.preference"]._fields)

    def test_014_clinic_marketing_preference_field_active(self):
        self.assertIn("active", self.env["clinic.marketing.preference"]._fields)

    def test_015_clinic_marketing_preference_field_campaign_recipient_ids(self):
        self.assertIn("campaign_recipient_ids", self.env["clinic.marketing.preference"]._fields)

    def test_016_clinic_marketing_preference_field_campaign_count(self):
        self.assertIn("campaign_count", self.env["clinic.marketing.preference"]._fields)

    def test_017_model_clinic_marketing_segment(self):
        self.assertIn("clinic.marketing.segment", self.env.registry)

    def test_018_clinic_marketing_segment_field_name(self):
        self.assertIn("name", self.env["clinic.marketing.segment"]._fields)

    def test_019_clinic_marketing_segment_field_code(self):
        self.assertIn("code", self.env["clinic.marketing.segment"]._fields)

    def test_020_clinic_marketing_segment_field_sequence(self):
        self.assertIn("sequence", self.env["clinic.marketing.segment"]._fields)

    def test_021_clinic_marketing_segment_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.marketing.segment"]._fields)

    def test_022_clinic_marketing_segment_field_branch_id(self):
        self.assertIn("branch_id", self.env["clinic.marketing.segment"]._fields)

    def test_023_clinic_marketing_segment_field_state(self):
        self.assertIn("state", self.env["clinic.marketing.segment"]._fields)

    def test_024_clinic_marketing_segment_field_active(self):
        self.assertIn("active", self.env["clinic.marketing.segment"]._fields)

    def test_025_clinic_marketing_segment_field_description(self):
        self.assertIn("description", self.env["clinic.marketing.segment"]._fields)

    def test_026_clinic_marketing_segment_field_gender(self):
        self.assertIn("gender", self.env["clinic.marketing.segment"]._fields)

    def test_027_clinic_marketing_segment_field_min_age(self):
        self.assertIn("min_age", self.env["clinic.marketing.segment"]._fields)

    def test_028_clinic_marketing_segment_field_max_age(self):
        self.assertIn("max_age", self.env["clinic.marketing.segment"]._fields)

    def test_029_clinic_marketing_segment_field_patient_stage_ids(self):
        self.assertIn("patient_stage_ids", self.env["clinic.marketing.segment"]._fields)

    def test_030_clinic_marketing_segment_field_patient_tag_ids(self):
        self.assertIn("patient_tag_ids", self.env["clinic.marketing.segment"]._fields)

    def test_031_clinic_marketing_segment_field_membership_filter(self):
        self.assertIn("membership_filter", self.env["clinic.marketing.segment"]._fields)

    def test_032_clinic_marketing_segment_field_membership_plan_ids(self):
        self.assertIn("membership_plan_ids", self.env["clinic.marketing.segment"]._fields)

    def test_033_clinic_marketing_segment_field_completed_booking_within_days(self):
        self.assertIn("completed_booking_within_days", self.env["clinic.marketing.segment"]._fields)

    def test_034_clinic_marketing_segment_field_no_completed_booking_for_days(self):
        self.assertIn("no_completed_booking_for_days", self.env["clinic.marketing.segment"]._fields)

    def test_035_clinic_marketing_segment_field_feedback_filter(self):
        self.assertIn("feedback_filter", self.env["clinic.marketing.segment"]._fields)

    def test_036_clinic_marketing_segment_field_required_channel(self):
        self.assertIn("required_channel", self.env["clinic.marketing.segment"]._fields)

    def test_037_clinic_marketing_segment_field_estimated_count(self):
        self.assertIn("estimated_count", self.env["clinic.marketing.segment"]._fields)

    def test_038_clinic_marketing_segment_field_campaign_count(self):
        self.assertIn("campaign_count", self.env["clinic.marketing.segment"]._fields)

    def test_039_model_clinic_marketing_promotion(self):
        self.assertIn("clinic.marketing.promotion", self.env.registry)

    def test_040_clinic_marketing_promotion_field_name(self):
        self.assertIn("name", self.env["clinic.marketing.promotion"]._fields)

    def test_041_clinic_marketing_promotion_field_code(self):
        self.assertIn("code", self.env["clinic.marketing.promotion"]._fields)

    def test_042_clinic_marketing_promotion_field_sequence(self):
        self.assertIn("sequence", self.env["clinic.marketing.promotion"]._fields)

    def test_043_clinic_marketing_promotion_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.marketing.promotion"]._fields)

    def test_044_clinic_marketing_promotion_field_branch_id(self):
        self.assertIn("branch_id", self.env["clinic.marketing.promotion"]._fields)

    def test_045_clinic_marketing_promotion_field_state(self):
        self.assertIn("state", self.env["clinic.marketing.promotion"]._fields)

    def test_046_clinic_marketing_promotion_field_active(self):
        self.assertIn("active", self.env["clinic.marketing.promotion"]._fields)

    def test_047_clinic_marketing_promotion_field_promotion_type(self):
        self.assertIn("promotion_type", self.env["clinic.marketing.promotion"]._fields)

    def test_048_clinic_marketing_promotion_field_billing_voucher_program_id(self):
        self.assertIn("billing_voucher_program_id", self.env["clinic.marketing.promotion"]._fields)

    def test_049_clinic_marketing_promotion_field_package_voucher_batch_id(self):
        self.assertIn("package_voucher_batch_id", self.env["clinic.marketing.promotion"]._fields)

    def test_050_clinic_marketing_promotion_field_treatment_pricelist_item_id(self):
        self.assertIn("treatment_pricelist_item_id", self.env["clinic.marketing.promotion"]._fields)

    def test_051_clinic_marketing_promotion_field_ecommerce_item_id(self):
        self.assertIn("ecommerce_item_id", self.env["clinic.marketing.promotion"]._fields)

    def test_052_clinic_marketing_promotion_field_valid_from(self):
        self.assertIn("valid_from", self.env["clinic.marketing.promotion"]._fields)

    def test_053_clinic_marketing_promotion_field_valid_to(self):
        self.assertIn("valid_to", self.env["clinic.marketing.promotion"]._fields)

    def test_054_clinic_marketing_promotion_field_headline(self):
        self.assertIn("headline", self.env["clinic.marketing.promotion"]._fields)

    def test_055_clinic_marketing_promotion_field_summary(self):
        self.assertIn("summary", self.env["clinic.marketing.promotion"]._fields)

    def test_056_clinic_marketing_promotion_field_terms_html(self):
        self.assertIn("terms_html", self.env["clinic.marketing.promotion"]._fields)

    def test_057_clinic_marketing_promotion_field_cta_label(self):
        self.assertIn("cta_label", self.env["clinic.marketing.promotion"]._fields)

    def test_058_clinic_marketing_promotion_field_landing_url(self):
        self.assertIn("landing_url", self.env["clinic.marketing.promotion"]._fields)

    def test_059_clinic_marketing_promotion_field_image_1920(self):
        self.assertIn("image_1920", self.env["clinic.marketing.promotion"]._fields)

    def test_060_clinic_marketing_promotion_field_source_display_name(self):
        self.assertIn("source_display_name", self.env["clinic.marketing.promotion"]._fields)

    def test_061_clinic_marketing_promotion_field_campaign_ids(self):
        self.assertIn("campaign_ids", self.env["clinic.marketing.promotion"]._fields)

    def test_062_clinic_marketing_promotion_field_campaign_count(self):
        self.assertIn("campaign_count", self.env["clinic.marketing.promotion"]._fields)

    def test_063_model_clinic_marketing_campaign(self):
        self.assertIn("clinic.marketing.campaign", self.env.registry)

    def test_064_clinic_marketing_campaign_field_name(self):
        self.assertIn("name", self.env["clinic.marketing.campaign"]._fields)

    def test_065_clinic_marketing_campaign_field_code(self):
        self.assertIn("code", self.env["clinic.marketing.campaign"]._fields)

    def test_066_clinic_marketing_campaign_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.marketing.campaign"]._fields)

    def test_067_clinic_marketing_campaign_field_branch_id(self):
        self.assertIn("branch_id", self.env["clinic.marketing.campaign"]._fields)

    def test_068_clinic_marketing_campaign_field_owner_id(self):
        self.assertIn("owner_id", self.env["clinic.marketing.campaign"]._fields)

    def test_069_clinic_marketing_campaign_field_segment_id(self):
        self.assertIn("segment_id", self.env["clinic.marketing.campaign"]._fields)

    def test_070_clinic_marketing_campaign_field_promotion_id(self):
        self.assertIn("promotion_id", self.env["clinic.marketing.campaign"]._fields)

    def test_071_clinic_marketing_campaign_field_state(self):
        self.assertIn("state", self.env["clinic.marketing.campaign"]._fields)

    def test_072_clinic_marketing_campaign_field_planned_at(self):
        self.assertIn("planned_at", self.env["clinic.marketing.campaign"]._fields)

    def test_073_clinic_marketing_campaign_field_launched_at(self):
        self.assertIn("launched_at", self.env["clinic.marketing.campaign"]._fields)

    def test_074_clinic_marketing_campaign_field_completed_at(self):
        self.assertIn("completed_at", self.env["clinic.marketing.campaign"]._fields)

    def test_075_clinic_marketing_campaign_field_objective(self):
        self.assertIn("objective", self.env["clinic.marketing.campaign"]._fields)

    def test_076_clinic_marketing_campaign_field_send_email(self):
        self.assertIn("send_email", self.env["clinic.marketing.campaign"]._fields)

    def test_077_clinic_marketing_campaign_field_send_whatsapp(self):
        self.assertIn("send_whatsapp", self.env["clinic.marketing.campaign"]._fields)

    def test_078_clinic_marketing_campaign_field_email_subject(self):
        self.assertIn("email_subject", self.env["clinic.marketing.campaign"]._fields)

    def test_079_clinic_marketing_campaign_field_email_preview(self):
        self.assertIn("email_preview", self.env["clinic.marketing.campaign"]._fields)

    def test_080_clinic_marketing_campaign_field_email_body_html(self):
        self.assertIn("email_body_html", self.env["clinic.marketing.campaign"]._fields)

    def test_081_clinic_marketing_campaign_field_email_from(self):
        self.assertIn("email_from", self.env["clinic.marketing.campaign"]._fields)

    def test_082_clinic_marketing_campaign_field_email_mailing_id(self):
        self.assertIn("email_mailing_id", self.env["clinic.marketing.campaign"]._fields)

    def test_083_clinic_marketing_campaign_field_utm_campaign_id(self):
        self.assertIn("utm_campaign_id", self.env["clinic.marketing.campaign"]._fields)

    def test_084_clinic_marketing_campaign_field_whatsapp_body(self):
        self.assertIn("whatsapp_body", self.env["clinic.marketing.campaign"]._fields)

    def test_085_clinic_marketing_campaign_field_whatsapp_transport(self):
        self.assertIn("whatsapp_transport", self.env["clinic.marketing.campaign"]._fields)

    def test_086_clinic_marketing_campaign_field_recipient_ids(self):
        self.assertIn("recipient_ids", self.env["clinic.marketing.campaign"]._fields)

    def test_087_clinic_marketing_campaign_field_message_ids(self):
        self.assertIn("message_ids", self.env["clinic.marketing.campaign"]._fields)

    def test_088_clinic_marketing_campaign_field_recipient_count(self):
        self.assertIn("recipient_count", self.env["clinic.marketing.campaign"]._fields)

    def test_089_clinic_marketing_campaign_field_included_count(self):
        self.assertIn("included_count", self.env["clinic.marketing.campaign"]._fields)

    def test_090_clinic_marketing_campaign_field_excluded_count(self):
        self.assertIn("excluded_count", self.env["clinic.marketing.campaign"]._fields)

    def test_091_clinic_marketing_campaign_field_email_recipient_count(self):
        self.assertIn("email_recipient_count", self.env["clinic.marketing.campaign"]._fields)

    def test_092_clinic_marketing_campaign_field_whatsapp_recipient_count(self):
        self.assertIn("whatsapp_recipient_count", self.env["clinic.marketing.campaign"]._fields)

    def test_093_clinic_marketing_campaign_field_whatsapp_queued_count(self):
        self.assertIn("whatsapp_queued_count", self.env["clinic.marketing.campaign"]._fields)

    def test_094_clinic_marketing_campaign_field_whatsapp_sent_count(self):
        self.assertIn("whatsapp_sent_count", self.env["clinic.marketing.campaign"]._fields)

    def test_095_clinic_marketing_campaign_field_whatsapp_failed_count(self):
        self.assertIn("whatsapp_failed_count", self.env["clinic.marketing.campaign"]._fields)

    def test_096_clinic_marketing_campaign_field_email_sent_count(self):
        self.assertIn("email_sent_count", self.env["clinic.marketing.campaign"]._fields)

    def test_097_clinic_marketing_campaign_field_email_opened_ratio(self):
        self.assertIn("email_opened_ratio", self.env["clinic.marketing.campaign"]._fields)

    def test_098_clinic_marketing_campaign_field_email_clicked_ratio(self):
        self.assertIn("email_clicked_ratio", self.env["clinic.marketing.campaign"]._fields)

    def test_099_clinic_marketing_campaign_field_email_bounced_ratio(self):
        self.assertIn("email_bounced_ratio", self.env["clinic.marketing.campaign"]._fields)

    def test_100_clinic_marketing_campaign_field_email_replied_ratio(self):
        self.assertIn("email_replied_ratio", self.env["clinic.marketing.campaign"]._fields)

    def test_101_model_clinic_marketing_recipient(self):
        self.assertIn("clinic.marketing.recipient", self.env.registry)

    def test_102_clinic_marketing_recipient_field_campaign_id(self):
        self.assertIn("campaign_id", self.env["clinic.marketing.recipient"]._fields)

    def test_103_clinic_marketing_recipient_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.marketing.recipient"]._fields)

    def test_104_clinic_marketing_recipient_field_branch_id(self):
        self.assertIn("branch_id", self.env["clinic.marketing.recipient"]._fields)

    def test_105_clinic_marketing_recipient_field_segment_id(self):
        self.assertIn("segment_id", self.env["clinic.marketing.recipient"]._fields)

    def test_106_clinic_marketing_recipient_field_promotion_id(self):
        self.assertIn("promotion_id", self.env["clinic.marketing.recipient"]._fields)

    def test_107_clinic_marketing_recipient_field_patient_id(self):
        self.assertIn("patient_id", self.env["clinic.marketing.recipient"]._fields)

    def test_108_clinic_marketing_recipient_field_partner_id(self):
        self.assertIn("partner_id", self.env["clinic.marketing.recipient"]._fields)

    def test_109_clinic_marketing_recipient_field_preference_id(self):
        self.assertIn("preference_id", self.env["clinic.marketing.recipient"]._fields)

    def test_110_clinic_marketing_recipient_field_email(self):
        self.assertIn("email", self.env["clinic.marketing.recipient"]._fields)

    def test_111_clinic_marketing_recipient_field_mobile(self):
        self.assertIn("mobile", self.env["clinic.marketing.recipient"]._fields)

    def test_112_clinic_marketing_recipient_field_record_count(self):
        self.assertIn("record_count", self.env["clinic.marketing.recipient"]._fields)

    def test_113_clinic_marketing_recipient_field_inclusion_state(self):
        self.assertIn("inclusion_state", self.env["clinic.marketing.recipient"]._fields)

    def test_114_clinic_marketing_recipient_field_exclusion_reason(self):
        self.assertIn("exclusion_reason", self.env["clinic.marketing.recipient"]._fields)

    def test_115_clinic_marketing_recipient_field_email_allowed(self):
        self.assertIn("email_allowed", self.env["clinic.marketing.recipient"]._fields)

    def test_116_clinic_marketing_recipient_field_whatsapp_allowed(self):
        self.assertIn("whatsapp_allowed", self.env["clinic.marketing.recipient"]._fields)

    def test_117_clinic_marketing_recipient_field_email_delivery_state(self):
        self.assertIn("email_delivery_state", self.env["clinic.marketing.recipient"]._fields)

    def test_118_clinic_marketing_recipient_field_email_failure_reason(self):
        self.assertIn("email_failure_reason", self.env["clinic.marketing.recipient"]._fields)

    def test_119_clinic_marketing_recipient_field_whatsapp_message_ids(self):
        self.assertIn("whatsapp_message_ids", self.env["clinic.marketing.recipient"]._fields)

    def test_120_clinic_marketing_recipient_field_whatsapp_state(self):
        self.assertIn("whatsapp_state", self.env["clinic.marketing.recipient"]._fields)

    def test_121_model_clinic_marketing_message(self):
        self.assertIn("clinic.marketing.message", self.env.registry)

    def test_122_clinic_marketing_message_field_campaign_id(self):
        self.assertIn("campaign_id", self.env["clinic.marketing.message"]._fields)

    def test_123_clinic_marketing_message_field_recipient_id(self):
        self.assertIn("recipient_id", self.env["clinic.marketing.message"]._fields)

    def test_124_clinic_marketing_message_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.marketing.message"]._fields)

    def test_125_clinic_marketing_message_field_patient_id(self):
        self.assertIn("patient_id", self.env["clinic.marketing.message"]._fields)

    def test_126_clinic_marketing_message_field_partner_id(self):
        self.assertIn("partner_id", self.env["clinic.marketing.message"]._fields)

    def test_127_clinic_marketing_message_field_destination(self):
        self.assertIn("destination", self.env["clinic.marketing.message"]._fields)

    def test_128_clinic_marketing_message_field_body(self):
        self.assertIn("body", self.env["clinic.marketing.message"]._fields)

    def test_129_clinic_marketing_message_field_scheduled_at(self):
        self.assertIn("scheduled_at", self.env["clinic.marketing.message"]._fields)

    def test_130_clinic_marketing_message_field_state(self):
        self.assertIn("state", self.env["clinic.marketing.message"]._fields)

    def test_131_clinic_marketing_message_field_opened_at(self):
        self.assertIn("opened_at", self.env["clinic.marketing.message"]._fields)

    def test_132_clinic_marketing_message_field_sent_at(self):
        self.assertIn("sent_at", self.env["clinic.marketing.message"]._fields)

    def test_133_clinic_marketing_message_field_failure_reason(self):
        self.assertIn("failure_reason", self.env["clinic.marketing.message"]._fields)

    def test_134_clinic_marketing_message_field_provider_reference(self):
        self.assertIn("provider_reference", self.env["clinic.marketing.message"]._fields)

    def test_135_clinic_marketing_message_field_whatsapp_url(self):
        self.assertIn("whatsapp_url", self.env["clinic.marketing.message"]._fields)

    def test_136_clinic_marketing_preference_method_compute_name(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.preference"], "_compute_name"))

    def test_137_clinic_marketing_preference_method_compute_campaign_count(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.preference"], "_compute_campaign_count"))

    def test_138_clinic_marketing_preference_method_check_patient_scope(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.preference"], "_check_patient_scope"))

    def test_139_clinic_marketing_preference_method_set_channel_consent(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.preference"], "_set_channel_consent"))

    def test_140_clinic_marketing_preference_method_action_opt_in_email(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.preference"], "action_opt_in_email"))

    def test_141_clinic_marketing_preference_method_action_opt_out_email(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.preference"], "action_opt_out_email"))

    def test_142_clinic_marketing_preference_method_action_opt_in_whatsapp(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.preference"], "action_opt_in_whatsapp"))

    def test_143_clinic_marketing_preference_method_action_opt_out_whatsapp(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.preference"], "action_opt_out_whatsapp"))

    def test_144_clinic_marketing_preference_method_action_do_not_contact(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.preference"], "action_do_not_contact"))

    def test_145_clinic_marketing_preference_method_action_allow_contact(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.preference"], "action_allow_contact"))

    def test_146_clinic_marketing_preference_method_action_open_patient(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.preference"], "action_open_patient"))

    def test_147_clinic_marketing_preference_method_action_open_campaigns(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.preference"], "action_open_campaigns"))

    def test_148_clinic_marketing_preference_method_channel_allowed(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.preference"], "_channel_allowed"))

    def test_149_clinic_marketing_preference_method_find_for_partner(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.preference"], "_find_for_partner"))

    def test_150_clinic_marketing_segment_method_check_segment_rules(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.segment"], "_check_segment_rules"))

    def test_151_clinic_marketing_segment_method_compute_estimated_count(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.segment"], "_compute_estimated_count"))

    def test_152_clinic_marketing_segment_method_compute_campaign_count(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.segment"], "_compute_campaign_count"))

    def test_153_clinic_marketing_segment_method_base_patient_domain(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.segment"], "_base_patient_domain"))

    def test_154_clinic_marketing_segment_method_filter_membership(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.segment"], "_filter_membership"))

    def test_155_clinic_marketing_segment_method_filter_booking_recency(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.segment"], "_filter_booking_recency"))

    def test_156_clinic_marketing_segment_method_filter_feedback(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.segment"], "_filter_feedback"))

    def test_157_clinic_marketing_segment_method_filter_channel_availability(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.segment"], "_filter_channel_availability"))

    def test_158_clinic_marketing_segment_method_candidate_patients(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.segment"], "_candidate_patients"))

    def test_159_clinic_marketing_segment_method_action_activate(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.segment"], "action_activate"))

    def test_160_clinic_marketing_segment_method_action_archive(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.segment"], "action_archive"))

    def test_161_clinic_marketing_segment_method_action_reset_to_draft(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.segment"], "action_reset_to_draft"))

    def test_162_clinic_marketing_segment_method_action_preview_patients(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.segment"], "action_preview_patients"))

    def test_163_clinic_marketing_segment_method_action_open_campaigns(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.segment"], "action_open_campaigns"))

    def test_164_clinic_marketing_promotion_method_compute_source_display_name(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.promotion"], "_compute_source_display_name"))

    def test_165_clinic_marketing_promotion_method_compute_campaign_count(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.promotion"], "_compute_campaign_count"))

    def test_166_clinic_marketing_promotion_method_check_source_contract(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.promotion"], "_check_source_contract"))

    def test_167_clinic_marketing_promotion_method_source_record(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.promotion"], "_source_record"))

    def test_168_clinic_marketing_promotion_method_effective_landing_url(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.promotion"], "_effective_landing_url"))

    def test_169_clinic_marketing_promotion_method_action_activate(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.promotion"], "action_activate"))

    def test_170_clinic_marketing_promotion_method_action_expire(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.promotion"], "action_expire"))

    def test_171_clinic_marketing_promotion_method_action_archive(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.promotion"], "action_archive"))

    def test_172_clinic_marketing_promotion_method_action_reset_to_draft(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.promotion"], "action_reset_to_draft"))

    def test_173_clinic_marketing_promotion_method_action_open_source(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.promotion"], "action_open_source"))

    def test_174_clinic_marketing_promotion_method_action_open_campaigns(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.promotion"], "action_open_campaigns"))

    def test_175_clinic_marketing_promotion_method_cron_expire_promotions(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.promotion"], "_cron_expire_promotions"))

    def test_176_clinic_marketing_campaign_method_compute_recipient_counts(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "_compute_recipient_counts"))

    def test_177_clinic_marketing_campaign_method_compute_message_counts(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "_compute_message_counts"))

    def test_178_clinic_marketing_campaign_method_check_campaign_scope(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "_check_campaign_scope"))

    def test_179_clinic_marketing_campaign_method_require_coordinator(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "_require_coordinator"))

    def test_180_clinic_marketing_campaign_method_require_manager(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "_require_manager"))

    def test_181_clinic_marketing_campaign_method_check_branch_policy(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "_check_branch_policy"))

    def test_182_clinic_marketing_campaign_method_candidate_patients(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "_candidate_patients"))

    def test_183_clinic_marketing_campaign_method_recipient_snapshot_vals(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "_recipient_snapshot_vals"))

    def test_184_clinic_marketing_campaign_method_action_prepare_audience(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "action_prepare_audience"))

    def test_185_clinic_marketing_campaign_method_validate_ready(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "_validate_ready"))

    def test_186_clinic_marketing_campaign_method_action_mark_ready(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "action_mark_ready"))

    def test_187_clinic_marketing_campaign_method_ensure_utm_campaign(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "_ensure_utm_campaign"))

    def test_188_clinic_marketing_campaign_method_ensure_email_mailing(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "_ensure_email_mailing"))

    def test_189_clinic_marketing_campaign_method_build_whatsapp_messages(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "_build_whatsapp_messages"))

    def test_190_clinic_marketing_campaign_method_action_launch(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "action_launch"))

    def test_191_clinic_marketing_campaign_method_action_sync_delivery(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "action_sync_delivery"))

    def test_192_clinic_marketing_campaign_method_delivery_complete(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "_delivery_complete"))

    def test_193_clinic_marketing_campaign_method_action_complete(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "action_complete"))

    def test_194_clinic_marketing_campaign_method_action_cancel(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "action_cancel"))

    def test_195_clinic_marketing_campaign_method_action_reset_to_draft(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "action_reset_to_draft"))

    def test_196_clinic_marketing_campaign_method_action_open_recipients(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "action_open_recipients"))

    def test_197_clinic_marketing_campaign_method_action_open_whatsapp_messages(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "action_open_whatsapp_messages"))

    def test_198_clinic_marketing_campaign_method_action_open_email_mailing(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "action_open_email_mailing"))

    def test_199_clinic_marketing_campaign_method_action_open_segment(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "action_open_segment"))

    def test_200_clinic_marketing_campaign_method_action_open_promotion(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "action_open_promotion"))

    def test_201_clinic_marketing_campaign_method_cron_sync_running_campaigns(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.campaign"], "_cron_sync_running_campaigns"))

    def test_202_clinic_marketing_recipient_method_compute_whatsapp_state(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.recipient"], "_compute_whatsapp_state"))

    def test_203_clinic_marketing_recipient_method_check_patient_scope(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.recipient"], "_check_patient_scope"))

    def test_204_clinic_marketing_recipient_method_action_open_patient(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.recipient"], "action_open_patient"))

    def test_205_clinic_marketing_recipient_method_action_open_preference(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.recipient"], "action_open_preference"))

    def test_206_clinic_marketing_recipient_method_action_open_campaign(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.recipient"], "action_open_campaign"))

    def test_207_clinic_marketing_recipient_method_action_open_whatsapp_messages(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.recipient"], "action_open_whatsapp_messages"))

    def test_208_clinic_marketing_message_method_compute_whatsapp_url(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.message"], "_compute_whatsapp_url"))

    def test_209_clinic_marketing_message_method_normalize_destination(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.message"], "_normalize_destination"))

    def test_210_clinic_marketing_message_method_check_scope(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.message"], "_check_scope"))

    def test_211_clinic_marketing_message_method_dispatch_via_gateway(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.message"], "_dispatch_via_gateway"))

    def test_212_clinic_marketing_message_method_action_open_whatsapp(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.message"], "action_open_whatsapp"))

    def test_213_clinic_marketing_message_method_action_dispatch_gateway(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.message"], "action_dispatch_gateway"))

    def test_214_clinic_marketing_message_method_action_mark_sent(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.message"], "action_mark_sent"))

    def test_215_clinic_marketing_message_method_action_mark_failed(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.message"], "action_mark_failed"))

    def test_216_clinic_marketing_message_method_action_cancel(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.message"], "action_cancel"))

    def test_217_clinic_marketing_message_method_cron_dispatch_due(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.message"], "_cron_dispatch_due"))

    def test_218_clinic_marketing_message_method_action_open_patient(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.message"], "action_open_patient"))

    def test_219_table_clinic_marketing_preference(self):
        self.assertEqual(self.env["clinic.marketing.preference"]._table, "clinic_marketing_preference")

    def test_220_table_clinic_marketing_segment(self):
        self.assertEqual(self.env["clinic.marketing.segment"]._table, "clinic_marketing_segment")

    def test_221_table_clinic_marketing_promotion(self):
        self.assertEqual(self.env["clinic.marketing.promotion"]._table, "clinic_marketing_promotion")

    def test_222_table_clinic_marketing_campaign(self):
        self.assertEqual(self.env["clinic.marketing.campaign"]._table, "clinic_marketing_campaign")

    def test_223_table_clinic_marketing_recipient(self):
        self.assertEqual(self.env["clinic.marketing.recipient"]._table, "clinic_marketing_recipient")

    def test_224_table_clinic_marketing_message(self):
        self.assertEqual(self.env["clinic.marketing.message"]._table, "clinic_marketing_message")

    def test_225_selection_clinic_marketing_preference_email_consent_unknown(self):
        selection = dict(self.env["clinic.marketing.preference"]._fields["email_consent"].selection)
        self.assertIn("unknown", selection)

    def test_226_selection_clinic_marketing_preference_email_consent_opt_in(self):
        selection = dict(self.env["clinic.marketing.preference"]._fields["email_consent"].selection)
        self.assertIn("opt_in", selection)

    def test_227_selection_clinic_marketing_preference_email_consent_opt_out(self):
        selection = dict(self.env["clinic.marketing.preference"]._fields["email_consent"].selection)
        self.assertIn("opt_out", selection)

    def test_228_selection_clinic_marketing_preference_whatsapp_consent_unknown(self):
        selection = dict(self.env["clinic.marketing.preference"]._fields["whatsapp_consent"].selection)
        self.assertIn("unknown", selection)

    def test_229_selection_clinic_marketing_preference_whatsapp_consent_opt_in(self):
        selection = dict(self.env["clinic.marketing.preference"]._fields["whatsapp_consent"].selection)
        self.assertIn("opt_in", selection)

    def test_230_selection_clinic_marketing_preference_whatsapp_consent_opt_out(self):
        selection = dict(self.env["clinic.marketing.preference"]._fields["whatsapp_consent"].selection)
        self.assertIn("opt_out", selection)

    def test_231_selection_clinic_marketing_segment_state_draft(self):
        selection = dict(self.env["clinic.marketing.segment"]._fields["state"].selection)
        self.assertIn("draft", selection)

    def test_232_selection_clinic_marketing_segment_state_active(self):
        selection = dict(self.env["clinic.marketing.segment"]._fields["state"].selection)
        self.assertIn("active", selection)

    def test_233_selection_clinic_marketing_segment_state_archived(self):
        selection = dict(self.env["clinic.marketing.segment"]._fields["state"].selection)
        self.assertIn("archived", selection)

    def test_234_selection_clinic_marketing_segment_membership_filter_any(self):
        selection = dict(self.env["clinic.marketing.segment"]._fields["membership_filter"].selection)
        self.assertIn("any", selection)

    def test_235_selection_clinic_marketing_segment_membership_filter_active(self):
        selection = dict(self.env["clinic.marketing.segment"]._fields["membership_filter"].selection)
        self.assertIn("active", selection)

    def test_236_selection_clinic_marketing_segment_membership_filter_inactive(self):
        selection = dict(self.env["clinic.marketing.segment"]._fields["membership_filter"].selection)
        self.assertIn("inactive", selection)

    def test_237_selection_clinic_marketing_segment_feedback_filter_any(self):
        selection = dict(self.env["clinic.marketing.segment"]._fields["feedback_filter"].selection)
        self.assertIn("any", selection)

    def test_238_selection_clinic_marketing_segment_feedback_filter_promoter(self):
        selection = dict(self.env["clinic.marketing.segment"]._fields["feedback_filter"].selection)
        self.assertIn("promoter", selection)

    def test_239_selection_clinic_marketing_segment_feedback_filter_detractor(self):
        selection = dict(self.env["clinic.marketing.segment"]._fields["feedback_filter"].selection)
        self.assertIn("detractor", selection)

    def test_240_selection_clinic_marketing_segment_required_channel_any(self):
        selection = dict(self.env["clinic.marketing.segment"]._fields["required_channel"].selection)
        self.assertIn("any", selection)

    def test_241_selection_clinic_marketing_segment_required_channel_email(self):
        selection = dict(self.env["clinic.marketing.segment"]._fields["required_channel"].selection)
        self.assertIn("email", selection)

    def test_242_selection_clinic_marketing_segment_required_channel_whatsapp(self):
        selection = dict(self.env["clinic.marketing.segment"]._fields["required_channel"].selection)
        self.assertIn("whatsapp", selection)

    def test_243_selection_clinic_marketing_segment_required_channel_both(self):
        selection = dict(self.env["clinic.marketing.segment"]._fields["required_channel"].selection)
        self.assertIn("both", selection)

    def test_244_selection_clinic_marketing_promotion_state_draft(self):
        selection = dict(self.env["clinic.marketing.promotion"]._fields["state"].selection)
        self.assertIn("draft", selection)

    def test_245_selection_clinic_marketing_promotion_state_active(self):
        selection = dict(self.env["clinic.marketing.promotion"]._fields["state"].selection)
        self.assertIn("active", selection)

    def test_246_selection_clinic_marketing_promotion_state_expired(self):
        selection = dict(self.env["clinic.marketing.promotion"]._fields["state"].selection)
        self.assertIn("expired", selection)

    def test_247_selection_clinic_marketing_promotion_state_archived(self):
        selection = dict(self.env["clinic.marketing.promotion"]._fields["state"].selection)
        self.assertIn("archived", selection)

    def test_248_selection_clinic_marketing_promotion_promotion_type_information(self):
        selection = dict(self.env["clinic.marketing.promotion"]._fields["promotion_type"].selection)
        self.assertIn("information", selection)

    def test_249_selection_clinic_marketing_promotion_promotion_type_billing_voucher(self):
        selection = dict(self.env["clinic.marketing.promotion"]._fields["promotion_type"].selection)
        self.assertIn("billing_voucher", selection)

    def test_250_selection_clinic_marketing_promotion_promotion_type_package_voucher(self):
        selection = dict(self.env["clinic.marketing.promotion"]._fields["promotion_type"].selection)
        self.assertIn("package_voucher", selection)

    def test_251_selection_clinic_marketing_promotion_promotion_type_treatment_price(self):
        selection = dict(self.env["clinic.marketing.promotion"]._fields["promotion_type"].selection)
        self.assertIn("treatment_price", selection)

    def test_252_selection_clinic_marketing_promotion_promotion_type_ecommerce(self):
        selection = dict(self.env["clinic.marketing.promotion"]._fields["promotion_type"].selection)
        self.assertIn("ecommerce", selection)

    def test_253_selection_clinic_marketing_campaign_state_draft(self):
        selection = dict(self.env["clinic.marketing.campaign"]._fields["state"].selection)
        self.assertIn("draft", selection)

    def test_254_selection_clinic_marketing_campaign_state_planning(self):
        selection = dict(self.env["clinic.marketing.campaign"]._fields["state"].selection)
        self.assertIn("planning", selection)

    def test_255_selection_clinic_marketing_campaign_state_ready(self):
        selection = dict(self.env["clinic.marketing.campaign"]._fields["state"].selection)
        self.assertIn("ready", selection)

    def test_256_selection_clinic_marketing_campaign_state_running(self):
        selection = dict(self.env["clinic.marketing.campaign"]._fields["state"].selection)
        self.assertIn("running", selection)

    def test_257_selection_clinic_marketing_campaign_state_completed(self):
        selection = dict(self.env["clinic.marketing.campaign"]._fields["state"].selection)
        self.assertIn("completed", selection)

    def test_258_selection_clinic_marketing_campaign_state_cancelled(self):
        selection = dict(self.env["clinic.marketing.campaign"]._fields["state"].selection)
        self.assertIn("cancelled", selection)

    def test_259_selection_clinic_marketing_recipient_inclusion_state_included(self):
        selection = dict(self.env["clinic.marketing.recipient"]._fields["inclusion_state"].selection)
        self.assertIn("included", selection)

    def test_260_selection_clinic_marketing_recipient_inclusion_state_excluded(self):
        selection = dict(self.env["clinic.marketing.recipient"]._fields["inclusion_state"].selection)
        self.assertIn("excluded", selection)

    def test_261_selection_clinic_marketing_recipient_email_delivery_state_not_applicable(self):
        selection = dict(self.env["clinic.marketing.recipient"]._fields["email_delivery_state"].selection)
        self.assertIn("not_applicable", selection)

    def test_262_selection_clinic_marketing_recipient_email_delivery_state_pending(self):
        selection = dict(self.env["clinic.marketing.recipient"]._fields["email_delivery_state"].selection)
        self.assertIn("pending", selection)

    def test_263_selection_clinic_marketing_recipient_email_delivery_state_outgoing(self):
        selection = dict(self.env["clinic.marketing.recipient"]._fields["email_delivery_state"].selection)
        self.assertIn("outgoing", selection)

    def test_264_selection_clinic_marketing_recipient_email_delivery_state_processing(self):
        selection = dict(self.env["clinic.marketing.recipient"]._fields["email_delivery_state"].selection)
        self.assertIn("processing", selection)

    def test_265_selection_clinic_marketing_recipient_email_delivery_state_sent(self):
        selection = dict(self.env["clinic.marketing.recipient"]._fields["email_delivery_state"].selection)
        self.assertIn("sent", selection)

    def test_266_selection_clinic_marketing_recipient_email_delivery_state_opened(self):
        selection = dict(self.env["clinic.marketing.recipient"]._fields["email_delivery_state"].selection)
        self.assertIn("opened", selection)

    def test_267_selection_clinic_marketing_recipient_email_delivery_state_replied(self):
        selection = dict(self.env["clinic.marketing.recipient"]._fields["email_delivery_state"].selection)
        self.assertIn("replied", selection)

    def test_268_selection_clinic_marketing_recipient_email_delivery_state_bounced(self):
        selection = dict(self.env["clinic.marketing.recipient"]._fields["email_delivery_state"].selection)
        self.assertIn("bounced", selection)

    def test_269_selection_clinic_marketing_recipient_email_delivery_state_failed(self):
        selection = dict(self.env["clinic.marketing.recipient"]._fields["email_delivery_state"].selection)
        self.assertIn("failed", selection)

    def test_270_selection_clinic_marketing_recipient_email_delivery_state_cancelled(self):
        selection = dict(self.env["clinic.marketing.recipient"]._fields["email_delivery_state"].selection)
        self.assertIn("cancelled", selection)

    def test_271_selection_clinic_marketing_recipient_whatsapp_state_not_applicable(self):
        selection = dict(self.env["clinic.marketing.recipient"]._fields["whatsapp_state"].selection)
        self.assertIn("not_applicable", selection)

    def test_272_selection_clinic_marketing_recipient_whatsapp_state_queued(self):
        selection = dict(self.env["clinic.marketing.recipient"]._fields["whatsapp_state"].selection)
        self.assertIn("queued", selection)

    def test_273_selection_clinic_marketing_recipient_whatsapp_state_opened(self):
        selection = dict(self.env["clinic.marketing.recipient"]._fields["whatsapp_state"].selection)
        self.assertIn("opened", selection)

    def test_274_selection_clinic_marketing_recipient_whatsapp_state_sent(self):
        selection = dict(self.env["clinic.marketing.recipient"]._fields["whatsapp_state"].selection)
        self.assertIn("sent", selection)

    def test_275_selection_clinic_marketing_recipient_whatsapp_state_failed(self):
        selection = dict(self.env["clinic.marketing.recipient"]._fields["whatsapp_state"].selection)
        self.assertIn("failed", selection)

    def test_276_selection_clinic_marketing_recipient_whatsapp_state_cancelled(self):
        selection = dict(self.env["clinic.marketing.recipient"]._fields["whatsapp_state"].selection)
        self.assertIn("cancelled", selection)

    def test_277_selection_clinic_marketing_message_state_queued(self):
        selection = dict(self.env["clinic.marketing.message"]._fields["state"].selection)
        self.assertIn("queued", selection)

    def test_278_selection_clinic_marketing_message_state_opened(self):
        selection = dict(self.env["clinic.marketing.message"]._fields["state"].selection)
        self.assertIn("opened", selection)

    def test_279_selection_clinic_marketing_message_state_sent(self):
        selection = dict(self.env["clinic.marketing.message"]._fields["state"].selection)
        self.assertIn("sent", selection)

    def test_280_selection_clinic_marketing_message_state_failed(self):
        selection = dict(self.env["clinic.marketing.message"]._fields["state"].selection)
        self.assertIn("failed", selection)

    def test_281_selection_clinic_marketing_message_state_cancelled(self):
        selection = dict(self.env["clinic.marketing.message"]._fields["state"].selection)
        self.assertIn("cancelled", selection)

    def test_282_comodel_clinic_marketing_preference_partner_id(self):
        self.assertEqual(self.env["clinic.marketing.preference"]._fields["partner_id"].comodel_name, "res.partner")

    def test_283_comodel_clinic_marketing_preference_patient_id(self):
        self.assertEqual(self.env["clinic.marketing.preference"]._fields["patient_id"].comodel_name, "clinic.patient")

    def test_284_comodel_clinic_marketing_segment_branch_id(self):
        self.assertEqual(self.env["clinic.marketing.segment"]._fields["branch_id"].comodel_name, "clinic.branch")

    def test_285_comodel_clinic_marketing_segment_membership_plan_ids(self):
        self.assertEqual(self.env["clinic.marketing.segment"]._fields["membership_plan_ids"].comodel_name, "membership.plan")

    def test_286_comodel_clinic_marketing_promotion_billing_voucher_program_id(self):
        self.assertEqual(self.env["clinic.marketing.promotion"]._fields["billing_voucher_program_id"].comodel_name, "clinic.billing.voucher.program")

    def test_287_comodel_clinic_marketing_promotion_package_voucher_batch_id(self):
        self.assertEqual(self.env["clinic.marketing.promotion"]._fields["package_voucher_batch_id"].comodel_name, "clinic.package.voucher.batch")

    def test_288_comodel_clinic_marketing_promotion_treatment_pricelist_item_id(self):
        self.assertEqual(self.env["clinic.marketing.promotion"]._fields["treatment_pricelist_item_id"].comodel_name, "clinic.treatment.pricelist.item")

    def test_289_comodel_clinic_marketing_promotion_ecommerce_item_id(self):
        self.assertEqual(self.env["clinic.marketing.promotion"]._fields["ecommerce_item_id"].comodel_name, "clinic.ecommerce.catalog.item")

    def test_290_comodel_clinic_marketing_campaign_segment_id(self):
        self.assertEqual(self.env["clinic.marketing.campaign"]._fields["segment_id"].comodel_name, "clinic.marketing.segment")

    def test_291_comodel_clinic_marketing_campaign_promotion_id(self):
        self.assertEqual(self.env["clinic.marketing.campaign"]._fields["promotion_id"].comodel_name, "clinic.marketing.promotion")

    def test_292_comodel_clinic_marketing_campaign_email_mailing_id(self):
        self.assertEqual(self.env["clinic.marketing.campaign"]._fields["email_mailing_id"].comodel_name, "mailing.mailing")

    def test_293_comodel_clinic_marketing_campaign_utm_campaign_id(self):
        self.assertEqual(self.env["clinic.marketing.campaign"]._fields["utm_campaign_id"].comodel_name, "utm.campaign")

    def test_294_comodel_clinic_marketing_recipient_patient_id(self):
        self.assertEqual(self.env["clinic.marketing.recipient"]._fields["patient_id"].comodel_name, "clinic.patient")

    def test_295_comodel_clinic_marketing_recipient_partner_id(self):
        self.assertEqual(self.env["clinic.marketing.recipient"]._fields["partner_id"].comodel_name, "res.partner")

    def test_296_comodel_clinic_marketing_message_recipient_id(self):
        self.assertEqual(self.env["clinic.marketing.message"]._fields["recipient_id"].comodel_name, "clinic.marketing.recipient")

    def test_297_upstream_model_res_company(self):
        self.assertIn("res.company", self.env.registry)

    def test_298_upstream_res_company_field_policy_branch_scope_marketing(self):
        self.assertIn("policy_branch_scope_marketing", self.env["res.company"]._fields)

    def test_299_upstream_res_company_field_clinic_marketing_require_explicit_consent(self):
        self.assertIn("clinic_marketing_require_explicit_consent", self.env["res.company"]._fields)

    def test_300_upstream_res_company_field_clinic_marketing_max_audience(self):
        self.assertIn("clinic_marketing_max_audience", self.env["res.company"]._fields)

    def test_301_upstream_res_company_field_clinic_marketing_whatsapp_transport(self):
        self.assertIn("clinic_marketing_whatsapp_transport", self.env["res.company"]._fields)

    def test_302_upstream_model_res_partner(self):
        self.assertIn("res.partner", self.env.registry)

    def test_303_upstream_res_partner_field_is_patient(self):
        self.assertIn("is_patient", self.env["res.partner"]._fields)

    def test_304_upstream_res_partner_field_patient_id(self):
        self.assertIn("patient_id", self.env["res.partner"]._fields)

    def test_305_upstream_res_partner_field_branch_id(self):
        self.assertIn("branch_id", self.env["res.partner"]._fields)

    def test_306_upstream_res_partner_field_clinic_marketing_preference_ids(self):
        self.assertIn("clinic_marketing_preference_ids", self.env["res.partner"]._fields)

    def test_307_upstream_res_partner_field_clinic_marketing_recipient_ids(self):
        self.assertIn("clinic_marketing_recipient_ids", self.env["res.partner"]._fields)

    def test_308_upstream_res_partner_field_clinic_marketing_preference_count(self):
        self.assertIn("clinic_marketing_preference_count", self.env["res.partner"]._fields)

    def test_309_upstream_res_partner_field_clinic_marketing_campaign_count(self):
        self.assertIn("clinic_marketing_campaign_count", self.env["res.partner"]._fields)

    def test_310_upstream_model_clinic_patient(self):
        self.assertIn("clinic.patient", self.env.registry)

    def test_311_upstream_clinic_patient_field_partner_id(self):
        self.assertIn("partner_id", self.env["clinic.patient"]._fields)

    def test_312_upstream_clinic_patient_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.patient"]._fields)

    def test_313_upstream_clinic_patient_field_stage_id(self):
        self.assertIn("stage_id", self.env["clinic.patient"]._fields)

    def test_314_upstream_clinic_patient_field_tag_ids(self):
        self.assertIn("tag_ids", self.env["clinic.patient"]._fields)

    def test_315_upstream_clinic_patient_field_gender(self):
        self.assertIn("gender", self.env["clinic.patient"]._fields)

    def test_316_upstream_clinic_patient_field_age_years(self):
        self.assertIn("age_years", self.env["clinic.patient"]._fields)

    def test_317_upstream_clinic_patient_field_email(self):
        self.assertIn("email", self.env["clinic.patient"]._fields)

    def test_318_upstream_clinic_patient_field_mobile(self):
        self.assertIn("mobile", self.env["clinic.patient"]._fields)

    def test_319_upstream_clinic_patient_field_phone(self):
        self.assertIn("phone", self.env["clinic.patient"]._fields)

    def test_320_upstream_clinic_patient_field_active(self):
        self.assertIn("active", self.env["clinic.patient"]._fields)

    def test_321_upstream_clinic_patient_field_clinic_marketing_campaign_count(self):
        self.assertIn("clinic_marketing_campaign_count", self.env["clinic.patient"]._fields)

    def test_322_upstream_model_booking_booking(self):
        self.assertIn("booking.booking", self.env.registry)

    def test_323_upstream_booking_booking_field_company_id(self):
        self.assertIn("company_id", self.env["booking.booking"]._fields)

    def test_324_upstream_booking_booking_field_patient_id(self):
        self.assertIn("patient_id", self.env["booking.booking"]._fields)

    def test_325_upstream_booking_booking_field_start_datetime(self):
        self.assertIn("start_datetime", self.env["booking.booking"]._fields)

    def test_326_upstream_booking_booking_field_state(self):
        self.assertIn("state", self.env["booking.booking"]._fields)

    def test_327_upstream_model_membership_contract(self):
        self.assertIn("membership.contract", self.env.registry)

    def test_328_upstream_membership_contract_field_company_id(self):
        self.assertIn("company_id", self.env["membership.contract"]._fields)

    def test_329_upstream_membership_contract_field_patient_id(self):
        self.assertIn("patient_id", self.env["membership.contract"]._fields)

    def test_330_upstream_membership_contract_field_plan_id(self):
        self.assertIn("plan_id", self.env["membership.contract"]._fields)

    def test_331_upstream_membership_contract_field_state(self):
        self.assertIn("state", self.env["membership.contract"]._fields)

    def test_332_upstream_model_clinic_feedback(self):
        self.assertIn("clinic.feedback", self.env.registry)

    def test_333_upstream_clinic_feedback_field_patient_id(self):
        self.assertIn("patient_id", self.env["clinic.feedback"]._fields)

    def test_334_upstream_clinic_feedback_field_submitted_at(self):
        self.assertIn("submitted_at", self.env["clinic.feedback"]._fields)

    def test_335_upstream_clinic_feedback_field_nps_class(self):
        self.assertIn("nps_class", self.env["clinic.feedback"]._fields)

    def test_336_upstream_clinic_feedback_field_state(self):
        self.assertIn("state", self.env["clinic.feedback"]._fields)

    def test_337_upstream_model_clinic_billing_voucher_program(self):
        self.assertIn("clinic.billing.voucher.program", self.env.registry)

    def test_338_upstream_clinic_billing_voucher_program_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.billing.voucher.program"]._fields)

    def test_339_upstream_model_clinic_package_voucher_batch(self):
        self.assertIn("clinic.package.voucher.batch", self.env.registry)

    def test_340_upstream_clinic_package_voucher_batch_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.package.voucher.batch"]._fields)

    def test_341_upstream_clinic_package_voucher_batch_field_branch_id(self):
        self.assertIn("branch_id", self.env["clinic.package.voucher.batch"]._fields)

    def test_342_upstream_clinic_package_voucher_batch_field_state(self):
        self.assertIn("state", self.env["clinic.package.voucher.batch"]._fields)

    def test_343_upstream_model_clinic_treatment_pricelist_item(self):
        self.assertIn("clinic.treatment.pricelist.item", self.env.registry)

    def test_344_upstream_clinic_treatment_pricelist_item_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.treatment.pricelist.item"]._fields)

    def test_345_upstream_model_clinic_ecommerce_catalog_item(self):
        self.assertIn("clinic.ecommerce.catalog.item", self.env.registry)

    def test_346_upstream_clinic_ecommerce_catalog_item_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.ecommerce.catalog.item"]._fields)

    def test_347_upstream_clinic_ecommerce_catalog_item_field_state(self):
        self.assertIn("state", self.env["clinic.ecommerce.catalog.item"]._fields)

    def test_348_upstream_clinic_ecommerce_catalog_item_field_website_url(self):
        self.assertIn("website_url", self.env["clinic.ecommerce.catalog.item"]._fields)

    def test_349_upstream_clinic_ecommerce_catalog_item_field_clinic_marketing_promotion_count(self):
        self.assertIn("clinic_marketing_promotion_count", self.env["clinic.ecommerce.catalog.item"]._fields)

    def test_350_upstream_model_clinic_branch(self):
        self.assertIn("clinic.branch", self.env.registry)

    def test_351_upstream_clinic_branch_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.branch"]._fields)

    def test_352_upstream_clinic_branch_field_clinic_marketing_campaign_ids(self):
        self.assertIn("clinic_marketing_campaign_ids", self.env["clinic.branch"]._fields)

    def test_353_upstream_clinic_branch_field_clinic_marketing_campaign_count(self):
        self.assertIn("clinic_marketing_campaign_count", self.env["clinic.branch"]._fields)

    def test_354_upstream_model_mailing_mailing(self):
        self.assertIn("mailing.mailing", self.env.registry)

    def test_355_upstream_mailing_mailing_field_clinic_marketing_campaign_id(self):
        self.assertIn("clinic_marketing_campaign_id", self.env["mailing.mailing"]._fields)

    def test_356_native_mailing_mailing_field_subject(self):
        self.assertIn("subject", self.env["mailing.mailing"]._fields)

    def test_357_native_mailing_mailing_field_preview(self):
        self.assertIn("preview", self.env["mailing.mailing"]._fields)

    def test_358_native_mailing_mailing_field_body_arch(self):
        self.assertIn("body_arch", self.env["mailing.mailing"]._fields)

    def test_359_native_mailing_mailing_field_mailing_model_id(self):
        self.assertIn("mailing_model_id", self.env["mailing.mailing"]._fields)

    def test_360_native_mailing_mailing_field_mailing_domain(self):
        self.assertIn("mailing_domain", self.env["mailing.mailing"]._fields)

    def test_361_native_mailing_mailing_field_mailing_type(self):
        self.assertIn("mailing_type", self.env["mailing.mailing"]._fields)

    def test_362_native_mailing_mailing_field_campaign_id(self):
        self.assertIn("campaign_id", self.env["mailing.mailing"]._fields)

    def test_363_native_mailing_mailing_field_user_id(self):
        self.assertIn("user_id", self.env["mailing.mailing"]._fields)

    def test_364_native_mailing_mailing_field_use_exclusion_list(self):
        self.assertIn("use_exclusion_list", self.env["mailing.mailing"]._fields)

    def test_365_native_mailing_mailing_field_email_from(self):
        self.assertIn("email_from", self.env["mailing.mailing"]._fields)

    def test_366_native_mailing_mailing_field_schedule_type(self):
        self.assertIn("schedule_type", self.env["mailing.mailing"]._fields)

    def test_367_native_mailing_mailing_field_schedule_date(self):
        self.assertIn("schedule_date", self.env["mailing.mailing"]._fields)

    def test_368_native_mailing_mailing_field_state(self):
        self.assertIn("state", self.env["mailing.mailing"]._fields)

    def test_369_native_mailing_mailing_field_sent(self):
        self.assertIn("sent", self.env["mailing.mailing"]._fields)

    def test_370_native_mailing_mailing_field_opened_ratio(self):
        self.assertIn("opened_ratio", self.env["mailing.mailing"]._fields)

    def test_371_native_mailing_mailing_field_clicks_ratio(self):
        self.assertIn("clicks_ratio", self.env["mailing.mailing"]._fields)

    def test_372_native_mailing_mailing_field_bounced_ratio(self):
        self.assertIn("bounced_ratio", self.env["mailing.mailing"]._fields)

    def test_373_native_mailing_mailing_field_replied_ratio(self):
        self.assertIn("replied_ratio", self.env["mailing.mailing"]._fields)

    def test_374_native_mailing_trace_field_mass_mailing_id(self):
        self.assertIn("mass_mailing_id", self.env["mailing.trace"]._fields)

    def test_375_native_mailing_trace_field_model(self):
        self.assertIn("model", self.env["mailing.trace"]._fields)

    def test_376_native_mailing_trace_field_res_id(self):
        self.assertIn("res_id", self.env["mailing.trace"]._fields)

    def test_377_native_mailing_trace_field_trace_status(self):
        self.assertIn("trace_status", self.env["mailing.trace"]._fields)

    def test_378_native_mailing_trace_field_failure_reason(self):
        self.assertIn("failure_reason", self.env["mailing.trace"]._fields)

    def test_379_native_utm_campaign_field_name(self):
        self.assertIn("name", self.env["utm.campaign"]._fields)

    def test_380_native_method_mailing_mailing_action_put_in_queue(self):
        self.assertTrue(hasattr(self.env["mailing.mailing"], "action_put_in_queue"))

    def test_381_native_method_mailing_mailing_action_cancel(self):
        self.assertTrue(hasattr(self.env["mailing.mailing"], "action_cancel"))

    def test_382_group_group_marketing_user(self):
        self.assertTrue(self.env.ref("clinic_marketing.group_marketing_user"))

    def test_383_group_group_marketing_coordinator(self):
        self.assertTrue(self.env.ref("clinic_marketing.group_marketing_coordinator"))

    def test_384_group_group_marketing_manager(self):
        self.assertTrue(self.env.ref("clinic_marketing.group_marketing_manager"))

    def test_385_group_group_mass_mailing_user(self):
        self.assertTrue(self.env.ref("mass_mailing.group_mass_mailing_user"))

    def test_386_group_group_mass_mailing_campaign(self):
        self.assertTrue(self.env.ref("mass_mailing.group_mass_mailing_campaign"))

    def test_387_coordinator_implies_user(self):
        user = self.env.ref("clinic_marketing.group_marketing_user")
        coordinator = self.env.ref("clinic_marketing.group_marketing_coordinator")
        self.assertIn(user, coordinator.implied_ids)

    def test_388_manager_implies_coordinator(self):
        coordinator = self.env.ref("clinic_marketing.group_marketing_coordinator")
        manager = self.env.ref("clinic_marketing.group_marketing_manager")
        self.assertIn(coordinator, manager.implied_ids)

    def test_389_coordinator_implies_mass_mailing_user(self):
        native = self.env.ref("mass_mailing.group_mass_mailing_user")
        coordinator = self.env.ref("clinic_marketing.group_marketing_coordinator")
        self.assertIn(native, coordinator.implied_ids)

    def test_390_manager_implies_mass_mailing_campaign(self):
        native = self.env.ref("mass_mailing.group_mass_mailing_campaign")
        manager = self.env.ref("clinic_marketing.group_marketing_manager")
        self.assertIn(native, manager.implied_ids)

    def test_391_view_clinic_marketing_preference_search(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.marketing.preference"),
            ("type", "=", "search"),
        ], limit=1)
        self.assertTrue(view)

    def test_392_view_clinic_marketing_preference_list(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.marketing.preference"),
            ("type", "=", "list"),
        ], limit=1)
        self.assertTrue(view)

    def test_393_view_clinic_marketing_preference_form(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.marketing.preference"),
            ("type", "=", "form"),
        ], limit=1)
        self.assertTrue(view)

    def test_394_view_clinic_marketing_segment_search(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.marketing.segment"),
            ("type", "=", "search"),
        ], limit=1)
        self.assertTrue(view)

    def test_395_view_clinic_marketing_segment_list(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.marketing.segment"),
            ("type", "=", "list"),
        ], limit=1)
        self.assertTrue(view)

    def test_396_view_clinic_marketing_segment_form(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.marketing.segment"),
            ("type", "=", "form"),
        ], limit=1)
        self.assertTrue(view)

    def test_397_view_clinic_marketing_promotion_search(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.marketing.promotion"),
            ("type", "=", "search"),
        ], limit=1)
        self.assertTrue(view)

    def test_398_view_clinic_marketing_promotion_list(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.marketing.promotion"),
            ("type", "=", "list"),
        ], limit=1)
        self.assertTrue(view)

    def test_399_view_clinic_marketing_promotion_form(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.marketing.promotion"),
            ("type", "=", "form"),
        ], limit=1)
        self.assertTrue(view)

    def test_400_view_clinic_marketing_campaign_search(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.marketing.campaign"),
            ("type", "=", "search"),
        ], limit=1)
        self.assertTrue(view)

    def test_401_view_clinic_marketing_campaign_list(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.marketing.campaign"),
            ("type", "=", "list"),
        ], limit=1)
        self.assertTrue(view)

    def test_402_view_clinic_marketing_campaign_form(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.marketing.campaign"),
            ("type", "=", "form"),
        ], limit=1)
        self.assertTrue(view)

    def test_403_view_clinic_marketing_recipient_search(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.marketing.recipient"),
            ("type", "=", "search"),
        ], limit=1)
        self.assertTrue(view)

    def test_404_view_clinic_marketing_recipient_list(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.marketing.recipient"),
            ("type", "=", "list"),
        ], limit=1)
        self.assertTrue(view)

    def test_405_view_clinic_marketing_recipient_form(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.marketing.recipient"),
            ("type", "=", "form"),
        ], limit=1)
        self.assertTrue(view)

    def test_406_view_clinic_marketing_message_search(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.marketing.message"),
            ("type", "=", "search"),
        ], limit=1)
        self.assertTrue(view)

    def test_407_view_clinic_marketing_message_list(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.marketing.message"),
            ("type", "=", "list"),
        ], limit=1)
        self.assertTrue(view)

    def test_408_view_clinic_marketing_message_form(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.marketing.message"),
            ("type", "=", "form"),
        ], limit=1)
        self.assertTrue(view)

    def test_409_xmlid_view_marketing_campaign_kanban(self):
        self.assertTrue(self.env.ref("clinic_marketing.view_marketing_campaign_kanban"))

    def test_410_xmlid_view_marketing_recipient_pivot(self):
        self.assertTrue(self.env.ref("clinic_marketing.view_marketing_recipient_pivot"))

    def test_411_xmlid_view_marketing_recipient_graph(self):
        self.assertTrue(self.env.ref("clinic_marketing.view_marketing_recipient_graph"))

    def test_412_xmlid_action_marketing_campaign(self):
        self.assertTrue(self.env.ref("clinic_marketing.action_marketing_campaign"))

    def test_413_xmlid_action_marketing_preference(self):
        self.assertTrue(self.env.ref("clinic_marketing.action_marketing_preference"))

    def test_414_xmlid_action_marketing_segment(self):
        self.assertTrue(self.env.ref("clinic_marketing.action_marketing_segment"))

    def test_415_xmlid_action_marketing_promotion(self):
        self.assertTrue(self.env.ref("clinic_marketing.action_marketing_promotion"))

    def test_416_xmlid_action_marketing_recipient(self):
        self.assertTrue(self.env.ref("clinic_marketing.action_marketing_recipient"))

    def test_417_xmlid_action_marketing_message(self):
        self.assertTrue(self.env.ref("clinic_marketing.action_marketing_message"))

    def test_418_xmlid_action_marketing_settings(self):
        self.assertTrue(self.env.ref("clinic_marketing.action_marketing_settings"))

    def test_419_xmlid_seq_marketing_campaign(self):
        self.assertTrue(self.env.ref("clinic_marketing.seq_marketing_campaign"))

    def test_420_xmlid_cron_marketing_sync_campaigns(self):
        self.assertTrue(self.env.ref("clinic_marketing.cron_marketing_sync_campaigns"))

    def test_421_xmlid_cron_marketing_dispatch_whatsapp(self):
        self.assertTrue(self.env.ref("clinic_marketing.cron_marketing_dispatch_whatsapp"))

    def test_422_xmlid_cron_marketing_expire_promotions(self):
        self.assertTrue(self.env.ref("clinic_marketing.cron_marketing_expire_promotions"))

    def test_423_search_architecture_odoo19(self):
        xmlids = (
            "clinic_marketing.view_marketing_preference_search",
            "clinic_marketing.view_marketing_segment_search",
            "clinic_marketing.view_marketing_promotion_search",
            "clinic_marketing.view_marketing_recipient_search",
            "clinic_marketing.view_marketing_message_search",
            "clinic_marketing.view_marketing_campaign_search",
        )
        for xmlid in xmlids:
            view = self.env.ref(xmlid)
            arch = view.arch_db
            if hasattr(arch, "get"):
                arch = arch.get(self.env.lang) or next(iter(arch.values()), "")
            root = etree.fromstring((arch or "").encode())
            self.assertEqual(root.tag, "search")
            self.assertFalse(root.attrib)
            for group in root.xpath("./group"):
                self.assertFalse(group.attrib)

    def test_424_bridge_method_res_partner_action_open_clinic_marketing_preferences(self):
        self.assertTrue(hasattr(self.env["res.partner"], "action_open_clinic_marketing_preferences"))

    def test_425_bridge_method_res_partner_action_open_clinic_marketing_campaigns(self):
        self.assertTrue(hasattr(self.env["res.partner"], "action_open_clinic_marketing_campaigns"))

    def test_426_bridge_method_clinic_patient_action_open_clinic_marketing_campaigns(self):
        self.assertTrue(hasattr(self.env["clinic.patient"], "action_open_clinic_marketing_campaigns"))

    def test_427_bridge_method_clinic_branch_action_open_clinic_marketing_campaigns(self):
        self.assertTrue(hasattr(self.env["clinic.branch"], "action_open_clinic_marketing_campaigns"))

    def test_428_bridge_method_clinic_ecommerce_catalog_item_action_open_clinic_marketing_promotions(self):
        self.assertTrue(hasattr(self.env["clinic.ecommerce.catalog.item"], "action_open_clinic_marketing_promotions"))

    def test_429_settings_field_clinic_marketing_require_explicit_consent(self):
        self.assertIn("clinic_marketing_require_explicit_consent", self.env["res.config.settings"]._fields)

    def test_430_settings_field_clinic_marketing_max_audience(self):
        self.assertIn("clinic_marketing_max_audience", self.env["res.config.settings"]._fields)

    def test_431_settings_field_clinic_marketing_whatsapp_transport(self):
        self.assertIn("clinic_marketing_whatsapp_transport", self.env["res.config.settings"]._fields)

    def test_432_no_parallel_clinic_marketing_booking(self):
        self.assertNotIn("clinic.marketing.booking", self.env.registry)

    def test_433_no_parallel_clinic_marketing_invoice(self):
        self.assertNotIn("clinic.marketing.invoice", self.env.registry)

    def test_434_no_parallel_clinic_marketing_whatsapp_gateway(self):
        self.assertNotIn("clinic.marketing.whatsapp.gateway", self.env.registry)

    def test_435_no_parallel_clinic_marketing_audit(self):
        self.assertNotIn("clinic.marketing.audit", self.env.registry)

    def test_436_no_parallel_clinic_marketing_analytics(self):
        self.assertNotIn("clinic.marketing.analytics", self.env.registry)

    def test_437_native_utm_campaign_title_field(self):
        self.assertIn("title", self.env["utm.campaign"]._fields)

    def test_438_promotion_validate_source_ready_method(self):
        self.assertTrue(hasattr(self.env["clinic.marketing.promotion"], "_validate_source_ready"))

