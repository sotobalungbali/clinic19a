# -*- coding: utf-8 -*-
# ClinicOne - Treatment Catalog & Pricing
# File: models/engines/engine_insurance.py
#
# Insurance Engine (soft-coupled):
# - Menentukan enrollment/polis aktif customer pada tanggal tertentu
# - Mencari rule coverage yang relevan (treatment/category/tag/bundle)
# - Menghitung delta:
#     covered_amount (negatif), deductible_applied (positif), copay (positif),
#     limit/shortfall korektif (positif), serta penyesuaian OOP cap (negatif).
# - Menghormati flag konfigurasi:
#     - res.company.clinic_booking_include_insurance
#     - clinic.treatment.pricelist.apply_insurance
#     - treatment.insurance_applicable (jika ada)
#
# Model yang DIHARAPKAN (jika modul asuransi aktif — semua akses aman/opsional):
# - clinic.insurance.member   (partner_id, plan_id, valid_from/to, state, deductible_remaining, oop_remaining, annual_remaining, ...)
# - clinic.insurance.plan     (name, payer_id, company_id, rules, general settings)
# - clinic.insurance.rule     (scope='treatment'|'bundle'|'both', method='percent'|'amount'|'fixed_price',
#                              percent, amount, fixed_price, copay_type=fixed|percent, copay_value,
#                              deductible_applicable(bool), min_qty, min_base_amount,
#                              per_visit_limit, annual_limit, waiting_period_days,
#                              preauth_required, referral_required,
#                              treatment_id/m2m, category_id, tag_ids, bundle_id,
#                              channel, clinic_pricelist_id, required_context_tags, excluded_context_tags,
#                              priority/sequence, active, valid_from/to)
#
# Catatan:
# - Nama model/field bisa berbeda di addon asuransi kamu. Engine ini memakai akses defensif:
#   _get_model(), _has_field(), _get_any(), _get_any_number() sehingga aman meski struktur berbeda.
#
from odoo import api, models, fields, _
import logging

_logger = logging.getLogger(__name__)


class ClinicEngineInsurance(models.AbstractModel):
    _name = "clinic.engine_insurance"
    _description = "ClinicOne Insurance Engine (soft-coupled)"

    # ========================================================================
    # PUBLIC API — dipanggil Bridge
    # ========================================================================
    @api.model
    def compute_treatment_deltas(
        self, treatment, partner_id=None, pricelist_id=None,
        quantity=1.0, at_date=None, context_tags=None
    ):
        """Hitung penyesuaian harga oleh asuransi untuk satu Treatment."""
        if not treatment:
            return []

        # Hormati flag global (perusahaan/pricelist) & flag di treatment
        if hasattr(treatment, "insurance_applicable") and not bool(treatment.insurance_applicable):
            return []
        if not self._company_or_pricelist_allows_insurance(treatment.company_id, pricelist_id):
            return []

        if not partner_id:
            return []  # tak ada pasien → tak ada asuransi

        qty = float(quantity or 1.0)
        ctx = self._parse_context(context_tags or [])
        at_dt = fields.Datetime.to_datetime(at_date) if at_date else fields.Datetime.now()

        # Dapatkan enrollment/plan aktif
        member, plan = self._get_active_member_and_plan(partner_id, at_dt)
        if not plan:
            return []

        # Base price acuan
        base_price = self._get_base_price_for_treatment(treatment, pricelist_id, qty, at_dt)

        # Ambil rule coverage relevan (scope 'treatment')
        rules = self._get_applicable_rules("treatment", plan, treatment.company_id, pricelist_id, at_dt, ctx)
        if not rules:
            return []

        # Filter rule match (treatment/category/tag), waktu, syarat preauth/referral/waiting period
        matched = []
        for r in rules:
            ok, reason = self._rule_matches_treatment(r, treatment, qty, ctx, at_dt, member)
            if ok:
                matched.append(r)
        if not matched:
            return []

        # Pilih rule terbaik (prioritas tertinggi → atau paling menguntungkan)
        chosen_rule = self._choose_best_rule(matched, base_price, qty)

        # Hitung delta detail (coverage/copay/deductible/limits/OOP)
        delta, meta_parts = self._compute_insurance_delta_for_rule(
            rule=chosen_rule, base_price=base_price, qty=qty, ctx=ctx, member=member, plan=plan
        )
        if delta is None:
            return []

        label = self._component_label(plan, member, chosen_rule)
        prio = int(self._get_any(chosen_rule, ["priority", "sequence"], default=510))  # 5xx insurance domain
        meta = self._compose_meta(member, plan, chosen_rule, "treatment", base_price, qty, ctx, meta_parts)

        # Kembalikan satu komponen insurance (delta total)
        return [{"label": label, "amount": float(delta), "priority": prio, "meta": meta}]

    @api.model
    def compute_bundle_deltas(
        self, bundle, partner_id=None, pricelist_id=None,
        quantity=1.0, at_date=None, context_tags=None
    ):
        """Hitung penyesuaian harga oleh asuransi untuk Bundle."""
        if not bundle:
            return []

        if not self._company_or_pricelist_allows_insurance(bundle.company_id, pricelist_id):
            return []
        if not partner_id:
            return []

        qty = float(quantity or 1.0)
        ctx = self._parse_context(context_tags or [])
        at_dt = fields.Datetime.to_datetime(at_date) if at_date else fields.Datetime.now()

        member, plan = self._get_active_member_and_plan(partner_id, at_dt)
        if not plan:
            return []

        base_price = self._get_base_price_for_bundle(bundle, pricelist_id, qty, at_dt)

        rules = self._get_applicable_rules("bundle", plan, bundle.company_id, pricelist_id, at_dt, ctx)
        if not rules:
            return []

        matched = []
        for r in rules:
            ok, reason = self._rule_matches_bundle(r, bundle, qty, ctx, at_dt, member)
            if ok:
                matched.append(r)
        if not matched:
            return []

        chosen_rule = self._choose_best_rule(matched, base_price, qty)
        delta, meta_parts = self._compute_insurance_delta_for_rule(
            rule=chosen_rule, base_price=base_price, qty=qty, ctx=ctx, member=member, plan=plan
        )
        if delta is None:
            return []

        label = self._component_label(plan, member, chosen_rule)
        prio = int(self._get_any(chosen_rule, ["priority", "sequence"], default=510))
        meta = self._compose_meta(member, plan, chosen_rule, "bundle", base_price, qty, ctx, meta_parts)

        return [{"label": label, "amount": float(delta), "priority": prio, "meta": meta}]

    # ========================================================================
    # DISCOVERY: MEMBER/PLAN/RULES
    # ========================================================================
    def _company_or_pricelist_allows_insurance(self, company, pricelist_id):
        """Baca bendera kebijakan dari res.company dan header clinic.treatment.pricelist (jika ada)."""
        try:
            # company flag (default False di settings; bisa diubah)
            company_ok = bool(getattr(company, "clinic_booking_include_insurance", False)) \
                         or bool(getattr(company, "clinic_default_insurance_applicable", False))
        except Exception:
            company_ok = False

        header = self._resolve_clinic_pricelist(pricelist_id)
        header_ok = True
        if header and self._has_field(header, "apply_insurance"):
            header_ok = bool(header.apply_insurance)

        return bool(company_ok and header_ok)

    def _get_active_member_and_plan(self, partner_id, at_date):
        """Cari enrollment asuransi aktif untuk partner pada at_date.
        Return (member_rec or None, plan_rec or None).
        """
        Member = self._get_model("clinic.insurance.member")
        Plan = self._get_model("clinic.insurance.plan")
        env = self.env
        adt = fields.Datetime.to_datetime(at_date) if at_date else fields.Datetime.now()

        if not Member or not Plan:
            # fallback: coba field partner.default_insurance_plan_id
            partner = env["res.partner"].browse(partner_id)
            if self._has_field(partner, "clinic_insurance_plan_id") and partner.clinic_insurance_plan_id:
                return None, partner.clinic_insurance_plan_id
            return None, None

        enrolls = Member.search([("partner_id", "=", partner_id)], limit=50)
        active = None
        for m in enrolls:
            if not self._record_is_active_by_date(m, adt):
                continue
            if self._has_field(m, "state") and m.state not in ("active", "valid", "running"):
                continue
            active = m
            break
        if not active:
            return None, None
        plan = getattr(active, "plan_id", False) if self._has_field(active, "plan_id") else False
        return active, plan if plan and plan.exists() else (active, None)

    def _get_applicable_rules(self, scope, plan, company, pricelist_id, at_date, ctx):
        """Ambil rules coverage kandidat dari plan."""
        Rule = self._get_model("clinic.insurance.rule")
        if not Rule:
            return []

        domain = [("active", "=", True)]
        if self._has_field(Rule, "scope"):
            domain += ["|", ("scope", "=", scope), ("scope", "=", "both")]
        # link ke plan
        if self._has_field(Rule, "plan_id") and plan:
            domain.append(("plan_id", "=", plan.id))
        # company wise (opsional)
        if company and self._has_field(Rule, "company_id"):
            domain.append(("company_id", "in", [False, company.id]))

        rules = Rule.search(domain, limit=1000)
        if not rules:
            return []

        # Validity
        rules = [r for r in rules if self._record_is_active_by_date(r, at_date)]

        # Channel & Pricelist scoping
        header = self._resolve_clinic_pricelist(pricelist_id)
        channel = getattr(header, "channel", "all") if header else "all"
        filtered = []
        for r in rules:
            if self._has_field(r, "channel") and r.channel and r.channel not in ("all", "any", channel):
                continue
            if self._has_field(r, "clinic_pricelist_id") and r.clinic_pricelist_id:
                if not header or r.clinic_pricelist_id.id != header.id:
                    continue
            if not self._context_tags_ok(r, ctx.get("raw_tags", [])):
                continue
            filtered.append(r)
        return filtered

    # ========================================================================
    # MATCHING: TREATMENT / BUNDLE + SYARAT KHUSUS
    # ========================================================================
    def _rule_matches_treatment(self, rule, treatment, qty, ctx, at_date, member):
        # min qty
        if self._has_field(rule, "min_qty") and rule.min_qty and float(qty or 0.0) < float(rule.min_qty):
            return (False, "min_qty")

        # treatment specific
        if self._has_field(rule, "treatment_id") and rule.treatment_id:
            return (rule.treatment_id.id == treatment.id, "treatment_id")

        # many2many
        if self._has_field(rule, "treatment_ids") and rule.treatment_ids:
            if treatment.id in rule.treatment_ids.ids:
                return (True, "treatment_ids")

        # category
        if self._has_field(rule, "category_id") and rule.category_id:
            cat = treatment.category_id
            if not cat:
                return (False, "category_id")
            if not (cat.id == rule.category_id.id or str(rule.category_id.id) in (cat.parent_path or "")):
                return (False, "category_id")

        # tags
        if self._has_field(rule, "tag_ids") and rule.tag_ids:
            if not set(rule.tag_ids.ids).intersection(set(treatment.tag_ids.ids)):
                return (False, "tag_ids")

        # waiting period
        if not self._waiting_period_ok(rule, member, at_date):
            return (False, "waiting_period")

        # pre-authorization & referral requirements
        if not self._auth_requirements_ok(rule, ctx):
            return (False, "authorization")

        return (True, "ok")

    def _rule_matches_bundle(self, rule, bundle, qty, ctx, at_date, member):
        if self._has_field(rule, "min_qty") and rule.min_qty and float(qty or 0.0) < float(rule.min_qty):
            return (False, "min_qty")

        if self._has_field(rule, "bundle_id") and rule.bundle_id:
            return (rule.bundle_id.id == bundle.id, "bundle_id")

        if self._has_field(rule, "tag_ids") and rule.tag_ids:
            ttags = set(bundle.line_ids.mapped("treatment_id.tag_ids").ids)
            if not set(rule.tag_ids.ids).intersection(ttags):
                return (False, "tag_ids")

        if not self._waiting_period_ok(rule, member, at_date):
            return (False, "waiting_period")
        if not self._auth_requirements_ok(rule, ctx):
            return (False, "authorization")

        return (True, "ok")

    def _waiting_period_ok(self, rule, member, at_date):
        """Cek masa tunggu (opsional)."""
        if not member:
            return True
        wp = self._get_any_number(rule, ["waiting_period_days", "waiting_days"])
        if wp in (None, False) or wp <= 0:
            return True
        # ambil enrollment start date
        start = self._get_any(member, ["valid_from", "date_from", "start_date"])
        if not start:
            return True
        ad = fields.Datetime.to_datetime(at_date) if at_date else fields.Datetime.now()
        sd = fields.Datetime.to_datetime(start)
        return (ad - sd).days >= int(wp)

    def _auth_requirements_ok(self, rule, ctx):
        """Cek prasyarat preauth/referral lewat context tags:
        - 'preauth:yes' / 'referral:yes'
        """
        preauth = bool(self._get_any(rule, ["preauth_required", "pre_authorization_required"], default=False))
        referral = bool(self._get_any(rule, ["referral_required"], default=False))
        if preauth and str(ctx.get("preauth", "")).lower() != "yes":
            return False
        if referral and str(ctx.get("referral", "")).lower() != "yes":
            return False
        return True

    # ========================================================================
    # PILIH RULE & HITUNG DELTA INSURANCE
    # ========================================================================
    def _choose_best_rule(self, rules, base_price, qty):
        """Heuristik: pilih rule yang memberi patient portion terendah (base+delta)."""
        best = None
        best_final = None
        for r in rules:
            est_delta, _ = self._compute_insurance_delta_for_rule(r, base_price, qty, ctx={}, member=None, plan=None)
            if est_delta is None:
                continue
            final = float(base_price) + float(est_delta)
            if best is None or final < best_final:
                best, best_final = r, final
        return best or rules[0]

    def _compute_insurance_delta_for_rule(self, rule, base_price, qty, ctx, member, plan):
        """Kembalikan (delta_total, meta_parts_dict).
        Delta total = (+deductible_applied) + (+copay_amount) - (covered_amount) + (+limit_shortfall_adjust)
        """
        qty = float(qty or 1.0)
        bp = float(base_price or 0.0)

        # 1) Deductible (applied dulu, kurangi basis yang dicakup)
        deductible_remaining = self._context_or_member_number(ctx, member, ["deductible_remaining", "deductible_left"], default=None)
        deductible_applicable = bool(self._get_any(rule, ["deductible_applicable"], default=True))
        deductible_applied = 0.0
        coverage_base = bp
        if deductible_applicable and deductible_remaining not in (None, False) and deductible_remaining > 0:
            deductible_applied = min(coverage_base, float(deductible_remaining))
            coverage_base -= deductible_applied  # sisa yang bisa dicakup asuransi

        # 2) Coverage (percent/fixed/fixed_price)
        method = self._get_method(rule)
        raw_covered = 0.0
        if method == "percent":
            pct = self._get_any_number(rule, ["percent", "coverage_percent"])
            if pct not in (None, False) and pct > 0:
                raw_covered = coverage_base * (pct / 100.0) * qty
        elif method == "amount":
            amt = self._get_any_number(rule, ["amount", "coverage_amount"])
            if amt not in (None, False) and amt > 0:
                raw_covered = min(coverage_base * qty, float(amt) * qty)
        elif method == "fixed_price":
            fp = self._get_any_number(rule, ["fixed_price", "coverage_price"])
            if fp not in (None, False) and fp >= 0:
                # fixed price = total yang dibayar pasien (pre-copay) → covered = (bp*qty) - fp (minimal 0)
                intended_patient = float(fp) * qty
                raw_covered = max((bp * qty) - intended_patient, 0.0)

        # 3) Batas per-visit dan tahunan (annual)
        per_visit_limit = self._get_any_number(rule, ["per_visit_limit", "max_covered_per_visit"])
        annual_limit_rule = self._get_any_number(rule, ["annual_limit", "max_covered_per_year"])
        annual_remaining = self._context_or_member_number(ctx, member, ["annual_remaining", "annual_coverage_remaining"], default=None)

        covered_after_limits = raw_covered
        limit_shortfall = 0.0

        if per_visit_limit not in (None, False) and per_visit_limit >= 0:
            if covered_after_limits > per_visit_limit:
                limit_shortfall += (covered_after_limits - per_visit_limit)
                covered_after_limits = per_visit_limit

        if annual_limit_rule not in (None, False) and annual_remaining not in (None, False):
            # Coverage tak boleh melebihi remaining annual
            allowed = min(float(annual_limit_rule), float(annual_remaining))
            if covered_after_limits > allowed:
                limit_shortfall += (covered_after_limits - allowed)
                covered_after_limits = allowed

        covered_amount = max(0.0, covered_after_limits)

        # 4) Co-pay (ditambah ke beban pasien)
        copay_type = (self._get_any(rule, ["copay_type"]) or "fixed").lower()
        copay_val = self._get_any_number(rule, ["copay_value", "copay", "co_pay"])
        copay_amount = 0.0
        if copay_val not in (None, False) and copay_val > 0:
            if copay_type in ("percent", "percentage"):
                # Umumnya persen dari biaya yang "allowed"; kita pakai coverage_base setelah deductible
                copay_amount = (coverage_base * (copay_val / 100.0)) * qty
            else:
                copay_amount = float(copay_val) * qty

        # 5) Out-of-pocket (OOP) cap — jika disediakan
        oop_remaining = self._context_or_member_number(ctx, member, ["oop_remaining", "out_of_pocket_remaining"], default=None)
        patient_portion = (bp * qty) - covered_amount + deductible_applied + copay_amount
        oop_adjust = 0.0
        if oop_remaining not in (None, False):
            # Jika porsi pasien melampaui OOP remaining → turunkan sampai batas (asuransi menutup selisih)
            if patient_portion > float(oop_remaining):
                diff = patient_portion - float(oop_remaining)
                # diff ini seharusnya dikover → kurangi patient (delta negatif)
                oop_adjust = -diff
                patient_portion = float(oop_remaining)

        # 6) Minimum base amount (rule gating)
        min_base = self._get_any_number(rule, ["min_base_amount", "minimum_base_amount"])
        if min_base not in (None, False) and bp < float(min_base):
            # tidak memenuhi syarat coverage; semua nol
            deductible_applied = 0.0
            covered_amount = 0.0
            copay_amount = 0.0
            limit_shortfall = 0.0
            oop_adjust = 0.0

        # 7) Delta total = +deductible +copay -covered +shortfall +oop_adjust
        delta_total = float(deductible_applied + copay_amount - covered_amount + limit_shortfall + oop_adjust)

        # Meta parts untuk audit
        meta_parts = {
            "method": method,
            "covered_amount": round(covered_amount, 2),
            "deductible_applied": round(deductible_applied, 2),
            "copay_amount": round(copay_amount, 2),
            "limit_shortfall": round(limit_shortfall, 2),
            "oop_adjust": round(oop_adjust, 2),
            "patient_portion_est": round(patient_portion, 2),
        }
        return delta_total, meta_parts

    # ========================================================================
    # BASE PRICE HELPERS
    # ========================================================================
    def _get_base_price_for_treatment(self, treatment, pricelist_id, qty, at_date):
        """Selaras dengan Bridge: product.pricelist → fallback base price treatment."""
        try:
            product = treatment.get_service_product()
            if pricelist_id and product and product.exists():
                header = self._resolve_clinic_pricelist(pricelist_id)
                pl = header.product_pricelist_id if header else self.env["product.pricelist"].browse(pricelist_id)
                if pl and pl.exists():
                    return float(pl._get_product_price(product, qty or 1.0, uom=product.uom_id, date=at_date))
            return float(treatment.get_default_price() or 0.0)
        except Exception as e:  # pragma: no cover
            _logger.debug("Insurance base price (treatment) fallback: %s", e)
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
            _logger.debug("Insurance base price (bundle) PRICELIST fallback: %s", e)

        if bundle.pricing_policy == "fixed":
            return float(bundle.base_price or 0.0)
        if bundle.pricing_policy == "sum":
            return float(bundle.computed_sum_price or 0.0)
        return float(bundle.base_price or 0.0)

    # ========================================================================
    # CONTEXT & META
    # ========================================================================
    def _parse_context(self, context_tags):
        """Parse context tags menjadi dict key-value:
        - 'preauth:yes|no', 'referral:yes|no'
        - 'deductible_remaining:XXX', 'annual_remaining:XXX', 'oop_remaining:XXX'
        - token umum: 'urgent', 'channel:booking', dsb.
        """
        ctx = {"raw_tags": list(context_tags)}
        for t in context_tags:
            if not isinstance(t, str):
                continue
            tl = t.strip()
            if ":" in tl:
                k, v = tl.split(":", 1)
                ctx[k.strip().lower()] = v.strip()
            else:
                ctx[tl.lower()] = True
        # ubah angka yang diketahui
        for num_key in ("deductible_remaining", "annual_remaining", "oop_remaining"):
            if num_key in ctx:
                try:
                    ctx[num_key] = float(ctx[num_key])
                except Exception:
                    pass
        return ctx

    def _context_or_member_number(self, ctx, member, field_candidates, default=None):
        """Ambil angka dari context terlebih dahulu; jika tidak ada, coba dari member (jika field ada)."""
        for key in field_candidates:
            if key in ctx and isinstance(ctx[key], (int, float)):
                return float(ctx[key])
        if member:
            for fname in field_candidates:
                val = self._get_any_number(member, [fname])
                if val not in (None, False):
                    return float(val)
        return default

    def _component_label(self, plan, member, rule):
        pname = getattr(plan, "name", "") if plan else ""
        rname = self._get_any(rule, ["name", "display_name"], default="")
        if pname and rname:
            return _("Insurance (%s) — %s") % (pname, rname)
        if pname:
            return _("Insurance (%s)") % pname
        return _("Insurance Coverage")

    def _compose_meta(self, member, plan, rule, scope, base_price, qty, ctx, parts):
        meta = {
            "scope": scope,
            "base_price": float(base_price or 0.0),
            "quantity": float(qty or 1.0),
            "rule_id": rule.id,
            "rule_model": rule._name,
            "plan_id": getattr(plan, "id", False) if plan else False,
            "member_id": getattr(member, "id", False) if member else False,
            "method": self._get_method(rule),
        }
        meta.update(parts or {})
        # sertakan referensi scoping/flags penting untuk audit
        for fname in ("treatment_id", "treatment_ids", "category_id", "tag_ids", "bundle_id",
                      "clinic_pricelist_id", "preauth_required", "referral_required", "waiting_period_days"):
            if self._has_field(rule, fname):
                try:
                    val = getattr(rule, fname)
                    meta[fname] = val.ids if hasattr(val, "ids") else (val.id if getattr(val, "id", False) else val)
                except Exception:
                    continue
        # salin indikator context krusial
        for k in ("preauth", "referral", "deductible_remaining", "annual_remaining", "oop_remaining"):
            if k in ctx:
                meta[f"context.{k}"] = ctx[k]
        return meta

    # ========================================================================
    # GENERIC HELPERS (validity, method, pricelist, models, fields)
    # ========================================================================
    def _get_method(self, rule):
        raw = self._get_any(rule, ["method", "coverage_method", "rule_type"], default="percent")
        raw = (raw or "percent").lower()
        if raw in ("fixed", "fixed_price", "price"):
            return "fixed_price"
        if raw in ("percent", "percentage", "perc"):
            return "percent"
        if raw in ("amount", "nominal", "coverage_amount"):
            return "amount"
        return "percent"

    def _record_is_active_by_date(self, rec, at_date):
        vf = self._get_any(rec, ["valid_from", "date_from", "start_date"])
        vt = self._get_any(rec, ["valid_to", "date_to", "end_date"])
        if not vf and not vt:
            return True
        ad = fields.Datetime.to_datetime(at_date) if at_date else fields.Datetime.now()
        ok_from = True if not vf else (ad >= fields.Datetime.to_datetime(vf))
        ok_to = True if not vt else (ad <= fields.Datetime.to_datetime(vt))
        return bool(ok_from and ok_to)

    def _context_tags_ok(self, rec, tags):
        req = self._get_any(rec, ["required_context_tags"])
        if req:
            reqs = {t.strip() for t in str(req).split(",") if t.strip()}
            if not set(tags or []).issuperset(reqs):
                return False
        exc = self._get_any(rec, ["excluded_context_tags"])
        if exc:
            exs = {t.strip() for t in str(exc).split(",") if t.strip()}
            if set(tags or []).intersection(exs):
                return False
        return True

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

