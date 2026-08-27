# -*- coding: utf-8 -*-
# ClinicOne - Treatment Catalog & Pricing
# File: models/bridges/bridge_reports.py
#
# Reporting Bridge:
# - Mengagregasi data dari account.move.line (invoice lines), meta pricing, booking, insurance, inventory
# - Menghasilkan dataset, KPI, dan ringkasan untuk dashboard & laporan
# - Soft-coupled: semua akses model/field diperiksa aman
#
from odoo import api, models, fields, _
from odoo.exceptions import UserError
import logging
import json
import io
import base64
from collections import defaultdict

_logger = logging.getLogger(__name__)


class ClinicReportsBridge(models.AbstractModel):
    _name = "clinic.reports.bridge"
    _description = "ClinicOne Reports Bridge (pricing, billing, booking, inventory)"

    # =========================================================================
    # PUBLIC: DATASET INVOICE LINES + PRICING COMPONENTS
    # =========================================================================
    @api.model
    def get_invoice_lines_dataset(
        self,
        date_from=None,
        date_to=None,
        company_id=None,
        include_drafts=False,
        partner_id=None,
        treatment_or_bundle_only=True,
        with_components=True,
        with_meta=True,
    ):
        """
        Ambil dataset baris invoice dalam rentang tanggal, dilengkapi pricing components (bila tersedia).
        Return: list[dict]
        Tiap dict (kolom inti):
          - move_id, move_name, move_type, invoice_date, state, company_id
          - partner_id, partner_name
          - product_id, product_name
          - quantity, price_unit_company, subtotal_company_signed
          - is_refund (bool), is_insurance_line (bool, jika ada field x_is_insurance)
          - components: list komponen {kind,label,amount,priority,meta}
          - promo_discount, membership_discount, surcharge_amount, insurance_patient_adj, insurance_covered
          - meta: dict (jika ada x_price_meta atau dari line/booking)
          - dimensions ringan: treatment_id, bundle_id, category_id, tag_ids (bila ada di meta)
        """
        if not self._has_accounting():
            raise UserError(_("Accounting apps are required for invoice-based reports."))

        lines = self._fetch_invoice_lines(
            date_from=date_from, date_to=date_to, company_id=company_id,
            include_drafts=include_drafts, partner_id=partner_id
        )
        res = []
        for ln in lines:
            mv = ln.move_id
            company = mv.company_id
            currency_line = ln.currency_id or mv.currency_id or company.currency_id
            # amount (company currency) — gunakan balance * sign; untuk laporan penjualan, ambil subtotal
            subtotal_ccy = self._to_company_currency(ln.price_subtotal, currency_line, company, mv.invoice_date or mv.date or fields.Date.context_today(self))
            sign = -1.0 if mv.move_type in ("out_refund", "in_refund") else 1.0
            subtotal_ccy *= sign

            price_unit_ccy = self._to_company_currency(ln.price_unit, currency_line, company, mv.invoice_date or mv.date or fields.Date.context_today(self))

            comps = []  # components
            meta = {}

            if with_components or with_meta:
                comps, meta = self._extract_components_and_meta(ln)

            # hitung agregat per kind
            promo_disc = sum([-c["amount"] for c in comps if c.get("kind") == "promo" and float(c.get("amount", 0.0)) < 0.0])
            member_disc = sum([-c["amount"] for c in comps if c.get("kind") == "membership" and float(c.get("amount", 0.0)) < 0.0])
            surcharge_amt = sum([c["amount"] for c in comps if c.get("kind") == "surcharge" and float(c.get("amount", 0.0)) > 0.0])
            # Insurance:
            ins_covered = 0.0
            ins_patient_adj = 0.0
            for c in comps:
                if c.get("kind") == "insurance":
                    m = c.get("meta") or {}
                    covered = float(m.get("covered_amount", 0.0) or 0.0)
                    deductible = float(m.get("deductible_applied", 0.0) or 0.0)
                    copay = float(m.get("copay_amount", 0.0) or 0.0)
                    limit_shortfall = float(m.get("limit_shortfall", 0.0) or 0.0)
                    oop_adjust = float(m.get("oop_adjust", 0.0) or 0.0)
                    # Porsi pasien (positif) yang ditambahkan: deductible + copay + shortfall - relief OOP (oop_adjust negatif → kurangi porsi pasien)
                    ins_patient_adj += max(0.0, deductible) + max(0.0, copay) + max(0.0, limit_shortfall) + (oop_adjust if oop_adjust > 0 else 0.0)
                    ins_covered += max(0.0, covered)

            # is insurance invoice line?
            is_ins_line = False
            if "x_is_insurance" in ln._fields:
                is_ins_line = bool(getattr(ln, "x_is_insurance"))

            # filter baris product non-service? tergantung kebijakan
            if treatment_or_bundle_only:
                # heuristik: service product atau product dari treatment/bundle (tipe service)
                try:
                    if ln.product_id and ln.product_id.type not in ("service", "consu"):
                        # masih izinkan 'consu' karena beberapa klinik menggunakan consumable sebagai baris tagihan
                        pass
                except Exception:
                    pass

            rec = {
                "move_id": mv.id,
                "move_name": mv.name or mv.ref or "",
                "move_type": mv.move_type,
                "invoice_date": mv.invoice_date or mv.date,
                "state": mv.state,
                "company_id": company.id,
                "company_name": company.display_name,
                "partner_id": mv.partner_id.id if mv.partner_id else False,
                "partner_name": mv.partner_id.display_name if mv.partner_id else "",
                "product_id": ln.product_id.id if ln.product_id else False,
                "product_name": ln.product_id.display_name if ln.product_id else "",
                "quantity": float(ln.quantity or 0.0),
                "price_unit_company": float(price_unit_ccy),
                "subtotal_company_signed": float(subtotal_ccy),
                "is_refund": bool(mv.move_type in ("out_refund", "in_refund")),
                "is_insurance_line": bool(is_ins_line),
                "components": comps if with_components else [],
                "promo_discount": round(promo_disc, 2),
                "membership_discount": round(member_disc, 2),
                "surcharge_amount": round(surcharge_amt, 2),
                "insurance_covered": round(ins_covered, 2),
                "insurance_patient_adj": round(ins_patient_adj, 2),
                "meta": meta if with_meta else {},
            }

            # dimensi tambahan dari meta (jika ada)
            if meta:
                rec.update({
                    "treatment_id": meta.get("treatment_id") or (meta.get("meta") or {}).get("treatment_id"),
                    "bundle_id": meta.get("bundle_id") or (meta.get("meta") or {}).get("bundle_id"),
                    "plan_id": meta.get("plan_id") or (meta.get("meta") or {}).get("plan_id"),
                })
            res.append(rec)
        return res

    # =========================================================================
    # PUBLIC: KPI & RINGKASAN
    # =========================================================================
    @api.model
    def compute_kpis(self, date_from=None, date_to=None, company_id=None):
        """
        KPI utama penjualan klinik berdasarkan invoice (posted):
          - revenue_patient: total invoice pasien (tidak termasuk invoice insurer bila x_is_insurance tersedia)
          - revenue_insurer : total invoice insurer (deteksi via x_is_insurance atau meta)
          - promo_discount  : akumulasi diskon promo
          - membership_discount
          - surcharge_amount
          - insurance_covered (nilai yang dikover insurer yang tercermin pada komponen di harga pasien)
          - avg_ticket (rata-rata subtotal per invoice pasien)
        """
        ds = self.get_invoice_lines_dataset(date_from, date_to, company_id, include_drafts=False, with_components=True, with_meta=True)
        # group by move
        moves = defaultdict(lambda: {"amount": 0.0, "is_ins": False})
        total_promo = total_member = total_surcharge = total_ins_cov = 0.0
        for r in ds:
            moves[r["move_id"]]["amount"] += r["subtotal_company_signed"]
            is_ins = bool(r.get("is_insurance_line")) or self._guess_insurer_move(r)
            moves[r["move_id"]]["is_ins"] = moves[r["move_id"]]["is_ins"] or is_ins
            total_promo += r["promo_discount"]
            total_member += r["membership_discount"]
            total_surcharge += r["surcharge_amount"]
            total_ins_cov += r["insurance_covered"]

        revenue_patient = sum(v["amount"] for v in moves.values() if not v["is_ins"])
        revenue_insurer = sum(v["amount"] for v in moves.values() if v["is_ins"])
        patient_moves_count = sum(1 for v in moves.values() if not v["is_ins"])
        avg_ticket = (revenue_patient / patient_moves_count) if patient_moves_count else 0.0

        return {
            "revenue_patient": round(revenue_patient, 2),
            "revenue_insurer": round(revenue_insurer, 2),
            "promo_discount": round(total_promo, 2),
            "membership_discount": round(total_member, 2),
            "surcharge_amount": round(total_surcharge, 2),
            "insurance_covered": round(total_ins_cov, 2),
            "avg_ticket": round(avg_ticket, 2),
            "from": date_from,
            "to": date_to,
            "company_id": company_id,
        }

    @api.model
    def report_promotions_effectiveness(self, date_from=None, date_to=None, company_id=None, top_n=20):
        """
        Ringkasan efektivitas promo: total diskon per label/rule/campaign bila meta tersedia.
        Return: list[{key,label,discount,lines}]
        """
        ds = self.get_invoice_lines_dataset(date_from, date_to, company_id, with_components=True)
        agg = {}
        for r in ds:
            for c in r.get("components", []):
                if c.get("kind") != "promo":
                    continue
                key = str((c.get("meta", {}) or {}).get("rule_id") or c.get("label"))
                row = agg.setdefault(key, {"key": key, "label": c.get("label"), "discount": 0.0, "lines": 0})
                if float(c.get("amount", 0.0)) < 0.0:
                    row["discount"] += -float(c["amount"])
                row["lines"] += 1
        # sort desc by discount
        rows = sorted(agg.values(), key=lambda x: x["discount"], reverse=True)
        return rows[:top_n] if top_n else rows

    @api.model
    def report_membership_impact(self, date_from=None, date_to=None, company_id=None, group_by="tier"):
        """
        Dampak membership: total diskon per tier/plan (bergantung meta dari engine_membership).
        group_by: 'tier'|'rule'|'label'
        """
        ds = self.get_invoice_lines_dataset(date_from, date_to, company_id, with_components=True)
        agg = {}
        for r in ds:
            for c in r.get("components", []):
                if c.get("kind") != "membership":
                    continue
                meta = c.get("meta") or {}
                if group_by == "rule":
                    key = str(meta.get("rule_id") or c.get("label"))
                    label = c.get("label")
                elif group_by == "label":
                    key = c.get("label")
                    label = c.get("label")
                else:
                    key = str(meta.get("tier_id") or meta.get("membership_tier_id") or c.get("label"))
                    label = meta.get("tier_name") or c.get("label")
                row = agg.setdefault(key, {"key": key, "label": label, "discount": 0.0, "lines": 0})
                amt = float(c.get("amount", 0.0) or 0.0)
                if amt < 0.0:
                    row["discount"] += -amt
                row["lines"] += 1
        return sorted(agg.values(), key=lambda x: x["discount"], reverse=True)

    # @api.model
    # def report_insurance_coverage(self, date_from=None, date_to=None, company_id=None, group_by="plan"):
    #     """
    #     Ringkas coverage insurer (dari komponen harga).
    #     group_by: 'plan'|'payer'|'label'
    #     """
    #     ds = self.get_invoice_lines_dataset(date_from, date_to, company_id, with_components=True)
    #     agg = {}
    #     for r in ds:
    #         for c in r.get("components", []):
    #             if c.get("kind") != "insurance":
    #                 continue
    #             m = c.get("meta") or {}
    #             if group_by == "payer":
    #                 payer_id = self._payer_from_plan(m.get("plan_id"))
    #                 key = f"payer:{payer_id or 'none'}"
    #                 label = self._partner_name_safe(payer_id) if payer_id else _("(No Payer)")
    #             elif group_by == "label":
    #                 key = c.get("label")
    #                 label = c.get("label")
    #             else:
    #                 key = f"plan:{m.get('plan_id') or 'none'}"
    #                 label = self._plan_name_safe(m.get("plan_id")) if m.get("plan_id") else _("(No Plan)")
    #             row = agg.setdefault(key, {"key": key, "label": label, "covered": 0.0, "patient_adj": 0.0, "lines": 0})
    #             row["covered"] += max(0.0, float(m.get("covered_amount") or 0.0))
    #             row["patient_adj"] += max(0.0, float(m.get("deductible_applied") or 0.0)) + max(0.0, float(m.get("copay_amount") or 0.0)) + max(0.0, float(m.get("limit_shortfall") or 0.0)) + max(0.0, float(m.get("oop_adjust") or 0.0))
    #             row["lines"] += 1
    #     return sorted(agg.values(), key=lambda x: x["covered"], reverse=True)

    @api.model
    def report_surcharge_impact(self, date_from=None, date_to=None, company_id=None, group_by="dimension"):
        """
        Dampak surcharge: total surcharge per dimensi (therapist/room/equipment/time) bila meta terisi.
        group_by: 'dimension'|'label'|'rule'
        """
        ds = self.get_invoice_lines_dataset(date_from, date_to, company_id, with_components=True)
        agg = {}
        for r in ds:
            for c in r.get("components", []):
                if c.get("kind") != "surcharge":
                    continue
                meta = c.get("meta") or {}
                if group_by == "rule":
                    key = str(meta.get("rule_id") or c.get("label"))
                    label = c.get("label")
                elif group_by == "label":
                    key = c.get("label")
                    label = c.get("label")
                else:
                    key = meta.get("group_key") or self._infer_surcharge_dimension(meta)
                    label = key
                row = agg.setdefault(key, {"key": key, "label": label, "surcharge": 0.0, "lines": 0})
                row["surcharge"] += max(0.0, float(c.get("amount", 0.0) or 0.0))
                row["lines"] += 1
        return sorted(agg.values(), key=lambda x: x["surcharge"], reverse=True)

    # @api.model
    # def report_booking_conversion(self, date_from=None, date_to=None, company_id=None):
    #     """
    #     Konversi booking → billing:
    #     - bookings_created: jumlah booking dibuat
    #     - bookings_billed : booking yang memiliki invoice (invoice_origin berisi nama booking)
    #     - conversion_rate : billed / created
    #     """
    #     # Booking models (soft)
    #     Booking = self._get_any_model(["booking.booking", "clinic.appointment", "clinic.visit"])
    #     if not Booking:
    #         return {"bookings_created": 0, "bookings_billed": 0, "conversion_rate": 0.0}

    #     domain = []
    #     if company_id:
    #         domain.append(("company_id", "=", company_id))
    #     if date_from:
    #         domain.append(("create_date", ">=", fields.Datetime.to_datetime(date_from)))
    #     if date_to:
    #         domain.append(("create_date", "<=", fields.Datetime.to_datetime(date_to)))

    #     created = Booking.search_count(domain)

    #     billed = 0
    #     if self._has_accounting():
    #         Move = self.env["account.move"]
    #         dom_mv = [("move_type", "in", ("out_invoice", "out_refund")), ("state", "=", "posted")]
    #         if company_id:
    #             dom_mv.append(("company_id", "=", company_id))
    #         if date_from:
    #             dom_mv.append(("invoice_date", ">=", date_from))
    #         if date_to:
    #             dom_mv.append(("invoice_date", "<=", date_to))
    #         mv = Move.search(dom_mv)
    #         names = set(Booking.search(domain).mapped("name"))
    #         billed = sum(1 for m in mv if m.invoice_origin and m.invoice_origin in names)

    #     rate = (billed / created) if created else 0.0
    #     return {"bookings_created": created, "bookings_billed": billed, "conversion_rate": round(rate, 4)}

    @api.model
    def report_inventory_consumption(self, date_from=None, date_to=None, company_id=None, top_n=30):
        """
        Rekap konsumsi inventory (berdasarkan stock.picking konsumsi; soft-coupled).
        Return: list[{product_id, product_name, qty_done, uom_name}]
        """
        if not self._has_stock():
            return []

        Pick = self.env["stock.picking"]
        domain = [("state", "=", "done")]
        if company_id:
            domain.append(("company_id", "=", company_id))
        if date_from:
            domain.append(("date_done", ">=", fields.Datetime.to_datetime(date_from)))
        if date_to:
            domain.append(("date_done", "<=", fields.Datetime.to_datetime(date_to)))

        picks = Pick.search(domain)
        agg = {}
        for p in picks:
            for mv in p.move_ids:
                for ml in mv.move_line_ids:
                    prod = ml.product_id
                    key = prod.id
                    row = agg.setdefault(key, {"product_id": prod.id, "product_name": prod.display_name, "qty_done": 0.0, "uom_name": (ml.product_uom_id and ml.product_uom_id.display_name) or prod.uom_id.display_name})
                    row["qty_done"] += float(ml.qty_done or 0.0)

        rows = sorted(agg.values(), key=lambda x: x["qty_done"], reverse=True)
        return rows[:top_n] if top_n else rows

    # =========================================================================
    # PUBLIC: EXPORT KE FILE (XLSX/CSV)
    # =========================================================================
    @api.model
    def export_rows(self, rows, columns, filename="report.xlsx"):
        """
        Ekspor rows (list[dict]) dengan urutan kolom 'columns' (list[str]).
        Prioritas XLSX (xlsxwriter), fallback CSV bila xlsxwriter tidak tersedia.
        Return: dict {'filename': str, 'file': base64, 'mimetype': str}
        """
        # coba xlsxwriter
        try:
            import xlsxwriter  # noqa: F401
            return self._export_xlsx(rows, columns, filename=filename)
        except Exception:
            return self._export_csv(rows, columns, filename=filename.replace(".xlsx", ".csv"))

    # =========================================================================
    # INTERNAL: FETCH & EXTRACT
    # =========================================================================
    def _fetch_invoice_lines(self, date_from, date_to, company_id, include_drafts, partner_id):
        AML = self.env["account.move.line"]
        domain = [("move_id.move_type", "in", ("out_invoice", "out_refund"))]
        if not include_drafts:
            domain.append(("move_id.state", "=", "posted"))
        if company_id:
            domain.append(("move_id.company_id", "=", company_id))
        if partner_id:
            domain.append(("move_id.partner_id", "=", partner_id))
        if date_from:
            domain.append(("move_id.invoice_date", ">=", date_from))
        if date_to:
            domain.append(("move_id.invoice_date", "<=", date_to))
        # exclude section/note lines
        if "display_type" in AML._fields:
            domain.append(("display_type", "=", False))
        lines = AML.search(domain)
        return lines

    def _extract_components_and_meta(self, aml):
        """
        Ambil komponen pricing & meta dari beberapa kemungkinan lokasi field:
        - account.move.line: x_price_components (json), x_price_meta (json)
        - booking line (soft): price_components_json / components_json / pricing_components
        - fallback: kosong
        """
        comps = []
        meta = {}

        # 1) Langsung dari account.move.line (custom fields)
        if "x_price_components" in aml._fields:
            try:
                comps = json.loads(aml.x_price_components or "[]")
            except Exception:
                comps = []
        if "x_price_meta" in aml._fields:
            try:
                meta = json.loads(aml.x_price_meta or "{}")
            except Exception:
                meta = {}

        if comps or meta:
            normalized = [self._normalize_component(x) for x in (comps or [])]
            return normalized, meta or {}

        # 2) Coba dari booking line yang terkait (soft): cari origin (move.invoice_origin) dan cocokan line_id
        booking = None
        try:
            mv = aml.move_id
            if mv and mv.invoice_origin:
                booking = self._find_booking_by_name(mv.invoice_origin)
        except Exception:
            booking = None

        if booking:
            line = self._guess_booking_line_from_aml(booking, aml)
            if line:
                field_candidates = ("price_components_json", "components_json", "pricing_components")
                for fname in field_candidates:
                    if fname in line._fields and getattr(line, fname):
                        try:
                            comps = json.loads(getattr(line, fname) or "[]")
                        except Exception:
                            comps = []
                        break

        normalized = [self._normalize_component(x) for x in (comps or [])]
        return normalized, meta or {}

    def _normalize_component(self, comp):
        """Pastikan struktur komponen konsisten."""
        try:
            label = comp.get("label") or _("Component")
            amount = float(comp.get("amount", 0.0) or 0.0)
            kind = comp.get("kind") or "misc"
            priority = int(comp.get("priority", 600))
            meta = comp.get("meta") or {}
            return {"label": label, "amount": amount, "kind": kind, "priority": priority, "meta": meta}
        except Exception:
            return {"label": _("Component"), "amount": 0.0, "kind": "misc", "priority": 600, "meta": {}}

    # =========================================================================
    # INTERNAL: UTILS (DIMENSIONS, NAME, LOOKUPS)
    # =========================================================================
    def _to_company_currency(self, amount, currency, company, at_date):
        if not currency or currency.id == company.currency_id.id:
            return float(amount or 0.0)
        return currency._convert(amount or 0.0, company.currency_id, company, at_date or fields.Date.context_today(self))

    def _guess_insurer_move(self, row):
        """Heuristik jika x_is_insurance tidak tersedia."""
        # Jika partner tampak sebagai perusahaan asuransi (memiliki tag 'Insurer' misalnya),
        # atau meta komponen insurance memiliki plan_id → kemungkinan invoice insurer.
        if row.get("is_insurance_line"):
            return True
        meta = row.get("meta") or {}
        if meta.get("plan_id"):
            # baris pasien pun bisa mengandung plan_id di meta; ini tidak berarti invoice insurer
            # jadi heuristik ini hanya pelengkap; tetap false
            return False
        # fallback: periksa nama partner mengandung frasa umum
        name = (row.get("partner_name") or "").lower()
        return any(k in name for k in ["insurance", "insurer", "bpjs", "payer", "asuransi"])

    def _payer_from_plan(self, plan_id):
        Plan = self.env.registry.get("clinic.insurance.plan") and self.env["clinic.insurance.plan"] or None
        if not (Plan and plan_id):
            return None
        try:
            plan = Plan.browse(plan_id)
            if plan and plan.exists() and "payer_id" in plan._fields and plan.payer_id:
                return plan.payer_id.id
        except Exception:
            return None
        return None

    def _partner_name_safe(self, partner_id):
        if not partner_id:
            return ""
        P = self.env["res.partner"].browse(partner_id)
        return P.display_name if P and P.exists() else ""

    def _plan_name_safe(self, plan_id):
        Plan = self.env.registry.get("clinic.insurance.plan") and self.env["clinic.insurance.plan"] or None
        if not (Plan and plan_id):
            return ""
        p = Plan.browse(plan_id)
        return p.display_name if p and p.exists() else ""

    def _infer_surcharge_dimension(self, meta):
        for k in ("therapist", "room", "equipment", "time", "holiday", "location"):
            # meta.group_key sudah diisi engine_surcharge; ini fallback
            if meta.get(f"context.{k}") or meta.get(k):
                return k
        return "dimension"

    def _find_booking_by_name(self, name):
        for m in ("booking.booking", "clinic.appointment", "clinic.visit"):
            if self.env.registry.get(m):
                rec = self.env[m].search([("name", "=", name)], limit=1)
                if rec:
                    return rec
        return None

    def _guess_booking_line_from_aml(self, booking, aml):
        """Heuristik untuk mencari line booking yang terkait dengan baris invoice."""
        # Cari line dengan product yang sama & qty mendekati
        candidates_models = ["clinic.booking.line", "clinic.appointment.line", "clinic.visit.line"]
        for fname in booking._fields.keys():
            try:
                val = getattr(booking, fname)
                if hasattr(val, "_name") and val._name in candidates_models:
                    for ln in val:
                        prod = getattr(ln, "product_id", None) or getattr(ln, "service_product_id", None)
                        if prod and aml.product_id and prod.id == aml.product_id.id:
                            return ln
            except Exception:
                continue
        return None

    # =========================================================================
    # INTERNAL: EXPORT HELPERS
    # =========================================================================
    def _export_xlsx(self, rows, columns, filename="report.xlsx"):
        import xlsxwriter  # ensured by caller
        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {"in_memory": True})
        ws = wb.add_worksheet("Report")
        fmt_header = wb.add_format({"bold": True})
        # header
        for c, col in enumerate(columns):
            ws.write(0, c, col, fmt_header)
        # rows
        for r, row in enumerate(rows, start=1):
            for c, col in enumerate(columns):
                ws.write(r, c, self._cell_value(row.get(col)))
        wb.close()
        data = output.getvalue()
        return {"filename": filename, "file": base64.b64encode(data), "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}

    def _export_csv(self, rows, columns, filename="report.csv"):
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([self._cell_value(row.get(col)) for col in columns])
        data = output.getvalue().encode("utf-8")
        return {"filename": filename, "file": base64.b64encode(data), "mimetype": "text/csv"}

    def _cell_value(self, v):
        if isinstance(v, (dict, list)):
            try:
                return json.dumps(v, ensure_ascii=False)
            except Exception:
                return str(v)
        if isinstance(v, (fields.Date, fields.Datetime)):
            return str(v)
        return v

    # =========================================================================
    # INTERNAL: ENV SAFETY
    # =========================================================================
    def _has_accounting(self):
        return bool(self.env.registry.get("account.move") and self.env.registry.get("account.move.line"))

    def _has_stock(self):
        return bool(self.env.registry.get("stock.picking") and self.env.registry.get("stock.move"))

    def _get_any_model(self, names):
        for n in names:
            if self.env.registry.get(n):
                return self.env[n]
        return None

