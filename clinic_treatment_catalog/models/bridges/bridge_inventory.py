# -*- coding: utf-8 -*-
# ClinicOne - Treatment Catalog & Pricing
# File: models/bridges/bridge_inventory.py
#
# Inventory Bridge: kebutuhan, reservasi, konsumsi, dan release untuk Treatment/Bundle.
# Soft-coupled: seluruh akses model/field dicek aman, agar tidak memaksa install modul lain.
#
from odoo import api, models, fields, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ClinicInventoryBridge(models.AbstractModel):
    _name = "clinic.inventory.bridge"
    _description = "ClinicOne Inventory Bridge (consumables planning & execution)"

    # ======================================================================
    # PUBLIC API — REQUIREMENTS
    # ======================================================================
    @api.model
    def compute_requirements_for_treatment(self, treatment, quantity=1.0, context_tags=None, explode_bom=True):
        """Hitung daftar kebutuhan consumable untuk satu Treatment.
        Return: list of dicts (normalized requirements):
        [{
           'product_id': int,
           'uom_id': int,
           'qty': float,               # total qty (sudah dikali quantity)
           'name': str,                # label/notes
           'allow_substitutes': bool,  # hint
           'lot_policy': 'none'|'required'|'optional',
        }, ...]
        """
        self._assert_single(treatment, "clinic.treatment.catalog")
        qty = float(quantity or 1.0)
        reqs = []

        # 1) Kumpulkan dari line-line consumable pada Treatment (jika ada)
        for line in self._iter_treatment_consumable_lines(treatment):
            prod = getattr(line, "product_id", False)
            if not (prod and prod.exists()):
                continue
            line_qty = self._coerce_float(getattr(line, "quantity", 0.0)) or self._coerce_float(getattr(line, "qty", 0.0)) or 0.0
            if line_qty <= 0:
                continue
            uom = getattr(line, "uom_id", False) or getattr(prod, "uom_id", False)
            reqs.append({
                "product_id": prod.id,
                "uom_id": uom.id if uom else False,
                "qty": line_qty * qty,
                "name": getattr(line, "name", False) or getattr(prod, "display_name", _("Consumable")),
                "allow_substitutes": bool(getattr(line, "allow_substitutes", False)),
                "lot_policy": getattr(line, "lot_policy", "none") if hasattr(line, "lot_policy") else "none",
            })

        # 2) Tambahan: dari BoM product service (opsional, jika mrp aktif)
        if explode_bom:
            bom_reqs = self._explode_bom_of_service_product(treatment, qty)
            reqs += bom_reqs

        # 3) Gabungkan qty per product/uom
        return self._group_requirements(reqs)

    @api.model
    def compute_requirements_for_bundle(self, bundle, quantity=1.0, context_tags=None, explode_bom=True):
        """Hitung kebutuhan untuk Bundle (agregasi dari treatment di dalamnya)."""
        self._assert_single(bundle, "clinic.treatment.bundle")
        qty = float(quantity or 1.0)
        reqs = []
        # Dari line bundle
        for bl in getattr(bundle, "line_ids", self.env[bundle._name]):
            tr = getattr(bl, "treatment_id", False)
            line_qty = self._coerce_float(getattr(bl, "quantity", 1.0)) or 1.0
            if tr and tr.exists():
                reqs += self.compute_requirements_for_treatment(tr, quantity=(qty * line_qty), context_tags=context_tags, explode_bom=explode_bom)
        # Gabungkan (sudah tergabung oleh compute di atas; untuk jaga-jaga)
        return self._group_requirements(reqs)

    # ======================================================================
    # PUBLIC API — RESERVATION
    # ======================================================================
    @api.model
    def plan_reservation_from_booking(
        self,
        booking,
        allow_substitutes=True,
        create_picking=True,
        group_by_booking=True,
        auto_assign=True,
        debug=False,
    ):
        """Buat rencana reservasi stok dari booking.
        - Jika modul stock tidak ada → kembalikan payload simulasi (tanpa membuat dokumen).
        - Jika ada → buat stock.picking bertipe 'consumption' (configurable), satu picking per booking.
        Return dict:
        {
          'booking_id': id,
          'picking_id': id|False,
          'created_move_ids': [ids],
          'requirements': [ {product_id, uom_id, qty, name}, ... ],
          'simulated': bool,     # True jika tanpa stock
          'message': str,
        }
        """
        self._assert_record(booking)
        company = self._get_company(booking)
        reqs, qty_map = self._collect_requirements_from_booking(booking)

        if not reqs:
            return {"booking_id": booking.id, "picking_id": False, "created_move_ids": [], "requirements": [], "simulated": True, "message": _("No consumables.")}

        # Jika modul stock tidak ada → simulasi saja
        if not self._has_stock():
            return {
                "booking_id": booking.id,
                "picking_id": False,
                "created_move_ids": [],
                "requirements": reqs,
                "simulated": True,
                "message": _("Stock app not installed. Reservation is simulated only."),
            }

        # Siapkan picking (1 per booking)
        picking_type = self._resolve_consumption_picking_type(company)
        if not picking_type:
            raise UserError(_("Configure a consumption picking type (Settings → Inventory)."))

        src, dest = self._resolve_locations(booking, picking_type)
        picking = self._get_or_create_picking_for_booking(booking, picking_type, src, dest)

        created_moves = []
        for r in reqs:
            product = self.env["product.product"].browse(r["product_id"])
            uom = self.env["uom.uom"].browse(r["uom_id"]) if r.get("uom_id") else product.uom_id
            move_vals = {
                "name": r.get("name") or product.display_name,
                "product_id": product.id,
                "product_uom": uom.id if uom else product.uom_id.id,
                "product_uom_qty": r["qty"],
                "picking_id": picking.id,
                "location_id": src.id,
                "location_dest_id": dest.id,
                "state": "draft",
            }
            mv = self.env["stock.move"].create(move_vals)
            created_moves.append(mv.id)

        # Confirm & Assign (reserve)
        picking.action_confirm()
        if auto_assign:
            picking.action_assign()

        msg = _("Reservation created (Picking %s).") % picking.name
        if debug:
            _logger.info("Reservation picking %s created for booking %s", picking.name, self._display_booking(booking))
        return {
            "booking_id": booking.id,
            "picking_id": picking.id,
            "created_move_ids": created_moves,
            "requirements": reqs,
            "simulated": False,
            "message": msg,
        }

    # ======================================================================
    # PUBLIC API — CONSUMPTION (VALIDATE)
    # ======================================================================
    @api.model
    def confirm_consumption_from_booking(
        self,
        booking,
        lot_map=None,
        use_reserved_qty=True,
        auto_post=True,
        allow_backorder=False,
        debug=False,
    ):
        """Validasi konsumsi untuk booking:
        - Jika picking reservasi sudah ada: isi `quantity_done` lalu validate.
        - Jika belum ada: buat picking baru dan validate.
        - lot_map: dict {product_id: 'LOTNAME' atau lot_id} untuk isi lot/serial (opsional).
        - use_reserved_qty: jika True → jadikan seluruh reserved sebagai done bila quantity_done belum diisi.
        Return: {'picking_id': id|False, 'done': bool, 'message': str}
        """
        self._assert_record(booking)
        company = self._get_company(booking)
        lot_map = lot_map or {}

        # Jika stock tidak ada → simulasi sukses
        if not self._has_stock():
            return {"picking_id": False, "done": True, "message": _("Stock app not installed. Consumption simulated.")}

        picking_type = self._resolve_consumption_picking_type(company)
        if not picking_type:
            raise UserError(_("Configure a consumption picking type (Settings → Inventory)."))

        src, dest = self._resolve_locations(booking, picking_type)
        picking = self._find_picking_for_booking(booking, picking_type) or self._get_or_create_picking_for_booking(booking, picking_type, src, dest)

        # Pastikan moves ada (jika baru dibuat dari nol)
        if not picking.move_ids:
            reqs, _ = self._collect_requirements_from_booking(booking)
            for r in reqs:
                product = self.env["product.product"].browse(r["product_id"])
                uom = self.env["uom.uom"].browse(r["uom_id"]) if r.get("uom_id") else product.uom_id
                mv = self.env["stock.move"].create({
                    "name": r.get("name") or product.display_name,
                    "product_id": product.id,
                    "product_uom": uom.id,
                    "product_uom_qty": r["qty"],
                    "picking_id": picking.id,
                    "location_id": src.id,
                    "location_dest_id": dest.id,
                    "state": "draft",
                })
            picking.action_confirm()
            picking.action_assign()

        # Isi quantity_done dari reserved jika diminta
        for mv in picking.move_ids:
            if use_reserved_qty:
                # If already have move lines reserved → set done = reserved
                for ml in mv.move_line_ids:
                    if not ml.qty_done or ml.qty_done == 0:
                        ml.qty_done = ml.product_uom_qty
            # Lot/serial: isi dari lot_map bila disediakan (by id atau name)
            if lot_map:
                self._apply_lot_map_on_move_lines(mv, lot_map)

        # Validate
        if allow_backorder:
            result = picking.button_validate()
        else:
            # Tahan wizard backorder: atur context agar auto no backorder bila di Odoo 15+ (variasi antar versi)
            try:
                ctx = dict(self.env.context, cancel_backorder=True)
                picking.with_context(ctx).button_validate()
                result = True
            except Exception:
                result = picking.button_validate()

        if debug:
            _logger.info("Consumption validated for picking %s (booking %s)", picking.name, self._display_booking(booking))
        return {"picking_id": picking.id, "done": True, "message": _("Consumption validated for %s.") % picking.name}

    # ======================================================================
    # PUBLIC API — RELEASE / CANCEL
    # ======================================================================
    @api.model
    def release_reservation_from_booking(self, booking, cancel_moves=False):
        """Batalkan reservasi untuk booking jika picking (belum selesai) tersedia.
        - cancel_moves=False: unreserve (set ke confirmed), biarkan picking tetap ada.
        - cancel_moves=True : batalkan picking (action_cancel) bila masih draft/confirmed/assigned.
        """
        self._assert_record(booking)
        if not self._has_stock():
            return {"ok": True, "message": _("Stock app not installed. Nothing to release.")}

        picking = self._find_any_consumption_picking_for_booking(booking)
        if not picking:
            return {"ok": True, "message": _("No reservation found to release.")}

        if picking.state == "done":
            return {"ok": False, "message": _("Picking is already done, cannot release.")}
        if cancel_moves:
            picking.action_cancel()
            return {"ok": True, "message": _("Reservation picking %s cancelled.") % picking.name}
        else:
            try:
                picking.do_unreserve()
            except Exception:
                # fallback manual: set move to confirmed, unlink move lines
                for mv in picking.move_ids:
                    mv._do_unreserve()
            return {"ok": True, "message": _("Reservation unreserved for picking %s.") % picking.name}

    # ======================================================================
    # INTERNAL — REQUIREMENTS DISCOVERY
    # ======================================================================
    def _iter_treatment_consumable_lines(self, treatment):
        """Generator recordset untuk berbagai kemungkinan nama relasi consumable."""
        for fname in ("consumable_line_ids", "material_line_ids", "bom_line_ids"):
            if fname in treatment._fields:
                lines = getattr(treatment, fname)
                if lines:
                    for ln in lines:
                        yield ln

    def _explode_bom_of_service_product(self, treatment, qty):
        """Jika modul MRP ada dan service product memiliki BoM, explode menjadi kebutuhan komponen."""
        reqs = []
        product = self._service_product(treatment)
        if not product:
            return reqs
        if not self._has_mrp():
            return reqs
        BoM = self.env["mrp.bom"]
        bom = BoM.search([("product_tmpl_id", "=", product.product_tmpl_id.id)], limit=1)
        if not bom:
            return reqs
        try:
            # explode mengembalikan komponen beserta uom & qty
            (bom_line_ids, _) = bom.explode(product.product_tmpl_id, qty, picking_type=bom.picking_type_id)
        except Exception:
            # fallback versi Odoo berbeda
            (bom_line_ids, _) = bom.explode(product, qty)
        for line, line_data in bom_line_ids:
            comp = getattr(line, "product_id", False)
            if not comp:
                continue
            uom = getattr(line, "product_uom_id", False) or comp.uom_id
            comp_qty = line_data.get("qty", 0.0) or getattr(line, "product_qty", 0.0) or 0.0
            if comp_qty <= 0:
                continue
            reqs.append({
                "product_id": comp.id,
                "uom_id": uom.id if uom else False,
                "qty": comp_qty,  # sudah dikalikan qty pada explode
                "name": getattr(line, "name", False) or comp.display_name,
                "allow_substitutes": False,
                "lot_policy": "none",
            })
        return reqs

    def _group_requirements(self, reqs):
        """Gabungkan requirement sejenis (product_id & uom_id sama)."""
        key_map = {}
        for r in reqs or []:
            if not r.get("product_id"):
                continue
            key = (r["product_id"], r.get("uom_id") or 0)
            acc = key_map.setdefault(key, {
                "product_id": r["product_id"],
                "uom_id": r.get("uom_id") or False,
                "qty": 0.0,
                "name": r.get("name") or "",
                "allow_substitutes": bool(r.get("allow_substitutes")),
                "lot_policy": r.get("lot_policy", "none"),
            })
            acc["qty"] += float(r.get("qty") or 0.0)
        return list(key_map.values())

    def _collect_requirements_from_booking(self, booking):
        """Ambil list semua treatment/bundle pada booking dan hitung kebutuhannya."""
        reqs = []
        qty_map = {}
        # Temukan line-line booking
        line_models = ["clinic.booking.line", "clinic.appointment.line", "clinic.visit.line"]
        lines = self._find_lines(booking, line_models)
        if not lines:
            # booking single target
            target, is_bundle = self._resolve_target(booking)
            if target:
                q = self._get_quantity(booking) or 1.0
                if is_bundle:
                    reqs += self.compute_requirements_for_bundle(target, quantity=q)
                else:
                    reqs += self.compute_requirements_for_treatment(target, quantity=q)
        else:
            for ln in lines:
                target, is_bundle = self._resolve_target(ln)
                if not target:
                    continue
                q = self._get_quantity(ln) or 1.0
                if is_bundle:
                    reqs += self.compute_requirements_for_bundle(target, quantity=q)
                else:
                    reqs += self.compute_requirements_for_treatment(target, quantity=q)
        reqs = self._group_requirements(reqs)
        return reqs, qty_map

    # ======================================================================
    # INTERNAL — PICKING / MOVE HELPERS
    # ======================================================================
    def _get_or_create_picking_for_booking(self, booking, picking_type, src_loc, dest_loc):
        pk = self._find_picking_for_booking(booking, picking_type)
        if pk:
            # pastikan lokasi sesuai
            if pk.location_id.id != src_loc.id or pk.location_dest_id.id != dest_loc.id:
                try:
                    pk.write({"location_id": src_loc.id, "location_dest_id": dest_loc.id})
                except Exception:
                    pass
            return pk

        vals = {
            "picking_type_id": picking_type.id,
            "location_id": src_loc.id,
            "location_dest_id": dest_loc.id,
            "origin": self._display_booking(booking),
            "company_id": self._get_company(booking).id,
        }
        # partner di picking (opsional)
        partner = self._get_partner(booking)
        if partner:
            vals["partner_id"] = partner.id

        pk = self.env["stock.picking"].create(vals)
        return pk

    def _find_picking_for_booking(self, booking, picking_type):
        Pick = self.env["stock.picking"]
        pk = Pick.search([
            ("picking_type_id", "=", picking_type.id),
            ("origin", "=", self._display_booking(booking)),
            ("company_id", "=", self._get_company(booking).id),
            ("state", "in", ["draft", "confirmed", "assigned"]),
        ], limit=1)
        return pk

    def _find_any_consumption_picking_for_booking(self, booking):
        Pick = self.env["stock.picking"]
        ptypes = self.env["stock.picking.type"].search([("code", "in", ["internal", "outgoing", "incoming"])])
        pk = Pick.search([
            ("origin", "=", self._display_booking(booking)),
            ("picking_type_id", "in", ptypes.ids),
            ("company_id", "=", self._get_company(booking).id),
            ("state", "in", ["draft", "confirmed", "assigned"]),
        ], limit=1)
        return pk

    def _apply_lot_map_on_move_lines(self, move, lot_map):
        """Isi lot/serial pada move lines sesuai lot_map {product_id: lot(id|name)}."""
        Lot = self.env.registry.get("stock.lot") and self.env["stock.lot"] or None
        if not Lot:
            return
        for ml in move.move_line_ids:
            if not ml.product_id or ml.product_id.id not in lot_map:
                continue
            lot_val = lot_map.get(ml.product_id.id)
            lot_id = None
            # Bisa id atau nama
            if isinstance(lot_val, int):
                lot_id = lot_val
            else:
                # find/create by name & product
                lot = Lot.search([("name", "=", str(lot_val)), ("product_id", "=", ml.product_id.id)], limit=1)
                if not lot:
                    # hanya create jika product tracking != none
                    if getattr(ml.product_id, "tracking", "none") != "none":
                        lot = Lot.create({"name": str(lot_val), "product_id": ml.product_id.id, "company_id": move.company_id.id})
                lot_id = lot.id if lot else None
            if lot_id:
                try:
                    ml.write({"lot_id": lot_id})
                except Exception:
                    pass

    # ======================================================================
    # INTERNAL — RESOLUTION (LOCATIONS, PICKING TYPE)
    # ======================================================================
    def _resolve_consumption_picking_type(self, company):
        """Ambil picking type untuk konsumsi klinik.
        Urutan:
          1) company.clinic_consumption_picking_type_id (jika ada)
          2) stock.picking.type name ilike 'consumption' (code 'internal')
          3) default internal picking type dari warehouse default
        """
        PT = self.env["stock.picking.type"]
        # 1) company setting
        try:
            pt = getattr(company, "clinic_consumption_picking_type_id", False)
            if pt and pt.exists():
                return pt
        except Exception:
            pass
        # 2) by name
        pt = PT.search([("code", "=", "internal"), ("name", "ilike", "consumption")], limit=1)
        if pt:
            return pt
        # 3) default warehouse
        wh = self._resolve_default_warehouse(company)
        if wh:
            pt = PT.search([("warehouse_id", "=", wh.id), ("code", "=", "internal")], limit=1)
            if pt:
                return pt
        return None

    def _resolve_locations(self, booking, picking_type):
        """Tentukan lokasi sumber/destinasi:
        - dari picking_type default, bila ada
        - dari lokasi di booking (location_id) sebagai destinasi (consumption room) bila masuk akal
        """
        src = picking_type.default_location_src_id or self._warehouse_stock_location(self._resolve_default_warehouse(self._get_company(booking)))
        dest = picking_type.default_location_dest_id or src
        # Jika booking punya location_id (mis. lokasi tindakan), gunakan sebagai dest bila berbeda
        loc = self._get_any(booking, ["location_id"])
        if loc and loc.exists():
            dest = loc
        if not src or not dest:
            raise UserError(_("Cannot resolve source/destination locations for consumption."))
        return src, dest

    def _resolve_default_warehouse(self, company):
        WH = self.env.registry.get("stock.warehouse") and self.env["stock.warehouse"] or None
        if not WH:
            return None
        try:
            dw = getattr(company, "clinic_default_warehouse_id", False)
            if dw and dw.exists():
                return dw
        except Exception:
            pass
        # fallback: first warehouse of company
        wh = WH.search([("company_id", "=", company.id)], limit=1)
        return wh

    def _warehouse_stock_location(self, warehouse):
        if not warehouse:
            return None
        loc = getattr(warehouse, "lot_stock_id", False)
        return loc if loc and loc.exists() else None

    # ======================================================================
    # INTERNAL — COMMON HELPERS
    # ======================================================================
    def _has_stock(self):
        return bool(self.env.registry.get("stock.move") and self.env.registry.get("stock.picking"))

    def _has_mrp(self):
        return bool(self.env.registry.get("mrp.bom"))

    def _assert_single(self, rec, model_name):
        if not rec or rec._name != model_name:
            raise UserError(_("Invalid record model. Expected %s.") % model_name)
        if len(rec) != 1:
            raise UserError(_("You must call with a single record."))

    def _assert_record(self, rec):
        if not rec or not rec.exists():
            raise UserError(_("Record not found or already deleted."))

    def _service_product(self, rec):
        getp = getattr(rec, "get_service_product", None)
        try:
            prod = getp() if callable(getp) else None
            return prod if (prod and prod.exists()) else None
        except Exception:
            return None

    def _coerce_float(self, val):
        try:
            return float(val or 0.0)
        except Exception:
            return 0.0

    def _get_company(self, rec):
        if rec and "company_id" in rec._fields and rec.company_id:
            return rec.company_id
        return self.env.company

    def _get_partner(self, rec):
        for n in ("partner_id", "patient_id", "customer_id"):
            if rec and n in rec._fields and getattr(rec, n):
                return getattr(rec, n)
        return None

    def _get_any(self, rec, names):
        if not rec:
            return None
        for n in names:
            if n in rec._fields:
                try:
                    return getattr(rec, n)
                except Exception:
                    continue
        return None

    def _get_quantity(self, rec):
        if not rec:
            return 1.0
        for n in ("quantity", "qty", "units", "session_qty"):
            if n in rec._fields and getattr(rec, n) not in (None, False):
                try:
                    return float(getattr(rec, n))
                except Exception:
                    return 1.0
        return 1.0

    def _find_lines(self, booking, candidate_models):
        if not booking:
            return self.env[booking._name]
        for fname in booking._fields.keys():
            try:
                val = getattr(booking, fname)
                if hasattr(val, "_name") and val._name in candidate_models:
                    return val
            except Exception:
                continue
        return self.env[booking._name]

    def _resolve_target(self, record):
        if not record:
            return None, False
        for n in ("treatment_id", "service_id"):
            if n in record._fields and getattr(record, n):
                return getattr(record, n), False
        for n in ("bundle_id", "package_id"):
            if n in record._fields and getattr(record, n):
                return getattr(record, n), True
        # header
        if "treatment_id" in record._fields and record.treatment_id:
            return record.treatment_id, False
        if "bundle_id" in record._fields and record.bundle_id:
            return record.bundle_id, True
        return None, False

    def _display_booking(self, booking):
        if not booking:
            return "Booking"
        for n in ("name", "display_name", "reference"):
            if n in booking._fields and getattr(booking, n):
                return str(getattr(booking, n))
        return "Booking"

