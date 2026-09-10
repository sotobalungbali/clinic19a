# -*- coding: utf-8 -*-
# ClinicOne Billing — upstream navigation bridges.
# The extensions add only billing traceability; ownership stays in each upstream addon.

from odoo import api, fields, models, _


def _billing_action(model_name, domain, context=None, title=None):
    return {
        "type": "ir.actions.act_window",
        "name": title or _("Clinic Billing"),
        "res_model": model_name,
        "view_mode": "list,form",
        "domain": domain,
        "context": context or {},
        "target": "current",
    }


class ClinicPatientBillingBridge(models.Model):
    _inherit = "clinic.patient"

    billing_invoice_count = fields.Integer(compute="_compute_billing_invoice_count")

    def _compute_billing_invoice_count(self):
        Invoice = self.env["clinic.billing.invoice"]
        for rec in self:
            rec.billing_invoice_count = Invoice.search_count([("clinic_patient_id", "=", rec.id)])

    def action_view_billing_invoices(self):
        self.ensure_one()
        return _billing_action(
            "clinic.billing.invoice",
            [("clinic_patient_id", "=", self.id)],
            {"default_clinic_patient_id": self.id, "default_patient_id": self.partner_id.id},
            _("Patient Billing"),
        )


class ClinicDoctorBillingBridge(models.Model):
    _inherit = "clinic.doctor"

    billing_invoice_count = fields.Integer(compute="_compute_billing_invoice_count")

    def _compute_billing_invoice_count(self):
        Invoice = self.env["clinic.billing.invoice"]
        for rec in self:
            rec.billing_invoice_count = Invoice.search_count([("clinic_doctor_id", "=", rec.id)])

    def action_view_billing_invoices(self):
        self.ensure_one()
        return _billing_action(
            "clinic.billing.invoice",
            [("clinic_doctor_id", "=", self.id)],
            {"default_clinic_doctor_id": self.id},
            _("Doctor Billing"),
        )


class BookingBillingBridge(models.Model):
    _inherit = "booking.booking"

    billing_invoice_count = fields.Integer(compute="_compute_billing_invoice_count")

    def _compute_billing_invoice_count(self):
        Invoice = self.env["clinic.billing.invoice"]
        for rec in self:
            rec.billing_invoice_count = Invoice.search_count([("booking_id", "=", rec.id)])

    def action_view_billing_invoices(self):
        self.ensure_one()
        return _billing_action(
            "clinic.billing.invoice",
            [("booking_id", "=", self.id)],
            {
                "default_booking_id": self.id,
                "default_clinic_patient_id": self.patient_id.id,
                "default_clinic_doctor_id": self.doctor_id.id,
                "default_patient_id": self.patient_id.partner_id.id if self.patient_id.partner_id else False,
            },
            _("Booking Billing"),
        )


class EncounterBillingBridge(models.Model):
    _inherit = "clinic.encounter"

    billing_invoice_count = fields.Integer(compute="_compute_billing_invoice_count")

    def _compute_billing_invoice_count(self):
        Invoice = self.env["clinic.billing.invoice"]
        for rec in self:
            rec.billing_invoice_count = Invoice.search_count([("encounter_id", "=", rec.id)])

    def action_view_billing_invoices(self):
        self.ensure_one()
        return _billing_action(
            "clinic.billing.invoice",
            [("encounter_id", "=", self.id)],
            {
                "default_encounter_id": self.id,
                "default_clinic_patient_id": self.patient_id.id,
                "default_clinic_doctor_id": self.doctor_id.id,
                "default_patient_id": self.partner_id.id,
            },
            _("Encounter Billing"),
        )


class CarePlanBillingBridge(models.Model):
    _inherit = "clinic.care.plan"

    billing_document_count = fields.Integer(compute="_compute_billing_document_count")

    def _compute_billing_document_count(self):
        Invoice = self.env["clinic.billing.invoice"]
        for rec in self:
            rec.billing_document_count = Invoice.search_count([("care_plan_id", "=", rec.id)])

    def action_view_billing_documents(self):
        self.ensure_one()
        return _billing_action(
            "clinic.billing.invoice",
            [("care_plan_id", "=", self.id)],
            {
                "default_care_plan_id": self.id,
                "default_clinic_patient_id": self.patient_id.id,
                "default_clinic_doctor_id": self.doctor_id.id,
                "default_patient_id": self.patient_id.partner_id.id if self.patient_id.partner_id else False,
            },
            _("Care Plan Billing"),
        )


class PackageAllocationBillingBridge(models.Model):
    _inherit = "clinic.package.allocation"

    billing_document_count = fields.Integer(compute="_compute_billing_document_count")

    def _compute_billing_document_count(self):
        Invoice = self.env["clinic.billing.invoice"]
        for rec in self:
            rec.billing_document_count = Invoice.search_count([("package_allocation_id", "=", rec.id)])

    def action_view_billing_documents(self):
        self.ensure_one()
        return _billing_action(
            "clinic.billing.invoice",
            [("package_allocation_id", "=", self.id)],
            {
                "default_package_allocation_id": self.id,
                "default_clinic_patient_id": self.patient_id.id,
                "default_clinic_doctor_id": self.doctor_id.id if self.doctor_id else False,
                "default_patient_id": self.partner_id.id,
            },
            _("Package Billing"),
        )


class PackageUsageBillingBridge(models.Model):
    _inherit = "clinic.package.usage"

    billing_line_count = fields.Integer(compute="_compute_billing_line_count")

    def _compute_billing_line_count(self):
        Line = self.env["clinic.billing.line"]
        for rec in self:
            rec.billing_line_count = Line.search_count([("package_usage_id", "=", rec.id)])

    def action_view_billing_lines(self):
        self.ensure_one()
        return _billing_action(
            "clinic.billing.line",
            [("package_usage_id", "=", self.id)],
            {"default_package_usage_id": self.id},
            _("Package Redemption Billing"),
        )


class EmarAdministrationBillingBridge(models.Model):
    _inherit = "clinic.emar.administration"

    billing_line_count = fields.Integer(compute="_compute_billing_line_count")

    def _compute_billing_line_count(self):
        Line = self.env["clinic.billing.line"]
        for rec in self:
            rec.billing_line_count = Line.search_count([("emar_administration_id", "=", rec.id)])

    def action_view_billing_lines(self):
        self.ensure_one()
        return _billing_action(
            "clinic.billing.line",
            [("emar_administration_id", "=", self.id)],
            {"default_emar_administration_id": self.id},
            _("eMAR Billing"),
        )



