# -*- coding: utf-8 -*-
# ClinicOne - Treatment Catalog & Pricing
# File: models/engines/engine_surcharge.py
#
# Surcharge Engine (soft-coupled):
# - Menghitung surcharge berdasarkan berbagai dimensi:
#   therapist level, room/room-type, equipment/device, time window (prime time),
#   weekend/holiday, location/branch, urgency, context tags.
# - Scoping terhadap treatment/category/tag/bundle.
# - Metode perhitungan: percent (dari base), amount (flat), fixed_price (selisih dgn base).
# - Kebijakan grouping/stacking per-dimensi: exclusive group vs stacking bebas.
#
# Model yang DIHARAPKAN (jika modul terkait aktif, semua akses aman):
# - clinic.surcharge.rule (
#       name, active, company_id, scope('treatment'|'bundle'|'both'),
#       method('percent'|'amount'|'fixed_price'),
#       percent, amount, fixed_price,
#       min_qty, min_base_amount, max_surcharge_amount,
#       valid_from/valid_to (atau date_from/date_to/start_date/end_date),
#       channel, clinic_pricelist_id,
#       treatment_id/m2m, category_id, tag_ids, bundle_id,
#       therapist_level_id(s), room_type_id(s), equipment_id(s),
#       weekday_mask, time_start/time_end, prime_time(bool), weekend_only(bool), holiday_only(bool),
#       location_id/branch_id/company_id (opsional), urgency_only(bool),
#       required_context_tags/excluded_context_tags,
#       exclusive(bool), group_key(char), group_policy('sum'|'max'|'min'),
#       priority/sequence
#   )
#
# Catatan:
# - Jika struktur berbeda di addon surcharge kamu, engine ini tetap aman karena memakai
#   akses defensif (_get_any, _has_field, _get_model) dan daftar alias nama field.
#
from odoo import api, models, fields, _
import logging

_logger = logging.getLogger(__name__)


class ClinicEngineSurcharge(models.AbstractModel):
    _name = "clinic.engine_surcharge"
    _description = "ClinicOne Surcharge Engine (soft-coupled)"

    # ========================================================================
    # PUBLIC API — dipanggil Bridge
    # ========================================================================
    @api.model
    def compute_treatment_deltas(
        self, treatment, partner_id=None, pricelist_id=None,
        quantity=1.0, at_date=None, context_tags=None
    ):
        """Hitung delta surcharge untuk sebuah Treatment."""
        if not treatment:
            return []

        # Hormati flag "surcharge applicable" bila ada
        if hasattr(treatment, "surcharge_applicable") and not bool(treatment.surcharge_applicable):
            return []

        qty = quantity or 1.0
        ctx = self._parse_context(context_tags or [])
        at_dt = fields.Datetime.to_datetime(at_date) if at_date else fields.Datetime.now()

        # Base price (acuan percent / fixed_price delta)
        base_price = self._get_base_price_for_treatment(treatment, pricelist_id, qty, at_dt)

        # Kumpulkan candidate rules
        rules = self._get_applicable_rules(
            scope="treatment", company=treatment.company_id,
            pricelist_id=pricelist_id, at_date=at_dt, context=ctx
        )
        if not rules:
            return []

        # Filter rule by scoping ke object treatment dan dimensi surcharge
        matched = []
        for r in rules:
            if self._rule_matches_treatment(r, treatment, qty, ctx, at_dt):
                matched.append(r)
        if not matched:
            return []

        # Hitung delta per rule + batasan
        candidates = []
        for r in matched:
            delta = self._compute_rule_delta(r, base_price, qty)
            if delta is None:
                continue
            delta = self._apply_rule_limits(r, delta, base_price, qty)
            label = self._rule_label(r)
            prio = int(self._get_any(r, ["priority", "sequence"], default=410))  # 4xx = surcharge domain
            meta = self._rule_meta(r, scope="treatment", base_price=base_price, quantity=qty, context=ctx)
            candidates.append({"label": label, "amount": float(delta), "priority": prio, "meta": meta})

        if not candidates:
            return []

        # Terapkan grouping/stacking di dalam engine (agar tidak dobel dalam 1 dimensi)
        chosen = self._apply_grouping_and_stacking(candidates)

        return chosen

    @api.model
    def compute_bundle_deltas(
        self, bundle, partner_id=None, pricelist_id=None,
        quantity=1.0, at_date=None, context_tags=None
    ):
        """Hitung delta surcharge untuk Bundle."""
        if not bundle:
            return []

        # Untuk bundle, tidak ada flag "surcharge_applicable" standar; diasumsikan bisa.
        qty = quantity or 1.0
        ctx = self._parse_context(context_tags or [])
        at_dt = fields.Datetime.to_datetime(at_date) if at_date else fields.Datetime.now()

        base_price = self._get_base_price_for_bundle(bundle, pricelist_id, qty, at_dt)

        rules = self._get_applicable_rules(
            scope="bundle", company=bundle.company_id,
            pricelist_id=pricelist_id, at_date=at_dt, context=ctx
        )
        if not rules:
            return []

        matched = []
        for r in rules:
            if self._rule_matches_bundle(r, bundle, qty, ctx, at_dt):
                matched.append(r)
        if not matched:
            return []

        candidates = []
        for r in matched:
            delta = self._compute_rule_delta(r, base_price, qty)
            if delta is None:
                continue
            delta = self._apply_rule_limits(r, delta, base_price, qty)
            label = self._rule_label(r)
            prio = int(self._get_any(r, ["priority", "sequence"], default=410))
            meta = self._rule_meta(r, scope="bundle", base_price=base_price, quantity=qty, context=ctx)
            candidates.append({"label": label, "amount": float(delta), "priority": prio, "meta": meta})

        if not candidates:
            return []

        chosen = self._apply_grouping_and_stacking(candidates)
        return chosen

    # ========================================================================
    # RULE DISCOVERY
    # ========================================================================
    def _get_applicable_rules(self, scope, company, pricelist_id, at_date, context):
        """Ambil rules surcharge kandidat."""
        Rule = self._get_model("clinic.surcharge.rule")
        if not Rule:
            return []

        domain = [("active", "=", True)]
        if self._has_field(Rule, "scope"):
            # dukung 'both'
            domain += ["|", ("scope", "=", scope), ("scope", "=", "both")]
        if company and self._has_field(Rule, "company_id"):
            domain.append(("company_id", "in", [False, company.id]))

        rules = Rule.search(domain, limit=1000)
        if not rules:
            return []

        # Validitas tanggal
        rules = [r for r in rules if self._record_is_active_by_date(r, at_date)]

        # Channel / clinic pricelist
        header = self._resolve_clinic_pricelist(pricelist_id)
        channel = getattr(header, "channel", "all") if header else "all"

        filtered = []
        for r in rules:
            if self._has_field(r, "channel") and r.channel and r.channel not in ("all", "any", channel):
                continue
            if self._has_field(r, "clinic_pricelist_id") and r.clinic_pricelist_id:
                if not header or r.clinic_pricelist_id.id != header.id:
                    continue
            # Required/Excluded context tags
            if not self._context_tags_ok(r, context.get("raw_tags", [])):
                continue
            filtered.append(r)
        rules = filtered

        # Dimensi waktu (prime time/weekday/time window/weekend/holiday/urgency)
        rr = []
        for r in rules:
            if not self._time_ok(r, at_date, context):
                continue
            if not self._location_ok(r, context):
                continue
            rr.append(r)
        return rr

    # ========================================================================
    # MATCHING TERHADAP TREATMENT / BUNDLE
    # ========================================================================
    def _rule_matches_treatment(self, rule, treatment, qty, context, at_date):
        # Min qty / min base akan divalidasi juga di limits, tapi kita bisa filter awal
        if self._has_field(rule, "min_qty") and rule.min_qty and float(qty or 0.0) < float(rule.min_qty):
            return False

        # Scoping langsung ke treatment/kategori/tag
        # Treatment spesifik
        if self._has_field(rule, "treatment_id") and rule.treatment_id:
            if rule.treatment_id.id != treatment.id:
                return False

        # Banyak treatment
        if self._has_field(rule, "treatment_ids") and rule.treatment_ids:
            if treatment.id not in rule.treatment_ids.ids:
                return False

        # Kategori
        if self._has_field(rule, "category_id") and rule.category_id:
            cat = treatment.category_id
            if not cat:
                return False
            if not (cat.id == rule.category_id.id or str(rule.category_id.id) in (cat.parent_path or "")):
                return False

        # Tag
        if self._has_field(rule, "tag_ids") and rule.tag_ids:
            if not set(rule.tag_ids.ids).intersection(set(treatment.tag_ids.ids)):
                return False

        # Dimensi surcharge (therapist/room/equipment) via context
        if not self._dimension_ok(rule, context):
            return False

        return True

    def _rule_matches_bundle(self, rule, bundle, qty, context, at_date):
        if self._has_field(rule, "min_qty") and rule.min_qty and float(qty or 0.0) < float(rule.min_qty):
            return False

        # Bundle spesifik
        if self._has_field(rule, "bundle_id") and rule.bundle_id:
            if rule.bundle_id.id != bundle.id:
                return False

        # Tag line treatments (opsional)
        if self._has_field(rule, "tag_ids") and rule.tag_ids:
            ttags = set(bundle.line_ids.mapped("treatment_id.tag_ids").ids)
            if not set(rule.tag_ids.ids).intersection(ttags):
                return False

        if not self._dimension_ok(rule, context):
            return False

        return True

    # ========================================================================
    # HITUNG DELTA & LIMITS
    # ========================================================================
    def _compute_rule_delta(self, rule, base_price, qty):
        """Return delta float (positif = surcharge)."""
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
            return (float(base_price) * float(pct) / 100.0) * float(qty or 1.0)
        elif method == "amount":
            amt = self._get_any_number(rule, ["amount", "surcharge_amount"])
            if amt in (None, 0.0):
                return None
            return float(amt) * float(qty or 1.0)
        return None

    def _apply_rule_limits(self, rule, delta, base_price, qty):
        """Batasi delta sesuai rule: min_base_amount, max_surcharge_amount."""
        mba = self._get_any_number(rule, ["min_base_amount", "minimum_base_amount"])
        if mba not in (None, False) and float(base_price) < float(mba):
            return 0.0

        cap = self._get_any_number(rule, ["max_surcharge_amount", "maximum_surcharge_amount"])
        if cap not in (None, False) and float(cap) >= 0.0 and delta > 0.0:
            if float(delta) > float(cap) * float(qty or 1.0):
                return float(cap) * float(qty or 1.0)
        return delta

    # ========================================================================
    # GROUPING & STACKING
    # ========================================================================
    def _apply_grouping_and_stacking(self, candidates):
        """Kelola stacking per group:
        - Bila meta.exclusive=True → ambil 1 terbaik di group_key tsb.
        - Bila meta.group_policy in ('max','min','sum') → patuhi.
        - Default: sum (kembalikan semua kandidat, Bridge akan menjumlah).
        """
        if not candidates:
            return []

        # Kelompokkan berdasarkan group_key (jika tidak ada → '_default')
        groups = {}
        for c in candidates:
            gk = c.get("meta", {}).get("group_key") or "_default"
            groups.setdefault(gk, []).append(c)

        chosen = []
        for gk, items in groups.items():
            # Apakah ada rule exclusive dalam group?
            exclusives = [i for i in items if i.get("meta", {}).get("exclusive")]
            policy = (items[0].get("meta", {}) or {}).get("group_policy") if items else None
            policy = (policy or "sum").lower()

            if exclusives:
                # Ambil 1 'terbesar' dampaknya.
                # Untuk surcharge (umumnya positif), pilih delta terbesar.
                # Jika semuanya negatif (rare), pilih paling negatif (nilai minimum).
                pos = [x for x in exclusives if x["amount"] >= 0]
                if pos:
                    best = max(pos, key=lambda x: x["amount"])
                else:
                    best = min(exclusives, key=lambda x: x["amount"])
                chosen.append(best)
                continue

            if policy == "max":
                best = max(items, key=lambda x: x["amount"])
                chosen.append(best)
            elif policy == "min":
                best = min(items, key=lambda x: x["amount"])
                chosen.append(best)
            else:
                # sum: kembalikan semua (Bridge akan menjumlahkan)
                chosen.extend(items)

        return chosen

    # ========================================================================
    # DIMENSION & CONTEXT CHECKERS
    # ========================================================================
    def _dimension_ok(self, rule, context):
        """Cocokkan therapist/room/equipment/urgency/location if specified in rule."""
        # Therapist level
        ctx_level = context.get("therapist_level")
        if self._has_field(rule, "therapist_level_id") and rule.therapist_level_id:
            if not ctx_level or not self._ctx_match_single(ctx_level, rule.therapist_level_id):
                return False
        if self._has_field(rule, "therapist_level_ids") and rule.therapist_level_ids:
            if not ctx_level or not self._ctx_match_multi(ctx_level, rule.therapist_level_ids):
                return False

        # Room/Room type
        ctx_roomtype = context.get("room_type") or context.get("room")
        if self._has_field(rule, "room_type_id") and rule.room_type_id:
            if not ctx_roomtype or not self._ctx_match_single(ctx_roomtype, rule.room_type_id):
                return False
        if self._has_field(rule, "room_type_ids") and rule.room_type_ids:
            if not ctx_roomtype or not self._ctx_match_multi(ctx_roomtype, rule.room_type_ids):
                return False

        # Equipment/Device
        ctx_equipment = context.get("equipment") or context.get("device")
        if self._has_field(rule, "equipment_id") and rule.equipment_id:
            if not ctx_equipment or not self._ctx_match_single(ctx_equipment, rule.equipment_id):
                return False
        if self._has_field(rule, "equipment_ids") and rule.equipment_ids:
            if not ctx_equipment or not self._ctx_match_multi(ctx_equipment, rule.equipment_ids):
                return False

        # Urgency
        ctx_urgent = bool(context.get("urgent"))
        if self._has_field(rule, "urgency_only") and rule.urgency_only:
            if not ctx_urgent:
                return False

        # Location/Branch (opsional); cocokkan slug/id di context
        ctx_loc = context.get("location") or context.get("branch") or context.get("company")
        for fname in ("location_id", "branch_id", "company_id"):
            if self._has_field(rule, fname) and getattr(rule, fname):
                if not ctx_loc:
                    return False
                if not self._ctx_match_single(ctx_loc, getattr(rule, fname)):
                    return False

        return True

    def _time_ok(self, rule, at_date, context):
        """Periksa weekday/time window/prime_time/weekend/holiday sesuai rule."""
        # Weekday mask (1=Mon..7=Sun)
        mask = self._get_any(rule, ["weekday_mask"])
        if mask:
            try:
                weekdays = {int(x) for x in str(mask).split(",") if x}
                dow = (fields.Datetime.to_datetime(at_date) or fields.Datetime.now()).weekday() + 1
                if dow not in weekdays:
                    return False
            except Exception:
                pass

        # Time window
        if not self._time_window_ok(rule, at_date):
            return False

        # Prime time
        if self._get_any(rule, ["prime_time"], default=False):
            if not self._is_prime_time(rule, at_date, context):
                return False

        # Weekend only
        if self._get_any(rule, ["weekend_only"], default=False):
            dow = (fields.Datetime.to_datetime(at_date) or fields.Datetime.now()).weekday()
            if dow not in (5, 6):  # 5=Sat, 6=Sun
                return False

        # Holiday only
        if self._get_any(rule, ["holiday_only"], default=False):
            if not self._is_holiday(at_date, context):
                return False

        return True

    def _time_window_ok(self, rec, at_date):
        """Cek time_start/time_end (float jam atau 'HH:MM')."""
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

        tstart = self._get_any(rec, ["time_start", "start_time", "window_start"])
        tend = self._get_any(rec, ["time_end", "end_time", "window_end"])
        if not (tstart or tend):
            return True
        now = fields.Datetime.to_datetime(at_date) if at_date else fields.Datetime.now()
        minutes = now.hour * 60 + now.minute
        ms = _to_minutes(tstart)
        me = _to_minutes(tend)
        if ms is not None and minutes < ms:
            return False
        if me is not None and minutes > me:
            return False
        return True

    def _is_prime_time(self, rule, at_date, context):
        """Heuristik prime time: flag di context_tags (prime_time) ATAU time window 17:00–21:00 jika tidak spesifik."""
        tags = context.get("raw_tags", [])
        if any(str(t).lower() == "prime_time" for t in tags):
            return True
        now = fields.Datetime.to_datetime(at_date) if at_date else fields.Datetime.now()
        return 17 <= now.hour <= 21

    def _is_holiday(self, at_date, context):
        """Cek hari libur; dukung:
        - context tag 'holiday'
        - resource.calendar.leaves dengan holiday=True (jika tersedia)
        """
        tags = context.get("raw_tags", [])
        if any(str(t).lower() == "holiday" for t in tags):
            return True
        Leaves = self._get_model("resource.calendar.leaves")
        if Leaves and "holiday" in getattr(Leaves, "_fields", {}):
            ad = fields.Date.to_date(at_date) if at_date else fields.Date.context_today(self)
            recs = Leaves.search([("holiday", "=", True), ("date_from", "<=", ad), ("date_to", ">=", ad)], limit=1)
            return bool(recs)
        return False

    def _location_ok(self, rule, context):
        """Jika rule batasi lokasi/branch/company, cocokkan dengan context."""
        ctx_loc = context.get("location") or context.get("branch") or context.get("company")
        for fname in ("location_id", "branch_id", "company_id"):
            if self._has_field(rule, fname) and getattr(rule, fname):
                if not ctx_loc:
                    return False
                if not self._ctx_match_single(ctx_loc, getattr(rule, fname)):
                    return False
        return True

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
            _logger.debug("Surcharge base price (treatment) fallback: %s", e)
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
            _logger.debug("Surcharge base price (bundle) PRICELIST fallback: %s", e)

        if bundle.pricing_policy == "fixed":
            return float(bundle.base_price or 0.0)
        if bundle.pricing_policy == "sum":
            return float(bundle.computed_sum_price or 0.0)
        return float(bundle.base_price or 0.0)

    # ========================================================================
    # CONTEXT PARSER & MATCHERS
    # ========================================================================
    def _parse_context(self, context_tags):
        """Parse context_tags menjadi dict dimensi:
        - therapist_level:<slug|id>
        - room_type:<slug|id> | room:<slug|id>
        - equipment:<slug|id> | device:<slug|id>
        - location:<slug|id> | branch:<slug|id> | company:<slug|id>
        - prime_time, weekend, holiday, urgent
        """
        ctx = {"raw_tags": list(context_tags)}
        for t in context_tags:
            if not isinstance(t, str):
                continue
            tl = t.lower()
            if ":" in tl:
                k, v = tl.split(":", 1)
                v = v.strip()
                if k in ("therapist_level", "room_type", "room", "equipment", "device", "location", "branch", "company"):
                    ctx[k] = v
            else:
                if tl in ("prime_time", "weekend", "holiday", "urgent"):
                    ctx[tl] = True
        return ctx

    def _ctx_match_single(self, ctx_value, rec_or_m2o):
        """Cocokkan context slug/id ke record Many2one."""
        if not ctx_value or not rec_or_m2o:
            return False
        # Izinkan match by id atau name/code (case-insensitive)
        val = str(ctx_value).strip().lower()
        try:
            rid = getattr(rec_or_m2o, "id", False) or rec_or_m2o.id
            if str(rid) == val:
                return True
        except Exception:
            pass
        for fname in ("code", "name", "display_name"):
            if fname in getattr(rec_or_m2o, "_fields", {}):
                try:
                    if str(getattr(rec_or_m2o, fname)).strip().lower() == val:
                        return True
                except Exception:
                    continue
        return False

    def _ctx_match_multi(self, ctx_value, m2m):
        if not ctx_value or not m2m:
            return False
        val = str(ctx_value).strip().lower()
        # match by id
        try:
            if any(str(x.id) == val for x in m2m):
                return True
        except Exception:
            pass
        # match by code/name
        for rec in m2m:
            for fname in ("code", "name", "display_name"):
                if fname in getattr(rec, "_fields", {}):
                    try:
                        if str(getattr(rec, fname)).strip().lower() == val:
                            return True
                    except Exception:
                        continue
        return False

    # ========================================================================
    # LABEL, META, VALIDITY & UTILS
    # ========================================================================
    def _rule_label(self, rule):
        name = self._get_any(rule, ["name", "display_name"], default="Surcharge")
        return _("Surcharge — %s") % name

    def _rule_meta(self, rule, scope, base_price, quantity, context):
        meta = {
            "rule_id": rule.id,
            "rule_model": rule._name,
            "scope": scope,
            "method": self._get_method(rule),
            "base_price": float(base_price or 0.0),
            "quantity": float(quantity or 1.0),
            "exclusive": bool(self._get_any(rule, ["exclusive", "is_exclusive"], default=False)),
            "group_key": self._get_any(rule, ["group_key", "dimension_key", "exclusive_group"]) or self._infer_group_key(rule),
            "group_policy": (self._get_any(rule, ["group_policy"]) or "sum").lower(),
        }
        # Lampirkan referensi scoping/dimensi (untuk audit)
        for fname in (
            "treatment_id", "treatment_ids", "category_id", "tag_ids", "bundle_id",
            "therapist_level_id", "therapist_level_ids",
            "room_type_id", "room_type_ids",
            "equipment_id", "equipment_ids",
            "clinic_pricelist_id",
        ):
            if self._has_field(rule, fname):
                try:
                    val = getattr(rule, fname)
                    meta[fname] = val.ids if hasattr(val, "ids") else (val.id if getattr(val, "id", False) else val)
                except Exception:
                    continue
        # salin context ringkas untuk jejak
        for k in ("therapist_level", "room_type", "room", "equipment", "device", "location", "branch", "company", "urgent"):
            if k in context:
                meta[f"context.{k}"] = context[k]
        return meta

    def _infer_group_key(self, rule):
        """Tebak group key dari dimensi yang diisi pada rule."""
        for gk in (
            ("therapist", ("therapist_level_id", "therapist_level_ids")),
            ("room", ("room_type_id", "room_type_ids")),
            ("equipment", ("equipment_id", "equipment_ids")),
            ("time", ("weekday_mask", "time_start", "time_end", "prime_time")),
            ("holiday", ("holiday_only",)),
            ("location", ("location_id", "branch_id", "company_id")),
        ):
            if any(self._has_field(rule, f) and getattr(rule, f) for f in gk[1]):
                return gk[0]
        return "_default"

    def _get_method(self, rule):
        raw = self._get_any(rule, ["method", "rule_type", "benefit_type"], default="percent")
        raw = (raw or "percent").lower()
        if raw in ("fixed", "fixed_price", "price"):
            return "fixed_price"
        if raw in ("percent", "percentage", "perc"):
            return "percent"
        if raw in ("amount", "nominal", "surcharge_amount"):
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

