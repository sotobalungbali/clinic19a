
# -*- coding: utf-8 -*-
"""
patient_condition.py

- Kamus kondisi: clinic.condition.category, clinic.condition, clinic.condition.code
- Kondisi pasien (problem list): clinic.patient.condition
- Episode/kejadian kondisi: clinic.patient.condition.episode

Integrasi aman:
- Gunakan _has_model untuk cek ketersediaan model lintas-modul (clinic_encounter, clinic_imaging, dll.)
- Action XML ID memakai fallback act_window dinamis jika tidak ditemukan.
"""
from datetime import date, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =====================================================================
# Helper: cek model ada/tidak di registry
# =====================================================================
def _has_model(env, model_name):
    try:
        env[model_name]
        return True
    except KeyError:
        return False


# =====================================================================
# Kategori Kondisi
# =====================================================================
class ClinicConditionCategory(models.Model):
    _name = "clinic.condition.category"
    _description = "Condition Category"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(help="Optional short code (e.g., DERM, CARDIO, ENDO, NEURO).")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _constraint_cond_cat_code_unique = models.Constraint(
        'unique(code)',
        'Condition Category code must be unique.',
    )


# =====================================================================
# Kamus Kondisi
# =====================================================================
class ClinicCondition(models.Model):
    _name = "clinic.condition"
    _description = "Condition"
    _order = "category_id, name"

    name = fields.Char(required=True, translate=True)
    category_id = fields.Many2one(
        "clinic.condition.category", string="Category", ondelete="restrict", index=True
    )
    active = fields.Boolean(default=True, index=True)
    chronic = fields.Boolean(
        help="Mark if this condition is generally chronic (for display/filtering)."
    )
    default_severity = fields.Selection(
        [
            ("mild", "Mild"),
            ("moderate", "Moderate"),
            ("severe", "Severe"),
            ("life_threatening", "Life-threatening"),
            ("unknown", "Unknown"),
        ],
        default="unknown",
    )
    synonyms = fields.Char(
        help="Comma-separated synonyms for search convenience."
    )

    # Kode standar (ICD/SNOMED/Other) via child table
    code_ids = fields.One2many("clinic.condition.code", "condition_id", string="Codes")

    _constraint_cond_unique = models.Constraint(
        'unique(name, category_id)',
        'Condition must be unique in its category.',
    )


class ClinicConditionCode(models.Model):
    _name = "clinic.condition.code"
    _description = "Condition Code"
    _order = "system, code"

    condition_id = fields.Many2one(
        "clinic.condition", required=True, ondelete="cascade", index=True
    )
    system = fields.Selection(
        [
            ("icd10", "ICD-10"),
            ("icd10cm", "ICD-10-CM"),
            ("icd9", "ICD-9"),
            ("snomed", "SNOMED-CT"),
            ("icpc2", "ICPC-2"),
            ("other", "Other"),
        ],
        required=True,
    )
    code = fields.Char(required=True)
    description = fields.Char(help="Optional description/title for the code.")

    _constraint_cond_code_unique = models.Constraint(
        'unique(condition_id, system, code)',
        'Code must be unique per condition/system.',
    )

    @api.depends("system", "code", "description")
    def _compute_display_name(self):
        """Preserve the clinical-code label under the Odoo 19 display-name API."""
        selection = dict(self._fields["system"].selection)
        for record in self:
            system_label = selection.get(record.system, record.system or "")
            label = f"{system_label}: {record.code or ''}".strip()
            if record.description:
                label = f"{label} • {record.description}"
            record.display_name = label

    def name_get(self):
        res = []
        for rec in self:
            sys = dict(self._fields["system"].selection).get(rec.system)
            label = f"{sys}: {rec.code}"
            if rec.description:
                label += f" • {rec.description}"
            res.append((rec.id, label))
        return res


# =====================================================================
# Kondisi Pasien (Problem List)
# =====================================================================
class ClinicPatientCondition(models.Model):
    _name = "clinic.patient.condition"
    _description = "Patient Condition"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "is_chronic DESC, status DESC, severity DESC, onset_date DESC, create_date DESC"

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

    # Kamus kondisi (preferred)
    condition_id = fields.Many2one(
        "clinic.condition",
        string="Condition",
        ondelete="restrict",
        index=True,
        tracking=True,
        help="Select from condition dictionary for consistency."
    )
    category_id = fields.Many2one(
        "clinic.condition.category",
        string="Category",
        ondelete="restrict",
        index=True,
        help="Derived from condition; can be set manually for free-text condition.",
    )
    # Free-text bila belum ada di kamus
    condition_name = fields.Char(
        string="Condition (Text)",
        tracking=True,
        help="Use when the condition is not available in the dictionary."
    )

    # Kode (opsional): pilih dari kamus atau custom code
    code_id = fields.Many2one(
        "clinic.condition.code",
        string="Primary Code",
        ondelete="set null",
        help="Link to a code in the dictionary, if applicable."
    )
    code_system = fields.Selection(
        selection=lambda self: self.env["clinic.condition.code"]._fields["system"].selection,
        string="Code System",
        help="Use with Code Value when not selecting a dictionary code."
    )
    code_value = fields.Char(string="Code Value", help="Custom code value (when not using dictionary code).")

    # -----------------------------------
    # Status klinis (FHIR-like)
    # -----------------------------------
    status = fields.Selection(
        [
            ("active", "Active"),
            ("recurrence", "Recurrence"),
            ("remission", "Remission"),
            ("resolved", "Resolved"),
            ("inactive", "Inactive"),
            ("entered_in_error", "Entered in Error"),
        ],
        default="active",
        tracking=True,
    )
    verification_status = fields.Selection(
        [
            ("unconfirmed", "Unconfirmed"),
            ("provisional", "Provisional"),
            ("differential", "Differential"),
            ("confirmed", "Confirmed"),
            ("refuted", "Refuted"),
            ("entered_in_error", "Entered in Error"),
        ],
        default="unconfirmed",
        tracking=True,
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

    # Staging generik + free text
    stage = fields.Selection(
        [
            ("na", "N/A"),
            ("stage_1", "Stage I"),
            ("stage_2", "Stage II"),
            ("stage_3", "Stage III"),
            ("stage_4", "Stage IV"),
            ("stage_5", "Stage V"),
        ],
        default="na",
        tracking=True,
    )
    stage_text = fields.Char(string="Stage (Text)", help="Optional textual staging (e.g., TNM: T2N1M0).")

    # Lokasi/kelainan
    body_site = fields.Char(string="Body Site", help="e.g., 'Left forearm', 'Cervical spine'.")
    laterality = fields.Selection(
        [
            ("left", "Left"),
            ("right", "Right"),
            ("bilateral", "Bilateral"),
            ("midline", "Midline"),
            ("unknown", "Unknown"),
        ],
        default="unknown",
    )

    # Onset & resolusi
    onset_date = fields.Date(string="Onset Date", tracking=True)
    abatement_date = fields.Date(string="Abatement/Resolution Date", tracking=True)
    last_review_date = fields.Date(string="Last Clinical Review")

    # Kronisitas
    is_chronic = fields.Boolean(
        compute="_compute_is_chronic",
        store=True,
        help="True when dictionary marks chronic or duration exceeds threshold.",
    )
    chronic_threshold_days = fields.Integer(
        default=90,
        help="Heuristic: if duration (onset→today) exceeds this and not resolved → chronic.",
    )
    chronic_override = fields.Selection(
        [
            ("auto", "Auto"),
            ("force_chronic", "Force Chronic"),
            ("force_acute", "Force Acute"),
        ],
        default="auto",
        help="Override automatic chronic inference when necessary."
    )

    # Ringkasan & tampilan
    display_name = fields.Char(compute="_compute_display_name", store=True)
    notes = fields.Text()
    attachment_count = fields.Integer(compute="_compute_attachment_count")

    # Episode/kejadian terkait
    episode_ids = fields.One2many(
        "clinic.patient.condition.episode", "condition_id", string="Episodes"
    )
    worst_episode_severity = fields.Selection(
        selection=lambda self: self._fields["severity"].selection,
        compute="_compute_worst_episode_severity",
        store=True,
    )

    active = fields.Boolean(default=True, tracking=True)

    # -----------------------------------
    # Unik & indexing
    # -----------------------------------
    _constraint_uniq_patient_condition_active = models.Constraint(
        'unique(patient_id, condition_id, status)',
        'Duplicate condition/status entry for this patient.',
    )

    _constraint_uniq_patient_condition_text_active = models.Constraint(
        'unique(patient_id, condition_name, category_id, status)',
        'Duplicate text condition/status for this patient in the same category.',
    )

    # =========================================================
    # COMPUTE
    # =========================================================
    @api.depends("condition_id", "condition_name", "severity", "status", "code_id", "code_system", "code_value")
    def _compute_display_name(self):
        for rec in self:
            cond = rec.condition_id.name if rec.condition_id else (rec.condition_name or _("Unknown"))
            sev = dict(self._fields["severity"].selection).get(rec.severity or "unknown")
            st = dict(self._fields["status"].selection).get(rec.status or "active")

            code = ""
            if rec.code_id:
                sys = dict(self.env["clinic.condition.code"]._fields["system"].selection).get(rec.code_id.system)
                code = f"{sys}:{rec.code_id.code}"
            elif rec.code_system and rec.code_value:
                sys = dict(self.env["clinic.condition.code"]._fields["system"].selection).get(rec.code_system)
                code = f"{sys}:{rec.code_value}"
            label = cond
            if code:
                label = f"{label} [{code}]"
            rec.display_name = f"{label} • {sev} • {st}"

    @api.depends("onset_date", "abatement_date", "status", "chronic_override", "condition_id.chronic", "chronic_threshold_days")
    def _compute_is_chronic(self):
        today = date.today()
        for rec in self:
            if rec.chronic_override == "force_chronic":
                rec.is_chronic = True
                continue
            if rec.chronic_override == "force_acute":
                rec.is_chronic = False
                continue

            # Jika kamus menandai chronic → chronic
            if rec.condition_id and rec.condition_id.chronic:
                rec.is_chronic = True
                continue

            # Heuristik: jika belum resolved dan durasi > threshold → chronic
            if rec.status in {"active", "recurrence", "remission"} and rec.onset_date and not rec.abatement_date:
                duration = (today - rec.onset_date).days
                rec.is_chronic = duration >= (rec.chronic_threshold_days or 90)
            else:
                rec.is_chronic = False

    def _compute_attachment_count(self):
        Attachment = self.env["ir.attachment"]
        for rec in self:
            rec.attachment_count = Attachment.search_count([
                ("res_model", "=", self._name),
                ("res_id", "=", rec.id),
            ])

    @api.depends("episode_ids.severity")
    def _compute_worst_episode_severity(self):
        rank = {"unknown": 0, "mild": 1, "moderate": 2, "severe": 3, "life_threatening": 4}
        for rec in self:
            worst = "unknown"
            for ep in rec.episode_ids:
                if rank.get(ep.severity, 0) > rank.get(worst, 0):
                    worst = ep.severity
            rec.worst_episode_severity = worst

    # =========================================================
    # ONCHANGE / HELPERS
    # =========================================================
    @api.onchange("condition_id")
    def _onchange_condition_id(self):
        for rec in self:
            if rec.condition_id:
                if not rec.category_id and rec.condition_id.category_id:
                    rec.category_id = rec.condition_id.category_id
                if not rec.condition_name:
                    rec.condition_name = rec.condition_id.name
                if rec.condition_id.default_severity and rec.severity == "unknown":
                    rec.severity = rec.condition_id.default_severity

    @api.onchange("code_id")
    def _onchange_code_id(self):
        for rec in self:
            if rec.code_id:
                rec.code_system = rec.code_id.system
                rec.code_value = rec.code_id.code

    # =========================================================
    # CONSTRAINTS
    # =========================================================
    @api.constrains("onset_date", "abatement_date")
    def _check_dates(self):
        for rec in self:
            if rec.onset_date and rec.abatement_date and rec.abatement_date < rec.onset_date:
                raise ValidationError(_("Abatement/Resolution Date cannot be before Onset Date."))

    @api.constrains("status", "verification_status")
    def _check_status_logic(self):
        for rec in self:
            if rec.status == "entered_in_error" or rec.verification_status == "entered_in_error":
                # tidak paksa rule tambahan — organisasi bisa bebas
                pass

    # =========================================================
    # CRUD OVERRIDES
    # =========================================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Derivasi kategori & nama dari kamus jika belum diisi
            if not vals.get("category_id") and vals.get("condition_id"):
                cond = self.env["clinic.condition"].browse(vals["condition_id"])
                if cond and cond.category_id:
                    vals["category_id"] = cond.category_id.id
            if not vals.get("condition_name") and vals.get("condition_id"):
                cond = self.env["clinic.condition"].browse(vals["condition_id"])
                if cond:
                    vals["condition_name"] = cond.name
            # Default code_system/value dari code_id
            if vals.get("code_id") and (not vals.get("code_system") or not vals.get("code_value")):
                code = self.env["clinic.condition.code"].browse(vals["code_id"])
                if code:
                    vals.setdefault("code_system", code.system)
                    vals.setdefault("code_value", code.code)
            # Default onset_date jika kosong dan status aktif
            if not vals.get("onset_date") and vals.get("status", "active") in {"active", "recurrence", "remission"}:
                vals["onset_date"] = date.today()
            # Recorded defaults via chatter (recorded_by/date tidak dibutuhkan di sini)
        recs = super().create(vals_list)

        # Pasca-buat: mapping ringkasan ke partner
        for rec in recs:
            rec._map_condition_summary_to_partner()

        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            rec._map_condition_summary_to_partner()
        return res

    # =========================================================
    # UTILITIES / INTEGRATION
    # =========================================================
    def _map_condition_summary_to_partner(self):
        """Tuliskan ringkasan kondisi aktif ke partner (opsional).
        - Prioritaskan field custom 'medical_condition_note' jika ada.
        - Fallback ke 'comment' (internal note) tanpa menghapus catatan lain.
        """
        for rec in self:
            partner = rec.patient_id.partner_id
            if not partner:
                continue
            # Ambil daftar kondisi aktif untuk pasien
            active_conds = rec.patient_id.condition_ids.filtered(
                lambda c: c.status in {"active", "recurrence", "remission"} and c.active
            )
            items = []
            for c in active_conds:
                name = c.condition_id.name if c.condition_id else (c.condition_name or _("Unknown"))
                sev = dict(self._fields["severity"].selection).get(c.severity or "unknown")
                items.append(f"{name} ({sev})")
            summary = ", ".join(items)

            if hasattr(partner, "medical_condition_note"):
                if partner.medical_condition_note != summary:
                    partner.medical_condition_note = summary
            elif hasattr(partner, "comment"):
                base = partner.comment or ""
                lines = [l for l in base.split("\n") if not l.startswith("Conditions:")]
                if summary:
                    lines.append(f"Conditions: {summary}")
                partner.comment = "\n".join(lines).strip()

    # =========================================================
    # SMART BUTTONS / ACTIONS
    # =========================================================
    def _action_open_generic(self, xmlid_candidates, domain, name, res_model):
        self.ensure_one()
        action = False
        for xmlid in xmlid_candidates:
            if not xmlid:
                continue
            act = self.env.ref(xmlid, raise_if_not_found=False)
            if act:
                action = act.read()[0]
                break
        if not action:
            action = {
                "type": "ir.actions.act_window",
                "name": name,
                "res_model": res_model,
                "view_mode": "list,form,kanban,calendar,graph,pivot",
                "target": "current",
                "domain": domain,
                "context": {},
            }
        ctx = action.get("context", {}) or {}
        ctx.update({
            "search_default_patient_id": self.patient_id.id,
            "default_patient_id": self.patient_id.id,
        })
        action["context"] = ctx
        action["domain"] = domain
        return action
    # TEMPORARILY DISABLED
    # def action_open_related_encounters(self):
    #     """Buka encounter pasien yang relevan dengan kondisi ini (jika modul aktif)."""
    #     self.ensure_one()
    #     if not _has_model(self.env, "clinic.encounter"):
    #         raise UserError(_("Module 'clinic_encounter' is not installed."))
    #     domain = [("patient_id", "=", self.patient_id.id)]
    #     # Jika encounter punya m2m 'condition_ids', coba filter lebih spesifik
    #     Encounter = self.env["clinic.encounter"]
    #     if "condition_ids" in Encounter._fields:
    #         domain = ["&"] + domain + [("condition_ids", "in", [self.id])]
    #     return self._action_open_generic(
    #         xmlid_candidates=[
    #             "clinic_encounter.action_clinic_encounter_from_patient",
    #             "clinic_encounter.action_clinic_encounter",
    #         ],
    #         domain=domain,
    #         name=_("Encounters"),
    #         res_model="clinic.encounter",
    #     )
    # TEMPORARILY DISABLED
    # def action_open_related_imaging(self):
    #     """Buka imaging/hasil radiologi terkait (jika modul aktif)."""
    #     self.ensure_one()
    #     if not _has_model(self.env, "clinic.imaging"):
    #         raise UserError(_("Module 'clinic_imaging' is not installed."))
    #     domain = [("patient_id", "=", self.patient_id.id)]
    #     Imaging = self.env["clinic.imaging"]
    #     # Jika imaging menyimpan 'condition_id' atau m2m 'condition_ids', perketat domain
    #     if "condition_id" in Imaging._fields:
    #         domain = ["&"] + domain + [("condition_id", "=", self.id)]
    #     elif "condition_ids" in Imaging._fields:
    #         domain = ["&"] + domain + [("condition_ids", "in", [self.id])]
    #     return self._action_open_generic(
    #         xmlid_candidates=[
    #             "clinic_imaging.action_clinic_imaging_from_patient",
    #             "clinic_imaging.action_clinic_imaging",
    #         ],
    #         domain=domain,
    #         name=_("Imaging"),
    #         res_model="clinic.imaging",
    #     )

    def action_open_attachments(self):
        """Smart button lampiran pada record kondisi."""
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

    def action_mark_resolved(self):
        """Set status 'resolved' & isi abatement_date jika kosong."""
        for rec in self:
            rec.status = "resolved"
            if not rec.abatement_date:
                rec.abatement_date = date.today()
        return True

    # =========================================================
    # NAME GET / SEARCH
    # =========================================================
    def name_get(self):
        res = []
        for rec in self:
            name = rec.display_name or rec.condition_name or (rec.condition_id and rec.condition_id.name) or _("Condition")
            res.append((rec.id, name))
        return res

    @api.model
    @api.readonly
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        """Search patient conditions by free text, catalog condition, or code."""
        domain = domain or []
        search_domain = []
        if name:
            search_domain = [
                "|", "|",
                ("condition_name", operator, name),
                ("condition_id.name", operator, name),
                ("code_value", operator, name),
            ]

        records = self.search(search_domain + domain, limit=limit)
        return [(record.id, record.display_name) for record in records.sudo()]


# =====================================================================
# Episode/Kejadian Kondisi (opsional)
# =====================================================================
class ClinicPatientConditionEpisode(models.Model):
    _name = "clinic.patient.condition.episode"
    _description = "Patient Condition Episode"
    _inherit = ["mail.thread"]
    _order = "episode_datetime DESC, create_date DESC"

    condition_id = fields.Many2one(
        "clinic.patient.condition",
        string="Condition",
        required=True,
        ondelete="cascade",
        index=True,
    )
    patient_id = fields.Many2one(
        "clinic.patient",
        related="condition_id.patient_id",
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="condition_id.company_id",
        store=True,
        readonly=True,
    )

    episode_datetime = fields.Datetime(
        string="Episode Date/Time",
        default=lambda self: fields.Datetime.now(),
        tracking=True,
    )
    description = fields.Text(help="Narrative details for this episode/flare-up.")
    severity = fields.Selection(
        selection=lambda self: self.env["clinic.patient.condition"]._fields["severity"].selection,
        default="unknown",
        tracking=True,
    )
    outcome = fields.Selection(
        [
            ("improved", "Improved"),
            ("unchanged", "Unchanged"),
            ("worsened", "Worsened"),
            ("fatal", "Fatal"),
            ("unknown", "Unknown"),
        ],
        default="unknown",
    )
    # TEMPORARILY DISABLED
    # Integrasi encounter (opsional)
    # encounter_id = fields.Many2one(
    #     comodel_name="clinic.encounter" if _has_model(models.Environment.manage().env, "clinic.encounter") else "ir.ui.view",
    #     string="Encounter",
    #     help="Link to encounter if clinic_encounter is installed."
    # )

    attachment_count = fields.Integer(compute="_compute_attachment_count")

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

