# -*- coding: utf-8 -*-
"""
ClinicOne eMAR - Inventory Mixin (Abstract)

Purpose
-------
Reusable inventory helpers for models that need to:
- Resolve warehouse & picking types safely (internal picking).
- Find or create "Clinic Consumption" destination location.
- Handle lot/serial & expiration fields (life_date vs expiration_date).
- Build stock moves & pickings (reservation & consumption flows).
- Confirm/assign moves (reserve) and validate pickings (done).
- Provide generic "reserve" and "consume" wrappers with soft coupling.

This mixin is abstract and DOES NOT _inherit any eMAR core model. It can be
safely included by any model in this addon and the wider ClinicOne ecosystem.

Compatibility
-------------
- Odoo 19 CE.
- Optional ties with ClinicOne's clinic_inventory (xml_id location) if installed.
- Works even if Inventory app isn't installed (raises graceful UserError only
  when inventory actions are requested).

Typical Usage (in a concrete model)
-----------------------------------
class ClinicEmarOrder(models.Model):
    _name = "clinic.emar.order"
    _inherit = ["mail.thread", "clinic.emar.mixin.audit", "clinic.emar.mixin.inventory"]

    def action_reserve_inventory(self):
        # Optional: provide your own 'lines' structure, see _inventory_collect_reservable_lines() contract.
        picking, moves = self.inventory_build_reservation()
        return True

class ClinicEmarAdministration(models.Model):
    _name = "clinic.emar.administration"
    _inherit = ["mail.thread", "clinic.emar.mixin.audit", "clinic.emar.mixin.inventory"]

    def action_consume_inventory(self):
        picking, moves = self.inventory_consume()
        return True
"""

from datetime import date, datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# ---------------------------------------------------------------------------
# Small utilities (internal)
# ---------------------------------------------------------------------------
def _get_model(env, model_name):
    try:
        return env[model_name]
    except Exception:
        return None


def _has_field(record_or_model, field_name):
    return hasattr(record_or_model, "_fields") and field_name in record_or_model._fields


# ---------------------------------------------------------------------------
# Abstract Mixin
# ---------------------------------------------------------------------------
class ClinicEmarInventoryMixin(models.AbstractModel):
    _name = "clinic.emar.mixin.inventory"
    _description = "ClinicOne eMAR Inventory Mixin (Abstract)"
    _abstract = True

    # -----------------------------------------------------------------------
    # LOT / EXPIRATION
    # -----------------------------------------------------------------------
    def _inventory_get_lot_expiration_field(self):
        """
        Return the field name used for expiration on stock.lot:
        'life_date' (older) or 'expiration_date' (newer). Return None if not found.
        """
        Lot = _get_model(self.env, "stock.lot")
        if not Lot:
            return None
        if "life_date" in Lot._fields:
            return "life_date"
        if "expiration_date" in Lot._fields:
            return "expiration_date"
        return None

    def _inventory_is_lot_expired(self, lot, at_date=None):
        """
        Check if a given lot is expired at a given date (today by default).
        """
        if not lot:
            return False
        exp_field = self._inventory_get_lot_expiration_field()
        if not exp_field or not _has_field(lot, exp_field):
            return False
        ref = at_date or fields.Date.context_today(self)
        try:
            dref = fields.Date.from_string(ref) if isinstance(ref, str) else ref
        except Exception:
            dref = date.today()
        val = getattr(lot, exp_field, False)
        if isinstance(val, datetime):
            val = val.date()
        return bool(val and val < dref)

    # -----------------------------------------------------------------------
    # WAREHOUSE / PICKING TYPE / LOCATIONS
    # -----------------------------------------------------------------------
    def _inventory_get_default_warehouse(self, company_id=None):
        """
        Return preferred stock.warehouse for a company.
        """
        Wh = _get_model(self.env, "stock.warehouse")
        if not Wh:
            return None
        cid = company_id or (self.env.company.id if self.env.company else False)
        dom = [("company_id", "=", cid)] if cid else []
        wh = Wh.search(dom, limit=1)
        if wh:
            return wh
        # last resort: any warehouse
        return Wh.search([], limit=1)

    def _inventory_get_internal_picking_type(self, warehouse):
        """
        Return an 'internal' stock.picking.type for the given warehouse (preferred) or globally.
        """
        PkType = _get_model(self.env, "stock.picking.type")
        if not (PkType and warehouse):
            return None
        ptype = PkType.search([("warehouse_id", "=", warehouse.id), ("code", "=", "internal")], limit=1)
        if ptype:
            return ptype
        return PkType.search([("code", "=", "internal")], limit=1)

    def _inventory_find_or_create_consumption_location(self, company_id, warehouse=None):
        """
        Find or create a dedicated 'Clinic Consumption' internal location:
        1) Try xml_id "clinic_inventory.location_clinic_consumption" if clinic_inventory is installed.
        2) Search internal location by name (ilike 'Clinic Consumption') in company.
        3) Create a child internal location under warehouse.lot_stock_id (if possible).
        4) Fallback to warehouse.lot_stock_id (may cause no-op moves if src=dst).
        """
        Loc = _get_model(self.env, "stock.location")
        if not Loc:
            return None

        # 1) Try xml_id
        try:
            loc = self.env.ref("clinic_inventory.location_clinic_consumption", raise_if_not_found=False)
            if loc and (not loc.company_id or loc.company_id.id == company_id):
                return loc
        except Exception:
            pass

        # 2) Search by name
        loc = Loc.search([
            ("name", "ilike", "Clinic Consumption"),
            ("usage", "=", "internal"),
            "|", ("company_id", "=", False), ("company_id", "=", company_id),
        ], limit=1)
        if loc:
            return loc

        # 3) Create child location under WH stock
        wh = warehouse or self._inventory_get_default_warehouse(company_id)
        parent = wh.lot_stock_id if wh and wh.lot_stock_id else None
        vals = {
            "name": "Clinic Consumption",
            "usage": "internal",
            "company_id": company_id,
        }
        if parent:
            vals["location_id"] = parent.id
        try:
            loc = Loc.create(vals)
            if loc:
                return loc
        except Exception:
            pass

        # 4) Fallback
        return parent

    # -----------------------------------------------------------------------
    # MOVE / PICKING BUILDERS
    # -----------------------------------------------------------------------
    def _inventory_prepare_move_vals(
        self, owner, line, product, qty, src_loc, dst_loc, *,
        lot=None, picking=None, admin=None, origin=None, name=None
    ):
        """
        Build values for stock.move (does not create). Links to eMAR via fields if present.

        Parameters
        ----------
        owner : record (the business doc, e.g., eMAR order/administration)
        line : optional related line (e.g., medication line)
        product : product.product
        qty : float
        src_loc : stock.location (source)
        dst_loc : stock.location (destination)
        lot : stock.lot or False
        picking : stock.picking or False
        admin : administration record (if relevant)
        origin : str (override)
        name : str (override)
        """
        if not product or qty <= 0:
            return None

        company_id = owner.company_id.id if _has_field(owner, "company_id") and owner.company_id else (self.env.company.id)
        uom = product.uom_id if _has_field(product, "uom_id") else False
        mv_name = name or _("eMAR: %s") % (getattr(owner, "name", _("Document")))
        mv_origin = origin or getattr(owner, "name", _("eMAR"))

        vals = {
            "name": mv_name,
            "company_id": company_id,
            "product_id": product.id,
            "product_uom": uom.id if uom else False,
            "product_uom_qty": qty,
            "location_id": src_loc.id if src_loc else False,
            "location_dest_id": dst_loc.id if dst_loc else False,
            "origin": mv_origin,
            "picking_id": picking.id if picking else False,
        }

        # Bridge links (only if field exists on stock.move)
        Move = _get_model(self.env, "stock.move")
        if Move:
            if _has_field(Move, "emar_order_id") and owner._name == "clinic.emar.order":
                vals["emar_order_id"] = owner.id
            if _has_field(Move, "emar_line_id") and line:
                vals["emar_line_id"] = line.id
            if _has_field(Move, "emar_administration_id") and admin:
                vals["emar_administration_id"] = admin.id
            if lot and _has_field(Move, "restrict_lot_id"):
                vals["restrict_lot_id"] = lot.id
        return vals

    def _inventory_create_picking(self, owner, picking_type, src_loc, dst_loc, *, name=None, origin=None, extra=None):
        """
        Create stock.picking for owner; link back via emar_order_id if available.
        """
        Picking = _get_model(self.env, "stock.picking")
        if not Picking:
            raise UserError(_("Inventory app is not installed."))

        vals = {
            "name": name or _("EMAR - %s") % (getattr(owner, "name", _("Document")),),
            "picking_type_id": picking_type.id if picking_type else False,
            "location_id": src_loc.id if src_loc else False,
            "location_dest_id": dst_loc.id if dst_loc else False,
            "scheduled_date": fields.Datetime.now(),
            "origin": origin or getattr(owner, "name", _("eMAR")),
            "company_id": owner.company_id.id if _has_field(owner, "company_id") and owner.company_id else self.env.company.id,
        }

        # Bridge link on picking header if exists
        if _has_field(Picking, "emar_order_id") and owner._name == "clinic.emar.order":
            vals["emar_order_id"] = owner.id

        if extra and isinstance(extra, dict):
            vals.update({k: v for k, v in extra.items() if k in Picking._fields})

        return Picking.create(vals)

    def _inventory_create_and_reserve_moves(self, picking, move_vals_list):
        """
        Create moves in given picking, then confirm & assign (reserve).
        """
        Move = _get_model(self.env, "stock.move")
        if not (Move and picking and move_vals_list):
            return Move.browse()
        moves = Move.create(move_vals_list)
        try:
            moves._action_confirm()
            moves._action_assign()
        except Exception:
            # leave unreserved if assign fails
            pass
        return moves

    def _inventory_set_moves_done_quantities(self, moves):
        """
        Ensure moves (or move lines) carry done quantities equal to planned.
        """
        for mv in moves:
            try:
                if mv.move_line_ids:
                    for ml in mv.move_line_ids:
                        # Odoo 19 uses stock.move.line.quantity for the done
                        # quantity. Keep a guarded fallback for older databases
                        # during migrations, without depending on qty_done.
                        if _has_field(ml, "quantity"):
                            current = ml.quantity or 0.0
                            ml.quantity = current or mv.product_uom_qty
                        elif _has_field(ml, "qty_done"):
                            ml.qty_done = ml.qty_done or mv.product_uom_qty
                elif _has_field(mv, "quantity"):
                    mv.quantity = mv.product_uom_qty
                elif _has_field(mv, "quantity_done"):
                    mv.quantity_done = mv.product_uom_qty
            except Exception:
                pass
        return True

    def _inventory_validate_picking(self, picking):
        """
        Validate a picking safely: prefer _action_done; fallback to button_validate.
        """
        if not picking:
            return False
        try:
            picking._action_done()
            return True
        except Exception:
            try:
                picking.button_validate()
                return True
            except Exception:
                return False

    # -----------------------------------------------------------------------
    # DEFAULT COLLECTORS (can be overridden in concrete models)
    # -----------------------------------------------------------------------
    def _inventory_collect_reservable_lines(self):
        """
        Default collector for 'reservation' context.
        Expects that 'self' is a single business document with a 'line_ids' field
        that holds items having: product_id, quantity, optional usage_type & lot_id.

        Returns list of dicts: [{"product": product, "qty": float, "lot": lot_or_False, "line": record_or_False}]
        """
        self.ensure_one()
        res = []
        lines = getattr(self, "line_ids", [])
        for ln in lines:
            prod = getattr(ln, "product_id", False)
            qty = getattr(ln, "quantity", 0.0) or 0.0
            if not prod or qty <= 0:
                continue
            if _has_field(ln, "usage_type") and ln.usage_type in ("service",):
                # skip pure services by default
                continue
            lot = getattr(ln, "lot_id", False) if _has_field(ln, "lot_id") else False
            res.append({"product": prod, "qty": float(qty), "lot": lot, "line": ln})
        return res

    def _inventory_collect_consumption_items(self):
        """
        Default collector for 'consumption' context.
        Priority:
          A) self.admin_line_ids / self.line_ids with product/qty[/lot]
          B) fallback to self.line_ids like reservation
        Returns list of dicts: [{"product": product, "qty": float, "lot": lot_or_False, "line": record_or_False}]
        """
        self.ensure_one()
        for fname in ("admin_line_ids", "line_ids", "consumable_line_ids"):
            if _has_field(self, fname) and getattr(self, fname):
                items = []
                for ln in getattr(self, fname):
                    prod = getattr(ln, "product_id", False)
                    if not prod:
                        continue
                    qty = getattr(ln, "quantity", None)
                    if qty is None:
                        qty = getattr(ln, "qty", None)
                    qty = float(qty or 0.0)
                    if qty <= 0:
                        continue
                    lot = getattr(ln, "lot_id", False) if _has_field(ln, "lot_id") else False
                    src_line = getattr(ln, "order_line_id", False) if _has_field(ln, "order_line_id") else False
                    items.append({"product": prod, "qty": qty, "lot": lot, "line": src_line or ln})
                if items:
                    return items
        # Fallback
        return self._inventory_collect_reservable_lines()

    # -----------------------------------------------------------------------
    # PUBLIC WRAPPERS: RESERVATION / RELEASE / CONSUMPTION
    # -----------------------------------------------------------------------
    def inventory_build_reservation(self, *, lines=None, warehouse=None, picking_type=None,
                                    picking_name=None, extra_picking_vals=None):
        """
        Create an INTERNAL picking to reserve inventory for this business object.

        Parameters
        ----------
        lines : list[dict] or None
            If None, uses _inventory_collect_reservable_lines().
            Each item: {"product": product, "qty": float, "lot": lot_or_False, "line": record_or_False}
        warehouse : stock.warehouse or None
            If None, resolved from company.
        picking_type : stock.picking.type or None
            If None, resolved as 'internal' for the given warehouse.
        picking_name : str or None
            Override picking name (default "EMAR Reservation - <owner.name>").
        extra_picking_vals : dict or None
            Extra values for stock.picking (filtered against picking fields).

        Returns
        -------
        (picking, moves)
        """
        Picking = _get_model(self.env, "stock.picking")
        Move = _get_model(self.env, "stock.move")
        if not (Picking and Move):
            raise UserError(_("Inventory app is not installed."))

        self.ensure_one()
        company_id = self.company_id.id if _has_field(self, "company_id") and self.company_id else self.env.company.id
        wh = warehouse or self._inventory_get_default_warehouse(company_id)
        if not wh:
            raise UserError(_("No warehouse available for this company."))

        ptype = picking_type or self._inventory_get_internal_picking_type(wh)
        if not ptype:
            raise UserError(_("No internal picking type found."))

        src = wh.lot_stock_id
        dst = self._inventory_find_or_create_consumption_location(company_id, warehouse=wh)
        if not src or not dst:
            raise UserError(_("Could not resolve source/destination locations."))

        picking = self._inventory_create_picking(
            self,
            ptype,
            src,
            dst,
            name=picking_name or _("EMAR Reservation - %s") % (getattr(self, "name", _("Document")),),
            origin=getattr(self, "name", _("eMAR")),
            extra=extra_picking_vals or {},
        )

        items = lines if isinstance(lines, list) else self._inventory_collect_reservable_lines()
        if not items:
            raise UserError(_("No reservable lines to process."))

        move_vals = []
        for it in items:
            prod = it.get("product")
            qty = float(it.get("qty") or 0.0)
            lot = it.get("lot")
            ln = it.get("line")
            vals = self._inventory_prepare_move_vals(self, ln, prod, qty, src, dst, lot=lot, picking=picking)
            if vals:
                move_vals.append(vals)

        moves = self._inventory_create_and_reserve_moves(picking, move_vals)

        # Notify (chatter) if available
        if hasattr(self, "message_post"):
            try:
                self.message_post(body=_("Reservation picking prepared with %s move(s).") % len(moves))
            except Exception:
                pass
        return picking, moves

    def inventory_release_reservation(self, picking=None):
        """
        Cancel a reservation picking to release reserved quants.
        If picking is None, tries to use self.reservation_picking_id if present.
        """
        Picking = _get_model(self.env, "stock.picking")
        if not Picking:
            raise UserError(_("Inventory app is not installed."))

        self.ensure_one()
        pk = picking or (self.reservation_picking_id if _has_field(self, "reservation_picking_id") else None)
        if not pk:
            return True
        if pk.state in ("done", "cancel"):
            return True
        try:
            pk.action_cancel()
        except Exception:
            pk.write({"state": "cancel"})
        if hasattr(self, "message_post"):
            try:
                self.message_post(body=_("Reservation picking cancelled to release stock."))
            except Exception:
                pass
        return True

    def inventory_consume(self, *, items=None, warehouse=None, picking_type=None,
                          picking_name=None, extra_picking_vals=None, admin=None):
        """
        Create and validate an INTERNAL picking to consume inventory for this business object.

        Parameters
        ----------
        items : list[dict] or None
            If None, uses _inventory_collect_consumption_items().
            Each item: {"product": product, "qty": float, "lot": lot_or_False, "line": record_or_False}
        warehouse : stock.warehouse or None
            If None, resolved from company.
        picking_type : stock.picking.type or None
            If None, resolved as 'internal' for the given warehouse.
        picking_name : str or None
            Override picking name (default "EMAR Consumption - <owner.name>").
        extra_picking_vals : dict or None
            Extra values for stock.picking (filtered against picking fields).
        admin : record or None
            Administration context record (for move linkage if stock.move has emar_administration_id).

        Returns
        -------
        (picking, moves)
        """
        Picking = _get_model(self.env, "stock.picking")
        Move = _get_model(self.env, "stock.move")
        if not (Picking and Move):
            raise UserError(_("Inventory app is not installed."))

        self.ensure_one()
        company_id = self.company_id.id if _has_field(self, "company_id") and self.company_id else self.env.company.id
        wh = warehouse or self._inventory_get_default_warehouse(company_id)
        if not wh:
            raise UserError(_("No warehouse available for this company."))

        ptype = picking_type or self._inventory_get_internal_picking_type(wh)
        if not ptype:
            raise UserError(_("No internal picking type found."))

        src = wh.lot_stock_id
        dst = self._inventory_find_or_create_consumption_location(company_id, warehouse=wh)
        if not src or not dst:
            raise UserError(_("Could not resolve source/destination locations."))

        picking = self._inventory_create_picking(
            self,
            ptype,
            src,
            dst,
            name=picking_name or _("EMAR Consumption - %s") % (getattr(self, "name", _("Document")),),
            origin=getattr(self, "name", _("eMAR")),
            extra=extra_picking_vals or {},
        )

        data_items = items if isinstance(items, list) else self._inventory_collect_consumption_items()
        if not data_items:
            raise UserError(_("No items to consume."))

        move_vals = []
        for it in data_items:
            prod = it.get("product")
            qty = float(it.get("qty") or 0.0)
            lot = it.get("lot")
            ln = it.get("line")
            vals = self._inventory_prepare_move_vals(self, ln, prod, qty, src, dst, lot=lot, picking=picking, admin=admin or self)
            if vals:
                move_vals.append(vals)

        moves = self._inventory_create_and_reserve_moves(picking, move_vals)
        self._inventory_set_moves_done_quantities(moves)

        ok = self._inventory_validate_picking(picking)
        if not ok and hasattr(self, "message_post"):
            try:
                self.message_post(body=_("Consumption picking created but not validated automatically. Please review."))
            except Exception:
                pass

        if hasattr(self, "message_post"):
            try:
                self.message_post(body=_("Inventory consumed. Picking: %s") % (picking.name,))
            except Exception:
                pass
        return picking, moves

