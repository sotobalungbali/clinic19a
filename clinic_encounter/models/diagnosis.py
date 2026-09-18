# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/diagnosis.py
#
# Tujuan:
# - Menyediakan model Diagnosis klinis yang melekat pada Encounter.
# - Mendukung kode referensi (ICD/SNOMED/Local), certainty, severity, chronicity, dan status aktif/selesai.
# - Integrasi ringan (soft-coupled) dengan SOAP, rencana prosedur/sesi, dan billing.
#
# Catatan integrasi:
# - Relasi Many2many dengan clinic.soap.note telah didefinisikan di file soap_note.py (clinic_diagnosis_soap_rel).
# - Rencana prosedur diasumsikan menggunakan model clinic.encounter.procedure (memiliki encounter_id & optional diagnosis_id).
# - Penagihan mengikuti konvensi invoice_origin == encounter.name (lihat tombol action_open_invoices()).
#
from datetime import timedelta, date

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# -----------------------------------------------------------------------------
# Kategori Diagnosis (opsional, untuk grouping / pelaporan)
# -----------------------------------------------------------------------------
class ClinicDiagnosisCategory(models.Model):
    _name = "clinic.diagnosis.category"
    _description = "Diagnosis Category"
    _order = "sequence, name"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, index=True)
    description = fields.Text()


# -----------------------------------------------------------------------------
# Diagnosis Utama
# -----------------------------------------------------------------------------
class ClinicDiagnosis(models.Model):
    _name = "clinic.diagnosis"
    _description = "Clinical Diagnosis"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_diagnosed desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identitas & Perusahaan
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Diagnosis Name",
        required=True,
        tracking=True,
        index=True,
        help="Human-readable diagnosis label. Can be free text or mapped to a coding system.",
    )
    code = fields.Char(
        string="Code",
        index=True,
        help="Optional code (ICD-10/SNOMED/Local).",
    )
    code_system = fields.Selection(
        [
            ("icd10", "ICD-10"),
            ("icd9", "ICD-9-CM"),
            ("snomed", "SNOMED CT"),
            ("local", "Local"),
            ("free_text", "Free Text"),
        ],
        string="Code System",
        default="free_text",
        index=True,
        tracking=True,
    )
    display_code = fields.Char(
        string="Code • Name",
        compute="_compute_display_code",
        store=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    # -------------------------------------------------------------------------
    # Konteks Klinis
    # -------------------------------------------------------------------------
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Encounter",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        related="encounter_id.patient_id",
        store=True,
        readonly=True,
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Patient Partner",
        related="patient_id.partner_id",
        store=True,
        readonly=True,
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Provider/Doctor",
        related="encounter_id.doctor_id",
        store=True,
        readonly=True,
        index=True,
    )
    category_id = fields.Many2one(
        "clinic.diagnosis.category",
        string="Category",
        ondelete="set null",
        index=True,
    )
    source = fields.Selection(
        [
            ("manual", "Manual Entry"),
            ("soap_free_text", "SOAP Free Text"),
            ("import", "Imported"),
            ("migration", "Migration"),
        ],
        string="Source",
        default="manual",
        index=True,
        help="Origin of the diagnosis record.",
    )

    # Link balik ke SOAP notes (M2M dideklarasi dari sisi SOAP)
    soap_note_ids = fields.Many2many(
        "clinic.soap.note",
        "clinic_diagnosis_soap_rel",
        "diagnosis_id",
        "soap_id",
        string="SOAP Notes",
        help="SOAP Notes that refer to this diagnosis.",
    )

    # -------------------------------------------------------------------------
    # Status, Klasifikasi & Parameter Klinis
    # -------------------------------------------------------------------------
    type = fields.Selection(
        [
            ("primary", "Primary"),
            ("secondary", "Secondary"),
            ("comorbidity", "Comorbidity"),
            ("complication", "Complication"),
        ],
        string="Type",
        default="secondary",
        index=True,
        tracking=True,
    )
    is_primary = fields.Boolean(
        string="Primary Flag",
        compute="_compute_is_primary",
        inverse="_inverse_is_primary",
        store=True,
        help="Mirrors type == 'primary'. Toggling this will set the type accordingly.",
    )
    certainty = fields.Selection(
        [
            ("suspected", "Suspected"),
            ("probable", "Probable"),
            ("confirmed", "Confirmed"),
            ("ruled_out", "Ruled Out"),
        ],
        string="Certainty",
        default="suspected",
        index=True,
        tracking=True,
    )
    severity = fields.Selection(
        [
            ("mild", "Mild"),
            ("moderate", "Moderate"),
            ("severe", "Severe"),
        ],
        string="Severity",
        index=True,
    )
    chronicity = fields.Selection(
        [
            ("acute", "Acute"),
            ("subacute", "Sub-acute"),
            ("chronic", "Chronic"),
        ],
        string="Chronicity",
        index=True,
    )
    status = fields.Selection(
        [
            ("active", "Active"),
            ("resolved", "Resolved"),
            ("inactive", "Inactive"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="active",
        index=True,
        tracking=True,
        help="Functional status of this diagnosis.",
    )
    is_active = fields.Boolean(
        string="Is Active?",
        compute="_compute_is_active",
        store=True,
        help="Derived from status and resolution date.",
    )

    # Anatomi / sisi (opsional untuk pelaporan)
    body_site = fields.Char(string="Body Site")
    laterality = fields.Selection(
        [("left", "Left"), ("right", "Right"), ("bilateral", "Bilateral")],
        string="Laterality",
    )

    # Waktu Klinis
    date_onset = fields.Date(string="Onset Date")
    date_diagnosed = fields.Date(string="Diagnosed Date", default=lambda self: fields.Date.today())
    date_resolved = fields.Date(string="Resolved Date")
    duration_days = fields.Integer(
        string="Duration (Days)",
        compute="_compute_duration_days",
        store=True,
        help="From onset until resolved (or today if still active).",
    )

    # Deskripsi & Catatan
    description = fields.Text(string="Clinical Description")
    note = fields.Text(string="Notes (Internal)")

    # -------------------------------------------------------------------------
    # Integrasi Prosedur & Billing (soft-coupled)
    # -------------------------------------------------------------------------
    suggested_procedure_ids = fields.Many2many(
        "clinic.procedure.catalog",
        "clinic_dx_proc_catalog_rel",
        "diagnosis_id",
        "procedure_id",
        string="Suggested Procedures",
        help="Optional mapping to procedure catalog for decision support.",
    )
    related_procedure_count = fields.Integer(
        string="Procedure Plans",
        compute="_compute_counters",
        store=False,
    )
    session_count = fields.Integer(
        string="Sessions",
        compute="_compute_counters",
        store=False,
    )
    invoice_count = fields.Integer(
        string="Invoices",
        compute="_compute_invoice_count",
        store=False,
    )

    color = fields.Integer(string="Color Index")
    priority = fields.Selection(
        [("0", "Normal"), ("1", "High"), ("2", "Urgent")],
        string="Priority",
        default="0",
        index=True,
    )

    # -------------------------------------------------------------------------
    # Komputasi
    # -------------------------------------------------------------------------
    @api.depends("code", "name")
    def _compute_display_code(self):
        for rec in self:
            rec.display_code = f"[{rec.code}] {rec.name}" if rec.code else rec.name

    @api.depends("type")
    def _compute_is_primary(self):
        for rec in self:
            rec.is_primary = rec.type == "primary"

    def _inverse_is_primary(self):
        for rec in self:
            rec.type = "primary" if rec.is_primary else (rec.type if rec.type != "primary" else "secondary")

    @api.depends("status", "date_resolved")
    def _compute_is_active(self):
        today = fields.Date.context_today(self)
        for rec in self:
            active = rec.status == "active"
            if rec.date_resolved and rec.date_resolved <= today:
                active = False
            rec.is_active = active

    @api.depends("date_onset", "date_resolved", "status")
    def _compute_duration_days(self):
        today = fields.Date.context_today(self)
        for rec in self:
            start = rec.date_onset or rec.date_diagnosed or today
            end = rec.date_resolved if rec.date_resolved else (today if rec.status == "active" else today)
            rec.duration_days = (end - start).days if isinstance(end, date) and isinstance(start, date) else 0

    def _compute_counters(self):
        EncounterProc = self.env["clinic.encounter.procedure"]
        Session = self.env["clinic.procedure.session"]
        for rec in self:
            # Asumsi clinic.encounter.procedure memiliki field optional diagnosis_id
            rec.related_procedure_count = EncounterProc.search_count(
                [("encounter_id", "=", rec.encounter_id.id), ("diagnosis_id", "=", rec.id)]
            )
            rec.session_count = Session.search_count(
                [("encounter_id", "=", rec.encounter_id.id), ("diagnosis_id", "=", rec.id)]
            )

    def _compute_invoice_count(self):
        AccountMove = self.env["account.move"]
        for rec in self:
            moves = AccountMove.search([
                ("invoice_origin", "=", rec.encounter_id.name if rec.encounter_id else False),
                ("move_type", "in", ["out_invoice", "out_refund"]),
                ("company_id", "=", rec.company_id.id),
            ])
            rec.invoice_count = len(moves)

    # -------------------------------------------------------------------------
    # Constraint & Validasi
    # -------------------------------------------------------------------------
    _constraint_code_len_check = models.Constraint(
        "CHECK (char_length(coalesce(code, '')) <= 64)",
        'Code too long (max 64).',
    )

    @api.constrains("date_onset", "date_resolved")
    def _check_dates(self):
        for rec in self:
            if rec.date_onset and rec.date_resolved and rec.date_resolved < rec.date_onset:
                raise ValidationError(_("Resolved Date cannot be earlier than Onset Date."))

    @api.constrains("type", "encounter_id", "status")
    def _check_single_primary_per_encounter(self):
        for rec in self:
            if rec.type == "primary" and rec.status != "cancelled" and rec.encounter_id:
                domain = [
                    ("id", "!=", rec.id),
                    ("encounter_id", "=", rec.encounter_id.id),
                    ("type", "=", "primary"),
                    ("status", "!=", "cancelled"),
                ]
                if self.search_count(domain):
                    raise ValidationError(_("Only one primary diagnosis is allowed per encounter."))

    @api.constrains("certainty", "date_diagnosed")
    def _check_certainty_dates(self):
        for rec in self:
            if rec.certainty == "confirmed" and not rec.date_diagnosed:
                raise ValidationError(_("Confirmed diagnosis requires a Diagnosed Date."))

    @api.constrains("company_id", "encounter_id")
    def _check_company_consistency(self):
        for rec in self:
            if rec.encounter_id and rec.company_id and rec.company_id != rec.encounter_id.company_id:
                raise ValidationError(_("Diagnosis company must match the Encounter company."))

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            # Activity reminder untuk owner encounter
            try:
                if rec.encounter_id:
                    rec.activity_schedule(
                        "mail.mail_activity_data_todo",
                        summary=_("Review Diagnosis"),
                        user_id=(rec.encounter_id.user_id.id or self.env.user.id),
                        date_deadline=fields.Date.today(),
                    )
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        # Penyesuaian otomatis prioritas berdasarkan severity (opsional)
        for rec in self:
            if rec.severity == "severe" and rec.priority != "2":
                super(ClinicDiagnosis, rec).write({"priority": "2"})
            elif rec.severity == "moderate" and rec.priority == "0":
                super(ClinicDiagnosis, rec).write({"priority": "1"})
        return res

    # -------------------------------------------------------------------------
    # Actions / Workflow
    # -------------------------------------------------------------------------
    def action_set_primary(self):
        """Jadikan diagnosis ini sebagai Primary, pastikan tidak ada primary lain yang aktif."""
        self.ensure_one()
        if self.status == "cancelled":
            raise UserError(_("Cancelled diagnosis cannot be set as Primary."))
        # Unset primary lain di encounter
        others = self.search([
            ("id", "!=", self.id),
            ("encounter_id", "=", self.encounter_id.id),
            ("type", "=", "primary"),
            ("status", "!=", "cancelled"),
        ])
        if others:
            others.write({"type": "secondary"})
        self.write({"type": "primary"})
        return True

    def action_mark_resolved(self, resolved_date=False, note=None):
        """Tandai sebagai Resolved; isi tanggal resolved jika belum ada."""
        for rec in self:
            updates = {"status": "resolved"}
            if resolved_date:
                updates["date_resolved"] = resolved_date
            elif not rec.date_resolved:
                updates["date_resolved"] = fields.Date.today()
            rec.write(updates)
            if note:
                rec.message_post(body=_("Diagnosis resolved: %s") % note)
        return True

    def action_reopen(self, note=None):
        """Kembalikan status menjadi Active."""
        for rec in self:
            rec.write({"status": "active", "date_resolved": False})
            if note:
                rec.message_post(body=_("Diagnosis reopened: %s") % note)
        return True

    def action_open_procedures(self):
        """Buka daftar rencana prosedur yang terkait diagnosis ini pada encounter."""
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_encounter_procedure").read()[0]
        # Asumsikan model clinic.encounter.procedure memiliki field 'diagnosis_id'
        action["domain"] = [
            ("encounter_id", "=", self.encounter_id.id),
            ("diagnosis_id", "=", self.id),
        ]
        ctx = {
            "default_encounter_id": self.encounter_id.id,
            "default_diagnosis_id": self.id,
            "search_default_diagnosis_id": self.id,
        }
        action["context"] = ctx
        return action

    def action_plan_procedure_quick(self):
        """Buka wizard (jika ada) untuk menambahkan prosedur dari suggested_procedure_ids."""
        self.ensure_one()
        if not self.suggested_procedure_ids:
            raise UserError(_("No suggested procedures linked to this diagnosis."))
        action = self.env.ref("clinic_encounter.action_generate_procedure_from_dx_wizard").read()[0]
        action["context"] = {
            "default_encounter_id": self.encounter_id.id,
            "default_diagnosis_id": self.id,
            "default_procedure_ids": [(6, 0, self.suggested_procedure_ids.ids)],
        }
        return action

    def action_open_sessions(self):
        """Buka sesi tindakan yang diasosiasikan diagnosis ini di encounter yang sama."""
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_procedure_session").read()[0]
        action["domain"] = [
            ("encounter_id", "=", self.encounter_id.id),
            ("diagnosis_id", "=", self.id),
        ]
        action["context"] = {
            "default_encounter_id": self.encounter_id.id,
            "default_diagnosis_id": self.id,
            "search_default_diagnosis_id": self.id,
        }
        return action

    def action_open_invoices(self):
        """Buka invoice yang terkait encounter ini."""
        self.ensure_one()
        AccountMove = self.env["account.move"]
        moves = AccountMove.search([
            ("invoice_origin", "=", self.encounter_id.name if self.encounter_id else False),
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("company_id", "=", self.company_id.id),
        ])
        if not moves:
            raise UserError(_("No related invoices found via Encounter."))
        action = self.env.ref("account.action_move_out_invoice_type").read()[0]
        action["domain"] = [("id", "in", moves.ids)]
        return action

    def action_open_encounter(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_encounter").read()[0]
        action["res_id"] = self.encounter_id.id
        action["domain"] = [("id", "=", self.encounter_id.id)]
        action["view_mode"] = "form"
        return action

    # -------------------------------------------------------------------------
    # Name & Search
    # -------------------------------------------------------------------------
    @api.depends("display_code", "name", "type", "certainty")
    def _compute_display_name(self):
        certainty_labels = dict(self._fields["certainty"].selection)
        for rec in self:
            label = rec.display_code or rec.name or ""
            badges = []
            if rec.type == "primary":
                badges.append(_("Primary"))
            if rec.certainty:
                badges.append(certainty_labels.get(rec.certainty))
            if badges:
                label = f"{label} ({', '.join([b for b in badges if b])})"
            rec.display_name = label

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        extra_domain = list(domain or [])
        name_domain = ["|", "|", ("name", operator, name), ("code", operator, name), ("display_code", operator, name)]
        recs = self.search(name_domain + extra_domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]

