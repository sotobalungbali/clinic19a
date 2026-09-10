
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import datetime


class ClinicTreatmentSession(models.Model):
    """Core execution model for ClinicOne treatment workflow."""

    _name = "clinic.treatment.session"
    _description = "Clinic Treatment Session"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_datetime desc, id desc"
    _rec_name = "display_name"
    _check_company_auto = True

    name = fields.Char(string="Session Number", required=True, copy=False, default="New", readonly=True, tracking=True, index=True)
    display_name = fields.Char(compute="_compute_display_name", store=True)
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True, tracking=True)
    color = fields.Integer()

    patient_id = fields.Many2one("res.partner", string="Patient", required=True, index=True, tracking=True, domain=[("is_patient", "=", True)])
    patient_phone = fields.Char(related="patient_id.phone", readonly=True)
    patient_email = fields.Char(related="patient_id.email", readonly=True)
    clinic_doctor_id = fields.Many2one("hr.employee", string="Doctor / Therapist", index=True, tracking=True)
    doctor_user_id = fields.Many2one("res.users", related="clinic_doctor_id.user_id", readonly=True)
    treatment_id = fields.Many2one("clinic.treatment", string="Treatment", index=True, tracking=True)
    booking_id = fields.Many2one("booking.booking", string="Booking", index=True, tracking=True)
    booking_state = fields.Selection(related="booking_id.state", string="Booking Status", readonly=True)
    room_id = fields.Many2one("booking.room", string="Room / Device", index=True, tracking=True)

    start_datetime = fields.Datetime(required=True, index=True, tracking=True)
    end_datetime = fields.Datetime(required=True, index=True, tracking=True)
    duration_planned = fields.Float(string="Planned Duration (min)", default=0.0, tracking=True)
    duration_actual = fields.Float(string="Actual Duration (min)", compute="_compute_duration_actual", store=True)
    is_overtime = fields.Boolean(compute="_compute_is_overtime", store=True, index=True)

    state = fields.Selection([
        ("draft", "Draft"), ("confirmed", "Confirmed"),
        ("in_progress", "In Progress"), ("done", "Done"),
        ("no_show", "No-show"), ("cancelled", "Cancelled"),
    ], default="draft", required=True, index=True, tracking=True, copy=False)
    stage_id = fields.Many2one("clinic.treatment.session.stage", index=True, tracking=True)
    can_edit = fields.Boolean(compute="_compute_can_edit")

    note_internal = fields.Text()
    note_public = fields.Text()
    chief_complaint = fields.Text()
    objective_notes = fields.Text()
    assessment = fields.Text()
    plan = fields.Text()
    contraindication_flag = fields.Boolean(tracking=True)
    cancellation_reason = fields.Text()
    no_show_reason = fields.Text()

    line_ids = fields.One2many("clinic.treatment.session.line", "session_id", copy=True)
    billing_invoice_id = fields.Many2one("clinic.billing.invoice", copy=False, index=True)
    move_id = fields.Many2one("account.move", string="Accounting Invoice", copy=False, index=True)
    attachment_count = fields.Integer(compute="_compute_attachment_count")
    activity_count = fields.Integer(compute="_compute_activity_count")

    _name_company_unique = models.Constraint(
        "UNIQUE (name, company_id)",
        "Treatment Session Number must be unique per company.",
    )
    _planned_duration_nonnegative = models.Constraint(
        "CHECK (duration_planned >= 0)",
        "Planned Duration cannot be negative.",
    )

    @api.depends("name", "patient_id", "treatment_id")
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.name or _("New")]
            if rec.patient_id:
                parts.append(rec.patient_id.display_name)
            if rec.treatment_id:
                parts.append(rec.treatment_id.display_name)
            rec.display_name = " - ".join(parts)

    @api.depends("state", "start_datetime", "end_datetime")
    def _compute_duration_actual(self):
        for rec in self:
            if rec.start_datetime and rec.end_datetime and rec.state == "done":
                start = fields.Datetime.to_datetime(rec.start_datetime)
                end = fields.Datetime.to_datetime(rec.end_datetime)
                rec.duration_actual = max((end - start).total_seconds() / 60.0, 0.0)
            else:
                rec.duration_actual = 0.0

    @api.depends("duration_actual", "duration_planned", "state")
    def _compute_is_overtime(self):
        for rec in self:
            rec.is_overtime = bool(
                rec.state == "done" and rec.duration_planned > 0
                and rec.duration_actual > rec.duration_planned
            )

    def _compute_can_edit(self):
        manager = self.env.user.has_group("clinic_treatment_session.group_treatment_session_manager")
        for rec in self:
            rec.can_edit = manager or rec.state in ("draft", "confirmed")

    def _compute_attachment_count(self):
        Attachment = self.env["ir.attachment"]
        for rec in self:
            rec.attachment_count = Attachment.search_count([
                ("res_model", "=", self._name), ("res_id", "=", rec.id)
            ])

    def _compute_activity_count(self):
        for rec in self:
            rec.activity_count = len(rec.activity_ids)

    @api.constrains("start_datetime", "end_datetime")
    def _check_dates(self):
        for rec in self:
            if rec.start_datetime and rec.end_datetime and rec.end_datetime <= rec.start_datetime:
                raise ValidationError(_("End datetime must be after start datetime."))

    @api.constrains("company_id", "booking_id", "room_id")
    def _check_company_consistency(self):
        for rec in self:
            for related in (rec.booking_id, rec.room_id):
                if related and "company_id" in related._fields and related.company_id and related.company_id != rec.company_id:
                    raise ValidationError(_("Related operational records must use the same company."))

    @api.model_create_multi
    def create(self, vals_list):
        Stage = self.env["clinic.treatment.session.stage"]
        normalized = []
        for incoming in vals_list:
            vals = dict(incoming)
            if not vals.get("name") or vals.get("name") in ("New", "/"):
                vals["name"] = self.env["ir.sequence"].next_by_code("clinic_treatment_session.session") or "New"
            if not vals.get("stage_id"):
                stage = Stage.get_default_stage(
                    vals.get("state") or "draft",
                    vals.get("company_id") or self.env.company.id,
                )
                if stage:
                    vals["stage_id"] = stage.id
            normalized.append(vals)
        records = super().create(normalized)
        records._subscribe_related_partners()
        return records

    def write(self, vals):
        if "state" in vals and not self.env.context.get("clinic_treatment_session_workflow"):
            for rec in self:
                if rec.state != vals["state"]:
                    raise ValidationError(_("Treatment Session status must be changed through workflow actions."))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.state not in ("draft", "cancelled", "no_show"):
                raise UserError(_("Only Draft, Cancelled, or No-show sessions can be deleted."))
        return super().unlink()

    def _subscribe_related_partners(self):
        for rec in self:
            partner_ids = [rec.patient_id.id] if rec.patient_id else []
            if rec.clinic_doctor_id and rec.clinic_doctor_id.work_contact_id:
                partner_ids.append(rec.clinic_doctor_id.work_contact_id.id)
            if partner_ids:
                rec.message_subscribe(partner_ids=list(set(partner_ids)))
        return True

    def action_view_attachments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Attachments"),
            "res_model": "ir.attachment", "view_mode": "list,form",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "context": {"default_res_model": self._name, "default_res_id": self.id},
        }

    def action_view_activities(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Activities"),
            "res_model": "mail.activity", "view_mode": "list,form",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
        }

    def action_view_patient(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Patient"),
            "res_model": "res.partner", "view_mode": "form", "res_id": self.patient_id.id,
        }

    def action_view_invoice(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("No Accounting Invoice is linked."))
        return {
            "type": "ir.actions.act_window", "name": _("Accounting Invoice"),
            "res_model": "account.move", "view_mode": "form", "res_id": self.move_id.id,
        }

    def reschedule(self, new_start, new_end=None, room_id=False, doctor_id=False):
        self.ensure_one()
        if self.state in ("done", "no_show", "cancelled"):
            raise UserError(_("You cannot reschedule a session that is Done, No-show, or Cancelled."))
        vals = {"start_datetime": new_start}
        if new_end:
            vals["end_datetime"] = new_end
        if room_id:
            vals["room_id"] = room_id
        if doctor_id:
            vals["clinic_doctor_id"] = doctor_id
        self.write(vals)
        return True
