# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ClinicTreatmentSessionLineEnterprise(models.Model):
    """Harden stock consumption without changing the historical line contract."""

    _inherit = "clinic.treatment.session.line"

    def _require_clinician(self):
        if not (
            self.env.user.has_group(
                "clinic_treatment_session."
                "group_treatment_session_clinician"
            )
            or self.env.user.has_group(
                "clinic_treatment_session."
                "group_treatment_session_manager"
            )
        ):
            raise AccessError(
                _("Treatment Session Clinician access is required.")
            )

    def action_mark_ready(self):
        self._require_clinician()
        return super().action_mark_ready()

    def action_mark_consumed(self):
        self._require_clinician()

        for line in self:
            if line.consumption_state == "consumed":
                continue

            quantity = line.consumed_qty or line.quantity or 0.0
            if quantity < 0:
                raise ValidationError(
                    _("Consumed quantity cannot be negative.")
                )
            if quantity > (line.quantity or 0.0):
                raise ValidationError(
                    _(
                        "Consumed quantity cannot exceed planned quantity."
                    )
                )

            if not line.is_stock_relevant:
                line.write(
                    {
                        "consumption_state": "consumed",
                        "consumed_qty": quantity,
                        "date_consumed": fields.Datetime.now(),
                    }
                )
                continue

            if not line.product_id:
                raise UserError(
                    _("A stock-relevant line requires a product.")
                )

            source = line.location_id
            destination = line.location_dest_id
            if not source or not destination:
                default_source, default_destination = (
                    line._get_default_consumption_locations()
                )
                source = source or default_source
                destination = destination or default_destination

            if not source or not destination:
                raise UserError(
                    _(
                        "Stock consumption locations are not configured. "
                        "Set them on the line or in Treatment Session Settings."
                    )
                )

            if source == destination:
                raise ValidationError(
                    _("Source and Destination stock locations must differ.")
                )

            move = line.stock_move_id
            if move and move.state == "done":
                line.write(
                    {
                        "consumption_state": "consumed",
                        "consumed_qty": quantity,
                        "date_consumed": (
                            line.date_consumed or fields.Datetime.now()
                        ),
                    }
                )
                continue

            if not move:
                values = {
                    "name": line.name or line.product_id.display_name,
                    "product_id": line.product_id.id,
                    "product_uom_qty": quantity,
                    "product_uom": (
                        line.product_uom_id.id
                        or line.product_id.uom_id.id
                    ),
                    "location_id": source.id,
                    "location_dest_id": destination.id,
                    "company_id": line.company_id.id,
                    "origin": line.session_id.name,
                }
                move = self.env["stock.move"].create(values)
                line.stock_move_id = move.id

            # Odoo 19 stock internals are used deliberately: public action
            # button helpers differ across stock views and versions.
            if move.state == "draft":
                move._action_confirm()
            if move.state not in ("assigned", "done", "cancel"):
                move._action_assign()

            if move.state != "done":
                if "quantity" in move._fields:
                    move.quantity = quantity
                move._action_done()

            if move.state != "done":
                raise UserError(
                    _(
                        "Stock move %s did not reach Done. "
                        "The session line is not marked consumed."
                    )
                    % move.display_name
                )

            line.write(
                {
                    "consumption_state": "consumed",
                    "consumed_qty": quantity,
                    "date_consumed": fields.Datetime.now(),
                }
            )

        return True

    def action_reset_consumption(self):
        self._require_clinician()

        for line in self:
            if line.stock_move_id and line.stock_move_id.state == "done":
                raise UserError(
                    _(
                        "A completed inventory movement cannot be hidden by "
                        "resetting the session line. Reverse/correct the stock "
                        "movement in Inventory first."
                    )
                )

            line.write(
                {
                    "consumption_state": "planned",
                    "consumed_qty": 0.0,
                    "date_consumed": False,
                }
            )

        return True

    def action_open_stock_move(self):
        self.ensure_one()
        if not self.stock_move_id:
            raise UserError(_("No Stock Move is linked to this line."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Stock Move"),
            "res_model": "stock.move",
            "res_id": self.stock_move_id.id,
            "view_mode": "form",
        }
