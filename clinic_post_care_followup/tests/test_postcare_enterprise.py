from lxml import etree

from odoo.tests.common import TransactionCase


OWNED_MODELS = (
    "clinic.postcare.protocol",
    "clinic.postcare.protocol.step",
    "clinic.postcare.plan",
    "clinic.postcare.task",
    "clinic.postcare.checkin",
    "clinic.postcare.escalation",
)


class TestClinicPostcareEnterprise(TransactionCase):

    def test_01_owned_models_exist(self):
        for model in OWNED_MODELS:
            self.assertIn(model, self.env.registry)

    def test_02_company_mixin_exists(self):
        self.assertIn("clinic.postcare.company.mixin", self.env.registry)

    def test_03_historical_staff_task_model_contract_exists(self):
        self.assertIn("clinic.postcare.task", self.env.registry)

    def test_04_staff_task_assignee_contract(self):
        field = self.env["clinic.postcare.task"]._fields["assignee_id"]
        self.assertEqual(field.comodel_name, "clinic.staff")

    def test_05_staff_postcare_counter_preserved(self):
        self.assertIn("postcare_task_count", self.env["clinic.staff"]._fields)

    def test_06_staff_postcare_action_preserved(self):
        self.assertTrue(hasattr(self.env["clinic.staff"], "action_open_postcare_tasks"))

    def test_07_staff_postcare_relationship_added(self):
        field = self.env["clinic.staff"]._fields["postcare_task_ids"]
        self.assertEqual(field.comodel_name, "clinic.postcare.task")

    def test_08_protocol_company_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.protocol"]._fields["company_id"].comodel_name,
            "res.company",
        )

    def test_09_protocol_branch_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.protocol"]._fields["branch_id"].comodel_name,
            "clinic.branch",
        )

    def test_10_protocol_treatment_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.protocol"]._fields["treatment_catalog_ids"].comodel_name,
            "clinic.treatment.catalog",
        )

    def test_11_protocol_procedure_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.protocol"]._fields["procedure_catalog_ids"].comodel_name,
            "clinic.procedure.catalog",
        )

    def test_12_protocol_care_protocol_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.protocol"]._fields["care_protocol_id"].comodel_name,
            "clinic.care.protocol",
        )

    def test_13_protocol_staff_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.protocol"]._fields["default_assignee_id"].comodel_name,
            "clinic.staff",
        )

    def test_14_protocol_workflow_complete(self):
        states = dict(self.env["clinic.postcare.protocol"]._fields["state"].selection)
        for value in ("draft", "active", "archived"):
            self.assertIn(value, states)

    def test_15_protocol_step_parent_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.protocol.step"]._fields["protocol_id"].comodel_name,
            "clinic.postcare.protocol",
        )

    def test_16_protocol_step_channels(self):
        selection = dict(self.env["clinic.postcare.protocol.step"]._fields["channel"].selection)
        for value in ("email", "phone", "internal", "manual"):
            self.assertIn(value, selection)

    def test_17_protocol_step_does_not_claim_sms_whatsapp_delivery(self):
        selection = dict(self.env["clinic.postcare.protocol.step"]._fields["channel"].selection)
        self.assertNotIn("sms", selection)
        self.assertNotIn("whatsapp", selection)

    def test_18_protocol_step_has_response_governance(self):
        model = self.env["clinic.postcare.protocol.step"]
        for field in ("requires_response", "response_due_hours", "escalate_if_overdue", "escalation_after_hours"):
            self.assertIn(field, model._fields)

    def test_19_plan_patient_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.plan"]._fields["patient_id"].comodel_name,
            "clinic.patient",
        )

    def test_20_plan_partner_snapshot_stored(self):
        field = self.env["clinic.postcare.plan"]._fields["partner_id"]
        self.assertEqual(field.comodel_name, "res.partner")
        self.assertTrue(field.store)

    def test_21_plan_doctor_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.plan"]._fields["doctor_id"].comodel_name,
            "clinic.doctor",
        )

    def test_22_plan_staff_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.plan"]._fields["responsible_staff_id"].comodel_name,
            "clinic.staff",
        )

    def test_23_plan_protocol_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.plan"]._fields["protocol_id"].comodel_name,
            "clinic.postcare.protocol",
        )

    def test_24_plan_encounter_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.plan"]._fields["encounter_id"].comodel_name,
            "clinic.encounter",
        )

    def test_25_plan_booking_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.plan"]._fields["booking_id"].comodel_name,
            "booking.booking",
        )

    def test_26_plan_care_plan_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.plan"]._fields["care_plan_id"].comodel_name,
            "clinic.care.plan",
        )

    def test_27_plan_treatment_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.plan"]._fields["treatment_id"].comodel_name,
            "clinic.treatment",
        )

    def test_28_plan_workflow_complete(self):
        states = dict(self.env["clinic.postcare.plan"]._fields["state"].selection)
        for value in ("draft", "active", "escalated", "completed", "closed", "cancelled"):
            self.assertIn(value, states)

    def test_29_plan_next_due_is_searchable(self):
        field = self.env["clinic.postcare.plan"]._fields["next_due_at"]
        self.assertTrue(field.store)
        self.assertTrue(field.index)

    def test_30_plan_instruction_acknowledgment_fields_exist(self):
        model = self.env["clinic.postcare.plan"]
        for field in ("instruction_acknowledged", "acknowledged_at", "acknowledged_by_id"):
            self.assertIn(field, model._fields)

    def test_31_plan_task_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.plan"]._fields["task_ids"].comodel_name,
            "clinic.postcare.task",
        )

    def test_32_plan_checkin_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.plan"]._fields["checkin_ids"].comodel_name,
            "clinic.postcare.checkin",
        )

    def test_33_plan_escalation_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.plan"]._fields["escalation_ids"].comodel_name,
            "clinic.postcare.escalation",
        )

    def test_34_task_plan_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.task"]._fields["plan_id"].comodel_name,
            "clinic.postcare.plan",
        )

    def test_35_task_patient_snapshot_stored(self):
        field = self.env["clinic.postcare.task"]._fields["patient_id"]
        self.assertTrue(field.store)
        self.assertEqual(field.comodel_name, "clinic.patient")

    def test_36_task_branch_snapshot_stored(self):
        field = self.env["clinic.postcare.task"]._fields["branch_id"]
        self.assertTrue(field.store)
        self.assertEqual(field.comodel_name, "clinic.branch")

    def test_37_task_workflow_complete(self):
        states = dict(self.env["clinic.postcare.task"]._fields["state"].selection)
        for value in ("pending", "scheduled", "due", "sent", "contacted", "completed", "overdue", "escalated", "cancelled"):
            self.assertIn(value, states)

    def test_38_task_is_overdue_searchable(self):
        field = self.env["clinic.postcare.task"]._fields["is_overdue"]
        self.assertTrue(field.store)
        self.assertTrue(field.index)

    def test_39_task_completed_on_time_searchable(self):
        field = self.env["clinic.postcare.task"]._fields["completed_on_time"]
        self.assertTrue(field.store)
        self.assertTrue(field.index)

    def test_40_task_send_evidence_fields_exist(self):
        model = self.env["clinic.postcare.task"]
        for field in ("sent_at", "contacted_at", "completed_at", "send_count"):
            self.assertIn(field, model._fields)

    def test_41_task_cron_method_exists(self):
        self.assertTrue(hasattr(self.env["clinic.postcare.task"], "_cron_process_due_tasks"))

    def test_42_checkin_plan_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.checkin"]._fields["plan_id"].comodel_name,
            "clinic.postcare.plan",
        )

    def test_43_checkin_task_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.checkin"]._fields["task_id"].comodel_name,
            "clinic.postcare.task",
        )

    def test_44_checkin_pain_constraint_field(self):
        self.assertIn("pain_score", self.env["clinic.postcare.checkin"]._fields)

    def test_45_checkin_red_flag_is_searchable(self):
        field = self.env["clinic.postcare.checkin"]._fields["red_flag"]
        self.assertTrue(field.store)
        self.assertTrue(field.index)

    def test_46_checkin_workflow_complete(self):
        states = dict(self.env["clinic.postcare.checkin"]._fields["state"].selection)
        for value in ("draft", "received", "reviewed", "escalated", "closed"):
            self.assertIn(value, states)

    def test_47_checkin_attention_signals_exist(self):
        model = self.env["clinic.postcare.checkin"]
        for field in ("wellbeing", "pain_score", "fever_reported", "unexpected_bleeding", "breathing_concern", "manual_red_flag"):
            self.assertIn(field, model._fields)

    def test_48_escalation_plan_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.escalation"]._fields["plan_id"].comodel_name,
            "clinic.postcare.plan",
        )

    def test_49_escalation_task_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.escalation"]._fields["task_id"].comodel_name,
            "clinic.postcare.task",
        )

    def test_50_escalation_checkin_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.escalation"]._fields["checkin_id"].comodel_name,
            "clinic.postcare.checkin",
        )

    def test_51_escalation_owner_contract(self):
        self.assertEqual(
            self.env["clinic.postcare.escalation"]._fields["owner_staff_id"].comodel_name,
            "clinic.staff",
        )

    def test_52_escalation_workflow_complete(self):
        states = dict(self.env["clinic.postcare.escalation"]._fields["state"].selection)
        for value in ("open", "acknowledged", "in_progress", "resolved", "cancelled"):
            self.assertIn(value, states)

    def test_53_escalation_severity_complete(self):
        selection = dict(self.env["clinic.postcare.escalation"]._fields["severity"].selection)
        for value in ("low", "medium", "high", "critical"):
            self.assertIn(value, selection)

    def test_54_patient_postcare_relationship_exists(self):
        self.assertEqual(
            self.env["clinic.patient"]._fields["postcare_plan_ids"].comodel_name,
            "clinic.postcare.plan",
        )

    def test_55_encounter_postcare_relationship_exists(self):
        self.assertEqual(
            self.env["clinic.encounter"]._fields["postcare_plan_ids"].comodel_name,
            "clinic.postcare.plan",
        )

    def test_56_encounter_create_action_exists(self):
        self.assertTrue(hasattr(self.env["clinic.encounter"], "action_create_postcare_plan"))

    def test_57_encounter_auto_helper_exists(self):
        self.assertTrue(hasattr(self.env["clinic.encounter"], "_ensure_postcare_plan"))

    def test_58_booking_postcare_relationship_exists(self):
        self.assertEqual(
            self.env["booking.booking"]._fields["postcare_plan_ids"].comodel_name,
            "clinic.postcare.plan",
        )

    def test_59_booking_create_action_exists(self):
        self.assertTrue(hasattr(self.env["booking.booking"], "action_create_postcare_plan"))

    def test_60_care_plan_postcare_relationship_exists(self):
        self.assertEqual(
            self.env["clinic.care.plan"]._fields["postcare_plan_ids"].comodel_name,
            "clinic.postcare.plan",
        )

    def test_61_care_plan_create_action_exists(self):
        self.assertTrue(hasattr(self.env["clinic.care.plan"], "action_create_postcare_plan"))

    def test_62_treatment_postcare_relationship_exists(self):
        self.assertEqual(
            self.env["clinic.treatment"]._fields["postcare_plan_ids"].comodel_name,
            "clinic.postcare.plan",
        )

    def test_63_company_settings_exist(self):
        company = self.env["res.company"]
        for field in (
            "clinic_postcare_default_protocol_id",
            "clinic_postcare_default_assignee_id",
            "clinic_postcare_auto_create_from_encounter",
            "clinic_postcare_auto_create_lookback_days",
            "clinic_postcare_pain_red_flag_threshold",
        ):
            self.assertIn(field, company._fields)

    def test_64_auto_create_cron_method_exists(self):
        self.assertTrue(
            hasattr(self.env["clinic.postcare.plan"], "_cron_auto_create_from_completed_encounters")
        )

    def test_65_security_groups_exist(self):
        for xmlid in (
            "clinic_post_care_followup.group_postcare_user",
            "clinic_post_care_followup.group_postcare_coordinator",
            "clinic_post_care_followup.group_postcare_clinician",
            "clinic_post_care_followup.group_postcare_manager",
        ):
            self.assertTrue(self.env.ref(xmlid))

    def test_66_security_hierarchy(self):
        coordinator = self.env.ref("clinic_post_care_followup.group_postcare_coordinator")
        clinician = self.env.ref("clinic_post_care_followup.group_postcare_clinician")
        manager = self.env.ref("clinic_post_care_followup.group_postcare_manager")
        self.assertIn(self.env.ref("clinic_post_care_followup.group_postcare_user"), coordinator.implied_ids)
        self.assertIn(coordinator, clinician.implied_ids)
        self.assertIn(clinician, manager.implied_ids)

    def test_67_owned_models_have_search_views(self):
        for model in OWNED_MODELS:
            self.assertTrue(
                self.env["ir.ui.view"].search([("model", "=", model), ("type", "=", "search")], limit=1),
                model,
            )

    def test_68_owned_models_have_list_views(self):
        for model in OWNED_MODELS:
            self.assertTrue(
                self.env["ir.ui.view"].search([("model", "=", model), ("type", "=", "list")], limit=1),
                model,
            )

    def test_69_owned_models_have_form_views(self):
        for model in OWNED_MODELS:
            self.assertTrue(
                self.env["ir.ui.view"].search([("model", "=", model), ("type", "=", "form")], limit=1),
                model,
            )

    def test_70_search_views_follow_clinicone_odoo19_contract(self):
        xmlids = (
            "clinic_post_care_followup.view_postcare_protocol_search",
            "clinic_post_care_followup.view_postcare_protocol_step_search",
            "clinic_post_care_followup.view_postcare_plan_search",
            "clinic_post_care_followup.view_postcare_task_search",
            "clinic_post_care_followup.view_postcare_checkin_search",
            "clinic_post_care_followup.view_postcare_escalation_search",
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

    def test_71_patient_instruction_report_exists(self):
        self.assertTrue(self.env.ref("clinic_post_care_followup.action_report_postcare_instructions"))

    def test_72_followup_summary_report_exists(self):
        self.assertTrue(self.env.ref("clinic_post_care_followup.action_report_postcare_summary"))

    def test_73_mail_template_exists(self):
        template = self.env.ref("clinic_post_care_followup.mail_template_postcare_task")
        self.assertEqual(template.model, "clinic.postcare.task")

    def test_74_due_task_cron_exists(self):
        self.assertTrue(self.env.ref("clinic_post_care_followup.cron_postcare_process_due_tasks"))

    def test_75_auto_create_cron_exists(self):
        self.assertTrue(self.env.ref("clinic_post_care_followup.cron_postcare_auto_create_encounters"))

    def test_76_settings_action_is_local(self):
        action = self.env.ref("clinic_post_care_followup.action_postcare_settings")
        self.assertEqual(action.res_model, "res.config.settings")
        self.assertIn("clinic_post_care_followup", action.context or "")

    def test_77_no_future_feedback_model_dependency(self):
        self.assertNotIn("clinic.postcare.feedback", self.env.registry)

    def test_78_no_parallel_incident_model(self):
        self.assertNotIn("clinic.postcare.incident", self.env.registry)

    def test_79_no_parallel_patient_model(self):
        self.assertNotIn("clinic.postcare.patient", self.env.registry)

    def test_80_no_parallel_encounter_model(self):
        self.assertNotIn("clinic.postcare.encounter", self.env.registry)

    def test_81_task_kanban_exists(self):
        view = self.env.ref("clinic_post_care_followup.view_postcare_task_kanban")
        self.assertEqual(view.model, "clinic.postcare.task")
        self.assertEqual(view.type, "kanban")

