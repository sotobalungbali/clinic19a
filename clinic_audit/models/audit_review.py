# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ClinicAuditReviewTag(models.Model):
    _name = "clinic.audit.review.tag"
    _description = "Clinic Audit Review Tag"
    _order = "name"

    name = fields.Char(required=True, index=True)
    color = fields.Integer(default=0)
    active = fields.Boolean(default=True)

    _name_unique = models.Constraint(
        "UNIQUE(name)",
        "Audit review tag names must be unique.",
    )


class ClinicAuditReviewLine(models.Model):
    _name = "clinic.audit.review.line"
    _description = "Clinic Audit Review Timeline"
    _order = "id asc"
    _check_company_auto = True

    review_id = fields.Many2one(
        "clinic.audit.review",
        required=True,
        index=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        related="review_id.company_id",
        store=True,
        index=True,
        readonly=True,
    )
    branch_id = fields.Many2one(
        related="review_id.branch_id",
        store=True,
        index=True,
        readonly=True,
    )
    date = fields.Datetime(default=fields.Datetime.now, index=True)
    user_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        index=True,
    )
    action = fields.Selection(
        [
            ("note", "Note"),
            ("assign", "Assign"),
            ("request_info", "Request Info"),
            ("add_event", "Add Event"),
            ("add_log", "Add Legacy Log"),
            ("escalate", "Escalate"),
            ("resolve", "Resolve"),
            ("dismiss", "Dismiss"),
            ("other", "Other"),
        ],
        default="note",
        required=True,
        index=True,
    )
    message = fields.Text()
    event_id = fields.Many2one(
        "clinic.audit.event",
        ondelete="set null",
        index=True,
    )
    # Historical field retained. The comodel is the compatibility surface.
    log_id = fields.Many2one(
        "clinic.audit.log",
        ondelete="set null",
        index=True,
    )
    assignee_id = fields.Many2one("res.users")
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "clinic_aud_review_line_attach_rel",
        "line_id",
        "attachment_id",
    )

    def action_open_event(self):
        self.ensure_one()
        if not self.event_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Audit Event"),
            "res_model": "clinic.audit.event",
            "res_id": self.event_id.id,
            "view_mode": "form",
        }

    def action_open_log(self):
        self.ensure_one()
        if not self.log_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Legacy Audit Log"),
            "res_model": "clinic.audit.log",
            "res_id": self.log_id.id,
            "view_mode": "form",
        }


class ClinicAuditReview(models.Model):
    _name = "clinic.audit.review"
    _description = "Clinic Audit Compliance Review"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, due_date, id desc"
    _check_company_auto = True

    name = fields.Char(
        required=True,
        default=lambda self: _("New"),
        copy=False,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )
    branch_id = fields.Many2one(
        "clinic.branch",
        check_company=True,
        index=True,
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("new", "New (Legacy)"),
            ("in_review", "In Review"),
            ("investigating", "Investigating (Legacy)"),
            ("need_info", "Need Info (Legacy)"),
            ("escalated", "Escalated"),
            ("resolved", "Resolved"),
            ("dismissed", "Dismissed"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    severity = fields.Selection(
        [(x, x.title()) for x in ("low", "medium", "high", "critical")],
        default="medium",
        required=True,
        tracking=True,
    )
    priority = fields.Selection(
        [
            ("0", "Normal"),
            ("1", "High"),
            ("2", "Urgent"),
            ("3", "Critical"),
        ],
        default="0",
        required=True,
        tracking=True,
    )
    category = fields.Selection(
        [
            ("data_change", "Data Change"),
            ("access", "Access"),
            ("export", "Export"),
            ("policy_violation", "Policy Violation"),
            ("compliance", "Compliance"),
            ("security", "Security"),
            ("privacy", "Privacy"),
            ("quality", "Quality"),
            ("other", "Other"),
        ],
        default="compliance",
    )

    owner_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        tracking=True,
    )
    reviewer_id = fields.Many2one("res.users", tracking=True)
    assignee_id = fields.Many2one("res.users", tracking=True)
    approver_id = fields.Many2one("res.users", tracking=True)
    due_date = fields.Datetime(tracking=True)
    due_at = fields.Datetime(string="Legacy Due At", tracking=True)
    opened_at = fields.Datetime(default=fields.Datetime.now, readonly=True)
    closed_at = fields.Datetime(readonly=True)
    sla_hours = fields.Float(default=72.0)
    is_overdue = fields.Boolean(
        compute="_compute_metrics",
        search="_search_is_overdue",
        help=(
            "Dynamic overdue indicator. It remains non-stored so the result "
            "always reflects the current time; search is translated to the "
            "stored due-date and workflow fields."
        ),
    )
    duration_hours = fields.Float(compute="_compute_metrics")

    event_ids = fields.Many2many(
        "clinic.audit.event",
        "clinic_aud_review_event_rel",
        "review_id",
        "event_id",
        string="Audit Events",
    )
    event_count = fields.Integer(compute="_compute_counts")

    # Legacy review/log relation is intentionally preserved.
    primary_log_id = fields.Many2one(
        "clinic.audit.log",
        ondelete="set null",
    )
    log_ids = fields.Many2many(
        "clinic.audit.log",
        "clinic_audit_review_log_rel",
        "review_id",
        "log_id",
        string="Legacy Audit Logs",
    )
    log_count = fields.Integer(compute="_compute_counts")

    policy_id = fields.Many2one(
        "clinic.audit.policy",
        ondelete="set null",
    )
    tag_ids = fields.Many2many(
        "clinic.audit.review.tag",
        "clinic_audit_review_tag_rel",
        "review_id",
        "tag_id",
    )
    line_ids = fields.One2many(
        "clinic.audit.review.line",
        "review_id",
        string="Review Timeline",
    )
    line_count = fields.Integer(compute="_compute_counts")
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "clinic_audit_review_attach_rel",
        "review_id",
        "attachment_id",
    )

    summary = fields.Char()
    description = fields.Text()
    finding = fields.Text(tracking=True)
    recommendation = fields.Text()
    root_cause = fields.Text(tracking=True)
    corrective_action = fields.Text(tracking=True)
    resolution = fields.Text(tracking=True)
    payload_summary = fields.Text()
    resolved_by_id = fields.Many2one("res.users", readonly=True)
    resolved_at = fields.Datetime(readonly=True)

    @api.depends("event_ids", "log_ids", "line_ids")
    def _compute_counts(self):
        for rec in self:
            rec.event_count = len(rec.event_ids)
            rec.log_count = len(rec.log_ids)
            rec.line_count = len(rec.line_ids)

    @api.depends("opened_at", "closed_at", "due_date", "due_at", "state")
    def _compute_metrics(self):
        now = fields.Datetime.now()
        for rec in self:
            due = rec.due_date or rec.due_at
            rec.is_overdue = bool(
                due
                and rec.state not in {"resolved", "dismissed"}
                and due < now
            )
            end = rec.closed_at or now
            rec.duration_hours = (
                max((end - rec.opened_at).total_seconds() / 3600.0, 0.0)
                if rec.opened_at
                else 0.0
            )


    @api.model
    def _search_is_overdue(self, operator, value):
        """Translate a dynamic Boolean search into stored workflow fields.

        Odoo 19 commonly normalizes Boolean searches to ``in`` / ``not in``.
        Keep the search semantics identical to ``_compute_metrics`` while
        preserving the non-stored, current-time behavior.
        """
        if operator not in {"=", "!=", "in", "not in"}:
            return NotImplemented

        if operator in {"=", "!="}:
            requested = bool(value)
            if operator == "!=":
                requested = not requested
        else:
            values = (
                list(value)
                if isinstance(value, (list, tuple, set))
                else [value]
            )
            normalized = {bool(item) for item in values}

            if operator == "in":
                if not normalized:
                    return [("id", "=", False)]
                if normalized == {True, False}:
                    return []
                requested = True in normalized
            else:
                if not normalized:
                    return []
                if normalized == {True, False}:
                    return [("id", "=", False)]
                requested = False in normalized

        now = fields.Datetime.now()
        overdue_domain = [
            "&",
            ("state", "not in", ["resolved", "dismissed"]),
            "|",
            "&",
            ("due_date", "!=", False),
            ("due_date", "<", now),
            "&",
            ("due_date", "=", False),
            "&",
            ("due_at", "!=", False),
            ("due_at", "<", now),
        ]
        return overdue_domain if requested else ["!"] + overdue_domain

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if vals.get("name", _("New")) in (False, _("New")):
                vals["name"] = (
                    sequence.next_by_code("clinic.audit.review")
                    or _("New")
                )
            vals.setdefault("opened_at", fields.Datetime.now())
        return super().create(vals_list)

    @api.constrains("branch_id", "company_id")
    def _check_branch_company(self):
        for rec in self:
            if rec.branch_id and rec.branch_id.company_id != rec.company_id:
                raise ValidationError(
                    _("Review branch must belong to the selected company.")
                )

    @api.constrains("event_ids", "company_id", "branch_id")
    def _check_event_scope(self):
        for rec in self:
            if rec.event_ids.filtered(
                lambda event: event.company_id != rec.company_id
            ):
                raise ValidationError(
                    _("All audit events in a review must belong to the same company.")
                )
            if rec.branch_id and rec.event_ids.filtered(
                lambda event: event.branch_id and event.branch_id != rec.branch_id
            ):
                raise ValidationError(
                    _("Audit events must respect the review branch scope.")
                )

    def _check_workflow_access(self):
        if self.env.user.has_group("clinic_audit.group_audit_manager"):
            return
        allowed = self.filtered(
            lambda review: self.env.user
            in (review.owner_id | review.reviewer_id | review.assignee_id)
        )
        if len(allowed) != len(self):
            raise AccessError(
                _(
                    "Only assigned audit staff or Audit Manager "
                    "may change review workflow."
                )
            )

    def _append_timeline(self, action, message):
        self.env["clinic.audit.review.line"].create([
            {
                "review_id": review.id,
                "action": action,
                "message": message,
            }
            for review in self
        ])

    def action_start(self):
        self._check_workflow_access()
        self.write({"state": "in_review"})
        self._append_timeline("other", _("Review started."))
        return True

    def action_escalate(self):
        self._check_workflow_access()
        self.write({"state": "escalated", "priority": "3"})
        self._append_timeline("escalate", _("Review escalated."))
        return True

    def action_resolve(self):
        self._check_workflow_access()
        if any(not review.resolution for review in self):
            raise ValidationError(
                _("Resolution is required before closing a review.")
            )
        now = fields.Datetime.now()
        self.write({
            "state": "resolved",
            "resolved_by_id": self.env.user.id,
            "resolved_at": now,
            "closed_at": now,
        })
        self._append_timeline("resolve", _("Review resolved."))
        return True

    def action_dismiss(self):
        self._check_workflow_access()
        if any(not review.resolution for review in self):
            raise ValidationError(
                _("A dismissal explanation is required.")
            )
        now = fields.Datetime.now()
        self.write({
            "state": "dismissed",
            "resolved_by_id": self.env.user.id,
            "resolved_at": now,
            "closed_at": now,
        })
        self._append_timeline("dismiss", _("Review dismissed."))
        return True

    def action_reopen(self):
        self._check_workflow_access()
        self.write({
            "state": "in_review",
            "resolved_by_id": False,
            "resolved_at": False,
            "closed_at": False,
        })
        self._append_timeline("other", _("Review reopened."))
        return True

    def action_open_events(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Audit Events"),
            "res_model": "clinic.audit.event",
            "view_mode": "list,form",
            "domain": [("id", "in", self.event_ids.ids)],
        }

    def action_open_legacy_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Legacy Audit Logs"),
            "res_model": "clinic.audit.log",
            "view_mode": "list,form",
            "domain": [("id", "in", self.log_ids.ids)],
        }
