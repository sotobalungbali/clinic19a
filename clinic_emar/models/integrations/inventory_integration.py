# -*- coding: utf-8 -*-
"""Integrate eMAR administration with ClinicOne inventory consumption documents."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ClinicTreatmentProductUsageEmar(models.Model):
    _inherit = "clinic.treatment.product.usage"

    emar_order_id = fields.Many2one("clinic.emar.order", string="eMAR Order", index=True, ondelete="set null")
    emar_administration_id = fields.Many2one(
        "clinic.emar.administration", string="eMAR Administration", index=True, ondelete="set null"
    )

    def _clinic_treatment_reference_models(self):
        values = super()._clinic_treatment_reference_models()
        existing = {model for model, _label in values}
        for model, label in [
            ("clinic.emar.order", "eMAR Order"),
            ("clinic.emar.administration", "eMAR Administration"),
        ]:
            if model not in existing:
                values.append((model, label))
        return values


class ClinicEmarAdministrationInventory(models.Model):
    _inherit = "clinic.emar.administration"

    inventory_usage_id = fields.Many2one(
        "clinic.treatment.product.usage",
        string="Inventory Consumption",
        readonly=True,
        copy=False,
        ondelete="restrict",
        index=True,
    )
    inventory_move_count = fields.Integer(compute="_compute_inventory_move_count")

    @api.depends("inventory_usage_id", "inventory_usage_id.move_ids")
    def _compute_inventory_move_count(self):
        for rec in self:
            rec.inventory_move_count = len(rec.inventory_usage_id.move_ids)

    def _prepare_inventory_usage_vals(self):
        self.ensure_one()
        warehouse = (
            self.order_id.warehouse_id
            or self.company_id.emar_default_warehouse_id
            or self.env["stock.warehouse"].search([("company_id", "=", self.company_id.id)], limit=1)
        )
        if not warehouse:
            raise UserError(_("No warehouse is available for this eMAR administration."))
        product_uom = self.inventory_uom_id or (
            self.line_id.product_uom_id
            if self.line_id and self.line_id.product_uom_id
            else self.product_id.uom_id
        )
        qty = float(self.inventory_qty or 0.0)
        if qty <= 0:
            raise UserError(_("Inventory quantity must be greater than zero before stock consumption."))
        return {
            "company_id": self.company_id.id,
            "warehouse_id": warehouse.id,
            "patient_id": self.patient_id.partner_id.id if self.patient_id and self.patient_id.partner_id else False,
            "doctor_id": self.order_id.doctor_id.id if self.order_id and self.order_id.doctor_id else False,
            "responsible_id": self.env.user.id,
            "date_usage": self.administered_datetime or fields.Datetime.now(),
            "emar_order_id": self.order_id.id if self.order_id else False,
            "emar_administration_id": self.id,
            "treatment_ref": "clinic.emar.administration,%s" % self.id,
            "notes": _("Medication administration consumption for %s") % self.display_name,
            "line_ids": [
                (0, 0, {
                    "product_id": self.product_id.id,
                    "product_uom": product_uom.id,
                    "product_uom_qty": qty,
                    "lot_id": self.lot_id.id if self.lot_id else False,
                    "note": self.notes or False,
                })
            ],
        }

    def action_consume_inventory(self):
        """Use ClinicOne's governed treatment-usage document instead of ad-hoc moves."""
        for rec in self:
            if rec.inventory_usage_id:
                if rec.inventory_usage_id.state == "done":
                    continue
                usage = rec.inventory_usage_id
            else:
                usage = self.env["clinic.treatment.product.usage"].create(
                    rec._prepare_inventory_usage_vals()
                )
                rec.inventory_usage_id = usage.id
            if usage.state == "draft":
                usage.action_confirm()
            if usage.state == "confirmed":
                usage.action_consume()
            # Preserve the legacy picking link only when a downstream implementation
            # has attached a picking; ClinicOne inventory normally uses direct moves.
        return True

    def action_view_inventory_usage(self):
        self.ensure_one()
        if not self.inventory_usage_id:
            raise UserError(_("No ClinicOne inventory consumption document has been created yet."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Inventory Consumption"),
            "res_model": "clinic.treatment.product.usage",
            "view_mode": "form",
            "res_id": self.inventory_usage_id.id,
        }

    def action_view_inventory_moves(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Inventory Moves"),
            "res_model": "stock.move",
            "view_mode": "list,form",
            "domain": [("id", "in", self.inventory_usage_id.move_ids.ids if self.inventory_usage_id else [])],
            "context": {"create": False},
        }


class ClinicEmarOrderInventory(models.Model):
    _inherit = "clinic.emar.order"

    inventory_usage_ids = fields.One2many(
        "clinic.treatment.product.usage", "emar_order_id", string="Inventory Consumptions", readonly=True
    )
    inventory_usage_count = fields.Integer(compute="_compute_inventory_usage_count")

    @api.depends("inventory_usage_ids")
    def _compute_inventory_usage_count(self):
        for rec in self:
            rec.inventory_usage_count = len(rec.inventory_usage_ids)

    def action_view_inventory_usages(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Inventory Consumptions"),
            "res_model": "clinic.treatment.product.usage",
            "view_mode": "list,form",
            "domain": [("emar_order_id", "=", self.id)],
            "context": {"create": False},
        }

