from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .scope_mixin import (
    QUALITY_SOP_TRANSITION_TOKEN,
    QUALITY_SOP_VERSION_TRANSITION_TOKEN,
)


SOP_VERSION_STATES = [
    ("draft", "Draft"),
    ("in_review", "In Review"),
    ("approved", "Approved"),
    ("superseded", "Superseded"),
    ("withdrawn", "Withdrawn"),
]


class ClinicQualitySOPVersion(models.Model):
    """Version-controlled SOP content and approval evidence."""

    _name = "clinic.quality.sop.version"
    _description = "Clinic Quality SOP Version"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "clinic.quality.security.mixin",
    ]
    _order = "sop_id, create_date desc, id desc"
    _check_company_auto = True

    _sop_version_uniq = models.Constraint(
        "UNIQUE(sop_id, version_no)",
        "SOP Version number must be unique within the SOP.",
    )
    _sop_state_idx = models.Index(
        "(sop_id, state, review_due_date)"
    )

    sop_id = fields.Many2one(
        "clinic.quality.sop",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="sop_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    version_no = fields.Char(
        string="Version",
        required=True,
        index=True,
        tracking=True,
    )
    state = fields.Selection(
        SOP_VERSION_STATES,
        default="draft",
        required=True,
        readonly=True,
        index=True,
        tracking=True,
    )

    effective_date = fields.Date(
        index=True,
        tracking=True,
    )
    review_due_date = fields.Date(
        index=True,
        tracking=True,
    )
    change_summary = fields.Text(
        required=True,
        help="Human-readable summary of what changed in this version.",
    )
    content = fields.Html(
        string="Approved Procedure Content",
        required=True,
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "clinic_quality_sop_ver_attach_rel",
        "version_id",
        "attachment_id",
        string="Controlled Attachments",
    )

    submitted_at = fields.Datetime(readonly=True)
    submitted_by_id = fields.Many2one("res.users", readonly=True)
    approved_at = fields.Datetime(readonly=True)
    approved_by_id = fields.Many2one("res.users", readonly=True)
    withdrawn_at = fields.Datetime(readonly=True)
    withdrawn_by_id = fields.Many2one("res.users", readonly=True)
    withdrawal_reason = fields.Text()

    acknowledgement_ids = fields.One2many(
        "clinic.quality.sop.acknowledgement",
        "version_id",
        string="Acknowledgements",
        readonly=True,
    )
    acknowledgement_count = fields.Integer(
        compute="_compute_acknowledgement_count",
    )

    @api.depends(
        "acknowledgement_ids",
        "acknowledgement_ids.state",
    )
    def _compute_acknowledgement_count(self):
        for version in self:
            version.acknowledgement_count = len(
                version.acknowledgement_ids.filtered(
                    lambda acknowledgement:
                    acknowledgement.state == "acknowledged"
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        self._quality_require_inspector()

        records = super().create(vals_list)
        records._check_sop_version_scope()
        return records

    def write(self, vals):
        vals = dict(vals)

        if (
            set(vals).issubset({"withdrawal_reason"})
            and self.filtered(
                lambda version:
                version.state in ("approved", "superseded")
            )
            and not self.env.context.get("quality_sop_version_transition") is QUALITY_SOP_VERSION_TRANSITION_TOKEN
        ):
            self._quality_require_manager()
            return super().write(vals)

        if (
            "state" in vals
            or "submitted_at" in vals
            or "submitted_by_id" in vals
            or "approved_at" in vals
            or "approved_by_id" in vals
            or "withdrawn_at" in vals
            or "withdrawn_by_id" in vals
        ) and not self.env.context.get("quality_sop_version_transition") is QUALITY_SOP_VERSION_TRANSITION_TOKEN:
            raise AccessError(
                _("Use SOP Version workflow actions to change lifecycle.")
            )

        if (
            self.filtered(
                lambda version:
                version.state in (
                    "approved",
                    "superseded",
                    "withdrawn",
                )
            )
            and not self.env.context.get("quality_sop_version_transition") is QUALITY_SOP_VERSION_TRANSITION_TOKEN
        ):
            raise AccessError(
                _(
                    "Approved, Superseded and Withdrawn SOP Versions "
                    "are immutable."
                )
            )

        self._quality_require_inspector()
        result = super().write(vals)
        self._check_sop_version_scope()
        return result

    def unlink(self):
        self._quality_require_manager()

        if self.filtered(
            lambda version:
            version.state != "draft"
            or version.acknowledgement_ids
        ):
            raise UserError(
                _(
                    "Only an unacknowledged Draft SOP Version may be deleted."
                )
            )

        if self.filtered(
            lambda version:
            version.sop_id.current_version_id == version
        ):
            raise UserError(
                _("Current SOP Version cannot be deleted.")
            )

        return super().unlink()

    @api.constrains(
        "sop_id",
        "company_id",
        "effective_date",
        "review_due_date",
    )
    def _check_sop_version_scope(self):
        for version in self:
            if version.company_id != version.sop_id.company_id:
                raise ValidationError(
                    _("SOP Version company does not match its SOP.")
                )

            if (
                version.review_due_date
                and version.effective_date
                and version.review_due_date <= version.effective_date
            ):
                raise ValidationError(
                    _(
                        "Review Due Date must be later than Effective Date."
                    )
                )

    def action_submit_review(self):
        self._quality_require_inspector()

        for version in self:
            if version.state != "draft":
                raise UserError(
                    _("Only a Draft SOP Version can be submitted.")
                )
            if not (version.content or "").strip():
                raise UserError(_("SOP Content is required."))
            if not (version.change_summary or "").strip():
                raise UserError(_("Change Summary is required."))

            approver = (
                version.sop_id.approver_user_id
                or version.company_id.clinic_quality_default_approver_id
            )
            if not approver:
                raise UserError(
                    _(
                        "Configure an SOP Approver or Company Default "
                        "Quality Approver before submission."
                    )
                )

            version.with_context(
                quality_sop_version_transition=QUALITY_SOP_VERSION_TRANSITION_TOKEN
            ).write({
                "state": "in_review",
                "submitted_at": fields.Datetime.now(),
                "submitted_by_id": self.env.user.id,
            })

            version.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=_("Review SOP Version %s") % version.version_no,
                user_id=approver.id,
            )

            version.message_post(
                body=_(
                    "SOP Version %(version)s submitted for review by %(user)s."
                ) % {
                    "version": version.version_no,
                    "user": self.env.user.display_name,
                }
            )
        return True

    def action_approve(self):
        self._quality_require_approver()

        for version in self:
            if version.state != "in_review":
                raise UserError(
                    _("Only an In Review SOP Version can be approved.")
                )

            approver = (
                version.sop_id.approver_user_id
                or version.company_id.clinic_quality_default_approver_id
            )
            if approver and approver != self.env.user and not self.env.user.has_group(
                "clinic_quality.group_quality_manager"
            ):
                raise AccessError(
                    _("Only the designated SOP Approver or Quality Manager may approve.")
                )

            effective_date = (
                version.effective_date
                or fields.Date.today()
            )
            review_due_date = (
                version.review_due_date
                or effective_date
                + relativedelta(
                    months=version.company_id.clinic_quality_default_review_months
                )
            )

            previous = version.sop_id.current_version_id
            if previous and previous != version and previous.state == "approved":
                previous.with_context(
                    quality_sop_version_transition=QUALITY_SOP_VERSION_TRANSITION_TOKEN
                ).write({
                    "state": "superseded",
                })

            version.with_context(
                quality_sop_version_transition=QUALITY_SOP_VERSION_TRANSITION_TOKEN
            ).write({
                "state": "approved",
                "effective_date": effective_date,
                "review_due_date": review_due_date,
                "approved_at": fields.Datetime.now(),
                "approved_by_id": self.env.user.id,
            })

            version.sop_id.with_context(
                quality_sop_transition=QUALITY_SOP_TRANSITION_TOKEN
            ).write({
                "state": "active",
                "active": True,
                "current_version_id": version.id,
            })

            version.message_post(
                body=_(
                    "SOP Version %(version)s approved by %(user)s."
                ) % {
                    "version": version.version_no,
                    "user": self.env.user.display_name,
                }
            )
        return True

    def action_return_to_draft(self):
        self._quality_require_approver()

        for version in self:
            if version.state != "in_review":
                raise UserError(
                    _("Only an In Review SOP Version can be returned.")
                )
            version.with_context(
                quality_sop_version_transition=QUALITY_SOP_VERSION_TRANSITION_TOKEN
            ).write({
                "state": "draft",
                "submitted_at": False,
                "submitted_by_id": False,
            })
        return True

    def action_withdraw(self):
        self._quality_require_manager()

        for version in self:
            if version.state not in ("approved", "superseded"):
                raise UserError(
                    _(
                        "Only Approved or Superseded SOP Versions "
                        "can be withdrawn."
                    )
                )
            if not (version.withdrawal_reason or "").strip():
                raise UserError(
                    _("Withdrawal Reason is required.")
                )

            was_current = (
                version.sop_id.current_version_id == version
            )

            version.with_context(
                quality_sop_version_transition=QUALITY_SOP_VERSION_TRANSITION_TOKEN
            ).write({
                "state": "withdrawn",
                "withdrawn_at": fields.Datetime.now(),
                "withdrawn_by_id": self.env.user.id,
            })

            if was_current:
                version.sop_id.with_context(
                    quality_sop_transition=QUALITY_SOP_TRANSITION_TOKEN
                ).write({
                    "state": "draft",
                    "current_version_id": False,
                })

            version.message_post(
                body=_(
                    "SOP Version %(version)s withdrawn by %(user)s."
                ) % {
                    "version": version.version_no,
                    "user": self.env.user.display_name,
                }
            )
        return True

    def action_open_sop(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("SOP"),
            "res_model": "clinic.quality.sop",
            "view_mode": "form",
            "res_id": self.sop_id.id,
        }

    def action_open_acknowledgements(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("SOP Acknowledgements"),
            "res_model": "clinic.quality.sop.acknowledgement",
            "view_mode": "list,form",
            "domain": [("version_id", "=", self.id)],
        }
