# -*- coding: utf-8 -*-
"""Prescriber governance, co-sign and digital attestation for ClinicOne eMAR."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicDoctorEmarPrescriber(models.Model):
    _inherit = "clinic.doctor"

    is_prescriber = fields.Boolean(string="eMAR Prescriber Enabled", default=True, tracking=True)
    erx_enabled = fields.Boolean(string="Electronic Prescription Enabled", default=True, tracking=True)
    prescriber_license_no = fields.Char(string="Prescriber License No.", tracking=True)
    prescriber_license_expiry = fields.Date(string="Prescriber License Expiry", tracking=True)
    controlled_substance_enabled = fields.Boolean(string="Controlled Medication Authorization", tracking=True)
    controlled_permit_no = fields.Char(string="Controlled Medication Permit No.", tracking=True)
    controlled_permit_expiry = fields.Date(string="Controlled Medication Permit Expiry", tracking=True)
    allowed_product_ids = fields.Many2many(
        "product.product",
        "clinic_doctor_emar_allowed_product_rel",
        "doctor_id",
        "product_id",
        string="Allowed eMAR Products",
    )
    blocked_product_ids = fields.Many2many(
        "product.product",
        "clinic_doctor_emar_blocked_product_rel",
        "doctor_id",
        "product_id",
        string="Blocked eMAR Products",
    )
    allowed_category_ids = fields.Many2many(
        "product.category",
        "clinic_doctor_emar_allowed_category_rel",
        "doctor_id",
        "category_id",
        string="Allowed eMAR Categories",
    )
    blocked_category_ids = fields.Many2many(
        "product.category",
        "clinic_doctor_emar_blocked_category_rel",
        "doctor_id",
        "category_id",
        string="Blocked eMAR Categories",
    )
    requires_cosign = fields.Boolean(string="Requires Co-sign", tracking=True)
    cosign_policy = fields.Selection(
        [
            ("never", "Never"),
            ("always", "Always"),
            ("controlled", "Controlled Medications"),
            ("high_alert", "High-alert Medications"),
        ],
        default="never",
        required=True,
        tracking=True,
    )
    supervisor_doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Default Supervising Doctor",
        domain="[('id', '!=', id), ('company_id', '=', company_id)]",
        check_company=True,
        tracking=True,
    )
    emar_prescription_count = fields.Integer(compute="_compute_emar_counts")
    emar_order_count = fields.Integer(compute="_compute_emar_counts")
    is_prescriber_active = fields.Boolean(compute="_compute_prescriber_active", store=True)

    @api.depends("is_prescriber", "erx_enabled", "prescriber_license_expiry")
    def _compute_prescriber_active(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_prescriber_active = bool(
                rec.is_prescriber
                and rec.erx_enabled
                and (not rec.prescriber_license_expiry or rec.prescriber_license_expiry >= today)
            )

    def _compute_emar_counts(self):
        Prescription = self.env["clinic.emar.prescription"]
        Order = self.env["clinic.emar.order"]
        for rec in self:
            rec.emar_prescription_count = Prescription.search_count([("doctor_id", "=", rec.id)])
            rec.emar_order_count = Order.search_count([("clinic_doctor_id", "=", rec.id)])

    def _emar_profile_for_product(self, product):
        self.ensure_one()
        return self.env["clinic.emar.medication.profile"].search(
            [
                ("product_id", "=", product.id),
                ("company_id", "=", self.company_id.id),
                ("active", "=", True),
            ],
            limit=1,
        )

    def can_prescribe_product(self, product, on_date=None):
        self.ensure_one()
        on_date = on_date or fields.Date.context_today(self)
        license_no = self.prescriber_license_no or self.license_no
        if not self.is_prescriber or not self.erx_enabled:
            return False, _("Doctor is not enabled as an eMAR prescriber."), False
        if not license_no:
            return False, _("Doctor has no prescriber/professional license number."), False
        if self.prescriber_license_expiry and self.prescriber_license_expiry < on_date:
            return False, _("Prescriber license has expired."), False
        if product in self.blocked_product_ids or product.categ_id in self.blocked_category_ids:
            return False, _("Product is blocked by the prescriber's scope-of-practice policy."), False
        if self.allowed_product_ids and product not in self.allowed_product_ids:
            return False, _("Product is not in the prescriber's allowed-product list."), False
        if self.allowed_category_ids and product.categ_id not in self.allowed_category_ids:
            return False, _("Product category is outside the prescriber's allowed categories."), False

        profile = self._emar_profile_for_product(product)
        controlled = bool(profile and profile.controlled_level != "none")
        high_alert = bool(profile and profile.high_alert)
        if controlled:
            if not self.controlled_substance_enabled:
                return False, _("Controlled medication authorization is not enabled."), False
            if self.controlled_permit_expiry and self.controlled_permit_expiry < on_date:
                return False, _("Controlled medication authorization has expired."), False

        need_cosign = bool(self.requires_cosign or self.cosign_policy == "always")
        if self.cosign_policy == "controlled" and controlled:
            need_cosign = True
        if self.cosign_policy == "high_alert" and high_alert:
            need_cosign = True
        return True, "", need_cosign

    def action_view_emar_prescriptions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("eMAR Prescriptions"),
            "res_model": "clinic.emar.prescription",
            "view_mode": "list,form",
            "domain": [("doctor_id", "=", self.id)],
            "context": {"default_doctor_id": self.id},
        }

    def action_view_emar_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("eMAR Orders"),
            "res_model": "clinic.emar.order",
            "view_mode": "list,form",
            "domain": [("clinic_doctor_id", "=", self.id)],
            "context": {"default_clinic_doctor_id": self.id},
        }


class EmarPrescriberGovernanceMixin(models.AbstractModel):
    _name = "clinic.emar.prescriber.governance.mixin"
    _description = "eMAR Prescriber Governance Helper"

    def _governance_doctor(self):
        self.ensure_one()
        return self.doctor_id if self._name == "clinic.emar.prescription" else self.clinic_doctor_id

    def _governance_lines(self):
        self.ensure_one()
        return self.line_ids

    def _run_prescriber_check_values(self):
        self.ensure_one()
        doctor = self._governance_doctor()
        if not doctor:
            return "blocked", False, [_('No Clinic Doctor has been selected.')]
        blocked = []
        needs_cosign = False
        for line in self._governance_lines().filtered(lambda ln: ln.product_id):
            allowed, reason, line_cosign = doctor.can_prescribe_product(line.product_id)
            if not allowed:
                blocked.append(_("%s: %s") % (line.product_id.display_name, reason))
            needs_cosign = needs_cosign or line_cosign
        return ("blocked" if blocked else ("warning" if needs_cosign else "ok")), needs_cosign, blocked

    def _current_user_clinic_doctor(self):
        return self.env["clinic.doctor"].search(
            [
                ("user_id", "=", self.env.user.id),
                ("company_id", "=", self.env.company.id),
                ("is_prescriber", "=", True),
            ],
            limit=1,
        )


class ClinicEmarPrescriptionPrescriberGovernance(models.Model):
    _name = "clinic.emar.prescription"
    _inherit = ["clinic.emar.prescription", "clinic.emar.prescriber.governance.mixin"]

    prescriber_check_state = fields.Selection(
        [("pending", "Pending"), ("ok", "OK"), ("warning", "Co-sign Required"), ("blocked", "Blocked")],
        default="pending",
        required=True,
        tracking=True,
        index=True,
    )
    prescriber_check_note = fields.Text(readonly=True, copy=False)
    cosign_required = fields.Boolean(readonly=True, copy=False)
    cosigned_by_id = fields.Many2one("clinic.doctor", readonly=True, copy=False, check_company=True)
    cosigned_on = fields.Datetime(readonly=True, copy=False)
    signed_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    signed_on = fields.Datetime(readonly=True, copy=False)

    def action_run_prescriber_checks(self):
        for rec in self:
            state, need_cosign, blocked = rec._run_prescriber_check_values()
            rec.write({
                "prescriber_check_state": state,
                "prescriber_check_note": "\n".join(blocked),
                "cosign_required": need_cosign,
            })
        return True

    def _run_prescriber_gate(self):
        for rec in self:
            rec.action_run_prescriber_checks()
            if rec.prescriber_check_state == "blocked":
                raise UserError(_("Prescription is blocked by prescriber governance:\n%s") % (rec.prescriber_check_note or ""))
            if rec.cosign_required and not rec.cosigned_by_id:
                raise UserError(_("This prescription requires a supervising doctor co-sign before validation."))
        return True

    def action_cosign(self):
        for rec in self:
            signer = rec._current_user_clinic_doctor()
            if not signer:
                raise UserError(_("Your user is not linked to an enabled Clinic Doctor prescriber."))
            if signer == rec.doctor_id:
                raise UserError(_("The prescribing doctor cannot co-sign their own prescription."))
            if rec.doctor_id.supervisor_doctor_id and signer != rec.doctor_id.supervisor_doctor_id:
                raise UserError(_("Only the configured supervising doctor may co-sign this prescription."))
            rec.write({"cosigned_by_id": signer.id, "cosigned_on": fields.Datetime.now()})
        return True

    def action_digital_sign(self):
        for rec in self:
            doctor = rec._current_user_clinic_doctor()
            if doctor != rec.doctor_id:
                raise UserError(_("Only the prescribing doctor's linked user may digitally attest this prescription."))
            rec.write({"signed_by_id": self.env.user.id, "signed_on": fields.Datetime.now()})
        return True


class ClinicEmarOrderPrescriberGovernance(models.Model):
    _name = "clinic.emar.order"
    _inherit = ["clinic.emar.order", "clinic.emar.prescriber.governance.mixin"]

    prescriber_check_state = fields.Selection(
        [("pending", "Pending"), ("ok", "OK"), ("warning", "Co-sign Required"), ("blocked", "Blocked")],
        default="pending",
        required=True,
        tracking=True,
        index=True,
    )
    prescriber_check_note = fields.Text(readonly=True, copy=False)
    cosign_required = fields.Boolean(readonly=True, copy=False)
    cosigned_by_id = fields.Many2one("clinic.doctor", readonly=True, copy=False, check_company=True)
    cosigned_on = fields.Datetime(readonly=True, copy=False)
    signed_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    signed_on = fields.Datetime(readonly=True, copy=False)
    controlled_present = fields.Boolean(compute="_compute_medication_flags", store=True, index=True)
    high_alert_present = fields.Boolean(compute="_compute_medication_flags", store=True, index=True)

    @api.depends("line_ids.profile_id.controlled_level", "line_ids.profile_id.high_alert")
    def _compute_medication_flags(self):
        for rec in self:
            rec.controlled_present = any(
                ln.profile_id and ln.profile_id.controlled_level != "none" for ln in rec.line_ids
            )
            rec.high_alert_present = any(ln.profile_id and ln.profile_id.high_alert for ln in rec.line_ids)

    def action_run_prescriber_checks(self):
        for rec in self:
            state, need_cosign, blocked = rec._run_prescriber_check_values()
            rec.write({
                "prescriber_check_state": state,
                "prescriber_check_note": "\n".join(blocked),
                "cosign_required": need_cosign,
            })
        return True

    def _run_prescriber_gate(self):
        for rec in self:
            rec.action_run_prescriber_checks()
            if rec.prescriber_check_state == "blocked":
                raise UserError(_("Order is blocked by prescriber governance:\n%s") % (rec.prescriber_check_note or ""))
            if rec.cosign_required and not rec.cosigned_by_id:
                raise UserError(_("This order requires a supervising doctor co-sign before approval."))
        return True

    def action_cosign(self):
        for rec in self:
            signer = rec._current_user_clinic_doctor()
            if not signer:
                raise UserError(_("Your user is not linked to an enabled Clinic Doctor prescriber."))
            if signer == rec.clinic_doctor_id:
                raise UserError(_("The prescribing doctor cannot co-sign their own order."))
            supervisor = rec.clinic_doctor_id.supervisor_doctor_id if rec.clinic_doctor_id else False
            if supervisor and signer != supervisor:
                raise UserError(_("Only the configured supervising doctor may co-sign this order."))
            rec.write({"cosigned_by_id": signer.id, "cosigned_on": fields.Datetime.now()})
        return True

    def action_digital_sign(self):
        for rec in self:
            doctor = rec._current_user_clinic_doctor()
            if doctor != rec.clinic_doctor_id:
                raise UserError(_("Only the prescribing doctor's linked user may digitally attest this order."))
            rec.write({"signed_by_id": self.env.user.id, "signed_on": fields.Datetime.now()})
        return True
