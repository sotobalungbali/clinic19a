from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


# Internal transition tokens are process-local object identities.
# They are intentionally not serializable RPC secrets.
QUALITY_SOP_TRANSITION_TOKEN = object()
QUALITY_SOP_VERSION_TRANSITION_TOKEN = object()
QUALITY_ACK_VOID_TOKEN = object()
QUALITY_TEMPLATE_TRANSITION_TOKEN = object()
QUALITY_CHECK_TRANSITION_TOKEN = object()
QUALITY_CHECK_GENERATE_TOKEN = object()
QUALITY_CHECK_REGENERATE_TOKEN = object()
QUALITY_SCHEDULE_TRANSITION_TOKEN = object()


QUALITY_SCOPE_TYPES = [
    ("organization", "Organization / Clinic"),
    ("branch", "Branch"),
    ("room", "Room"),
    ("staff", "Staff"),
    ("doctor", "Doctor"),
    ("inventory_lot", "Inventory Lot / Batch"),
    ("treatment", "Treatment / Service"),
]


class ClinicQualitySecurityMixin(models.AbstractModel):
    """Shared backend role checks.

    UI visibility is convenience only. Business transitions call these
    helpers so RPC/API callers cannot bypass Quality authority.
    """

    _name = "clinic.quality.security.mixin"
    _description = "Clinic Quality Security Mixin"
    _abstract = True

    def _quality_require_user(self):
        if self.env.su:
            return True
        if not self.env.user.has_group(
            "clinic_quality.group_quality_user"
        ):
            raise AccessError(_("Quality User access is required."))
        return True

    def _quality_require_inspector(self):
        if self.env.su:
            return True
        if not self.env.user.has_group(
            "clinic_quality.group_quality_inspector"
        ):
            raise AccessError(_("Quality Inspector access is required."))
        return True

    def _quality_require_approver(self):
        if self.env.su:
            return True
        if not self.env.user.has_group(
            "clinic_quality.group_quality_approver"
        ):
            raise AccessError(_("Quality Approver access is required."))
        return True

    def _quality_require_manager(self):
        if self.env.su:
            return True
        if not self.env.user.has_group(
            "clinic_quality.group_quality_manager"
        ):
            raise AccessError(_("Quality Manager access is required."))
        return True


class ClinicQualityScopeMixin(models.AbstractModel):
    """Reusable enterprise scope fields for Checks and Schedules."""

    _name = "clinic.quality.scope.mixin"
    _description = "Clinic Quality Scope Mixin"
    _inherit = "clinic.quality.security.mixin"
    _abstract = True

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    allowed_branch_ids = fields.Many2many(
        "clinic.branch",
        compute="_compute_quality_allowed_branch_ids",
        string="Allowed Branches",
    )
    branch_id = fields.Many2one(
        "clinic.branch",
        string="Branch",
        domain="[('id', 'in', allowed_branch_ids)]",
        index=True,
        check_company=True,
        help=(
            "Optional governance branch. It becomes the required scope target "
            "when Scope Type is Branch."
        ),
    )

    scope_type = fields.Selection(
        QUALITY_SCOPE_TYPES,
        required=True,
        default="organization",
        index=True,
    )
    room_id = fields.Many2one(
        "clinic.room",
        ondelete="set null",
        index=True,
    )
    staff_id = fields.Many2one(
        "clinic.staff",
        ondelete="set null",
        index=True,
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        ondelete="set null",
        index=True,
    )
    stock_lot_id = fields.Many2one(
        "stock.lot",
        string="Inventory Lot / Batch",
        ondelete="set null",
        index=True,
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment / Service",
        ondelete="set null",
        index=True,
    )

    @api.depends_context("uid", "allowed_company_ids")
    def _compute_quality_allowed_branch_ids(self):
        Branch = self.env["clinic.branch"].sudo()
        user = self.env.user.sudo()

        for record in self:
            company = record.company_id or self.env.company
            allowed = user.allowed_branch_ids.filtered(
                lambda branch: branch.company_id == company
            )
            if not allowed:
                allowed = Branch.search([
                    ("company_id", "=", company.id),
                ])
            record.allowed_branch_ids = allowed

    @api.onchange("scope_type")
    def _onchange_quality_scope_type(self):
        for record in self:
            keep = {
                "room": "room_id",
                "staff": "staff_id",
                "doctor": "doctor_id",
                "inventory_lot": "stock_lot_id",
                "treatment": "treatment_id",
            }.get(record.scope_type)

            # Branch is both a branch-scope target and an optional governance
            # dimension for organization/room/staff/doctor/lot/treatment
            # checks. Do not clear it merely because the subject changes.
            if keep != "room_id":
                record.room_id = False
            if keep != "staff_id":
                record.staff_id = False
            if keep != "doctor_id":
                record.doctor_id = False
            if keep != "stock_lot_id":
                record.stock_lot_id = False
            if keep != "treatment_id":
                record.treatment_id = False

    @api.constrains(
        "company_id",
        "branch_id",
        "scope_type",
        "room_id",
        "staff_id",
        "doctor_id",
        "stock_lot_id",
        "treatment_id",
    )
    def _check_quality_scope(self):
        target_field = {
            "organization": None,
            "branch": "branch_id",
            "room": "room_id",
            "staff": "staff_id",
            "doctor": "doctor_id",
            "inventory_lot": "stock_lot_id",
            "treatment": "treatment_id",
        }

        target_fields = {
            "room_id",
            "staff_id",
            "doctor_id",
            "stock_lot_id",
            "treatment_id",
        }

        for record in self:
            expected = target_field[record.scope_type]

            if expected and not record[expected]:
                raise ValidationError(
                    _(
                        "%(target)s is required for Scope Type %(scope)s."
                    ) % {
                        "target": record._fields[expected].string,
                        "scope": dict(
                            record._fields["scope_type"].selection
                        ).get(record.scope_type),
                    }
                )

            expected_nonbranch = (
                {expected}
                if expected and expected != "branch_id"
                else set()
            )
            for field_name in target_fields - expected_nonbranch:
                if record[field_name]:
                    raise ValidationError(
                        _(
                            "Only the target matching Scope Type may be "
                            "selected. Clear %(field)s."
                        ) % {"field": record._fields[field_name].string}
                    )

            if (
                record.branch_id
                and record.branch_id.company_id != record.company_id
            ):
                raise ValidationError(
                    _("Quality Branch belongs to another company.")
                )

            if (
                record.branch_id
                and not self.env.su
                and record.branch_id
                not in record.allowed_branch_ids
            ):
                raise AccessError(
                    _("You are not allowed to use this Quality Branch.")
                )

            if (
                record.room_id
                and record.room_id.company_id != record.company_id
            ):
                raise ValidationError(
                    _("Quality Room belongs to another company.")
                )

            if (
                record.staff_id
                and record.staff_id.company_id
                and record.staff_id.company_id != record.company_id
            ):
                raise ValidationError(
                    _("Quality Staff belongs to another company.")
                )

            if (
                record.doctor_id
                and record.doctor_id.company_id != record.company_id
            ):
                raise ValidationError(
                    _("Quality Doctor belongs to another company.")
                )

            lot_company = (
                record.stock_lot_id.company_id
                if record.stock_lot_id
                and "company_id" in record.stock_lot_id._fields
                else False
            )
            if (
                lot_company
                and lot_company != record.company_id
            ):
                raise ValidationError(
                    _("Inventory Lot belongs to another company.")
                )

            if (
                record.treatment_id
                and record.treatment_id.company_id != record.company_id
            ):
                raise ValidationError(
                    _("Treatment belongs to another company.")
                )

    def _quality_scope_display_name(self):
        self.ensure_one()
        if self.scope_type == "organization":
            return self.company_id.display_name
        if self.scope_type == "branch":
            return self.branch_id.display_name
        if self.scope_type == "room":
            return self.room_id.display_name
        if self.scope_type == "staff":
            return self.staff_id.display_name
        if self.scope_type == "doctor":
            return self.doctor_id.display_name
        if self.scope_type == "inventory_lot":
            return self.stock_lot_id.display_name
        if self.scope_type == "treatment":
            return self.treatment_id.display_name
        return _("Quality Scope")
