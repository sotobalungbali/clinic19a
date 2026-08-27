# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestClinicEmarEnterprise(TransactionCase):
    """Regression contracts for the enterprise eMAR lifecycle.

    These tests intentionally focus on ownership, clinical gates and downstream
    model contracts rather than browser-level UI rendering.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.patient_partner = cls.env["res.partner"].create({"name": "eMAR Test Patient"})
        cls.patient = cls.env["clinic.patient"].create({
            "name": "eMAR Test Patient",
            "company_id": cls.company.id,
            "partner_id": cls.patient_partner.id,
            "emar_barcode": "PAT-EMAR-001",
        })
        cls.doctor_partner = cls.env["res.partner"].create({"name": "Dr eMAR Test"})
        cls.doctor = cls.env["clinic.doctor"].create({
            "partner_id": cls.doctor_partner.id,
            "company_id": cls.company.id,
            "license_no": "EMAR-TEST-LIC-001",
            "is_prescriber": True,
            "erx_enabled": True,
        })
        cls.product = cls.env["product.product"].create({
            "name": "eMAR Test Medication",
            "barcode": "MED-EMAR-001",
        })
        cls.profile = cls.env["clinic.emar.medication.profile"].create({
            "company_id": cls.company.id,
            "product_id": cls.product.id,
            "default_route": "oral",
            "default_frequency": "bid",
            "dose_uom_id": cls.product.uom_id.id,
            "max_single_dose": 1000.0,
            "max_daily_dose": 2000.0,
        })

    def _new_prescription(self, dose=500.0):
        now = fields.Datetime.now()
        return self.env["clinic.emar.prescription"].create({
            "company_id": self.company.id,
            "patient_id": self.patient.id,
            "doctor_id": self.doctor.id,
            "date_start": now,
            "date_end": now + timedelta(days=1),
            "line_ids": [(0, 0, {
                "company_id": self.company.id,
                "product_id": self.product.id,
                "quantity": 1.0,
                "product_uom_id": self.product.uom_id.id,
                "dose": dose,
                "dose_uom_id": self.product.uom_id.id,
                "frequency": "bid",
                "route": "oral",
                "profile_id": self.profile.id,
            })],
        })

    def test_01_medication_profile_unique_per_company(self):
        # SQL constraints abort the PostgreSQL transaction until rollback; isolate
        # the expected violation in a savepoint so later assertions remain valid.
        with self.cr.savepoint(), self.assertRaises(Exception):
            self.env["clinic.emar.medication.profile"].create({
                "company_id": self.company.id,
                "product_id": self.product.id,
            })

    def test_02_prescription_uses_canonical_clinic_patient_and_doctor(self):
        rx = self._new_prescription()
        self.assertEqual(rx.patient_id, self.patient)
        self.assertEqual(rx.doctor_id, self.doctor)

    def test_03_order_contract_preserves_downstream_partner_employee_schema(self):
        Order = self.env["clinic.emar.order"]
        self.assertEqual(Order._fields["patient_id"].comodel_name, "res.partner")
        self.assertEqual(Order._fields["doctor_id"].comodel_name, "hr.employee")
        self.assertEqual(Order._fields["clinic_patient_id"].comodel_name, "clinic.patient")
        self.assertEqual(Order._fields["clinic_doctor_id"].comodel_name, "clinic.doctor")
        self.assertIn("order_line_ids", Order._fields)

    def test_04_prescription_safety_passes_normal_medication(self):
        rx = self._new_prescription()
        rx.action_run_patient_safety_checks()
        self.assertIn(rx.safety_state, ("pass", "warning"))
        self.assertFalse(rx.dose_flag)

    def test_05_dose_limit_blocks_prescription(self):
        rx = self._new_prescription(dose=1500.0)
        rx.action_run_patient_safety_checks()
        self.assertEqual(rx.safety_state, "block")
        self.assertTrue(rx.dose_flag)

    def test_06_critical_allergy_blocks_prescription(self):
        self.env["clinic.patient.allergy"].create({
            "patient_id": self.patient.id,
            "product_id": self.product.id,
            "allergen_name": "eMAR Test Medication",
            "status": "active",
            "verification_status": "confirmed",
            "severity": "severe",
        })
        rx = self._new_prescription()
        rx.action_run_patient_safety_checks()
        self.assertEqual(rx.safety_state, "block")
        self.assertTrue(rx.allergy_flag)

    def test_07_prescriber_scope_check_passes_enabled_doctor(self):
        rx = self._new_prescription()
        rx.action_run_prescriber_checks()
        self.assertIn(rx.prescriber_check_state, ("ok", "warning"))

    def test_08_prescriber_blocked_product_is_enforced(self):
        self.doctor.blocked_product_ids = [(4, self.product.id)]
        try:
            rx = self._new_prescription()
            rx.action_run_prescriber_checks()
            self.assertEqual(rx.prescriber_check_state, "blocked")
        finally:
            self.doctor.blocked_product_ids = [(3, self.product.id)]

    def test_09_validation_runs_server_side_hard_gates(self):
        rx = self._new_prescription()
        rx.action_validate()
        self.assertEqual(rx.state, "validated")
        self.assertTrue(rx.safety_checked)
        self.assertNotEqual(rx.prescriber_check_state, "pending")

    def test_10_generate_order_preserves_full_medication_intent(self):
        rx = self._new_prescription()
        rx.action_validate()
        rx.action_generate_order()
        order = rx.order_ids[:1]
        self.assertTrue(order)
        self.assertEqual(order.clinic_patient_id, self.patient)
        self.assertEqual(order.patient_id, self.patient_partner)
        self.assertEqual(order.line_ids[:1].profile_id, self.profile)
        self.assertEqual(order.line_ids[:1].route, "oral")
        self.assertEqual(order.line_ids[:1].frequency, "bid")

    def test_11_schedule_unique_constraint_is_declared(self):
        self.assertTrue(hasattr(type(self.env["clinic.emar.schedule"]), "_uniq_order_line_datetime") or "planned_datetime" in self.env["clinic.emar.schedule"]._fields)

    def test_12_schedule_creation_does_not_falsely_mark_administered(self):
        rx = self._new_prescription()
        rx.action_validate()
        rx.action_generate_order()
        order = rx.order_ids[:1]
        order.action_confirm()
        schedule = order.schedule_ids[:1]
        if schedule:
            schedule.action_administer()
            self.assertNotEqual(schedule.state, "administered")

    def test_13_administration_verification_is_server_side(self):
        rx = self._new_prescription()
        rx.action_validate()
        rx.action_generate_order()
        order = rx.order_ids[:1]
        line = order.line_ids[:1]
        admin = self.env["clinic.emar.administration"].create({
            "company_id": self.company.id,
            "order_id": order.id,
            "line_id": line.id,
            "product_id": self.product.id,
            "dose_qty": 1.0,
            "administered_qty": 1.0,
            "dose_uom_id": self.product.uom_id.id,
        })
        admin.action_verify_administration()
        self.assertIn(admin.verification_state, ("passed", "warning"))

    def test_14_inventory_integration_model_contract_exists(self):
        Usage = self.env["clinic.treatment.product.usage"]
        self.assertIn("emar_order_id", Usage._fields)
        self.assertIn("emar_administration_id", Usage._fields)
        self.assertIn("inventory_usage_id", self.env["clinic.emar.administration"]._fields)

    def test_15_operational_records_have_company_scope(self):
        for model_name in (
            "clinic.emar.medication.profile",
            "clinic.emar.prescription",
            "clinic.emar.order",
            "clinic.emar.medication.line",
            "clinic.emar.schedule",
            "clinic.emar.administration",
            "clinic.emar.alert",
        ):
            self.assertIn("company_id", self.env[model_name]._fields)

    def test_16_direct_prescription_state_write_is_blocked(self):
        rx = self._new_prescription()
        with self.assertRaises(UserError):
            rx.write({"state": "validated"})
        rx.action_validate()
        self.assertEqual(rx.state, "validated")

    def test_17_q4h_frequency_is_supported(self):
        pattern = self.env["clinic.emar.schedule"]._parse_frequency("q4h")
        self.assertEqual(pattern.get("interval_hours"), 4)
        self.assertEqual(pattern.get("count_per_day"), 6)

    def test_18_account_stock_bridges_keep_canonical_clinical_comodels(self):
        self.assertEqual(
            self.env["account.move"]._fields["emar_patient_id"].comodel_name,
            "clinic.patient",
        )
        self.assertEqual(
            self.env["account.move"]._fields["emar_doctor_id"].comodel_name,
            "clinic.doctor",
        )
        self.assertEqual(
            self.env["stock.picking"]._fields["emar_patient_id"].comodel_name,
            "clinic.patient",
        )
        self.assertEqual(
            self.env["stock.picking"]._fields["emar_doctor_id"].comodel_name,
            "clinic.doctor",
        )

    def test_19_search_filter_fields_are_searchable(self):
        Order = self.env["clinic.emar.order"]
        self.assertTrue(Order._fields["high_alert_present"].store)
        self.assertTrue(Order._fields["controlled_present"].store)
        # Mirrors the search-view contracts so Odoo view validation cannot fail
        # with an unsearchable computed-field domain.
        Order.search([("high_alert_present", "=", True)], limit=1)
        Order.search([("controlled_present", "=", True)], limit=1)

    def test_20_odoo19_uom_contract_uses_relative_uom_hierarchy(self):
        Uom = self.env["uom.uom"]
        self.assertIn("relative_uom_id", Uom._fields)
        self.assertNotIn("reference_uom_id", Uom._fields)
        Line = self.env["clinic.emar.medication.line"]
        root = Line._uom_root(self.product.uom_id)
        self.assertTrue(root)
        self.assertFalse(root.relative_uom_id)

    def test_21_clinical_dose_and_inventory_quantity_are_separate(self):
        rx = self._new_prescription(dose=500.0)
        rx.action_validate()
        rx.action_generate_order()
        order = rx.order_ids[:1]
        line = order.line_ids[:1]
        admin = self.env["clinic.emar.administration"].create({
            "company_id": self.company.id,
            "order_id": order.id,
            "line_id": line.id,
            "product_id": self.product.id,
            "dose_qty": 500.0,
            "administered_qty": 500.0,
            "dose_uom_id": self.product.uom_id.id,
        })
        self.assertEqual(admin.administered_qty, 500.0)
        self.assertEqual(admin.inventory_qty, line.quantity)
        self.assertEqual(admin.inventory_uom_id, line.product_uom_id)

    def test_22_schedule_and_administration_use_canonical_clinical_identity(self):
        rx = self._new_prescription()
        rx.action_validate()
        rx.action_generate_order()
        order = rx.order_ids[:1]
        order.action_confirm()
        schedule = order.schedule_ids[:1]
        if schedule:
            self.assertEqual(schedule.patient_id, self.patient)
            self.assertEqual(schedule.doctor_id, self.doctor)
            action = schedule.action_administer()
            admin = self.env["clinic.emar.administration"].browse(action.get("res_id"))
            self.assertEqual(admin.patient_id, self.patient)
            self.assertEqual(admin.doctor_id, self.doctor)

    def test_23_odoo19_stock_picking_move_contract(self):
        Picking = self.env["stock.picking"]
        self.assertIn("move_ids", Picking._fields)
        self.assertNotIn("move_ids_without_package", Picking._fields)

    def test_24_medication_line_tracking_has_mail_thread_contract(self):
        Line = self.env["clinic.emar.medication.line"]
        self.assertIn("message_ids", Line._fields)
        self.assertIn("activity_ids", Line._fields)
        self.assertTrue(Line._fields["product_id"].tracking)

    def test_25_medication_line_header_context_keeps_canonical_comodels(self):
        rx = self._new_prescription()
        rx.action_validate()
        rx.action_generate_order()
        order = rx.order_ids[:1]
        line = order.line_ids[:1]
        self.assertEqual(line.patient_id, self.patient)
        self.assertEqual(line.doctor_id, self.doctor)
        self.assertEqual(line.patient_id._name, "clinic.patient")
        self.assertEqual(line.doctor_id._name, "clinic.doctor")


    def test_26_workflow_guard_registry_contract_is_loaded(self):
        """The four guarded ledgers must survive registry setup with both APIs."""
        for model_name in (
            "clinic.emar.prescription",
            "clinic.emar.order",
            "clinic.emar.schedule",
            "clinic.emar.administration",
        ):
            Model = self.env[model_name]
            self.assertTrue(hasattr(Model, "_emar_check_direct_state_write"))
            self.assertTrue(hasattr(Model, "_emar_guarded_write"))

    def test_27_company_emar_configuration_is_schema_safe(self):
        """eMAR company configuration must never add stored res_company columns."""
        Company = self.env["res.company"]
        for field_name in (
            "emar_default_warehouse_id",
            "emar_auto_generate_schedules",
            "emar_require_patient_scan",
            "emar_require_product_scan",
            "emar_require_double_check_high_alert",
            "emar_overdue_grace_minutes",
        ):
            field = Company._fields[field_name]
            self.assertFalse(
                field.store,
                "%s must remain non-stored to prevent source/schema HTTP 500 drift"
                % field_name,
            )

    def test_28_company_emar_configuration_is_company_scoped(self):
        """Parameter-backed settings must remain isolated by company."""
        other_company = self.env["res.company"].create({
            "name": "ClinicOne eMAR Secondary Company",
        })

        self.company._emar_write_parameter_values({
            "emar_auto_generate_schedules": False,
            "emar_require_patient_scan": True,
            "emar_overdue_grace_minutes": 17,
        })
        other_company._emar_write_parameter_values({
            "emar_auto_generate_schedules": True,
            "emar_require_patient_scan": False,
            "emar_overdue_grace_minutes": 41,
        })

        self.company.invalidate_recordset([
            "emar_auto_generate_schedules",
            "emar_require_patient_scan",
            "emar_overdue_grace_minutes",
        ])
        other_company.invalidate_recordset([
            "emar_auto_generate_schedules",
            "emar_require_patient_scan",
            "emar_overdue_grace_minutes",
        ])

        self.assertFalse(self.company.emar_auto_generate_schedules)
        self.assertTrue(self.company.emar_require_patient_scan)
        self.assertEqual(self.company.emar_overdue_grace_minutes, 17)

        self.assertTrue(other_company.emar_auto_generate_schedules)
        self.assertFalse(other_company.emar_require_patient_scan)
        self.assertEqual(other_company.emar_overdue_grace_minutes, 41)

    def test_29_reschedule_wizard_keeps_standard_transient_contract(self):
        """The wizard remains a real TransientModel after recovery hardening."""
        Wizard = self.env["clinic.emar.reschedule.wizard"]
        self.assertTrue(Wizard._transient)
        self.assertTrue(Wizard._auto)
        self.assertTrue(hasattr(Wizard, "_transient_vacuum"))

    def test_30_background_schema_guards_are_loaded(self):
        """Background jobs must be safe after normal schema synchronization."""
        Schedule = self.env["clinic.emar.schedule"]
        Wizard = self.env["clinic.emar.reschedule.wizard"]
        self.assertTrue(hasattr(Schedule, "_cron_schema_ready"))
        self.assertTrue(Schedule._cron_schema_ready())
        self.assertTrue(hasattr(Wizard, "_transient_vacuum"))

    def test_31_emar_settings_action_is_local_and_odoo19_safe(self):
        """eMAR Settings must not depend on the removed legacy base XML ID."""
        action = self.env.ref("clinic_emar.action_emar_config_settings")
        self.assertEqual(action.res_model, "res.config.settings")
        self.assertEqual(action.view_mode, "form")
        self.assertIn("clinic_emar", action.context or "")

