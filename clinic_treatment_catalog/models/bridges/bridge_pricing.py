# -*- coding: utf-8 -*-
# ClinicOne - Treatment Catalog & Pricing
# File: models/bridges/bridge_pricing.py
#
# Abstract Bridge (clinic.pricelist.bridge) yang menggabungkan:
# - Base price (Odoo product.pricelist → fallback base price)
# - Engine membership → promotions → surcharge → insurance (berurutan)
# - Minimum guardrail + rounding policy → compose result standar
#
# Integrasi:
# - models/engines/engine_membership.py   (clinic.engine_membership)
# - models/engines/engine_promotions.py   (clinic.engine_promotions)
# - models/engines/engine_surcharge.py    (clinic.engine_surcharge)
# - models/engines/engine_insurance.py    (clinic.engine_insurance)
#
# Kebijakan:
# - res.company: clinic_enable_bridge_pricing, clinic_rounding_policy, etc.
# - clinic.treatment.pricelist: apply_membership/promotions/surcharge/insurance, channel, etc.
#
from odoo import api, models, fields, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ClinicPricelistBridge(models.AbstractModel):
    _name = "clinic.pricelist.bridge"
    _description = "ClinicOne Pricelist Bridge (Treatment/Bundle Pricing Engine)"

    # ========================================================================
    # PUBLIC API
    # ========================================================================
    @api.model
    def compute_treatment_price(
        self,
        treatment,
        partner_id=None,
        pricelist_id=None,
        quantity=1.0,
        booking_dt=None,
        context_tags=None,
        company_id=None,
        debug=False,
    ):
        """Hitung harga final untuk 1 Treatment (non-procedural service).

        Return dict:
          {
            'price': float,
            'currency_id': int,
            'components': [ {label, amount, kind, applied, priority, meta}, ... ],
            'explanation': str,
            'breakdown_text': str,
            'meta': {...}
          }
        """
        self._assert_single(treatment, "clinic.treatment.catalog")
        qty = self._ensure_float(quantity)
        ctx_tags = context_tags or []
        at_dt = fields.Datetime.to_datetime(booking_dt) if booking_dt else fields.Datetime.now()

        company = self._resolve_company(company_id, getattr(treatment, "company_id", False))
        header, pl_odoo = self._resolve_pricelist(pricelist_id, partner_id, company)
        engines_order = self._engine_order(company, header)
        engines_apply = self._engine_flags(header, company)

        # Base price
        currency = getattr(treatment, "currency_id", False) or (company and company.currency_id)
        price, base_label, base_kind = self._base_price_treatment(treatment, pl_odoo, qty, at_dt)
        components = [treatment._price_component(base_label, price, kind=base_kind, priority=100)]
        explanation = []
        meta = {
            "object": "treatment",
            "treatment_id": treatment.id,
            "company_id": company.id if company else False,
            "partner_id": partner_id or False,
            "qty": qty,
            "used_pricelist_header_id": header.id if header else False,
            "used_product_pricelist_id": pl_odoo.id if pl_odoo else False,
            "engine_order": engines_order,
            "engine_apply": engines_apply,
            "context_tags": list(ctx_tags),
            "timestamp": fields.Datetime.now(),
        }

        # Jika bridge dimatikan di company → langsung kembalikan base
        if not self._is_bridge_enabled(company):
            res = treatment._compose_price_result(
                price=price, currency=currency, components=components,
                explanation=_("Bridge disabled. Using base price."),
                meta=meta,
            )
            return res

        # ENGINE PIPELINE
        price_before = price
        for engine_key in engines_order:
            if not engines_apply.get(engine_key, True):
                continue
            engine = self._get_engine(engine_key)
            if not engine:
                explanation.append(_("%s engine unavailable") % engine_key.replace("engine_", "").title())
                continue

            try:
                if engine_key == "engine_membership":
                    deltas = engine.compute_treatment_deltas(
                        treatment=treatment,
                        partner_id=partner_id,
                        pricelist_id=(header.id if header else (pl_odoo.id if pl_odoo else None)),
                        quantity=qty,
                        at_date=at_dt,
                        context_tags=ctx_tags,
                    )
                elif engine_key == "engine_promotions":
                    deltas = engine.compute_treatment_deltas(
                        treatment=treatment,
                        partner_id=partner_id,
                        pricelist_id=(header.id if header else (pl_odoo.id if pl_odoo else None)),
                        quantity=qty,
                        at_date=at_dt,
                        context_tags=ctx_tags,
                    )
                elif engine_key == "engine_surcharge":
                    deltas = engine.compute_treatment_deltas(
                        treatment=treatment,
                        partner_id=partner_id,
                        pricelist_id=(header.id if header else (pl_odoo.id if pl_odoo else None)),
                        quantity=qty,
                        at_date=at_dt,
                        context_tags=ctx_tags,
                    )
                elif engine_key == "engine_insurance":
                    deltas = engine.compute_treatment_deltas(
                        treatment=treatment,
                        partner_id=partner_id,
                        pricelist_id=(header.id if header else (pl_odoo.id if pl_odoo else None)),
                        quantity=qty,
                        at_date=at_dt,
                        context_tags=ctx_tags,
                    )
                else:
                    deltas = []
            except Exception as e:  # pragma: no cover
                _logger.debug("Engine %s failed: %s", engine_key, e)
                deltas = []
                explanation.append(_("%s engine error") % engine_key.replace("engine_", "").title())

            # tambahkan delta ke components & price
            for d in deltas or []:
                amount = self._ensure_float(d.get("amount"))
                label = d.get("label") or engine_key.replace("engine_", "").title()
                prio = int(d.get("priority", self._default_priority_for_engine(engine_key)))
                meta_d = d.get("meta") or {}
                kind = self._kind_for_engine(engine_key)
                components.append(treatment._price_component(label, amount, kind=kind, priority=prio, meta=meta_d))
                price += amount

        # Minimum + Rounding
        get_min = getattr(treatment, "get_minimum_price", None)
        minimum = get_min() if callable(get_min) else 0.0
        price, components = treatment._apply_minimum(price, minimum, currency, components)
        price = treatment._round_price(price, currency)

        # Compose
        exp_text = "; ".join(explanation) if explanation else _("Computed by Clinic Pricelist Bridge.")
        res = treatment._compose_price_result(price=price, currency=currency, components=components,
                                              explanation=exp_text, meta=meta)

        if debug:
            _logger.info("BRIDGE DEBUG (treatment %s): base=%s → final=%s; comps=%s",
                         treatment.id, price_before, price, [(c["kind"], c["amount"]) for c in components])
        return res

    @api.model
    def compute_bundle_price(
        self,
        bundle,
        partner_id=None,
        pricelist_id=None,
        quantity=1.0,
        sale_dt=None,
        context_tags=None,
        company_id=None,
        debug=False,
    ):
        """Hitung harga final untuk 1 Bundle (paket treatment)."""
        self._assert_single(bundle, "clinic.treatment.bundle")
        qty = self._ensure_float(quantity)
        ctx_tags = context_tags or []
        at_dt = fields.Datetime.to_datetime(sale_dt) if sale_dt else fields.Datetime.now()

        company = self._resolve_company(company_id, getattr(bundle, "company_id", False))
        header, pl_odoo = self._resolve_pricelist(pricelist_id, partner_id, company)
        engines_order = self._engine_order(company, header)
        engines_apply = self._engine_flags(header, company)

        # Base price bundle (fixed/sum/formula)
        base_price, base_label = self._base_price_bundle(bundle, pl_odoo, qty, at_dt)
        currency = getattr(bundle, "currency_id", False) or (company and company.currency_id)
        components = [bundle._price_component(base_label, base_price, kind="base", priority=100)]
        explanation = []
        meta = {
            "object": "bundle",
            "bundle_id": bundle.id,
            "company_id": company.id if company else False,
            "partner_id": partner_id or False,
            "qty": qty,
            "used_pricelist_header_id": header.id if header else False,
            "used_product_pricelist_id": pl_odoo.id if pl_odoo else False,
            "engine_order": engines_order,
            "engine_apply": engines_apply,
            "context_tags": list(ctx_tags),
            "timestamp": fields.Datetime.now(),
        }

        if not self._is_bridge_enabled(company):
            return bundle._compose_price_result(
                price=base_price, currency=currency, components=components,
                explanation=_("Bridge disabled. Using base price."), meta=meta
            )

        price_before = base_price
        price = base_price

        for engine_key in engines_order:
            if not engines_apply.get(engine_key, True):
                continue
            engine = self._get_engine(engine_key)
            if not engine:
                explanation.append(_("%s engine unavailable") % engine_key.replace("engine_", "").title())
                continue

            try:
                if engine_key in ("engine_membership", "engine_promotions", "engine_surcharge", "engine_insurance"):
                    deltas = engine.compute_bundle_deltas(
                        bundle=bundle,
                        partner_id=partner_id,
                        pricelist_id=(header.id if header else (pl_odoo.id if pl_odoo else None)),
                        quantity=qty,
                        at_date=at_dt,
                        context_tags=ctx_tags,
                    )
                else:
                    deltas = []
            except Exception as e:  # pragma: no cover
                _logger.debug("Engine %s failed: %s", engine_key, e)
                deltas = []
                explanation.append(_("%s engine error") % engine_key.replace("engine_", "").title())

            for d in deltas or []:
                amount = self._ensure_float(d.get("amount"))
                label = d.get("label") or engine_key.replace("engine_", "").title()
                prio = int(d.get("priority", self._default_priority_for_engine(engine_key)))
                meta_d = d.get("meta") or {}
                kind = self._kind_for_engine(engine_key)
                components.append(bundle._price_component(label, amount, kind=kind, priority=prio, meta=meta_d))
                price += amount

        # Minimum + Rounding
        minimum = self._ensure_float(getattr(bundle, "minimum_price", 0.0))
        price, components = bundle._apply_minimum(price, minimum, currency, components)
        price = bundle._round_price(price, currency)

        exp_text = "; ".join(explanation) if explanation else _("Computed by Clinic Pricelist Bridge.")
        res = bundle._compose_price_result(price=price, currency=currency, components=components,
                                           explanation=exp_text, meta=meta)

        if debug:
            _logger.info("BRIDGE DEBUG (bundle %s): base=%s → final=%s; comps=%s",
                         bundle.id, price_before, price, [(c["kind"], c["amount"]) for c in components])
        return res

    # ========================================================================
    # HELPERS — BASE PRICE
    # ========================================================================
    def _base_price_treatment(self, treatment, pl_odoo, qty, at_dt):
        """Kalkulasi base price untuk Treatment."""
        product = self._service_product(treatment)
        if pl_odoo and product:
            try:
                base = float(
                    pl_odoo._get_product_price(product, qty or 1.0, uom=product.uom_id, date=at_dt)
                )
                return base, _("Base (Odoo Pricelist)"), "base"
            except Exception as e:  # pragma: no cover
                _logger.debug("Odoo Pricelist base failed: %s", e)
        return float(treatment.get_default_price() or 0.0), _("Base (Fallback)"), "base"

    def _base_price_bundle(self, bundle, pl_odoo, qty, at_dt):
        """Kalkulasi base price untuk Bundle."""
        product = self._service_product(bundle)
        if pl_odoo and product:
            try:
                base = float(
                    pl_odoo._get_product_price(product, qty or 1.0, uom=product.uom_id, date=at_dt)
                )
                return base, _("Base (Odoo Pricelist)")
            except Exception as e:  # pragma: no cover
                _logger.debug("Odoo Pricelist base (bundle) failed: %s", e)

        # Fallback kebijakan bundle
        if getattr(bundle, "pricing_policy", "fixed") == "fixed":
            return float(bundle.base_price or 0.0), _("Base (Fixed)")
        elif getattr(bundle, "pricing_policy", "fixed") == "sum":
            return float(getattr(bundle, "computed_sum_price", 0.0) or 0.0), _("Base (Sum of Lines)")
        return float(bundle.base_price or 0.0), _("Base (Formula/Fallback)")

    def _service_product(self, rec):
        getp = getattr(rec, "get_service_product", None)
        if callable(getp):
            prod = getp()
            return prod if (prod and prod.exists()) else None
        return None

    # ========================================================================
    # HELPERS — ENGINES & POLICY
    # ========================================================================
    def _engine_order(self, company, header):
        """Urutan engine default dapat disesuaikan di masa depan jika ada setting."""
        # Default pipeline: membership → promotions → surcharge → insurance
        order = ["engine_membership", "engine_promotions", "engine_surcharge", "engine_insurance"]
        # Bisa tambahkan kustomisasi via context atau config di masa depan
        return order

    def _engine_flags(self, header, company):
        """Baca bendera apply_* dari header pricelist (jika ada) + sanity check."""
        flags = {
            "engine_membership": True,
            "engine_promotions": True,
            "engine_surcharge": True,
            "engine_insurance": False,
        }
        if header:
            try:
                flags["engine_membership"] = bool(getattr(header, "apply_membership", True))
                flags["engine_promotions"] = bool(getattr(header, "apply_promotions", True))
                flags["engine_surcharge"] = bool(getattr(header, "apply_surcharge", True))
                flags["engine_insurance"] = bool(getattr(header, "apply_insurance", False))
            except Exception:
                pass
        return flags

    def _default_priority_for_engine(self, engine_key):
        return {"engine_membership": 210, "engine_promotions": 310, "engine_surcharge": 410, "engine_insurance": 510}.get(engine_key, 600)

    def _kind_for_engine(self, engine_key):
        return {
            "engine_membership": "membership",
            "engine_promotions": "promo",
            "engine_surcharge": "surcharge",
            "engine_insurance": "insurance",
        }.get(engine_key, "misc")

    def _get_engine(self, engine_key):
        """Ambil instance engine dari registry."""
        name_map = {
            "engine_membership": "clinic.engine_membership",
            "engine_promotions": "clinic.engine_promotions",
            "engine_surcharge": "clinic.engine_surcharge",
            "engine_insurance": "clinic.engine_insurance",
        }
        model_name = name_map.get(engine_key)
        if not model_name:
            return None
        try:
            if self.env.registry.get(model_name):
                return self.env[model_name]
        except Exception:
            return None
        return None

    # ========================================================================
    # HELPERS — COMPANY & PRICELIST RESOLUTION
    # ========================================================================
    def _resolve_company(self, company_id, fallback_company):
        if company_id:
            comp = self.env["res.company"].browse(company_id)
            if comp and comp.exists():
                return comp
        if fallback_company and fallback_company.exists():
            return fallback_company
        return self.env.company

    def _is_bridge_enabled(self, company):
        """Cek toggle master bridge di Settings (res.company)."""
        try:
            return bool(getattr(company, "clinic_enable_bridge_pricing", True))
        except Exception:
            return True

    def _resolve_pricelist(self, pricelist_id, partner_id, company):
        """Terima ID clinic.treatment.pricelist atau product.pricelist, atau None.
        Kembalikan tuple: (clinic_header, odoo_pricelist)
        """
        header = None
        pl = None
        PLClinic = self.env.registry.get("clinic.treatment.pricelist") and self.env["clinic.treatment.pricelist"] or None
        PL = self.env.registry.get("product.pricelist") and self.env["product.pricelist"] or None

        if pricelist_id:
            if PLClinic and PLClinic.browse(pricelist_id).exists():
                header = PLClinic.browse(pricelist_id)
                pl = header.product_pricelist_id
            elif PL and PL.browse(pricelist_id).exists():
                pl = PL.browse(pricelist_id)
                if hasattr(pl, "clinic_pricelist_id") and pl.clinic_pricelist_id:
                    header = pl.clinic_pricelist_id

        # Jika masih kosong, coba default company
        if not header:
            try:
                header = getattr(company, "clinic_default_pricelist_id", False) or None
                if header and not header.exists():
                    header = None
            except Exception:
                header = None
        if not pl and header:
            pl = header.product_pricelist_id

        # Terakhir, coba property partner (Odoo) agar kompatibel SO/eCommerce
        if not pl and partner_id and PL:
            partner = self.env["res.partner"].browse(partner_id)
            prop_pl = getattr(partner, "property_product_pricelist", False)
            if prop_pl and prop_pl.exists():
                pl = prop_pl
                if hasattr(pl, "clinic_pricelist_id") and pl.clinic_pricelist_id and not header:
                    header = pl.clinic_pricelist_id

        # Pastikan company cocok (jika mungkin)
        if header and header.company_id and company and header.company_id.id != company.id:
            _logger.debug("Pricelist header company mismatch; keeping header=%s comp=%s", header.id, company.id)
        if pl and pl.company_id and company and pl.company_id.id != company.id:
            _logger.debug("Odoo pricelist company mismatch; keeping pl=%s comp=%s", pl.id, company.id)

        return header, pl

    # ========================================================================
    # GENERIC UTILS
    # ========================================================================
    def _assert_single(self, rec, model_name):
        if not rec or rec._name != model_name:
            raise UserError(_("Invalid record model. Expected %s.") % model_name)
        if len(rec) != 1:
            raise UserError(_("You must call bridge with a single record."))

    def _ensure_float(self, value):
        try:
            return float(value or 0.0)
        except Exception:
            return 0.0

