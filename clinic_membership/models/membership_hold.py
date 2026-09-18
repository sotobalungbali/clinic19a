


# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class MembershipHold(models.Model):
    """Auditable hold/freeze request governed by the purchased plan policy."""

    _name = "membership.hold"
    _description = "Membership Hold / Freeze"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "membership.workflow.mixin",
        "membership.event.mixin",
    ]
    _order = "date_from desc, id desc"

    name = fields.Char(
        string="Hold Reference",
        required=True,
        copy=False,
        index=True,
        default=lambda self: self._next_name(),
        tracking=True,
    )
    contract_id = fields.Many2one(
        "membership.contract",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    plan_id = fields.Many2one(
        related="contract_id.plan_id", store=True, readonly=True
    )
    partner_id = fields.Many2one(
        related="contract_id.partner_id", store=True, readonly=True
    )
    patient_id = fields.Many2one(
        related="contract_id.patient_id", store=True, readonly=True
    )
    company_id = fields.Many2one(
        related="contract_id.company_id", store=True, readonly=True, index=True
    )

    date_from = fields.Date(required=True, tracking=True)
    date_to = fields.Date(required=True, tracking=True)
    days = fields.Integer(compute="_compute_days", store=True)
    reason = fields.Text(required=True)
    policy_allow_hold = fields.Boolean(readonly=True)
    policy_max_days = fields.Integer(readonly=True)

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("applied", "Applied"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
            ("reverted", "Reverted"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )
    requested_by = fields.Many2one(
        "res.users", default=lambda self: self.env.user, readonly=True
    )
    submitted_by = fields.Many2one("res.users", readonly=True)
    approved_by = fields.Many2one("res.users", readonly=True)
    rejected_by = fields.Many2one("res.users", readonly=True)
    cancelled_by = fields.Many2one("res.users", readonly=True)
    reverted_by = fields.Many2one("res.users", readonly=True)
    submitted_on = fields.Datetime(readonly=True)
    approved_on = fields.Datetime(readonly=True)
    rejected_on = fields.Datetime(readonly=True)
    cancelled_on = fields.Datetime(readonly=True)
    applied_on = fields.Datetime(readonly=True)
    reverted_on = fields.Datetime(readonly=True)

    contract_state_saved = fields.Selection(
        [
            ("draft", "Draft"),
            ("awaiting_payment", "Awaiting Payment"),
            ("active", "Active"),
            ("on_hold", "On Hold"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
            ("renewed", "Renewed"),
        ],
        readonly=True,
    )
    contract_end_before = fields.Date(readonly=True)
    notes = fields.Text()

    _reference_company_uniq = models.Constraint(
        "UNIQUE(company_id, name)",
        "Membership hold reference must be unique per company.",
    )

    @api.model
    def _next_name(self):
        return self.env["ir.sequence"].next_by_code("membership.hold") or "/"

    @api.depends("date_from", "date_to")
    def _compute_days(self):
        for rec in self:
            rec.days = (
                (rec.date_to - rec.date_from).days + 1
                if rec.date_from and rec.date_to and rec.date_to >= rec.date_from
                else 0
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("name", self._next_name())
        return super().create(vals_list)

    def write(self, vals):
        self._membership_guard_direct_state_write(vals)
        protected = {"contract_id", "date_from", "date_to", "reason"}
        if protected.intersection(vals) and any(
            rec.state in ("applied", "reverted", "rejected", "cancelled")
            for rec in self
        ):
            raise UserError(_("Historical hold requests are immutable."))
        return super().write(vals)

    def unlink(self):
        if any(rec.state != "draft" for rec in self):
            raise UserError(_("Only Draft hold requests can be deleted."))
        return super().unlink()

    @api.constrains("date_from", "date_to")
    def _check_date_range(self):
        for rec in self:
            if rec.date_to < rec.date_from:
                raise ValidationError(_("Hold To cannot be earlier than Hold From."))

    @api.constrains("contract_id", "date_from", "date_to", "state")
    def _check_overlap(self):
        for rec in self:
            if rec.state in ("rejected", "cancelled", "reverted"):
                continue
            if self.search_count(
                [
                    ("id", "!=", rec.id),
                    ("contract_id", "=", rec.contract_id.id),
                    ("state", "in", ("submitted", "approved", "applied")),
                    ("date_from", "<=", rec.date_to),
                    ("date_to", ">=", rec.date_from),
                ]
            ):
                raise ValidationError(
                    _("Another non-cancelled hold overlaps this contract period.")
                )

    def _check_policy(self):
        self.ensure_one()
        if self.contract_id.state not in ("active", "on_hold"):
            raise UserError(_("Only Active/On Hold membership contracts support Hold requests."))
        if not self.plan_id.allow_hold:
            raise UserError(_("The membership plan does not allow Hold/Freeze."))
        if self.days <= 0:
            raise UserError(_("Hold duration must be greater than zero."))
        max_days = self.plan_id.max_hold_days_per_term or 0
        if max_days and self.contract_id.total_hold_days + self.days > max_days:
            raise UserError(
                _("This request would exceed the plan's %s-day hold limit.") % max_days
            )
        if self.contract_id.start_date and self.date_from < self.contract_id.start_date:
            raise UserError(_("Hold From cannot be before contract Start Date."))
        return True

    def action_submit(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only Draft hold requests can be submitted."))
            rec._check_policy()
            rec._membership_write_state(
                {
                    "state": "submitted",
                    "policy_allow_hold": rec.plan_id.allow_hold,
                    "policy_max_days": rec.plan_id.max_hold_days_per_term,
                    "submitted_by": rec.env.user.id,
                    "submitted_on": fields.Datetime.now(),
                }
            )
            rec._membership_publish_event(
                "hold.submitted",
                {"hold_id": rec.id, "contract_id": rec.contract_id.id},
            )
        return True

    def action_approve(self):
        for rec in self:
            if rec.state != "submitted":
                raise UserError(_("Only Submitted hold requests can be approved."))
            rec._check_policy()
            rec._membership_write_state(
                {
                    "state": "approved",
                    "approved_by": rec.env.user.id,
                    "approved_on": fields.Datetime.now(),
                }
            )
        return True

    def action_apply(self):
        for rec in self:
            if rec.state != "approved":
                raise UserError(_("Only Approved hold requests can be applied."))
            rec._check_policy()
            if rec.contract_id.state != "active":
                raise UserError(_("The membership contract must be Active before applying a hold."))
            saved_state = rec.contract_id.state
            saved_end = rec.contract_id.end_date
            rec.contract_id.action_set_on_hold(rec.date_from, rec.date_to)
            rec._membership_write_state(
                {
                    "state": "applied",
                    "contract_state_saved": saved_state,
                    "contract_end_before": saved_end,
                    "applied_on": fields.Datetime.now(),
                }
            )
            rec._membership_publish_event(
                "hold.applied",
                {
                    "hold_id": rec.id,
                    "contract_id": rec.contract_id.id,
                    "days": rec.days,
                },
            )
        return True

    def action_reject(self):
        for rec in self:
            if rec.state not in ("submitted", "approved"):
                raise UserError(_("Only Submitted/Approved hold requests can be rejected."))
            rec._membership_write_state(
                {
                    "state": "rejected",
                    "rejected_by": rec.env.user.id,
                    "rejected_on": fields.Datetime.now(),
                }
            )
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state == "applied":
                raise UserError(_("Applied holds must be Reverted, not Cancelled."))
            if rec.state in ("cancelled", "rejected", "reverted"):
                continue
            rec._membership_write_state(
                {
                    "state": "cancelled",
                    "cancelled_by": rec.env.user.id,
                    "cancelled_on": fields.Datetime.now(),
                }
            )
        return True

    def action_revert(self):
        for rec in self:
            if rec.state != "applied":
                raise UserError(_("Only Applied hold requests can be reverted."))
            contract = rec.contract_id
            if contract.state == "on_hold":
                contract.action_resume()
            values = {
                "total_hold_days": max(contract.total_hold_days - rec.days, 0),
            }
            if rec.contract_end_before:
                values["end_date"] = rec.contract_end_before
            contract.write(values)
            rec._membership_write_state(
                {
                    "state": "reverted",
                    "reverted_by": rec.env.user.id,
                    "reverted_on": fields.Datetime.now(),
                }
            )
            rec._membership_publish_event(
                "hold.reverted",
                {"hold_id": rec.id, "contract_id": rec.contract_id.id},
            )
        return True

    def action_view_contract(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Membership Contract"),
            "res_model": "membership.contract",
            "view_mode": "form",
            "res_id": self.contract_id.id,
        }


