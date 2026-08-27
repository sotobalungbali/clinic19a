from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicPostcareEscalation(models.Model):
    """Internal clinical attention/escalation record for post-care follow-up."""

    _name = "clinic.postcare.escalation"
    _description = "Clinic Post-Care Escalation"
    _inherit = ["mail.thread", "mail.activity.mixin", "clinic.postcare.company.mixin"]
    _order = "severity desc, create_date desc, id desc"
    _check_company_auto = True

    _plan_state_idx = models.Index("(company_id, plan_id, state, severity)")
    _owner_state_idx = models.Index("(company_id, owner_staff_id, state, severity)")

    name = fields.Char(default="/", readonly=True, copy=False, index=True)
    plan_id = fields.Many2one(
        "clinic.postcare.plan",
        required=True,
        check_company=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    task_id = fields.Many2one(
        "clinic.postcare.task",
        check_company=True,
        ondelete="set null",
        index=True,
        domain="[('plan_id', '=', plan_id)]",
    )
    checkin_id = fields.Many2one(
        "clinic.postcare.checkin",
        check_company=True,
        ondelete="set null",
        index=True,
        domain="[('plan_id', '=', plan_id)]",
    )
    patient_id = fields.Many2one(
        related="plan_id.patient_id",
        store=True,
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        related="plan_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    branch_id = fields.Many2one(
        related="plan_id.branch_id",
        store=True,
        readonly=True,
        index=True,
    )
    encounter_id = fields.Many2one(
        related="plan_id.encounter_id",
        store=True,
        readonly=True,
    )

    severity = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        default="medium",
        required=True,
        tracking=True,
        index=True,
    )
    state = fields.Selection(
        [
            ("open", "Open"),
            ("acknowledged", "Acknowledged"),
            ("in_progress", "In Progress"),
            ("resolved", "Resolved"),
            ("cancelled", "Cancelled"),
        ],
        default="open",
        required=True,
        tracking=True,
        index=True,
    )
    reason = fields.Text(required=True, tracking=True)
    clinical_note = fields.Text()
    resolution_note = fields.Text()
    owner_staff_id = fields.Many2one(
        "clinic.staff",
        string="Clinical Owner",
        check_company=True,
        ondelete="set null",
        index=True,
        domain="[('company_id', '=', company_id), ('is_active', '=', True)]",
    )
    acknowledged_at = fields.Datetime(readonly=True)
    acknowledged_by_id = fields.Many2one("res.users", readonly=True)
    resolved_at = fields.Datetime(readonly=True)
    resolved_by_id = fields.Many2one("res.users", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            plan = self.env["clinic.postcare.plan"].browse(vals.get("plan_id"))
            company = plan.company_id if plan.exists() else self.env.company
            if vals.get("name") in (False, "/"):
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("clinic.postcare.escalation")
                    or "/"
                )
            prepared.append(vals)

        records = super().create(prepared)
        for record in records:
            record._schedule_owner_activity()
            if record.plan_id.state == "active":
                record.plan_id.with_context(postcare_transition=True).write({"state": "escalated"})
        return records

    @api.constrains("plan_id", "task_id", "checkin_id", "owner_staff_id")
    def _check_escalation_scope(self):
        for record in self:
            if record.task_id and record.task_id.plan_id != record.plan_id:
                raise ValidationError(_("Escalation Task must belong to the same Post-Care Plan."))
            if record.checkin_id and record.checkin_id.plan_id != record.plan_id:
                raise ValidationError(_("Escalation Check-in must belong to the same Post-Care Plan."))
            if (
                record.owner_staff_id
                and record.owner_staff_id.company_id != record.company_id
            ):
                raise ValidationError(_("Escalation owner must belong to the same company."))

    def write(self, vals):
        audit_fields = {
            "state",
            "acknowledged_at",
            "acknowledged_by_id",
            "resolved_at",
            "resolved_by_id",
        }
        if audit_fields.intersection(vals) and not self.env.context.get("postcare_transition"):
            raise AccessError(_("Use Escalation workflow actions to change status/audit evidence."))
        return super().write(vals)

    def _owner_user(self):
        self.ensure_one()
        if self.owner_staff_id and self.owner_staff_id.partner_id:
            user = self.env["res.users"].search(
                [("partner_id", "=", self.owner_staff_id.partner_id.id)],
                limit=1,
            )
            if user:
                return user
        if self.plan_id.doctor_id and self.plan_id.doctor_id.user_id:
            return self.plan_id.doctor_id.user_id
        return self.create_uid

    # Every new escalation creates an accountable internal activity for its clinical owner.
    def _schedule_owner_activity(self):
        for record in self:
            user = record._owner_user()
            record.activity_schedule(
                "mail.mail_activity_data_todo",
                date_deadline=fields.Date.context_today(record),
                user_id=user.id,
                summary=_("Post-Care Escalation: %s") % record.patient_id.display_name,
                note=record.reason or "",
            )

    def action_acknowledge(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_clinician",
            _("Only Post-Care Clinicians can acknowledge Escalations."),
        )
        for record in self:
            if record.state != "open":
                raise UserError(_("Only Open Escalations can be acknowledged."))
            record.with_context(postcare_transition=True).write({
                "state": "acknowledged",
                "acknowledged_at": fields.Datetime.now(),
                "acknowledged_by_id": self.env.user.id,
            })
        return True

    def action_start(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_clinician",
            _("Only Post-Care Clinicians can start Escalations."),
        )
        for record in self:
            if record.state not in ("open", "acknowledged"):
                raise UserError(_("Only Open/Acknowledged Escalations can start."))
            record.with_context(postcare_transition=True).write({"state": "in_progress"})
        return True

    # Resolution returns the Plan to Active only after the last open escalation is cleared.
    def action_resolve(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_clinician",
            _("Only Post-Care Clinicians can resolve Escalations."),
        )
        for record in self:
            if not record.resolution_note:
                raise UserError(_("Resolution Note is required."))
            record.with_context(postcare_transition=True).write({
                "state": "resolved",
                "resolved_at": fields.Datetime.now(),
                "resolved_by_id": self.env.user.id,
            })
            record.activity_ids.action_done()

            if record.task_id and record.task_id.state in ("overdue", "escalated"):
                record.task_id.with_context(postcare_transition=True).write({"state": "contacted"})

            remaining = record.plan_id.escalation_ids.filtered(
                lambda esc: esc.id != record.id and esc.state not in ("resolved", "cancelled")
            )
            if not remaining and record.plan_id.state == "escalated":
                record.plan_id.with_context(postcare_transition=True).write({"state": "active"})
        return True

    def action_cancel(self):
        self._postcare_require_group(
            "clinic_post_care_followup.group_postcare_manager",
            _("Only a Post-Care Manager can cancel Escalations."),
        )
        self.with_context(postcare_transition=True).write({"state": "cancelled"})
        return True

    def action_open_plan(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Post-Care Plan"),
            "res_model": "clinic.postcare.plan",
            "view_mode": "form",
            "res_id": self.plan_id.id,
        }

    def action_open_source(self):
        self.ensure_one()
        if self.checkin_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Patient Check-in"),
                "res_model": "clinic.postcare.checkin",
                "view_mode": "form",
                "res_id": self.checkin_id.id,
            }
        if self.task_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Post-Care Task"),
                "res_model": "clinic.postcare.task",
                "view_mode": "form",
                "res_id": self.task_id.id,
            }
        return self.action_open_plan()
