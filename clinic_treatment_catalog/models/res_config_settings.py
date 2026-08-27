# -*- coding: utf-8 -*-
# ClinicOne - Treatment Catalog & Pricing
# File: models/res_config_settings.py
#
# Konfigurasi per perusahaan:
# - Disimpan di res.company (field "clinic_*") agar benar-benar multi-company
# - Diedit melalui res.config.settings (related, readonly=False)
#
# Cakupan pengaturan:
# - Default Pricelist (Clinic) & Default Product Category (service)
# - Pricing Bridge flags: enable, rounding policy, tax included
# - Default behavior: surcharge/insurance applicable
# - Booking integration: show price preview, include insurance estimation
# - eCommerce integration: disclaimer, visibility flags
# - Membership: stacking policy
# - Sequences: link sequence code untuk objek terkait
#
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


# =============================================================================
# RES COMPANY (penyimpanan nilai konfigurasi per perusahaan)
# =============================================================================
class ResCompany(models.Model):
    _inherit = "res.company"

    # ---- Defaults / Linkages
    clinic_default_pricelist_id = fields.Many2one(
        "clinic.treatment.pricelist",
        string="Default Clinic Pricelist",
        help="Pricelist klinik default untuk estimasi harga (Booking/Back-office/eCommerce)."
    )
    clinic_default_service_category_id = fields.Many2one(
        "product.category",
        string="Default Service Product Category",
        help="Kategori produk default saat modul membuat product.template tipe Service untuk Treatment/Bundle."
    )

    # ---- Pricing Bridge / Policy
    clinic_enable_bridge_pricing = fields.Boolean(
        string="Enable Bridge Pricing",
        default=True,
        help="Aktifkan perhitungan harga via Clinic Pricelist Bridge (membership, promo, surcharge, insurance). "
             "Jika nonaktif, sistem fallback ke Odoo Pricelist standar atau Base Price."
    )
    clinic_rounding_policy = fields.Selection(
        selection=[
            ("currency", "Currency Rounding"),
            ("half_up", "Half Up (0.5 → 1)"),
            ("down", "Round Down"),
            ("up", "Round Up"),
        ],
        string="Rounding Policy",
        default="currency",
        help="Kebijakan pembulatan yang dipakai oleh engine/bridge pricing."
    )
    clinic_pricing_tax_included = fields.Boolean(
        string="Prices Include Taxes (UI Flag)",
        default=False,
        help="Penanda UI untuk menampilkan harga termasuk pajak. Perhitungan final tetap ikut pajak & fiscal position."
    )

    # ---- Defaults pada Treatment
    clinic_default_surcharge_applicable = fields.Boolean(
        string="Default Surcharge Applicable on Treatment",
        default=True,
        help="Default flag 'Surcharge Applicable' saat membuat Treatment baru."
    )
    clinic_default_insurance_applicable = fields.Boolean(
        string="Default Insurance Applicable on Treatment",
        default=False,
        help="Default flag 'Insurance Applicable' saat membuat Treatment baru."
    )

    # ---- Booking Integration
    clinic_booking_price_preview = fields.Boolean(
        string="Show Price Preview in Booking",
        default=True,
        help="Tampilkan estimasi harga di form Booking menggunakan Pricelist/Bridge."
    )
    clinic_booking_include_insurance = fields.Boolean(
        string="Include Insurance in Booking Estimation",
        default=False,
        help="Saat estimasi di Booking, perhitungkan insurance (coverage/co-pay) jika tersedia."
    )

    # ---- eCommerce / Portal Integration
    clinic_ecom_show_disclaimer = fields.Boolean(
        string="Show Pricing Disclaimer on Portal",
        default=True,
        help="Tampilkan catatan bahwa harga portal dapat berubah karena surcharge/insurance saat eksekusi."
    )
    clinic_ecom_disclaimer = fields.Text(
        string="Portal Pricing Disclaimer",
        default="Harga di portal adalah estimasi dan belum termasuk surcharge (level terapis, ruangan, prime time) "
                "atau penyesuaian asuransi. Harga final ditentukan saat layanan dieksekusi.",
        help="Pesan yang muncul pada halaman portal/eCommerce terkait penjelasan harga."
    )

    # ---- Membership Integration
    clinic_membership_stacking = fields.Selection(
        selection=[
            ("allow_stack", "Allow Stacking (combine with other promos)"),
            ("exclusive", "Exclusive (no stacking)"),
        ],
        string="Membership Stacking Policy",
        default="exclusive",
        help="Kebijakan stacking benefit membership terhadap promo lain."
    )

    # ---- Sequences (link agar mudah konfig dari Settings)
    clinic_seq_treatment_code_id = fields.Many2one(
        "ir.sequence", string="Sequence: Treatment Code"
    )
    clinic_seq_treatment_category_code_id = fields.Many2one(
        "ir.sequence", string="Sequence: Treatment Category Code"
    )
    clinic_seq_treatment_tag_code_id = fields.Many2one(
        "ir.sequence", string="Sequence: Treatment Tag Code"
    )
    clinic_seq_treatment_bundle_code_id = fields.Many2one(
        "ir.sequence", string="Sequence: Treatment Bundle Code"
    )
    clinic_seq_treatment_pricelist_code_id = fields.Many2one(
        "ir.sequence", string="Sequence: Treatment Pricelist Code"
    )
    clinic_seq_treatment_attribute_code_id = fields.Many2one(
        "ir.sequence", string="Sequence: Treatment Attribute Code"
    )
    clinic_seq_treatment_attribute_value_code_id = fields.Many2one(
        "ir.sequence", string="Sequence: Treatment Attribute Value Code"
    )


# =============================================================================
# RES CONFIG SETTINGS (UI untuk mengedit nilai di atas per company)
# =============================================================================
class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ---- Related ke res.company agar multi-company & editable di Settings
    clinic_default_pricelist_id = fields.Many2one(
        related="company_id.clinic_default_pricelist_id",
        readonly=False,
        string="Default Clinic Pricelist"
    )
    clinic_default_service_category_id = fields.Many2one(
        related="company_id.clinic_default_service_category_id",
        readonly=False,
        string="Default Service Product Category"
    )

    clinic_enable_bridge_pricing = fields.Boolean(
        related="company_id.clinic_enable_bridge_pricing",
        readonly=False,
        string="Enable Bridge Pricing"
    )
    clinic_rounding_policy = fields.Selection(
        related="company_id.clinic_rounding_policy",
        readonly=False,
        string="Rounding Policy"
    )
    clinic_pricing_tax_included = fields.Boolean(
        related="company_id.clinic_pricing_tax_included",
        readonly=False,
        string="Prices Include Taxes (UI Flag)"
    )

    clinic_default_surcharge_applicable = fields.Boolean(
        related="company_id.clinic_default_surcharge_applicable",
        readonly=False,
        string="Default Surcharge Applicable"
    )
    clinic_default_insurance_applicable = fields.Boolean(
        related="company_id.clinic_default_insurance_applicable",
        readonly=False,
        string="Default Insurance Applicable"
    )

    clinic_booking_price_preview = fields.Boolean(
        related="company_id.clinic_booking_price_preview",
        readonly=False,
        string="Show Price Preview in Booking"
    )
    clinic_booking_include_insurance = fields.Boolean(
        related="company_id.clinic_booking_include_insurance",
        readonly=False,
        string="Include Insurance in Booking Estimation"
    )

    clinic_ecom_show_disclaimer = fields.Boolean(
        related="company_id.clinic_ecom_show_disclaimer",
        readonly=False,
        string="Show Portal Pricing Disclaimer"
    )
    clinic_ecom_disclaimer = fields.Text(
        related="company_id.clinic_ecom_disclaimer",
        readonly=False,
        string="Portal Pricing Disclaimer"
    )

    clinic_membership_stacking = fields.Selection(
        related="company_id.clinic_membership_stacking",
        readonly=False,
        string="Membership Stacking Policy"
    )

    clinic_seq_treatment_code_id = fields.Many2one(
        related="company_id.clinic_seq_treatment_code_id",
        readonly=False,
        string="Sequence: Treatment Code",
        domain="[('company_id','in',[False, company_id])]"
    )
    clinic_seq_treatment_category_code_id = fields.Many2one(
        related="company_id.clinic_seq_treatment_category_code_id",
        readonly=False,
        string="Sequence: Treatment Category Code",
        domain="[('company_id','in',[False, company_id])]"
    )
    clinic_seq_treatment_tag_code_id = fields.Many2one(
        related="company_id.clinic_seq_treatment_tag_code_id",
        readonly=False,
        string="Sequence: Treatment Tag Code",
        domain="[('company_id','in',[False, company_id])]"
    )
    clinic_seq_treatment_bundle_code_id = fields.Many2one(
        related="company_id.clinic_seq_treatment_bundle_code_id",
        readonly=False,
        string="Sequence: Treatment Bundle Code",
        domain="[('company_id','in',[False, company_id])]"
    )
    clinic_seq_treatment_pricelist_code_id = fields.Many2one(
        related="company_id.clinic_seq_treatment_pricelist_code_id",
        readonly=False,
        string="Sequence: Treatment Pricelist Code",
        domain="[('company_id','in',[False, company_id])]"
    )
    clinic_seq_treatment_attribute_code_id = fields.Many2one(
        related="company_id.clinic_seq_treatment_attribute_code_id",
        readonly=False,
        string="Sequence: Treatment Attribute Code",
        domain="[('company_id','in',[False, company_id])]"
    )
    clinic_seq_treatment_attribute_value_code_id = fields.Many2one(
        related="company_id.clinic_seq_treatment_attribute_value_code_id",
        readonly=False,
        string="Sequence: Treatment Attribute Value Code",
        domain="[('company_id','in',[False, company_id])]"
    )

    # ---- Bantuan Navigasi (aksi tombol pintar di view settings)
    def action_open_default_pricelist(self):
        """Buka Pricelist klinik default (jika ada)."""
        self.ensure_one()
        pl = self.clinic_default_pricelist_id
        if not pl or not pl.exists():
            raise ValidationError(_("Default Clinic Pricelist is not set."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic Pricelist"),
            "res_model": "clinic.treatment.pricelist",
            "res_id": pl.id,
            "view_mode": "form",
        }

    def action_open_sequences(self):
        """Buka daftar sequence terkait modul ini (filter by company)."""
        self.ensure_one()
        seq_ids = [
            self.clinic_seq_treatment_code_id.id,
            self.clinic_seq_treatment_category_code_id.id,
            self.clinic_seq_treatment_tag_code_id.id,
            self.clinic_seq_treatment_bundle_code_id.id,
            self.clinic_seq_treatment_pricelist_code_id.id,
            self.clinic_seq_treatment_attribute_code_id.id,
            self.clinic_seq_treatment_attribute_value_code_id.id,
        ]
        seq_ids = [sid for sid in seq_ids if sid]
        domain = [("id", "in", seq_ids)] if seq_ids else [("code", "ilike", "clinic.")]
        return {
            "type": "ir.actions.act_window",
            "name": _("ClinicOne Sequences"),
            "res_model": "ir.sequence",
            "view_mode": "list,form",
            "domain": domain,
            "context": {"search_default_group_by_company_id": 1},
        }

    # ---- Validations / Onchange
    @api.constrains("clinic_ecom_disclaimer")
    def _check_disclaimer_length(self):
        for rec in self:
            if rec.clinic_ecom_disclaimer and len(rec.clinic_ecom_disclaimer) > 2000:
                raise ValidationError(_("Portal Pricing Disclaimer is too long (max 2000 chars)."))

    @api.onchange("clinic_enable_bridge_pricing")
    def _onchange_bridge_toggle(self):
        for rec in self:
            # Jika bridge dimatikan, tetap biarkan flags lain, tapi berikan peringatan ringan
            if not rec.clinic_enable_bridge_pricing:
                return {
                    "warning": {
                        "title": _("Bridge Pricing is disabled"),
                        "message": _(
                            "Bridge Pricing is turned off. System will fallback to Odoo Pricelist or Base Price. "
                            "Membership, Surcharge, and Insurance engines may not apply."
                        ),
                    }
                }

    # ---- Helper untuk defaulting di create product template dari Treatment/Bundle
    @api.model
    def clinic_prepare_service_product_defaults(self, company):
        """Dipanggil oleh model lain saat auto-create product.template Service.
        Return dict minimal: {'categ_id': ..., 'taxes_id': ...} dsb sesuai kebutuhan.
        """
        company = company or self.env.company
        categ = company.clinic_default_service_category_id
        vals = {}
        if categ:
            vals["categ_id"] = categ.id
        # Tambah logika pajak default jika dibutuhkan di masa depan (mengambil dari company/l10n)
        return vals

