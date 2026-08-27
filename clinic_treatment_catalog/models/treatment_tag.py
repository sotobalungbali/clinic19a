# -*- coding: utf-8 -*-
# ClinicOne - Treatment Catalog & Pricing
# File: models/treatment_tag.py
#
# Fitur:
# - Tag bebas untuk segmentasi treatment (promo, marketing, ecommerce, membership, insurance, reporting, dll.)
# - Multi-company aware, tracking perubahan penting.
# - Smart button untuk membuka daftar treatment yang memiliki tag ini.
# - Guard agar tidak dihapus jika masih dipakai (sarankan archive).
# - Audit event terstruktur bila modul clinic_audit tersedia; fallback ke chatter.
#
# Integrasi lintas modul (tanpa hard dependency):
# - clinic.treatment.catalog  → relasi M2M via field tag_ids
# - clinic_reports/dashboard  → agregasi per tag
# - clinic_booking/ecommerce  → filter/penawaran berdasarkan tag
# - clinic_membership/insurance/promo → scoping via tag (scope)
# - clinic_marketing          → segmentasi kampanye

from odoo import api, fields, models, _, tools
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class ClinicTreatmentTag(models.Model):
    _name = "clinic.treatment.tag"
    _description = "Clinic Treatment Tag"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Basic
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Tag Name",
        required=True,
        tracking=True,
        index=True,
        help="Nama tag untuk segmentasi/penandaan treatment."
    )
    code = fields.Char(
        string="Code",
        copy=False,
        index=True,
        tracking=True,
        help="Kode unik per perusahaan (terisi otomatis dari sequence bila tersedia)."
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Urutan tampil di list/kanban."
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        tracking=True
    )
    color = fields.Integer(
        string="Color Index",
        help="Warna di kanban."
    )
    emoji = fields.Char(
        string="Emoji",
        help="Opsional, emoji singkat untuk tampilan (mis. 🔥, ⭐, 💎)."
    )

    # -------------------------------------------------------------------------
    # Company
    # -------------------------------------------------------------------------
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True
    )

    # -------------------------------------------------------------------------
    # Scoping & Presentation
    # -------------------------------------------------------------------------
    scope = fields.Selection(
        selection=[
            ("generic", "Generic"),
            ("promo", "Promotion/Seasonal/Campaign"),
            ("marketing", "Marketing/Segmentation"),
            ("ecommerce", "eCommerce/Portal"),
            ("membership", "Membership Tier/Benefit"),
            ("insurance", "Insurance/Coverage"),
            ("reporting", "Reporting/Analytics"),
        ],
        string="Scope",
        default="generic",
        required=True,
        help=(
            "Batasan penggunaan tag agar konsisten lintas modul.\n"
            "- Generic: bebas\n"
            "- Promo: diskon/kampanye musiman\n"
            "- Marketing: segmentasi pelanggan & kampanye\n"
            "- eCommerce: visibilitas/penawaran di website/portal\n"
            "- Membership: manfaat berbasis tier\n"
            "- Insurance: cakupan & kebijakan asuransi\n"
            "- Reporting: agregasi & analitik"
        )
    )
    description = fields.Html(
        string="Description",
        sanitize=True
    )
    image_1920 = fields.Image(
        string="Image",
        max_width=1920,
        max_height=1920
    )

    # -------------------------------------------------------------------------
    # Usage Counters
    # -------------------------------------------------------------------------
    treatment_count = fields.Integer(
        string="Treatments Using This Tag",
        compute="_compute_treatment_count",
        help="Jumlah treatment yang memiliki tag ini."
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    _code_company_uniq = models.Constraint(
        "unique(code, company_id)",
        "Code must be unique per company.",
    )

    @api.constrains("name")
    def _check_name_not_empty(self):
        for rec in self:
            if not rec.name or not rec.name.strip():
                raise ValidationError(_("Tag Name is required."))

    # =========================================================================
    # COMPUTES
    # =========================================================================
    def _compute_treatment_count(self):
        Treatment = self.env["clinic.treatment.catalog"]
        for rec in self:
            rec.treatment_count = Treatment.search_count([("tag_ids", "in", rec.id)])

    # =========================================================================
    # ORM OVERRIDES
    # =========================================================================
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env.ref("clinic_treatment_catalog.seq_treatment_tag_code", raise_if_not_found=False)
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            if not vals.get("code") and seq:
                vals["code"] = seq._next()
        recs = super().create(vals_list)
        recs._audit_event("create")
        return recs

    def write(self, vals):
        res = super().write(vals)
        tracked = {"name", "code", "scope", "active", "sequence", "company_id", "emoji", "color"}
        if set(vals).intersection(tracked):
            self._audit_event("write", changed_fields=list(set(vals).intersection(tracked)))
        return res

    def unlink(self):
        """Cegah menghapus tag jika masih dipakai oleh treatment.
        Sarankan untuk di-archive (active=False) bila ingin menyembunyikan.
        """
        Treatment = self.env["clinic.treatment.catalog"]
        for rec in self:
            if Treatment.search_count([("tag_ids", "in", rec.id)]) > 0:
                raise UserError(_("You cannot delete a tag that is used by treatments. Archive it instead."))
        return super().unlink()

    # =========================================================================
    # HELPERS / AUDIT
    # =========================================================================
    def _audit_event(self, action, changed_fields=None):
        """Kirim log ke clinic.audit.event bila ada; fallback ke chatter."""
        self.message_post(body=_("Tag %s: %s") % (action, ", ".join(changed_fields or [])))
        audit_model = self.env.registry.get("clinic.audit.event")
        if not audit_model:
            return
        for rec in self:
            try:
                self.env["clinic.audit.event"].sudo().create({
                    "name": "tag.%s" % action,
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

    # =========================================================================
    # ACTIONS / SMART BUTTONS
    # =========================================================================
    def action_open_treatments(self):
        """Smart button: buka daftar treatment yang memiliki tag ini."""
        self.ensure_one()
        action = self.env.ref("clinic_treatment_catalog.action_treatment_tree", raise_if_not_found=False)
        domain = [("tag_ids", "in", self.id)]
        name = _("Treatments with Tag: %s") % (self.name,)
        if action:
            res = action.read()[0]
            res["name"] = name
            res["domain"] = domain
            return res
        # Fallback generic action
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": "clinic.treatment.catalog",
            "view_mode": "list,form",
            "domain": domain,
        }

    # =========================================================================
    # NAME GET / SEARCH
    # =========================================================================
    def _clinic_display_label(self):
        self.ensure_one()
        label = "%s %s" % (self.emoji, self.name) if self.emoji else self.name
        return "[%s] %s" % (self.code, label) if self.code else label

    @api.depends("code", "name", "emoji")
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

