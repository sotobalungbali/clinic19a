# -*- coding: utf-8 -*-
"""
patient_allergy.py
- Kamus alergen: clinic.allergen.category, clinic.allergen
- Alergi pasien: clinic.patient.allergy
- Reaksi alergi pasien (opsional, ringkas): clinic.patient.allergy.reaction

Catatan integrasi:
- Menghindari hard-dependency. Gunakan helper _has_model(env, 'model.name') sebelum referensi model lain.
- Mapping opsional ke product.product (jika inventory terpasang), ke encounter (jika clinic_encounter terpasang).
- Tetap ringkas di modul ini. Detail alergi per encounter/triase masuk ke modul lain (clinic_encounter/clinic_triage_vitals).
"""
from datetime import datetime, date

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =====================================================================
# Helper kecil untuk cek ketersediaan model lintas-modul secara aman
# =====================================================================
def _has_model(env, model_name):
    try:
        env[model_name]
        return True
    except KeyError:
        return False


# =====================================================================
# Kategori Alergen
# =====================================================================
class ClinicAllergenCategory(models.Model):
    _name = "clinic.allergen.category"
    _description = "Allergen Category"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        help="Optional short code (e.g., DRUG, FOOD, LATEX, ENV)."
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _constraint_cat_code_unique = models.Constraint(
        'unique(code)',
        'Allergen Category code must be unique.',
    )


# =====================================================================
# Kamus Alergen
# =====================================================================
class ClinicAllergen(models.Model):
    _name = "clinic.allergen"
    _description = "Allergen"
    _order = "category_id, name"

    name = fields.Char(required=True, translate=True)
    category_id = fields.Many2one(
        "clinic.allergen.category", string="Category", ondelete="restrict", index=True
    )
    active = fields.Boolean(default=True, index=True)
    commonness = fields.Selection(
        [
            ("common", "Common"),
            ("uncommon", "Uncommon"),
            ("rare", "Rare"),
            ("unknown", "Unknown"),
        ],
        default="unknown",
        help="Prevalence indicator for information only.",
    )
    synonyms = fields.Char(
        help="Comma-separated synonyms for search convenience (e.g., 'amox, amoxycillin')."
    )

    # Integrasi opsional ke inventory (product.product)
    product_id = fields.Many2one(
        "product.product",
        string="Product (if applicable)",
        help="Link to a product if this allergen is a specific drug/item (requires product).",
    )

    # Visualisasi (label kartu)
    barcode_symbology = fields.Selection(
        [
            ("none", "None"),
            ("code128", "Code128"),
            ("qrcode", "QR Code"),
        ],
        default="none",
    )

    _constraint_allergen_unique = models.Constraint(
        'unique(name, category_id)',
        'Allergen must be unique in its category.',
    )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        """Jika user memilih product, isi nama alergennya bila kosong."""
        for rec in self:
            if rec.product_id and not rec.name:
                rec.name = rec.product_id.display_name or rec.product_id.name


# =====================================================================
# Katalog gejala/reaksi (opsional, ringkas)
# =====================================================================
class ClinicAllergyReactionType(models.Model):
    _name = "clinic.allergy.reaction.type"
    _description = "Allergy Reaction Type"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(help="Short code (e.g., RASH, HIVES, ANAPHYLAXIS)")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _constraint_rxn_type_code_unique = models.Constraint(
        'unique(code)',
        'Reaction type code must be unique.',
    )


# =====================================================================
# Alergi Pasien (ringkas di level master pasien)
# =====================================================================
class ClinicPatientAllergy(models.Model):
    _name = "clinic.patient.allergy"
    _description = "Patient Allergy"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "is_critical DESC, severity DESC, create_date DESC"

    # -----------------------------------
    # Scope & Relasi utama
    # -----------------------------------
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="patient_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )

    # Kamus alergen (preferred)
    allergen_id = fields.Many2one(
        "clinic.allergen",
        string="Allergen",
        ondelete="restrict",
        index=True,
        tracking=True,
        help="Select from allergen dictionary for consistency."
    )
    category_id = fields.Many2one(
        "clinic.allergen.category",
        string="Category",
        ondelete="restrict",
        index=True,
        tracking=True,
        help="Derived from allergen; can be set manually for free-text allergen.",
    )
    # Free-text jika belum ada di kamus
    allergen_name = fields.Char(
        string="Allergen (Text)",
        tracking=True,
        help="Use when the allergen is not available in the dictionary.",
    )

    # Integrasi opsional: product.product (obat, kosmetik spesifik)
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        help="If allergen refers to a specific product (requires product).",
    )

    # -----------------------------------
    # Status klinis (ringkas)
    # -----------------------------------
    status = fields.Selection(
        [
            ("active", "Active"),
            ("inactive", "Inactive"),
            ("resolved", "Resolved"),
            ("entered_in_error", "Entered in Error"),
        ],
        default="active",
        tracking=True,
    )
    verification_status = fields.Selection(
        [
            ("unconfirmed", "Unconfirmed"),
            ("confirmed", "Confirmed"),
            ("refuted", "Refuted"),
        ],
        default="unconfirmed",
        tracking=True,
        help="Verification status indicates whether the allergy is confirmed/refuted.",
    )
    severity = fields.Selection(
        [
            ("mild", "Mild"),
            ("moderate", "Moderate"),
            ("severe", "Severe"),
            ("life_threatening", "Life-threatening"),
            ("unknown", "Unknown"),
        ],
        default="unknown",
        tracking=True,
    )
    criticality = fields.Selection(
        [
            ("low", "Low"),
            ("high", "High"),
            ("indeterminate", "Indeterminate"),
        ],
        default="indeterminate",
        tracking=True,
        help="Clinical assessment of the potential hazard from future exposure.",
    )
    is_critical = fields.Boolean(
        string="Critical",
        compute="_compute_is_critical",
        store=True,
        help="True when severity is severe/life-threatening or criticality is high."
    )

    # -----------------------------------
    # Reaksi & Riwayat ringkas
    # -----------------------------------
    reaction_summary = fields.Text(
        help="Free-text summary of known reactions (e.g., 'Rash, shortness of breath')."
    )
    reaction_ids = fields.One2many(
        "clinic.patient.allergy.reaction",
        "allergy_id",
        string="Reactions",
    )
    worst_reaction = fields.Selection(
        selection=lambda self: self._fields["severity"].selection,
        compute="_compute_worst_reaction",
        store=True,
    )

    # -----------------------------------
    # Tanggal & sumber
    # -----------------------------------
    recorded_date = fields.Datetime(
        default=lambda self: fields.Datetime.now(),
        string="Recorded On",
        tracking=True,
    )
    recorded_by = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        string="Recorded By",
        tracking=True,
    )
    onset_date = fields.Date(string="Onset Date")
    last_occurrence_date = fields.Date(string="Last Occurrence")
    source = fields.Selection(
        [
            ("self_report", "Self-report"),
            ("provider", "Provider"),
            ("external_record", "External Record"),
            ("other", "Other"),
        ],
        default="self_report",
    )

    # -----------------------------------
    # Tampilan & lampiran
    # -----------------------------------
    display_name = fields.Char(compute="_compute_display_name", store=True)
    attachment_count = fields.Integer(compute="_compute_attachment_count")

    notes = fields.Text()

    # -----------------------------------
    # Unik & indexing
    # -----------------------------------
    _constraint_uniq_patient_allergen = models.Constraint(
        'unique(patient_id, allergen_id)',
        'This allergen already exists for the patient.',
    )

    _constraint_uniq_patient_allergen_text = models.Constraint(
        'unique(patient_id, allergen_name, category_id)',
        'This allergen text already exists for the patient in the same category.',
    )

    # =========================================================
    # COMPUTE
    # =========================================================
    @api.depends("allergen_id", "allergen_name", "severity", "status")
    def _compute_display_name(self):
        for rec in self:
            allergen = rec.allergen_id.name if rec.allergen_id else (rec.allergen_name or _("Unknown"))
            sev = dict(self._fields["severity"].selection).get(rec.severity or "unknown")
            st = dict(self._fields["status"].selection).get(rec.status or "active")
            rec.display_name = f"{allergen} [{sev} • {st}]"

    @api.depends("reaction_ids.severity")
    def _compute_worst_reaction(self):
        rank = {"unknown": 0, "mild": 1, "moderate": 2, "severe": 3, "life_threatening": 4}
        for rec in self:
            worst = "unknown"
            for rx in rec.reaction_ids:
                if rank.get(rx.severity, 0) > rank.get(worst, 0):
                    worst = rx.severity
            rec.worst_reaction = worst

    @api.depends("severity", "criticality")
    def _compute_is_critical(self):
        for rec in self:
            rec.is_critical = (rec.severity in {"severe", "life_threatening"}) or (rec.criticality == "high")

    def _compute_attachment_count(self):
        Attachment = self.env["ir.attachment"]
        for rec in self:
            rec.attachment_count = Attachment.search_count([
                ("res_model", "=", self._name),
                ("res_id", "=", rec.id),
            ])

    # =========================================================
    # ONCHANGE / HELPERS
    # =========================================================
    @api.onchange("allergen_id")
    def _onchange_allergen_id(self):
        for rec in self:
            if rec.allergen_id:
                # Turunkan kategori & nama jika kosong
                if not rec.category_id and rec.allergen_id.category_id:
                    rec.category_id = rec.allergen_id.category_id
                if not rec.allergen_name:
                    rec.allergen_name = rec.allergen_id.name
                # Sinkron product bila ada
                if rec.allergen_id.product_id and not rec.product_id:
                    rec.product_id = rec.allergen_id.product_id

    @api.onchange("product_id")
    def _onchange_product_id(self):
        """Jika user pilih product langsung, bantu isi allergen_name jika kosong."""
        for rec in self:
            if rec.product_id and not rec.allergen_name:
                rec.allergen_name = rec.product_id.display_name or rec.product_id.name

    # =========================================================
    # CONSTRAINTS
    # =========================================================
    @api.constrains("onset_date", "last_occurrence_date")
    def _check_dates(self):
        for rec in self:
            if rec.onset_date and rec.last_occurrence_date and rec.last_occurrence_date < rec.onset_date:
                raise ValidationError(_("Last Occurrence cannot be before Onset Date."))

    @api.constrains("status", "last_occurrence_date")
    def _check_resolved_has_last_occurrence(self):
        for rec in self:
            if rec.status == "resolved" and not rec.last_occurrence_date:
                # tidak terlalu keras—boleh diabaikan jika organisasi tidak memerlukan
                # raise ValidationError(_("Resolved allergy should have a Last Occurrence date."))
                pass

    # =========================================================
    # CRUD OVERRIDES
    # =========================================================
    @api.model_create_multi
    def create(self, vals_list):
        # Normalisasi awal
        for vals in vals_list:
            # Default category dari allergen
            if not vals.get("category_id") and vals.get("allergen_id"):
                allergen = self.env["clinic.allergen"].browse(vals["allergen_id"])
                if allergen and allergen.category_id:
                    vals["category_id"] = allergen.category_id.id
            # Isi allergen_name dari allergen jika kosong
            if not vals.get("allergen_name") and vals.get("allergen_id"):
                allergen = self.env["clinic.allergen"].browse(vals["allergen_id"])
                if allergen:
                    vals["allergen_name"] = allergen.name
            # Recorded info default
            vals.setdefault("recorded_by", self.env.user.id)
            vals.setdefault("recorded_date", fields.Datetime.now())

        recs = super().create(vals_list)

        # Pasca-buat: sinkronisasi ringan, mapping opsional ke partner note
        for rec in recs:
            rec._sync_patient_flags()
            rec._maybe_map_allergy_note_to_partner()

        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            rec._sync_patient_flags()
            # Update note partner jika nilai summary berubah
            if any(k in vals for k in ["reaction_summary", "status", "severity", "criticality", "allergen_name", "allergen_id"]):
                rec._maybe_map_allergy_note_to_partner()
        return res

    # =========================================================
    # UTILITIES / INTEGRATION
    # =========================================================
    def _sync_patient_flags(self):
        """Bisa digunakan untuk set indikator agregat di patient (jika nanti diperlukan).
        Saat ini, tidak mengubah field di clinic.patient agar tetap low-coupling.
        """
        return True

    def _maybe_map_allergy_note_to_partner(self):
        """Mapping ringan ke res.partner jika organisasi memakai field catatan alergi di partner.
        Tidak menambah dependensi: hanya jika field tersedia.
        """
        for rec in self:
            partner = rec.patient_id.partner_id
            if not partner:
                continue
            # Kumpulkan daftar alergi aktif sebagai ringkasan
            active_allergies = rec.patient_id.allergy_ids.filtered(lambda a: a.status == "active")
            summary_list = []
            for a in active_allergies:
                sev = dict(self._fields["severity"].selection).get(a.severity or "unknown")
                name = a.allergen_id.name if a.allergen_id else (a.allergen_name or _("Unknown"))
                summary_list.append(f"{name} ({sev})")
            summary = ", ".join(summary_list)

            # Mapping ke field partner jika ada
            if hasattr(partner, "medical_allergy_note"):
                if partner.medical_allergy_note != summary:
                    partner.medical_allergy_note = summary
            elif hasattr(partner, "comment"):  # fallback ke internal note
                # Jangan overwrite full comment; tambahkan key 'Allergies:' bila ada
                base = partner.comment or ""
                lines = [l for l in base.split("\n") if not l.startswith("Allergies:")]
                if summary:
                    lines.append(f"Allergies: {summary}")
                partner.comment = "\n".join(lines).strip()

    # =========================================================
    # AKSI / SMART BUTTONS
    # =========================================================
    def action_open_attachments(self):
        self.ensure_one()
        domain = [("res_model", "=", self._name), ("res_id", "=", self.id)]
        action = self.env.ref("base.action_attachment", raise_if_not_found=False)
        result = action and action.read()[0] or {
            "type": "ir.actions.act_window",
            "name": _("Attachments"),
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "target": "current",
        }
        result["domain"] = domain
        return result

    # def action_open_related_encounters(self):
    #     """Buka encounter yang menyinggung alergi ini (jika modul encounter menyimpan linknya)."""
    #     self.ensure_one()
    #     Encounter = False
    #     # Kemungkinan penyimpanan:
    #     # - clinic.encounter (field many2many ke allergies) atau
    #     # - clinic.encounter.allergy (model relasional).
    #     if _has_model(self.env, "clinic.encounter"):
    #         Encounter = self.env["clinic.encounter"]
    #     if not Encounter:
    #         raise UserError(_("Module 'clinic_encounter' is not installed."))

    #     # Coba domain generik: patient + teks allergen
    #     domain = [("patient_id", "=", self.patient_id.id)]
    #     # Jika encounter menyimpan m2m 'allergy_ids', kita bisa tambah filter tersebut:
    #     if "allergy_ids" in Encounter._fields:
    #         domain = ["&"] + domain + [("allergy_ids", "in", [self.id])]

    #     action = self.env.ref(
    #         "clinic_encounter.action_clinic_encounter",
    #         raise_if_not_found=False,
    #     )
    #     result = action and action.read()[0] or {
    #         "type": "ir.actions.act_window",
    #         "name": _("Encounters"),
    #         "res_model": "clinic.encounter",
    #         "view_mode": "tree,form,calendar,kanban",
    #         "target": "current",
    #     }
    #     result["domain"] = domain
    #     ctx = result.get("context", {}) or {}
    #     ctx.update({
    #         "search_default_patient_id": self.patient_id.id,
    #         "default_patient_id": self.patient_id.id,
    #     })
    #     result["context"] = ctx
    #     return result

    def action_mark_resolved(self):
        for rec in self:
            rec.status = "resolved"
            if not rec.last_occurrence_date:
                rec.last_occurrence_date = date.today()
        return True

    # =========================================================
    # NAME GET / SEARCH
    # =========================================================
    def name_get(self):
        res = []
        for rec in self:
            name = rec.allergen_id.name if rec.allergen_id else (rec.allergen_name or _("Unknown"))
            sev = dict(self._fields["severity"].selection).get(rec.severity or "unknown")
            res.append((rec.id, f"{name} ({sev})"))
        return res


# =====================================================================
# Reaksi Alergi Pasien (opsional, ringkas)
# =====================================================================
class ClinicPatientAllergyReaction(models.Model):
    _name = "clinic.patient.allergy.reaction"
    _description = "Patient Allergy Reaction"
    _inherit = ["mail.thread"]
    _order = "onset_datetime DESC, create_date DESC"

    allergy_id = fields.Many2one(
        "clinic.patient.allergy",
        string="Allergy",
        required=True,
        ondelete="cascade",
        index=True,
    )
    patient_id = fields.Many2one(
        "clinic.patient",
        related="allergy_id.patient_id",
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="allergy_id.company_id",
        store=True,
        readonly=True,
    )

    reaction_type_id = fields.Many2one(
        "clinic.allergy.reaction.type",
        string="Reaction",
        ondelete="restrict",
        index=True,
    )
    reaction_text = fields.Char(
        string="Reaction (Text)",
        help="Optional free-text when not using the reaction type dictionary."
    )
    description = fields.Text(help="Narrative details of the reaction.")

    severity = fields.Selection(
        [
            ("mild", "Mild"),
            ("moderate", "Moderate"),
            ("severe", "Severe"),
            ("life_threatening", "Life-threatening"),
            ("unknown", "Unknown"),
        ],
        default="unknown",
        tracking=True,
    )

    onset_datetime = fields.Datetime(string="Onset Date/Time", tracking=True)
    exposure_route = fields.Selection(
        [
            ("ingestion", "Ingestion"),
            ("inhalation", "Inhalation"),
            ("topical", "Topical"),
            ("injection", "Injection"),
            ("unknown", "Unknown"),
        ],
        default="unknown",
    )
    exposure_dose = fields.Char(help="Dose/concentration at exposure (if known).")

    outcome = fields.Selection(
        [
            ("recovered", "Recovered"),
            ("persistent", "Persistent"),
            ("unknown", "Unknown"),
            ("fatal", "Fatal"),
        ],
        default="unknown",
    )

    recorded_date = fields.Datetime(default=lambda self: fields.Datetime.now(), string="Recorded On")
    recorded_by = fields.Many2one("res.users", default=lambda self: self.env.user, string="Recorded By")

    attachment_count = fields.Integer(compute="_compute_attachment_count")

    @api.constrains("onset_datetime")
    def _check_onset_datetime(self):
        for rec in self:
            # Hanya validasi ringan: onset tidak boleh di masa depan jauh
            # (beberapa organisasi ingin melarang masa depan — fleksibel di sini)
            pass

    def _compute_attachment_count(self):
        Attachment = self.env["ir.attachment"]
        for rec in self:
            rec.attachment_count = Attachment.search_count([
                ("res_model", "=", self._name),
                ("res_id", "=", rec.id),
            ])

    def action_open_attachments(self):
        self.ensure_one()
        action = self.env.ref("base.action_attachment", raise_if_not_found=False)
        result = action and action.read()[0] or {
            "type": "ir.actions.act_window",
            "name": _("Attachments"),
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "target": "current",
        }
        result["domain"] = [("res_model", "=", self._name), ("res_id", "=", self.id)]
        return result

