from lxml import etree

from odoo.tests.common import TransactionCase


class TestClinicTelemedicineEnterprise(TransactionCase):

    def test_001_model_clinic_telemedicine_session(self):
        self.assertIn("clinic.telemedicine.session", self.env.registry)

    def test_002_clinic_telemedicine_session_field_name(self):
        self.assertIn("name", self.env["clinic.telemedicine.session"]._fields)

    def test_003_clinic_telemedicine_session_field_string_name(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["name"].string)

    def test_004_clinic_telemedicine_session_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.telemedicine.session"]._fields)

    def test_005_clinic_telemedicine_session_field_string_company_id(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["company_id"].string)

    def test_006_clinic_telemedicine_session_field_branch_id(self):
        self.assertIn("branch_id", self.env["clinic.telemedicine.session"]._fields)

    def test_007_clinic_telemedicine_session_field_string_branch_id(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["branch_id"].string)

    def test_008_clinic_telemedicine_session_field_patient_id(self):
        self.assertIn("patient_id", self.env["clinic.telemedicine.session"]._fields)

    def test_009_clinic_telemedicine_session_field_string_patient_id(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["patient_id"].string)

    def test_010_clinic_telemedicine_session_field_partner_id(self):
        self.assertIn("partner_id", self.env["clinic.telemedicine.session"]._fields)

    def test_011_clinic_telemedicine_session_field_string_partner_id(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["partner_id"].string)

    def test_012_clinic_telemedicine_session_field_doctor_id(self):
        self.assertIn("doctor_id", self.env["clinic.telemedicine.session"]._fields)

    def test_013_clinic_telemedicine_session_field_string_doctor_id(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["doctor_id"].string)

    def test_014_clinic_telemedicine_session_field_host_staff_id(self):
        self.assertIn("host_staff_id", self.env["clinic.telemedicine.session"]._fields)

    def test_015_clinic_telemedicine_session_field_string_host_staff_id(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["host_staff_id"].string)

    def test_016_clinic_telemedicine_session_field_booking_id(self):
        self.assertIn("booking_id", self.env["clinic.telemedicine.session"]._fields)

    def test_017_clinic_telemedicine_session_field_string_booking_id(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["booking_id"].string)

    def test_018_clinic_telemedicine_session_field_appointment_id(self):
        self.assertIn("appointment_id", self.env["clinic.telemedicine.session"]._fields)

    def test_019_clinic_telemedicine_session_field_string_appointment_id(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["appointment_id"].string)

    def test_020_clinic_telemedicine_session_field_encounter_id(self):
        self.assertIn("encounter_id", self.env["clinic.telemedicine.session"]._fields)

    def test_021_clinic_telemedicine_session_field_string_encounter_id(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["encounter_id"].string)

    def test_022_clinic_telemedicine_session_field_consent_form_id(self):
        self.assertIn("consent_form_id", self.env["clinic.telemedicine.session"]._fields)

    def test_023_clinic_telemedicine_session_field_string_consent_form_id(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["consent_form_id"].string)

    def test_024_clinic_telemedicine_session_field_state(self):
        self.assertIn("state", self.env["clinic.telemedicine.session"]._fields)

    def test_025_clinic_telemedicine_session_field_string_state(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["state"].string)

    def test_026_clinic_telemedicine_session_field_scheduled_start(self):
        self.assertIn("scheduled_start", self.env["clinic.telemedicine.session"]._fields)

    def test_027_clinic_telemedicine_session_field_string_scheduled_start(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["scheduled_start"].string)

    def test_028_clinic_telemedicine_session_field_scheduled_end(self):
        self.assertIn("scheduled_end", self.env["clinic.telemedicine.session"]._fields)

    def test_029_clinic_telemedicine_session_field_string_scheduled_end(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["scheduled_end"].string)

    def test_030_clinic_telemedicine_session_field_duration_minutes(self):
        self.assertIn("duration_minutes", self.env["clinic.telemedicine.session"]._fields)

    def test_031_clinic_telemedicine_session_field_string_duration_minutes(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["duration_minutes"].string)

    def test_032_clinic_telemedicine_session_field_provider_mode(self):
        self.assertIn("provider_mode", self.env["clinic.telemedicine.session"]._fields)

    def test_033_clinic_telemedicine_session_field_string_provider_mode(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["provider_mode"].string)

    def test_034_clinic_telemedicine_session_field_meeting_url(self):
        self.assertIn("meeting_url", self.env["clinic.telemedicine.session"]._fields)

    def test_035_clinic_telemedicine_session_field_string_meeting_url(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["meeting_url"].string)

    def test_036_clinic_telemedicine_session_field_provider_reference(self):
        self.assertIn("provider_reference", self.env["clinic.telemedicine.session"]._fields)

    def test_037_clinic_telemedicine_session_field_string_provider_reference(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["provider_reference"].string)

    def test_038_clinic_telemedicine_session_field_meeting_ready(self):
        self.assertIn("meeting_ready", self.env["clinic.telemedicine.session"]._fields)

    def test_039_clinic_telemedicine_session_field_string_meeting_ready(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["meeting_ready"].string)

    def test_040_clinic_telemedicine_session_field_patient_can_join(self):
        self.assertIn("patient_can_join", self.env["clinic.telemedicine.session"]._fields)

    def test_041_clinic_telemedicine_session_field_string_patient_can_join(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["patient_can_join"].string)

    def test_042_clinic_telemedicine_session_field_host_joined_at(self):
        self.assertIn("host_joined_at", self.env["clinic.telemedicine.session"]._fields)

    def test_043_clinic_telemedicine_session_field_string_host_joined_at(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["host_joined_at"].string)

    def test_044_clinic_telemedicine_session_field_patient_joined_at(self):
        self.assertIn("patient_joined_at", self.env["clinic.telemedicine.session"]._fields)

    def test_045_clinic_telemedicine_session_field_string_patient_joined_at(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["patient_joined_at"].string)

    def test_046_clinic_telemedicine_session_field_started_at(self):
        self.assertIn("started_at", self.env["clinic.telemedicine.session"]._fields)

    def test_047_clinic_telemedicine_session_field_string_started_at(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["started_at"].string)

    def test_048_clinic_telemedicine_session_field_ended_at(self):
        self.assertIn("ended_at", self.env["clinic.telemedicine.session"]._fields)

    def test_049_clinic_telemedicine_session_field_string_ended_at(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["ended_at"].string)

    def test_050_clinic_telemedicine_session_field_cancelled_at(self):
        self.assertIn("cancelled_at", self.env["clinic.telemedicine.session"]._fields)

    def test_051_clinic_telemedicine_session_field_string_cancelled_at(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["cancelled_at"].string)

    def test_052_clinic_telemedicine_session_field_cancellation_reason(self):
        self.assertIn("cancellation_reason", self.env["clinic.telemedicine.session"]._fields)

    def test_053_clinic_telemedicine_session_field_string_cancellation_reason(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["cancellation_reason"].string)

    def test_054_clinic_telemedicine_session_field_thread_ids(self):
        self.assertIn("thread_ids", self.env["clinic.telemedicine.session"]._fields)

    def test_055_clinic_telemedicine_session_field_string_thread_ids(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["thread_ids"].string)

    def test_056_clinic_telemedicine_session_field_thread_count(self):
        self.assertIn("thread_count", self.env["clinic.telemedicine.session"]._fields)

    def test_057_clinic_telemedicine_session_field_string_thread_count(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["thread_count"].string)

    def test_058_clinic_telemedicine_session_field_queue_ids(self):
        self.assertIn("queue_ids", self.env["clinic.telemedicine.session"]._fields)

    def test_059_clinic_telemedicine_session_field_string_queue_ids(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["queue_ids"].string)

    def test_060_clinic_telemedicine_session_field_queue_count(self):
        self.assertIn("queue_count", self.env["clinic.telemedicine.session"]._fields)

    def test_061_clinic_telemedicine_session_field_string_queue_count(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["queue_count"].string)

    def test_062_clinic_telemedicine_session_field_portal_url(self):
        self.assertIn("portal_url", self.env["clinic.telemedicine.session"]._fields)

    def test_063_clinic_telemedicine_session_field_string_portal_url(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["portal_url"].string)

    def test_064_model_clinic_telemedicine_thread(self):
        self.assertIn("clinic.telemedicine.thread", self.env.registry)

    def test_065_clinic_telemedicine_thread_field_name(self):
        self.assertIn("name", self.env["clinic.telemedicine.thread"]._fields)

    def test_066_clinic_telemedicine_thread_field_string_name(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["name"].string)

    def test_067_clinic_telemedicine_thread_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.telemedicine.thread"]._fields)

    def test_068_clinic_telemedicine_thread_field_string_company_id(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["company_id"].string)

    def test_069_clinic_telemedicine_thread_field_branch_id(self):
        self.assertIn("branch_id", self.env["clinic.telemedicine.thread"]._fields)

    def test_070_clinic_telemedicine_thread_field_string_branch_id(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["branch_id"].string)

    def test_071_clinic_telemedicine_thread_field_session_id(self):
        self.assertIn("session_id", self.env["clinic.telemedicine.thread"]._fields)

    def test_072_clinic_telemedicine_thread_field_string_session_id(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["session_id"].string)

    def test_073_clinic_telemedicine_thread_field_patient_id(self):
        self.assertIn("patient_id", self.env["clinic.telemedicine.thread"]._fields)

    def test_074_clinic_telemedicine_thread_field_string_patient_id(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["patient_id"].string)

    def test_075_clinic_telemedicine_thread_field_partner_id(self):
        self.assertIn("partner_id", self.env["clinic.telemedicine.thread"]._fields)

    def test_076_clinic_telemedicine_thread_field_string_partner_id(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["partner_id"].string)

    def test_077_clinic_telemedicine_thread_field_doctor_id(self):
        self.assertIn("doctor_id", self.env["clinic.telemedicine.thread"]._fields)

    def test_078_clinic_telemedicine_thread_field_string_doctor_id(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["doctor_id"].string)

    def test_079_clinic_telemedicine_thread_field_handler_id(self):
        self.assertIn("handler_id", self.env["clinic.telemedicine.thread"]._fields)

    def test_080_clinic_telemedicine_thread_field_string_handler_id(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["handler_id"].string)

    def test_081_clinic_telemedicine_thread_field_subject(self):
        self.assertIn("subject", self.env["clinic.telemedicine.thread"]._fields)

    def test_082_clinic_telemedicine_thread_field_string_subject(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["subject"].string)

    def test_083_clinic_telemedicine_thread_field_priority(self):
        self.assertIn("priority", self.env["clinic.telemedicine.thread"]._fields)

    def test_084_clinic_telemedicine_thread_field_string_priority(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["priority"].string)

    def test_085_clinic_telemedicine_thread_field_state(self):
        self.assertIn("state", self.env["clinic.telemedicine.thread"]._fields)

    def test_086_clinic_telemedicine_thread_field_string_state(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["state"].string)

    def test_087_clinic_telemedicine_thread_field_patient_can_reply(self):
        self.assertIn("patient_can_reply", self.env["clinic.telemedicine.thread"]._fields)

    def test_088_clinic_telemedicine_thread_field_string_patient_can_reply(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["patient_can_reply"].string)

    def test_089_clinic_telemedicine_thread_field_patient_can_upload(self):
        self.assertIn("patient_can_upload", self.env["clinic.telemedicine.thread"]._fields)

    def test_090_clinic_telemedicine_thread_field_string_patient_can_upload(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["patient_can_upload"].string)

    def test_091_clinic_telemedicine_thread_field_attention_required(self):
        self.assertIn("attention_required", self.env["clinic.telemedicine.thread"]._fields)

    def test_092_clinic_telemedicine_thread_field_string_attention_required(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["attention_required"].string)

    def test_093_clinic_telemedicine_thread_field_internal_note(self):
        self.assertIn("internal_note", self.env["clinic.telemedicine.thread"]._fields)

    def test_094_clinic_telemedicine_thread_field_string_internal_note(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["internal_note"].string)

    def test_095_clinic_telemedicine_thread_field_message_ids(self):
        self.assertIn("message_ids", self.env["clinic.telemedicine.thread"]._fields)

    def test_096_clinic_telemedicine_thread_field_string_message_ids(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["message_ids"].string)

    def test_097_clinic_telemedicine_thread_field_attachment_ids(self):
        self.assertIn("attachment_ids", self.env["clinic.telemedicine.thread"]._fields)

    def test_098_clinic_telemedicine_thread_field_string_attachment_ids(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["attachment_ids"].string)

    def test_099_clinic_telemedicine_thread_field_message_count(self):
        self.assertIn("message_count", self.env["clinic.telemedicine.thread"]._fields)

    def test_100_clinic_telemedicine_thread_field_string_message_count(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["message_count"].string)

    def test_101_clinic_telemedicine_thread_field_attachment_count(self):
        self.assertIn("attachment_count", self.env["clinic.telemedicine.thread"]._fields)

    def test_102_clinic_telemedicine_thread_field_string_attachment_count(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["attachment_count"].string)

    def test_103_clinic_telemedicine_thread_field_patient_unread_count(self):
        self.assertIn("patient_unread_count", self.env["clinic.telemedicine.thread"]._fields)

    def test_104_clinic_telemedicine_thread_field_string_patient_unread_count(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["patient_unread_count"].string)

    def test_105_clinic_telemedicine_thread_field_clinic_unread_count(self):
        self.assertIn("clinic_unread_count", self.env["clinic.telemedicine.thread"]._fields)

    def test_106_clinic_telemedicine_thread_field_string_clinic_unread_count(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["clinic_unread_count"].string)

    def test_107_clinic_telemedicine_thread_field_first_patient_message_at(self):
        self.assertIn("first_patient_message_at", self.env["clinic.telemedicine.thread"]._fields)

    def test_108_clinic_telemedicine_thread_field_string_first_patient_message_at(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["first_patient_message_at"].string)

    def test_109_clinic_telemedicine_thread_field_first_response_on(self):
        self.assertIn("first_response_on", self.env["clinic.telemedicine.thread"]._fields)

    def test_110_clinic_telemedicine_thread_field_string_first_response_on(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["first_response_on"].string)

    def test_111_clinic_telemedicine_thread_field_first_response_minutes(self):
        self.assertIn("first_response_minutes", self.env["clinic.telemedicine.thread"]._fields)

    def test_112_clinic_telemedicine_thread_field_string_first_response_minutes(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["first_response_minutes"].string)

    def test_113_clinic_telemedicine_thread_field_last_message_at(self):
        self.assertIn("last_message_at", self.env["clinic.telemedicine.thread"]._fields)

    def test_114_clinic_telemedicine_thread_field_string_last_message_at(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["last_message_at"].string)

    def test_115_clinic_telemedicine_thread_field_closed_at(self):
        self.assertIn("closed_at", self.env["clinic.telemedicine.thread"]._fields)

    def test_116_clinic_telemedicine_thread_field_string_closed_at(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["closed_at"].string)

    def test_117_clinic_telemedicine_thread_field_closed_by_id(self):
        self.assertIn("closed_by_id", self.env["clinic.telemedicine.thread"]._fields)

    def test_118_clinic_telemedicine_thread_field_string_closed_by_id(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["closed_by_id"].string)

    def test_119_clinic_telemedicine_thread_field_portal_url(self):
        self.assertIn("portal_url", self.env["clinic.telemedicine.thread"]._fields)

    def test_120_clinic_telemedicine_thread_field_string_portal_url(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["portal_url"].string)

    def test_121_model_clinic_telemedicine_message(self):
        self.assertIn("clinic.telemedicine.message", self.env.registry)

    def test_122_clinic_telemedicine_message_field_thread_id(self):
        self.assertIn("thread_id", self.env["clinic.telemedicine.message"]._fields)

    def test_123_clinic_telemedicine_message_field_string_thread_id(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["thread_id"].string)

    def test_124_clinic_telemedicine_message_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.telemedicine.message"]._fields)

    def test_125_clinic_telemedicine_message_field_string_company_id(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["company_id"].string)

    def test_126_clinic_telemedicine_message_field_patient_id(self):
        self.assertIn("patient_id", self.env["clinic.telemedicine.message"]._fields)

    def test_127_clinic_telemedicine_message_field_string_patient_id(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["patient_id"].string)

    def test_128_clinic_telemedicine_message_field_partner_id(self):
        self.assertIn("partner_id", self.env["clinic.telemedicine.message"]._fields)

    def test_129_clinic_telemedicine_message_field_string_partner_id(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["partner_id"].string)

    def test_130_clinic_telemedicine_message_field_doctor_id(self):
        self.assertIn("doctor_id", self.env["clinic.telemedicine.message"]._fields)

    def test_131_clinic_telemedicine_message_field_string_doctor_id(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["doctor_id"].string)

    def test_132_clinic_telemedicine_message_field_author_kind(self):
        self.assertIn("author_kind", self.env["clinic.telemedicine.message"]._fields)

    def test_133_clinic_telemedicine_message_field_string_author_kind(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["author_kind"].string)

    def test_134_clinic_telemedicine_message_field_author_user_id(self):
        self.assertIn("author_user_id", self.env["clinic.telemedicine.message"]._fields)

    def test_135_clinic_telemedicine_message_field_string_author_user_id(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["author_user_id"].string)

    def test_136_clinic_telemedicine_message_field_author_partner_id(self):
        self.assertIn("author_partner_id", self.env["clinic.telemedicine.message"]._fields)

    def test_137_clinic_telemedicine_message_field_string_author_partner_id(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["author_partner_id"].string)

    def test_138_clinic_telemedicine_message_field_author_staff_id(self):
        self.assertIn("author_staff_id", self.env["clinic.telemedicine.message"]._fields)

    def test_139_clinic_telemedicine_message_field_string_author_staff_id(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["author_staff_id"].string)

    def test_140_clinic_telemedicine_message_field_sender_display_name(self):
        self.assertIn("sender_display_name", self.env["clinic.telemedicine.message"]._fields)

    def test_141_clinic_telemedicine_message_field_string_sender_display_name(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["sender_display_name"].string)

    def test_142_clinic_telemedicine_message_field_body(self):
        self.assertIn("body", self.env["clinic.telemedicine.message"]._fields)

    def test_143_clinic_telemedicine_message_field_string_body(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["body"].string)

    def test_144_clinic_telemedicine_message_field_sent_at(self):
        self.assertIn("sent_at", self.env["clinic.telemedicine.message"]._fields)

    def test_145_clinic_telemedicine_message_field_string_sent_at(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["sent_at"].string)

    def test_146_clinic_telemedicine_message_field_direction(self):
        self.assertIn("direction", self.env["clinic.telemedicine.message"]._fields)

    def test_147_clinic_telemedicine_message_field_string_direction(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["direction"].string)

    def test_148_clinic_telemedicine_message_field_patient_read_at(self):
        self.assertIn("patient_read_at", self.env["clinic.telemedicine.message"]._fields)

    def test_149_clinic_telemedicine_message_field_string_patient_read_at(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["patient_read_at"].string)

    def test_150_clinic_telemedicine_message_field_clinic_read_at(self):
        self.assertIn("clinic_read_at", self.env["clinic.telemedicine.message"]._fields)

    def test_151_clinic_telemedicine_message_field_string_clinic_read_at(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["clinic_read_at"].string)

    def test_152_clinic_telemedicine_message_field_attachment_ids(self):
        self.assertIn("attachment_ids", self.env["clinic.telemedicine.message"]._fields)

    def test_153_clinic_telemedicine_message_field_string_attachment_ids(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["attachment_ids"].string)

    def test_154_clinic_telemedicine_message_field_attachment_count(self):
        self.assertIn("attachment_count", self.env["clinic.telemedicine.message"]._fields)

    def test_155_clinic_telemedicine_message_field_string_attachment_count(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["attachment_count"].string)

    def test_156_model_clinic_telemedicine_attachment(self):
        self.assertIn("clinic.telemedicine.attachment", self.env.registry)

    def test_157_clinic_telemedicine_attachment_field_thread_id(self):
        self.assertIn("thread_id", self.env["clinic.telemedicine.attachment"]._fields)

    def test_158_clinic_telemedicine_attachment_field_string_thread_id(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["thread_id"].string)

    def test_159_clinic_telemedicine_attachment_field_message_id(self):
        self.assertIn("message_id", self.env["clinic.telemedicine.attachment"]._fields)

    def test_160_clinic_telemedicine_attachment_field_string_message_id(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["message_id"].string)

    def test_161_clinic_telemedicine_attachment_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.telemedicine.attachment"]._fields)

    def test_162_clinic_telemedicine_attachment_field_string_company_id(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["company_id"].string)

    def test_163_clinic_telemedicine_attachment_field_patient_id(self):
        self.assertIn("patient_id", self.env["clinic.telemedicine.attachment"]._fields)

    def test_164_clinic_telemedicine_attachment_field_string_patient_id(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["patient_id"].string)

    def test_165_clinic_telemedicine_attachment_field_partner_id(self):
        self.assertIn("partner_id", self.env["clinic.telemedicine.attachment"]._fields)

    def test_166_clinic_telemedicine_attachment_field_string_partner_id(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["partner_id"].string)

    def test_167_clinic_telemedicine_attachment_field_name(self):
        self.assertIn("name", self.env["clinic.telemedicine.attachment"]._fields)

    def test_168_clinic_telemedicine_attachment_field_string_name(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["name"].string)

    def test_169_clinic_telemedicine_attachment_field_datas(self):
        self.assertIn("datas", self.env["clinic.telemedicine.attachment"]._fields)

    def test_170_clinic_telemedicine_attachment_field_string_datas(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["datas"].string)

    def test_171_clinic_telemedicine_attachment_field_mimetype(self):
        self.assertIn("mimetype", self.env["clinic.telemedicine.attachment"]._fields)

    def test_172_clinic_telemedicine_attachment_field_string_mimetype(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["mimetype"].string)

    def test_173_clinic_telemedicine_attachment_field_size_bytes(self):
        self.assertIn("size_bytes", self.env["clinic.telemedicine.attachment"]._fields)

    def test_174_clinic_telemedicine_attachment_field_string_size_bytes(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["size_bytes"].string)

    def test_175_clinic_telemedicine_attachment_field_sha256(self):
        self.assertIn("sha256", self.env["clinic.telemedicine.attachment"]._fields)

    def test_176_clinic_telemedicine_attachment_field_string_sha256(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["sha256"].string)

    def test_177_clinic_telemedicine_attachment_field_uploader_kind(self):
        self.assertIn("uploader_kind", self.env["clinic.telemedicine.attachment"]._fields)

    def test_178_clinic_telemedicine_attachment_field_string_uploader_kind(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["uploader_kind"].string)

    def test_179_clinic_telemedicine_attachment_field_uploaded_by_user_id(self):
        self.assertIn("uploaded_by_user_id", self.env["clinic.telemedicine.attachment"]._fields)

    def test_180_clinic_telemedicine_attachment_field_string_uploaded_by_user_id(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["uploaded_by_user_id"].string)

    def test_181_clinic_telemedicine_attachment_field_uploaded_by_partner_id(self):
        self.assertIn("uploaded_by_partner_id", self.env["clinic.telemedicine.attachment"]._fields)

    def test_182_clinic_telemedicine_attachment_field_string_uploaded_by_partner_id(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["uploaded_by_partner_id"].string)

    def test_183_clinic_telemedicine_attachment_field_uploaded_at(self):
        self.assertIn("uploaded_at", self.env["clinic.telemedicine.attachment"]._fields)

    def test_184_clinic_telemedicine_attachment_field_string_uploaded_at(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["uploaded_at"].string)

    def test_185_clinic_telemedicine_session_method_compute_duration_minutes(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "_compute_duration_minutes"))

    def test_186_clinic_telemedicine_session_method_compute_meeting_ready(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "_compute_meeting_ready"))

    def test_187_clinic_telemedicine_session_method_compute_patient_can_join(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "_compute_patient_can_join"))

    def test_188_clinic_telemedicine_session_method_compute_thread_count(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "_compute_thread_count"))

    def test_189_clinic_telemedicine_session_method_compute_queue_count(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "_compute_queue_count"))

    def test_190_clinic_telemedicine_session_method_compute_portal_url(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "_compute_portal_url"))

    def test_191_clinic_telemedicine_session_method_check_source_consistency(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "_check_source_consistency"))

    def test_192_clinic_telemedicine_session_method_check_meeting_url(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "_check_meeting_url"))

    def test_193_clinic_telemedicine_session_method_validate_https_url(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "_validate_https_url"))

    def test_194_clinic_telemedicine_session_method_require_clinician(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "_require_clinician"))

    def test_195_clinic_telemedicine_session_method_require_manager(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "_require_manager"))

    def test_196_clinic_telemedicine_session_method_validate_operational_readiness(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "_validate_operational_readiness"))

    def test_197_clinic_telemedicine_session_method_action_schedule(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "action_schedule"))

    def test_198_clinic_telemedicine_session_method_provision_meeting_via_provider(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "_provision_meeting_via_provider"))

    def test_199_clinic_telemedicine_session_method_action_provision_meeting(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "action_provision_meeting"))

    def test_200_clinic_telemedicine_session_method_action_mark_ready(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "action_mark_ready"))

    def test_201_clinic_telemedicine_session_method_action_start(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "action_start"))

    def test_202_clinic_telemedicine_session_method_action_complete(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "action_complete"))

    def test_203_clinic_telemedicine_session_method_action_cancel(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "action_cancel"))

    def test_204_clinic_telemedicine_session_method_action_mark_no_show(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "action_mark_no_show"))

    def test_205_clinic_telemedicine_session_method_patient_join_allowed(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "_patient_join_allowed"))

    def test_206_clinic_telemedicine_session_method_record_patient_join(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "_record_patient_join"))

    def test_207_clinic_telemedicine_session_method_action_join_meeting(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "action_join_meeting"))

    def test_208_clinic_telemedicine_session_method_ensure_secure_thread(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "_ensure_secure_thread"))

    def test_209_clinic_telemedicine_session_method_action_open_thread(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "action_open_thread"))

    def test_210_clinic_telemedicine_session_method_action_open_queues(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "action_open_queues"))

    def test_211_clinic_telemedicine_session_method_action_open_patient(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "action_open_patient"))

    def test_212_clinic_telemedicine_session_method_action_open_doctor(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "action_open_doctor"))

    def test_213_clinic_telemedicine_session_method_action_open_booking(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "action_open_booking"))

    def test_214_clinic_telemedicine_session_method_action_open_appointment(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "action_open_appointment"))

    def test_215_clinic_telemedicine_session_method_action_open_encounter(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "action_open_encounter"))

    def test_216_clinic_telemedicine_session_method_action_open_portal(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "action_open_portal"))

    def test_217_clinic_telemedicine_thread_method_compute_counts(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.thread"], "_compute_counts"))

    def test_218_clinic_telemedicine_thread_method_compute_first_response_minutes(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.thread"], "_compute_first_response_minutes"))

    def test_219_clinic_telemedicine_thread_method_compute_portal_url(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.thread"], "_compute_portal_url"))

    def test_220_clinic_telemedicine_thread_method_check_scope_consistency(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.thread"], "_check_scope_consistency"))

    def test_221_clinic_telemedicine_thread_method_require_clinician(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.thread"], "_require_clinician"))

    def test_222_clinic_telemedicine_thread_method_require_manager(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.thread"], "_require_manager"))

    def test_223_clinic_telemedicine_thread_method_record_message_metrics(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.thread"], "_record_message_metrics"))

    def test_224_clinic_telemedicine_thread_method_action_assign_to_me(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.thread"], "action_assign_to_me"))

    def test_225_clinic_telemedicine_thread_method_action_close(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.thread"], "action_close"))

    def test_226_clinic_telemedicine_thread_method_action_reopen(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.thread"], "action_reopen"))

    def test_227_clinic_telemedicine_thread_method_action_archive(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.thread"], "action_archive"))

    def test_228_clinic_telemedicine_thread_method_action_mark_clinic_read(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.thread"], "action_mark_clinic_read"))

    def test_229_clinic_telemedicine_thread_method_action_open_session(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.thread"], "action_open_session"))

    def test_230_clinic_telemedicine_thread_method_action_open_patient(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.thread"], "action_open_patient"))

    def test_231_clinic_telemedicine_thread_method_action_open_doctor(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.thread"], "action_open_doctor"))

    def test_232_clinic_telemedicine_thread_method_action_open_messages(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.thread"], "action_open_messages"))

    def test_233_clinic_telemedicine_thread_method_action_open_attachments(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.thread"], "action_open_attachments"))

    def test_234_clinic_telemedicine_thread_method_action_open_portal(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.thread"], "action_open_portal"))

    def test_235_clinic_telemedicine_message_method_compute_direction(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.message"], "_compute_direction"))

    def test_236_clinic_telemedicine_message_method_compute_attachment_count(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.message"], "_compute_attachment_count"))

    def test_237_clinic_telemedicine_message_method_check_scope(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.message"], "_check_scope"))

    def test_238_clinic_telemedicine_message_method_action_mark_clinic_read(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.message"], "action_mark_clinic_read"))

    def test_239_clinic_telemedicine_message_method_mark_patient_read(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.message"], "_mark_patient_read"))

    def test_240_clinic_telemedicine_message_method_action_open_thread(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.message"], "action_open_thread"))

    def test_241_clinic_telemedicine_message_method_action_open_attachments(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.message"], "action_open_attachments"))

    def test_242_clinic_telemedicine_attachment_method_decode_payload(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.attachment"], "_decode_payload"))

    def test_243_clinic_telemedicine_attachment_method_validate_file_payload(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.attachment"], "_validate_file_payload"))

    def test_244_clinic_telemedicine_attachment_method_check_scope(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.attachment"], "_check_scope"))

    def test_245_clinic_telemedicine_attachment_method_action_download(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.attachment"], "action_download"))

    def test_246_clinic_telemedicine_attachment_method_action_open_thread(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.attachment"], "action_open_thread"))

    def test_247_clinic_telemedicine_attachment_method_action_open_message(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.attachment"], "action_open_message"))

    def test_248_clinic_telemedicine_attachment_method_action_open_patient(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.attachment"], "action_open_patient"))

    def test_249_table_clinic_telemedicine_session(self):
        self.assertEqual(self.env["clinic.telemedicine.session"]._table, "clinic_telemedicine_session")

    def test_250_table_clinic_telemedicine_thread(self):
        self.assertEqual(self.env["clinic.telemedicine.thread"]._table, "clinic_telemedicine_thread")

    def test_251_table_clinic_telemedicine_message(self):
        self.assertEqual(self.env["clinic.telemedicine.message"]._table, "clinic_telemedicine_message")

    def test_252_table_clinic_telemedicine_attachment(self):
        self.assertEqual(self.env["clinic.telemedicine.attachment"]._table, "clinic_telemedicine_attachment")

    def test_253_selection_clinic_telemedicine_session_state_draft(self):
        selection = dict(self.env["clinic.telemedicine.session"]._fields["state"].selection)
        self.assertIn("draft", selection)

    def test_254_selection_clinic_telemedicine_session_state_scheduled(self):
        selection = dict(self.env["clinic.telemedicine.session"]._fields["state"].selection)
        self.assertIn("scheduled", selection)

    def test_255_selection_clinic_telemedicine_session_state_ready(self):
        selection = dict(self.env["clinic.telemedicine.session"]._fields["state"].selection)
        self.assertIn("ready", selection)

    def test_256_selection_clinic_telemedicine_session_state_in_progress(self):
        selection = dict(self.env["clinic.telemedicine.session"]._fields["state"].selection)
        self.assertIn("in_progress", selection)

    def test_257_selection_clinic_telemedicine_session_state_completed(self):
        selection = dict(self.env["clinic.telemedicine.session"]._fields["state"].selection)
        self.assertIn("completed", selection)

    def test_258_selection_clinic_telemedicine_session_state_cancelled(self):
        selection = dict(self.env["clinic.telemedicine.session"]._fields["state"].selection)
        self.assertIn("cancelled", selection)

    def test_259_selection_clinic_telemedicine_session_state_no_show(self):
        selection = dict(self.env["clinic.telemedicine.session"]._fields["state"].selection)
        self.assertIn("no_show", selection)

    def test_260_selection_clinic_telemedicine_session_provider_mode_manual_url(self):
        selection = dict(self.env["clinic.telemedicine.session"]._fields["provider_mode"].selection)
        self.assertIn("manual_url", selection)

    def test_261_selection_clinic_telemedicine_session_provider_mode_provider_hook(self):
        selection = dict(self.env["clinic.telemedicine.session"]._fields["provider_mode"].selection)
        self.assertIn("provider_hook", selection)

    def test_262_selection_clinic_telemedicine_thread_state_open(self):
        selection = dict(self.env["clinic.telemedicine.thread"]._fields["state"].selection)
        self.assertIn("open", selection)

    def test_263_selection_clinic_telemedicine_thread_state_closed(self):
        selection = dict(self.env["clinic.telemedicine.thread"]._fields["state"].selection)
        self.assertIn("closed", selection)

    def test_264_selection_clinic_telemedicine_thread_state_archived(self):
        selection = dict(self.env["clinic.telemedicine.thread"]._fields["state"].selection)
        self.assertIn("archived", selection)

    def test_265_selection_clinic_telemedicine_thread_priority_routine(self):
        selection = dict(self.env["clinic.telemedicine.thread"]._fields["priority"].selection)
        self.assertIn("routine", selection)

    def test_266_selection_clinic_telemedicine_thread_priority_priority(self):
        selection = dict(self.env["clinic.telemedicine.thread"]._fields["priority"].selection)
        self.assertIn("priority", selection)

    def test_267_selection_clinic_telemedicine_thread_priority_urgent(self):
        selection = dict(self.env["clinic.telemedicine.thread"]._fields["priority"].selection)
        self.assertIn("urgent", selection)

    def test_268_selection_clinic_telemedicine_message_author_kind_patient(self):
        selection = dict(self.env["clinic.telemedicine.message"]._fields["author_kind"].selection)
        self.assertIn("patient", selection)

    def test_269_selection_clinic_telemedicine_message_author_kind_doctor(self):
        selection = dict(self.env["clinic.telemedicine.message"]._fields["author_kind"].selection)
        self.assertIn("doctor", selection)

    def test_270_selection_clinic_telemedicine_message_author_kind_staff(self):
        selection = dict(self.env["clinic.telemedicine.message"]._fields["author_kind"].selection)
        self.assertIn("staff", selection)

    def test_271_selection_clinic_telemedicine_message_author_kind_system(self):
        selection = dict(self.env["clinic.telemedicine.message"]._fields["author_kind"].selection)
        self.assertIn("system", selection)

    def test_272_selection_clinic_telemedicine_message_direction_patient_to_clinic(self):
        selection = dict(self.env["clinic.telemedicine.message"]._fields["direction"].selection)
        self.assertIn("patient_to_clinic", selection)

    def test_273_selection_clinic_telemedicine_message_direction_clinic_to_patient(self):
        selection = dict(self.env["clinic.telemedicine.message"]._fields["direction"].selection)
        self.assertIn("clinic_to_patient", selection)

    def test_274_selection_clinic_telemedicine_message_direction_system(self):
        selection = dict(self.env["clinic.telemedicine.message"]._fields["direction"].selection)
        self.assertIn("system", selection)

    def test_275_selection_clinic_telemedicine_attachment_uploader_kind_patient(self):
        selection = dict(self.env["clinic.telemedicine.attachment"]._fields["uploader_kind"].selection)
        self.assertIn("patient", selection)

    def test_276_selection_clinic_telemedicine_attachment_uploader_kind_clinic(self):
        selection = dict(self.env["clinic.telemedicine.attachment"]._fields["uploader_kind"].selection)
        self.assertIn("clinic", selection)

    def test_277_selection_clinic_telemedicine_attachment_uploader_kind_system(self):
        selection = dict(self.env["clinic.telemedicine.attachment"]._fields["uploader_kind"].selection)
        self.assertIn("system", selection)

    def test_278_comodel_clinic_telemedicine_session_patient_id(self):
        self.assertEqual(self.env["clinic.telemedicine.session"]._fields["patient_id"].comodel_name, "clinic.patient")

    def test_279_comodel_clinic_telemedicine_session_doctor_id(self):
        self.assertEqual(self.env["clinic.telemedicine.session"]._fields["doctor_id"].comodel_name, "clinic.doctor")

    def test_280_comodel_clinic_telemedicine_session_host_staff_id(self):
        self.assertEqual(self.env["clinic.telemedicine.session"]._fields["host_staff_id"].comodel_name, "clinic.staff")

    def test_281_comodel_clinic_telemedicine_session_booking_id(self):
        self.assertEqual(self.env["clinic.telemedicine.session"]._fields["booking_id"].comodel_name, "booking.booking")

    def test_282_comodel_clinic_telemedicine_session_appointment_id(self):
        self.assertEqual(self.env["clinic.telemedicine.session"]._fields["appointment_id"].comodel_name, "clinic.appointment")

    def test_283_comodel_clinic_telemedicine_session_encounter_id(self):
        self.assertEqual(self.env["clinic.telemedicine.session"]._fields["encounter_id"].comodel_name, "clinic.encounter")

    def test_284_comodel_clinic_telemedicine_session_consent_form_id(self):
        self.assertEqual(self.env["clinic.telemedicine.session"]._fields["consent_form_id"].comodel_name, "clinic.consent.form")

    def test_285_comodel_clinic_telemedicine_thread_session_id(self):
        self.assertEqual(self.env["clinic.telemedicine.thread"]._fields["session_id"].comodel_name, "clinic.telemedicine.session")

    def test_286_comodel_clinic_telemedicine_thread_patient_id(self):
        self.assertEqual(self.env["clinic.telemedicine.thread"]._fields["patient_id"].comodel_name, "clinic.patient")

    def test_287_comodel_clinic_telemedicine_thread_doctor_id(self):
        self.assertEqual(self.env["clinic.telemedicine.thread"]._fields["doctor_id"].comodel_name, "clinic.doctor")

    def test_288_comodel_clinic_telemedicine_thread_handler_id(self):
        self.assertEqual(self.env["clinic.telemedicine.thread"]._fields["handler_id"].comodel_name, "clinic.staff")

    def test_289_comodel_clinic_telemedicine_message_thread_id(self):
        self.assertEqual(self.env["clinic.telemedicine.message"]._fields["thread_id"].comodel_name, "clinic.telemedicine.thread")

    def test_290_comodel_clinic_telemedicine_attachment_thread_id(self):
        self.assertEqual(self.env["clinic.telemedicine.attachment"]._fields["thread_id"].comodel_name, "clinic.telemedicine.thread")

    def test_291_comodel_clinic_telemedicine_attachment_message_id(self):
        self.assertEqual(self.env["clinic.telemedicine.attachment"]._fields["message_id"].comodel_name, "clinic.telemedicine.message")

    def test_292_integration_model_res_company(self):
        self.assertIn("res.company", self.env.registry)

    def test_293_integration_res_company_policy_branch_scope_telemedicine(self):
        self.assertIn("policy_branch_scope_telemedicine", self.env["res.company"]._fields)

    def test_294_integration_res_company_clinic_telemedicine_provider_mode(self):
        self.assertIn("clinic_telemedicine_provider_mode", self.env["res.company"]._fields)

    def test_295_integration_res_company_clinic_telemedicine_early_join_minutes(self):
        self.assertIn("clinic_telemedicine_early_join_minutes", self.env["res.company"]._fields)

    def test_296_integration_res_company_clinic_telemedicine_late_join_minutes(self):
        self.assertIn("clinic_telemedicine_late_join_minutes", self.env["res.company"]._fields)

    def test_297_integration_res_company_clinic_telemedicine_require_signed_consent(self):
        self.assertIn("clinic_telemedicine_require_signed_consent", self.env["res.company"]._fields)

    def test_298_integration_res_company_clinic_telemedicine_auto_create_thread(self):
        self.assertIn("clinic_telemedicine_auto_create_thread", self.env["res.company"]._fields)

    def test_299_integration_res_company_clinic_telemedicine_allow_patient_new_threads(self):
        self.assertIn("clinic_telemedicine_allow_patient_new_threads", self.env["res.company"]._fields)

    def test_300_integration_res_company_clinic_telemedicine_max_open_threads(self):
        self.assertIn("clinic_telemedicine_max_open_threads", self.env["res.company"]._fields)

    def test_301_integration_res_company_clinic_telemedicine_max_message_chars(self):
        self.assertIn("clinic_telemedicine_max_message_chars", self.env["res.company"]._fields)

    def test_302_integration_res_company_clinic_telemedicine_max_file_mb(self):
        self.assertIn("clinic_telemedicine_max_file_mb", self.env["res.company"]._fields)

    def test_303_integration_model_res_config_settings(self):
        self.assertIn("res.config.settings", self.env.registry)

    def test_304_integration_res_config_settings_clinic_telemedicine_provider_mode(self):
        self.assertIn("clinic_telemedicine_provider_mode", self.env["res.config.settings"]._fields)

    def test_305_integration_res_config_settings_clinic_telemedicine_early_join_minutes(self):
        self.assertIn("clinic_telemedicine_early_join_minutes", self.env["res.config.settings"]._fields)

    def test_306_integration_res_config_settings_clinic_telemedicine_late_join_minutes(self):
        self.assertIn("clinic_telemedicine_late_join_minutes", self.env["res.config.settings"]._fields)

    def test_307_integration_res_config_settings_clinic_telemedicine_require_signed_consent(self):
        self.assertIn("clinic_telemedicine_require_signed_consent", self.env["res.config.settings"]._fields)

    def test_308_integration_res_config_settings_clinic_telemedicine_auto_create_thread(self):
        self.assertIn("clinic_telemedicine_auto_create_thread", self.env["res.config.settings"]._fields)

    def test_309_integration_res_config_settings_clinic_telemedicine_allow_patient_new_threads(self):
        self.assertIn("clinic_telemedicine_allow_patient_new_threads", self.env["res.config.settings"]._fields)

    def test_310_integration_res_config_settings_clinic_telemedicine_max_open_threads(self):
        self.assertIn("clinic_telemedicine_max_open_threads", self.env["res.config.settings"]._fields)

    def test_311_integration_res_config_settings_clinic_telemedicine_max_message_chars(self):
        self.assertIn("clinic_telemedicine_max_message_chars", self.env["res.config.settings"]._fields)

    def test_312_integration_res_config_settings_clinic_telemedicine_max_file_mb(self):
        self.assertIn("clinic_telemedicine_max_file_mb", self.env["res.config.settings"]._fields)

    def test_313_integration_model_clinic_portal_profile(self):
        self.assertIn("clinic.portal.profile", self.env.registry)

    def test_314_integration_clinic_portal_profile_allow_telemedicine_access(self):
        self.assertIn("allow_telemedicine_access", self.env["clinic.portal.profile"]._fields)

    def test_315_integration_clinic_portal_profile_allow_secure_messaging(self):
        self.assertIn("allow_secure_messaging", self.env["clinic.portal.profile"]._fields)

    def test_316_integration_clinic_portal_profile_telemedicine_session_count(self):
        self.assertIn("telemedicine_session_count", self.env["clinic.portal.profile"]._fields)

    def test_317_integration_clinic_portal_profile_secure_thread_count(self):
        self.assertIn("secure_thread_count", self.env["clinic.portal.profile"]._fields)

    def test_318_integration_model_clinic_staff(self):
        self.assertIn("clinic.staff", self.env.registry)

    def test_319_integration_clinic_staff_telemed_thread_count(self):
        self.assertIn("telemed_thread_count", self.env["clinic.staff"]._fields)

    def test_320_integration_clinic_staff_telemedicine_thread_ids(self):
        self.assertIn("telemedicine_thread_ids", self.env["clinic.staff"]._fields)

    def test_321_integration_model_clinic_doctor(self):
        self.assertIn("clinic.doctor", self.env.registry)

    def test_322_integration_clinic_doctor_telemedicine_enabled(self):
        self.assertIn("telemedicine_enabled", self.env["clinic.doctor"]._fields)

    def test_323_integration_clinic_doctor_telemedicine_session_ids(self):
        self.assertIn("telemedicine_session_ids", self.env["clinic.doctor"]._fields)

    def test_324_integration_clinic_doctor_telemedicine_thread_ids(self):
        self.assertIn("telemedicine_thread_ids", self.env["clinic.doctor"]._fields)

    def test_325_integration_clinic_doctor_telemedicine_session_count(self):
        self.assertIn("telemedicine_session_count", self.env["clinic.doctor"]._fields)

    def test_326_integration_clinic_doctor_telemedicine_thread_count(self):
        self.assertIn("telemedicine_thread_count", self.env["clinic.doctor"]._fields)

    def test_327_integration_model_clinic_patient(self):
        self.assertIn("clinic.patient", self.env.registry)

    def test_328_integration_clinic_patient_telemedicine_session_ids(self):
        self.assertIn("telemedicine_session_ids", self.env["clinic.patient"]._fields)

    def test_329_integration_clinic_patient_telemedicine_thread_ids(self):
        self.assertIn("telemedicine_thread_ids", self.env["clinic.patient"]._fields)

    def test_330_integration_clinic_patient_telemedicine_session_count(self):
        self.assertIn("telemedicine_session_count", self.env["clinic.patient"]._fields)

    def test_331_integration_clinic_patient_telemedicine_thread_count(self):
        self.assertIn("telemedicine_thread_count", self.env["clinic.patient"]._fields)

    def test_332_integration_model_clinic_appointment(self):
        self.assertIn("clinic.appointment", self.env.registry)

    def test_333_integration_clinic_appointment_telemedicine(self):
        self.assertIn("telemedicine", self.env["clinic.appointment"]._fields)

    def test_334_integration_clinic_appointment_telemedicine_session_ids(self):
        self.assertIn("telemedicine_session_ids", self.env["clinic.appointment"]._fields)

    def test_335_integration_clinic_appointment_telemedicine_session_count(self):
        self.assertIn("telemedicine_session_count", self.env["clinic.appointment"]._fields)

    def test_336_integration_model_booking_booking(self):
        self.assertIn("booking.booking", self.env.registry)

    def test_337_integration_booking_booking_telemedicine_session_ids(self):
        self.assertIn("telemedicine_session_ids", self.env["booking.booking"]._fields)

    def test_338_integration_booking_booking_telemedicine_session_count(self):
        self.assertIn("telemedicine_session_count", self.env["booking.booking"]._fields)

    def test_339_integration_model_clinic_queue(self):
        self.assertIn("clinic.queue", self.env.registry)

    def test_340_integration_clinic_queue_telemedicine_session_id(self):
        self.assertIn("telemedicine_session_id", self.env["clinic.queue"]._fields)

    def test_341_integration_model_clinic_encounter(self):
        self.assertIn("clinic.encounter", self.env.registry)

    def test_342_integration_clinic_encounter_telemedicine_session_ids(self):
        self.assertIn("telemedicine_session_ids", self.env["clinic.encounter"]._fields)

    def test_343_integration_clinic_encounter_telemedicine_session_count(self):
        self.assertIn("telemedicine_session_count", self.env["clinic.encounter"]._fields)

    def test_344_integration_method_clinic_portal_profile_action_enable_telemedicine_access(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "action_enable_telemedicine_access"))

    def test_345_integration_method_clinic_portal_profile_action_disable_telemedicine_access(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "action_disable_telemedicine_access"))

    def test_346_integration_method_clinic_portal_profile_action_enable_secure_messaging(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "action_enable_secure_messaging"))

    def test_347_integration_method_clinic_portal_profile_action_disable_secure_messaging(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "action_disable_secure_messaging"))

    def test_348_integration_method_clinic_portal_profile__portal_telemedicine_session_domain(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "_portal_telemedicine_session_domain"))

    def test_349_integration_method_clinic_portal_profile__portal_secure_thread_domain(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "_portal_secure_thread_domain"))

    def test_350_integration_method_clinic_portal_profile__portal_telemedicine_counts(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "_portal_telemedicine_counts"))

    def test_351_integration_method_clinic_portal_profile_action_open_telemedicine_sessions(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "action_open_telemedicine_sessions"))

    def test_352_integration_method_clinic_portal_profile_action_open_secure_threads(self):
        self.assertTrue(hasattr(self.env["clinic.portal.profile"], "action_open_secure_threads"))

    def test_353_integration_method_clinic_staff_action_open_telemedicine_threads(self):
        self.assertTrue(hasattr(self.env["clinic.staff"], "action_open_telemedicine_threads"))

    def test_354_integration_method_clinic_doctor_action_open_telemedicine_sessions(self):
        self.assertTrue(hasattr(self.env["clinic.doctor"], "action_open_telemedicine_sessions"))

    def test_355_integration_method_clinic_doctor_action_open_telemedicine_threads(self):
        self.assertTrue(hasattr(self.env["clinic.doctor"], "action_open_telemedicine_threads"))

    def test_356_integration_method_clinic_patient_action_open_telemedicine_sessions(self):
        self.assertTrue(hasattr(self.env["clinic.patient"], "action_open_telemedicine_sessions"))

    def test_357_integration_method_clinic_patient_action_open_telemedicine_threads(self):
        self.assertTrue(hasattr(self.env["clinic.patient"], "action_open_telemedicine_threads"))

    def test_358_integration_method_clinic_appointment_action_create_telemedicine_session(self):
        self.assertTrue(hasattr(self.env["clinic.appointment"], "action_create_telemedicine_session"))

    def test_359_integration_method_clinic_appointment_action_open_telemedicine_sessions(self):
        self.assertTrue(hasattr(self.env["clinic.appointment"], "action_open_telemedicine_sessions"))

    def test_360_integration_method_booking_booking_action_create_telemedicine_session(self):
        self.assertTrue(hasattr(self.env["booking.booking"], "action_create_telemedicine_session"))

    def test_361_integration_method_booking_booking_action_open_telemedicine_sessions(self):
        self.assertTrue(hasattr(self.env["booking.booking"], "action_open_telemedicine_sessions"))

    def test_362_integration_method_clinic_queue_action_open_telemedicine_session(self):
        self.assertTrue(hasattr(self.env["clinic.queue"], "action_open_telemedicine_session"))

    def test_363_integration_method_clinic_encounter_action_open_telemedicine_sessions(self):
        self.assertTrue(hasattr(self.env["clinic.encounter"], "action_open_telemedicine_sessions"))

    def test_364_staff_historical_thread_comodel(self):
        self.assertEqual(
            self.env["clinic.staff"]._fields["telemedicine_thread_ids"].comodel_name,
            "clinic.telemedicine.thread",
        )

    def test_365_staff_historical_thread_inverse(self):
        self.assertEqual(
            self.env["clinic.staff"]._fields["telemedicine_thread_ids"].inverse_name,
            "handler_id",
        )

    def test_366_view_clinic_telemedicine_session_search(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.telemedicine.session"),
            ("type", "=", "search"),
        ], limit=1)
        self.assertTrue(view)

    def test_367_view_clinic_telemedicine_session_list(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.telemedicine.session"),
            ("type", "=", "list"),
        ], limit=1)
        self.assertTrue(view)

    def test_368_view_clinic_telemedicine_session_form(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.telemedicine.session"),
            ("type", "=", "form"),
        ], limit=1)
        self.assertTrue(view)

    def test_369_view_clinic_telemedicine_thread_search(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.telemedicine.thread"),
            ("type", "=", "search"),
        ], limit=1)
        self.assertTrue(view)

    def test_370_view_clinic_telemedicine_thread_list(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.telemedicine.thread"),
            ("type", "=", "list"),
        ], limit=1)
        self.assertTrue(view)

    def test_371_view_clinic_telemedicine_thread_form(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.telemedicine.thread"),
            ("type", "=", "form"),
        ], limit=1)
        self.assertTrue(view)

    def test_372_view_clinic_telemedicine_message_search(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.telemedicine.message"),
            ("type", "=", "search"),
        ], limit=1)
        self.assertTrue(view)

    def test_373_view_clinic_telemedicine_message_list(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.telemedicine.message"),
            ("type", "=", "list"),
        ], limit=1)
        self.assertTrue(view)

    def test_374_view_clinic_telemedicine_message_form(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.telemedicine.message"),
            ("type", "=", "form"),
        ], limit=1)
        self.assertTrue(view)

    def test_375_view_clinic_telemedicine_attachment_search(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.telemedicine.attachment"),
            ("type", "=", "search"),
        ], limit=1)
        self.assertTrue(view)

    def test_376_view_clinic_telemedicine_attachment_list(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.telemedicine.attachment"),
            ("type", "=", "list"),
        ], limit=1)
        self.assertTrue(view)

    def test_377_view_clinic_telemedicine_attachment_form(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.telemedicine.attachment"),
            ("type", "=", "form"),
        ], limit=1)
        self.assertTrue(view)

    def test_378_xmlid_view_telemedicine_session_kanban(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.view_telemedicine_session_kanban"))

    def test_379_xmlid_view_telemedicine_thread_kanban(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.view_telemedicine_thread_kanban"))

    def test_380_xmlid_view_telemedicine_portal_access_search(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.view_telemedicine_portal_access_search"))

    def test_381_xmlid_view_telemedicine_portal_access_list(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.view_telemedicine_portal_access_list"))

    def test_382_xmlid_view_telemedicine_portal_access_form(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.view_telemedicine_portal_access_form"))

    def test_383_xmlid_action_telemedicine_session(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.action_telemedicine_session"))

    def test_384_xmlid_action_telemedicine_thread(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.action_telemedicine_thread"))

    def test_385_xmlid_action_telemedicine_message(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.action_telemedicine_message"))

    def test_386_xmlid_action_telemedicine_attachment(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.action_telemedicine_attachment"))

    def test_387_xmlid_action_telemedicine_portal_access(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.action_telemedicine_portal_access"))

    def test_388_xmlid_action_telemedicine_settings(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.action_telemedicine_settings"))

    def test_389_xmlid_seq_telemedicine_session(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.seq_telemedicine_session"))

    def test_390_xmlid_seq_telemedicine_thread(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.seq_telemedicine_thread"))

    def test_391_xmlid_group_telemedicine_user(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.group_telemedicine_user"))

    def test_392_xmlid_group_telemedicine_clinician(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.group_telemedicine_clinician"))

    def test_393_xmlid_group_telemedicine_manager(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.group_telemedicine_manager"))

    def test_394_xmlid_portal_my_home_telemedicine(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.portal_my_home_telemedicine"))

    def test_395_xmlid_portal_breadcrumbs_telemedicine(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.portal_breadcrumbs_telemedicine"))

    def test_396_xmlid_portal_telemedicine_sessions(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.portal_telemedicine_sessions"))

    def test_397_xmlid_portal_telemedicine_session(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.portal_telemedicine_session"))

    def test_398_xmlid_portal_secure_threads(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.portal_secure_threads"))

    def test_399_xmlid_portal_secure_thread_new(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.portal_secure_thread_new"))

    def test_400_xmlid_portal_secure_thread(self):
        self.assertTrue(self.env.ref("clinic_telemedicine_secure_messaging.portal_secure_thread"))

    def test_401_clinician_implies_user(self):
        user = self.env.ref("clinic_telemedicine_secure_messaging.group_telemedicine_user")
        clinician = self.env.ref("clinic_telemedicine_secure_messaging.group_telemedicine_clinician")
        self.assertIn(user, clinician.implied_ids)

    def test_402_manager_implies_clinician(self):
        clinician = self.env.ref("clinic_telemedicine_secure_messaging.group_telemedicine_clinician")
        manager = self.env.ref("clinic_telemedicine_secure_messaging.group_telemedicine_manager")
        self.assertIn(clinician, manager.implied_ids)

    def test_403_stored_clinic_telemedicine_thread_message_count(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["message_count"].store)

    def test_404_stored_clinic_telemedicine_thread_attachment_count(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["attachment_count"].store)

    def test_405_stored_clinic_telemedicine_thread_patient_unread_count(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["patient_unread_count"].store)

    def test_406_stored_clinic_telemedicine_thread_clinic_unread_count(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["clinic_unread_count"].store)

    def test_407_stored_clinic_telemedicine_thread_first_response_minutes(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["first_response_minutes"].store)

    def test_408_stored_clinic_telemedicine_session_duration_minutes(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["duration_minutes"].store)

    def test_409_stored_clinic_telemedicine_message_direction(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["direction"].store)

    def test_410_attachment_security_decode_payload(self):
        self.assertTrue(callable(getattr(self.env["clinic.telemedicine.attachment"], "_decode_payload")))

    def test_411_attachment_security_validate_file_payload(self):
        self.assertTrue(callable(getattr(self.env["clinic.telemedicine.attachment"], "_validate_file_payload")))

    def test_412_search_architecture_odoo19(self):
        xmlids = (
            "clinic_telemedicine_secure_messaging.view_telemedicine_session_search",
            "clinic_telemedicine_secure_messaging.view_telemedicine_thread_search",
            "clinic_telemedicine_secure_messaging.view_telemedicine_message_search",
            "clinic_telemedicine_secure_messaging.view_telemedicine_attachment_search",
            "clinic_telemedicine_secure_messaging.view_telemedicine_portal_access_search",
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

    def test_413_no_parallel_clinic_telemedicine_provider(self):
        self.assertNotIn("clinic.telemedicine.provider", self.env.registry)

    def test_414_no_parallel_clinic_telemedicine_encryption_key(self):
        self.assertNotIn("clinic.telemedicine.encryption.key", self.env.registry)

    def test_415_no_parallel_clinic_telemedicine_incident(self):
        self.assertNotIn("clinic.telemedicine.incident", self.env.registry)

    def test_416_no_parallel_clinic_secure_chat(self):
        self.assertNotIn("clinic.secure.chat", self.env.registry)

    def test_417_no_parallel_clinic_telemedicine_audit(self):
        self.assertNotIn("clinic.telemedicine.audit", self.env.registry)

    def test_418_field_type_clinic_telemedicine_session_name(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["name"].type)

    def test_419_field_type_clinic_telemedicine_session_company_id(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["company_id"].type)

    def test_420_field_type_clinic_telemedicine_session_branch_id(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["branch_id"].type)

    def test_421_field_type_clinic_telemedicine_session_patient_id(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["patient_id"].type)

    def test_422_field_type_clinic_telemedicine_session_partner_id(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["partner_id"].type)

    def test_423_field_type_clinic_telemedicine_session_doctor_id(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["doctor_id"].type)

    def test_424_field_type_clinic_telemedicine_session_host_staff_id(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["host_staff_id"].type)

    def test_425_field_type_clinic_telemedicine_session_booking_id(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["booking_id"].type)

    def test_426_field_type_clinic_telemedicine_session_appointment_id(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["appointment_id"].type)

    def test_427_field_type_clinic_telemedicine_session_encounter_id(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["encounter_id"].type)

    def test_428_field_type_clinic_telemedicine_session_consent_form_id(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["consent_form_id"].type)

    def test_429_field_type_clinic_telemedicine_session_state(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["state"].type)

    def test_430_field_type_clinic_telemedicine_session_scheduled_start(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["scheduled_start"].type)

    def test_431_field_type_clinic_telemedicine_session_scheduled_end(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["scheduled_end"].type)

    def test_432_field_type_clinic_telemedicine_session_duration_minutes(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["duration_minutes"].type)

    def test_433_field_type_clinic_telemedicine_session_provider_mode(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["provider_mode"].type)

    def test_434_field_type_clinic_telemedicine_session_meeting_url(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["meeting_url"].type)

    def test_435_field_type_clinic_telemedicine_session_provider_reference(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["provider_reference"].type)

    def test_436_field_type_clinic_telemedicine_session_meeting_ready(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["meeting_ready"].type)

    def test_437_field_type_clinic_telemedicine_session_patient_can_join(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["patient_can_join"].type)

    def test_438_field_type_clinic_telemedicine_session_host_joined_at(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["host_joined_at"].type)

    def test_439_field_type_clinic_telemedicine_session_patient_joined_at(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["patient_joined_at"].type)

    def test_440_field_type_clinic_telemedicine_session_started_at(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["started_at"].type)

    def test_441_field_type_clinic_telemedicine_session_ended_at(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["ended_at"].type)

    def test_442_field_type_clinic_telemedicine_session_cancelled_at(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["cancelled_at"].type)

    def test_443_field_type_clinic_telemedicine_session_cancellation_reason(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["cancellation_reason"].type)

    def test_444_field_type_clinic_telemedicine_session_thread_ids(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["thread_ids"].type)

    def test_445_field_type_clinic_telemedicine_session_thread_count(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["thread_count"].type)

    def test_446_field_type_clinic_telemedicine_session_queue_ids(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["queue_ids"].type)

    def test_447_field_type_clinic_telemedicine_session_queue_count(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["queue_count"].type)

    def test_448_field_type_clinic_telemedicine_session_portal_url(self):
        self.assertTrue(self.env["clinic.telemedicine.session"]._fields["portal_url"].type)

    def test_449_field_type_clinic_telemedicine_thread_name(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["name"].type)

    def test_450_field_type_clinic_telemedicine_thread_company_id(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["company_id"].type)

    def test_451_field_type_clinic_telemedicine_thread_branch_id(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["branch_id"].type)

    def test_452_field_type_clinic_telemedicine_thread_session_id(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["session_id"].type)

    def test_453_field_type_clinic_telemedicine_thread_patient_id(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["patient_id"].type)

    def test_454_field_type_clinic_telemedicine_thread_partner_id(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["partner_id"].type)

    def test_455_field_type_clinic_telemedicine_thread_doctor_id(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["doctor_id"].type)

    def test_456_field_type_clinic_telemedicine_thread_handler_id(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["handler_id"].type)

    def test_457_field_type_clinic_telemedicine_thread_subject(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["subject"].type)

    def test_458_field_type_clinic_telemedicine_thread_priority(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["priority"].type)

    def test_459_field_type_clinic_telemedicine_thread_state(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["state"].type)

    def test_460_field_type_clinic_telemedicine_thread_patient_can_reply(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["patient_can_reply"].type)

    def test_461_field_type_clinic_telemedicine_thread_patient_can_upload(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["patient_can_upload"].type)

    def test_462_field_type_clinic_telemedicine_thread_attention_required(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["attention_required"].type)

    def test_463_field_type_clinic_telemedicine_thread_internal_note(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["internal_note"].type)

    def test_464_field_type_clinic_telemedicine_thread_message_ids(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["message_ids"].type)

    def test_465_field_type_clinic_telemedicine_thread_attachment_ids(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["attachment_ids"].type)

    def test_466_field_type_clinic_telemedicine_thread_message_count(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["message_count"].type)

    def test_467_field_type_clinic_telemedicine_thread_attachment_count(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["attachment_count"].type)

    def test_468_field_type_clinic_telemedicine_thread_patient_unread_count(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["patient_unread_count"].type)

    def test_469_field_type_clinic_telemedicine_thread_clinic_unread_count(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["clinic_unread_count"].type)

    def test_470_field_type_clinic_telemedicine_thread_first_patient_message_at(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["first_patient_message_at"].type)

    def test_471_field_type_clinic_telemedicine_thread_first_response_on(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["first_response_on"].type)

    def test_472_field_type_clinic_telemedicine_thread_first_response_minutes(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["first_response_minutes"].type)

    def test_473_field_type_clinic_telemedicine_thread_last_message_at(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["last_message_at"].type)

    def test_474_field_type_clinic_telemedicine_thread_closed_at(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["closed_at"].type)

    def test_475_field_type_clinic_telemedicine_thread_closed_by_id(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["closed_by_id"].type)

    def test_476_field_type_clinic_telemedicine_thread_portal_url(self):
        self.assertTrue(self.env["clinic.telemedicine.thread"]._fields["portal_url"].type)

    def test_477_field_type_clinic_telemedicine_message_thread_id(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["thread_id"].type)

    def test_478_field_type_clinic_telemedicine_message_company_id(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["company_id"].type)

    def test_479_field_type_clinic_telemedicine_message_patient_id(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["patient_id"].type)

    def test_480_field_type_clinic_telemedicine_message_partner_id(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["partner_id"].type)

    def test_481_field_type_clinic_telemedicine_message_doctor_id(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["doctor_id"].type)

    def test_482_field_type_clinic_telemedicine_message_author_kind(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["author_kind"].type)

    def test_483_field_type_clinic_telemedicine_message_author_user_id(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["author_user_id"].type)

    def test_484_field_type_clinic_telemedicine_message_author_partner_id(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["author_partner_id"].type)

    def test_485_field_type_clinic_telemedicine_message_author_staff_id(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["author_staff_id"].type)

    def test_486_field_type_clinic_telemedicine_message_sender_display_name(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["sender_display_name"].type)

    def test_487_field_type_clinic_telemedicine_message_body(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["body"].type)

    def test_488_field_type_clinic_telemedicine_message_sent_at(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["sent_at"].type)

    def test_489_field_type_clinic_telemedicine_message_direction(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["direction"].type)

    def test_490_field_type_clinic_telemedicine_message_patient_read_at(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["patient_read_at"].type)

    def test_491_field_type_clinic_telemedicine_message_clinic_read_at(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["clinic_read_at"].type)

    def test_492_field_type_clinic_telemedicine_message_attachment_ids(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["attachment_ids"].type)

    def test_493_field_type_clinic_telemedicine_message_attachment_count(self):
        self.assertTrue(self.env["clinic.telemedicine.message"]._fields["attachment_count"].type)

    def test_494_field_type_clinic_telemedicine_attachment_thread_id(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["thread_id"].type)

    def test_495_field_type_clinic_telemedicine_attachment_message_id(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["message_id"].type)

    def test_496_field_type_clinic_telemedicine_attachment_company_id(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["company_id"].type)

    def test_497_field_type_clinic_telemedicine_attachment_patient_id(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["patient_id"].type)

    def test_498_field_type_clinic_telemedicine_attachment_partner_id(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["partner_id"].type)

    def test_499_field_type_clinic_telemedicine_attachment_name(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["name"].type)

    def test_500_field_type_clinic_telemedicine_attachment_datas(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["datas"].type)

    def test_501_field_type_clinic_telemedicine_attachment_mimetype(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["mimetype"].type)

    def test_502_field_type_clinic_telemedicine_attachment_size_bytes(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["size_bytes"].type)

    def test_503_field_type_clinic_telemedicine_attachment_sha256(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["sha256"].type)

    def test_504_field_type_clinic_telemedicine_attachment_uploader_kind(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["uploader_kind"].type)

    def test_505_field_type_clinic_telemedicine_attachment_uploaded_by_user_id(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["uploaded_by_user_id"].type)

    def test_506_field_type_clinic_telemedicine_attachment_uploaded_by_partner_id(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["uploaded_by_partner_id"].type)

    def test_507_field_type_clinic_telemedicine_attachment_uploaded_at(self):
        self.assertTrue(self.env["clinic.telemedicine.attachment"]._fields["uploaded_at"].type)


    def test_508_partner_telemedicine_session_count_field(self):
        self.assertIn(
            "clinic_telemedicine_session_count",
            self.env["res.partner"]._fields,
        )

    def test_509_partner_telemedicine_thread_count_field(self):
        self.assertIn(
            "clinic_telemedicine_thread_count",
            self.env["res.partner"]._fields,
        )

    def test_510_partner_open_telemedicine_sessions_method(self):
        self.assertTrue(
            hasattr(
                self.env["res.partner"],
                "action_open_clinic_telemedicine_sessions",
            )
        )

    def test_511_partner_open_telemedicine_threads_method(self):
        self.assertTrue(
            hasattr(
                self.env["res.partner"],
                "action_open_clinic_telemedicine_threads",
            )
        )

    def test_512_partner_patient_id_contract(self):
        self.assertEqual(
            self.env["res.partner"]._fields["patient_id"].comodel_name,
            "clinic.patient",
        )

    def test_513_stable_native_partner_integration_view(self):
        view = self.env.ref(
            "clinic_telemedicine_secure_messaging."
            "view_partner_form_telemedicine_inherit"
        )
        self.assertEqual(view.model, "res.partner")
        self.assertEqual(
            view.inherit_id,
            self.env.ref("base.view_partner_form"),
        )

    def test_514_failed_patient_custom_view_not_used_by_repair_view(self):
        view = self.env.ref(
            "clinic_telemedicine_secure_messaging."
            "view_partner_form_telemedicine_inherit"
        )
        self.assertNotEqual(
            view.inherit_id._name,
            "clinic_patient.view_clinic_patient_form",
        )

    def test_515_repair_build_version(self):
        module = self.env["ir.module.module"].search(
            [("name", "=", "clinic_telemedicine_secure_messaging")],
            limit=1,
        )
        self.assertTrue(module)
