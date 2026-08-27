# -*- coding: utf-8 -*-
# ClinicOne - Treatment Catalog & Pricing
# File: models/engines/engine_membership.py
#
# Engine Membership (soft-coupled):
# - Menentukan tier membership pelanggan pada tanggal tertentu
# - Mengambil & mengevaluasi aturan benefit membership yang relevan
# - Menghitung delta harga: fixed price / % discount / fixed discount
# - Menghormati kebijakan stacking (exclusive vs allow_stack) dari res.company
# - Mendukung scoping rule terhadap treatment/category/tag atau bundle
#
# Model yang DIHARAPKAN (jika modul membership aktif):
# - clinic.membership.enrollment   (partner_id, tier_id, date_from/date_to, state)
# - clinic.membership.tier         (name, priority, etc.)
# - clinic.membership.benefit.rule (tier_id, scope='treatment'|'bundle', selection fields untuk scoping,
#                                   method: fixed_price|percent|amount, percent|amount|fixed_price,
#                                   min_qty, valid_from/valid_to OR date_start/date_end,
#                                   channel, tag filters, priority, active)
#
# Catatan:
# - Seluruh akses ke model/field dilakukan aman (cek registry/fields dulu) sehingga tidak memaksa dependensi.
# - Jika model/field tidak ada → rule dianggap tidak ada/di-skip dengan aman.

from odoo import api, models, fields, _
import logging

_logger = logging.getLogger(__name__)


class ClinicEngineMembership(models.AbstractModel):
    _name = "clinic.engine_membership"
    _description = "ClinicOne Membership Pricing Engine (soft-coupled)"

    # ========================================================================
    # PUBLIC API dipanggil Bridge
    # ========================================================================
    @api.model
    def compute_treatment_deltas(
        self, treatment, partner_id=None, pricelist_id=None,
        quantity=1.0, at_date=None, context_tags=None
    ):
        """Hitung delta membership untuk satu treatment.

        :param treatment: record clinic.treatment.catalog
        :param partner_id: int | None (customer)
        :param pricelist_id: id clinic.treatment.pricelist ATAU product.pricelist
        :param quantity: float
        :param at_date: datetime | None
        :param context_tags: list[str] | None
        :return: list[dict] komponen delta
        """
        env = self.env
        context_tags = context_tags or []
        quantity = quantity or 1.0

        if not partner_id:
            return []  # tanpa partner → tidak ada membership

        # 1) Temukan enrollment & tier aktif
        enrollment, tier = self._get_active_enrollment_and_tier(partner_id, at_date)
        if not tier:
            return []

        # 2) Ambil rules membership yang relevan (scope: treatment)
        rules = self._get_applicable_rules(
            scope="treatment", tier=tier, company=treatment.company_id,
            pricelist_id=pricelist_id, at_date=at_date, context_tags=context_tags
        )
        if not rules:
            return []

        # 3) Hitung base acuan (sebaiknya sama dengan base di Bridge)
        base_price = self._get_base_price_for_treatment(treatment, pricelist_id, quantity, at_date)
        if base_price is None:
            base_price = float(treatment.get_default_price() or 0.0)

        # 4) Filter rules by scoping (treatment/category/tag/qty/channel/tag kontekstual)
        scoped_rules = []
        for rule in rules:
            if self._rule_matches_treatment(rule, treatment, quantity, context_tags):
                scoped_rules.append(rule)
        if not scoped_rules:
            return []

        # 5) Buat kandidat delta dari setiap rule yang match
        candidates = []
        for r in scoped_rules:
            delta = self._compute_rule_delta_for_treatment(r, base_price, quantity)
            if delta is None:
                continue
            label = self._rule_label(r, tier)
            priority = self._get_field(r, "priority", default=210)  # default 210 (membership domain)
            candidates.append({
                "label": label,
                "amount": float(delta),
                "priority": int(priority),
                "meta": self._rule_meta(r, enrollment, tier, {
                    "base_price": base_price,
                    "quantity": quantity,
                    "scope": "treatment",
                }),
            })

        if not candidates:
            return []

        # 6) Terapkan kebijakan stacking dari res.company
        policy = self._get_company_stacking_policy(treatment.company_id)
        chosen = self._apply_stacking_policy(candidates, base_price, policy)

        return chosen

    @api.model
    def compute_bundle_deltas(
        self, bundle, partner_id=None, pricelist_id=None,
        quantity=1.0, at_date=None, context_tags=None
    ):
        """Hitung delta membership untuk bundle."""
        env = self.env
        context_tags = context_tags or []
        quantity = quantity or 1.0

        if not partner_id:
            return []

        enrollment, tier = self._get_active_enrollment_and_tier(partner_id, at_date)
        if not tier:
            return []

        rules = self._get_applicable_rules(
            scope="bundle", tier=tier, company=bundle.company_id,
            pricelist_id=pricelist_id, at_date=at_date, context_tags=context_tags
        )
        if not rules:
            return []

        base_price = self._get_base_price_for_bundle(bundle, pricelist_id, quantity, at_date)
        if base_price is None:
            # fallback ke kebijakan lokal bundle
            if bundle.pricing_policy == "fixed":
                base_price = float(bundle.base_price or 0.0)
            elif bundle.pricing_policy == "sum":
                base_price = float(bundle.computed_sum_price or 0.0)
            else:
                base_price = float(bundle.base_price or 0.0)

        scoped_rules = []
        for rule in rules:
            if self._rule_matches_bundle(rule, bundle, quantity, context_tags):
                scoped_rules.append(rule)
        if not scoped_rules:
            return []

        candidates = []
        for r in scoped_rules:
            delta = self._compute_rule_delta_for_bundle(r, base_price, quantity)
            if delta is None:
                continue
            label = self._rule_label(r, tier)
            priority = self._get_field(r, "priority", default=210)
            candidates.append({
                "label": label,
                "amount": float(delta),
                "priority": int(priority),
                "meta": self._rule_meta(r, enrollment, tier, {
                    "base_price": base_price,
                    "quantity": quantity,
                    "scope": "bundle",
                }),
            })

        if not candidates:
            return []

        policy = self._get_company_stacking_policy(bundle.company_id)
        chosen = self._apply_stacking_policy(candidates, base_price, policy)

        return chosen

    # ========================================================================
    # MEMBACA ENROLLMENT & TIER
    # ========================================================================
    def _get_active_enrollment_and_tier(self, partner_id, at_date=None):
        """Cari enrollment & tier aktif untuk partner pada at_date.
        Return (enrollment_rec or None, tier_rec or None).
        """
        env = self.env
        at_date = fields.Datetime.to_datetime(at_date) if at_date else fields.Datetime.now()
        Enrollment = self._get_model("clinic.membership.enrollment")
        Tier = self._get_model("clinic.membership.tier")

        if not Enrollment or not Tier:
            # Fallback: coba baca tier langsung dari partner (jika ada field)
            Partner = env["res.partner"].browse(partner_id)
            if self._has_field(Partner, "clinic_membership_tier_id") and Partner.clinic_membership_tier_id:
                return None, Partner.clinic_membership_tier_id
            return None, None

        domain = [("partner_id", "=", partner_id)]
        # Validity fields are not guaranteed; filter python-side if missing.
        enrolls = Enrollment.search(domain, limit=50)
        active = None
        for e in enrolls:
            if self._record_is_active_by_date(e, at_date) and self._enrollment_is_active_state(e):
                active = e
                break
        if not active:
            return None, None
        tier = getattr(active, "tier_id", False) if self._has_field(active, "tier_id") else False
        return active, tier if tier and tier.exists() else None

    def _record_is_active_by_date(self, rec, at_date):
        """Periksa valid_from/valid_to atau date_start/date_end bila ada."""
        if self._has_field(rec, "valid_from"):
            vf = rec.valid_from
        elif self._has_field(rec, "date_from"):
            vf = rec.date_from
        elif self._has_field(rec, "start_date"):
            vf = rec.start_date
        else:
            vf = None

        if self._has_field(rec, "valid_to"):
            vt = rec.valid_to
        elif self._has_field(rec, "date_to"):
            vt = rec.date_to
        elif self._has_field(rec, "end_date"):
            vt = rec.end_date
        else:
            vt = None

        # If both missing → dianggap aktif sepanjang masa
        if not vf and not vt:
            return True
        # Normalize types
        ad = fields.Datetime.to_datetime(at_date) if at_date else fields.Datetime.now()
        ok_from = True if not vf else (fields.Datetime.to_datetime(ad) >= fields.Datetime.to_datetime(vf))
        ok_to = True if not vt else (fields.Datetime.to_datetime(ad) <= fields.Datetime.to_datetime(vt))
        return bool(ok_from and ok_to)

    def _enrollment_is_active_state(self, rec):
        """Cek state aktif jika field ada (mis. state in ['active','paid'])."""
        if self._has_field(rec, "state"):
            return rec.state in ("active", "paid", "running", "open")
        return True

    # ========================================================================
    # AMBIL RULES YANG RELEVAN
    # ========================================================================
    def _get_applicable_rules(self, scope, tier, company, pricelist_id, at_date, context_tags):
        """Ambil candidate rules membership untuk scope tertentu."""
        Rule = self._get_model("clinic.membership.benefit.rule")
        if not Rule:
            return []

        domain = [("active", "=", True)]
        # Company
        if self._has_field(Rule, "company_id") and company:
            domain.append(("company_id", "in", [False, company.id]))
        # Scope
        if self._has_field(Rule, "scope"):
            domain.append(("scope", "=", scope))
        # Tier
        if self._has_field(Rule, "tier_id") and tier:
            domain.append(("tier_id", "=", tier.id))

        # Filter awal; detail validitas/channel/pricelist/tag akan di-filter Python-side
        rules = Rule.search(domain, limit=500)

        # Validitas tanggal
        rules = [r for r in rules if self._record_is_active_by_date(r, at_date)]

        # Channel (opsional)
        channel_ok = []
        for r in rules:
            if not self._has_field(r, "channel") or not r.channel or r.channel in ("all", "any"):
                channel_ok.append(r)
                continue
            # Jika rule mengharuskan channel spesifik, coba baca dari pricelist header
            pl_header = self._resolve_clinic_pricelist(pricelist_id)
            pl_channel = getattr(pl_header, "channel", "all") if pl_header else "all"
            if r.channel == pl_channel:
                channel_ok.append(r)
        rules = channel_ok

        # Pricelist scoping (opsional): beberapa organisasi hanya ingin rule berlaku pada pricelist tertentu
        if pricelist_id and any(self._has_field(r, "clinic_pricelist_id") for r in rules):
            filtered = []
            for r in rules:
                if not self._has_field(r, "clinic_pricelist_id") or not r.clinic_pricelist_id:
                    filtered.append(r)
                else:
                    # dukung dua tipe id: clinic.treatment.pricelist atau product.pricelist → kita cocokkan clinic header saja
                    pl_header = self._resolve_clinic_pricelist(pricelist_id)
                    if pl_header and r.clinic_pricelist_id.id == pl_header.id:
                        filtered.append(r)
            rules = filtered

        # Context tags (opsional): bila rule punya required_tags / excluded_tags
        req_ok = []
        for r in rules:
            if self._has_field(r, "required_context_tags") and r.required_context_tags:
                reqs = set((r.required_context_tags or "").split(","))
                if not set(context_tags or []).issuperset({t.strip() for t in reqs if t.strip()}):
                    continue
            if self._has_field(r, "excluded_context_tags") and r.excluded_context_tags:
                exs = set((r.excluded_context_tags or "").split(","))
                if set(context_tags or []).intersection({t.strip() for t in exs if t.strip()}):
                    continue
            req_ok.append(r)
        return req_ok

    def _resolve_clinic_pricelist(self, pricelist_id):
        """Terima ID clinic.treatment.pricelist ATAU product.pricelist → kembalikan clinic header jika ada."""
        env = self.env
        if not pricelist_id:
            return None
        header = None
        PLClinic = self._get_model("clinic.treatment.pricelist")
        if PLClinic and PLClinic.browse(pricelist_id).exists():
            header = PLClinic.browse(pricelist_id)
        else:
            PL = self._get_model("product.pricelist")
            if PL and PL.browse(pricelist_id).exists():
                pl = PL.browse(pricelist_id)
                # backlink field (lihat treatment_pricelist.py)
                if self._has_field(pl, "clinic_pricelist_id") and pl.clinic_pricelist_id:
                    header = pl.clinic_pricelist_id
        return header

    # ========================================================================
    # BASE PRICE (ACUAN DISKON)
    # ========================================================================
    def _get_base_price_for_treatment(self, treatment, pricelist_id, qty, at_date):
        """Samakan metode dengan Bridge: PRICELIST → fallback default price."""
        try:
            product = treatment.get_service_product()
            if pricelist_id and product and product.exists():
                pl_header = self._resolve_clinic_pricelist(pricelist_id)
                pl = pl_header.product_pricelist_id if pl_header else self.env["product.pricelist"].browse(pricelist_id)
                if pl and pl.exists():
                    return float(pl._get_product_price(product, qty or 1.0, uom=product.uom_id, date=at_date))
            return float(treatment.get_default_price() or 0.0)
        except Exception as e:  # pragma: no cover
            _logger.debug("Membership base price (treatment) fallback: %s", e)
            return float(treatment.get_default_price() or 0.0)

    def _get_base_price_for_bundle(self, bundle, pricelist_id, qty, at_date):
        """Untuk bundle, coba product.pricelist. Jika tidak, gunakan kebijakan bundle."""
        try:
            product = bundle.get_service_product()
            if pricelist_id and product and product.exists():
                pl_header = self._resolve_clinic_pricelist(pricelist_id)
                pl = pl_header.product_pricelist_id if pl_header else self.env["product.pricelist"].browse(pricelist_id)
                if pl and pl.exists():
                    return float(pl._get_product_price(product, qty or 1.0, uom=product.uom_id, date=at_date))
        except Exception as e:  # pragma: no cover
            _logger.debug("Membership base price (bundle) PRICELIST fallback: %s", e)

        # fallback ke kebijakan lokal
        if bundle.pricing_policy == "fixed":
            return float(bundle.base_price or 0.0)
        if bundle.pricing_policy == "sum":
            return float(bundle.computed_sum_price or 0.0)
        return float(bundle.base_price or 0.0)

    # ========================================================================
    # SCOPING RULE TERHADAP TREATMENT / BUNDLE
    # ========================================================================
    def _rule_matches_treatment(self, rule, treatment, qty, context_tags):
        """Evaluasi apakah rule berlaku untuk treatment ini."""
        # Min qty
        if self._has_field(rule, "min_qty") and rule.min_qty and float(qty or 0.0) < float(rule.min_qty):
            return False

        # Treatment langsung
        if self._has_field(rule, "treatment_id") and rule.treatment_id:
            return rule.treatment_id.id == treatment.id

        # Banyak treatment (opsional)
        if self._has_field(rule, "treatment_ids") and rule.treatment_ids:
            if treatment.id in rule.treatment_ids.ids:
                return True

        # Kategori
        if self._has_field(rule, "category_id") and rule.category_id:
            if treatment.category_id and (treatment.category_id.id == rule.category_id.id or
                                          treatment.category_id.id in rule.category_id.child_of(rule.category_id.id).ids):
                return True
            # Jika _child_of_ tidak tersedia di rule.category_id, fallback manual:
            if treatment.category_id and hasattr(treatment.category_id, "parent_path"):
                # child_of domain sebenarnya ditangani ORM; fallback: cek parent_path
                if str(rule.category_id.id) in (treatment.category_id.parent_path or ""):
                    return True

        # Tag inklusif
        if self._has_field(rule, "tag_ids") and rule.tag_ids:
            if set(rule.tag_ids.ids).intersection(set(treatment.tag_ids.ids)):
                return True

        # Jika rule tidak menspesifikkan apapun di atas, anggap rule global untuk scope ini
        none_specified = True
        for fname in ("treatment_id", "treatment_ids", "category_id", "tag_ids"):
            if self._has_field(rule, fname) and getattr(rule, fname):
                none_specified = False
        return none_specified

    def _rule_matches_bundle(self, rule, bundle, qty, context_tags):
        """Evaluasi rule untuk bundle."""
        if self._has_field(rule, "min_qty") and rule.min_qty and float(qty or 0.0) < float(rule.min_qty):
            return False

        # Bundle spesifik
        if self._has_field(rule, "bundle_id") and rule.bundle_id:
            return rule.bundle_id.id == bundle.id

        # Tag atau kategori pada bundle (opsional, jika tersedia)
        if self._has_field(rule, "tag_ids") and rule.tag_ids:
            # Bundle tidak punya tag langsung; bisa saja rule ingin tag pada line treatments
            # Implementasi sederhana: jika salah satu treatment pada bundle memiliki tag → match.
            line_treatments = bundle.line_ids.mapped("treatment_id")
            if set(rule.tag_ids.ids).intersection(set(line_treatments.mapped("tag_ids").ids)):
                return True

        # Rule global bila tak ada spesifikasi
        none_specified = True
        for fname in ("bundle_id", "tag_ids"):
            if self._has_field(rule, fname) and getattr(rule, fname):
                none_specified = False
        return none_specified

    # ========================================================================
    # HITUNG DELTA DARI RULE
    # ========================================================================
    def _compute_rule_delta_for_treatment(self, rule, base_price, qty):
        """Kembalikan delta (float) atau None bila rule ambigu/tidak valid.

        Metode yang didukung (nama field fleksibel):
          - fixed price   → fields: fixed_price / fixed / price
          - percent disc  → fields: percent / percentage
          - fixed disc    → fields: amount / fixed_discount
        """
        method = self._get_method(rule)
        if method == "fixed_price":
            fp = self._get_number(rule, ["fixed_price", "fixed", "price"])
            if fp is None:
                return None
            # delta: selisih fixed price vs base (per unit × qty)
            return (float(fp) - float(base_price)) * float(qty or 1.0)
        elif method == "percent":
            pct = self._get_number(rule, ["percent", "percentage"])
            if pct in (None, 0.0):
                return None
            # diskon → negatif
            return - (float(base_price) * float(pct) / 100.0) * float(qty or 1.0)
        elif method == "amount":
            amt = self._get_number(rule, ["amount", "fixed_discount", "discount_amount"])
            if amt in (None, 0.0):
                return None
            # diskon flat per unit
            return - float(amt) * float(qty or 1.0)
        return None

    def _compute_rule_delta_for_bundle(self, rule, base_price, qty):
        method = self._get_method(rule)
        if method == "fixed_price":
            fp = self._get_number(rule, ["fixed_price", "fixed", "price"])
            if fp is None:
                return None
            return (float(fp) - float(base_price)) * float(qty or 1.0)
        elif method == "percent":
            pct = self._get_number(rule, ["percent", "percentage"])
            if pct in (None, 0.0):
                return None
            return - (float(base_price) * float(pct) / 100.0) * float(qty or 1.0)
        elif method == "amount":
            amt = self._get_number(rule, ["amount", "fixed_discount", "discount_amount"])
            if amt in (None, 0.0):
                return None
            return - float(amt) * float(qty or 1.0)
        return None

    def _get_method(self, rule):
        """Normalisasi nama metode rule."""
        raw = self._get_field(rule, "benefit_type",
                              default=self._get_field(rule, "method",
                              default=self._get_field(rule, "rule_type", default="percent")))
        raw = (raw or "percent").lower()
        if raw in ("fixed", "fixed_price", "price"):
            return "fixed_price"
        if raw in ("percent", "percentage", "perc"):
            return "percent"
        if raw in ("amount", "nominal", "fixed_discount"):
            return "amount"
        return "percent"

    # ========================================================================
    # STACKING POLICY
    # ========================================================================
    def _apply_stacking_policy(self, candidates, base_price, policy):
        """Terapkan kebijakan stacking.
        - exclusive  : pilih kandidat dengan hasil akhir termurah (base + delta)
        - allow_stack: kombinasikan amount & percent; abaikan selain 1 fixed_price (pilih paling menguntungkan)
        """
        if not candidates:
            return []

        if policy == "exclusive":
            # Pilih 1 rule yang memberi (base + delta) terendah
            best = None
            best_final = None
            for c in candidates:
                final = float(base_price) + float(c["amount"])
                if best is None or final < best_final:
                    best, best_final = c, final
            return [best]

        # allow_stack
        fixed = [c for c in candidates if "fixed" in c["label"].lower()]  # heuristik label
        # Lebih robust: cek method dari meta jika tersedia
        if not fixed:
            # Tidak ada fixed price → jumlahkan semua
            return self._stack_all(candidates)
        # Jika ada lebih dari satu fixed → pilih fixed yang paling menguntungkan (final terendah), gabungkan dengan DELTA POSITIF saja? umumnya fixed menggantikan base → tak digabung
        best_fixed = None
        best_final = None
        for c in candidates:
            # coba deteksi dari meta
            method = (c.get("meta", {}).get("method") or "").lower()
            is_fixed = (method == "fixed_price") or ("fixed" in c["label"].lower())
            if not is_fixed:
                continue
            final = float(base_price) + float(c["amount"])
            if best_fixed is None or final < best_final:
                best_fixed, best_final = c, final
        return [best_fixed] if best_fixed else self._stack_all(candidates)

    def _stack_all(self, items):
        """Gabungkan semua delta → return list yang sama; Bridge yang menjumlahkan."""
        # Bisa juga di-normalisasi: gabungkan percent/amount jadi dua komponen, tapi demi traceability,
        # kita kembalikan per-rule agar audit jelas.
        return items

    def _get_company_stacking_policy(self, company):
        """Baca policy dari res.company; default 'exclusive'."""
        try:
            return company.clinic_membership_stacking or "exclusive"
        except Exception:
            return "exclusive"

    # ========================================================================
    # UTILITAS MODEL/FIELD/SAFE ACCESS
    # ========================================================================
    def _get_model(self, model_name):
        try:
            if self.env.registry.get(model_name):
                return self.env[model_name]
        except Exception:
            return None
        return None

    def _has_field(self, rec_or_model, field_name):
        try:
            model = rec_or_model
            if not hasattr(rec_or_model, "_fields"):
                # it's a recordset or model? both have _fields
                model = rec_or_model
            return field_name in getattr(model, "_fields", {})
        except Exception:
            return False

    def _get_field(self, rec, field_name, default=None):
        try:
            if self._has_field(rec, field_name):
                return getattr(rec, field_name)
        except Exception:
            pass
        return default

    def _get_number(self, rec, candidates):
        """Ambil angka dari salah satu nama field dalam list candidates."""
        for fname in candidates:
            val = self._get_field(rec, fname, default=None)
            if val not in (None, False):
                try:
                    return float(val)
                except Exception:
                    continue
        return None

    # ========================================================================
    # LABEL & META KOMBINASI
    # ========================================================================
    def _rule_label(self, rule, tier):
        name = self._get_field(rule, "name", default="")
        tier_name = getattr(tier, "name", "") if tier else ""
        if name and tier_name:
            return _("Membership (%s) — %s") % (tier_name, name)
        if tier_name:
            return _("Membership (%s)") % tier_name
        return _("Membership Benefit")

    def _rule_meta(self, rule, enrollment, tier, extra=None):
        meta = {
            "rule_id": rule.id,
            "rule_model": rule._name,
            "tier_id": getattr(tier, "id", False) if tier else False,
            "enrollment_id": getattr(enrollment, "id", False) if enrollment else False,
            "method": self._get_method(rule),
        }
        meta.update(extra or {})
        # Tambahkan jejak scoping bila ada
        for fname in ("treatment_id", "treatment_ids", "category_id", "tag_ids", "bundle_id", "min_qty"):
            if self._has_field(rule, fname):
                try:
                    val = getattr(rule, fname)
                    meta[fname] = val.ids if hasattr(val, "ids") else (val.id if getattr(val, "id", False) else val)
                except Exception:
                    continue
        return meta

