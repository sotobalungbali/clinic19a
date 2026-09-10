# -*- coding: utf-8 -*-
"""Owned, dependency-safe backlinks from ClinicOne clinical source models to eMAR."""
from odoo import api, fields, models, _


class ClinicPatientEmarBridge(models.Model):
    _inherit = "clinic.patient"

    emar_barcode = fields.Char(string="eMAR Patient Barcode", copy=False, index=True, tracking=True)
    emar_prescription_count = fields.Integer(compute="_compute_emar_counts")
    emar_order_count = fields.Integer(compute="_compute_emar_counts")
    emar_administration_count = fields.Integer(compute="_compute_emar_counts")
    emar_open_alert_count = fields.Integer(compute="_compute_emar_counts")

    _emar_barcode_company_unique = models.Constraint(
        "UNIQUE(emar_barcode, company_id)",
        "eMAR patient barcode must be unique per company.",
    )

    def _compute_emar_counts(self):
        Prescription = self.env["clinic.emar.prescription"]
        Order = self.env["clinic.emar.order"]
        Administration = self.env["clinic.emar.administration"]
        Alert = self.env["clinic.emar.alert"]
        for rec in self:
            rec.emar_prescription_count = Prescription.search_count([("patient_id", "=", rec.id)])
            rec.emar_order_count = Order.search_count([("clinic_patient_id", "=", rec.id)])
            rec.emar_administration_count = Administration.search_count([("patient_id", "=", rec.id)])
            rec.emar_open_alert_count = Alert.search_count([("patient_id", "=", rec.id), ("state", "in", ("open", "ack"))])

    def action_view_emar_prescriptions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Prescriptions"),
            "res_model": "clinic.emar.prescription", "view_mode": "list,form",
            "domain": [("patient_id", "=", self.id)],
            "context": {"default_patient_id": self.id},
        }

    def action_view_emar_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("eMAR Orders"),
            "res_model": "clinic.emar.order", "view_mode": "list,form",
            "domain": [("clinic_patient_id", "=", self.id)],
            "context": {"default_clinic_patient_id": self.id, "default_patient_id": self.partner_id.id if self.partner_id else False},
        }

    def action_view_emar_administrations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Medication Administrations"),
            "res_model": "clinic.emar.administration", "view_mode": "list,form",
            "domain": [("patient_id", "=", self.id)], "context": {"create": False},
        }

    def action_view_emar_alerts(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Medication Alerts"),
            "res_model": "clinic.emar.alert", "view_mode": "list,form",
            "domain": [("patient_id", "=", self.id)], "context": {"create": False},
        }


class ClinicEncounterEmarBridge(models.Model):
    _inherit = "clinic.encounter"

    emar_prescription_ids = fields.One2many("clinic.emar.prescription", "encounter_id", string="eMAR Prescriptions", readonly=True)
    emar_order_ids = fields.One2many("clinic.emar.order", "encounter_id", string="eMAR Orders", readonly=True)
    emar_prescription_count = fields.Integer(compute="_compute_emar_counts")
    emar_order_count = fields.Integer(compute="_compute_emar_counts")

    @api.depends("emar_prescription_ids", "emar_order_ids")
    def _compute_emar_counts(self):
        for rec in self:
            rec.emar_prescription_count = len(rec.emar_prescription_ids)
            rec.emar_order_count = len(rec.emar_order_ids)

    def action_view_emar_prescriptions(self):
        self.ensure_one()
        patient = self.patient_id if "patient_id" in self._fields else False
        return {
            "type": "ir.actions.act_window", "name": _("Encounter Prescriptions"),
            "res_model": "clinic.emar.prescription", "view_mode": "list,form",
            "domain": [("encounter_id", "=", self.id)],
            "context": {"default_encounter_id": self.id, "default_patient_id": patient.id if patient else False},
        }

    def action_view_emar_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Encounter eMAR Orders"),
            "res_model": "clinic.emar.order", "view_mode": "list,form",
            "domain": [("encounter_id", "=", self.id)], "context": {"default_encounter_id": self.id},
        }


class BookingEmarBridge(models.Model):
    _inherit = "booking.booking"

    emar_prescription_ids = fields.One2many("clinic.emar.prescription", "booking_id", string="eMAR Prescriptions", readonly=True)
    emar_order_ids = fields.One2many("clinic.emar.order", "booking_id", string="eMAR Orders", readonly=True)
    emar_prescription_count = fields.Integer(compute="_compute_emar_counts")
    emar_order_count = fields.Integer(compute="_compute_emar_counts")

    @api.depends("emar_prescription_ids", "emar_order_ids")
    def _compute_emar_counts(self):
        for rec in self:
            rec.emar_prescription_count = len(rec.emar_prescription_ids)
            rec.emar_order_count = len(rec.emar_order_ids)

    def action_view_emar_prescriptions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Booking Prescriptions"),
            "res_model": "clinic.emar.prescription", "view_mode": "list,form",
            "domain": [("booking_id", "=", self.id)], "context": {"default_booking_id": self.id},
        }

    def action_view_emar_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Booking eMAR Orders"),
            "res_model": "clinic.emar.order", "view_mode": "list,form",
            "domain": [("booking_id", "=", self.id)], "context": {"default_booking_id": self.id},
        }

