from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from .scope_mixin import QUALITY_SOP_TRANSITION_TOKEN


SOP_STATES = [
    ("draft", "Draft"),
    ("active", "Active"),
    ("retired", "Retired"),
]


class ClinicQualitySOP(models.Model):
    """Governed Standard Operating Procedure header.

    The header owns identity/applicability. Approved content lives in immutable
    version records so historic Quality Checks always retain the exact SOP
    version used when evidence was collected.
    """

    _name = "clinic.quality.sop"
    _description = "Clinic Quality Standard Operating Procedure"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "clinic.quality.security.mixin",
    ]
    _order = "code, name, id"
    _check_company_auto = True

    _code_company_uniq = models.Constraint(
        "UNIQUE(code, company_id)",
        "SOP Code must be unique per company.",
    )
    _company_state_idx = models.Index(
        "(company_id, state, active)"
    )

    name = fields.Char(
        string="SOP Title",
        required=True,
        index=True,
        tracking=True,
    )
    code = fields.Char(
        string="SOP Code",
        required=True,
        index=True,
        tracking=True,
    )
    active = fields.Boolean(
        default=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    branch_ids = fields.Many2many(
        "clinic.branch",
        "clinic_quality_sop_branch_rel",
        "sop_id",
        "branch_id",
        string="Applicable Branches",
        help=(
            "Leave empty for company-wide applicability. Selected branches "
            "limit where this SOP is intended to apply."
        ),
    )

    owner_user_id = fields.Many2one(
        "res.users",
        string="SOP Owner",
        required=True,
        default=lambda self: self.env.user,
        index=True,
        tracking=True,
    )
    approver_user_id = fields.Many2one(
        "res.users",
        string="Default Approver",
        index=True,
        tracking=True,
    )
    state = fields.Selection(
        SOP_STATES,
        default="draft",
        required=True,
        readonly=True,
        index=True,
        tracking=True,
    )

    purpose = fields.Text()
    scope = fields.Text()
    responsibilities = fields.Text()
    keywords = fields.Char(
        help="Optional comma-separated terms used for internal search."
    )

    version_ids = fields.One2many(
        "clinic.quality.sop.version",
        "sop_id",
        string="Versions",
        readonly=True,
    )
    current_version_id = fields.Many2one(
        "clinic.quality.sop.version",
        string="Current Approved Version",
        readonly=True,
        copy=False,
        ondelete="restrict",
        index=True,
    )
    acknowledgement_ids = fields.One2many(
        "clinic.quality.sop.acknowledgement",
        "sop_id",
        string="Acknowledgements",
        readonly=True,
    )
    check_template_ids = fields.One2many(
        "clinic.quality.check.template",
        "sop_id",
        string="Quality Check Templates",
        readonly=True,
    )

    version_count = fields.Integer(
        compute="_compute_quality_counts",
    )
    acknowledgement_count = fields.Integer(
        compute="_compute_quality_counts",
    )
    check_template_count = fields.Integer(
        compute="_compute_quality_counts",
    )
    next_review_date = fields.Date(
        related="current_version_id.review_due_date",
        store=True,
        readonly=True,
        index=True,
    )

    @api.depends(
        "version_ids",
        "acknowledgement_ids",
        "acknowledgement_ids.state",
        "check_template_ids",
    )
    def _compute_quality_counts(self):
        for sop in self:
            sop.version_count = len(sop.version_ids)
            sop.acknowledgement_count = len(
                sop.acknowledgement_ids.filtered(
                    lambda acknowledgement:
                    acknowledgement.state == "acknowledged"
                )
            )
            sop.check_template_count = len(sop.check_template_ids)

    @api.model_create_multi
    def create(self, vals_list):
        self._quality_require_manager()

        prepared = []
        for original in vals_list:
            vals = dict(original)
            company = (
                self.env["res.company"]
                .browse(vals.get("company_id"))
                .exists()
                or self.env.company
            )
            vals.setdefault(
                "approver_user_id",
                company.clinic_quality_default_approver_id.id
                if company.clinic_quality_default_approver_id
                else False,
            )
            prepared.append(vals)

        records = super().create(prepared)
        records._check_sop_company_scope()
        return records

    def write(self, vals):
        vals = dict(vals)

        if (
            "state" in vals
            or "current_version_id" in vals
            or "active" in vals
        ) and not self.env.context.get("quality_sop_transition") is QUALITY_SOP_TRANSITION_TOKEN:
            raise AccessError(
                _(
                    "Use SOP workflow actions to change lifecycle/current "
                    "version."
                )
            )

        if not self.env.context.get("quality_sop_transition") is QUALITY_SOP_TRANSITION_TOKEN:
            self._quality_require_manager()

        result = super().write(vals)
        self._check_sop_company_scope()
        return result

    def unlink(self):
        self._quality_require_manager()
        if self.filtered(
            lambda sop:
            sop.state != "draft"
            or sop.version_ids
            or sop.check_template_ids
        ):
            raise UserError(
                _(
                    "Only an unused Draft SOP may be deleted. Retire governed "
                    "SOPs instead."
                )
            )
        return super().unlink()

    @api.constrains(
        "company_id",
        "branch_ids",
        "owner_user_id",
        "approver_user_id",
        "current_version_id",
    )
    def _check_sop_company_scope(self):
        for sop in self:
            invalid_branches = sop.branch_ids.filtered(
                lambda branch:
                branch.company_id != sop.company_id
            )
            if invalid_branches:
                raise UserError(
                    _("All SOP Branches must belong to the SOP company.")
                )

            for role_name, user in (
                (_("SOP Owner"), sop.owner_user_id),
                (_("Default Approver"), sop.approver_user_id),
            ):
                if user and sop.company_id not in user.company_ids:
                    raise UserError(
                        _(
                            "%(role)s does not have access to the SOP company."
                        ) % {"role": role_name}
                    )

            if sop.approver_user_id and not sop.approver_user_id.has_group(
                "clinic_quality.group_quality_approver"
            ):
                raise UserError(
                    _(
                        "Default Approver must belong to the "
                        "Quality Approver role."
                    )
                )

            if (
                sop.current_version_id
                and sop.current_version_id.sop_id != sop
            ):
                raise UserError(
                    _("Current Version must belong to this SOP.")
                )

    def action_new_version(self):
        self.ensure_one()
        self._quality_require_inspector()

        if self.state == "retired":
            raise UserError(
                _("Restore the SOP before creating a new version.")
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("New SOP Version"),
            "res_model": "clinic.quality.sop.version",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_sop_id": self.id,
            },
        }

    def action_acknowledge_current_version(self):
        self.ensure_one()
        self._quality_require_user()

        version = self.current_version_id
        if not version or version.state != "approved":
            raise UserError(
                _("This SOP has no current Approved Version.")
            )

        staff = self.env["clinic.staff"].search([
            ("partner_id", "=", self.env.user.partner_id.id),
            ("company_id", "=", self.company_id.id),
        ], limit=1)
        if not staff:
            raise UserError(
                _(
                    "The current user is not linked to a Clinic Staff record "
                    "for this company."
                )
            )

        acknowledgement = self.env[
            "clinic.quality.sop.acknowledgement"
        ].search([
            ("version_id", "=", version.id),
            ("staff_id", "=", staff.id),
        ], limit=1)

        if acknowledgement and acknowledgement.state == "voided":
            raise UserError(
                _(
                    "This Staff acknowledgement for the current SOP Version "
                    "was explicitly voided. Create and approve a corrected SOP "
                    "Version rather than recreating evidence for the same "
                    "version."
                )
            )

        if not acknowledgement:
            acknowledgement = self.env[
                "clinic.quality.sop.acknowledgement"
            ].create({
                "version_id": version.id,
                "staff_id": staff.id,
            })

        return {
            "type": "ir.actions.act_window",
            "name": _("SOP Acknowledgement"),
            "res_model": "clinic.quality.sop.acknowledgement",
            "view_mode": "form",
            "res_id": acknowledgement.id,
        }

    def action_retire(self):
        self._quality_require_manager()
        for sop in self:
            if sop.state == "retired":
                continue
            sop.with_context(
                quality_sop_transition=QUALITY_SOP_TRANSITION_TOKEN
            ).write({
                "state": "retired",
                # Keep the record visible: Retired is a governed lifecycle
                # state, not an Odoo archive operation.
                "active": True,
            })
            sop.message_post(
                body=_("SOP retired by %s.") % self.env.user.display_name
            )
        return True

    def action_restore(self):
        self._quality_require_manager()
        for sop in self:
            if sop.state != "retired":
                continue
            new_state = (
                "active"
                if sop.current_version_id
                and sop.current_version_id.state == "approved"
                else "draft"
            )
            sop.with_context(
                quality_sop_transition=QUALITY_SOP_TRANSITION_TOKEN
            ).write({
                "state": new_state,
                "active": True,
            })
            sop.message_post(
                body=_("SOP restored by %s.") % self.env.user.display_name
            )
        return True

    def action_open_versions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("SOP Versions"),
            "res_model": "clinic.quality.sop.version",
            "view_mode": "list,form",
            "domain": [("sop_id", "=", self.id)],
            "context": {"default_sop_id": self.id},
        }

    def action_open_acknowledgements(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("SOP Acknowledgements"),
            "res_model": "clinic.quality.sop.acknowledgement",
            "view_mode": "list,form",
            "domain": [("sop_id", "=", self.id)],
        }

    def action_open_check_templates(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Quality Check Templates"),
            "res_model": "clinic.quality.check.template",
            "view_mode": "list,form",
            "domain": [("sop_id", "=", self.id)],
            "context": {"default_sop_id": self.id},
        }

    def action_open_current_version(self):
        self.ensure_one()
        if not self.current_version_id:
            raise UserError(_("No current SOP Version exists."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Current SOP Version"),
            "res_model": "clinic.quality.sop.version",
            "view_mode": "form",
            "res_id": self.current_version_id.id,
        }

    def action_print_current_sop(self):
        self.ensure_one()
        if not self.current_version_id:
            raise UserError(_("No current SOP Version exists."))
        return self.env.ref(
            "clinic_quality.action_report_quality_sop"
        ).report_action(self)
