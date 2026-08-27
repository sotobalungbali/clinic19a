# -*- coding: utf-8 -*-
# ClinicOne - Treatment Catalog & Pricing
# File: models/mixin_pricing.py
#
# Mixin utilitas pricing untuk dipakai pada berbagai model:
#  - Rounding policy (currency/half_up/down/up)
#  - Penyusunan price result dict + breakdown komponen
#  - Guardrail minimum price
#  - Fallback ke Odoo product.pricelist
#  - Konversi durasi → menit
#  - Helper format uang & akses settings company
#
# Desain soft-coupled:
#  - Tidak ada hard dependency ke modul lain.
#  - Membaca konfigurasi dari res.company (diisi via res.config.settings modul ini).
#
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN, ROUND_UP, InvalidOperation
from odoo import fields, tools, _
import logging

_logger = logging.getLogger(__name__)


class ClinicPricingMixin(object):
    """
    Campuran (mixin) utilitas pricing.
    Kelas ini **bukan** models.Model, tapi akan berada di MRO saat di-extend oleh model Odoo.

    ==== API RINGKAS ====
    - self._round_price(amount, currency, policy=None)
    - self._apply_minimum(price, minimum, currency, components=None, label='Minimum Price Guardrail')
    - self._compose_price_result(price, currency, components=None, explanation=None, meta=None)
    - self._pricelist_get_price(product, pricelist, qty=1.0, date=False, uom_id=False, default=None)
    - self._minutes_from_duration(value, uom='minute')
    - self._format_money(amount, currency=None)
    - self._get_settings(company=None)  → dict ringkas kebijakan company
    - self._safe_get_model(model_name)  → return env[model] jika ada, else None
    - self._price_component(label, amount, kind='base', meta=None, priority=100)
    """

    # =========================================================================
    # ROUNDING
    # =========================================================================
    def _round_price(self, amount, currency, policy=None):
        """Bulatkan angka sesuai kebijakan.
        policy: 'currency' (default), 'half_up', 'down', 'up'
        """
        try:
            amt = float(amount or 0.0)
        except (ValueError, TypeError):
            amt = 0.0
        policy = policy or self._get_settings().get("rounding_policy") or "currency"

        if policy == "currency":
            # gunakan pembulatan mata uang Odoo
            try:
                return currency.round(amt) if currency else round(amt, 2)
            except Exception:
                return round(amt, 2)

        # pembulatan manual berbasis Decimal ke jumlah desimal currency
        decimals = 2
        try:
            if currency and hasattr(currency, "decimal_places") and currency.decimal_places is not None:
                decimals = int(currency.decimal_places)
        except Exception:
            pass

        quant = Decimal("1").scaleb(-decimals)  # contoh: 2 desimal → Decimal('0.01')
        d = Decimal(str(amt))
        rounding = ROUND_HALF_UP if policy == "half_up" else ROUND_DOWN if policy == "down" else ROUND_UP
        try:
            return float(d.quantize(quant, rounding=rounding))
        except InvalidOperation:
            return round(amt, decimals)

    # =========================================================================
    # SETTINGS & HELPERS
    # =========================================================================
    def _get_settings(self, company=None):
        """Ambil potongan konfigurasi penting dari res.company (aman jika field belum ada)."""
        company = company or getattr(self, "company_id", None) or self.env.company
        vals = {
            "enable_bridge": True,
            "rounding_policy": "currency",
            "tax_included_ui": False,
            "booking_price_preview": True,
            "booking_include_insurance": False,
        }
        # Field-field ini didefinisikan di models/res_config_settings.py (res.company inherit)
        for field_name, key in [
            ("clinic_enable_bridge_pricing", "enable_bridge"),
            ("clinic_rounding_policy", "rounding_policy"),
            ("clinic_pricing_tax_included", "tax_included_ui"),
            ("clinic_booking_price_preview", "booking_price_preview"),
            ("clinic_booking_include_insurance", "booking_include_insurance"),
        ]:
            try:
                if hasattr(company, field_name):
                    vals[key] = getattr(company, field_name)
            except Exception:
                # aman jika belum ada
                pass
        return vals

    def _safe_get_model(self, model_name):
        """Kembalikan env[model_name] jika ada di registry; jika tidak, None."""
        try:
            if self.env.registry.get(model_name):
                return self.env[model_name]
        except Exception:
            return None
        return None

    def _format_money(self, amount, currency=None):
        """Format angka uang menurut locale/user."""
        try:
            return tools.format_amount(self.env, amount or 0.0, currency=currency)
        except Exception:
            # fallback sederhana
            return "{:,.2f}".format(float(amount or 0.0))

    # Durasi → menit, dipakai di treatment.py
    def _minutes_from_duration(self, value, uom="minute"):
        try:
            val = float(value or 0.0)
        except (ValueError, TypeError):
            val = 0.0
        return int(val if uom == "minute" else val * 60.0)

    # =========================================================================
    # PRICE COMPOSITION & MINIMUM GUARD
    # =========================================================================
    def _price_component(self, label, amount, kind="base", meta=None, priority=100, applied=True):
        """Buat dict komponen untuk breakdown harga."""
        return {
            "label": label,
            "amount": float(amount or 0.0),
            "kind": kind,                # base | membership | promo | surcharge | insurance | minimum | misc
            "applied": bool(applied),
            "priority": int(priority),   # urutan tampil
            "meta": meta or {},          # payload tambahan (ids, refs)
        }

    def _apply_minimum(self, price, minimum, currency, components=None, label=None):
        """Jika price < minimum, naikkan price ke minimum dan catat komponen 'minimum' sebagai koreksi."""
        price = float(price or 0.0)
        minimum = float(minimum or 0.0)
        components = components or []
        if minimum and price < minimum:
            delta = minimum - price
            components.append(self._price_component(
                label or _("Minimum Price Guardrail"),
                delta,
                kind="minimum",
                priority=900
            ))
            return self._round_price(minimum, currency), components
        return self._round_price(price, currency), components

    def _compose_price_result(self, price, currency, components=None, explanation=None, meta=None):
        """Normalisasi hasil harga:
        {
          'price': <float>,
          'currency_id': <id>,
          'components': [ {label, amount, kind, applied, priority, meta}, ... ],
          'explanation': '<string>',
          'breakdown_text': '<string human readable>',
          'meta': {...}
        }
        """
        components = components or []
        # sort komponen by priority
        components = sorted(components, key=lambda c: (int(c.get("priority", 100)), c.get("label", "")))
        breakdown_parts = []
        total = 0.0
        for comp in components:
            amt = float(comp.get("amount") or 0.0)
            total += amt
            sign = "+" if amt >= 0 else "−"
            # tampilkan nilai absolut (tanpa minus di depan)
            breakdown_parts.append("%s %s" % (sign, self._format_money(abs(amt), currency)))
        breakdown_text = " ".join(breakdown_parts).strip()
        # keterangan singkat
        explanation = explanation or ""
        return {
            "price": float(price or 0.0),
            "currency_id": currency.id if currency else False,
            "components": components,
            "explanation": explanation,
            "breakdown_text": breakdown_text,
            "meta": meta or {},
        }

    # =========================================================================
    # ODOO PRICELIST FALLBACK
    # =========================================================================
    def _pricelist_get_price(self, product, pricelist, qty=1.0, date=False, uom_id=False, default=None):
        """Ambil harga menggunakan Odoo product.pricelist standar.
        Return float (atau default bila gagal).
        """
        try:
            if not product or not product.exists() or not pricelist or not pricelist.exists():
                return default
            uom = self.env["uom.uom"].browse(uom_id) if uom_id else product.uom_id
            price = pricelist._get_product_price(
                product,
                qty or 1.0,
                uom=uom,
                date=date or fields.Date.context_today(self),
            )
            return float(price)
        except Exception as e:
            _logger.debug("Pricelist fallback failed: %s", e)
        return default

    # =========================================================================
    # HIGH-LEVEL HELPERS (opsional dipakai bridge/preview)
    # =========================================================================
    def _compute_local_formula(self, base_price, flags=None, context=None):
        """Placeholder perhitungan lokal sederhana saat policy='formula' tapi bridge tidak tersedia.
        Bisa di-override oleh model konkrit bila diperlukan.
        """
        flags = flags or {}
        # Saat ini: tidak ada formula khusus → kembalikan base price.
        return float(base_price or 0.0), []

    def _summarize_components(self, components, currency=None):
        """Buat teks ringkas dari list komponen (untuk tooltip/UI)."""
        if not components:
            return ""
        parts = []
        for comp in components:
            lbl = comp.get("label") or ""
            amt = float(comp.get("amount") or 0.0)
            parts.append("%s %s" % (lbl, self._format_money(amt, currency)))
        return "; ".join(parts)

    # =========================================================================
    # MINI EXAMPLE (komentar)
    # =========================================================================
    # Contoh alur hitung (di model konkret):
    #
    # def action_price_preview(...):
    #     currency = self.currency_id
    #     comps = []
    #     base = self.base_price or 0.0
    #     comps.append(self._price_component(_("Base Price"), base, kind="base", priority=100))
    #     # membership/promo/surcharge/insurance (jika ada engine) akan menambahkan komponen
    #     # total = sum(comp.amount)  → atau gunakan base + delta (tergantung implementasi)
    #     total = base
    #     for c in comps[1:]:
    #         total += c["amount"]
    #     # guard minimum
    #     total, comps = self._apply_minimum(total, self.minimum_price, currency, comps)
    #     total = self._round_price(total, currency)
    #     return self._compose_price_result(total, currency, comps, explanation="Local preview")

