# -*- coding: utf-8 -*-
# ClinicOne - Treatment Catalog & Pricing
# File: models/bridges/bridge_booking.py
#
# Booking Bridge:
# - Menyusun context dari booking/line (therapist/room/equipment/time/channel/insurance/coupon)
# - Menemukan pricelist yang tepat (clinic header / product.pricelist / company default / partner property)
# - Memanggil clinic.pricelist.bridge untuk hitung harga treatment/bundle
# - Menulis snapshot harga ke baris booking (opsional & soft-coupled)
#
from odoo import api, models, fields, _
import logging

_logger = logging.getLogger(__name__)


class ClinicBookingBridge(models.AbstractModel):
    _name = "clinic.booking.bridge"
    _description = "ClinicOne Booking Bridge (context & pricing orchestration)"

    # =========================================================================
    # PUBLIC API
    # =========================================================================
    @api.model
    def compute_prices_for_booking(self, booking, pricelist_id=None, write_snapshot=False, debug=False):
        """Hitung harga untuk seluruh baris booking (jika model baris tersedia).
        Return list hasil per line: [{line_id, type, result_dict}, ...]
        """
        self._assert_record(booking)
        results = []

        line_models = [
            "clinic.booking.line",
            "clinic.appointment.line",
            "clinic.visit.line",
        ]
        # Temukan one2many relasi baris yang tersedia
        lines = self._find_lines(booking, line_models)
        if not lines:
            # fallback: jika booking langsung punya treatment_id/bundle_id (single service)
            res = self.compute_price_for_line(booking, pricelist_id=pricelist_id, write_snapshot=write_snapshot, debug=debug)
            return [{"line_id": getattr(booking, "id", False), "type": "single", "result": res}]

        for ln in lines:
            res = self.compute_price_for_line(ln, pricelist_id=pricelist_id, write_snapshot=write_snapshot, debug=debug)
            results.append({"line_id": ln.id, "type": "line", "result": res})
        return results

    @api.model
    def compute_price_for_line(self, line, pricelist_id=None, write_snapshot=False, debug=False):
        """Hitung satu baris (line bisa jadi:
           - baris booking/appointment/visit, ATAU
           - record booking yang memuat treatment/bundle langsung)
        """
        self._assert_record(line)

        # 1) Resolusi booking/header
        booking = self._find_parent_booking(line)
        partner_id = self._get_partner_id(booking, line)
        company = self._get_company(booking, line)
        header, pl_odoo = self._resolve_pricelist(pricelist_id, booking, partner_id, company)

        # 2) Tentukan target (treatment atau bundle) + quantity + tanggal
        target, is_bundle = self._resolve_target(line)
        if not target:
            return {}

        qty = self._get_quantity(line)
        at_dt = self._get_datetime(line, booking)

        # 3) Kumpulkan context_tags dari booking & line
        ctx_tags = self._collect_context_tags(booking, line, at_dt)

        # 4) Panggil bridge harga inti
        bridge = self.env["clinic.pricelist.bridge"]
        used_pl_id = header.id if header else (pl_odoo.id if pl_odoo else None)

        if is_bundle:
            result = bridge.compute_bundle_price(
                bundle=target,
                partner_id=partner_id,
                pricelist_id=used_pl_id,
                quantity=qty,
                sale_dt=at_dt,
                context_tags=ctx_tags,
                company_id=company.id if company else None,
                debug=debug,
            )
        else:
            result = bridge.compute_treatment_price(
                treatment=target,
                partner_id=partner_id,
                pricelist_id=used_pl_id,
                quantity=qty,
                booking_dt=at_dt,
                context_tags=ctx_tags,
                company_id=company.id if company else None,
                debug=debug,
            )

        # 5) (Opsional) Tulis snapshot ke line jika field tersedia
        if write_snapshot and result:
            self._write_snapshot_to_line(line, result)

        return result or {}

    # =========================================================================
    # CONTEXT & PRICELIST RESOLUTION
    # =========================================================================
    def _collect_context_tags(self, booking, line, at_dt):
        """Bangun daftar context_tags dari booking/line.
        Format yang digunakan engine:
          - therapist_level:<slug|id>
          - room_type:<slug|id> / room:<slug|id>
          - equipment:<slug|id> / device:<slug|id>
          - location:<slug|id> / branch:<slug|id> / company:<slug|id>
          - channel:booking
          - prime_time / weekend / holiday / urgent
          - coupon:CODE
          - preauth:yes|no / referral:yes|no
          - deductible_remaining:<float> / annual_remaining:<float> / oop_remaining:<float>
        """
        tags = []

        # Channel
        tags.append("channel:booking")

        # Therapist / level
        therapist = self._get_any(line, ["therapist_id", "practitioner_id", "provider_id"])
        if therapist:
            lvl = self._get_any(therapist, ["level_id", "grade_id", "rank_id"])
            if lvl:
                tags.append(f"therapist_level:{self._slug_from_record(lvl)}")

        # Room / room type
        room = self._get_any(line, ["room_id", "facility_id"])
        rtype = self._get_any(room, ["room_type_id"]) if room else None
        if rtype:
            tags.append(f"room_type:{self._slug_from_record(rtype)}")
        elif room:
            # pakai room sebagai fallback
            tags.append(f"room:{self._slug_from_record(room)}")

        # Equipment / device (m2m atau m2o)
        eq = self._get_any(line, ["equipment_id", "device_id"])
        eqs = self._get_any(line, ["equipment_ids", "device_ids"])
        if eq:
            tags.append(f"equipment:{self._slug_from_record(eq)}")
        if eqs:
            # Ambil satu yang paling relevan; engine kita bisa pakai satu kunci
            first = eqs[:1] if hasattr(eqs, "__getitem__") else eqs
            if first:
                rec = first[0] if hasattr(first, "__getitem__") else first
                if rec:
                    tags.append(f"equipment:{self._slug_from_record(rec)}")

        # Lokasi / branch / company
        loc = self._get_any(booking or line, ["location_id"])
        if loc:
            tags.append(f"location:{self._slug_from_record(loc)}")
        branch = self._get_any(booking or line, ["branch_id"])
        if branch:
            tags.append(f"branch:{self._slug_from_record(branch)}")
        company = self._get_company(booking, line)
        if company:
            tags.append(f"company:{company.id}")

        # Urgency
        urgent = self._get_any(booking or line, ["is_urgent", "urgent"])
        if bool(urgent):
            tags.append("urgent")

        # Insurance toggles
        preauth = self._get_any(booking or line, ["preauth_ok", "pre_authorized", "preauth"])
        if preauth is True or (isinstance(preauth, str) and preauth.lower() in ("y", "yes", "true")):
            tags.append("preauth:yes")
        elif preauth is False or (isinstance(preauth, str) and preauth.lower() in ("n", "no", "false")):
            tags.append("preauth:no")

        referral = self._get_any(booking or line, ["referral_ok", "has_referral", "referral"])
        if referral is True or (isinstance(referral, str) and referral.lower() in ("y", "yes", "true")):
            tags.append("referral:yes")
        elif referral is False or (isinstance(referral, str) and referral.lower() in ("n", "no", "false")):
            tags.append("referral:no")

        # Insurance numeric context
        for key in ("deductible_remaining", "annual_remaining", "oop_remaining"):
            val = self._get_any(booking or line, [key])
            if val not in (None, False):
                try:
                    tags.append(f"{key}:{float(val)}")
                except Exception:
                    pass

        # Coupon (line > booking)
        coupon = self._get_any(line, ["coupon_code", "promo_code"]) or self._get_any(booking, ["coupon_code", "promo_code"])
        if coupon:
            tags.append(f"coupon:{str(coupon).strip()}")

        # Time signals
        if at_dt:
            dow = at_dt.weekday()  # 0=Mon..6=Sun
            if dow in (5, 6):
                tags.append("weekend")
            # prime_time heuristik (17:00..21:00)
            if 17 <= at_dt.hour <= 21:
                tags.append("prime_time")
            # holiday (opsional) — jika resource.calendar.leaves dengan holiday=True ada, tagging dilakukan di engine; di sini tambahkan hint dari booking jika ada
            if self._get_any(booking or line, ["is_holiday_slot"]):
                tags.append("holiday")

        return tags

    def _resolve_pricelist(self, pricelist_id, booking, partner_id, company):
        """Kembalikan (clinic_header, product_pricelist) sesuai konteks booking/partner/company."""
        header = None
        pl_odoo = None
        PLClinic = self.env.registry.get("clinic.treatment.pricelist") and self.env["clinic.treatment.pricelist"] or None
        PL = self.env.registry.get("product.pricelist") and self.env["product.pricelist"] or None

        # 1) Prioritas: argumen explicit
        if pricelist_id:
            if PLClinic and PLClinic.browse(pricelist_id).exists():
                header = PLClinic.browse(pricelist_id)
                pl_odoo = header.product_pricelist_id
            elif PL and PL.browse(pricelist_id).exists():
                pl_odoo = PL.browse(pricelist_id)
                if hasattr(pl_odoo, "clinic_pricelist_id") and pl_odoo.clinic_pricelist_id:
                    header = pl_odoo.clinic_pricelist_id

        # 2) Header booking
        if not header:
            header = self._get_any(booking, ["clinic_pricelist_id"])
            if header and hasattr(header, "product_pricelist_id") and header.product_pricelist_id:
                pl_odoo = header.product_pricelist_id

        # 3) Pricelist booking (product.pricelist)
        if not pl_odoo:
            pl_odoo = self._get_any(booking, ["product_pricelist_id", "pricelist_id"])

        # 4) Company default
        if not header and company and hasattr(company, "clinic_default_pricelist_id"):
            header = company.clinic_default_pricelist_id
            if header and hasattr(header, "product_pricelist_id") and header.product_pricelist_id:
                pl_odoo = pl_odoo or header.product_pricelist_id

        # 5) Partner property
        if not pl_odoo and partner_id and PL:
            partner = self.env["res.partner"].browse(partner_id)
            if partner and partner.exists():
                prop = getattr(partner, "property_product_pricelist", False)
                if prop and prop.exists():
                    pl_odoo = prop
                    if hasattr(pl_odoo, "clinic_pricelist_id") and pl_odoo.clinic_pricelist_id and not header:
                        header = pl_odoo.clinic_pricelist_id

        return header, pl_odoo

    # =========================================================================
    # LINE / BOOKING RESOLUTION
    # =========================================================================
    def _find_lines(self, booking, candidate_models):
        """Cari one2many lines pada booking dari daftar kandidat model."""
        if not booking:
            return self.env["ir.model.fields"].browse()  # kosong
        for field_name in booking._fields.keys():
            val = getattr(booking, field_name)
            # Cari X2Many ke salah satu kandidat model
            try:
                if hasattr(val, "_name") and val._name in candidate_models:
                    return val
            except Exception:
                continue
        return self.env[booking._name]  # recordset kosong

    def _find_parent_booking(self, record):
        """Jika record adalah line, coba temukan parent booking/appointment-nya."""
        # Heuristik: cari m2o yang mengarah ke model booking umum
        for fname in ("booking_id", "appointment_id", "visit_id", "order_id"):
            if fname in record._fields:
                parent = getattr(record, fname)
                if parent and parent.exists():
                    return parent
        # Bisa jadi record itu sendiri adalah booking
        return record if record._name in ("booking.booking", "clinic.appointment", "clinic.visit") else None

    def _resolve_target(self, record):
        """Tentukan apakah baris menargetkan treatment atau bundle."""
        # Line style
        tr = self._get_any(record, ["treatment_id", "service_id"])
        bd = self._get_any(record, ["bundle_id", "package_id"])
        if tr:
            return tr, False
        if bd:
            return bd, True

        # Booking style (single target on header)
        tr = self._get_any(record, ["treatment_id"])
        bd = self._get_any(record, ["bundle_id"])
        if tr:
            return tr, False
        if bd:
            return bd, True

        return None, False

    def _get_quantity(self, record):
        qty = self._get_any(record, ["quantity", "qty", "units", "session_qty"])
        if qty in (None, False, 0):
            return 1.0
        try:
            return float(qty)
        except Exception:
            return 1.0

    def _get_datetime(self, line, booking):
        """Ambil tanggal/waktu booking yang relevan untuk pricing (timezone-aware)."""
        for fname in ("start_datetime", "datetime_start", "scheduled_start", "appointment_datetime"):
            val = self._get_any(line, [fname])
            if val:
                return fields.Datetime.to_datetime(val)
        for fname in ("start_datetime", "datetime_start", "scheduled_start", "appointment_datetime", "booking_datetime"):
            val = self._get_any(booking, [fname])
            if val:
                return fields.Datetime.to_datetime(val)
        return fields.Datetime.now()

    def _get_partner_id(self, booking, line):
        """Cari partner/patient untuk harga (keanggotaan, promo, insurance)."""
        cand = [
            (booking, ["partner_id", "patient_id", "customer_id"]),
            (line, ["partner_id", "patient_id", "customer_id"]),
        ]
        for rec, names in cand:
            pid = self._get_any(rec, names)
            if pid and getattr(pid, "id", False):
                return pid.id
        return None

    def _get_company(self, booking, line):
        comp = self._get_any(booking, ["company_id"]) or self._get_any(line, ["company_id"]) or self.env.company
        return comp

    # =========================================================================
    # SNAPSHOT WRITER (opsional)
    # =========================================================================
    def _write_snapshot_to_line(self, line, result):
        """Tulis hasil pricing ke line jika field tersedia.
        Field yang dicoba (soft):
          - price_unit / unit_price / price (float)
          - currency_id (many2one)
          - price_breakdown (char/text)
          - price_components_json / price_meta_json (json/char/text)
          - price_explanation (text)
        """
        vals = {}
        price = float(result.get("price", 0.0) or 0.0)
        currency_id = result.get("currency_id")
        breakdown = result.get("breakdown_text", "")
        explanation = result.get("explanation", "")
        comps = result.get("components", [])
        meta = result.get("meta", {})

        # unit price fields
        for fname in ("price_unit", "unit_price", "price"):
            if fname in line._fields:
                vals[fname] = price
                break

        # currency
        if "currency_id" in line._fields and currency_id:
            vals["currency_id"] = currency_id

        # breakdown/explanation
        for fname in ("price_breakdown", "price_note", "price_explanation"):
            if fname in line._fields:
                vals[fname] = breakdown if fname != "price_explanation" else explanation
                # Tidak break: mungkin kedua-duanya ada (breakdown & explanation)
        # components/meta json/text
        for fname in ("price_components_json", "components_json", "pricing_components"):
            if fname in line._fields:
                try:
                    vals[fname] = self._json_dumps_safe(comps)
                except Exception:
                    vals[fname] = str(comps)
                break
        for fname in ("price_meta_json", "pricing_meta"):
            if fname in line._fields:
                try:
                    vals[fname] = self._json_dumps_safe(meta)
                except Exception:
                    vals[fname] = str(meta)
                break

        if vals:
            line.sudo().write(vals)

    # =========================================================================
    # UTILS (GENERIC)
    # =========================================================================
    def _assert_record(self, rec):
        if not rec or not rec.exists():
            raise ValueError("Booking/Line record is required")

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

    def _slug_from_record(self, rec):
        """Buat slug sederhana dari id|code|name."""
        try:
            if getattr(rec, "id", False):
                return str(rec.id)
        except Exception:
            pass
        for fname in ("code", "name", "display_name"):
            if fname in getattr(rec, "_fields", {}):
                try:
                    val = getattr(rec, fname)
                    if val:
                        return str(val).strip().replace(" ", "_")
                except Exception:
                    continue
        return "unknown"

    def _json_dumps_safe(self, obj):
        try:
            import json
            return json.dumps(obj, ensure_ascii=False)
        except Exception:
            return str(obj)

