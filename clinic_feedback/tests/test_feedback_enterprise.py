from lxml import etree

from odoo.tests.common import TransactionCase


OWNED_MODELS = (
    "clinic.feedback.survey",
    "clinic.feedback.question",
    "clinic.feedback.request",
    "clinic.feedback",
    "clinic.feedback.answer",
    "clinic.feedback.escalation",
)


class TestClinicFeedbackEnterprise(TransactionCase):

    def test_01_owned_models_exist(self):
        for model in OWNED_MODELS:
            self.assertIn(model, self.env.registry)

    def test_02_company_mixin_exists(self):
        self.assertIn("clinic.feedback.company.mixin", self.env.registry)

    def test_03_booking_feedback_link_still_exists(self):
        self.assertIn("booking.feedback.link", self.env.registry)

    def test_04_booking_feedback_link_still_owned_upstream_contract(self):
        model = self.env["booking.feedback.link"]
        for field in (
            "booking_id",
            "patient_id",
            "doctor_id",
            "treatment_id",
            "token",
            "rating_value",
            "comment",
            "would_recommend",
            "state",
        ):
            self.assertIn(field, model._fields)

    def test_05_booking_submit_method_preserved(self):
        self.assertTrue(
            hasattr(self.env["booking.feedback.link"], "action_submit_feedback")
        )

    def test_06_booking_token_lookup_preserved(self):
        self.assertTrue(
            hasattr(self.env["booking.feedback.link"], "sudo_find_by_token")
        )

    def test_07_booking_link_extension_has_survey(self):
        field = self.env["booking.feedback.link"]._fields["feedback_survey_id"]
        self.assertEqual(field.comodel_name, "clinic.feedback.survey")

    def test_08_booking_link_extension_has_canonical_feedback(self):
        field = self.env["booking.feedback.link"]._fields["clinic_feedback_id"]
        self.assertEqual(field.comodel_name, "clinic.feedback")

    def test_09_queue_feedback_request_bridge_exists(self):
        field = self.env["clinic.queue"]._fields["feedback_request_id"]
        self.assertEqual(field.comodel_name, "clinic.feedback.request")

    def test_10_queue_open_feedback_action_exists(self):
        self.assertTrue(
            hasattr(self.env["clinic.queue"], "action_open_feedback_request")
        )

    def test_11_survey_company_contract(self):
        field = self.env["clinic.feedback.survey"]._fields["company_id"]
        self.assertEqual(field.comodel_name, "res.company")

    def test_12_survey_branch_contract(self):
        field = self.env["clinic.feedback.survey"]._fields["branch_id"]
        self.assertEqual(field.comodel_name, "clinic.branch")

    def test_13_survey_workflow_complete(self):
        selection = dict(self.env["clinic.feedback.survey"]._fields["state"].selection)
        for value in ("draft", "active", "archived"):
            self.assertIn(value, selection)

    def test_14_survey_types_complete(self):
        selection = dict(
            self.env["clinic.feedback.survey"]._fields["survey_type"].selection
        )
        for value in (
            "satisfaction",
            "booking",
            "encounter",
            "postcare",
            "doctor",
            "facility",
        ):
            self.assertIn(value, selection)

    def test_15_survey_has_question_contract(self):
        field = self.env["clinic.feedback.survey"]._fields["question_ids"]
        self.assertEqual(field.comodel_name, "clinic.feedback.question")

    def test_16_survey_core_question_switches_exist(self):
        model = self.env["clinic.feedback.survey"]
        for field in (
            "require_overall_rating",
            "ask_nps",
            "ask_recommendation",
            "ask_comment",
        ):
            self.assertIn(field, model._fields)

    def test_17_question_survey_contract(self):
        field = self.env["clinic.feedback.question"]._fields["survey_id"]
        self.assertEqual(field.comodel_name, "clinic.feedback.survey")

    def test_18_question_types_complete(self):
        selection = dict(
            self.env["clinic.feedback.question"]._fields["question_type"].selection
        )
        for value in ("rating_1_5", "nps_0_10", "yes_no", "text"):
            self.assertIn(value, selection)

    def test_19_question_categories_complete(self):
        selection = dict(
            self.env["clinic.feedback.question"]._fields["category"].selection
        )
        for value in (
            "overall",
            "care",
            "doctor",
            "staff",
            "waiting",
            "facility",
            "communication",
            "postcare",
            "other",
        ):
            self.assertIn(value, selection)

    def test_20_request_survey_contract(self):
        field = self.env["clinic.feedback.request"]._fields["survey_id"]
        self.assertEqual(field.comodel_name, "clinic.feedback.survey")

    def test_21_request_patient_contact_contract(self):
        field = self.env["clinic.feedback.request"]._fields["patient_id"]
        self.assertEqual(field.comodel_name, "res.partner")

    def test_22_request_patient_card_contract(self):
        field = self.env["clinic.feedback.request"]._fields["patient_card_id"]
        self.assertEqual(field.comodel_name, "clinic.patient")
        self.assertTrue(field.store)

    def test_23_request_source_types_complete(self):
        selection = dict(
            self.env["clinic.feedback.request"]._fields["source_type"].selection
        )
        for value in ("manual", "booking", "queue", "encounter", "postcare"):
            self.assertIn(value, selection)

    def test_24_request_booking_contract(self):
        field = self.env["clinic.feedback.request"]._fields["booking_id"]
        self.assertEqual(field.comodel_name, "booking.booking")

    def test_25_request_queue_contract(self):
        field = self.env["clinic.feedback.request"]._fields["queue_id"]
        self.assertEqual(field.comodel_name, "clinic.queue")

    def test_26_request_encounter_contract(self):
        field = self.env["clinic.feedback.request"]._fields["encounter_id"]
        self.assertEqual(field.comodel_name, "clinic.encounter")

    def test_27_request_postcare_contract(self):
        field = self.env["clinic.feedback.request"]._fields["postcare_plan_id"]
        self.assertEqual(field.comodel_name, "clinic.postcare.plan")

    def test_28_request_doctor_contract(self):
        field = self.env["clinic.feedback.request"]._fields["doctor_id"]
        self.assertEqual(field.comodel_name, "clinic.doctor")

    def test_29_request_staff_contract(self):
        field = self.env["clinic.feedback.request"]._fields["staff_id"]
        self.assertEqual(field.comodel_name, "clinic.staff")

    def test_30_request_treatment_contract(self):
        field = self.env["clinic.feedback.request"]._fields["treatment_id"]
        self.assertEqual(field.comodel_name, "clinic.treatment")

    def test_31_request_workflow_complete(self):
        selection = dict(
            self.env["clinic.feedback.request"]._fields["state"].selection
        )
        for value in (
            "draft",
            "ready",
            "sent",
            "opened",
            "submitted",
            "expired",
            "revoked",
        ):
            self.assertIn(value, selection)

    def test_32_request_expiry_is_stored(self):
        field = self.env["clinic.feedback.request"]._fields["expires_at"]
        self.assertTrue(field.store)
        self.assertTrue(field.index)

    def test_33_request_is_expired_searchable(self):
        field = self.env["clinic.feedback.request"]._fields["is_expired"]
        self.assertTrue(field.store)
        self.assertTrue(field.index)

    def test_34_request_token_exists_and_indexed(self):
        field = self.env["clinic.feedback.request"]._fields["access_token"]
        self.assertTrue(field.index)

    def test_35_request_public_submission_method_exists(self):
        self.assertTrue(
            hasattr(self.env["clinic.feedback.request"], "submit_public")
        )

    def test_36_request_token_lookup_method_exists(self):
        self.assertTrue(
            hasattr(self.env["clinic.feedback.request"], "sudo_find_by_token")
        )

    def test_37_request_expiry_cron_method_exists(self):
        self.assertTrue(
            hasattr(self.env["clinic.feedback.request"], "_cron_expire_requests")
        )

    def test_38_request_source_automation_method_exists(self):
        self.assertTrue(
            hasattr(self.env["clinic.feedback.request"], "_cron_auto_create_requests")
        )

    def test_39_feedback_request_contract(self):
        field = self.env["clinic.feedback"]._fields["request_id"]
        self.assertEqual(field.comodel_name, "clinic.feedback.request")

    def test_40_feedback_booking_link_contract(self):
        field = self.env["clinic.feedback"]._fields["booking_feedback_link_id"]
        self.assertEqual(field.comodel_name, "booking.feedback.link")

    def test_41_feedback_survey_contract(self):
        field = self.env["clinic.feedback"]._fields["survey_id"]
        self.assertEqual(field.comodel_name, "clinic.feedback.survey")

    def test_42_feedback_patient_contract(self):
        field = self.env["clinic.feedback"]._fields["patient_id"]
        self.assertEqual(field.comodel_name, "res.partner")

    def test_43_feedback_patient_card_contract(self):
        field = self.env["clinic.feedback"]._fields["patient_card_id"]
        self.assertEqual(field.comodel_name, "clinic.patient")

    def test_44_feedback_doctor_contract(self):
        field = self.env["clinic.feedback"]._fields["doctor_id"]
        self.assertEqual(field.comodel_name, "clinic.doctor")

    def test_45_feedback_staff_contract(self):
        field = self.env["clinic.feedback"]._fields["staff_id"]
        self.assertEqual(field.comodel_name, "clinic.staff")

    def test_46_feedback_source_traceability_fields(self):
        model = self.env["clinic.feedback"]
        expected = {
            "booking_id": "booking.booking",
            "queue_id": "clinic.queue",
            "encounter_id": "clinic.encounter",
            "postcare_plan_id": "clinic.postcare.plan",
        }
        for field_name, comodel in expected.items():
            self.assertEqual(model._fields[field_name].comodel_name, comodel)

    def test_47_feedback_types_complete(self):
        selection = dict(self.env["clinic.feedback"]._fields["feedback_type"].selection)
        for value in ("satisfaction", "compliment", "suggestion", "complaint"):
            self.assertIn(value, selection)

    def test_48_feedback_workflow_complete(self):
        selection = dict(self.env["clinic.feedback"]._fields["state"].selection)
        for value in (
            "draft",
            "submitted",
            "under_review",
            "escalated",
            "closed",
        ):
            self.assertIn(value, selection)

    def test_49_feedback_nps_class_complete(self):
        selection = dict(self.env["clinic.feedback"]._fields["nps_class"].selection)
        for value in (
            "not_applicable",
            "detractor",
            "passive",
            "promoter",
        ):
            self.assertIn(value, selection)

    def test_50_feedback_satisfaction_percent_searchable(self):
        field = self.env["clinic.feedback"]._fields["satisfaction_percent"]
        self.assertTrue(field.store)
        self.assertTrue(field.index)

    def test_51_feedback_nps_class_searchable(self):
        field = self.env["clinic.feedback"]._fields["nps_class"]
        self.assertTrue(field.store)
        self.assertTrue(field.index)

    def test_52_feedback_needs_escalation_searchable(self):
        field = self.env["clinic.feedback"]._fields["needs_escalation"]
        self.assertTrue(field.store)
        self.assertTrue(field.index)

    def test_53_feedback_answer_contract(self):
        field = self.env["clinic.feedback"]._fields["answer_ids"]
        self.assertEqual(field.comodel_name, "clinic.feedback.answer")

    def test_54_feedback_escalation_contract(self):
        field = self.env["clinic.feedback"]._fields["escalation_ids"]
        self.assertEqual(field.comodel_name, "clinic.feedback.escalation")

    def test_55_feedback_request_factory_exists(self):
        self.assertTrue(
            hasattr(self.env["clinic.feedback"], "create_from_request")
        )

    def test_56_feedback_booking_factory_exists(self):
        self.assertTrue(
            hasattr(self.env["clinic.feedback"], "create_from_booking_link")
        )

    def test_57_answer_feedback_contract(self):
        field = self.env["clinic.feedback.answer"]._fields["feedback_id"]
        self.assertEqual(field.comodel_name, "clinic.feedback")

    def test_58_answer_question_contract(self):
        field = self.env["clinic.feedback.answer"]._fields["question_id"]
        self.assertEqual(field.comodel_name, "clinic.feedback.question")

    def test_59_answer_survey_snapshot_stored(self):
        field = self.env["clinic.feedback.answer"]._fields["survey_id"]
        self.assertTrue(field.store)
        self.assertEqual(field.comodel_name, "clinic.feedback.survey")

    def test_60_answer_company_snapshot_stored(self):
        field = self.env["clinic.feedback.answer"]._fields["company_id"]
        self.assertTrue(field.store)
        self.assertEqual(field.comodel_name, "res.company")

    def test_61_escalation_feedback_contract(self):
        field = self.env["clinic.feedback.escalation"]._fields["feedback_id"]
        self.assertEqual(field.comodel_name, "clinic.feedback")

    def test_62_escalation_patient_snapshot_stored(self):
        field = self.env["clinic.feedback.escalation"]._fields["patient_id"]
        self.assertTrue(field.store)
        self.assertEqual(field.comodel_name, "res.partner")

    def test_63_escalation_owner_contract(self):
        field = self.env["clinic.feedback.escalation"]._fields["owner_staff_id"]
        self.assertEqual(field.comodel_name, "clinic.staff")

    def test_64_escalation_workflow_complete(self):
        selection = dict(
            self.env["clinic.feedback.escalation"]._fields["state"].selection
        )
        for value in (
            "open",
            "acknowledged",
            "in_progress",
            "resolved",
            "cancelled",
        ):
            self.assertIn(value, selection)

    def test_65_escalation_severity_complete(self):
        selection = dict(
            self.env["clinic.feedback.escalation"]._fields["severity"].selection
        )
        for value in ("low", "medium", "high", "critical"):
            self.assertIn(value, selection)

    def test_66_escalation_category_complete(self):
        selection = dict(
            self.env["clinic.feedback.escalation"]._fields["category"].selection
        )
        for value in (
            "service",
            "doctor",
            "staff",
            "waiting",
            "facility",
            "communication",
            "billing",
            "postcare",
            "other",
        ):
            self.assertIn(value, selection)

    def test_67_escalation_overdue_searchable(self):
        field = self.env["clinic.feedback.escalation"]._fields["is_overdue"]
        self.assertTrue(field.store)
        self.assertTrue(field.index)

    def test_68_escalation_persisted_overdue_stamp_exists(self):
        field = self.env["clinic.feedback.escalation"]._fields["overdue_marked_at"]
        self.assertTrue(field.index)

    def test_69_escalation_cron_method_exists(self):
        self.assertTrue(
            hasattr(self.env["clinic.feedback.escalation"], "_cron_mark_overdue")
        )

    def test_70_booking_request_relationship_exists(self):
        field = self.env["booking.booking"]._fields["clinic_feedback_request_ids"]
        self.assertEqual(field.comodel_name, "clinic.feedback.request")

    def test_71_booking_request_action_exists(self):
        self.assertTrue(
            hasattr(
                self.env["booking.booking"],
                "action_create_clinic_feedback_request",
            )
        )

    def test_72_encounter_request_relationship_exists(self):
        field = self.env["clinic.encounter"]._fields["feedback_request_ids"]
        self.assertEqual(field.comodel_name, "clinic.feedback.request")

    def test_73_encounter_request_action_exists(self):
        self.assertTrue(
            hasattr(self.env["clinic.encounter"], "action_create_feedback_request")
        )

    def test_74_postcare_request_relationship_exists(self):
        field = self.env["clinic.postcare.plan"]._fields["feedback_request_ids"]
        self.assertEqual(field.comodel_name, "clinic.feedback.request")

    def test_75_postcare_request_action_exists(self):
        self.assertTrue(
            hasattr(self.env["clinic.postcare.plan"], "action_create_feedback_request")
        )

    def test_76_patient_feedback_metrics_exist(self):
        model = self.env["clinic.patient"]
        for field in (
            "clinic_feedback_count",
            "clinic_feedback_open_escalation_count",
            "clinic_feedback_avg_rating",
        ):
            self.assertIn(field, model._fields)

    def test_77_patient_feedback_action_exists(self):
        self.assertTrue(
            hasattr(self.env["clinic.patient"], "action_open_clinic_feedback")
        )

    def test_78_doctor_feedback_metrics_exist(self):
        model = self.env["clinic.doctor"]
        for field in (
            "clinic_feedback_count",
            "clinic_feedback_avg_rating",
            "clinic_feedback_nps",
        ):
            self.assertIn(field, model._fields)

    def test_79_doctor_feedback_action_exists(self):
        self.assertTrue(
            hasattr(self.env["clinic.doctor"], "action_open_clinic_feedback")
        )

    def test_80_staff_feedback_metrics_exist(self):
        model = self.env["clinic.staff"]
        for field in (
            "clinic_feedback_ids",
            "clinic_feedback_count",
            "clinic_feedback_avg_rating",
        ):
            self.assertIn(field, model._fields)

    def test_81_staff_feedback_action_exists(self):
        self.assertTrue(
            hasattr(self.env["clinic.staff"], "action_open_clinic_feedback")
        )

    def test_82_partner_booking_feedback_fields_preserved(self):
        model = self.env["res.partner"]
        self.assertIn("feedback_count", model._fields)
        self.assertIn("feedback_avg_rating", model._fields)

    def test_83_partner_feedback_compute_preserved(self):
        self.assertTrue(
            hasattr(self.env["res.partner"], "_compute_feedback_stats")
        )

    def test_84_company_feedback_settings_exist(self):
        model = self.env["res.company"]
        for field in (
            "clinic_feedback_default_survey_id",
            "clinic_feedback_default_owner_staff_id",
            "clinic_feedback_low_rating_threshold",
            "clinic_feedback_nps_escalation_threshold",
            "clinic_feedback_escalation_sla_hours",
            "clinic_feedback_auto_from_encounter",
            "clinic_feedback_auto_from_postcare",
            "clinic_feedback_auto_send",
            "clinic_feedback_source_lookback_days",
        ):
            self.assertIn(field, model._fields)

    def test_85_security_groups_exist(self):
        for xmlid in (
            "clinic_feedback.group_feedback_user",
            "clinic_feedback.group_feedback_coordinator",
            "clinic_feedback.group_feedback_reviewer",
            "clinic_feedback.group_feedback_manager",
        ):
            self.assertTrue(self.env.ref(xmlid))

    def test_86_security_hierarchy(self):
        user = self.env.ref("clinic_feedback.group_feedback_user")
        coordinator = self.env.ref("clinic_feedback.group_feedback_coordinator")
        reviewer = self.env.ref("clinic_feedback.group_feedback_reviewer")
        manager = self.env.ref("clinic_feedback.group_feedback_manager")
        self.assertIn(user, coordinator.implied_ids)
        self.assertIn(coordinator, reviewer.implied_ids)
        self.assertIn(reviewer, manager.implied_ids)

    def test_87_owned_models_have_search_views(self):
        for model in OWNED_MODELS:
            view = self.env["ir.ui.view"].search(
                [("model", "=", model), ("type", "=", "search")],
                limit=1,
            )
            self.assertTrue(view, model)

    def test_88_owned_models_have_list_views(self):
        for model in OWNED_MODELS:
            view = self.env["ir.ui.view"].search(
                [("model", "=", model), ("type", "=", "list")],
                limit=1,
            )
            self.assertTrue(view, model)

    def test_89_owned_models_have_form_views(self):
        for model in OWNED_MODELS:
            view = self.env["ir.ui.view"].search(
                [("model", "=", model), ("type", "=", "form")],
                limit=1,
            )
            self.assertTrue(view, model)

    def test_90_search_views_follow_clinicone_odoo19_contract(self):
        xmlids = (
            "clinic_feedback.view_feedback_survey_search",
            "clinic_feedback.view_feedback_question_search",
            "clinic_feedback.view_feedback_request_search",
            "clinic_feedback.view_feedback_search",
            "clinic_feedback.view_feedback_answer_search",
            "clinic_feedback.view_feedback_escalation_search",
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

    def test_91_feedback_pivot_exists(self):
        view = self.env.ref("clinic_feedback.view_feedback_pivot")
        self.assertEqual(view.model, "clinic.feedback")
        self.assertEqual(view.type, "pivot")

    def test_92_feedback_graph_exists(self):
        view = self.env.ref("clinic_feedback.view_feedback_graph")
        self.assertEqual(view.model, "clinic.feedback")
        self.assertEqual(view.type, "graph")

    def test_93_feedback_summary_report_exists(self):
        report = self.env.ref("clinic_feedback.action_report_feedback_summary")
        self.assertEqual(report.model, "clinic.feedback")

    def test_94_feedback_mail_template_exists(self):
        template = self.env.ref("clinic_feedback.mail_template_feedback_request")
        self.assertEqual(template.model, "clinic.feedback.request")

    def test_95_feedback_expiry_cron_exists(self):
        self.assertTrue(self.env.ref("clinic_feedback.cron_feedback_expire_requests"))

    def test_96_feedback_source_cron_exists(self):
        self.assertTrue(
            self.env.ref("clinic_feedback.cron_feedback_auto_create_requests")
        )

    def test_97_feedback_sla_cron_exists(self):
        self.assertTrue(
            self.env.ref("clinic_feedback.cron_feedback_overdue_escalations")
        )

    def test_98_feedback_settings_action_is_local(self):
        action = self.env.ref("clinic_feedback.action_feedback_settings")
        self.assertEqual(action.res_model, "res.config.settings")
        self.assertIn("clinic_feedback", action.context or "")

    def test_99_public_form_template_exists(self):
        self.assertTrue(self.env.ref("clinic_feedback.public_feedback_form"))

    def test_100_public_thank_you_template_exists(self):
        self.assertTrue(self.env.ref("clinic_feedback.public_feedback_thank_you"))

    def test_101_public_unavailable_template_exists(self):
        self.assertTrue(self.env.ref("clinic_feedback.public_feedback_unavailable"))

    def test_102_no_parallel_booking_feedback_model(self):
        self.assertNotIn("clinic.feedback.booking.link", self.env.registry)

    def test_103_no_parallel_patient_model(self):
        self.assertNotIn("clinic.feedback.patient", self.env.registry)

    def test_104_no_parallel_incident_model(self):
        self.assertNotIn("clinic.feedback.incident", self.env.registry)

    def test_105_no_parallel_dashboard_model(self):
        self.assertNotIn("clinic.feedback.dashboard", self.env.registry)

    def test_106_canonical_overall_rating_is_optional_storage(self):
        field = self.env["clinic.feedback"]._fields["overall_rating"]
        self.assertFalse(field.required)

    def test_107_answer_create_method_is_hardened(self):
        self.assertTrue(hasattr(self.env["clinic.feedback.answer"], "create"))

    def test_108_doctor_nps_field_exists(self):
        field = self.env["clinic.doctor"]._fields["clinic_feedback_nps"]
        self.assertEqual(field.type, "float")

    def test_109_feedback_escalation_has_cancel_action(self):
        self.assertTrue(
            hasattr(self.env["clinic.feedback.escalation"], "action_cancel")
        )

