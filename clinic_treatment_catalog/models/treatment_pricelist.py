# -*- coding: utf-8 -*-
# ClinicOne - Treatment Catalog & Pricing
# File: models/treatment_pricelist.py
#
# Model:
#   - clinic.treatment.pricelist : Header pricelist khusus klinik, terhubung ke product.pricelist
#
# Tujuan:
#   - Menjadi "payung" kebijakan harga klinik (membership, surcharge, insurance, promo) tanpa hard dependency
#   - Tetap kompatibel dengan alur standar Odoo (SO/Invoice/Web) melalui product.pricelist terhubung
#   - Memberi API helper untuk preview harga treatment dan smart actions ke item aturan
#
# Integrasi (soft-coupled):
#   - product.pricelist (Odoo)    : product_pricelist_id
#   - clinic.treatment.catalog    : preview harga & domain scoping
#   - clinic.treatment.pricelist.item : child rules (di file treatment_pricelist_item.py)
#   - clinic.pricelist.bridge     : engine harga central (jika terpasang)
#   - clinic.audit.event          : audit terstruktur (opsional)
#
from odoo import api, fields, models, _, tools
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class ClinicTreatmentPricelist(models.Model):
    _name = "clinic.treatment.pricelist"
    _description = "Clinic Treatment Pricelist"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Name",
        required=True,
        tracking=True,
        index=True,
        help="Nama pricelist klinik."
    )
    code = fields.Char(
        string="Code",
        copy=False,
        readonly=True,
        index=True,
        tracking=True,
        help="Kode unik, terisi dari sequence saat create."
    )
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True, tracking=True)
    notes = fields.Html(string="Notes", sanitize=True)

    # -------------------------------------------------------------------------
    # Company & Currency
    # -------------------------------------------------------------------------
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True
    )

    # -------------------------------------------------------------------------
    # Validity & Scope
    # -------------------------------------------------------------------------
    valid_from = fields.Date(string="Valid From")
    valid_to = fields.Date(string="Valid To")
    is_currently_valid = fields.Boolean(
        string="Currently Valid",
        compute="_compute_is_currently_valid",
        search="_search_is_currently_valid",
        store=False,
        help="Dynamic validity based on active status and the current date.",
    )

    # Scoping sederhana agar engine dapat membaca kebijakan tanpa hard dependency
    channel = fields.Selection(
        selection=[
            ("all", "All Channels"),
            ("backoffice", "Back-office"),
            ("booking", "Booking/Frontdesk"),
            ("ecommerce", "eCommerce/Portal"),
            ("api", "API/3rd party"),
        ],
        string="Primary Channel",
        default="all",
        required=True,
        help="Channel utama sasaran pricelist ini."
    )
    tag_ids = fields.Many2many(
        "clinic.treatment.tag",
        "clinic_pricelist_tag_rel",
        "pricelist_id",
        "tag_id",
        string="Scope Tags",
        help="Tag untuk pembatasan/penandaan promo/segmen (opsional)."
    )

    # -------------------------------------------------------------------------
    # Policy Flags (dibaca bridge/engine)
    # -------------------------------------------------------------------------
    apply_membership = fields.Boolean(
        string="Apply Membership Benefits",
        default=True,
        help="Izinkan manfaat membership diterapkan pada perhitungan harga."
    )
    apply_promotions = fields.Boolean(
        string="Apply Promotions",
        default=True,
        help="Aktifkan aturan promo musiman/kupon."
    )
    apply_surcharge = fields.Boolean(
        string="Apply Surcharge",
        default=True,
        help="Izinkan surcharge (level terapis, room/equipment, prime time)."
    )
    apply_insurance = fields.Boolean(
        string="Apply Insurance",
        default=False,
        help="Pricelist ini mendukung skenario asuransi (coverage/co-pay)."
    )
    tax_included = fields.Boolean(
        string="Prices Include Taxes",
        default=False,
        help="Bendera informasi untuk UI; perhitungan final tetap mengikuti konfigurasi pajak & fiscal position."
    )
    rounding_policy = fields.Selection(
        selection=[
            ("currency", "Currency Rounding"),
            ("half_up", "Half Up (0.5 → 1)"),
            ("down", "Round Down"),
            ("up", "Round Up"),
        ],
        string="Rounding Policy",
        default="currency",
        help="Panduan pembulatan untuk bridge/engine."
    )

    # -------------------------------------------------------------------------
    # Link ke Odoo product.pricelist
    # -------------------------------------------------------------------------
    product_pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Odoo Pricelist",
        ondelete="set null",
        tracking=True,
        help="Pricelist Odoo yang terhubung untuk alur standar SO/Invoice/eCommerce."
    )

    # -------------------------------------------------------------------------
    # Relations to Rules (child model ada di file treatment_pricelist_item.py)
    # -------------------------------------------------------------------------
    item_ids = fields.One2many(
        "clinic.treatment.pricelist.item",
        "pricelist_id",
        string="Treatment Price Rules"
    )
    item_count = fields.Integer(string="Rules", compute="_compute_counts")
    treatment_count = fields.Integer(string="Treatments in Rules", compute="_compute_counts")

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    _code_company_uniq = models.Constraint(
        "unique(code, company_id)",
        "Code must be unique per company.",
    )

    # =========================================================================
    # COMPUTES
    # =========================================================================
    @api.depends("valid_from", "valid_to", "active")
    def _compute_is_currently_valid(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.active:
                rec.is_currently_valid = False
                continue
            vf_ok = (not rec.valid_from) or (rec.valid_from <= today)
            vt_ok = (not rec.valid_to) or (today <= rec.valid_to)
            rec.is_currently_valid = bool(vf_ok and vt_ok)

    @api.model
    def _search_is_currently_valid(self, operator, value):
        """Search the dynamic validity flag using stored source fields.

        The flag depends on today's date, so storing it would become stale when
        the calendar day changes. Odoo 19 normalizes Boolean comparisons to
        ``in``/``not in`` with Boolean value lists; handle those operators and
        keep the query fully SQL-searchable through ``active``, ``valid_from``
        and ``valid_to``.
        """
        if operator in ("=", "!="):
            requested_values = [value]
            operator = "in" if operator == "=" else "not in"
        elif operator in ("in", "not in"):
            requested_values = list(value) if isinstance(value, (list, tuple, set)) else [value]
        else:
            return NotImplemented

        requested = {bool(item) for item in requested_values}
        if operator == "not in":
            requested = {True, False} - requested

        if requested == {True, False}:
            return []
        if not requested:
            return [("id", "=", 0)]

        today = fields.Date.context_today(self)
        currently_valid_domain = [
            ("active", "=", True),
            "|",
            ("valid_from", "=", False),
            ("valid_from", "<=", today),
            "|",
            ("valid_to", "=", False),
            ("valid_to", ">=", today),
        ]
        currently_invalid_domain = [
            "|",
            ("active", "=", False),
            "|",
            ("valid_from", ">", today),
            ("valid_to", "<", today),
        ]
        return currently_valid_domain if True in requested else currently_invalid_domain

    def _compute_counts(self):
        for rec in self:
            rec.item_count = len(rec.item_ids)
            rec.treatment_count = len(rec.item_ids.mapped("treatment_id"))

    # =========================================================================
    # ONCHANGE / CONSTRAINTS
    # =========================================================================
    @api.constrains("valid_from", "valid_to")
    def _check_validity(self):
        for rec in self:
            if rec.valid_from and rec.valid_to and rec.valid_from > rec.valid_to:
                raise ValidationError(_("Valid From cannot be greater than Valid To."))

    # =========================================================================
    # ORM OVERRIDES
    # =========================================================================
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env.ref("clinic_treatment_catalog.seq_treatment_pricelist_code", raise_if_not_found=False)
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            if not vals.get("code") and seq:
                vals["code"] = seq._next()
        recs = super().create(vals_list)
        # Ensure linked product.pricelist exists
        for rec in recs:
            rec._ensure_product_pricelist()
            rec._sync_to_product_pricelist()
        recs._audit_event("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        # Sync changes to product.pricelist when relevant
        tracked = {"name", "active", "company_id", "valid_from", "valid_to"}
        if set(vals).intersection(tracked):
            for rec in self:
                rec._ensure_product_pricelist()
                rec._sync_to_product_pricelist()
        # Audit
        if set(vals):
            self._audit_event("write", changed_fields=list(vals.keys()))
        return res

    def unlink(self):
        """Cegah hapus jika masih memiliki item; sarankan archive."""
        for rec in self:
            if rec.item_ids:
                raise UserError(_("You cannot delete a pricelist that still has price rules. Archive it instead."))
        return super().unlink()

    # =========================================================================
    # HELPERS
    # =========================================================================
    def _audit_event(self, action, changed_fields=None):
        """Audit ke clinic.audit.event (opsional) + fallback chatter."""
        self.message_post(body=_("Pricelist %s: %s") % (action, ", ".join(changed_fields or [])))
        audit_model = self.env.registry.get("clinic.audit.event")
        if not audit_model:
            return
        for rec in self:
            try:
                self.env["clinic.audit.event"].sudo().create({
                    "name": "pricelist.%s" % action,
                    "model": rec._name,
                    "res_id": rec.id,
                    "company_id": rec.company_id.id,
                    "payload": {
                        "changed_fields": changed_fields or [],
                        "user_id": self.env.user.id,
                    },
                })
            except Exception as e:  # pragma: no cover
                _logger.debug("Audit event skipped: %s", e)

    def _ensure_product_pricelist(self):
        """Pastikan ada product.pricelist yang terhubung.
        Bila belum ada → buat otomatis agar kompatibel SO/eCommerce.
        """
        for rec in self:
            if rec.product_pricelist_id and rec.product_pricelist_id.exists():
                continue
            pl_vals = {
                "name": rec.name,
                "active": rec.active,
                "company_id": rec.company_id.id,
                "currency_id": rec.currency_id.id,
                # Validity tetap dikelola oleh header/rules ClinicOne.
            }
            pl = self.env["product.pricelist"].create(pl_vals)
            # Link balik
            pl._clinic_link(rec)
            rec.product_pricelist_id = pl.id

    def _sync_to_product_pricelist(self):
        """Sinkron nama/aktif/perusahaan ke product.pricelist terhubung."""
        for rec in self.sudo():
            pl = rec.product_pricelist_id
            if not pl or not pl.exists():
                continue
            updates = {}
            if pl.name != rec.name:
                updates["name"] = rec.name
            if pl.active != rec.active:
                updates["active"] = rec.active
            if pl.company_id.id != rec.company_id.id:
                updates["company_id"] = rec.company_id.id
            if pl.currency_id.id != rec.currency_id.id:
                # Secara umum, currency di pricelist Odoo sebaiknya tidak sering diubah.
                updates["currency_id"] = rec.currency_id.id
            if updates:
                pl.write(updates)

    # =========================================================================
    # PUBLIC API
    # =========================================================================
    def action_open_items(self):
        """Smart button: buka aturan harga (clinic.treatment.pricelist.item) pada header ini."""
        self.ensure_one()
        action = self.env.ref("clinic_treatment_catalog.action_treatment_pricelist_item", raise_if_not_found=False)
        domain = [("pricelist_id", "=", self.id)]
        if action:
            res = action.read()[0]
            res["domain"] = domain
            res["context"] = {"default_pricelist_id": self.id}
            return res
        # Fallback generic
        return {
            "type": "ir.actions.act_window",
            "name": _("Treatment Price Rules"),
            "res_model": "clinic.treatment.pricelist.item",
            "view_mode": "list,form",
            "domain": domain,
            "context": {"default_pricelist_id": self.id},
        }

    def action_price_preview(self, treatment_id, partner_id=None, quantity=1.0, booking_dt=None, context_tags=None):
        """Preview harga treatment berdasarkan header ini.
        - Jika bridge tersedia → delegasi ke engine
        - Jika tidak → fallback product.pricelist standar atau base_price treatment
        Return dict: {'price': float, 'currency_id': id, 'explanation': str}
        """
        self.ensure_one()
        Treatment = self.env["clinic.treatment.catalog"].browse(treatment_id)
        if not Treatment.exists():
            raise UserError(_("Treatment not found."))

        expl = []
        currency = self.currency_id
        # Bridge?
        bridge_model = self.env.registry.get("clinic.pricelist.bridge")
        if bridge_model:
            try:
                res = self.env["clinic.pricelist.bridge"].sudo().compute_treatment_price(
                    treatment=Treatment,
                    partner_id=partner_id,
                    pricelist_id=self.id,
                    quantity=quantity,
                    booking_dt=booking_dt,
                    context_tags=context_tags or [],
                )
                return {
                    "price": res.get("price", 0.0),
                    "currency_id": currency.id if currency else False,
                    "explanation": res.get("explanation", ""),
                }
            except Exception as e:  # pragma: no cover
                _logger.warning("Bridge compute failed; fallback to standard: %s", e)
                expl.append(_("Bridge error, fallback applied."))

        # Fallback: gunakan product.pricelist standar jika terkait & ada product pada treatment
        price = Treatment.get_default_price()
        pl = self.product_pricelist_id
        product = Treatment.get_service_product()
        if pl and pl.exists() and product and product.exists():
            try:
                price = float(
                    pl._get_product_price(product, quantity or 1.0, uom=product.uom_id, date=False)
                )
                expl.append(_("Odoo Pricelist applied."))
            except Exception as e:  # pragma: no cover
                _logger.debug("Odoo pricelist fallback skipped: %s", e)

        return {
            "price": price,
            "currency_id": currency.id if currency else False,
            "explanation": " ".join(expl),
        }

    # =========================================================================
    # NAME GET / SEARCH
    # =========================================================================
    def _clinic_display_label(self):
        self.ensure_one()
        return "[%s] %s" % (self.code, self.name) if self.code else self.name

    @api.depends("code", "name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec._clinic_display_label()

    def name_get(self):
        return [(rec.id, rec._clinic_display_label()) for rec in self]

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        domain = domain or []
        criteria = ["|", ("code", operator, name), ("name", operator, name)] if name else []
        recs = self.search(criteria + domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]


# =============================================================================
# EXTEND ODOO PRICELIST — tambahkan backlink agar mudah navigasi
# =============================================================================
class ProductPricelist(models.Model):
    _inherit = "product.pricelist"

    clinic_pricelist_id = fields.Many2one(
        "clinic.treatment.pricelist",
        string="Clinic Treatment Pricelist",
        ondelete="set null",
        help="Backlink ke ClinicOne pricelist header."
    )

    def _clinic_link(self, clinic_pl):
        """Utility untuk link product.pricelist ↔ clinic.treatment.pricelist (dipanggil dari header)."""
        self.ensure_one()
        if not clinic_pl or not clinic_pl.exists():
            return
        vals = {}
        if self.clinic_pricelist_id.id != clinic_pl.id:
            vals["clinic_pricelist_id"] = clinic_pl.id
        if vals:
            self.write(vals)

