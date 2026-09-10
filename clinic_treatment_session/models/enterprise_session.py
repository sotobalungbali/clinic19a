
# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicTreatmentSessionEnterprise(models.Model):
    """Enterprise overlay preserving the historical Treatment Session owner."""

    _inherit = "clinic.treatment.session"

    _workflow_states = {
        "draft": {"confirmed", "in_progress", "no_show", "cancelled"},
        "confirmed": {"in_progress", "no_show", "cancelled"},
        "in_progress": {"done", "cancelled"},
        "done": set(),
        "no_show": {"draft"},
        "cancelled": {"draft"},
    }

    branch_id = fields.Many2one(
        "clinic.branch", string="Branch", index=True, check_company=True,
        tracking=True, domain="[('company_id', '=', company_id)]",
    )
    clinic_patient_id = fields.Many2one(
        "clinic.patient", string="Clinic Patient",
        compute="_compute_canonical_links", store=True, index=True, readonly=True,
    )
    doctor_id = fields.Many2one(
        "clinic.doctor", string="Clinic Doctor", index=True,
        check_company=True, tracking=True,
    )
    encounter_id = fields.Many2one(
        "clinic.encounter", string="Encounter", index=True,
        check_company=True, tracking=True,
    )
    referral_id = fields.Many2one(
        "clinic.referral", string="Referral", index=True,
        check_company=True, tracking=True,
    )
    package_allocation_id = fields.Many2one(
        "clinic.package.allocation", string="Package Allocation",
        index=True, check_company=True, ondelete="restrict",
    )
    package_allocation_line_id = fields.Many2one(
        "clinic.package.allocation.line", string="Package Allocation Line",
        index=True, check_company=True, ondelete="restrict",
    )
    package_usage_id = fields.Many2one(
        "clinic.package.usage", string="Package Usage",
        compute="_compute_package_usage_id", readonly=True,
    )

    actual_start_datetime = fields.Datetime(
        string="Actual Start", tracking=True, copy=False, index=True,
    )
    actual_end_datetime = fields.Datetime(
        string="Actual End", tracking=True, copy=False, index=True,
    )
    execution_duration_minutes = fields.Float(
        compute="_compute_execution_metrics", store=True,
    )
    duration_variance_minutes = fields.Float(
        compute="_compute_execution_metrics", store=True,
    )

    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", store=True, readonly=True,
    )
    amount_untaxed = fields.Monetary(
        compute="_compute_session_amounts", store=True, currency_field="currency_id",
    )
    amount_total = fields.Monetary(
        compute="_compute_session_amounts", store=True, currency_field="currency_id",
    )
    billing_state = fields.Selection(
        related="billing_invoice_id.state", string="Billing Status", readonly=True,
    )
    is_fully_invoiced = fields.Boolean(
        compute="_compute_is_fully_invoiced", store=True,
    )

    line_count = fields.Integer(compute="_compute_operational_counts")
    consumed_line_count = fields.Integer(compute="_compute_operational_counts")
    billable_line_count = fields.Integer(compute="_compute_operational_counts")
    stock_move_count = fields.Integer(compute="_compute_operational_counts")
    audit_event_count = fields.Integer(compute="_compute_operational_counts")

    @api.depends("patient_id")
    def _compute_canonical_links(self):
        Patient = self.env["clinic.patient"]
        has_partner = "partner_id" in Patient._fields
        for rec in self:
            rec.clinic_patient_id = (
                Patient.search([("partner_id", "=", rec.patient_id.id)], limit=1)
                if rec.patient_id and has_partner
                else False
            )

    def _compute_package_usage_id(self):
        Usage = self.env["clinic.package.usage"]
        has_session = "treatment_session_id" in Usage._fields
        for rec in self:
            rec.package_usage_id = (
                Usage.search(
                    [("treatment_session_id", "=", rec.id)],
                    order="id desc", limit=1,
                )
                if has_session and rec.id
                else False
            )

    @api.depends("actual_start_datetime", "actual_end_datetime", "duration_planned")
    def _compute_execution_metrics(self):
        for rec in self:
            actual = 0.0
            if rec.actual_start_datetime and rec.actual_end_datetime:
                actual = max(
                    (
                        fields.Datetime.to_datetime(rec.actual_end_datetime)
                        - fields.Datetime.to_datetime(rec.actual_start_datetime)
                    ).total_seconds() / 60.0,
                    0.0,
                )
            rec.execution_duration_minutes = actual
            rec.duration_variance_minutes = (
                actual - rec.duration_planned if actual else 0.0
            )

    @api.depends(
        "line_ids.price_subtotal", "line_ids.price_total",
        "line_ids.is_billable", "line_ids.display_type",
    )
    def _compute_session_amounts(self):
        for rec in self:
            lines = rec.line_ids.filtered(
                lambda l: l.display_type == "line" and l.is_billable
            )
            rec.amount_untaxed = sum(lines.mapped("price_subtotal"))
            rec.amount_total = sum(lines.mapped("price_total"))

    @api.depends("billing_invoice_id", "billing_invoice_id.state")
    def _compute_is_fully_invoiced(self):
        for rec in self:
            invoice = rec.billing_invoice_id
            if not invoice:
                rec.is_fully_invoiced = False
                continue
            state = invoice.state if "state" in invoice._fields else False
            paid = bool(invoice.is_paid) if "is_paid" in invoice._fields else False
            rec.is_fully_invoiced = paid or state in ("paid", "done", "posted", "closed")

    def _compute_operational_counts(self):
        Audit = self.env["clinic.audit.event"]
        has_ref = "ref_model" in Audit._fields and "ref_res_id" in Audit._fields
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.consumed_line_count = len(rec.line_ids.filtered(lambda l: l.consumption_state == "consumed"))
            rec.billable_line_count = len(rec.line_ids.filtered(lambda l: l.display_type == "line" and l.is_billable))
            rec.stock_move_count = len(rec.line_ids.filtered("stock_move_id"))
            rec.audit_event_count = (
                Audit.search_count([("ref_model", "=", rec._name), ("ref_res_id", "=", rec.id)])
                if has_ref and rec.id else 0
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_enterprise_links_from_booking()
        records._sync_stage_with_state()
        return records

    def write(self, vals):
        if "state" in vals and self.env.context.get("clinic_treatment_session_workflow"):
            for rec in self:
                rec._check_state_transition(rec.state, vals["state"])
        res = super().write(vals)
        if set(vals) & {"booking_id", "patient_id", "clinic_doctor_id"}:
            self._sync_enterprise_links_from_booking()
        return res

    def _sync_enterprise_links_from_booking(self):
        for rec in self:
            booking = rec.booking_id
            if not booking:
                continue
            vals = {}
            for fname in (
                "doctor_id", "referral_id", "package_allocation_id",
                "package_allocation_line_id", "branch_id",
            ):
                if fname in booking._fields and booking[fname] and not rec[fname]:
                    if booking[fname]._name == rec._fields[fname].comodel_name:
                        vals[fname] = booking[fname].id
            if vals:
                rec.with_context(clinic_treatment_session_workflow=True).write(vals)
        return True

    def _sync_stage_with_state(self):
        Stage = self.env["clinic.treatment.session.stage"]
        for rec in self:
            stage = Stage.get_default_stage(rec.state, rec.company_id.id)
            if stage and rec.stage_id != stage:
                rec.with_context(clinic_treatment_session_workflow=True).write(
                    {"stage_id": stage.id}
                )
        return True

    def _check_state_transition(self, old_state, new_state):
        if old_state != new_state and new_state not in self._workflow_states.get(old_state, set()):
            raise ValidationError(
                _("Invalid Treatment Session transition: %s → %s.")
                % (old_state, new_state)
            )

    def _require_manager(self):
        if not self.env.user.has_group(
            "clinic_treatment_session.group_treatment_session_manager"
        ):
            raise AccessError(_("Treatment Session Manager access is required."))

    def _require_clinician(self):
        if not (
            self.env.user.has_group(
                "clinic_treatment_session.group_treatment_session_clinician"
            )
            or self.env.user.has_group(
                "clinic_treatment_session.group_treatment_session_manager"
            )
        ):
            raise AccessError(_("Treatment Session Clinician access is required."))

    def _check_operational_conflicts(self):
        Param = self.env["ir.config_parameter"].sudo()
        check_doctor = Param.get_param(
            "clinic_treatment_session.prevent_doctor_overlap", "1"
        ) in ("1", "True", "true")
        check_room = Param.get_param(
            "clinic_treatment_session.prevent_room_overlap", "1"
        ) in ("1", "True", "true")
        for rec in self:
            common = [
                ("id", "!=", rec.id),
                ("company_id", "=", rec.company_id.id),
                ("state", "in", ("confirmed", "in_progress")),
                ("start_datetime", "<", rec.end_datetime),
                ("end_datetime", ">", rec.start_datetime),
            ]
            if check_doctor and rec.doctor_id and self.search_count(
                common + [("doctor_id", "=", rec.doctor_id.id)]
            ):
                raise ValidationError(_("Clinic Doctor has an overlapping Treatment Session."))
            if check_room and rec.room_id and self.search_count(
                common + [("room_id", "=", rec.room_id.id)]
            ):
                raise ValidationError(_("Room has an overlapping Treatment Session."))

    def action_confirm(self):
        self._check_operational_conflicts()
        return super().action_confirm()

    def action_start(self):
        self._require_clinician()
        self._check_operational_conflicts()
        now = fields.Datetime.now()
        for rec in self:
            if rec.state in ("draft", "confirmed"):
                rec._workflow_write({
                    "state": "in_progress",
                    "actual_start_datetime": rec.actual_start_datetime or now,
                })
                rec._sync_stage_with_state()
        return True

    def action_done(self):
        self._require_clinician()
        now = fields.Datetime.now()
        for rec in self:
            if rec.state != "in_progress":
                raise ValidationError(_("Only an In Progress Treatment Session can be completed."))
            rec._workflow_write({"state": "done", "actual_end_datetime": now})
            rec._sync_stage_with_state()
            rec._post_done_hook()
        return True

    def action_reset_draft(self):
        self._require_manager()
        return super().action_reset_draft()

    @api.model
    def cron_mark_auto_no_show(self):
        Param = self.env["ir.config_parameter"].sudo()
        enabled = Param.get_param(
            "clinic_treatment_session.auto_no_show_enabled", "0"
        ) in ("1", "True", "true")
        if not enabled:
            return True
        try:
            hours = float(
                Param.get_param("clinic_treatment_session.auto_no_show_hours", "2")
            )
        except (TypeError, ValueError):
            hours = 2.0
        cutoff = (
            fields.Datetime.to_datetime(fields.Datetime.now())
            - timedelta(hours=max(hours, 0.0))
        )
        due = self.search([
            ("state", "in", ("draft", "confirmed")),
            ("start_datetime", "<=", cutoff),
        ], limit=200)
        for rec in due:
            rec._workflow_write({"state": "no_show"})
            rec._sync_stage_with_state()
        return True

    def _post_done_hook(self):
        result = super()._post_done_hook()
        Param = self.env["ir.config_parameter"].sudo()
        if Param.get_param(
            "clinic_treatment_session.auto_create_billing", "0"
        ) in ("1", "True", "true"):
            mode = Param.get_param(
                "clinic_treatment_session.billing_mode", "clinic_billing"
            )
            for rec in self:
                if mode == "clinic_billing" and not rec.billing_invoice_id:
                    rec.action_create_clinic_billing()
                elif mode == "account_invoice" and not rec.move_id:
                    rec.action_create_invoice()
        return result
