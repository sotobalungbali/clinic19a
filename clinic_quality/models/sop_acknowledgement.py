from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .scope_mixin import QUALITY_ACK_VOID_TOKEN


ACK_STATES = [
    ("acknowledged", "Acknowledged"),
    ("voided", "Voided"),
]


class ClinicQualitySOPAcknowledgement(models.Model):
    """Immutable acknowledgement evidence with explicit voiding, not deletion."""

    _name = "clinic.quality.sop.acknowledgement"
    _description = "Clinic Quality SOP Acknowledgement"
    _inherit = "clinic.quality.security.mixin"
    _order = "acknowledged_at desc, id desc"
    _check_company_auto = True

    _version_staff_uniq = models.Constraint(
        "UNIQUE(version_id, staff_id)",
        "A Staff member can acknowledge an SOP Version only once.",
    )
    _company_state_idx = models.Index(
        "(company_id, state, acknowledged_at)"
    )

    version_id = fields.Many2one(
        "clinic.quality.sop.version",
        required=True,
        ondelete="restrict",
        index=True,
    )
    sop_id = fields.Many2one(
        related="version_id.sop_id",
        store=True,
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        related="version_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    staff_id = fields.Many2one(
        "clinic.staff",
        required=True,
        ondelete="restrict",
        index=True,
    )

    state = fields.Selection(
        ACK_STATES,
        default="acknowledged",
        required=True,
        readonly=True,
        index=True,
    )
    acknowledged_at = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
        readonly=True,
        index=True,
    )
    acknowledged_by_user_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        index=True,
    )
    note = fields.Text(
        help="Optional Staff acknowledgement note."
    )

    void_reason = fields.Text()
    voided_at = fields.Datetime(readonly=True)
    voided_by_id = fields.Many2one("res.users", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        self._quality_require_user()

        prepared = []
        for original in vals_list:
            vals = dict(original)
            version = self.env["clinic.quality.sop.version"].browse(
                vals.get("version_id")
            ).exists()
            staff = self.env["clinic.staff"].browse(
                vals.get("staff_id")
            ).exists()

            if not version or version.state != "approved":
                raise ValidationError(
                    _("Only an Approved SOP Version can be acknowledged.")
                )
            if not staff:
                raise ValidationError(_("A valid Clinic Staff record is required."))
            if staff.company_id and staff.company_id != version.company_id:
                raise ValidationError(
                    _("Staff belongs to another company.")
                )

            if not self.env.user.has_group(
                "clinic_quality.group_quality_manager"
            ):
                if staff.partner_id != self.env.user.partner_id:
                    raise AccessError(
                        _(
                            "Users may acknowledge only their own Clinic Staff "
                            "record. Quality Manager can register corrections."
                        )
                    )

            vals["acknowledged_by_user_id"] = self.env.user.id
            vals["acknowledged_at"] = fields.Datetime.now()
            vals["state"] = "acknowledged"
            prepared.append(vals)

        return super().create(prepared)

    def write(self, vals):
        vals = dict(vals)

        if (
            set(vals).issubset({"void_reason"})
            and self.filtered(
                lambda acknowledgement:
                acknowledgement.state == "acknowledged"
            )
            and not self.env.context.get("quality_ack_void") is QUALITY_ACK_VOID_TOKEN
        ):
            self._quality_require_manager()
            return super().write(vals)

        if not self.env.context.get("quality_ack_void") is QUALITY_ACK_VOID_TOKEN:
            raise AccessError(
                _(
                    "SOP Acknowledgement evidence is immutable. "
                    "Use Void for corrections."
                )
            )
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise AccessError(
                _("SOP Acknowledgement evidence cannot be deleted.")
            )
        return super().unlink()

    def action_void(self):
        self._quality_require_manager()

        for acknowledgement in self:
            if acknowledgement.state == "voided":
                continue
            if not (acknowledgement.void_reason or "").strip():
                raise UserError(
                    _("Void Reason is required.")
                )

            acknowledgement.with_context(
                quality_ack_void=QUALITY_ACK_VOID_TOKEN
            ).write({
                "state": "voided",
                "voided_at": fields.Datetime.now(),
                "voided_by_id": self.env.user.id,
            })
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

    def action_open_version(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("SOP Version"),
            "res_model": "clinic.quality.sop.version",
            "view_mode": "form",
            "res_id": self.version_id.id,
        }

    def action_open_staff(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic Staff"),
            "res_model": "clinic.staff",
            "view_mode": "form",
            "res_id": self.staff_id.id,
        }
