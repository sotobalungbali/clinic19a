
# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicTreatmentSessionLineEnterprise(models.Model):
    """Backend-enforced stock consumption for Treatment Session Lines."""

    _inherit = "clinic.treatment.session.line"

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

    def action_mark_ready(self):
        self._require_clinician()
        return super().action_mark_ready()

    def action_mark_consumed(self):
        self._require_clinician()
        for line in self:
            if line.display_type != "line" or line.consumption_state == "consumed":
                continue
            qty = line.consumed_qty or line.quantity or 0.0
            if qty < 0 or qty > line.quantity:
                raise ValidationError(_("Consumed Quantity must be between zero and Planned Quantity."))

            if not line.is_stock_relevant:
                line.write({
                    "consumption_state": "consumed",
                    "consumed_qty": qty,
                    "date_consumed": fields.Datetime.now(),
                })
                continue

            source, dest = line._get_default_consumption_locations()
            if not source or not dest:
                raise UserError(_("Stock consumption locations are not configured."))
            if source == dest:
                raise ValidationError(_("Source and Destination locations must differ."))

            move = line.stock_move_id
            if not move:
                move = self.env["stock.move"].create({
                    "name": line.name or line.product_id.display_name,
                    "product_id": line.product_id.id,
                    "product_uom_qty": qty,
                    "product_uom": (line.product_uom_id or line.product_id.uom_id).id,
                    "location_id": source.id,
                    "location_dest_id": dest.id,
                    "company_id": line.company_id.id,
                    "origin": line.session_id.name,
                })
                line.stock_move_id = move

            if move.state == "draft":
                move._action_confirm()
            if move.state not in ("done", "cancel"):
                if "quantity" in move._fields:
                    move.quantity = qty
                move._action_done()

            if move.state != "done":
                raise UserError(_("Stock Move did not reach Done; consumption was not completed."))

            line.write({
                "consumption_state": "consumed",
                "consumed_qty": qty,
                "date_consumed": fields.Datetime.now(),
            })
        return True

    def action_reset_consumption(self):
        self._require_clinician()
        for line in self:
            if line.stock_move_id and line.stock_move_id.state == "done":
                raise UserError(
                    _("A completed inventory movement cannot be hidden by resetting the session line.")
                )
        return super().action_reset_consumption()

    def action_open_stock_move(self):
        self.ensure_one()
        if not self.stock_move_id:
            raise UserError(_("No Stock Move is linked."))
        return {
            "type": "ir.actions.act_window", "name": _("Stock Move"),
            "res_model": "stock.move", "view_mode": "form",
            "res_id": self.stock_move_id.id,
        }
