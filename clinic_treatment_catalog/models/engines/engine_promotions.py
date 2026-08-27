# -*- coding: utf-8 -*-
# ClinicOne - Treatment Catalog & Pricing
# File: models/engines/engine_promotions.py
#
# Promotions Engine (soft-coupled):
# - Menghitung delta diskon/mark-up dari promosi (campaign/rule/coupon)
# - Mendukung metode: fixed_price, percent, amount (fixed discount)
# - Scoping: treatment/category/tag, channel, clinic pricelist, qty, date/time window, weekday
# - Coupon: dukungan kode via context_tags (format: "coupon:CODE") atau field rule
# - Prioritas & stacking: exclusive vs allow_stack (per rule) + kompatibel dengan policy global
# - Batasan: min/max discount, max uses (preview tidak mengurangi counter — hanya compute)
#
# Model YANG DIHARAPKAN (jika modul promo aktif):
# - clinic.promo.campaign (name, active, company_id, valid_from, valid_to, channel, priority, allow_stack, ...)
# - clinic.promo.rule (campaign_id, scope('treatment'|'bundle'), treatment_id/m2m, category_id, tag_ids,
#                      method('fixed_price'|'percent'|'amount'), percent/amount/fixed_price,
#                      min_qty, max_discount_amount, min_base_amount, weekday_mask, time_start, time_end,
#                      clinic_pricelist_id (opsional), required_context_tags/excluded_context_tags,
#                      coupon_required(bool), coupon_code/relasi ke coupon, priority, active)
# - clinic.promo.coupon (code, campaign_id, valid_from, valid_to, usage_limit_total, usage_limit_per_partner, active)
#
# Catatan:
# - Semua akses model/field diamankan (cek registry & field dulu).
# - Jika struktur berbeda di addon promo yang kamu miliki, engine ini masih aman
#   karena memakai akses defensif dan nama kandidat field yang umum.
#
from odoo import api, models, fields, _
import logging

_logger = logging.getLogger(__name__)


class ClinicEnginePromotions(models.AbstractModel):
    _name = "clinic.engine_promotions"
    _description = "ClinicOne Promotions Engine (soft-coupled)"

    # ========================================================================
    # PUBLIC API: dipanggil oleh Bridge
    # ========================================================================
    @api.model
    def compute_treatment_deltas(
        self, treatment, partner_id=None, pricelist_id=None,
        quantity=1.0, at_date=None, context_tags=None
    ):
        """Hitung delta promosi untuk Treatment.

        Return: list[dict] komponen delta:
          [{ 'label': str, 'amount': -123.45, 'priority': 310, 'meta': {...} }, ...]
        """
        if not treatment:
            return []

        quantity = quantity or 1.0
        ctx_tags = context_tags or []
        at_dt = fields.Datetime.to_datetime(at_date) if at_date else fields.Datetime.now()

        # 1) Tentukan base price (acuan diskon)
        base_price = self._get_base_price_for_treatment(treatment, pricelist_id, quantity, at_dt)

        # 2) Ambil semua rules promo yang relevan untuk scope 'treatment'
        promos = self._get_applicable_promotions(
            scope="treatment",
            company=treatment.company_id,
            pricelist_id=pricelist_id,
            at_date=at_dt,
            context_tags=ctx_tags,
            partner_id=partner_id,
        )
        if not promos:
            return []

        # 3) Filter rule yang match terhadap treatment & kondisi
        matched = []
        for rule in promos:
            ok, reason = self._rule_matches_treatment(rule, treatment, quantity, ctx_tags, partner_id, at_dt)
            if ok:
                matched.append(rule)

        if not matched:
            return []

        # 4) Hitung delta per rule, hormati batas min/max & metadata
        candidates = []
        for r in matched:
            delta = self._compute_rule_delta_for_treatment(r, base_price, quantity)
            if delta is None:
                continue
            delta = self._apply_rule_limits(r, delta, base_price, quantity)
            label = self._rule_label(r)
            priority = int(self._get_any(r, ["priority", "sequence"], default=310))
            meta = self._rule_meta(r, scope="treatment", base_price=base_price, quantity=quantity)
            candidates.append({"label": label, "amount": float(delta), "priority": priority, "meta": meta})

        if not candidates:
            return []

        # 5) Stacking policy (per rule/campaign) + heuristik global:
        #    - Jika ada rule yang menyatakan exclusive → pilih satu terbaik di keluarga campaign itu
        #    - Jika allow_stack → kembalikan semua rule yang allow_stack
        chosen = self._apply_promo_stacking(candidates)

        return chosen

    @api.model
    def compute_bundle_deltas(
        self, bundle, partner_id=None, pricelist_id=None,
        quantity=1.0, at_date=None, context_tags=None
    ):
        """Hitung delta promosi untuk Bundle."""
        if not bundle:
            return []

        quantity = quantity or 1.0
        ctx_tags = context_tags or []
        at_dt = fields.Datetime.to_datetime(at_date) if at_date else fields.Datetime.now()

        # Base price acuan
        base_price = self._get_base_price_for_bundle(bundle, pricelist_id, quantity, at_dt)

        promos = self._get_applicable_promotions(
            scope="bundle",
            company=bundle.company_id,
            pricelist_id=pricelist_id,
            at_date=at_dt,
            context_tags=ctx_tags,
            partner_id=partner_id,
        )
        if not promos:
            return []

        matched = []
        for rule in promos:
            ok, reason = self._rule_matches_bundle(rule, bundle, quantity, ctx_tags, partner_id, at_dt)
            if ok:
                matched.append(rule)

        if not matched:
            return []

        candidates = []
        for r in matched:
            delta = self._compute_rule_delta_for_bundle(r, base_price, quantity)
            if delta is None:
                continue
            delta = self._apply_rule_limits(r, delta, base_price, quantity)
            label = self._rule_label(r)
            priority = int(self._get_any(r, ["priority", "sequence"], default=310))
            meta = self._rule_meta(r, scope="bundle", base_price=base_price, quantity=quantity)
            candidates.append({"label": label, "amount": float(delta), "priority": priority, "meta": meta})

        if not candidates:
            return []

        chosen = self._apply_promo_stacking(candidates)
        return chosen

    # ========================================================================
    # PROMO DISCOVERY
    # ========================================================================
    def _get_applicable_promotions(self, scope, company, pricelist_id, at_date, context_tags, partner_id):
        """
        Kumpulkan rules promo kandidat (aktif, valid date, channel/pricelist cocok, coupon cocok).
        Kembalikan list record rule (model apapun) yang lolos filter awal.
        """
        Rule = self._get_model("clinic.promo.rule")
        Campaign = self._get_model("clinic.promo.campaign")
        Coupon = self._get_model("clinic.promo.coupon")

        if not Rule:
            return []

        # Domain awal: aktif + scope + company (jika field ada)
        domain = [("active", "=", True)]
        if self._has_field(Rule, "scope"):
            domain.append(("scope", "=", scope))
        if company and self._has_field(Rule, "company_id"):
            domain.append(("company_id", "in", [False, company.id]))

        rules = Rule.search(domain, limit=1000)
        if not rules:
            return []

        # Validitas tanggal (rule)
        rules = [r for r in rules if self._record_is_active_by_date(r, at_date)]

        # Campaign aktif & valid
        if self._has_field(Rule, "campaign_id") and Campaign:
            tmp = []
            for r in rules:
                c = getattr(r, "campaign_id", False)
                if not c:
                    tmp.append(r)
                    continue
                if getattr(c, "active", True) and self._record_is_active_by_date(c, at_date):
                    tmp.append(r)
            rules = tmp

        # Channel/Clinic Pricelist
        filtered = []
        header = self._resolve_clinic_pricelist(pricelist_id)
        channel = getattr(header, "channel", "all") if header else "all"
        for r in rules:
            if self._has_field(r, "channel") and r.channel and r.channel not in ("all", "any", channel):
                continue
            if self._has_field(r, "clinic_pricelist_id") and r.clinic_pricelist_id:
                if not header or r.clinic_pricelist_id.id != header.id:
                    continue
            filtered.append(r)
        rules = filtered

        # Context tags (rule & campaign) — required / excluded
        rules = [r for r in rules if self._context_tags_ok(r, context_tags)]
        if Campaign and any(self._has_field(r, "campaign_id") for r in rules):
            rules = [r for r in rules if self._campaign_context_tags_ok(getattr(r, "campaign_id", False), context_tags)]

        # Coupon (opsional): deteksi di context_tags format 'coupon:CODE'
        coupons = self._extract_coupon_codes(context_tags)
        if coupons:
            rules = self._filter_rules_by_coupons(rules, Coupon, coupons, at_date, partner_id)

        # Limit penggunaan/budget (preview tidak mengurangi; hanya screening jika sudah habis total)
        rules = [r for r in rules if self._has_remaining_budget_or_usage(r, partner_id)]

        return rules

    # ========================================================================
    # RULE MATCHING
    # ========================================================================
    def _rule_matches_treatment(self, rule, treatment, qty, context_tags, partner_id, at_date):
        """Evaluasi apakah rule berlaku untuk treatment."""
        # min qty
        if self._has_field(rule, "min_qty") and rule.min_qty and float(qty or 0.0) < float(rule.min_qty):
            return (False, "min_qty")

        # treatment langsung
        if self._has_field(rule, "treatment_id") and rule.treatment_id:
            return (rule.treatment_id.id == treatment.id, "treatment_id")

        # banyak treatment
        if self._has_field(rule, "treatment_ids") and rule.treatment_ids:
            if treatment.id in rule.treatment_ids.ids:
                return (True, "treatment_ids")

        # kategori
        if self._has_field(rule, "category_id") and rule.category_id:
            cat = treatment.category_id
            if cat and (cat.id == rule.category_id.id or str(rule.category_id.id) in (cat.parent_path or "")):
                return (True, "category_id")

        # tag
        if self._has_field(rule, "tag_ids") and rule.tag_ids:
            if set(rule.tag_ids.ids).intersection(set(treatment.tag_ids.ids)):
                return (True, "tag_ids")

        # time window / weekday (opsional)
        if not self._time_ok(rule, at_date):
            return (False, "time_window")

        # partner whitelist/blacklist (opsional)
        if not self._partner_ok(rule, partner_id):
            return (False, "partner")

        # Jika rule tidak spesifik field scoping, anggap global untuk scope ini
        none_specified = True
        for fname in ("treatment_id", "treatment_ids", "category_id", "tag_ids"):
            if self._has_field(rule, fname) and getattr(rule, fname):
                none_specified = False
        return (True, "global") if none_specified else (False, "no_match")

    def _rule_matches_bundle(self, rule, bundle, qty, context_tags, partner_id, at_date):
        if self._has_field(rule, "min_qty") and rule.min_qty and float(qty or 0.0) < float(rule.min_qty):
            return (False, "min_qty")

        # bundle spesifik (jika ada field)
        if self._has_field(rule, "bundle_id") and rule.bundle_id:
            return (rule.bundle_id.id == bundle.id, "bundle_id")

        # tag di dalam bundle (cek via treatment lines)
        if self._has_field(rule, "tag_ids") and rule.tag_ids:
            ttags = set(bundle.line_ids.mapped("treatment_id.tag_ids").ids)
            if set(rule.tag_ids.ids).intersection(ttags):
                return (True, "tag_ids")

        if not self._time_ok(rule, at_date):
            return (False, "time_window")
        if not self._partner_ok(rule, partner_id):
            return (False, "partner")

        none_specified = True
        for fname in ("bundle_id", "tag_ids"):
            if self._has_field(rule, fname) and getattr(rule, fname):
                none_specified = False
        return (True, "global") if none_specified else (False, "no_match")

    # ========================================================================
    # DELTA COMPUTATION
    # ========================================================================
    def _compute_rule_delta_for_treatment(self, rule, base_price, qty):
        method = self._get_method(rule)
        if method == "fixed_price":
            fp = self._get_any_number(rule, ["fixed_price", "fixed", "price"])
            if fp is None:
                return None
            return (float(fp) - float(base_price)) * float(qty or 1.0)
        elif method == "percent":
            pct = self._get_any_number(rule, ["percent", "percentage"])
            if pct in (None, 0.0):
                return None
            return - (float(base_price) * float(pct) / 100.0) * float(qty or 1.0)
        elif method == "amount":
            amt = self._get_any_number(rule, ["amount", "fixed_discount", "discount_amount"])
            if amt in (None, 0.0):
                return None
            return - float(amt) * float(qty or 1.0)
        return None

    def _compute_rule_delta_for_bundle(self, rule, base_price, qty):
        method = self._get_method(rule)
        if method == "fixed_price":
            fp = self._get_any_number(rule, ["fixed_price", "fixed", "price"])
            if fp is None:
                return None
            return (float(fp) - float(base_price)) * float(qty or 1.0)
        elif method == "percent":
            pct = self._get_any_number(rule, ["percent", "percentage"])
            if pct in (None, 0.0):
                return None
            return - (float(base_price) * float(pct) / 100.0) * float(qty or 1.0)
        elif method == "amount":
            amt = self._get_any_number(rule, ["amount", "fixed_discount", "discount_amount"])
            if amt in (None, 0.0):
                return None
            return - float(amt) * float(qty or 1.0)
        return None

    def _apply_rule_limits(self, rule, delta, base_price, qty):
        """Hormati batas minimum base, dan max discount amount per rule bila ada."""
        # Minimum base amount
        mba = self._get_any_number(rule, ["min_base_amount", "minimum_base_amount"])
        if mba not in (None, False) and float(base_price) < float(mba):
            return 0.0

        # Max discount per line (absolute cap); delta adalah negatif utk diskon
        cap = self._get_any_number(rule, ["max_discount_amount", "maximum_discount_amount"])
        if cap not in (None, False) and float(cap) >= 0.0 and delta < 0.0:
            # delta negatif → batasi |delta|
            if abs(delta) > float(cap) * float(qty or 1.0):
                return - float(cap) * float(qty or 1.0)
        return delta

    # ========================================================================
    # STACKING / EXCLUSIVITY
    # ========================================================================
    def _apply_promo_stacking(self, candidates):
        """Terapkan kebijakan stacking per kandidat.
        Heuristik:
          - Jika kandidat punya meta.exclusive=True → pilih yang memberi final terbaik (delta paling negatif)
          - Jika tidak ada exclusive → kembalikan semua (allow stack)
        """
        if not candidates:
            return []

        exclusives = [c for c in candidates if c.get("meta", {}).get("exclusive")]
        if exclusives:
            # pilih satu exclusive dengan delta paling menguntungkan (paling negatif)
            best = None
            for c in exclusives:
                if best is None or float(c["amount"]) < float(best["amount"]):
                    best = c
            return [best]
        # allow stacking: semua kandidat kembali (Bridge akan jumlahkan)
        return candidates

    # ========================================================================
    # HELPERS: BASE PRICE, TIME/PARTNER, COUPON, CONTEXT, BUDGET
    # ========================================================================
    def _get_base_price_for_treatment(self, treatment, pricelist_id, qty, at_date):
        """Samakan dengan bridge: gunakan Odoo Pricelist jika ada; fallback base_price."""
        try:
            product = treatment.get_service_product()
            if pricelist_id and product and product.exists():
                header = self._resolve_clinic_pricelist(pricelist_id)
                pl = header.product_pricelist_id if header else self.env["product.pricelist"].browse(pricelist_id)
                if pl and pl.exists():
                    return float(pl._get_product_price(product, qty or 1.0, uom=product.uom_id, date=at_date))
            return float(treatment.get_default_price() or 0.0)
        except Exception as e:  # pragma: no cover
            _logger.debug("Promo base price (treatment) fallback: %s", e)
            return float(treatment.get_default_price() or 0.0)

    def _get_base_price_for_bundle(self, bundle, pricelist_id, qty, at_date):
        try:
            product = bundle.get_service_product()
            if pricelist_id and product and product.exists():
                header = self._resolve_clinic_pricelist(pricelist_id)
                pl = header.product_pricelist_id if header else self.env["product.pricelist"].browse(pricelist_id)
                if pl and pl.exists():
                    return float(pl._get_product_price(product, qty or 1.0, uom=product.uom_id, date=at_date))
        except Exception as e:  # pragma: no cover
            _logger.debug("Promo base price (bundle) PRICELIST fallback: %s", e)

        if bundle.pricing_policy == "fixed":
            return float(bundle.base_price or 0.0)
        if bundle.pricing_policy == "sum":
            return float(bundle.computed_sum_price or 0.0)
        return float(bundle.base_price or 0.0)

    def _time_ok(self, rule, at_date):
        """Weekday + time window check (opsional)."""
        # Weekday mask: string "1,2,3" atau binary mask; kita dukung string daftar
        if self._has_field(rule, "weekday_mask") and rule.weekday_mask:
            try:
                weekdays = {int(x) for x in str(rule.weekday_mask).split(",") if x}
                # Python: Monday=0..Sunday=6; asumsikan rule 1=Mon .. 7=Sun
                dow = (fields.Datetime.to_datetime(at_date) or fields.Datetime.now()).weekday() + 1
                if dow not in weekdays:
                    return False
            except Exception:
                pass

        # Time window (jam:menit) — dukung field time_start/time_end bertipe float jam atau char "HH:MM"
        def _to_minutes(v):
            if v in (None, False):
                return None
            if isinstance(v, (int, float)):
                return int(float(v) * 60.0)
            try:
                hh, mm = str(v).split(":")
                return int(hh) * 60 + int(mm)
            except Exception:
                return None

        tstart = self._get_any(rule, ["time_start", "start_time", "window_start"])
        tend = self._get_any(rule, ["time_end", "end_time", "window_end"])
        if tstart or tend:
            now = fields.Datetime.context_timestamp(rule, at_date or fields.Datetime.now())
            minutes = now.hour * 60 + now.minute
            ms = _to_minutes(tstart)
            me = _to_minutes(tend)
            if ms is not None and minutes < ms:
                return False
            if me is not None and minutes > me:
                return False
        return True

    def _partner_ok(self, rule, partner_id):
        """Whitelist/Blacklist partner (opsional)."""
        if not partner_id:
            return True
        if self._has_field(rule, "partner_ids") and rule.partner_ids:
            return partner_id in rule.partner_ids.ids
        if self._has_field(rule, "excluded_partner_ids") and rule.excluded_partner_ids:
            return partner_id not in rule.excluded_partner_ids.ids
        return True

    def _context_tags_ok(self, rule, context_tags):
        """Required/Excluded context tags di rule."""
        req = self._get_any(rule, ["required_context_tags"])
        if req:
            reqs = {t.strip() for t in str(req).split(",") if t.strip()}
            if not set(context_tags or []).issuperset(reqs):
                return False
        exc = self._get_any(rule, ["excluded_context_tags"])
        if exc:
            exs = {t.strip() for t in str(exc).split(",") if t.strip()}
            if set(context_tags or []).intersection(exs):
                return False
        return True

    def _campaign_context_tags_ok(self, campaign, context_tags):
        """Required/Excluded context tags di campaign (opsional)."""
        if not campaign:
            return True
        req = self._get_any(campaign, ["required_context_tags"])
        if req:
            reqs = {t.strip() for t in str(req).split(",") if t.strip()}
            if not set(context_tags or []).issuperset(reqs):
                return False
        exc = self._get_any(campaign, ["excluded_context_tags"])
        if exc:
            exs = {t.strip() for t in str(exc).split(",") if t.strip()}
            if set(context_tags or []).intersection(exs):
                return False
        return True

    def _extract_coupon_codes(self, context_tags):
        """Ambil token 'coupon:XXXX' dari context_tags."""
        coupons = []
        for t in context_tags or []:
            if isinstance(t, str) and t.lower().startswith("coupon:"):
                code = t.split(":", 1)[1].strip()
                if code:
                    coupons.append(code)
        return coupons

    def _filter_rules_by_coupons(self, rules, Coupon, coupons, at_date, partner_id):
        """Jika ada kupon, hanya pertahankan rule yang cocok dan kupon valid."""
        if not Coupon:
            # Jika engine coupon tidak ada, tetap izinkan rules tanpa coupon_required
            return [r for r in rules if not (self._has_field(r, "coupon_required") and r.coupon_required)]
        filtered = []
        for r in rules:
            requires = bool(self._has_field(r, "coupon_required") and r.coupon_required)
            if not requires:
                filtered.append(r)
                continue
            # cocokkan kupon:
            # a) single code di rule (coupon_code)
            code_ok = False
            rule_code = self._get_any(r, ["coupon_code", "code"])
            if rule_code and str(rule_code).strip() in coupons:
                code_ok = True
            # b) relasi ke coupon records
            if not code_ok and self._has_field(r, "coupon_ids") and r.coupon_ids:
                # validitas coupon:
                for cp in r.coupon_ids:
                    if not getattr(cp, "active", True):
                        continue
                    if not self._record_is_active_by_date(cp, at_date):
                        continue
                    if str(getattr(cp, "code", "")).strip() in coupons:
                        code_ok = True
                        break
            if not code_ok:
                continue
            # Optional per-partner usage limit checks bisa ditambahkan di tahap booking/confirm (bukan di preview)
            filtered.append(r)
        return filtered

    def _has_remaining_budget_or_usage(self, rule, partner_id):
        """Screening batas promosi: jika sudah habis total budget/usage, jangan ditawarkan.
        (Preview tidak memodifikasi counter).
        """
        # Budget nominal total (opsional)
        budget_total = self._get_any_number(rule, ["budget_total", "budget_amount"])
        budget_used = self._get_any_number(rule, ["budget_used", "budget_consumed"])
        if budget_total not in (None, False) and budget_used not in (None, False):
            if float(budget_used) >= float(budget_total):
                return False

        # Usage total (opsional)
        usage_total = self._get_any_number(rule, ["usage_limit_total", "max_uses"])
        usage_used = self._get_any_number(rule, ["usage_used_total", "uses"])
        if usage_total not in (None, False) and usage_used not in (None, False):
            if float(usage_used) >= float(usage_total):
                return False

        # Per partner (opsional) — pengecekan sebenarnya sebaiknya saat konfirmasi transaksi
        if partner_id:
            limit_pp = self._get_any_number(rule, ["usage_limit_per_partner", "max_uses_per_partner"])
            # usage_by_partner bisa diimplementasikan di addon promo (table log). Di preview kita tidak bisa cek pasti.
            # Jadi hanya screening jika field aggregator tersedia.
            if limit_pp not in (None, False):
                # Jika ada field 'usage_partner_ids' (m2m) atau 'usage_partner_json' (char), kita bisa estimasi.
                if self._has_field(rule, "usage_partner_ids") and rule.usage_partner_ids:
                    used = 1 if partner_id in rule.usage_partner_ids.ids else 0
                    if used >= float(limit_pp):
                        return False
        return True

    # ========================================================================
    # UTIL: METHOD, LABEL, META, VALIDITY, PRICELIST, MODEL/FIELD SAFE ACCESS
    # ========================================================================
    def _get_method(self, rule):
        raw = self._get_any(rule, ["method", "benefit_type", "rule_type"], default="percent")
        raw = (raw or "percent").lower()
        if raw in ("fixed", "fixed_price", "price"):
            return "fixed_price"
        if raw in ("percent", "percentage", "perc"):
            return "percent"
        if raw in ("amount", "nominal", "fixed_discount"):
            return "amount"
        return "percent"

    def _rule_label(self, rule):
        name = self._get_any(rule, ["name", "display_name"], default="Promotion")
        camp = self._get_any(rule, ["campaign_id"])
        cname = getattr(camp, "name", "") if camp else ""
        if cname:
            return _("%s — %s") % (cname, name)
        return _("Promotion — %s") % name

    def _rule_meta(self, rule, scope, base_price, quantity):
        meta = {
            "rule_id": rule.id,
            "rule_model": rule._name,
            "scope": scope,
            "method": self._get_method(rule),
            "base_price": float(base_price or 0.0),
            "quantity": float(quantity or 1.0),
            "exclusive": bool(self._get_any(rule, ["exclusive", "is_exclusive"], default=False)),
        }
        # lampirkan id referensi scoping jika ada (untuk audit)
        for fname in ("treatment_id", "treatment_ids", "category_id", "tag_ids", "bundle_id", "clinic_pricelist_id"):
            if self._has_field(rule, fname):
                try:
                    val = getattr(rule, fname)
                    meta[fname] = val.ids if hasattr(val, "ids") else (val.id if getattr(val, "id", False) else val)
                except Exception:
                    continue
        return meta

    def _record_is_active_by_date(self, rec, at_date):
        """Valid From/To flexible (mendukung nama field berbeda)."""
        vf = self._get_any(rec, ["valid_from", "date_from", "start_date"])
        vt = self._get_any(rec, ["valid_to", "date_to", "end_date"])
        if not vf and not vt:
            return True
        ad = fields.Datetime.to_datetime(at_date) if at_date else fields.Datetime.now()
        ok_from = True if not vf else (ad >= fields.Datetime.to_datetime(vf))
        ok_to = True if not vt else (ad <= fields.Datetime.to_datetime(vt))
        return bool(ok_from and ok_to)

    def _resolve_clinic_pricelist(self, pricelist_id):
        env = self.env
        if not pricelist_id:
            return None
        PLClinic = self._get_model("clinic.treatment.pricelist")
        if PLClinic and PLClinic.browse(pricelist_id).exists():
            return PLClinic.browse(pricelist_id)
        PL = self._get_model("product.pricelist")
        if PL and PL.browse(pricelist_id).exists():
            pl = PL.browse(pricelist_id)
            if self._has_field(pl, "clinic_pricelist_id") and pl.clinic_pricelist_id:
                return pl.clinic_pricelist_id
        return None

    def _get_model(self, model_name):
        try:
            if self.env.registry.get(model_name):
                return self.env[model_name]
        except Exception:
            return None
        return None

    def _has_field(self, rec_or_model, field_name):
        try:
            return field_name in getattr(rec_or_model, "_fields", {})
        except Exception:
            return False

    def _get_any(self, rec, names, default=None):
        """Ambil nilai pertama yang ada dari daftar nama field/attr."""
        if isinstance(names, (list, tuple)):
            for n in names:
                try:
                    if self._has_field(rec, n):
                        return getattr(rec, n)
                except Exception:
                    continue
            return default
        else:
            try:
                if self._has_field(rec, names):
                    return getattr(rec, names)
            except Exception:
                pass
            return default

    def _get_any_number(self, rec, names, default=None):
        val = self._get_any(rec, names, default=None)
        if val in (None, False):
            return default
        try:
            return float(val)
        except Exception:
            return default

