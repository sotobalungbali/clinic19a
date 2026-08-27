# -*- coding: utf-8 -*-
# ClinicOne - Treatment Catalog & Pricing
# File: models/bridges/bridge_billing.py
#
# Billing Bridge:
# - Orkestrasi dari booking/line → pricing → invoice/claim
# - Soft-coupled: aman walau accounting, insurance, analytic belum ada
#
from odoo import api, models, fields, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ClinicBillingBridge(models.AbstractModel):
    _name = "clinic.billing.bridge"
    _description = "ClinicOne Billing Bridge (pricing → invoices/claims)"

    # ======================================================================
    # PUBLIC API — BOOKING → BILLING
    # ======================================================================
    @api.model
    def compute_billing_payload_from_booking(
        self,
        booking,
        pricelist_id=None,
        create_insurance_claim=True,
        group_insurer_by_plan=True,
        write_snapshot=False,
        debug=False,
    ):
        """
        Siapkan payload billing dari sebuah booking/appointment:
        - Hitung harga tiap baris (via clinic.booking.bridge + clinic.pricelist.bridge)
        - Pecah porsi pasien vs insurer (jika ada coverage)
        - Kembalikan struktur payload untuk pembuatan invoice/claim

        return dict:
        {
          'company_id': int,
          'currency_id': int,
          'patient_partner_id': int | None,
          'patient_lines': [inv_line_vals, ...],
          'insurer_lines_by_partner': {
              insurer_partner_key: {
                  'partner_id': int,
                  'lines': [inv_line_vals, ...],
                  'plan_ids': [ids],
              },
              ...
          },
          'meta': {...}
        }
        """
        self._assert_record(booking)
        company = self._get_company(booking)
        patient_partner = self._get_partner(booking)
        currency = company.currency_id if company else self.env.company.currency_id

        # 1) Ambil hasil pricing dari booking
        book_bridge = self.env["clinic.booking.bridge"]
        priced = book_bridge.compute_prices_for_booking(
            booking=booking,
            pricelist_id=pricelist_id,
            write_snapshot=write_snapshot,
            debug=debug,
        )
        if not priced:
            raise UserError(_("No billable lines detected for this booking."))

        # 2) Ubah hasil pricing menjadi draft invoice lines (pasien) & (opsional) insurer
        patient_lines = []
        insurer_lines_by_partner = {}

        for item in priced:
            result = (item or {}).get("result") or {}
            if not result:
                continue

            # Target & kuantitas & waktu dari line (atau header booking)
            line_rec = self._find_line_by_id(booking, item.get("line_id"))
            target, is_bundle = self._resolve_target(line_rec or booking)
            qty = self._get_quantity(line_rec or booking, default=1.0)
            at_dt = self._get_datetime(line_rec, booking)

            # Produk jasa (service product)
            product = self._service_product(target) or self._company_fallback_product(company)
            if not product:
                raise UserError(_("No service product defined for billing. Configure a default service product in Settings."))

            # Baris pasien
            pline = self._prepare_move_line_vals_from_pricing(
                product=product,
                name=self._display_name_for_line(target, is_bundle, line_rec),
                qty=qty,
                unit_price=result.get("price", 0.0),
                currency=currency,
                partner=self._get_partner(booking),
                company=company,
                pricing_result=result,
                context_record=line_rec or booking,
                when=at_dt,
            )
            patient_lines.append(pline)

            # Baris insurer (opsional)
            if create_insurance_claim:
                ins = self._extract_insurance_allocation(result)
                if ins and ins.get("amount", 0.0) > 0:
                    insurer_partner = self._resolve_insurer_partner(ins.get("plan_id"))
                    if not insurer_partner:
                        continue
                    iline = self._prepare_move_line_vals_from_pricing(
                        product=product,
                        name=self._display_name_for_line(target, is_bundle, line_rec, insurance=True, label=ins.get("label")),
                        qty=qty,
                        unit_price=ins["amount"],
                        currency=currency,
                        partner=insurer_partner,
                        company=company,
                        pricing_result=result,
                        context_record=line_rec or booking,
                        when=at_dt,
                        is_insurance=True,
                        plan_id=ins.get("plan_id"),
                        member_id=ins.get("member_id"),
                    )
                    key = insurer_partner.id if group_insurer_by_plan else f"{insurer_partner.id}-{ins.get('plan_id') or '0'}"
                    insurer_lines_by_partner.setdefault(key, {"partner": insurer_partner, "lines": [], "plan_ids": set()})
                    insurer_lines_by_partner[key]["lines"].append(iline)
                    if ins.get("plan_id"):
                        insurer_lines_by_partner[key]["plan_ids"].add(ins.get("plan_id"))

        payload = {
            "company_id": company.id if company else False,
            "currency_id": currency.id if currency else False,
            "patient_partner_id": patient_partner.id if patient_partner else False,
            "patient_lines": patient_lines,
            "insurer_lines_by_partner": {
                k: {"partner_id": v["partner"].id, "lines": v["lines"], "plan_ids": list(v["plan_ids"])}
                for k, v in insurer_lines_by_partner.items()
            },
            "meta": {
                "booking_id": booking.id,
                "priced_count": len(priced),
                "has_insurance": bool(insurer_lines_by_partner),
            },
        }
        return payload

    @api.model
    def create_invoices_from_booking(
        self,
        booking,
        journal_id=None,
        pricelist_id=None,
        auto_post=False,
        create_insurance_claim=True,
        group_insurer_by_plan=True,
        debug=False,
    ):
        """
        Buat dokumen invoice dari booking:
        - 1 out_invoice untuk pasien (partner booking),
        - N out_invoice untuk insurer (1 per insurer_partner atau per plan).
        """
        if not self._has_accounting():
            raise UserError(_("Accounting app is not installed/available."))

        payload = self.compute_billing_payload_from_booking(
            booking=booking,
            pricelist_id=pricelist_id,
            create_insurance_claim=create_insurance_claim,
            group_insurer_by_plan=group_insurer_by_plan,
            write_snapshot=True,
            debug=debug,
        )

        created_moves = []
        company = self.env["res.company"].browse(payload["company_id"]) if payload.get("company_id") else self.env.company

        # 1) Invoice pasien
        if payload.get("patient_lines"):
            mv = self._create_move_with_lines(
                move_type="out_invoice",
                partner_id=payload.get("patient_partner_id"),
                company=company,
                journal_id=journal_id,
                lines=payload["patient_lines"],
                auto_post=auto_post,
                origin=self._booking_name(booking),
                narration=_("Invoice generated from booking %s") % self._booking_name(booking),
            )
            created_moves.append(mv.id)

        # 2) Invoice insurer (jika ada)
        for key, group in (payload.get("insurer_lines_by_partner") or {}).items():
            ilines = group.get("lines") or []
            if not ilines:
                continue
            insurer_partner_id = group.get("partner_id")
            plan_ids = group.get("plan_ids") or []
            narration = _("Insurance claim for booking %s") % self._booking_name(booking)
            if plan_ids and self.env.registry.get("clinic.insurance.plan"):
                try:
                    plans = self.env["clinic.insurance.plan"].browse(plan_ids)
                    pname = ", ".join(plans.mapped("name"))
                    narration = _("%s — Plans: %s") % (narration, pname)
                except Exception:
                    pass
            mv = self._create_move_with_lines(
                move_type="out_invoice",
                partner_id=insurer_partner_id,
                company=company,
                journal_id=journal_id,
                lines=ilines,
                auto_post=auto_post,
                origin=self._booking_name(booking),
                narration=narration,
            )
            created_moves.append(mv.id)

        return self.env["account.move"].browse(created_moves) if created_moves else self.env["account.move"]

    # ======================================================================
    # PUBLIC API — GENERIC ITEMS → BILLING
    # ======================================================================
    @api.model
    def create_invoice_from_items(
        self,
        items,
        partner_id,
        company_id=None,
        journal_id=None,
        currency_id=None,
        auto_post=False,
        origin=None,
        narration=None,
    ):
        """
        Buat invoice dari list items generik (tanpa booking):
        items: [{
            'treatment_id' or 'bundle_id': int,
            'quantity': float,
            'date': datetime | None,
            'pricelist_id': int | None,
            'context_tags': [str,...] | None,
            'is_insurance': bool (optional),
            'plan_id': int (optional, insurance),
            'member_id': int (optional, insurance),
        }, ...]
        """
        if not self._has_accounting():
            raise UserError(_("Accounting app is not installed/available."))

        partner = self.env["res.partner"].browse(partner_id)
        if not partner or not partner.exists():
            raise UserError(_("Valid partner is required."))

        company = self.env["res.company"].browse(company_id) if company_id else self.env.company
        currency = self.env["res.currency"].browse(currency_id) if currency_id else (company.currency_id or self.env.company.currency_id)

        lines = []
        for it in items or []:
            target, is_bundle = self._resolve_target_from_ids(it)
            if not target:
                _logger.debug("Skip item without target: %s", it)
                continue
            qty = float(it.get("quantity") or 1.0)
            at_dt = it.get("date") or fields.Datetime.now()
            # Harga via bridge
            bridge = self.env["clinic.pricelist.bridge"]
            res = (bridge.compute_bundle_price(bundle=target, partner_id=partner_id, pricelist_id=it.get("pricelist_id"),
                                               quantity=qty, sale_dt=at_dt, context_tags=(it.get("context_tags") or []), company_id=company.id)
                   if is_bundle else
                   bridge.compute_treatment_price(treatment=target, partner_id=partner_id, pricelist_id=it.get("pricelist_id"),
                                                  quantity=qty, booking_dt=at_dt, context_tags=(it.get("context_tags") or []), company_id=company.id))
            product = self._service_product(target) or self._company_fallback_product(company)
            if not product:
                raise UserError(_("No service product defined for billing. Configure a default service product in Settings."))

            ln = self._prepare_move_line_vals_from_pricing(
                product=product,
                name=self._display_name_for_line(target, is_bundle, None, insurance=bool(it.get("is_insurance"))),
                qty=qty,
                unit_price=res.get("price", 0.0),
                currency=currency,
                partner=partner,
                company=company,
                pricing_result=res,
                context_record=None,
                when=at_dt,
                is_insurance=bool(it.get("is_insurance")),
                plan_id=it.get("plan_id"),
                member_id=it.get("member_id"),
            )
            lines.append(ln)

        mv = self._create_move_with_lines(
            move_type="out_invoice",
            partner_id=partner_id,
            company=company,
            journal_id=journal_id,
            lines=lines,
            auto_post=auto_post,
            origin=origin,
            narration=narration,
        )
        return mv

    # ======================================================================
    # CORE HELPERS — MOVE/LINE CREATION
    # ======================================================================
    def _prepare_move_line_vals_from_pricing(
        self, product, name, qty, unit_price, currency, partner, company,
        pricing_result, context_record, when, is_insurance=False, plan_id=None, member_id=None
    ):
        """Bangun dict vals untuk account.move.line dari hasil pricing."""
        # Map taxes via fiscal position
        taxes = self._map_taxes(product, partner, company)
        price_unit_company_cur = self._convert_to_company_currency(unit_price, currency, company, when)

        vals = {
            "product_id": product.id,
            "name": name or product.display_name,
            "quantity": qty,
            "price_unit": price_unit_company_cur,
            "tax_ids": [(6, 0, taxes.ids if taxes else [])],
        }

        # Optional fields (soft)
        aml_model = self.env["account.move.line"]
        if "currency_id" in aml_model._fields:
            vals["currency_id"] = company.currency_id.id

        # Capture pricing details for audit (jika custom fields tersedia)
        comps = pricing_result.get("components", [])
        breakdown = pricing_result.get("breakdown_text") or ""
        explanation = pricing_result.get("explanation") or ""
        meta = pricing_result.get("meta") or {}

        # Tuliskan breakdown/explanation ke context_record jika fieldnya ada
        for fname in ("price_breakdown", "price_note", "price_explanation"):
            if context_record and fname in getattr(context_record, "_fields", {}):
                try:
                    if fname == "price_explanation":
                        context_record.sudo().write({fname: explanation})
                    else:
                        context_record.sudo().write({fname: breakdown})
                except Exception:
                    pass

        # Jika account.move.line punya field kustom JSON, tulis
        if "x_price_components" in aml_model._fields:
            vals["x_price_components"] = self._json_dumps_safe(comps)
        if "x_price_meta" in aml_model._fields:
            vals["x_price_meta"] = self._json_dumps_safe(meta)

        # Tagging insurance (jika ada field custom)
        if is_insurance:
            if "x_is_insurance" in aml_model._fields:
                vals["x_is_insurance"] = True
            if plan_id and "x_insurance_plan_id" in aml_model._fields:
                vals["x_insurance_plan_id"] = plan_id
            if member_id and "x_insurance_member_id" in aml_model._fields:
                vals["x_insurance_member_id"] = member_id

        # Analytic account (opsional; hanya tulis jika field ada)
        a_account = self._analytic_account_default(context_record, partner, company, product)
        if a_account and "analytic_account_id" in aml_model._fields:
            vals["analytic_account_id"] = a_account.id

        return vals

    def _create_move_with_lines(
        self, move_type, partner_id, company, journal_id, lines, auto_post, origin=None, narration=None
    ):
        """Buat account.move + lines (Accounting harus tersedia)."""
        Move = self.env["account.move"]
        if not Move:
            raise UserError(_("Accounting models not available."))

        journal = self._resolve_journal(journal_id, company, move_type)

        mv_vals = {
            "move_type": move_type,
            "partner_id": partner_id,
            "company_id": company.id if company else self.env.company.id,
            "journal_id": journal.id if journal else False,
            "invoice_origin": origin or "",
            "invoice_line_ids": [(0, 0, ln) for ln in (lines or [])],
            "narration": narration or "",
        }
        mv = Move.create(mv_vals)
        if auto_post:
            mv.action_post()
        return mv

    # ======================================================================
    # INSURANCE ALLOCATION
    # ======================================================================
    def _extract_insurance_allocation(self, pricing_result):
        """
        Ambil komponen insurance dari pricing_result.components dan hitung jumlah
        yang seharusnya ditagihkan ke insurer (klaim).
        Logika:
          insurer_amount = covered_amount + max(0, -oop_adjust)
          (deductible/copay/limit_shortfall tetap jadi porsi pasien)
        """
        for comp in pricing_result.get("components", []):
            if comp.get("kind") != "insurance":
                continue
            meta = comp.get("meta") or {}
            covered = float(meta.get("covered_amount", 0.0) or 0.0)
            oop_adjust = float(meta.get("oop_adjust", 0.0) or 0.0)
            insurer_amount = covered + (abs(oop_adjust) if oop_adjust < 0 else 0.0)
            return {
                "amount": max(0.0, insurer_amount),
                "plan_id": meta.get("plan_id"),
                "member_id": meta.get("member_id"),
                "label": _("Insurance Coverage"),
            }
        return None

    def _resolve_insurer_partner(self, plan_id):
        """Kembalikan partner insurer dari plan (jika tersedia)."""
        if not plan_id:
            return None
        Plan = self.env.registry.get("clinic.insurance.plan") and self.env["clinic.insurance.plan"] or None
        if not Plan:
            return None
        plan = Plan.browse(plan_id)
        if not plan or not plan.exists():
            return None
        payer = getattr(plan, "payer_id", False)
        return payer if payer and payer.exists() else None

    # ======================================================================
    # TAX / FISCAL POSITION / CURRENCY / ANALYTIC
    # ======================================================================
    def _map_taxes(self, product, partner, company):
        """Ambil pajak dari product → mapping via fiscal position partner."""
        taxes = product.taxes_id.filtered(lambda t: not company or t.company_id.id == company.id)
        fpos = None
        try:
            fpos = partner.property_account_position_id if partner and hasattr(partner, "property_account_position_id") else None
        except Exception:
            fpos = None
        if fpos:
            taxes = fpos.map_tax(taxes, product=product, partner=partner)
        return taxes

    def _convert_to_company_currency(self, amount, currency, company, date):
        if not currency or not company or currency.id == company.currency_id.id:
            return float(amount or 0.0)
        return currency._convert(amount or 0.0, company.currency_id, company, date or fields.Date.context_today(self))

    def _analytic_account_default(self, record, partner, company, product):
        """
        Kembalikan analytic account default dari sumber-sumber yang mungkin menyediakannya.
        Tidak ada interaksi dengan model apa pun secara eksplisit; hanya membaca field bila ada.
        """
        # urutan prioritas
        for rec, names in (
            (record, ("analytic_account_id",)),
            (partner, ("analytic_account_id",)),
            (product, ("analytic_account_id",)),
            (company, ("clinic_default_analytic_account_id",)),  # field custom opsional
        ):
            if not rec:
                continue
            for n in names:
                if n in getattr(rec, "_fields", {}):
                    val = getattr(rec, n)
                    if val and val.exists():
                        return val
        return None

    def _resolve_journal(self, journal_id, company, move_type):
        Journal = self.env["account.journal"]
        if journal_id:
            jr = Journal.browse(journal_id)
            if jr and jr.exists():
                return jr
        # fallback: journal default by type
        jtype = "sale" if move_type in ("out_invoice", "out_refund") else "purchase"
        jr = Journal.search([("company_id", "=", company.id), ("type", "=", jtype)], limit=1)
        return jr

    # ======================================================================
    # BOOKING CONTEXT HELPERS
    # ======================================================================
    def _get_company(self, booking):
        if not booking:
            return self.env.company
        if "company_id" in booking._fields and booking.company_id:
            return booking.company_id
        return self.env.company

    def _get_partner(self, booking):
        for name in ("partner_id", "patient_id", "customer_id"):
            if name in booking._fields and getattr(booking, name):
                return getattr(booking, name)
        return None

    def _booking_name(self, booking):
        if not booking:
            return ""
        for n in ("name", "display_name"):
            if n in booking._fields and getattr(booking, n):
                return str(getattr(booking, n))
        return "Booking"

    def _find_line_by_id(self, booking, line_id):
        if not booking or not line_id:
            return None
        # cari di semua One2many pada booking
        for fname, field in booking._fields.items():
            try:
                val = getattr(booking, fname)
                if hasattr(val, "_name") and hasattr(val, "ids") and line_id in val.ids:
                    return val.browse(line_id)
            except Exception:
                continue
        return None

    def _resolve_target(self, record):
        """Kembalikan (target_record, is_bundle)."""
        if not record:
            return None, False
        for n in ("treatment_id", "service_id"):
            if n in record._fields and getattr(record, n):
                return getattr(record, n), False
        for n in ("bundle_id", "package_id"):
            if n in record._fields and getattr(record, n):
                return getattr(record, n), True
        # booking header single target
        if "treatment_id" in record._fields and record.treatment_id:
            return record.treatment_id, False
        if "bundle_id" in record._fields and record.bundle_id:
            return record.bundle_id, True
        return None, False

    def _resolve_target_from_ids(self, item):
        """Untuk API generic: terima id (treatment_id/bundle_id)."""
        Treatment = self.env.registry.get("clinic.treatment.catalog") and self.env["clinic.treatment.catalog"] or None
        Bundle = self.env.registry.get("clinic.treatment.bundle") and self.env["clinic.treatment.bundle"] or None
        if item.get("treatment_id") and Treatment:
            rec = Treatment.browse(item["treatment_id"])
            return (rec if rec and rec.exists() else None), False
        if item.get("bundle_id") and Bundle:
            rec = Bundle.browse(item["bundle_id"])
            return (rec if rec and rec.exists() else None), True
        return None, False

    def _get_quantity(self, record, default=1.0):
        if not record:
            return default
        for n in ("quantity", "qty", "units", "session_qty"):
            if n in record._fields and getattr(record, n) not in (None, False):
                try:
                    return float(getattr(record, n))
                except Exception:
                    return default
        return default

    def _get_datetime(self, line, booking):
        for fname in ("start_datetime", "datetime_start", "scheduled_start", "appointment_datetime"):
            val = self._get_any(line, [fname])
            if val:
                return fields.Datetime.to_datetime(val)
        for fname in ("start_datetime", "datetime_start", "scheduled_start", "appointment_datetime", "booking_datetime"):
            val = self._get_any(booking, [fname])
            if val:
                return fields.Datetime.to_datetime(val)
        return fields.Datetime.now()

    def _get_any(self, rec, names):
        if not rec:
            return None
        try:
            for n in names:
                if n in rec._fields:
                    return getattr(rec, n)
        except Exception:
            return None
        return None

    def _display_name_for_line(self, target, is_bundle, line, insurance=False, label=None):
        base = target.display_name if target else _("Service")
        if is_bundle:
            base = _("Bundle: %s") % base
        if insurance:
            return _("%s — %s") % (base, label or _("Insurance"))
        return base

    def _service_product(self, rec):
        getp = getattr(rec, "get_service_product", None)
        try:
            prod = getp() if callable(getp) else None
            return prod if (prod and prod.exists()) else None
        except Exception:
            return None

    def _company_fallback_product(self, company):
        """Ambil product layanan default dari Settings (opsional)."""
        if not company:
            company = self.env.company
        try:
            prod = getattr(company, "clinic_default_service_product_id", False)
            return prod if prod and prod.exists() else None
        except Exception:
            return None

    def _json_dumps_safe(self, obj):
        try:
            import json
            return json.dumps(obj, ensure_ascii=False)
        except Exception:
            return str(obj)

    # ======================================================================
    # ENV / SAFETY
    # ======================================================================
    def _has_accounting(self):
        return bool(self.env.registry.get("account.move") and self.env.registry.get("account.move.line"))

    def _assert_record(self, rec):
        if not rec or not rec.exists():
            raise UserError(_("Record not found or already deleted."))

