# -*- coding: utf-8 -*-
"""
ClinicOne eMAR - Billing Mixin (Abstract)

Purpose
-------
Reusable billing helpers for models that need to:
- Resolve sales journal by company.
- Determine billing partner (payer) with sensible fallbacks.
- Pick appropriate pricelist and compute price unit.
- Map taxes through partner fiscal position.
- Build account.move and account.move.line values, including eMAR references (if present).
- Create or append to a draft invoice for a given origin object.
- Provide generic wrappers to collect billable items from common line structures.

Design
------
- Abstract mixin: DOES NOT _inherit any eMAR core model; safe to include in any model.
- Soft coupling:
  * If Accounting app is missing, methods raise UserError at the time they are invoked.
  * If invoice/link fields (emar_*) don't exist on account models, they are simply skipped.
- Compatible with Odoo 19 CE.
- Integrates harmoniously with ~38 ClinicOne addons (patient/doctor/treatment/inventory/billing).

Typical usage in a concrete model
---------------------------------
class ClinicEmarOrder(models.Model):
    _name = "clinic.emar.order"
    _inherit = ["mail.thread", "clinic.emar.mixin.audit", "clinic.emar.mixin.billing"]

    def action_create_invoice(self):
        partner = self._billing_get_partner(self)
        items = self._billing_collect_default_items()
        inv = self.billing_append_or_create(self, partner=partner, items=items)
        return True
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def _get_model(env, model_name):
    try:
        return env[model_name]
    except Exception:
        return None


def _has_field(record_or_model, field_name):
    return hasattr(record_or_model, "_fields") and field_name in record_or_model._fields


# ---------------------------------------------------------------------------
# Abstract Billing Mixin
# ---------------------------------------------------------------------------
class ClinicEmarBillingMixin(models.AbstractModel):
    _name = "clinic.emar.mixin.billing"
    _description = "ClinicOne eMAR Billing Mixin (Abstract)"
    _abstract = True

    # -----------------------------------------------------------------------
    # Journal / Partner / Pricelist / Taxes
    # -----------------------------------------------------------------------
    def _billing_get_sale_journal(self, company):
        """
        Find a 'sale' journal for the given company. Fallback to any 'sale' journal.
        """
        Journal = _get_model(self.env, "account.journal")
        if not Journal:
            return None
        dom = [("type", "=", "sale")]
        if company:
            dom.append(("company_id", "=", company.id))
        j = Journal.search(dom, limit=1)
        if not j:
            j = Journal.search([("type", "=", "sale")], limit=1)
        return j

    def _billing_get_partner(self, obj):
        """
        Determine the billing partner (payer). Priority:
          1) obj.payer_partner_id
          2) obj.patient_id.partner_id (if exists)
          3) obj.partner_id
          4) obj.company_id.partner_id (as last resort)
        """
        if _has_field(obj, "payer_partner_id") and obj.payer_partner_id:
            return obj.payer_partner_id
        if _has_field(obj, "patient_id") and obj.patient_id and _has_field(obj.patient_id, "partner_id") and obj.patient_id.partner_id:
            return obj.patient_id.partner_id
        if _has_field(obj, "partner_id") and obj.partner_id:
            return obj.partner_id
        if _has_field(obj, "company_id") and obj.company_id and obj.company_id.partner_id:
            return obj.company_id.partner_id
        return None

    def _billing_get_pricelist(self, obj, partner):
        """
        Get a product.pricelist to compute unit prices. Priority:
          1) obj.pricelist_id
          2) patient.pricelist_id
          3) partner.property_product_pricelist
        """
        Pricelist = _get_model(self.env, "product.pricelist")
        if not Pricelist:
            return None
        if _has_field(obj, "pricelist_id") and obj.pricelist_id:
            return obj.pricelist_id
        patient = getattr(obj, "patient_id", False) if _has_field(obj, "patient_id") else False
        if patient and _has_field(patient, "pricelist_id") and patient.pricelist_id:
            return patient.pricelist_id
        if partner and _has_field(partner, "property_product_pricelist") and partner.property_product_pricelist:
            return partner.property_product_pricelist
        return None

    def _billing_map_taxes(self, product, partner, company):
        """
        Get product customer taxes for company and map through partner's fiscal position.
        """
        Tax = _get_model(self.env, "account.tax")
        if not Tax:
            return self.env["account.tax"]  # empty
        taxes = product.taxes_id.filtered(lambda t: t.company_id == company) if _has_field(product, "taxes_id") else Tax.browse()
        fp = partner.property_account_position_id if partner and _has_field(partner, "property_account_position_id") else False
        if fp and hasattr(fp, "map_tax"):
            taxes = fp.map_tax(taxes, product, partner)
        return taxes

    def _billing_get_price_unit(self, pricelist, product, qty, partner):
        """
        Compute price_unit using pricelist; fallback to product.list_price.
        """
        if pricelist:
            try:
                price = pricelist._get_product_price(product, qty, partner)
                if price is not None:
                    return price
            except Exception:
                pass
        return getattr(product, "list_price", 0.0) or 0.0

    def _billing_get_uom(self, line_or_product):
        """
        Choose UoM for invoice line: line.product_uom_id → line.uom_id → product.uom_id.
        """
        if not line_or_product:
            return None
        if _has_field(line_or_product, "product_uom_id") and line_or_product.product_uom_id:
            return line_or_product.product_uom_id
        if _has_field(line_or_product, "uom_id") and line_or_product.uom_id:
            return line_or_product.uom_id
        if _has_field(line_or_product, "product_id") and line_or_product.product_id and _has_field(line_or_product.product_id, "uom_id"):
            return line_or_product.product_id.uom_id
        if _has_field(line_or_product, "uom_id"):
            return line_or_product.uom_id
        if _has_field(line_or_product, "product") and line_or_product.product and _has_field(line_or_product.product, "uom_id"):
            return line_or_product.product.uom_id
        # When it's a product
        if _has_field(line_or_product, "uom_id"):
            return line_or_product.uom_id
        return None

    # -----------------------------------------------------------------------
    # Builders: account.move & account.move.line
    # -----------------------------------------------------------------------
    def _billing_prepare_invoice_vals(self, origin_obj, partner, *, move_type="out_invoice", journal=None, currency=None):
        """
        Build values for account.move. Includes eMAR header references if fields exist.
        """
        vals = {
            "move_type": move_type,
            "partner_id": partner.id if partner else False,
            "invoice_origin": getattr(origin_obj, "name", False),
            "invoice_date": fields.Date.context_today(self),
            "company_id": origin_obj.company_id.id if _has_field(origin_obj, "company_id") and origin_obj.company_id else self.env.company.id,
        }
        if journal:
            vals["journal_id"] = journal.id
        if partner and _has_field(partner, "property_payment_term_id") and partner.property_payment_term_id:
            vals["invoice_payment_term_id"] = partner.property_payment_term_id.id

        # Header eMAR refs (only if account.move has those fields)
        Move = _get_model(self.env, "account.move")
        if Move:
            if _has_field(Move, "emar_order_id") and origin_obj._name == "clinic.emar.order":
                vals["emar_order_id"] = origin_obj.id
            if _has_field(Move, "emar_prescription_id") and origin_obj._name == "clinic.emar.prescription":
                vals["emar_prescription_id"] = origin_obj.id
            if _has_field(Move, "emar_administration_id") and origin_obj._name == "clinic.emar.administration":
                vals["emar_administration_id"] = origin_obj.id

            # Mirrors for reporting (optional)
            if _has_field(Move, "patient_id") and _has_field(origin_obj, "patient_id") and origin_obj.patient_id:
                vals["patient_id"] = origin_obj.patient_id.id
            if _has_field(Move, "doctor_id") and _has_field(origin_obj, "doctor_id") and origin_obj.doctor_id:
                vals["doctor_id"] = origin_obj.doctor_id.id
        return vals

    def _billing_prepare_line_vals(
        self, origin_obj, line, partner, company, *,
        override_qty=None, override_price=None, override_name=None, admin=None
    ):
        """
        Build a single account.move.line values dict from a billable line or item.

        Parameters
        ----------
        origin_obj : record (order/prescription/administration)
        line : record providing product/qty/uom/notes (or None when using dict items)
        partner : res.partner (billing partner)
        company : res.company
        override_qty : float or None
        override_price : float or None
        override_name : str or None
        admin : record or None (administration context)

        Returns
        -------
        dict or None
        """
        # Resolve product & qty
        product = getattr(line, "product_id", None) if line else None
        qty = override_qty if override_qty is not None else float(getattr(line, "quantity", 0.0) or 0.0)
        if not product or qty <= 0:
            return None

        pricelist = self._billing_get_pricelist(origin_obj, partner)
        price_unit = override_price if override_price is not None else self._billing_get_price_unit(pricelist, product, qty, partner)
        taxes = self._billing_map_taxes(product, partner, company)
        uom = self._billing_get_uom(line) or product.uom_id

        # Description
        name = override_name or product.display_name
        if not override_name:
            if _has_field(line, "notes") and line.notes:
                name = "%s - %s" % (product.display_name, line.notes)
            elif _has_field(origin_obj, "name") and origin_obj.name:
                name = "%s (%s)" % (product.display_name, origin_obj.name)

        vals = {
            "name": name,
            "product_id": product.id,
            "quantity": qty,
            "price_unit": price_unit,
            "tax_ids": [(6, 0, taxes.ids)] if taxes else False,
            "product_uom_id": uom.id if uom else False,
        }

        # eMAR refs on line (if account.move.line exposes them)
        Line = _get_model(self.env, "account.move.line")
        if Line:
            if _has_field(Line, "emar_order_id") and origin_obj._name == "clinic.emar.order":
                vals["emar_order_id"] = origin_obj.id
            if _has_field(Line, "emar_prescription_id") and origin_obj._name == "clinic.emar.prescription":
                vals["emar_prescription_id"] = origin_obj.id
            if _has_field(Line, "emar_administration_id") and admin:
                vals["emar_administration_id"] = admin.id
            if _has_field(Line, "emar_line_id") and line and _has_field(line, "id"):
                vals["emar_line_id"] = line.id

        return vals

    def _billing_prepare_line_vals_from_item(self, origin_obj, item, partner, company, *, admin=None):
        """
        Build line vals from a dict item:
          item = {"product": product, "qty": float, "uom": uom or False, "line": record or False, "price_unit": optional, "name": optional}
        """
        product = item.get("product")
        qty = float(item.get("qty") or 0.0)
        if not product or qty <= 0:
            return None
        price_unit = item.get("price_unit")
        name = item.get("name")
        # Create a lightweight line-like proxy to reuse _billing_get_uom()
        class _Proxy(object):
            pass
        proxy = _Proxy()
        setattr(proxy, "product_id", product)
        if item.get("uom"):
            setattr(proxy, "product_uom_id", item.get("uom"))
        if item.get("line"):
            setattr(proxy, "id", item.get("line").id)
        return self._billing_prepare_line_vals(
            origin_obj,
            proxy,
            partner,
            company,
            override_qty=qty,
            override_price=price_unit,
            override_name=name,
            admin=admin,
        )

    def _billing_prepare_line_commands_from_lines(self, origin_obj, lines, partner, company):
        """
        Convert iterable of line records into [(0, 0, vals), ...] for invoice_line_ids.
        Skips:
          - If line has 'billable' = False
          - If line has usage_type='service' AND billable=False
        """
        res = []
        for ln in lines:
            if "billable" in ln._fields and getattr(ln, "billable") is False:
                continue
            if "usage_type" in ln._fields and ln.usage_type in ("service",) and _has_field(ln, "billable") and not ln.billable:
                continue
            vals = self._billing_prepare_line_vals(origin_obj, ln, partner, company)
            if vals:
                res.append((0, 0, vals))
        return res

    def _billing_prepare_line_commands_from_items(self, origin_obj, items, partner, company, *, admin=None):
        """
        Convert list of dict items (see _billing_prepare_line_vals_from_item) into commands.
        """
        res = []
        for it in items:
            vals = self._billing_prepare_line_vals_from_item(origin_obj, it, partner, company, admin=admin)
            if vals:
                res.append((0, 0, vals))
        return res

    def _billing_find_existing_draft_invoice(self, origin_obj, partner, company, *, move_type="out_invoice"):
        """
        Try to find an existing DRAFT invoice for this partner & eMAR origin.
        """
        Move = _get_model(self.env, "account.move")
        if not Move:
            return None
        domain = [
            ("move_type", "=", move_type),
            ("state", "=", "draft"),
            ("partner_id", "=", partner.id),
            ("company_id", "=", company.id),
        ]
        # Narrow by eMAR origin if account.move exposes the fields
        if _has_field(Move, "emar_order_id") and origin_obj._name == "clinic.emar.order":
            domain.append(("emar_order_id", "=", origin_obj.id))
        elif _has_field(Move, "emar_prescription_id") and origin_obj._name == "clinic.emar.prescription":
            domain.append(("emar_prescription_id", "=", origin_obj.id))
        elif _has_field(Move, "emar_administration_id") and origin_obj._name == "clinic.emar.administration":
            domain.append(("emar_administration_id", "=", origin_obj.id))
        else:
            # fallback to invoice_origin if emar_* fields not available
            origin_name = getattr(origin_obj, "name", False)
            if origin_name:
                domain.append(("invoice_origin", "=", origin_name))
        return Move.search(domain, limit=1)

    def _billing_append_or_create_invoice(self, origin_obj, partner, line_commands, *, move_type="out_invoice", journal=None, currency=None):
        """
        Append to an existing draft invoice or create a new one.
        """
        Move = _get_model(self.env, "account.move")
        if not Move:
            raise UserError(_("Accounting app is not installed."))

        company = origin_obj.company_id or self.env.company
        inv = self._billing_find_existing_draft_invoice(origin_obj, partner, company, move_type=move_type)
        if inv:
            inv.write({"invoice_line_ids": line_commands})
            return inv

        # Create new draft
        journal = journal or self._billing_get_sale_journal(company)
        if not journal:
            raise UserError(_("No sales journal found for this company."))

        vals = self._billing_prepare_invoice_vals(origin_obj, partner, move_type=move_type, journal=journal, currency=currency)
        vals["invoice_line_ids"] = line_commands
        return Move.create(vals)

    # -----------------------------------------------------------------------
    # Public helpers / wrappers for concrete models
    # -----------------------------------------------------------------------
    def _billing_collect_default_lines(self):
        """
        Default collector for lines on self (expects a 'line_ids' O2M with product/qty).
        Concrete models can override to apply custom billable logic.
        """
        self.ensure_one()
        return getattr(self, "line_ids", self.env[self._name]).sudo()

    def _billing_collect_default_items(self):
        """
        Default collector returning [{'product', 'qty', 'uom', 'line', 'price_unit'(opt), 'name'(opt)}].
        By default converts _billing_collect_default_lines().
        """
        items = []
        for ln in self._billing_collect_default_lines():
            prod = getattr(ln, "product_id", False)
            qty = float(getattr(ln, "quantity", 0.0) or 0.0)
            if not prod or qty <= 0:
                continue
            uom = self._billing_get_uom(ln) or (prod.uom_id if _has_field(prod, "uom_id") else False)
            items.append({"product": prod, "qty": qty, "uom": uom, "line": ln})
        return items

    def billing_prepare_line_commands(self, origin_obj=None, partner=None, items=None, *, admin=None):
        """
        Build invoice line commands for the given origin (defaults to self).
        'items' is a list of dicts from _billing_collect_default_items(); if None, it is collected automatically.
        """
        origin = origin_obj or self
        partner = partner or self._billing_get_partner(origin)
        if not partner:
            raise UserError(_("No billing partner resolved."))

        company = origin.company_id or self.env.company
        data_items = items if isinstance(items, list) else origin._billing_collect_default_items()
        if not data_items:
            raise UserError(_("No billable items found."))

        return self._billing_prepare_line_commands_from_items(origin, data_items, partner, company, admin=admin)

    def billing_append_or_create(self, origin_obj=None, partner=None, items=None, *, move_type="out_invoice", journal=None, currency=None, admin=None):
        """
        High-level helper to create/append a draft invoice for 'origin_obj' (defaults to self).
        """
        origin = origin_obj or self
        partner = partner or self._billing_get_partner(origin)
        if not partner:
            raise UserError(_("No billing partner resolved."))

        line_cmds = self.billing_prepare_line_commands(origin_obj=origin, partner=partner, items=items, admin=admin)
        inv = self._billing_append_or_create_invoice(origin, partner, line_cmds, move_type=move_type, journal=journal, currency=currency)

        # Optional chatter notification
        if hasattr(origin, "message_post"):
            try:
                origin.message_post(body=_("Invoice prepared: %s") % (inv.name or inv.display_name))
            except Exception:
                pass
        return inv

