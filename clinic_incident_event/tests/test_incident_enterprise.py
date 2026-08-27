from lxml import etree

from odoo.tests.common import TransactionCase


class TestClinicIncidentEnterprise(TransactionCase):

    def test_001_model_clinic_incident_category(self):
        self.assertIn("clinic.incident.category", self.env.registry)

    def test_002_clinic_incident_category_field_name(self):
        self.assertIn("name", self.env["clinic.incident.category"]._fields)

    def test_003_clinic_incident_category_field_type_name(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["name"].type)

    def test_004_clinic_incident_category_field_string_name(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["name"].string)

    def test_005_clinic_incident_category_field_model_name(self):
        self.assertEqual(self.env["clinic.incident.category"]._fields["name"].model_name, "clinic.incident.category")

    def test_006_clinic_incident_category_field_code(self):
        self.assertIn("code", self.env["clinic.incident.category"]._fields)

    def test_007_clinic_incident_category_field_type_code(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["code"].type)

    def test_008_clinic_incident_category_field_string_code(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["code"].string)

    def test_009_clinic_incident_category_field_model_code(self):
        self.assertEqual(self.env["clinic.incident.category"]._fields["code"].model_name, "clinic.incident.category")

    def test_010_clinic_incident_category_field_sequence(self):
        self.assertIn("sequence", self.env["clinic.incident.category"]._fields)

    def test_011_clinic_incident_category_field_type_sequence(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["sequence"].type)

    def test_012_clinic_incident_category_field_string_sequence(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["sequence"].string)

    def test_013_clinic_incident_category_field_model_sequence(self):
        self.assertEqual(self.env["clinic.incident.category"]._fields["sequence"].model_name, "clinic.incident.category")

    def test_014_clinic_incident_category_field_active(self):
        self.assertIn("active", self.env["clinic.incident.category"]._fields)

    def test_015_clinic_incident_category_field_type_active(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["active"].type)

    def test_016_clinic_incident_category_field_string_active(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["active"].string)

    def test_017_clinic_incident_category_field_model_active(self):
        self.assertEqual(self.env["clinic.incident.category"]._fields["active"].model_name, "clinic.incident.category")

    def test_018_clinic_incident_category_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.incident.category"]._fields)

    def test_019_clinic_incident_category_field_type_company_id(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["company_id"].type)

    def test_020_clinic_incident_category_field_string_company_id(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["company_id"].string)

    def test_021_clinic_incident_category_field_model_company_id(self):
        self.assertEqual(self.env["clinic.incident.category"]._fields["company_id"].model_name, "clinic.incident.category")

    def test_022_clinic_incident_category_field_incident_type(self):
        self.assertIn("incident_type", self.env["clinic.incident.category"]._fields)

    def test_023_clinic_incident_category_field_type_incident_type(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["incident_type"].type)

    def test_024_clinic_incident_category_field_string_incident_type(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["incident_type"].string)

    def test_025_clinic_incident_category_field_model_incident_type(self):
        self.assertEqual(self.env["clinic.incident.category"]._fields["incident_type"].model_name, "clinic.incident.category")

    def test_026_clinic_incident_category_field_default_severity(self):
        self.assertIn("default_severity", self.env["clinic.incident.category"]._fields)

    def test_027_clinic_incident_category_field_type_default_severity(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["default_severity"].type)

    def test_028_clinic_incident_category_field_string_default_severity(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["default_severity"].string)

    def test_029_clinic_incident_category_field_model_default_severity(self):
        self.assertEqual(self.env["clinic.incident.category"]._fields["default_severity"].model_name, "clinic.incident.category")

    def test_030_clinic_incident_category_field_requires_investigation(self):
        self.assertIn("requires_investigation", self.env["clinic.incident.category"]._fields)

    def test_031_clinic_incident_category_field_type_requires_investigation(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["requires_investigation"].type)

    def test_032_clinic_incident_category_field_string_requires_investigation(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["requires_investigation"].string)

    def test_033_clinic_incident_category_field_model_requires_investigation(self):
        self.assertEqual(self.env["clinic.incident.category"]._fields["requires_investigation"].model_name, "clinic.incident.category")

    def test_034_clinic_incident_category_field_requires_capa(self):
        self.assertIn("requires_capa", self.env["clinic.incident.category"]._fields)

    def test_035_clinic_incident_category_field_type_requires_capa(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["requires_capa"].type)

    def test_036_clinic_incident_category_field_string_requires_capa(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["requires_capa"].string)

    def test_037_clinic_incident_category_field_model_requires_capa(self):
        self.assertEqual(self.env["clinic.incident.category"]._fields["requires_capa"].model_name, "clinic.incident.category")

    def test_038_clinic_incident_category_field_requires_regulatory_review(self):
        self.assertIn("requires_regulatory_review", self.env["clinic.incident.category"]._fields)

    def test_039_clinic_incident_category_field_type_requires_regulatory_review(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["requires_regulatory_review"].type)

    def test_040_clinic_incident_category_field_string_requires_regulatory_review(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["requires_regulatory_review"].string)

    def test_041_clinic_incident_category_field_model_requires_regulatory_review(self):
        self.assertEqual(self.env["clinic.incident.category"]._fields["requires_regulatory_review"].model_name, "clinic.incident.category")

    def test_042_clinic_incident_category_field_triage_target_hours(self):
        self.assertIn("triage_target_hours", self.env["clinic.incident.category"]._fields)

    def test_043_clinic_incident_category_field_type_triage_target_hours(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["triage_target_hours"].type)

    def test_044_clinic_incident_category_field_string_triage_target_hours(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["triage_target_hours"].string)

    def test_045_clinic_incident_category_field_model_triage_target_hours(self):
        self.assertEqual(self.env["clinic.incident.category"]._fields["triage_target_hours"].model_name, "clinic.incident.category")

    def test_046_clinic_incident_category_field_investigation_target_hours(self):
        self.assertIn("investigation_target_hours", self.env["clinic.incident.category"]._fields)

    def test_047_clinic_incident_category_field_type_investigation_target_hours(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["investigation_target_hours"].type)

    def test_048_clinic_incident_category_field_string_investigation_target_hours(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["investigation_target_hours"].string)

    def test_049_clinic_incident_category_field_model_investigation_target_hours(self):
        self.assertEqual(self.env["clinic.incident.category"]._fields["investigation_target_hours"].model_name, "clinic.incident.category")

    def test_050_clinic_incident_category_field_action_plan_target_hours(self):
        self.assertIn("action_plan_target_hours", self.env["clinic.incident.category"]._fields)

    def test_051_clinic_incident_category_field_type_action_plan_target_hours(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["action_plan_target_hours"].type)

    def test_052_clinic_incident_category_field_string_action_plan_target_hours(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["action_plan_target_hours"].string)

    def test_053_clinic_incident_category_field_model_action_plan_target_hours(self):
        self.assertEqual(self.env["clinic.incident.category"]._fields["action_plan_target_hours"].model_name, "clinic.incident.category")

    def test_054_clinic_incident_category_field_description(self):
        self.assertIn("description", self.env["clinic.incident.category"]._fields)

    def test_055_clinic_incident_category_field_type_description(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["description"].type)

    def test_056_clinic_incident_category_field_string_description(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["description"].string)

    def test_057_clinic_incident_category_field_model_description(self):
        self.assertEqual(self.env["clinic.incident.category"]._fields["description"].model_name, "clinic.incident.category")

    def test_058_clinic_incident_category_field_response_guidance(self):
        self.assertIn("response_guidance", self.env["clinic.incident.category"]._fields)

    def test_059_clinic_incident_category_field_type_response_guidance(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["response_guidance"].type)

    def test_060_clinic_incident_category_field_string_response_guidance(self):
        self.assertTrue(self.env["clinic.incident.category"]._fields["response_guidance"].string)

    def test_061_clinic_incident_category_field_model_response_guidance(self):
        self.assertEqual(self.env["clinic.incident.category"]._fields["response_guidance"].model_name, "clinic.incident.category")

    def test_062_model_clinic_incident(self):
        self.assertIn("clinic.incident", self.env.registry)

    def test_063_clinic_incident_field_name(self):
        self.assertIn("name", self.env["clinic.incident"]._fields)

    def test_064_clinic_incident_field_type_name(self):
        self.assertTrue(self.env["clinic.incident"]._fields["name"].type)

    def test_065_clinic_incident_field_string_name(self):
        self.assertTrue(self.env["clinic.incident"]._fields["name"].string)

    def test_066_clinic_incident_field_model_name(self):
        self.assertEqual(self.env["clinic.incident"]._fields["name"].model_name, "clinic.incident")

    def test_067_clinic_incident_field_title(self):
        self.assertIn("title", self.env["clinic.incident"]._fields)

    def test_068_clinic_incident_field_type_title(self):
        self.assertTrue(self.env["clinic.incident"]._fields["title"].type)

    def test_069_clinic_incident_field_string_title(self):
        self.assertTrue(self.env["clinic.incident"]._fields["title"].string)

    def test_070_clinic_incident_field_model_title(self):
        self.assertEqual(self.env["clinic.incident"]._fields["title"].model_name, "clinic.incident")

    def test_071_clinic_incident_field_active(self):
        self.assertIn("active", self.env["clinic.incident"]._fields)

    def test_072_clinic_incident_field_type_active(self):
        self.assertTrue(self.env["clinic.incident"]._fields["active"].type)

    def test_073_clinic_incident_field_string_active(self):
        self.assertTrue(self.env["clinic.incident"]._fields["active"].string)

    def test_074_clinic_incident_field_model_active(self):
        self.assertEqual(self.env["clinic.incident"]._fields["active"].model_name, "clinic.incident")

    def test_075_clinic_incident_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.incident"]._fields)

    def test_076_clinic_incident_field_type_company_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["company_id"].type)

    def test_077_clinic_incident_field_string_company_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["company_id"].string)

    def test_078_clinic_incident_field_model_company_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["company_id"].model_name, "clinic.incident")

    def test_079_clinic_incident_field_allowed_branch_ids(self):
        self.assertIn("allowed_branch_ids", self.env["clinic.incident"]._fields)

    def test_080_clinic_incident_field_type_allowed_branch_ids(self):
        self.assertTrue(self.env["clinic.incident"]._fields["allowed_branch_ids"].type)

    def test_081_clinic_incident_field_string_allowed_branch_ids(self):
        self.assertTrue(self.env["clinic.incident"]._fields["allowed_branch_ids"].string)

    def test_082_clinic_incident_field_model_allowed_branch_ids(self):
        self.assertEqual(self.env["clinic.incident"]._fields["allowed_branch_ids"].model_name, "clinic.incident")

    def test_083_clinic_incident_field_branch_id(self):
        self.assertIn("branch_id", self.env["clinic.incident"]._fields)

    def test_084_clinic_incident_field_type_branch_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["branch_id"].type)

    def test_085_clinic_incident_field_string_branch_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["branch_id"].string)

    def test_086_clinic_incident_field_model_branch_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["branch_id"].model_name, "clinic.incident")

    def test_087_clinic_incident_field_category_id(self):
        self.assertIn("category_id", self.env["clinic.incident"]._fields)

    def test_088_clinic_incident_field_type_category_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["category_id"].type)

    def test_089_clinic_incident_field_string_category_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["category_id"].string)

    def test_090_clinic_incident_field_model_category_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["category_id"].model_name, "clinic.incident")

    def test_091_clinic_incident_field_incident_type(self):
        self.assertIn("incident_type", self.env["clinic.incident"]._fields)

    def test_092_clinic_incident_field_type_incident_type(self):
        self.assertTrue(self.env["clinic.incident"]._fields["incident_type"].type)

    def test_093_clinic_incident_field_string_incident_type(self):
        self.assertTrue(self.env["clinic.incident"]._fields["incident_type"].string)

    def test_094_clinic_incident_field_model_incident_type(self):
        self.assertEqual(self.env["clinic.incident"]._fields["incident_type"].model_name, "clinic.incident")

    def test_095_clinic_incident_field_classification(self):
        self.assertIn("classification", self.env["clinic.incident"]._fields)

    def test_096_clinic_incident_field_type_classification(self):
        self.assertTrue(self.env["clinic.incident"]._fields["classification"].type)

    def test_097_clinic_incident_field_string_classification(self):
        self.assertTrue(self.env["clinic.incident"]._fields["classification"].string)

    def test_098_clinic_incident_field_model_classification(self):
        self.assertEqual(self.env["clinic.incident"]._fields["classification"].model_name, "clinic.incident")

    def test_099_clinic_incident_field_severity(self):
        self.assertIn("severity", self.env["clinic.incident"]._fields)

    def test_100_clinic_incident_field_type_severity(self):
        self.assertTrue(self.env["clinic.incident"]._fields["severity"].type)

    def test_101_clinic_incident_field_string_severity(self):
        self.assertTrue(self.env["clinic.incident"]._fields["severity"].string)

    def test_102_clinic_incident_field_model_severity(self):
        self.assertEqual(self.env["clinic.incident"]._fields["severity"].model_name, "clinic.incident")

    def test_103_clinic_incident_field_harm_level(self):
        self.assertIn("harm_level", self.env["clinic.incident"]._fields)

    def test_104_clinic_incident_field_type_harm_level(self):
        self.assertTrue(self.env["clinic.incident"]._fields["harm_level"].type)

    def test_105_clinic_incident_field_string_harm_level(self):
        self.assertTrue(self.env["clinic.incident"]._fields["harm_level"].string)

    def test_106_clinic_incident_field_model_harm_level(self):
        self.assertEqual(self.env["clinic.incident"]._fields["harm_level"].model_name, "clinic.incident")

    def test_107_clinic_incident_field_recurrence_risk(self):
        self.assertIn("recurrence_risk", self.env["clinic.incident"]._fields)

    def test_108_clinic_incident_field_type_recurrence_risk(self):
        self.assertTrue(self.env["clinic.incident"]._fields["recurrence_risk"].type)

    def test_109_clinic_incident_field_string_recurrence_risk(self):
        self.assertTrue(self.env["clinic.incident"]._fields["recurrence_risk"].string)

    def test_110_clinic_incident_field_model_recurrence_risk(self):
        self.assertEqual(self.env["clinic.incident"]._fields["recurrence_risk"].model_name, "clinic.incident")

    def test_111_clinic_incident_field_state(self):
        self.assertIn("state", self.env["clinic.incident"]._fields)

    def test_112_clinic_incident_field_type_state(self):
        self.assertTrue(self.env["clinic.incident"]._fields["state"].type)

    def test_113_clinic_incident_field_string_state(self):
        self.assertTrue(self.env["clinic.incident"]._fields["state"].string)

    def test_114_clinic_incident_field_model_state(self):
        self.assertEqual(self.env["clinic.incident"]._fields["state"].model_name, "clinic.incident")

    def test_115_clinic_incident_field_occurred_at(self):
        self.assertIn("occurred_at", self.env["clinic.incident"]._fields)

    def test_116_clinic_incident_field_type_occurred_at(self):
        self.assertTrue(self.env["clinic.incident"]._fields["occurred_at"].type)

    def test_117_clinic_incident_field_string_occurred_at(self):
        self.assertTrue(self.env["clinic.incident"]._fields["occurred_at"].string)

    def test_118_clinic_incident_field_model_occurred_at(self):
        self.assertEqual(self.env["clinic.incident"]._fields["occurred_at"].model_name, "clinic.incident")

    def test_119_clinic_incident_field_detected_at(self):
        self.assertIn("detected_at", self.env["clinic.incident"]._fields)

    def test_120_clinic_incident_field_type_detected_at(self):
        self.assertTrue(self.env["clinic.incident"]._fields["detected_at"].type)

    def test_121_clinic_incident_field_string_detected_at(self):
        self.assertTrue(self.env["clinic.incident"]._fields["detected_at"].string)

    def test_122_clinic_incident_field_model_detected_at(self):
        self.assertEqual(self.env["clinic.incident"]._fields["detected_at"].model_name, "clinic.incident")

    def test_123_clinic_incident_field_reported_at(self):
        self.assertIn("reported_at", self.env["clinic.incident"]._fields)

    def test_124_clinic_incident_field_type_reported_at(self):
        self.assertTrue(self.env["clinic.incident"]._fields["reported_at"].type)

    def test_125_clinic_incident_field_string_reported_at(self):
        self.assertTrue(self.env["clinic.incident"]._fields["reported_at"].string)

    def test_126_clinic_incident_field_model_reported_at(self):
        self.assertEqual(self.env["clinic.incident"]._fields["reported_at"].model_name, "clinic.incident")

    def test_127_clinic_incident_field_reported_by_user_id(self):
        self.assertIn("reported_by_user_id", self.env["clinic.incident"]._fields)

    def test_128_clinic_incident_field_type_reported_by_user_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["reported_by_user_id"].type)

    def test_129_clinic_incident_field_string_reported_by_user_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["reported_by_user_id"].string)

    def test_130_clinic_incident_field_model_reported_by_user_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["reported_by_user_id"].model_name, "clinic.incident")

    def test_131_clinic_incident_field_reported_by_staff_id(self):
        self.assertIn("reported_by_staff_id", self.env["clinic.incident"]._fields)

    def test_132_clinic_incident_field_type_reported_by_staff_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["reported_by_staff_id"].type)

    def test_133_clinic_incident_field_string_reported_by_staff_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["reported_by_staff_id"].string)

    def test_134_clinic_incident_field_model_reported_by_staff_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["reported_by_staff_id"].model_name, "clinic.incident")

    def test_135_clinic_incident_field_case_owner_id(self):
        self.assertIn("case_owner_id", self.env["clinic.incident"]._fields)

    def test_136_clinic_incident_field_type_case_owner_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["case_owner_id"].type)

    def test_137_clinic_incident_field_string_case_owner_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["case_owner_id"].string)

    def test_138_clinic_incident_field_model_case_owner_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["case_owner_id"].model_name, "clinic.incident")

    def test_139_clinic_incident_field_reviewer_id(self):
        self.assertIn("reviewer_id", self.env["clinic.incident"]._fields)

    def test_140_clinic_incident_field_type_reviewer_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["reviewer_id"].type)

    def test_141_clinic_incident_field_string_reviewer_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["reviewer_id"].string)

    def test_142_clinic_incident_field_model_reviewer_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["reviewer_id"].model_name, "clinic.incident")

    def test_143_clinic_incident_field_patient_id(self):
        self.assertIn("patient_id", self.env["clinic.incident"]._fields)

    def test_144_clinic_incident_field_type_patient_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["patient_id"].type)

    def test_145_clinic_incident_field_string_patient_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["patient_id"].string)

    def test_146_clinic_incident_field_model_patient_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["patient_id"].model_name, "clinic.incident")

    def test_147_clinic_incident_field_partner_id(self):
        self.assertIn("partner_id", self.env["clinic.incident"]._fields)

    def test_148_clinic_incident_field_type_partner_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["partner_id"].type)

    def test_149_clinic_incident_field_string_partner_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["partner_id"].string)

    def test_150_clinic_incident_field_model_partner_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["partner_id"].model_name, "clinic.incident")

    def test_151_clinic_incident_field_doctor_id(self):
        self.assertIn("doctor_id", self.env["clinic.incident"]._fields)

    def test_152_clinic_incident_field_type_doctor_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["doctor_id"].type)

    def test_153_clinic_incident_field_string_doctor_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["doctor_id"].string)

    def test_154_clinic_incident_field_model_doctor_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["doctor_id"].model_name, "clinic.incident")

    def test_155_clinic_incident_field_involved_staff_ids(self):
        self.assertIn("involved_staff_ids", self.env["clinic.incident"]._fields)

    def test_156_clinic_incident_field_type_involved_staff_ids(self):
        self.assertTrue(self.env["clinic.incident"]._fields["involved_staff_ids"].type)

    def test_157_clinic_incident_field_string_involved_staff_ids(self):
        self.assertTrue(self.env["clinic.incident"]._fields["involved_staff_ids"].string)

    def test_158_clinic_incident_field_model_involved_staff_ids(self):
        self.assertEqual(self.env["clinic.incident"]._fields["involved_staff_ids"].model_name, "clinic.incident")

    def test_159_clinic_incident_field_room_id(self):
        self.assertIn("room_id", self.env["clinic.incident"]._fields)

    def test_160_clinic_incident_field_type_room_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["room_id"].type)

    def test_161_clinic_incident_field_string_room_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["room_id"].string)

    def test_162_clinic_incident_field_model_room_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["room_id"].model_name, "clinic.incident")

    def test_163_clinic_incident_field_encounter_id(self):
        self.assertIn("encounter_id", self.env["clinic.incident"]._fields)

    def test_164_clinic_incident_field_type_encounter_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["encounter_id"].type)

    def test_165_clinic_incident_field_string_encounter_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["encounter_id"].string)

    def test_166_clinic_incident_field_model_encounter_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["encounter_id"].model_name, "clinic.incident")

    def test_167_clinic_incident_field_adverse_event_id(self):
        self.assertIn("adverse_event_id", self.env["clinic.incident"]._fields)

    def test_168_clinic_incident_field_type_adverse_event_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["adverse_event_id"].type)

    def test_169_clinic_incident_field_string_adverse_event_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["adverse_event_id"].string)

    def test_170_clinic_incident_field_model_adverse_event_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["adverse_event_id"].model_name, "clinic.incident")

    def test_171_clinic_incident_field_booking_id(self):
        self.assertIn("booking_id", self.env["clinic.incident"]._fields)

    def test_172_clinic_incident_field_type_booking_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["booking_id"].type)

    def test_173_clinic_incident_field_string_booking_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["booking_id"].string)

    def test_174_clinic_incident_field_model_booking_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["booking_id"].model_name, "clinic.incident")

    def test_175_clinic_incident_field_queue_id(self):
        self.assertIn("queue_id", self.env["clinic.incident"]._fields)

    def test_176_clinic_incident_field_type_queue_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["queue_id"].type)

    def test_177_clinic_incident_field_string_queue_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["queue_id"].string)

    def test_178_clinic_incident_field_model_queue_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["queue_id"].model_name, "clinic.incident")

    def test_179_clinic_incident_field_emar_administration_id(self):
        self.assertIn("emar_administration_id", self.env["clinic.incident"]._fields)

    def test_180_clinic_incident_field_type_emar_administration_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["emar_administration_id"].type)

    def test_181_clinic_incident_field_string_emar_administration_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["emar_administration_id"].string)

    def test_182_clinic_incident_field_model_emar_administration_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["emar_administration_id"].model_name, "clinic.incident")

    def test_183_clinic_incident_field_telemedicine_session_id(self):
        self.assertIn("telemedicine_session_id", self.env["clinic.incident"]._fields)

    def test_184_clinic_incident_field_type_telemedicine_session_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["telemedicine_session_id"].type)

    def test_185_clinic_incident_field_string_telemedicine_session_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["telemedicine_session_id"].string)

    def test_186_clinic_incident_field_model_telemedicine_session_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["telemedicine_session_id"].model_name, "clinic.incident")

    def test_187_clinic_incident_field_telemedicine_thread_id(self):
        self.assertIn("telemedicine_thread_id", self.env["clinic.incident"]._fields)

    def test_188_clinic_incident_field_type_telemedicine_thread_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["telemedicine_thread_id"].type)

    def test_189_clinic_incident_field_string_telemedicine_thread_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["telemedicine_thread_id"].string)

    def test_190_clinic_incident_field_model_telemedicine_thread_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["telemedicine_thread_id"].model_name, "clinic.incident")

    def test_191_clinic_incident_field_feedback_escalation_id(self):
        self.assertIn("feedback_escalation_id", self.env["clinic.incident"]._fields)

    def test_192_clinic_incident_field_type_feedback_escalation_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["feedback_escalation_id"].type)

    def test_193_clinic_incident_field_string_feedback_escalation_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["feedback_escalation_id"].string)

    def test_194_clinic_incident_field_model_feedback_escalation_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["feedback_escalation_id"].model_name, "clinic.incident")

    def test_195_clinic_incident_field_description(self):
        self.assertIn("description", self.env["clinic.incident"]._fields)

    def test_196_clinic_incident_field_type_description(self):
        self.assertTrue(self.env["clinic.incident"]._fields["description"].type)

    def test_197_clinic_incident_field_string_description(self):
        self.assertTrue(self.env["clinic.incident"]._fields["description"].string)

    def test_198_clinic_incident_field_model_description(self):
        self.assertEqual(self.env["clinic.incident"]._fields["description"].model_name, "clinic.incident")

    def test_199_clinic_incident_field_immediate_action(self):
        self.assertIn("immediate_action", self.env["clinic.incident"]._fields)

    def test_200_clinic_incident_field_type_immediate_action(self):
        self.assertTrue(self.env["clinic.incident"]._fields["immediate_action"].type)

    def test_201_clinic_incident_field_string_immediate_action(self):
        self.assertTrue(self.env["clinic.incident"]._fields["immediate_action"].string)

    def test_202_clinic_incident_field_model_immediate_action(self):
        self.assertEqual(self.env["clinic.incident"]._fields["immediate_action"].model_name, "clinic.incident")

    def test_203_clinic_incident_field_patient_impact(self):
        self.assertIn("patient_impact", self.env["clinic.incident"]._fields)

    def test_204_clinic_incident_field_type_patient_impact(self):
        self.assertTrue(self.env["clinic.incident"]._fields["patient_impact"].type)

    def test_205_clinic_incident_field_string_patient_impact(self):
        self.assertTrue(self.env["clinic.incident"]._fields["patient_impact"].string)

    def test_206_clinic_incident_field_model_patient_impact(self):
        self.assertEqual(self.env["clinic.incident"]._fields["patient_impact"].model_name, "clinic.incident")

    def test_207_clinic_incident_field_reporter_note(self):
        self.assertIn("reporter_note", self.env["clinic.incident"]._fields)

    def test_208_clinic_incident_field_type_reporter_note(self):
        self.assertTrue(self.env["clinic.incident"]._fields["reporter_note"].type)

    def test_209_clinic_incident_field_string_reporter_note(self):
        self.assertTrue(self.env["clinic.incident"]._fields["reporter_note"].string)

    def test_210_clinic_incident_field_model_reporter_note(self):
        self.assertEqual(self.env["clinic.incident"]._fields["reporter_note"].model_name, "clinic.incident")

    def test_211_clinic_incident_field_root_cause_summary(self):
        self.assertIn("root_cause_summary", self.env["clinic.incident"]._fields)

    def test_212_clinic_incident_field_type_root_cause_summary(self):
        self.assertTrue(self.env["clinic.incident"]._fields["root_cause_summary"].type)

    def test_213_clinic_incident_field_string_root_cause_summary(self):
        self.assertTrue(self.env["clinic.incident"]._fields["root_cause_summary"].string)

    def test_214_clinic_incident_field_model_root_cause_summary(self):
        self.assertEqual(self.env["clinic.incident"]._fields["root_cause_summary"].model_name, "clinic.incident")

    def test_215_clinic_incident_field_resolution_summary(self):
        self.assertIn("resolution_summary", self.env["clinic.incident"]._fields)

    def test_216_clinic_incident_field_type_resolution_summary(self):
        self.assertTrue(self.env["clinic.incident"]._fields["resolution_summary"].type)

    def test_217_clinic_incident_field_string_resolution_summary(self):
        self.assertTrue(self.env["clinic.incident"]._fields["resolution_summary"].string)

    def test_218_clinic_incident_field_model_resolution_summary(self):
        self.assertEqual(self.env["clinic.incident"]._fields["resolution_summary"].model_name, "clinic.incident")

    def test_219_clinic_incident_field_regulatory_required(self):
        self.assertIn("regulatory_required", self.env["clinic.incident"]._fields)

    def test_220_clinic_incident_field_type_regulatory_required(self):
        self.assertTrue(self.env["clinic.incident"]._fields["regulatory_required"].type)

    def test_221_clinic_incident_field_string_regulatory_required(self):
        self.assertTrue(self.env["clinic.incident"]._fields["regulatory_required"].string)

    def test_222_clinic_incident_field_model_regulatory_required(self):
        self.assertEqual(self.env["clinic.incident"]._fields["regulatory_required"].model_name, "clinic.incident")

    def test_223_clinic_incident_field_reportability_reviewed(self):
        self.assertIn("reportability_reviewed", self.env["clinic.incident"]._fields)

    def test_224_clinic_incident_field_type_reportability_reviewed(self):
        self.assertTrue(self.env["clinic.incident"]._fields["reportability_reviewed"].type)

    def test_225_clinic_incident_field_string_reportability_reviewed(self):
        self.assertTrue(self.env["clinic.incident"]._fields["reportability_reviewed"].string)

    def test_226_clinic_incident_field_model_reportability_reviewed(self):
        self.assertEqual(self.env["clinic.incident"]._fields["reportability_reviewed"].model_name, "clinic.incident")

    def test_227_clinic_incident_field_regulator_body(self):
        self.assertIn("regulator_body", self.env["clinic.incident"]._fields)

    def test_228_clinic_incident_field_type_regulator_body(self):
        self.assertTrue(self.env["clinic.incident"]._fields["regulator_body"].type)

    def test_229_clinic_incident_field_string_regulator_body(self):
        self.assertTrue(self.env["clinic.incident"]._fields["regulator_body"].string)

    def test_230_clinic_incident_field_model_regulator_body(self):
        self.assertEqual(self.env["clinic.incident"]._fields["regulator_body"].model_name, "clinic.incident")

    def test_231_clinic_incident_field_regulator_reference(self):
        self.assertIn("regulator_reference", self.env["clinic.incident"]._fields)

    def test_232_clinic_incident_field_type_regulator_reference(self):
        self.assertTrue(self.env["clinic.incident"]._fields["regulator_reference"].type)

    def test_233_clinic_incident_field_string_regulator_reference(self):
        self.assertTrue(self.env["clinic.incident"]._fields["regulator_reference"].string)

    def test_234_clinic_incident_field_model_regulator_reference(self):
        self.assertEqual(self.env["clinic.incident"]._fields["regulator_reference"].model_name, "clinic.incident")

    def test_235_clinic_incident_field_regulator_reported_at(self):
        self.assertIn("regulator_reported_at", self.env["clinic.incident"]._fields)

    def test_236_clinic_incident_field_type_regulator_reported_at(self):
        self.assertTrue(self.env["clinic.incident"]._fields["regulator_reported_at"].type)

    def test_237_clinic_incident_field_string_regulator_reported_at(self):
        self.assertTrue(self.env["clinic.incident"]._fields["regulator_reported_at"].string)

    def test_238_clinic_incident_field_model_regulator_reported_at(self):
        self.assertEqual(self.env["clinic.incident"]._fields["regulator_reported_at"].model_name, "clinic.incident")

    def test_239_clinic_incident_field_triage_due_at(self):
        self.assertIn("triage_due_at", self.env["clinic.incident"]._fields)

    def test_240_clinic_incident_field_type_triage_due_at(self):
        self.assertTrue(self.env["clinic.incident"]._fields["triage_due_at"].type)

    def test_241_clinic_incident_field_string_triage_due_at(self):
        self.assertTrue(self.env["clinic.incident"]._fields["triage_due_at"].string)

    def test_242_clinic_incident_field_model_triage_due_at(self):
        self.assertEqual(self.env["clinic.incident"]._fields["triage_due_at"].model_name, "clinic.incident")

    def test_243_clinic_incident_field_investigation_due_at(self):
        self.assertIn("investigation_due_at", self.env["clinic.incident"]._fields)

    def test_244_clinic_incident_field_type_investigation_due_at(self):
        self.assertTrue(self.env["clinic.incident"]._fields["investigation_due_at"].type)

    def test_245_clinic_incident_field_string_investigation_due_at(self):
        self.assertTrue(self.env["clinic.incident"]._fields["investigation_due_at"].string)

    def test_246_clinic_incident_field_model_investigation_due_at(self):
        self.assertEqual(self.env["clinic.incident"]._fields["investigation_due_at"].model_name, "clinic.incident")

    def test_247_clinic_incident_field_action_plan_due_at(self):
        self.assertIn("action_plan_due_at", self.env["clinic.incident"]._fields)

    def test_248_clinic_incident_field_type_action_plan_due_at(self):
        self.assertTrue(self.env["clinic.incident"]._fields["action_plan_due_at"].type)

    def test_249_clinic_incident_field_string_action_plan_due_at(self):
        self.assertTrue(self.env["clinic.incident"]._fields["action_plan_due_at"].string)

    def test_250_clinic_incident_field_model_action_plan_due_at(self):
        self.assertEqual(self.env["clinic.incident"]._fields["action_plan_due_at"].model_name, "clinic.incident")

    def test_251_clinic_incident_field_closed_at(self):
        self.assertIn("closed_at", self.env["clinic.incident"]._fields)

    def test_252_clinic_incident_field_type_closed_at(self):
        self.assertTrue(self.env["clinic.incident"]._fields["closed_at"].type)

    def test_253_clinic_incident_field_string_closed_at(self):
        self.assertTrue(self.env["clinic.incident"]._fields["closed_at"].string)

    def test_254_clinic_incident_field_model_closed_at(self):
        self.assertEqual(self.env["clinic.incident"]._fields["closed_at"].model_name, "clinic.incident")

    def test_255_clinic_incident_field_closed_by_id(self):
        self.assertIn("closed_by_id", self.env["clinic.incident"]._fields)

    def test_256_clinic_incident_field_type_closed_by_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["closed_by_id"].type)

    def test_257_clinic_incident_field_string_closed_by_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["closed_by_id"].string)

    def test_258_clinic_incident_field_model_closed_by_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["closed_by_id"].model_name, "clinic.incident")

    def test_259_clinic_incident_field_cancellation_reason(self):
        self.assertIn("cancellation_reason", self.env["clinic.incident"]._fields)

    def test_260_clinic_incident_field_type_cancellation_reason(self):
        self.assertTrue(self.env["clinic.incident"]._fields["cancellation_reason"].type)

    def test_261_clinic_incident_field_string_cancellation_reason(self):
        self.assertTrue(self.env["clinic.incident"]._fields["cancellation_reason"].string)

    def test_262_clinic_incident_field_model_cancellation_reason(self):
        self.assertEqual(self.env["clinic.incident"]._fields["cancellation_reason"].model_name, "clinic.incident")

    def test_263_clinic_incident_field_investigation_ids(self):
        self.assertIn("investigation_ids", self.env["clinic.incident"]._fields)

    def test_264_clinic_incident_field_type_investigation_ids(self):
        self.assertTrue(self.env["clinic.incident"]._fields["investigation_ids"].type)

    def test_265_clinic_incident_field_string_investigation_ids(self):
        self.assertTrue(self.env["clinic.incident"]._fields["investigation_ids"].string)

    def test_266_clinic_incident_field_model_investigation_ids(self):
        self.assertEqual(self.env["clinic.incident"]._fields["investigation_ids"].model_name, "clinic.incident")

    def test_267_clinic_incident_field_action_ids(self):
        self.assertIn("action_ids", self.env["clinic.incident"]._fields)

    def test_268_clinic_incident_field_type_action_ids(self):
        self.assertTrue(self.env["clinic.incident"]._fields["action_ids"].type)

    def test_269_clinic_incident_field_string_action_ids(self):
        self.assertTrue(self.env["clinic.incident"]._fields["action_ids"].string)

    def test_270_clinic_incident_field_model_action_ids(self):
        self.assertEqual(self.env["clinic.incident"]._fields["action_ids"].model_name, "clinic.incident")

    def test_271_clinic_incident_field_timeline_ids(self):
        self.assertIn("timeline_ids", self.env["clinic.incident"]._fields)

    def test_272_clinic_incident_field_type_timeline_ids(self):
        self.assertTrue(self.env["clinic.incident"]._fields["timeline_ids"].type)

    def test_273_clinic_incident_field_string_timeline_ids(self):
        self.assertTrue(self.env["clinic.incident"]._fields["timeline_ids"].string)

    def test_274_clinic_incident_field_model_timeline_ids(self):
        self.assertEqual(self.env["clinic.incident"]._fields["timeline_ids"].model_name, "clinic.incident")

    def test_275_clinic_incident_field_investigation_count(self):
        self.assertIn("investigation_count", self.env["clinic.incident"]._fields)

    def test_276_clinic_incident_field_type_investigation_count(self):
        self.assertTrue(self.env["clinic.incident"]._fields["investigation_count"].type)

    def test_277_clinic_incident_field_string_investigation_count(self):
        self.assertTrue(self.env["clinic.incident"]._fields["investigation_count"].string)

    def test_278_clinic_incident_field_model_investigation_count(self):
        self.assertEqual(self.env["clinic.incident"]._fields["investigation_count"].model_name, "clinic.incident")

    def test_279_clinic_incident_field_completed_investigation_count(self):
        self.assertIn("completed_investigation_count", self.env["clinic.incident"]._fields)

    def test_280_clinic_incident_field_type_completed_investigation_count(self):
        self.assertTrue(self.env["clinic.incident"]._fields["completed_investigation_count"].type)

    def test_281_clinic_incident_field_string_completed_investigation_count(self):
        self.assertTrue(self.env["clinic.incident"]._fields["completed_investigation_count"].string)

    def test_282_clinic_incident_field_model_completed_investigation_count(self):
        self.assertEqual(self.env["clinic.incident"]._fields["completed_investigation_count"].model_name, "clinic.incident")

    def test_283_clinic_incident_field_action_count(self):
        self.assertIn("action_count", self.env["clinic.incident"]._fields)

    def test_284_clinic_incident_field_type_action_count(self):
        self.assertTrue(self.env["clinic.incident"]._fields["action_count"].type)

    def test_285_clinic_incident_field_string_action_count(self):
        self.assertTrue(self.env["clinic.incident"]._fields["action_count"].string)

    def test_286_clinic_incident_field_model_action_count(self):
        self.assertEqual(self.env["clinic.incident"]._fields["action_count"].model_name, "clinic.incident")

    def test_287_clinic_incident_field_open_action_count(self):
        self.assertIn("open_action_count", self.env["clinic.incident"]._fields)

    def test_288_clinic_incident_field_type_open_action_count(self):
        self.assertTrue(self.env["clinic.incident"]._fields["open_action_count"].type)

    def test_289_clinic_incident_field_string_open_action_count(self):
        self.assertTrue(self.env["clinic.incident"]._fields["open_action_count"].string)

    def test_290_clinic_incident_field_model_open_action_count(self):
        self.assertEqual(self.env["clinic.incident"]._fields["open_action_count"].model_name, "clinic.incident")

    def test_291_clinic_incident_field_timeline_count(self):
        self.assertIn("timeline_count", self.env["clinic.incident"]._fields)

    def test_292_clinic_incident_field_type_timeline_count(self):
        self.assertTrue(self.env["clinic.incident"]._fields["timeline_count"].type)

    def test_293_clinic_incident_field_string_timeline_count(self):
        self.assertTrue(self.env["clinic.incident"]._fields["timeline_count"].string)

    def test_294_clinic_incident_field_model_timeline_count(self):
        self.assertEqual(self.env["clinic.incident"]._fields["timeline_count"].model_name, "clinic.incident")

    def test_295_clinic_incident_field_is_overdue(self):
        self.assertIn("is_overdue", self.env["clinic.incident"]._fields)

    def test_296_clinic_incident_field_type_is_overdue(self):
        self.assertTrue(self.env["clinic.incident"]._fields["is_overdue"].type)

    def test_297_clinic_incident_field_string_is_overdue(self):
        self.assertTrue(self.env["clinic.incident"]._fields["is_overdue"].string)

    def test_298_clinic_incident_field_model_is_overdue(self):
        self.assertEqual(self.env["clinic.incident"]._fields["is_overdue"].model_name, "clinic.incident")

    def test_299_clinic_incident_field_is_serious(self):
        self.assertIn("is_serious", self.env["clinic.incident"]._fields)

    def test_300_clinic_incident_field_type_is_serious(self):
        self.assertTrue(self.env["clinic.incident"]._fields["is_serious"].type)

    def test_301_clinic_incident_field_string_is_serious(self):
        self.assertTrue(self.env["clinic.incident"]._fields["is_serious"].string)

    def test_302_clinic_incident_field_model_is_serious(self):
        self.assertEqual(self.env["clinic.incident"]._fields["is_serious"].model_name, "clinic.incident")

    def test_303_clinic_incident_field_needs_regulatory_review(self):
        self.assertIn("needs_regulatory_review", self.env["clinic.incident"]._fields)

    def test_304_clinic_incident_field_type_needs_regulatory_review(self):
        self.assertTrue(self.env["clinic.incident"]._fields["needs_regulatory_review"].type)

    def test_305_clinic_incident_field_string_needs_regulatory_review(self):
        self.assertTrue(self.env["clinic.incident"]._fields["needs_regulatory_review"].string)

    def test_306_clinic_incident_field_model_needs_regulatory_review(self):
        self.assertEqual(self.env["clinic.incident"]._fields["needs_regulatory_review"].model_name, "clinic.incident")

    def test_307_model_clinic_incident_investigation(self):
        self.assertIn("clinic.incident.investigation", self.env.registry)

    def test_308_clinic_incident_investigation_field_name(self):
        self.assertIn("name", self.env["clinic.incident.investigation"]._fields)

    def test_309_clinic_incident_investigation_field_type_name(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["name"].type)

    def test_310_clinic_incident_investigation_field_string_name(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["name"].string)

    def test_311_clinic_incident_investigation_field_model_name(self):
        self.assertEqual(self.env["clinic.incident.investigation"]._fields["name"].model_name, "clinic.incident.investigation")

    def test_312_clinic_incident_investigation_field_incident_id(self):
        self.assertIn("incident_id", self.env["clinic.incident.investigation"]._fields)

    def test_313_clinic_incident_investigation_field_type_incident_id(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["incident_id"].type)

    def test_314_clinic_incident_investigation_field_string_incident_id(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["incident_id"].string)

    def test_315_clinic_incident_investigation_field_model_incident_id(self):
        self.assertEqual(self.env["clinic.incident.investigation"]._fields["incident_id"].model_name, "clinic.incident.investigation")

    def test_316_clinic_incident_investigation_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.incident.investigation"]._fields)

    def test_317_clinic_incident_investigation_field_type_company_id(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["company_id"].type)

    def test_318_clinic_incident_investigation_field_string_company_id(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["company_id"].string)

    def test_319_clinic_incident_investigation_field_model_company_id(self):
        self.assertEqual(self.env["clinic.incident.investigation"]._fields["company_id"].model_name, "clinic.incident.investigation")

    def test_320_clinic_incident_investigation_field_branch_id(self):
        self.assertIn("branch_id", self.env["clinic.incident.investigation"]._fields)

    def test_321_clinic_incident_investigation_field_type_branch_id(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["branch_id"].type)

    def test_322_clinic_incident_investigation_field_string_branch_id(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["branch_id"].string)

    def test_323_clinic_incident_investigation_field_model_branch_id(self):
        self.assertEqual(self.env["clinic.incident.investigation"]._fields["branch_id"].model_name, "clinic.incident.investigation")

    def test_324_clinic_incident_investigation_field_patient_id(self):
        self.assertIn("patient_id", self.env["clinic.incident.investigation"]._fields)

    def test_325_clinic_incident_investigation_field_type_patient_id(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["patient_id"].type)

    def test_326_clinic_incident_investigation_field_string_patient_id(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["patient_id"].string)

    def test_327_clinic_incident_investigation_field_model_patient_id(self):
        self.assertEqual(self.env["clinic.incident.investigation"]._fields["patient_id"].model_name, "clinic.incident.investigation")

    def test_328_clinic_incident_investigation_field_methodology(self):
        self.assertIn("methodology", self.env["clinic.incident.investigation"]._fields)

    def test_329_clinic_incident_investigation_field_type_methodology(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["methodology"].type)

    def test_330_clinic_incident_investigation_field_string_methodology(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["methodology"].string)

    def test_331_clinic_incident_investigation_field_model_methodology(self):
        self.assertEqual(self.env["clinic.incident.investigation"]._fields["methodology"].model_name, "clinic.incident.investigation")

    def test_332_clinic_incident_investigation_field_state(self):
        self.assertIn("state", self.env["clinic.incident.investigation"]._fields)

    def test_333_clinic_incident_investigation_field_type_state(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["state"].type)

    def test_334_clinic_incident_investigation_field_string_state(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["state"].string)

    def test_335_clinic_incident_investigation_field_model_state(self):
        self.assertEqual(self.env["clinic.incident.investigation"]._fields["state"].model_name, "clinic.incident.investigation")

    def test_336_clinic_incident_investigation_field_lead_user_id(self):
        self.assertIn("lead_user_id", self.env["clinic.incident.investigation"]._fields)

    def test_337_clinic_incident_investigation_field_type_lead_user_id(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["lead_user_id"].type)

    def test_338_clinic_incident_investigation_field_string_lead_user_id(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["lead_user_id"].string)

    def test_339_clinic_incident_investigation_field_model_lead_user_id(self):
        self.assertEqual(self.env["clinic.incident.investigation"]._fields["lead_user_id"].model_name, "clinic.incident.investigation")

    def test_340_clinic_incident_investigation_field_participant_user_ids(self):
        self.assertIn("participant_user_ids", self.env["clinic.incident.investigation"]._fields)

    def test_341_clinic_incident_investigation_field_type_participant_user_ids(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["participant_user_ids"].type)

    def test_342_clinic_incident_investigation_field_string_participant_user_ids(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["participant_user_ids"].string)

    def test_343_clinic_incident_investigation_field_model_participant_user_ids(self):
        self.assertEqual(self.env["clinic.incident.investigation"]._fields["participant_user_ids"].model_name, "clinic.incident.investigation")

    def test_344_clinic_incident_investigation_field_started_at(self):
        self.assertIn("started_at", self.env["clinic.incident.investigation"]._fields)

    def test_345_clinic_incident_investigation_field_type_started_at(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["started_at"].type)

    def test_346_clinic_incident_investigation_field_string_started_at(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["started_at"].string)

    def test_347_clinic_incident_investigation_field_model_started_at(self):
        self.assertEqual(self.env["clinic.incident.investigation"]._fields["started_at"].model_name, "clinic.incident.investigation")

    def test_348_clinic_incident_investigation_field_completed_at(self):
        self.assertIn("completed_at", self.env["clinic.incident.investigation"]._fields)

    def test_349_clinic_incident_investigation_field_type_completed_at(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["completed_at"].type)

    def test_350_clinic_incident_investigation_field_string_completed_at(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["completed_at"].string)

    def test_351_clinic_incident_investigation_field_model_completed_at(self):
        self.assertEqual(self.env["clinic.incident.investigation"]._fields["completed_at"].model_name, "clinic.incident.investigation")

    def test_352_clinic_incident_investigation_field_scope(self):
        self.assertIn("scope", self.env["clinic.incident.investigation"]._fields)

    def test_353_clinic_incident_investigation_field_type_scope(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["scope"].type)

    def test_354_clinic_incident_investigation_field_string_scope(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["scope"].string)

    def test_355_clinic_incident_investigation_field_model_scope(self):
        self.assertEqual(self.env["clinic.incident.investigation"]._fields["scope"].model_name, "clinic.incident.investigation")

    def test_356_clinic_incident_investigation_field_evidence_summary(self):
        self.assertIn("evidence_summary", self.env["clinic.incident.investigation"]._fields)

    def test_357_clinic_incident_investigation_field_type_evidence_summary(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["evidence_summary"].type)

    def test_358_clinic_incident_investigation_field_string_evidence_summary(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["evidence_summary"].string)

    def test_359_clinic_incident_investigation_field_model_evidence_summary(self):
        self.assertEqual(self.env["clinic.incident.investigation"]._fields["evidence_summary"].model_name, "clinic.incident.investigation")

    def test_360_clinic_incident_investigation_field_chronology(self):
        self.assertIn("chronology", self.env["clinic.incident.investigation"]._fields)

    def test_361_clinic_incident_investigation_field_type_chronology(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["chronology"].type)

    def test_362_clinic_incident_investigation_field_string_chronology(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["chronology"].string)

    def test_363_clinic_incident_investigation_field_model_chronology(self):
        self.assertEqual(self.env["clinic.incident.investigation"]._fields["chronology"].model_name, "clinic.incident.investigation")

    def test_364_clinic_incident_investigation_field_five_whys(self):
        self.assertIn("five_whys", self.env["clinic.incident.investigation"]._fields)

    def test_365_clinic_incident_investigation_field_type_five_whys(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["five_whys"].type)

    def test_366_clinic_incident_investigation_field_string_five_whys(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["five_whys"].string)

    def test_367_clinic_incident_investigation_field_model_five_whys(self):
        self.assertEqual(self.env["clinic.incident.investigation"]._fields["five_whys"].model_name, "clinic.incident.investigation")

    def test_368_clinic_incident_investigation_field_contributing_factors(self):
        self.assertIn("contributing_factors", self.env["clinic.incident.investigation"]._fields)

    def test_369_clinic_incident_investigation_field_type_contributing_factors(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["contributing_factors"].type)

    def test_370_clinic_incident_investigation_field_string_contributing_factors(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["contributing_factors"].string)

    def test_371_clinic_incident_investigation_field_model_contributing_factors(self):
        self.assertEqual(self.env["clinic.incident.investigation"]._fields["contributing_factors"].model_name, "clinic.incident.investigation")

    def test_372_clinic_incident_investigation_field_root_cause(self):
        self.assertIn("root_cause", self.env["clinic.incident.investigation"]._fields)

    def test_373_clinic_incident_investigation_field_type_root_cause(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["root_cause"].type)

    def test_374_clinic_incident_investigation_field_string_root_cause(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["root_cause"].string)

    def test_375_clinic_incident_investigation_field_model_root_cause(self):
        self.assertEqual(self.env["clinic.incident.investigation"]._fields["root_cause"].model_name, "clinic.incident.investigation")

    def test_376_clinic_incident_investigation_field_lessons_learned(self):
        self.assertIn("lessons_learned", self.env["clinic.incident.investigation"]._fields)

    def test_377_clinic_incident_investigation_field_type_lessons_learned(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["lessons_learned"].type)

    def test_378_clinic_incident_investigation_field_string_lessons_learned(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["lessons_learned"].string)

    def test_379_clinic_incident_investigation_field_model_lessons_learned(self):
        self.assertEqual(self.env["clinic.incident.investigation"]._fields["lessons_learned"].model_name, "clinic.incident.investigation")

    def test_380_clinic_incident_investigation_field_recommendation(self):
        self.assertIn("recommendation", self.env["clinic.incident.investigation"]._fields)

    def test_381_clinic_incident_investigation_field_type_recommendation(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["recommendation"].type)

    def test_382_clinic_incident_investigation_field_string_recommendation(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["recommendation"].string)

    def test_383_clinic_incident_investigation_field_model_recommendation(self):
        self.assertEqual(self.env["clinic.incident.investigation"]._fields["recommendation"].model_name, "clinic.incident.investigation")

    def test_384_model_clinic_incident_action(self):
        self.assertIn("clinic.incident.action", self.env.registry)

    def test_385_clinic_incident_action_field_name(self):
        self.assertIn("name", self.env["clinic.incident.action"]._fields)

    def test_386_clinic_incident_action_field_type_name(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["name"].type)

    def test_387_clinic_incident_action_field_string_name(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["name"].string)

    def test_388_clinic_incident_action_field_model_name(self):
        self.assertEqual(self.env["clinic.incident.action"]._fields["name"].model_name, "clinic.incident.action")

    def test_389_clinic_incident_action_field_incident_id(self):
        self.assertIn("incident_id", self.env["clinic.incident.action"]._fields)

    def test_390_clinic_incident_action_field_type_incident_id(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["incident_id"].type)

    def test_391_clinic_incident_action_field_string_incident_id(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["incident_id"].string)

    def test_392_clinic_incident_action_field_model_incident_id(self):
        self.assertEqual(self.env["clinic.incident.action"]._fields["incident_id"].model_name, "clinic.incident.action")

    def test_393_clinic_incident_action_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.incident.action"]._fields)

    def test_394_clinic_incident_action_field_type_company_id(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["company_id"].type)

    def test_395_clinic_incident_action_field_string_company_id(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["company_id"].string)

    def test_396_clinic_incident_action_field_model_company_id(self):
        self.assertEqual(self.env["clinic.incident.action"]._fields["company_id"].model_name, "clinic.incident.action")

    def test_397_clinic_incident_action_field_branch_id(self):
        self.assertIn("branch_id", self.env["clinic.incident.action"]._fields)

    def test_398_clinic_incident_action_field_type_branch_id(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["branch_id"].type)

    def test_399_clinic_incident_action_field_string_branch_id(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["branch_id"].string)

    def test_400_clinic_incident_action_field_model_branch_id(self):
        self.assertEqual(self.env["clinic.incident.action"]._fields["branch_id"].model_name, "clinic.incident.action")

    def test_401_clinic_incident_action_field_action_type(self):
        self.assertIn("action_type", self.env["clinic.incident.action"]._fields)

    def test_402_clinic_incident_action_field_type_action_type(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["action_type"].type)

    def test_403_clinic_incident_action_field_string_action_type(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["action_type"].string)

    def test_404_clinic_incident_action_field_model_action_type(self):
        self.assertEqual(self.env["clinic.incident.action"]._fields["action_type"].model_name, "clinic.incident.action")

    def test_405_clinic_incident_action_field_priority(self):
        self.assertIn("priority", self.env["clinic.incident.action"]._fields)

    def test_406_clinic_incident_action_field_type_priority(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["priority"].type)

    def test_407_clinic_incident_action_field_string_priority(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["priority"].string)

    def test_408_clinic_incident_action_field_model_priority(self):
        self.assertEqual(self.env["clinic.incident.action"]._fields["priority"].model_name, "clinic.incident.action")

    def test_409_clinic_incident_action_field_state(self):
        self.assertIn("state", self.env["clinic.incident.action"]._fields)

    def test_410_clinic_incident_action_field_type_state(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["state"].type)

    def test_411_clinic_incident_action_field_string_state(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["state"].string)

    def test_412_clinic_incident_action_field_model_state(self):
        self.assertEqual(self.env["clinic.incident.action"]._fields["state"].model_name, "clinic.incident.action")

    def test_413_clinic_incident_action_field_owner_user_id(self):
        self.assertIn("owner_user_id", self.env["clinic.incident.action"]._fields)

    def test_414_clinic_incident_action_field_type_owner_user_id(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["owner_user_id"].type)

    def test_415_clinic_incident_action_field_string_owner_user_id(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["owner_user_id"].string)

    def test_416_clinic_incident_action_field_model_owner_user_id(self):
        self.assertEqual(self.env["clinic.incident.action"]._fields["owner_user_id"].model_name, "clinic.incident.action")

    def test_417_clinic_incident_action_field_owner_staff_id(self):
        self.assertIn("owner_staff_id", self.env["clinic.incident.action"]._fields)

    def test_418_clinic_incident_action_field_type_owner_staff_id(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["owner_staff_id"].type)

    def test_419_clinic_incident_action_field_string_owner_staff_id(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["owner_staff_id"].string)

    def test_420_clinic_incident_action_field_model_owner_staff_id(self):
        self.assertEqual(self.env["clinic.incident.action"]._fields["owner_staff_id"].model_name, "clinic.incident.action")

    def test_421_clinic_incident_action_field_due_at(self):
        self.assertIn("due_at", self.env["clinic.incident.action"]._fields)

    def test_422_clinic_incident_action_field_type_due_at(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["due_at"].type)

    def test_423_clinic_incident_action_field_string_due_at(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["due_at"].string)

    def test_424_clinic_incident_action_field_model_due_at(self):
        self.assertEqual(self.env["clinic.incident.action"]._fields["due_at"].model_name, "clinic.incident.action")

    def test_425_clinic_incident_action_field_started_at(self):
        self.assertIn("started_at", self.env["clinic.incident.action"]._fields)

    def test_426_clinic_incident_action_field_type_started_at(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["started_at"].type)

    def test_427_clinic_incident_action_field_string_started_at(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["started_at"].string)

    def test_428_clinic_incident_action_field_model_started_at(self):
        self.assertEqual(self.env["clinic.incident.action"]._fields["started_at"].model_name, "clinic.incident.action")

    def test_429_clinic_incident_action_field_done_at(self):
        self.assertIn("done_at", self.env["clinic.incident.action"]._fields)

    def test_430_clinic_incident_action_field_type_done_at(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["done_at"].type)

    def test_431_clinic_incident_action_field_string_done_at(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["done_at"].string)

    def test_432_clinic_incident_action_field_model_done_at(self):
        self.assertEqual(self.env["clinic.incident.action"]._fields["done_at"].model_name, "clinic.incident.action")

    def test_433_clinic_incident_action_field_verified_at(self):
        self.assertIn("verified_at", self.env["clinic.incident.action"]._fields)

    def test_434_clinic_incident_action_field_type_verified_at(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["verified_at"].type)

    def test_435_clinic_incident_action_field_string_verified_at(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["verified_at"].string)

    def test_436_clinic_incident_action_field_model_verified_at(self):
        self.assertEqual(self.env["clinic.incident.action"]._fields["verified_at"].model_name, "clinic.incident.action")

    def test_437_clinic_incident_action_field_verified_by_id(self):
        self.assertIn("verified_by_id", self.env["clinic.incident.action"]._fields)

    def test_438_clinic_incident_action_field_type_verified_by_id(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["verified_by_id"].type)

    def test_439_clinic_incident_action_field_string_verified_by_id(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["verified_by_id"].string)

    def test_440_clinic_incident_action_field_model_verified_by_id(self):
        self.assertEqual(self.env["clinic.incident.action"]._fields["verified_by_id"].model_name, "clinic.incident.action")

    def test_441_clinic_incident_action_field_description(self):
        self.assertIn("description", self.env["clinic.incident.action"]._fields)

    def test_442_clinic_incident_action_field_type_description(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["description"].type)

    def test_443_clinic_incident_action_field_string_description(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["description"].string)

    def test_444_clinic_incident_action_field_model_description(self):
        self.assertEqual(self.env["clinic.incident.action"]._fields["description"].model_name, "clinic.incident.action")

    def test_445_clinic_incident_action_field_completion_note(self):
        self.assertIn("completion_note", self.env["clinic.incident.action"]._fields)

    def test_446_clinic_incident_action_field_type_completion_note(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["completion_note"].type)

    def test_447_clinic_incident_action_field_string_completion_note(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["completion_note"].string)

    def test_448_clinic_incident_action_field_model_completion_note(self):
        self.assertEqual(self.env["clinic.incident.action"]._fields["completion_note"].model_name, "clinic.incident.action")

    def test_449_clinic_incident_action_field_effectiveness_result(self):
        self.assertIn("effectiveness_result", self.env["clinic.incident.action"]._fields)

    def test_450_clinic_incident_action_field_type_effectiveness_result(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["effectiveness_result"].type)

    def test_451_clinic_incident_action_field_string_effectiveness_result(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["effectiveness_result"].string)

    def test_452_clinic_incident_action_field_model_effectiveness_result(self):
        self.assertEqual(self.env["clinic.incident.action"]._fields["effectiveness_result"].model_name, "clinic.incident.action")

    def test_453_clinic_incident_action_field_effectiveness_note(self):
        self.assertIn("effectiveness_note", self.env["clinic.incident.action"]._fields)

    def test_454_clinic_incident_action_field_type_effectiveness_note(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["effectiveness_note"].type)

    def test_455_clinic_incident_action_field_string_effectiveness_note(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["effectiveness_note"].string)

    def test_456_clinic_incident_action_field_model_effectiveness_note(self):
        self.assertEqual(self.env["clinic.incident.action"]._fields["effectiveness_note"].model_name, "clinic.incident.action")

    def test_457_clinic_incident_action_field_evidence_attachment_ids(self):
        self.assertIn("evidence_attachment_ids", self.env["clinic.incident.action"]._fields)

    def test_458_clinic_incident_action_field_type_evidence_attachment_ids(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["evidence_attachment_ids"].type)

    def test_459_clinic_incident_action_field_string_evidence_attachment_ids(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["evidence_attachment_ids"].string)

    def test_460_clinic_incident_action_field_model_evidence_attachment_ids(self):
        self.assertEqual(self.env["clinic.incident.action"]._fields["evidence_attachment_ids"].model_name, "clinic.incident.action")

    def test_461_clinic_incident_action_field_is_overdue(self):
        self.assertIn("is_overdue", self.env["clinic.incident.action"]._fields)

    def test_462_clinic_incident_action_field_type_is_overdue(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["is_overdue"].type)

    def test_463_clinic_incident_action_field_string_is_overdue(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["is_overdue"].string)

    def test_464_clinic_incident_action_field_model_is_overdue(self):
        self.assertEqual(self.env["clinic.incident.action"]._fields["is_overdue"].model_name, "clinic.incident.action")

    def test_465_model_clinic_incident_timeline(self):
        self.assertIn("clinic.incident.timeline", self.env.registry)

    def test_466_clinic_incident_timeline_field_incident_id(self):
        self.assertIn("incident_id", self.env["clinic.incident.timeline"]._fields)

    def test_467_clinic_incident_timeline_field_type_incident_id(self):
        self.assertTrue(self.env["clinic.incident.timeline"]._fields["incident_id"].type)

    def test_468_clinic_incident_timeline_field_string_incident_id(self):
        self.assertTrue(self.env["clinic.incident.timeline"]._fields["incident_id"].string)

    def test_469_clinic_incident_timeline_field_model_incident_id(self):
        self.assertEqual(self.env["clinic.incident.timeline"]._fields["incident_id"].model_name, "clinic.incident.timeline")

    def test_470_clinic_incident_timeline_field_company_id(self):
        self.assertIn("company_id", self.env["clinic.incident.timeline"]._fields)

    def test_471_clinic_incident_timeline_field_type_company_id(self):
        self.assertTrue(self.env["clinic.incident.timeline"]._fields["company_id"].type)

    def test_472_clinic_incident_timeline_field_string_company_id(self):
        self.assertTrue(self.env["clinic.incident.timeline"]._fields["company_id"].string)

    def test_473_clinic_incident_timeline_field_model_company_id(self):
        self.assertEqual(self.env["clinic.incident.timeline"]._fields["company_id"].model_name, "clinic.incident.timeline")

    def test_474_clinic_incident_timeline_field_branch_id(self):
        self.assertIn("branch_id", self.env["clinic.incident.timeline"]._fields)

    def test_475_clinic_incident_timeline_field_type_branch_id(self):
        self.assertTrue(self.env["clinic.incident.timeline"]._fields["branch_id"].type)

    def test_476_clinic_incident_timeline_field_string_branch_id(self):
        self.assertTrue(self.env["clinic.incident.timeline"]._fields["branch_id"].string)

    def test_477_clinic_incident_timeline_field_model_branch_id(self):
        self.assertEqual(self.env["clinic.incident.timeline"]._fields["branch_id"].model_name, "clinic.incident.timeline")

    def test_478_clinic_incident_timeline_field_event_at(self):
        self.assertIn("event_at", self.env["clinic.incident.timeline"]._fields)

    def test_479_clinic_incident_timeline_field_type_event_at(self):
        self.assertTrue(self.env["clinic.incident.timeline"]._fields["event_at"].type)

    def test_480_clinic_incident_timeline_field_string_event_at(self):
        self.assertTrue(self.env["clinic.incident.timeline"]._fields["event_at"].string)

    def test_481_clinic_incident_timeline_field_model_event_at(self):
        self.assertEqual(self.env["clinic.incident.timeline"]._fields["event_at"].model_name, "clinic.incident.timeline")

    def test_482_clinic_incident_timeline_field_event_type(self):
        self.assertIn("event_type", self.env["clinic.incident.timeline"]._fields)

    def test_483_clinic_incident_timeline_field_type_event_type(self):
        self.assertTrue(self.env["clinic.incident.timeline"]._fields["event_type"].type)

    def test_484_clinic_incident_timeline_field_string_event_type(self):
        self.assertTrue(self.env["clinic.incident.timeline"]._fields["event_type"].string)

    def test_485_clinic_incident_timeline_field_model_event_type(self):
        self.assertEqual(self.env["clinic.incident.timeline"]._fields["event_type"].model_name, "clinic.incident.timeline")

    def test_486_clinic_incident_timeline_field_title(self):
        self.assertIn("title", self.env["clinic.incident.timeline"]._fields)

    def test_487_clinic_incident_timeline_field_type_title(self):
        self.assertTrue(self.env["clinic.incident.timeline"]._fields["title"].type)

    def test_488_clinic_incident_timeline_field_string_title(self):
        self.assertTrue(self.env["clinic.incident.timeline"]._fields["title"].string)

    def test_489_clinic_incident_timeline_field_model_title(self):
        self.assertEqual(self.env["clinic.incident.timeline"]._fields["title"].model_name, "clinic.incident.timeline")

    def test_490_clinic_incident_timeline_field_note(self):
        self.assertIn("note", self.env["clinic.incident.timeline"]._fields)

    def test_491_clinic_incident_timeline_field_type_note(self):
        self.assertTrue(self.env["clinic.incident.timeline"]._fields["note"].type)

    def test_492_clinic_incident_timeline_field_string_note(self):
        self.assertTrue(self.env["clinic.incident.timeline"]._fields["note"].string)

    def test_493_clinic_incident_timeline_field_model_note(self):
        self.assertEqual(self.env["clinic.incident.timeline"]._fields["note"].model_name, "clinic.incident.timeline")

    def test_494_clinic_incident_timeline_field_user_id(self):
        self.assertIn("user_id", self.env["clinic.incident.timeline"]._fields)

    def test_495_clinic_incident_timeline_field_type_user_id(self):
        self.assertTrue(self.env["clinic.incident.timeline"]._fields["user_id"].type)

    def test_496_clinic_incident_timeline_field_string_user_id(self):
        self.assertTrue(self.env["clinic.incident.timeline"]._fields["user_id"].string)

    def test_497_clinic_incident_timeline_field_model_user_id(self):
        self.assertEqual(self.env["clinic.incident.timeline"]._fields["user_id"].model_name, "clinic.incident.timeline")

    def test_498_clinic_incident_timeline_field_from_state(self):
        self.assertIn("from_state", self.env["clinic.incident.timeline"]._fields)

    def test_499_clinic_incident_timeline_field_type_from_state(self):
        self.assertTrue(self.env["clinic.incident.timeline"]._fields["from_state"].type)

    def test_500_clinic_incident_timeline_field_string_from_state(self):
        self.assertTrue(self.env["clinic.incident.timeline"]._fields["from_state"].string)

    def test_501_clinic_incident_timeline_field_model_from_state(self):
        self.assertEqual(self.env["clinic.incident.timeline"]._fields["from_state"].model_name, "clinic.incident.timeline")

    def test_502_clinic_incident_timeline_field_to_state(self):
        self.assertIn("to_state", self.env["clinic.incident.timeline"]._fields)

    def test_503_clinic_incident_timeline_field_type_to_state(self):
        self.assertTrue(self.env["clinic.incident.timeline"]._fields["to_state"].type)

    def test_504_clinic_incident_timeline_field_string_to_state(self):
        self.assertTrue(self.env["clinic.incident.timeline"]._fields["to_state"].string)

    def test_505_clinic_incident_timeline_field_model_to_state(self):
        self.assertEqual(self.env["clinic.incident.timeline"]._fields["to_state"].model_name, "clinic.incident.timeline")

    def test_506_clinic_incident_category_method_check_global_code_uniqueness(self):
        self.assertTrue(hasattr(self.env["clinic.incident.category"], "_check_global_code_uniqueness"))

    def test_507_clinic_incident_category_method_check_company_scope(self):
        self.assertTrue(hasattr(self.env["clinic.incident.category"], "_check_company_scope"))

    def test_508_clinic_incident_method_compute_allowed_branch_ids(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_compute_allowed_branch_ids"))

    def test_509_clinic_incident_method_compute_counts(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_compute_counts"))

    def test_510_clinic_incident_method_compute_is_overdue(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_compute_is_overdue"))

    def test_511_clinic_incident_method_compute_risk_flags(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_compute_risk_flags"))

    def test_512_clinic_incident_method_onchange_category_id(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_onchange_category_id"))

    def test_513_clinic_incident_method_allowed_incident_branches(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_allowed_incident_branches"))

    def test_514_clinic_incident_method_default_incident_branch(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_default_incident_branch"))

    def test_515_clinic_incident_method_check_scope_consistency(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_check_scope_consistency"))

    def test_516_clinic_incident_method_check_dates(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_check_dates"))

    def test_517_clinic_incident_method_require_reporter(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_require_reporter"))

    def test_518_clinic_incident_method_require_investigator(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_require_investigator"))

    def test_519_clinic_incident_method_require_manager(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_require_manager"))

    def test_520_clinic_incident_method_default_due_dates(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_default_due_dates"))

    def test_521_clinic_incident_method_log_timeline(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_log_timeline"))

    def test_522_clinic_incident_method_incident_form_action(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_incident_form_action"))

    def test_523_clinic_incident_method_open_related_record(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_open_related_record"))

    def test_524_clinic_incident_method_action_open_patient(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "action_open_patient"))

    def test_525_clinic_incident_method_action_open_encounter(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "action_open_encounter"))

    def test_526_clinic_incident_method_action_open_adverse_event(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "action_open_adverse_event"))

    def test_527_clinic_incident_method_action_open_booking(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "action_open_booking"))

    def test_528_clinic_incident_method_action_open_queue(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "action_open_queue"))

    def test_529_clinic_incident_method_action_open_emar_administration(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "action_open_emar_administration"))

    def test_530_clinic_incident_method_action_open_telemedicine_session(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "action_open_telemedicine_session"))

    def test_531_clinic_incident_method_action_open_secure_thread(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "action_open_secure_thread"))

    def test_532_clinic_incident_method_action_open_feedback_escalation(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "action_open_feedback_escalation"))

    def test_533_clinic_incident_method_action_open_investigations(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "action_open_investigations"))

    def test_534_clinic_incident_method_action_open_actions(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "action_open_actions"))

    def test_535_clinic_incident_method_action_open_timeline(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "action_open_timeline"))

    def test_536_clinic_incident_method_action_print_case_summary(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "action_print_case_summary"))

    def test_537_clinic_incident_method_action_report(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "action_report"))

    def test_538_clinic_incident_method_action_start_triage(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "action_start_triage"))

    def test_539_clinic_incident_method_action_review_reportability(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "action_review_reportability"))

    def test_540_clinic_incident_method_action_start_investigation(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "action_start_investigation"))

    def test_541_clinic_incident_method_action_move_to_action_plan(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "action_move_to_action_plan"))

    def test_542_clinic_incident_method_action_move_to_verification(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "action_move_to_verification"))

    def test_543_clinic_incident_method_action_mark_regulator_reported(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "action_mark_regulator_reported"))

    def test_544_clinic_incident_method_action_close(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "action_close"))

    def test_545_clinic_incident_method_action_cancel(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "action_cancel"))

    def test_546_clinic_incident_method_category_for_type(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_category_for_type"))

    def test_547_clinic_incident_method_onchange_adverse_event_id(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_onchange_adverse_event_id"))

    def test_548_clinic_incident_method_onchange_telemedicine_session_id(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_onchange_telemedicine_session_id"))

    def test_549_clinic_incident_method_onchange_telemedicine_thread_id(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_onchange_telemedicine_thread_id"))

    def test_550_clinic_incident_method_onchange_emar_administration_id(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_onchange_emar_administration_id"))

    def test_551_clinic_incident_method_onchange_booking_id(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_onchange_booking_id"))

    def test_552_clinic_incident_method_onchange_queue_id(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_onchange_queue_id"))

    def test_553_clinic_incident_method_onchange_feedback_escalation_id(self):
        self.assertTrue(hasattr(self.env["clinic.incident"], "_onchange_feedback_escalation_id"))

    def test_554_clinic_incident_investigation_method_check_company(self):
        self.assertTrue(hasattr(self.env["clinic.incident.investigation"], "_check_company"))

    def test_555_clinic_incident_investigation_method_action_start(self):
        self.assertTrue(hasattr(self.env["clinic.incident.investigation"], "action_start"))

    def test_556_clinic_incident_investigation_method_action_complete(self):
        self.assertTrue(hasattr(self.env["clinic.incident.investigation"], "action_complete"))

    def test_557_clinic_incident_investigation_method_action_cancel(self):
        self.assertTrue(hasattr(self.env["clinic.incident.investigation"], "action_cancel"))

    def test_558_clinic_incident_investigation_method_action_open_incident(self):
        self.assertTrue(hasattr(self.env["clinic.incident.investigation"], "action_open_incident"))

    def test_559_clinic_incident_action_method_compute_is_overdue(self):
        self.assertTrue(hasattr(self.env["clinic.incident.action"], "_compute_is_overdue"))

    def test_560_clinic_incident_action_method_check_scope(self):
        self.assertTrue(hasattr(self.env["clinic.incident.action"], "_check_scope"))

    def test_561_clinic_incident_action_method_action_start(self):
        self.assertTrue(hasattr(self.env["clinic.incident.action"], "action_start"))

    def test_562_clinic_incident_action_method_action_mark_done(self):
        self.assertTrue(hasattr(self.env["clinic.incident.action"], "action_mark_done"))

    def test_563_clinic_incident_action_method_verify(self):
        self.assertTrue(hasattr(self.env["clinic.incident.action"], "_verify"))

    def test_564_clinic_incident_action_method_action_verify_effective(self):
        self.assertTrue(hasattr(self.env["clinic.incident.action"], "action_verify_effective"))

    def test_565_clinic_incident_action_method_action_verify_partial(self):
        self.assertTrue(hasattr(self.env["clinic.incident.action"], "action_verify_partial"))

    def test_566_clinic_incident_action_method_action_verify_ineffective(self):
        self.assertTrue(hasattr(self.env["clinic.incident.action"], "action_verify_ineffective"))

    def test_567_clinic_incident_action_method_action_cancel(self):
        self.assertTrue(hasattr(self.env["clinic.incident.action"], "action_cancel"))

    def test_568_clinic_incident_action_method_action_open_incident(self):
        self.assertTrue(hasattr(self.env["clinic.incident.action"], "action_open_incident"))

    def test_569_clinic_incident_timeline_method_check_scope(self):
        self.assertTrue(hasattr(self.env["clinic.incident.timeline"], "_check_scope"))

    def test_570_clinic_incident_timeline_method_action_open_incident(self):
        self.assertTrue(hasattr(self.env["clinic.incident.timeline"], "action_open_incident"))

    def test_571_comodel_clinic_incident_branch_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["branch_id"].comodel_name, "clinic.branch")

    def test_572_comodel_clinic_incident_category_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["category_id"].comodel_name, "clinic.incident.category")

    def test_573_comodel_clinic_incident_patient_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["patient_id"].comodel_name, "clinic.patient")

    def test_574_comodel_clinic_incident_doctor_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["doctor_id"].comodel_name, "clinic.doctor")

    def test_575_comodel_clinic_incident_involved_staff_ids(self):
        self.assertEqual(self.env["clinic.incident"]._fields["involved_staff_ids"].comodel_name, "clinic.staff")

    def test_576_comodel_clinic_incident_room_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["room_id"].comodel_name, "clinic.room")

    def test_577_comodel_clinic_incident_encounter_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["encounter_id"].comodel_name, "clinic.encounter")

    def test_578_comodel_clinic_incident_adverse_event_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["adverse_event_id"].comodel_name, "clinic.adverse.event")

    def test_579_comodel_clinic_incident_booking_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["booking_id"].comodel_name, "booking.booking")

    def test_580_comodel_clinic_incident_queue_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["queue_id"].comodel_name, "clinic.queue")

    def test_581_comodel_clinic_incident_emar_administration_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["emar_administration_id"].comodel_name, "clinic.emar.administration")

    def test_582_comodel_clinic_incident_telemedicine_session_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["telemedicine_session_id"].comodel_name, "clinic.telemedicine.session")

    def test_583_comodel_clinic_incident_telemedicine_thread_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["telemedicine_thread_id"].comodel_name, "clinic.telemedicine.thread")

    def test_584_comodel_clinic_incident_feedback_escalation_id(self):
        self.assertEqual(self.env["clinic.incident"]._fields["feedback_escalation_id"].comodel_name, "clinic.feedback.escalation")

    def test_585_comodel_clinic_incident_investigation_incident_id(self):
        self.assertEqual(self.env["clinic.incident.investigation"]._fields["incident_id"].comodel_name, "clinic.incident")

    def test_586_comodel_clinic_incident_action_incident_id(self):
        self.assertEqual(self.env["clinic.incident.action"]._fields["incident_id"].comodel_name, "clinic.incident")

    def test_587_comodel_clinic_incident_timeline_incident_id(self):
        self.assertEqual(self.env["clinic.incident.timeline"]._fields["incident_id"].comodel_name, "clinic.incident")

    def test_588_selection_clinic_incident_state_draft(self):
        selection = dict(self.env["clinic.incident"]._fields["state"].selection)
        self.assertIn("draft", selection)

    def test_589_selection_clinic_incident_state_reported(self):
        selection = dict(self.env["clinic.incident"]._fields["state"].selection)
        self.assertIn("reported", selection)

    def test_590_selection_clinic_incident_state_triage(self):
        selection = dict(self.env["clinic.incident"]._fields["state"].selection)
        self.assertIn("triage", selection)

    def test_591_selection_clinic_incident_state_investigation(self):
        selection = dict(self.env["clinic.incident"]._fields["state"].selection)
        self.assertIn("investigation", selection)

    def test_592_selection_clinic_incident_state_action_plan(self):
        selection = dict(self.env["clinic.incident"]._fields["state"].selection)
        self.assertIn("action_plan", selection)

    def test_593_selection_clinic_incident_state_verification(self):
        selection = dict(self.env["clinic.incident"]._fields["state"].selection)
        self.assertIn("verification", selection)

    def test_594_selection_clinic_incident_state_closed(self):
        selection = dict(self.env["clinic.incident"]._fields["state"].selection)
        self.assertIn("closed", selection)

    def test_595_selection_clinic_incident_state_cancelled(self):
        selection = dict(self.env["clinic.incident"]._fields["state"].selection)
        self.assertIn("cancelled", selection)

    def test_596_selection_clinic_incident_classification_near_miss(self):
        selection = dict(self.env["clinic.incident"]._fields["classification"].selection)
        self.assertIn("near_miss", selection)

    def test_597_selection_clinic_incident_classification_no_harm(self):
        selection = dict(self.env["clinic.incident"]._fields["classification"].selection)
        self.assertIn("no_harm", selection)

    def test_598_selection_clinic_incident_classification_adverse_event(self):
        selection = dict(self.env["clinic.incident"]._fields["classification"].selection)
        self.assertIn("adverse_event", selection)

    def test_599_selection_clinic_incident_classification_sentinel(self):
        selection = dict(self.env["clinic.incident"]._fields["classification"].selection)
        self.assertIn("sentinel", selection)

    def test_600_selection_clinic_incident_classification_operational(self):
        selection = dict(self.env["clinic.incident"]._fields["classification"].selection)
        self.assertIn("operational", selection)

    def test_601_selection_clinic_incident_severity_low(self):
        selection = dict(self.env["clinic.incident"]._fields["severity"].selection)
        self.assertIn("low", selection)

    def test_602_selection_clinic_incident_severity_medium(self):
        selection = dict(self.env["clinic.incident"]._fields["severity"].selection)
        self.assertIn("medium", selection)

    def test_603_selection_clinic_incident_severity_high(self):
        selection = dict(self.env["clinic.incident"]._fields["severity"].selection)
        self.assertIn("high", selection)

    def test_604_selection_clinic_incident_severity_critical(self):
        selection = dict(self.env["clinic.incident"]._fields["severity"].selection)
        self.assertIn("critical", selection)

    def test_605_selection_clinic_incident_investigation_state_draft(self):
        selection = dict(self.env["clinic.incident.investigation"]._fields["state"].selection)
        self.assertIn("draft", selection)

    def test_606_selection_clinic_incident_investigation_state_in_progress(self):
        selection = dict(self.env["clinic.incident.investigation"]._fields["state"].selection)
        self.assertIn("in_progress", selection)

    def test_607_selection_clinic_incident_investigation_state_completed(self):
        selection = dict(self.env["clinic.incident.investigation"]._fields["state"].selection)
        self.assertIn("completed", selection)

    def test_608_selection_clinic_incident_investigation_state_cancelled(self):
        selection = dict(self.env["clinic.incident.investigation"]._fields["state"].selection)
        self.assertIn("cancelled", selection)

    def test_609_selection_clinic_incident_action_state_planned(self):
        selection = dict(self.env["clinic.incident.action"]._fields["state"].selection)
        self.assertIn("planned", selection)

    def test_610_selection_clinic_incident_action_state_in_progress(self):
        selection = dict(self.env["clinic.incident.action"]._fields["state"].selection)
        self.assertIn("in_progress", selection)

    def test_611_selection_clinic_incident_action_state_done(self):
        selection = dict(self.env["clinic.incident.action"]._fields["state"].selection)
        self.assertIn("done", selection)

    def test_612_selection_clinic_incident_action_state_verified(self):
        selection = dict(self.env["clinic.incident.action"]._fields["state"].selection)
        self.assertIn("verified", selection)

    def test_613_selection_clinic_incident_action_state_cancelled(self):
        selection = dict(self.env["clinic.incident.action"]._fields["state"].selection)
        self.assertIn("cancelled", selection)

    def test_614_selection_clinic_incident_timeline_event_type_created(self):
        selection = dict(self.env["clinic.incident.timeline"]._fields["event_type"].selection)
        self.assertIn("created", selection)

    def test_615_selection_clinic_incident_timeline_event_type_state(self):
        selection = dict(self.env["clinic.incident.timeline"]._fields["event_type"].selection)
        self.assertIn("state", selection)

    def test_616_selection_clinic_incident_timeline_event_type_investigation(self):
        selection = dict(self.env["clinic.incident.timeline"]._fields["event_type"].selection)
        self.assertIn("investigation", selection)

    def test_617_selection_clinic_incident_timeline_event_type_action(self):
        selection = dict(self.env["clinic.incident.timeline"]._fields["event_type"].selection)
        self.assertIn("action", selection)

    def test_618_selection_clinic_incident_timeline_event_type_regulatory(self):
        selection = dict(self.env["clinic.incident.timeline"]._fields["event_type"].selection)
        self.assertIn("regulatory", selection)

    def test_619_selection_clinic_incident_timeline_event_type_source(self):
        selection = dict(self.env["clinic.incident.timeline"]._fields["event_type"].selection)
        self.assertIn("source", selection)

    def test_620_selection_clinic_incident_timeline_event_type_note(self):
        selection = dict(self.env["clinic.incident.timeline"]._fields["event_type"].selection)
        self.assertIn("note", selection)

    def test_621_selection_clinic_incident_timeline_event_type_system(self):
        selection = dict(self.env["clinic.incident.timeline"]._fields["event_type"].selection)
        self.assertIn("system", selection)

    def test_622_integration_model_res_company(self):
        self.assertIn("res.company", self.env.registry)

    def test_623_integration_field_res_company_policy_branch_scope_incident_event(self):
        self.assertIn("policy_branch_scope_incident_event", self.env["res.company"]._fields)

    def test_624_integration_field_res_company_clinic_incident_default_case_owner_id(self):
        self.assertIn("clinic_incident_default_case_owner_id", self.env["res.company"]._fields)

    def test_625_integration_field_res_company_clinic_incident_default_capa_days(self):
        self.assertIn("clinic_incident_default_capa_days", self.env["res.company"]._fields)

    def test_626_integration_field_res_company_clinic_incident_staff_kpi_enabled(self):
        self.assertIn("clinic_incident_staff_kpi_enabled", self.env["res.company"]._fields)

    def test_627_integration_model_res_users(self):
        self.assertIn("res.users", self.env.registry)

    def test_628_integration_field_res_users_allowed_branch_ids(self):
        self.assertIn("allowed_branch_ids", self.env["res.users"]._fields)

    def test_629_integration_field_res_users_working_branch_id(self):
        self.assertIn("working_branch_id", self.env["res.users"]._fields)

    def test_630_integration_field_res_users_clinic_incident_access_branch_ids(self):
        self.assertIn("clinic_incident_access_branch_ids", self.env["res.users"]._fields)

    def test_631_integration_model_res_config_settings(self):
        self.assertIn("res.config.settings", self.env.registry)

    def test_632_integration_field_res_config_settings_clinic_incident_default_case_owner_id(self):
        self.assertIn("clinic_incident_default_case_owner_id", self.env["res.config.settings"]._fields)

    def test_633_integration_field_res_config_settings_clinic_incident_default_capa_days(self):
        self.assertIn("clinic_incident_default_capa_days", self.env["res.config.settings"]._fields)

    def test_634_integration_field_res_config_settings_clinic_incident_staff_kpi_enabled(self):
        self.assertIn("clinic_incident_staff_kpi_enabled", self.env["res.config.settings"]._fields)

    def test_635_integration_model_res_partner(self):
        self.assertIn("res.partner", self.env.registry)

    def test_636_integration_field_res_partner_patient_id(self):
        self.assertIn("patient_id", self.env["res.partner"]._fields)

    def test_637_integration_field_res_partner_clinic_incident_count(self):
        self.assertIn("clinic_incident_count", self.env["res.partner"]._fields)

    def test_638_integration_model_clinic_patient(self):
        self.assertIn("clinic.patient", self.env.registry)

    def test_639_integration_field_clinic_patient_incident_ids(self):
        self.assertIn("incident_ids", self.env["clinic.patient"]._fields)

    def test_640_integration_field_clinic_patient_incident_count(self):
        self.assertIn("incident_count", self.env["clinic.patient"]._fields)

    def test_641_integration_model_clinic_doctor(self):
        self.assertIn("clinic.doctor", self.env.registry)

    def test_642_integration_field_clinic_doctor_incident_ids(self):
        self.assertIn("incident_ids", self.env["clinic.doctor"]._fields)

    def test_643_integration_field_clinic_doctor_incident_count(self):
        self.assertIn("incident_count", self.env["clinic.doctor"]._fields)

    def test_644_integration_model_clinic_staff(self):
        self.assertIn("clinic.staff", self.env.registry)

    def test_645_integration_field_clinic_staff_incident_count(self):
        self.assertIn("incident_count", self.env["clinic.staff"]._fields)

    def test_646_integration_model_clinic_staff_kpi(self):
        self.assertIn("clinic.staff.kpi", self.env.registry)

    def test_647_integration_field_clinic_staff_kpi_incidents_count(self):
        self.assertIn("incidents_count", self.env["clinic.staff.kpi"]._fields)

    def test_648_integration_field_clinic_staff_kpi_incidents_rate_per_100_assign(self):
        self.assertIn("incidents_rate_per_100_assign", self.env["clinic.staff.kpi"]._fields)

    def test_649_integration_field_clinic_staff_kpi_assignments_count(self):
        self.assertIn("assignments_count", self.env["clinic.staff.kpi"]._fields)

    def test_650_integration_model_booking_booking(self):
        self.assertIn("booking.booking", self.env.registry)

    def test_651_integration_field_booking_booking_incident_ids(self):
        self.assertIn("incident_ids", self.env["booking.booking"]._fields)

    def test_652_integration_field_booking_booking_incident_count(self):
        self.assertIn("incident_count", self.env["booking.booking"]._fields)

    def test_653_integration_model_clinic_queue(self):
        self.assertIn("clinic.queue", self.env.registry)

    def test_654_integration_field_clinic_queue_incident_ids(self):
        self.assertIn("incident_ids", self.env["clinic.queue"]._fields)

    def test_655_integration_field_clinic_queue_incident_count(self):
        self.assertIn("incident_count", self.env["clinic.queue"]._fields)

    def test_656_integration_model_clinic_adverse_event(self):
        self.assertIn("clinic.adverse.event", self.env.registry)

    def test_657_integration_field_clinic_adverse_event_incident_count(self):
        self.assertIn("incident_count", self.env["clinic.adverse.event"]._fields)

    def test_658_integration_model_clinic_encounter(self):
        self.assertIn("clinic.encounter", self.env.registry)

    def test_659_integration_field_clinic_encounter_incident_ids(self):
        self.assertIn("incident_ids", self.env["clinic.encounter"]._fields)

    def test_660_integration_field_clinic_encounter_incident_count(self):
        self.assertIn("incident_count", self.env["clinic.encounter"]._fields)

    def test_661_integration_model_clinic_emar_administration(self):
        self.assertIn("clinic.emar.administration", self.env.registry)

    def test_662_integration_field_clinic_emar_administration_incident_ids(self):
        self.assertIn("incident_ids", self.env["clinic.emar.administration"]._fields)

    def test_663_integration_field_clinic_emar_administration_incident_count(self):
        self.assertIn("incident_count", self.env["clinic.emar.administration"]._fields)

    def test_664_integration_model_clinic_feedback_escalation(self):
        self.assertIn("clinic.feedback.escalation", self.env.registry)

    def test_665_integration_field_clinic_feedback_escalation_incident_ids(self):
        self.assertIn("incident_ids", self.env["clinic.feedback.escalation"]._fields)

    def test_666_integration_field_clinic_feedback_escalation_incident_count(self):
        self.assertIn("incident_count", self.env["clinic.feedback.escalation"]._fields)

    def test_667_integration_model_clinic_telemedicine_session(self):
        self.assertIn("clinic.telemedicine.session", self.env.registry)

    def test_668_integration_field_clinic_telemedicine_session_incident_ids(self):
        self.assertIn("incident_ids", self.env["clinic.telemedicine.session"]._fields)

    def test_669_integration_field_clinic_telemedicine_session_incident_count(self):
        self.assertIn("incident_count", self.env["clinic.telemedicine.session"]._fields)

    def test_670_integration_model_clinic_telemedicine_thread(self):
        self.assertIn("clinic.telemedicine.thread", self.env.registry)

    def test_671_integration_field_clinic_telemedicine_thread_incident_ids(self):
        self.assertIn("incident_ids", self.env["clinic.telemedicine.thread"]._fields)

    def test_672_integration_field_clinic_telemedicine_thread_incident_count(self):
        self.assertIn("incident_count", self.env["clinic.telemedicine.thread"]._fields)

    def test_673_integration_method_res_partner_action_open_clinic_incidents(self):
        self.assertTrue(hasattr(self.env["res.partner"], "action_open_clinic_incidents"))

    def test_674_integration_method_clinic_patient_action_open_incident_cases(self):
        self.assertTrue(hasattr(self.env["clinic.patient"], "action_open_incident_cases"))

    def test_675_integration_method_clinic_doctor_action_open_incident_cases(self):
        self.assertTrue(hasattr(self.env["clinic.doctor"], "action_open_incident_cases"))

    def test_676_integration_method_booking_booking_action_open_incident_cases(self):
        self.assertTrue(hasattr(self.env["booking.booking"], "action_open_incident_cases"))

    def test_677_integration_method_clinic_queue_action_open_incident_cases(self):
        self.assertTrue(hasattr(self.env["clinic.queue"], "action_open_incident_cases"))

    def test_678_integration_method_clinic_adverse_event_action_create_incident_case(self):
        self.assertTrue(hasattr(self.env["clinic.adverse.event"], "action_create_incident_case"))

    def test_679_integration_method_clinic_adverse_event_action_open_incident_cases(self):
        self.assertTrue(hasattr(self.env["clinic.adverse.event"], "action_open_incident_cases"))

    def test_680_integration_method_clinic_encounter_action_open_incident_cases(self):
        self.assertTrue(hasattr(self.env["clinic.encounter"], "action_open_incident_cases"))

    def test_681_integration_method_clinic_emar_administration_action_open_incident_cases(self):
        self.assertTrue(hasattr(self.env["clinic.emar.administration"], "action_open_incident_cases"))

    def test_682_integration_method_clinic_feedback_escalation_action_open_incident_cases(self):
        self.assertTrue(hasattr(self.env["clinic.feedback.escalation"], "action_open_incident_cases"))

    def test_683_integration_method_clinic_telemedicine_session_action_open_incident_cases(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.session"], "action_open_incident_cases"))

    def test_684_integration_method_clinic_telemedicine_thread_action_open_incident_cases(self):
        self.assertTrue(hasattr(self.env["clinic.telemedicine.thread"], "action_open_incident_cases"))

    def test_685_integration_method_clinic_staff_action_open_incidents(self):
        self.assertTrue(hasattr(self.env["clinic.staff"], "action_open_incidents"))

    def test_686_integration_method_clinic_staff__compute_counts(self):
        self.assertTrue(hasattr(self.env["clinic.staff"], "_compute_counts"))

    def test_687_integration_method_clinic_staff_kpi__aggregate_from_incidents_live(self):
        self.assertTrue(hasattr(self.env["clinic.staff.kpi"], "_aggregate_from_incidents_live"))

    def test_688_integration_method_clinic_staff_kpi_recompute_snapshot(self):
        self.assertTrue(hasattr(self.env["clinic.staff.kpi"], "recompute_snapshot"))

    def test_689_integration_method_clinic_staff_kpi_action_open_incidents(self):
        self.assertTrue(hasattr(self.env["clinic.staff.kpi"], "action_open_incidents"))

    def test_690_table_clinic_incident_category(self):
        self.assertEqual(self.env["clinic.incident.category"]._table, "clinic_incident_category")

    def test_691_table_clinic_incident(self):
        self.assertEqual(self.env["clinic.incident"]._table, "clinic_incident")

    def test_692_table_clinic_incident_investigation(self):
        self.assertEqual(self.env["clinic.incident.investigation"]._table, "clinic_incident_investigation")

    def test_693_table_clinic_incident_action(self):
        self.assertEqual(self.env["clinic.incident.action"]._table, "clinic_incident_action")

    def test_694_table_clinic_incident_timeline(self):
        self.assertEqual(self.env["clinic.incident.timeline"]._table, "clinic_incident_timeline")

    def test_695_stored_clinic_incident_partner_id(self):
        self.assertTrue(self.env["clinic.incident"]._fields["partner_id"].store)

    def test_696_stored_clinic_incident_investigation_count(self):
        self.assertTrue(self.env["clinic.incident"]._fields["investigation_count"].store)

    def test_697_stored_clinic_incident_completed_investigation_count(self):
        self.assertTrue(self.env["clinic.incident"]._fields["completed_investigation_count"].store)

    def test_698_stored_clinic_incident_action_count(self):
        self.assertTrue(self.env["clinic.incident"]._fields["action_count"].store)

    def test_699_stored_clinic_incident_open_action_count(self):
        self.assertTrue(self.env["clinic.incident"]._fields["open_action_count"].store)

    def test_700_stored_clinic_incident_timeline_count(self):
        self.assertTrue(self.env["clinic.incident"]._fields["timeline_count"].store)

    def test_701_stored_clinic_incident_is_serious(self):
        self.assertTrue(self.env["clinic.incident"]._fields["is_serious"].store)

    def test_702_stored_clinic_incident_needs_regulatory_review(self):
        self.assertTrue(self.env["clinic.incident"]._fields["needs_regulatory_review"].store)

    def test_703_stored_clinic_incident_investigation_company_id(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["company_id"].store)

    def test_704_stored_clinic_incident_investigation_branch_id(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["branch_id"].store)

    def test_705_stored_clinic_incident_investigation_patient_id(self):
        self.assertTrue(self.env["clinic.incident.investigation"]._fields["patient_id"].store)

    def test_706_stored_clinic_incident_action_company_id(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["company_id"].store)

    def test_707_stored_clinic_incident_action_branch_id(self):
        self.assertTrue(self.env["clinic.incident.action"]._fields["branch_id"].store)

    def test_708_stored_clinic_incident_timeline_company_id(self):
        self.assertTrue(self.env["clinic.incident.timeline"]._fields["company_id"].store)

    def test_709_stored_clinic_incident_timeline_branch_id(self):
        self.assertTrue(self.env["clinic.incident.timeline"]._fields["branch_id"].store)

    def test_710_view_clinic_incident_category_search(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.incident.category"),
            ("type", "=", "search"),
        ], limit=1)
        self.assertTrue(view)

    def test_711_view_clinic_incident_category_list(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.incident.category"),
            ("type", "=", "list"),
        ], limit=1)
        self.assertTrue(view)

    def test_712_view_clinic_incident_category_form(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.incident.category"),
            ("type", "=", "form"),
        ], limit=1)
        self.assertTrue(view)

    def test_713_view_clinic_incident_search(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.incident"),
            ("type", "=", "search"),
        ], limit=1)
        self.assertTrue(view)

    def test_714_view_clinic_incident_list(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.incident"),
            ("type", "=", "list"),
        ], limit=1)
        self.assertTrue(view)

    def test_715_view_clinic_incident_form(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.incident"),
            ("type", "=", "form"),
        ], limit=1)
        self.assertTrue(view)

    def test_716_view_clinic_incident_investigation_search(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.incident.investigation"),
            ("type", "=", "search"),
        ], limit=1)
        self.assertTrue(view)

    def test_717_view_clinic_incident_investigation_list(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.incident.investigation"),
            ("type", "=", "list"),
        ], limit=1)
        self.assertTrue(view)

    def test_718_view_clinic_incident_investigation_form(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.incident.investigation"),
            ("type", "=", "form"),
        ], limit=1)
        self.assertTrue(view)

    def test_719_view_clinic_incident_action_search(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.incident.action"),
            ("type", "=", "search"),
        ], limit=1)
        self.assertTrue(view)

    def test_720_view_clinic_incident_action_list(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.incident.action"),
            ("type", "=", "list"),
        ], limit=1)
        self.assertTrue(view)

    def test_721_view_clinic_incident_action_form(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.incident.action"),
            ("type", "=", "form"),
        ], limit=1)
        self.assertTrue(view)

    def test_722_view_clinic_incident_timeline_search(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.incident.timeline"),
            ("type", "=", "search"),
        ], limit=1)
        self.assertTrue(view)

    def test_723_view_clinic_incident_timeline_list(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.incident.timeline"),
            ("type", "=", "list"),
        ], limit=1)
        self.assertTrue(view)

    def test_724_view_clinic_incident_timeline_form(self):
        view = self.env["ir.ui.view"].search([
            ("model", "=", "clinic.incident.timeline"),
            ("type", "=", "form"),
        ], limit=1)
        self.assertTrue(view)

    def test_725_xmlid_view_incident_kanban(self):
        self.assertTrue(self.env.ref("clinic_incident_event.view_incident_kanban"))

    def test_726_xmlid_view_incident_pivot(self):
        self.assertTrue(self.env.ref("clinic_incident_event.view_incident_pivot"))

    def test_727_xmlid_view_incident_graph(self):
        self.assertTrue(self.env.ref("clinic_incident_event.view_incident_graph"))

    def test_728_xmlid_view_incident_action_kanban(self):
        self.assertTrue(self.env.ref("clinic_incident_event.view_incident_action_kanban"))

    def test_729_xmlid_view_incident_action_pivot(self):
        self.assertTrue(self.env.ref("clinic_incident_event.view_incident_action_pivot"))

    def test_730_xmlid_view_incident_action_graph(self):
        self.assertTrue(self.env.ref("clinic_incident_event.view_incident_action_graph"))

    def test_731_xmlid_view_incident_regulatory_list(self):
        self.assertTrue(self.env.ref("clinic_incident_event.view_incident_regulatory_list"))

    def test_732_xmlid_view_partner_form_incident_inherit(self):
        self.assertTrue(self.env.ref("clinic_incident_event.view_partner_form_incident_inherit"))

    def test_733_xmlid_action_incident(self):
        self.assertTrue(self.env.ref("clinic_incident_event.action_incident"))

    def test_734_xmlid_action_incident_regulatory(self):
        self.assertTrue(self.env.ref("clinic_incident_event.action_incident_regulatory"))

    def test_735_xmlid_action_incident_investigation(self):
        self.assertTrue(self.env.ref("clinic_incident_event.action_incident_investigation"))

    def test_736_xmlid_action_incident_action(self):
        self.assertTrue(self.env.ref("clinic_incident_event.action_incident_action"))

    def test_737_xmlid_action_incident_timeline(self):
        self.assertTrue(self.env.ref("clinic_incident_event.action_incident_timeline"))

    def test_738_xmlid_action_incident_category(self):
        self.assertTrue(self.env.ref("clinic_incident_event.action_incident_category"))

    def test_739_xmlid_action_incident_settings(self):
        self.assertTrue(self.env.ref("clinic_incident_event.action_incident_settings"))

    def test_740_xmlid_action_report_incident_case(self):
        self.assertTrue(self.env.ref("clinic_incident_event.action_report_incident_case"))

    def test_741_xmlid_seq_incident(self):
        self.assertTrue(self.env.ref("clinic_incident_event.seq_incident"))

    def test_742_xmlid_seq_incident_investigation(self):
        self.assertTrue(self.env.ref("clinic_incident_event.seq_incident_investigation"))

    def test_743_xmlid_group_incident_user(self):
        self.assertTrue(self.env.ref("clinic_incident_event.group_incident_user"))

    def test_744_xmlid_group_incident_reporter(self):
        self.assertTrue(self.env.ref("clinic_incident_event.group_incident_reporter"))

    def test_745_xmlid_group_incident_investigator(self):
        self.assertTrue(self.env.ref("clinic_incident_event.group_incident_investigator"))

    def test_746_xmlid_group_incident_manager(self):
        self.assertTrue(self.env.ref("clinic_incident_event.group_incident_manager"))

    def test_747_seed_category_clinical_adverse(self):
        self.assertTrue(self.env.ref("clinic_incident_event.incident_category_clinical_adverse"))

    def test_748_seed_category_medication(self):
        self.assertTrue(self.env.ref("clinic_incident_event.incident_category_medication"))

    def test_749_seed_category_device(self):
        self.assertTrue(self.env.ref("clinic_incident_event.incident_category_device"))

    def test_750_seed_category_fall(self):
        self.assertTrue(self.env.ref("clinic_incident_event.incident_category_fall"))

    def test_751_seed_category_infection(self):
        self.assertTrue(self.env.ref("clinic_incident_event.incident_category_infection"))

    def test_752_seed_category_privacy(self):
        self.assertTrue(self.env.ref("clinic_incident_event.incident_category_privacy"))

    def test_753_seed_category_staff_safety(self):
        self.assertTrue(self.env.ref("clinic_incident_event.incident_category_staff_safety"))

    def test_754_seed_category_facility(self):
        self.assertTrue(self.env.ref("clinic_incident_event.incident_category_facility"))

    def test_755_seed_category_telemedicine(self):
        self.assertTrue(self.env.ref("clinic_incident_event.incident_category_telemedicine"))

    def test_756_seed_category_service(self):
        self.assertTrue(self.env.ref("clinic_incident_event.incident_category_service"))

    def test_757_seed_category_operational(self):
        self.assertTrue(self.env.ref("clinic_incident_event.incident_category_operational"))

    def test_758_seed_category_other(self):
        self.assertTrue(self.env.ref("clinic_incident_event.incident_category_other"))

    def test_759_reporter_implies_user(self):
        user = self.env.ref("clinic_incident_event.group_incident_user")
        reporter = self.env.ref("clinic_incident_event.group_incident_reporter")
        self.assertIn(user, reporter.implied_ids)

    def test_760_investigator_implies_reporter(self):
        reporter = self.env.ref("clinic_incident_event.group_incident_reporter")
        investigator = self.env.ref("clinic_incident_event.group_incident_investigator")
        self.assertIn(reporter, investigator.implied_ids)

    def test_761_manager_implies_investigator(self):
        investigator = self.env.ref("clinic_incident_event.group_incident_investigator")
        manager = self.env.ref("clinic_incident_event.group_incident_manager")
        self.assertIn(investigator, manager.implied_ids)

    def test_762_search_architecture_odoo19(self):
        xmlids = (
            "clinic_incident_event.view_incident_category_search",
            "clinic_incident_event.view_incident_search",
            "clinic_incident_event.view_incident_investigation_search",
            "clinic_incident_event.view_incident_action_search",
            "clinic_incident_event.view_incident_timeline_search",
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

    def test_763_upstream_owner_exists_clinic_adverse_event(self):
        self.assertIn("clinic.adverse.event", self.env.registry)

    def test_764_upstream_owner_exists_clinic_ae_action(self):
        self.assertIn("clinic.ae.action", self.env.registry)

    def test_765_upstream_owner_exists_clinic_ae_followup(self):
        self.assertIn("clinic.ae.followup", self.env.registry)

    def test_766_upstream_owner_exists_clinic_encounter(self):
        self.assertIn("clinic.encounter", self.env.registry)

    def test_767_upstream_owner_exists_clinic_emar_administration(self):
        self.assertIn("clinic.emar.administration", self.env.registry)

    def test_768_upstream_owner_exists_clinic_telemedicine_session(self):
        self.assertIn("clinic.telemedicine.session", self.env.registry)

    def test_769_upstream_owner_exists_clinic_telemedicine_thread(self):
        self.assertIn("clinic.telemedicine.thread", self.env.registry)

    def test_770_no_parallel_clinic_quality_incident(self):
        self.assertNotIn("clinic.quality.incident", self.env.registry)

    def test_771_no_parallel_clinic_incident_external_regulator(self):
        self.assertNotIn("clinic.incident.external.regulator", self.env.registry)

    def test_772_no_parallel_clinic_incident_analytics(self):
        self.assertNotIn("clinic.incident.analytics", self.env.registry)

    def test_773_historical_occurred_at_datetime(self):
        self.assertEqual(
            self.env["clinic.incident"]._fields["occurred_at"].type,
            "datetime",
        )

    def test_774_historical_involved_staff_many2many(self):
        field = self.env["clinic.incident"]._fields["involved_staff_ids"]
        self.assertEqual(field.type, "many2many")
        self.assertEqual(field.comodel_name, "clinic.staff")

    def test_775_queue_doctor_remains_hr_employee(self):
        self.assertEqual(
            self.env["clinic.queue"]._fields["doctor_id"].comodel_name,
            "hr.employee",
        )

    def test_776_feedback_patient_remains_partner(self):
        self.assertEqual(
            self.env["clinic.feedback.escalation"]._fields["patient_id"].comodel_name,
            "res.partner",
        )

    def test_777_emar_patient_contract(self):
        self.assertEqual(
            self.env["clinic.emar.administration"]._fields["patient_id"].comodel_name,
            "clinic.patient",
        )

    def test_778_telemedicine_handler_contract(self):
        self.assertEqual(
            self.env["clinic.telemedicine.thread"]._fields["handler_id"].comodel_name,
            "clinic.staff",
        )
