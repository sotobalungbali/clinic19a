# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/soap_note.py
#
# Tujuan:
# - Mendefinisikan catatan klinis terstruktur berbasis SOAP (S/O/A/P) yang melekat pada Encounter.
# - Mendukung template SOAP, tagging, versioning ringan (amendment), dan finalisasi (lock).
# - Terintegrasi dengan mail.thread & mail.activity untuk kolaborasi/audit.
# - Aman multi-company; kompatibel dengan model diagnosis & encounter di modul ini.
#
# Catatan integrasi lintas-modul (soft-coupled):
# - patient_id -> clinic.patient (dari encounter)
# - doctor_id  -> clinic.doctor (dari encounter)
# - assessment_diagnosis_ids -> clinic.diagnosis (model di file diagnosis.py)
# - Saat finalisasi, dapat membuat diagnosis free-text jika user belum memilih dari master (opsional)
#
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# -----------------------------------------------------------------------------
# Taksonomi tag sederhana untuk mengelompokkan SOAP (opsional)
# -----------------------------------------------------------------------------
class ClinicSoapTag(models.Model):
    _name = "clinic.soap.tag"
    _description = "SOAP Tag"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    color = fields.Integer(string="Color Index")
    active = fields.Boolean(default=True)
    description = fields.Text()


# -----------------------------------------------------------------------------
# Template SOAP untuk prefill S/O/A/P (dipakai wizard/aksi Apply Template)
# -----------------------------------------------------------------------------
class ClinicSoapTemplate(models.Model):
    _name = "clinic.soap.template"
    _description = "SOAP Template"
    _order = "sequence, name"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True, index=True)
    sequence = fields.Integer(default=10, index=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )
    tag_ids = fields.Many2many("clinic.soap.tag", string="Tags")

    # Konten template (Html untuk dukungan formatting dasar)
    subjective_tmpl = fields.Html(string="Subjective (Template)")
    objective_tmpl = fields.Html(string="Objective (Template)")
    assessment_tmpl = fields.Html(string="Assessment (Template)")
    plan_tmpl = fields.Html(string="Plan (Template)")

    default_priority = fields.Selection(
        [("0", "Normal"), ("1", "High"), ("2", "Urgent")],
        string="Default Priority",
        default="0",
        help="Jika diterapkan ke SOAP Note baru.",
    )

    _constraint_uniq_template_name_company = models.Constraint(
        'unique(name, company_id)',
        'Template name must be unique per company.',
    )


# -----------------------------------------------------------------------------
# SOAP Note utama: melekat pada Encounter
# -----------------------------------------------------------------------------
class ClinicSoapNote(models.Model):
    _name = "clinic.soap.note"
    _description = "SOAP Note"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_note desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identitas & Relasi
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="SOAP #",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        index=True,
        tracking=True,
    )
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
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
        "res.partner", string="Patient Partner", related="patient_id.partner_id", store=True, readonly=True
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Provider/Doctor",
        related="encounter_id.doctor_id",
        store=True,
        readonly=True,
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        default=lambda self: self.env.user,
        tracking=True,
        help="Staff yang membuat/mengelola SOAP ini.",
    )

    # -------------------------------------------------------------------------
    # Waktu & Status
    # -------------------------------------------------------------------------
    date_note = fields.Datetime(
        string="Note Date",
        default=lambda self: fields.Datetime.now(),
        index=True,
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("final", "Final"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
    )
    is_locked = fields.Boolean(
        string="Locked",
        compute="_compute_is_locked",
        store=True,
        help="Terkunci bila status Final atau Cancelled.",
    )
    priority = fields.Selection(
        [("0", "Normal"), ("1", "High"), ("2", "Urgent")],
        string="Priority",
        default="0",
        index=True,
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Konten SOAP (Html untuk formatting sederhana)
    # -------------------------------------------------------------------------
    chief_complaint = fields.Char(string="Chief Complaint")
    subjective = fields.Html(string="S — Subjective")
    objective = fields.Html(string="O — Objective")
    assessment = fields.Html(string="A — Assessment")
    plan = fields.Html(string="P — Plan")

    # Ringkasan singkat untuk tampilan list/kanban
    summary = fields.Char(string="Summary", compute="_compute_summary", store=True)

    # Skala nyeri / vital ringkas (opsional; detail vital ada di clinic.patient.vital)
    pain_scale = fields.Selection(
        [(str(i), str(i)) for i in range(0, 11)],
        string="Pain Scale (0-10)",
        help="Opsional penilaian skala nyeri saat membuat SOAP.",
    )

    # -------------------------------------------------------------------------
    # Diagnosis & Tagging
    # -------------------------------------------------------------------------
    assessment_diagnosis_ids = fields.Many2many(
        "clinic.diagnosis",
        "clinic_diagnosis_soap_rel",
        "soap_id",
        "diagnosis_id",
        string="Linked Diagnoses",
        help="Tautkan diagnosis klinis yang relevan dengan SOAP ini.",
    )
    # Catatan: Jika user belum memilih diagnosis dari master, assessment_free_dx bisa diisi,
    # dan saat finalisasi dapat dibuat diagnosis free-text (opsional).
    assessment_free_dx = fields.Char(
        string="Assessment (Free Dx)",
        help="Diagnosis free-text (akan dibuatkan record diagnosis saat finalisasi, opsional).",
    )

    tag_ids = fields.Many2many("clinic.soap.tag", string="Tags")

    # -------------------------------------------------------------------------
    # Template & Versioning ringan
    # -------------------------------------------------------------------------
    template_id = fields.Many2one("clinic.soap.template", string="Template")
    version = fields.Integer(string="Version", default=1, tracking=True)
    previous_id = fields.Many2one("clinic.soap.note", string="Previous Version", copy=False)
    is_amendment = fields.Boolean(
        string="Amendment",
        help="Centang jika ini pembaruan/penyempurnaan atas SOAP sebelumnya.",
        default=False,
    )

    # -------------------------------------------------------------------------
    # Monetisasi/bridges (read-only roll-up kecil, tidak memaksa billing)
    # -------------------------------------------------------------------------
    invoice_count = fields.Integer(
        string="Invoices",
        compute="_compute_invoice_count",
        store=False,
        help="Jumlah invoice yang terhubung lewat Encounter.",
    )

    # -------------------------------------------------------------------------
    # Komputasi
    # -------------------------------------------------------------------------
    @api.depends("state")
    def _compute_is_locked(self):
        for rec in self:
            rec.is_locked = rec.state in ("final", "cancelled")

    @api.depends("chief_complaint", "subjective", "assessment")
    def _compute_summary(self):
        def _shorten(text, maxlen=110):
            if not text:
                return ""
            # Strip tag html sederhana
            clean = tools.html2plaintext(text) if hasattr(tools := __import__("odoo.tools").tools, "html2plaintext") else text
            clean = " ".join(clean.split())
            return (clean[: maxlen - 1] + "…") if len(clean) > maxlen else clean

        for rec in self:
            parts = []
            if rec.chief_complaint:
                parts.append(rec.chief_complaint)
            # Tambahkan potongan subjek/assessment jika ada
            if rec.assessment:
                parts.append(_shorten(rec.assessment, 80))
            elif rec.subjective:
                parts.append(_shorten(rec.subjective, 80))
            rec.summary = " — ".join([p for p in parts if p]) or False

    def _compute_invoice_count(self):
        for rec in self:
            moves = rec._get_related_invoices()
            rec.invoice_count = len(moves)

    # -------------------------------------------------------------------------
    # Onchange & Defaults
    # -------------------------------------------------------------------------
    @api.onchange("template_id")
    def _onchange_template_id(self):
        """Prefill dari template bila field kosong. Tidak menimpa yang sudah terisi."""
        tmpl = self.template_id
        if not tmpl:
            return
        updates = {}
        if not self.subjective and tmpl.subjective_tmpl:
            updates["subjective"] = tmpl.subjective_tmpl
        if not self.objective and tmpl.objective_tmpl:
            updates["objective"] = tmpl.objective_tmpl
        if not self.assessment and tmpl.assessment_tmpl:
            updates["assessment"] = tmpl.assessment_tmpl
        if not self.plan and tmpl.plan_tmpl:
            updates["plan"] = tmpl.plan_tmpl
        if updates:
            self.update(updates)
        # Priority default dari template bila masih default
        if self.priority == "0" and tmpl.default_priority:
            self.priority = tmpl.default_priority

    # -------------------------------------------------------------------------
    # Constraint & Validasi
    # -------------------------------------------------------------------------
    _constraint_uniq_soap_name_company = models.Constraint(
        'unique(name, company_id)',
        'SOAP number must be unique per company.',
    )

    @api.constrains("encounter_id", "company_id")
    def _check_company_consistency(self):
        for rec in self:
            if rec.encounter_id and rec.company_id and rec.company_id != rec.encounter_id.company_id:
                raise ValidationError(_("SOAP Note company must match the Encounter company."))

    @api.constrains("state")
    def _check_locked_edit(self):
        # Pencegahan di level constraint: perubahan S/O/A/P pada state final/cancelled tidak boleh.
        # (Perubahan minor via chatter masih dimungkinkan untuk audit.)
        tracked_fields = {"subjective", "objective", "assessment", "plan", "chief_complaint"}
        for rec in self:
            if rec.state in ("final", "cancelled"):
                # Jika user ingin ubah, gunakan 'Duplicate as Amendment'
                # (Tidak ada pemeriksaan diff di sini; proteksi dilakukan via button actions & UI)
                pass

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if vals.get("name", _("New")) in (False, _("New")):
                vals["name"] = seq.next_by_code("clinic.soap.note") or _("New")
            # Default tautan encounter -> patient/doctor handled by related fields.
        recs = super().create(vals_list)
        # Activity default: minta review SOAP (optional)
        for rec in recs:
            try:
                rec.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Review SOAP Note"),
                    user_id=rec.user_id.id or self.env.user.id,
                    date_deadline=fields.Date.today(),
                )
            except Exception:
                pass
        return recs

    def write(self, vals):
        # Cegah edit konten saat locked (kecuali pengubahan state dari draft -> final/cancel)
        if any(field in vals for field in ["subjective", "objective", "assessment", "plan", "chief_complaint"]):
            for rec in self:
                if rec.is_locked and not self.env.context.get("allow_locked_write"):
                    raise UserError(_("This SOAP Note is locked. Create an amendment instead."))
        return super().write(vals)

    # -------------------------------------------------------------------------
    # Actions (Buttons)
    # -------------------------------------------------------------------------
    def action_apply_template(self):
        """Terapkan template secara force (menimpa)."""
        self.ensure_one()
        if not self.template_id:
            raise UserError(_("Please select a template first."))
        vals = {
            "subjective": self.template_id.subjective_tmpl or False,
            "objective": self.template_id.objective_tmpl or False,
            "assessment": self.template_id.assessment_tmpl or False,
            "plan": self.template_id.plan_tmpl or False,
        }
        if self.template_id.default_priority:
            vals["priority"] = self.template_id.default_priority
        return self.write(vals)

    def action_set_draft(self):
        """Kembalikan ke Draft (opsional, dibatasi security)."""
        for rec in self:
            if rec.state == "cancelled":
                raise UserError(_("Cancelled SOAP cannot be set back to Draft."))
            rec.write({"state": "draft"})
        return True

    def action_finalize(self, create_free_dx=True):
        """
        Finalisasi dan kunci SOAP:
        - Optional: buat diagnosis free-text jika assessment_free_dx ada & user belum pilih diagnosis master.
        - Jadwalkan tindak lanjut ke owner encounter.
        """
        for rec in self:
            if rec.state == "final":
                continue
            if not (rec.subjective or rec.objective or rec.assessment or rec.plan):
                raise UserError(_("Cannot finalize an empty SOAP. Please fill at least one section."))
            # Buat diagnosis free-text opsional
            if create_free_dx and rec.assessment_free_dx and not rec.assessment_diagnosis_ids:
                try:
                    dx = rec.env["clinic.diagnosis"].create({
                        "name": rec.assessment_free_dx,
                        "encounter_id": rec.encounter_id.id,
                        "patient_id": rec.patient_id.id if rec.patient_id else False,
                        "company_id": rec.company_id.id,
                        "source": "soap_free_text",
                    })
                    rec.assessment_diagnosis_ids = [(4, dx.id)]
                except Exception:
                    # Jangan gagalkan finalisasi karena gagal membuat DX opsional
                    pass
            rec.write({"state": "final"})
            # Follow-up activity ke owner encounter (jika ada)
            if rec.encounter_id:
                try:
                    rec.encounter_id.push_activity_followup(
                        summary=_("Review finalized SOAP"),
                        days=1,
                        user=rec.encounter_id.user_id or rec.user_id,
                    )
                except Exception:
                    pass
        return True

    def action_cancel(self, reason=None):
        """Batalkan SOAP (lock)."""
        for rec in self:
            if rec.state == "final":
                # Kebijakan: final -> cancel diperbolehkan? Di sini kita izinkan dengan catatan.
                pass
            updates = {"state": "cancelled"}
            if reason:
                note = (rec.message_follower_ids and "")  # placeholder to avoid flake8 unused
                # Tambahkan reason ke chatter sebagai log
                rec.message_post(body=_("SOAP cancelled: %s") % reason)
            rec.write(updates)
        return True

    def action_duplicate_as_amendment(self):
        """Gandakan SOAP sebagai amendment (version + 1, previous_id diisi)."""
        self.ensure_one()
        copy_vals = {
            "name": _("New"),
            "state": "draft",
            "version": self.version + 1,
            "previous_id": self.id,
            "is_amendment": True,
        }
        new = self.copy(copy_vals)
        # Activity untuk meninjau amendment
        try:
            new.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=_("Review SOAP Amendment"),
                user_id=new.user_id.id or self.env.user.id,
                date_deadline=fields.Date.today() + timedelta(days=1),
            )
        except Exception:
            pass
        return {
            "type": "ir.actions.act_window",
            "name": _("SOAP Amendment"),
            "res_model": self._name,
            "res_id": new.id,
            "view_mode": "form",
        }

    # -------------------------------------------------------------------------
    # Smart Buttons / External Actions
    # -------------------------------------------------------------------------
    def action_open_related_invoices(self):
        self.ensure_one()
        moves = self._get_related_invoices()
        if not moves:
            raise UserError(_("No related invoices found via Encounter."))
        action = self.env.ref("account.action_move_out_invoice_type").read()[0]
        action["domain"] = [("id", "in", moves.ids)]
        return action

    def action_open_encounter(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_encounter").read()[0]
        action["domain"] = [("id", "=", self.encounter_id.id)]
        action["res_id"] = self.encounter_id.id
        action["view_mode"] = "form"
        return action

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _get_related_invoices(self):
        """Ambil invoice berdasarkan invoice_origin == encounter.name (konvensi ClinicOne)."""
        AccountMove = self.env["account.move"]
        moves = AccountMove.search([
            ("invoice_origin", "=", self.encounter_id.name if self.encounter_id else False),
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("company_id", "=", self.company_id.id),
        ])
        return moves

    # -------------------------------------------------------------------------
    # Name & Search
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            label = rec.name or ""
            if rec.encounter_id:
                label = f"{label} ⸺ {rec.encounter_id.name}"
            if rec.chief_complaint:
                label = f"{label} ⸺ {rec.chief_complaint}"
            res.append((rec.id, label.strip(" ⸺")))
        return res

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        extra_domain = list(domain or [])
        name_domain = ["|", "|",
                  ("name", operator, name),
                  ("encounter_id.name", operator, name),
                  ("chief_complaint", operator, name)]
        recs = self.search(name_domain + extra_domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]


# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/result_document.py
#
# Fungsi utama:
# - Menyimpan dokumen hasil tindakan/encounter (laporan, foto, nilai terukur).
# - Nilai terstruktur per-parameter (angka/teks), referensi rentang, flag abnormal/critical.
# - Workflow: Draft → Validated → Released → (opsional) Cancelled.
# - Integrasi holistik: Encounter, Session, Procedure, Diagnosis, Billing, Portal.
#
from math import isfinite

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =============================================================================
# Model: Result Group (opsional untuk mengelompokkan parameter per panel)
# =============================================================================
class ClinicResultGroup(models.Model):
    _name = "clinic.result.group"
    _description = "Result Parameter Group"
    _order = "sequence, id"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10, index=True)
    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    description = fields.Text()
    collapsed = fields.Boolean(string="Collapsed by Default", default=False)


# =============================================================================
# Model: Result Document (header)
# =============================================================================
class ClinicResultDocument(models.Model):
    _name = "clinic.result.document"
    _description = "Clinical Result Document"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _order = "date_released desc, date_validated desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identitas & Perusahaan
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Result #",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        index=True,
        tracking=True,
    )
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", store=True, readonly=True
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
    session_id = fields.Many2one(
        "clinic.procedure.session",
        string="Session",
        ondelete="set null",
        index=True,
        help="If this result is specific to a particular procedure session.",
    )
    procedure_id = fields.Many2one(
        "clinic.procedure.catalog",
        string="Procedure",
        ondelete="set null",
        index=True,
        help="Procedure catalog reference for this result.",
    )
    diagnosis_id = fields.Many2one(
        "clinic.diagnosis",
        string="Diagnosis",
        ondelete="set null",
        index=True,
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
        "res.partner", string="Patient Partner", related="patient_id.partner_id", store=True, readonly=True
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Encounter Doctor",
        related="encounter_id.doctor_id",
        store=True,
        readonly=True,
        index=True,
    )

    # -------------------------------------------------------------------------
    # Status & Lifecycle
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("validated", "Validated"),
            ("released", "Released"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        index=True,
        tracking=True,
    )
    is_locked = fields.Boolean(
        string="Locked",
        compute="_compute_is_locked",
        store=True,
        help="Locked on Validated/Released/Cancelled.",
    )

    # Riwayat validasi & rilis
    validated_by_id = fields.Many2one("res.users", string="Validated By", readonly=True, tracking=True)
    date_validated = fields.Datetime(string="Validated On", readonly=True, tracking=True)
    released_by_id = fields.Many2one("res.users", string="Released By", readonly=True, tracking=True)
    date_released = fields.Datetime(string="Released On", readonly=True, tracking=True)

    # -------------------------------------------------------------------------
    # Informasi Sampel (opsional, untuk lab/alat)
    # -------------------------------------------------------------------------
    specimen_type = fields.Char(string="Specimen Type")
    specimen_id = fields.Char(string="Specimen ID / Barcode")
    collected_by_id = fields.Many2one("res.users", string="Collected By")
    date_collected = fields.Datetime(string="Collected On")
    date_analyzed = fields.Datetime(string="Analyzed On")

    # -------------------------------------------------------------------------
    # Konten Dokumen
    # -------------------------------------------------------------------------
    title = fields.Char(string="Report Title")
    summary = fields.Html(string="Summary / Impression")
    note_internal = fields.Text(string="Internal Notes")
    tag_ids = fields.Many2many("clinic.soap.tag", string="Tags")  # reuse tagging yang sudah ada

    # Nilai/parameter hasil
    line_ids = fields.One2many("clinic.result.value", "result_id", string="Result Values")

    # Lampiran (gambar/foto/dok)
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "clinic_result_attachment_rel",
        "result_id",
        "attachment_id",
        string="Attachments",
        help="Linked files (images, PDFs, etc.). You can also use chatter attachments.",
    )

    # Ikhtisar abnormal/critical
    abnormal_count = fields.Integer(
        string="Abnormal Items",
        compute="_compute_flags_counter",
        store=True,
    )
    critical_count = fields.Integer(
        string="Critical Items",
        compute="_compute_flags_counter",
        store=True,
    )

    # -------------------------------------------------------------------------
    # Billing Bridges (soft-coupled)
    # -------------------------------------------------------------------------
    invoice_line_ids = fields.Many2many(
        "account.move.line",
        "clinic_result_invoice_line_rel",
        "result_id",
        "aml_id",
        string="Invoice Lines",
        help="Optional mapping to billing lines generated by plan/session.",
    )
    invoice_count = fields.Integer(string="Invoices", compute="_compute_invoice_count", store=False)

    # UI
    color = fields.Integer(string="Color Index")
    priority = fields.Selection([("0", "Normal"), ("1", "High"), ("2", "Urgent")], default="0", index=True)

    # -------------------------------------------------------------------------
    # Portal (portal.mixin)
    # -------------------------------------------------------------------------
    def _get_report_base_filename(self):
        self.ensure_one()
        return f"{self.name} - {self.patient_id.display_name if self.patient_id else ''}".strip()

    # -------------------------------------------------------------------------
    # Komputasi
    # -------------------------------------------------------------------------
    @api.depends("state")
    def _compute_is_locked(self):
        for rec in self:
            rec.is_locked = rec.state in ("validated", "released", "cancelled")

    @api.depends("line_ids.flag", "line_ids.is_abnormal", "line_ids.is_critical")
    def _compute_flags_counter(self):
        for rec in self:
            rec.abnormal_count = len(rec.line_ids.filtered(lambda l: l.is_abnormal))
            rec.critical_count = len(rec.line_ids.filtered(lambda l: l.is_critical))

    def _compute_invoice_count(self):
        AccountMove = self.env["account.move"]
        for rec in self:
            moves = AccountMove.search([
                ("line_ids", "in", rec.invoice_line_ids.ids or [0]),
                ("company_id", "=", rec.company_id.id),
                ("move_type", "in", ["out_invoice", "out_refund"]),
            ])
            rec.invoice_count = len(moves)

    # -------------------------------------------------------------------------
    # Onchange
    # -------------------------------------------------------------------------
    @api.onchange("session_id")
    def _onchange_session(self):
        sess = self.session_id
        if not sess:
            return
        vals = {}
        if sess.diagnosis_id and not self.diagnosis_id:
            vals["diagnosis_id"] = sess.diagnosis_id.id
        if sess.procedure_id and not self.procedure_id:
            vals["procedure_id"] = sess.procedure_id.id
        if not self.title and sess.procedure_id:
            vals["title"] = _("Result — %s") % (sess.procedure_id.display_name or sess.procedure_id.name)
        # tarik specimen time default dari sesi (jika available di konfigurasi; tidak memaksa)
        if not self.date_analyzed and sess.date_end:
            vals["date_analyzed"] = sess.date_end
        self.update(vals)

    # -------------------------------------------------------------------------
    # Constraint & Validasi
    # -------------------------------------------------------------------------
    _constraint_uniq_result_name_company = models.Constraint(
        'unique(name, company_id)',
        'Result number must be unique per company.',
    )

    @api.constrains("company_id", "encounter_id")
    def _check_company_consistency(self):
        for rec in self:
            if rec.encounter_id and rec.company_id and rec.company_id != rec.encounter_id.company_id:
                raise ValidationError(_("Result company must match Encounter company."))

    @api.constrains("date_collected", "date_analyzed", "date_released")
    def _check_date_consistency(self):
        for rec in self:
            if rec.date_collected and rec.date_analyzed and rec.date_analyzed < rec.date_collected:
                raise ValidationError(_("Analyzed On cannot be earlier than Collected On."))
            if rec.date_analyzed and rec.date_released and rec.date_released < rec.date_analyzed:
                raise ValidationError(_("Released On cannot be earlier than Analyzed On."))

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if vals.get("name", _("New")) in (False, _("New")):
                vals["name"] = seq.next_by_code("clinic.result.document") or _("New")
            # guard: wajib encounter_id
            if not vals.get("encounter_id") and vals.get("session_id"):
                sess = self.env["clinic.procedure.session"].browse(vals["session_id"])
                if sess and sess.encounter_id:
                    vals["encounter_id"] = sess.encounter_id.id
        recs = super().create(vals_list)
        # Activity review
        for rec in recs:
            try:
                rec.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Complete & validate result"),
                    user_id=rec.encounter_id.user_id.id if rec.encounter_id and rec.encounter_id.user_id else self.env.user.id,
                    date_deadline=fields.Date.today(),
                )
            except Exception:
                pass
        return recs

    def write(self, vals):
        # Cegah edit nilai konten saat locked (Draft-only editing)
        blocked_fields = {"title", "summary", "note_internal"}
        if blocked_fields & set(vals.keys()):
            for rec in self:
                if rec.is_locked and not self.env.context.get("allow_locked_write"):
                    raise UserError(_("This result is locked. Unrelease or create a new revision if editing is required."))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.state in ("validated", "released") and not self.env.user.has_group("base.group_system"):
                raise UserError(_("You cannot delete a validated/released result."))
        return super().unlink()

    # -------------------------------------------------------------------------
    # Workflow
    # -------------------------------------------------------------------------
    def action_set_draft(self):
        for rec in self:
            if rec.state == "cancelled":
                raise UserError(_("Cancelled results cannot be reset to Draft."))
            rec.write({"state": "draft"})
        return True

    def action_validate(self):
        """Validasi (lock) – pastikan ada konten (baris atau ringkasan/lampiran)."""
        for rec in self:
            has_content = bool(rec.line_ids) or bool(rec.summary) or bool(rec.attachment_ids)
            if not has_content:
                raise UserError(_("Cannot validate an empty result. Please add at least one value, summary, or attachment."))
            vals = {
                "state": "validated",
                "validated_by_id": self.env.user.id,
                "date_validated": fields.Datetime.now(),
            }
            # Set analyzed_on jika belum ada
            if not rec.date_analyzed:
                vals["date_analyzed"] = fields.Datetime.now()
            rec.write(vals)
            # Follow-up activity: release
            try:
                rec.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Release result to patient/portal"),
                    user_id=rec.encounter_id.user_id.id if rec.encounter_id and rec.encounter_id.user_id else self.env.user.id,
                    date_deadline=fields.Date.today(),
                )
            except Exception:
                pass
        return True

    def action_release(self):
        """Rilis ke pasien/portal (lock)."""
        for rec in self:
            if rec.state not in ("validated", "released"):
                raise UserError(_("Only validated results can be released."))
            vals = {
                "state": "released",
                "released_by_id": self.env.user.id,
                "date_released": fields.Datetime.now(),
            }
            rec.write(vals)
            # Opsional: kirim notifikasi email template jika disediakan
            try:
                template = self.env.ref("clinic_encounter.mail_template_result_released")
                if template:
                    template.send_mail(rec.id, force_send=False)
            except Exception:
                pass
        return True

    def action_cancel(self, reason=None):
        for rec in self:
            rec.write({"state": "cancelled"})
            if reason:
                rec.message_post(body=_("Result cancelled: %s") % reason)
        return True

    # -------------------------------------------------------------------------
    # Actions & Smart Buttons
    # -------------------------------------------------------------------------
    def action_open_encounter(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_encounter").read()[0]
        action["res_id"] = self.encounter_id.id
        action["domain"] = [("id", "=", self.encounter_id.id)]
        action["view_mode"] = "form"
        return action

    def action_open_session(self):
        self.ensure_one()
        if not self.session_id:
            raise UserError(_("This result is not linked to a session."))
        action = self.env.ref("clinic_encounter.action_clinic_procedure_session").read()[0]
        action["res_id"] = self.session_id.id
        action["domain"] = [("id", "=", self.session_id.id)]
        action["view_mode"] = "form"
        return action

    def action_view_invoices(self):
        self.ensure_one()
        AccountMove = self.env["account.move"]
        moves = AccountMove.search([
            ("line_ids", "in", self.invoice_line_ids.ids or [0]),
            ("company_id", "=", self.company_id.id),
            ("move_type", "in", ["out_invoice", "out_refund"]),
        ])
        if not moves and self.encounter_id:
            moves = AccountMove.search([
                ("invoice_origin", "=", self.encounter_id.name),
                ("move_type", "in", ["out_invoice", "out_refund"]),
                ("company_id", "=", self.company_id.id),
            ])
        if not moves:
            raise UserError(_("No related invoices found."))
        action = self.env.ref("account.action_move_out_invoice_type").read()[0]
        action["domain"] = [("id", "in", moves.ids)]
        return action

    def action_print_report(self):
        """Cetak report QWeb jika template tersedia (opsional)."""
        self.ensure_one()
        try:
            return self.env.ref("clinic_encounter.action_report_result_document").report_action(self)
        except Exception:
            raise UserError(_("Report template is not configured."))

    # -------------------------------------------------------------------------
    # Utilitas
    # -------------------------------------------------------------------------
    def add_value(self, name, value_number=None, value_text=None, unit=None, low=None, high=None, group=None, code=None):
        """Helper cepat menambah 1 parameter hasil."""
        self.ensure_one()
        vals = {
            "result_id": self.id,
            "name": name,
            "code": code or False,
            "value_type": "number" if value_number is not None else "text",
            "value_number": value_number,
            "value_text": value_text,
            "unit": unit,
            "ref_low": low,
            "ref_high": high,
            "group_id": group.id if getattr(group, "id", False) else False,
        }
        return self.env["clinic.result.value"].create(vals)


# =============================================================================
# Model: Result Value (detail baris parameter)
# =============================================================================
class ClinicResultValue(models.Model):
    _name = "clinic.result.value"
    _description = "Clinical Result Value"
    _order = "result_id, sequence, id"
    _check_company_auto = True

    # Header
    result_id = fields.Many2one(
        "clinic.result.document",
        string="Result Document",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="result_id.company_id",
        store=True,
        readonly=True,
    )
    patient_id = fields.Many2one(
        "clinic.patient",
        related="result_id.patient_id",
        store=True,
        readonly=True,
    )

    # Identitas & urutan
    sequence = fields.Integer(default=10, index=True)
    group_id = fields.Many2one("clinic.result.group", string="Group/Panel", ondelete="set null", index=True)

    # Definisi parameter
    name = fields.Char(string="Parameter", required=True, translate=True, index=True)
    code = fields.Char(string="Code", index=True, help="Optional parameter code (LOINC/Local).")
    method = fields.Char(string="Method")
    device = fields.Char(string="Device")
    notes = fields.Char(string="Notes")

    # Nilai
    value_type = fields.Selection(
        [("number", "Number"), ("text", "Text"), ("boolean", "Yes/No")],
        string="Value Type",
        default="number",
        required=True,
        index=True,
    )
    value_number = fields.Float(string="Value (Number)", digits=(16, 4))
    value_text = fields.Char(string="Value (Text)")
    value_bool = fields.Boolean(string="Value (Yes/No)")
    unit = fields.Char(string="Unit")
    uom_id = fields.Many2one("uom.uom", string="UoM", help="Optional structured UoM; unit text is still stored for printing.")

    # Referensi rentang
    ref_low = fields.Float(string="Ref. Low", digits=(16, 4))
    ref_high = fields.Float(string="Ref. High", digits=(16, 4))
    ref_text = fields.Char(string="Reference Text")

    # Flag & interpretasi
    flag = fields.Selection(
        [
            ("N", "Normal"),
            ("L", "Low"),
            ("H", "High"),
            ("C", "Critical"),
            ("A", "Abnormal"),
        ],
        string="Flag",
        compute="_compute_flags",
        store=True,
    )
    is_abnormal = fields.Boolean(string="Abnormal?", compute="_compute_flags", store=True)
    is_critical = fields.Boolean(string="Critical?", compute="_compute_flags", store=True)

    # Tampilan
    display_value = fields.Char(string="Display Value", compute="_compute_display_value", store=True)

    color = fields.Integer(string="Color Index")

    # -------------------------------------------------------------------------
    # Komputasi
    # -------------------------------------------------------------------------
    @api.depends("value_type", "value_number", "value_text", "value_bool", "unit", "uom_id")
    def _compute_display_value(self):
        for rec in self:
            if rec.value_type == "number":
                txt = "" if rec.value_number is False else ("%s" % rec.value_number)
                if rec.unit:
                    txt = f"{txt} {rec.unit}"
                elif rec.uom_id:
                    txt = f"{txt} {rec.uom_id.display_name}"
                rec.display_value = txt or False
            elif rec.value_type == "boolean":
                rec.display_value = _("Yes") if rec.value_bool else _("No")
            else:
                rec.display_value = rec.value_text or False

    @api.depends("value_type", "value_number", "ref_low", "ref_high")
    def _compute_flags(self):
        for rec in self:
            is_abn = False
            is_crit = False
            flag = "N"
            if rec.value_type == "number" and rec.value_number is not None:
                vn = rec.value_number
                # Critical menggunakan ref_text yang berisi pola "critical:<low>-<high>"? -> sengaja tidak memaksa.
                # Kita hanya deteksi Low/High berdasarkan ref_low/ref_high; admin bisa set "C" manual jika diperlukan.
                if rec.ref_low is not None and rec.ref_high is not None:
                    if vn < rec.ref_low:
                        flag = "L"
                        is_abn = True
                    elif vn > rec.ref_high:
                        flag = "H"
                        is_abn = True
                    else:
                        flag = "N"
                elif rec.ref_low is not None:
                    if vn < rec.ref_low:
                        flag = "L"; is_abn = True
                elif rec.ref_high is not None:
                    if vn > rec.ref_high:
                        flag = "H"; is_abn = True
                # Critical flag — biarkan manual via ref_text atau wizard (tidak otomatis).
            else:
                # Teks/boolean: tidak ada perhitungan otomatis; admin bisa tandai Abnormal manual
                pass

            rec.flag = flag
            rec.is_abnormal = is_abn or (flag in ("L", "H", "C", "A"))
            rec.is_critical = (flag == "C")

    # -------------------------------------------------------------------------
    # Constraint
    # -------------------------------------------------------------------------
    _constraint_name_not_empty = models.Constraint(
        "CHECK (char_length(coalesce(name, '')) > 0)",
        'Parameter must have a name.',
    )

    @api.constrains("value_type", "value_number")
    def _check_number_presence(self):
        for rec in self:
            if rec.value_type == "number" and rec.value_number is None:
                raise ValidationError(_("Numeric parameter must have a numeric value."))

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def mark_abnormal(self, critical=False):
        """Tandai secara manual abnormal/critical untuk kasus non-numerik."""
        for rec in self:
            rec.write({"flag": "C" if critical else "A"})


# # =============================================================================
# # EXTENSIONS & Bridges (opsional pelengkap)
# # =============================================================================
# class ClinicProcedureSession_ResultDocument(models.Model):
#     _inherit = "clinic.procedure.session"

#     result_ids = fields.One2many(
#         "clinic.result.document", "session_id", string="Results"
#     )
#     result_count = fields.Integer(compute="_compute_result_count", string="Results", store=False)

#     def _compute_result_count(self):
#         for rec in self:
#             rec.result_count = len(rec.result_ids)

#     def action_open_results(self):
#         self.ensure_one()
#         action = self.env.ref("clinic_encounter.action_clinic_result_document").read()[0]
#         action["domain"] = [("session_id", "=", self.id)]
#         action["context"] = {"default_session_id": self.id, "default_encounter_id": self.encounter_id.id}
#         return action

#     def action_create_quick_result(self):
#         """Buat hasil kosong terhubung ke sesi ini (helper cepat)."""
#         self.ensure_one()
#         res = self.env["clinic.result.document"].create({
#             "encounter_id": self.encounter_id.id,
#             "session_id": self.id,
#             "procedure_id": self.procedure_id.id if self.procedure_id else False,
#             "title": _("Result — %s") % (self.procedure_id.display_name if self.procedure_id else self.name),
#         })
#         return {
#             "type": "ir.actions.act_window",
#             "name": _("Result"),
#             "res_model": "clinic.result.document",
#             "res_id": res.id,
#             "view_mode": "form",
#         }


# class ClinicEncounter_ResultDocument(models.Model):
#     _inherit = "clinic.encounter"

#     result_ids = fields.One2many("clinic.result.document", "encounter_id", string="Results")
#     result_count = fields.Integer(compute="_compute_result_count", string="Results", store=False)

#     def _compute_result_count(self):
#         for rec in self:
#             rec.result_count = len(rec.result_ids)

#     def action_open_results(self):
#         self.ensure_one()
#         action = self.env.ref("clinic_encounter.action_clinic_result_document").read()[0]
#         action["domain"] = [("encounter_id", "=", self.id)]
#         action["context"] = {"default_encounter_id": self.id}
#         return action


# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/procedure_step.py
#
# Fungsi:
# - Mendefinisikan langkah-langkah (template) dari sebuah prosedur klinis.
# - Mendukung checklist tiap langkah, dependensi (predecessors), dan atribut mutu/risiko.
# - Integrasi "soft-coupled" dengan sesi tindakan; menyediakan helper untuk menyiapkan
#   vals pembuatan session-step jika model itu tersedia (tanpa memaksa dependensi).
#
# Kaitan utama:
# - procedure_id -> clinic.procedure.catalog
# - tag_ids      -> clinic.procedure.tag (untuk pelabelan/pencarian)
# - checklist    -> clinic.procedure.step.checklist (item per langkah)
#
# Integrasi lintas-modul (opsional, aman bila modul tidak ada):
# - Jika nanti dibuat model `clinic.procedure.session.step`, method
#   `prepare_session_step_vals()` sudah siap dipakai oleh generator sesi.
#
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# ---------------------------------------------------------------------------
# Template Langkah Prosedur
# ---------------------------------------------------------------------------
class ClinicProcedureStep(models.Model):
    _name = "clinic.procedure.step"
    _description = "Procedure Step (Template)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "procedure_id, sequence, id"
    _check_company_auto = True

    # Identitas & Konteks
    name = fields.Char(
        string="Step Title",
        required=True,
        translate=True,
        index=True,
        tracking=True,
    )
    code = fields.Char(
        string="Step Code",
        index=True,
        help="Optional internal code for this step.",
    )
    sequence = fields.Integer(
        default=10,
        index=True,
        help="Order of this step within the procedure.",
    )
    active = fields.Boolean(default=True, tracking=True)

    procedure_id = fields.Many2one(
        "clinic.procedure.catalog",
        string="Procedure",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
        help="The procedure this step belongs to.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="procedure_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    tag_ids = fields.Many2many("clinic.procedure.tag", string="Tags")

    # Konten & Instruksi
    description = fields.Html(string="Description / Details")
    instructions = fields.Html(string="Instructions (How-To)")
    expected_result = fields.Html(string="Expected Result / Outcome")
    notes = fields.Text(string="Internal Notes")

    # Durasi & Timer
    duration_min = fields.Float(
        string="Expected Duration (min)",
        help="Estimated duration for this step (minutes).",
    )
    use_timer = fields.Boolean(
        string="Use Timer",
        help="If enabled, session may track real-time elapsed for this step.",
        default=True,
    )

    # Kebijakan Klinis / Mutu
    mandatory = fields.Boolean(
        string="Mandatory",
        default=True,
        help="If enabled, the step is required; sessions may prevent completion if skipped without reason.",
    )
    is_critical = fields.Boolean(
        string="Critical Step",
        help="If critical, extra alerts may be shown before skipping.",
    )
    qc_checkpoint = fields.Boolean(
        string="Quality Checkpoint",
        help="If enabled, this step acts as a QC gate (e.g., requires supervisor verification).",
    )
    risk_level = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")],
        string="Risk Level",
        default="low",
        index=True,
        help="Qualitative risk level for this step (used for analytics/QA).",
    )
    required_equipment = fields.Char(
        string="Required Equipment",
        help="Free-text equipment/hardware needed (soft-coupled; no strict device model dependency).",
    )
    required_ppe = fields.Char(
        string="Required PPE",
        help="Personal protective equipment requirements (free-text).",
    )

    # Checklist & Dependensi
    checklist_ids = fields.One2many(
        "clinic.procedure.step.checklist",
        "step_id",
        string="Checklist",
        help="Default checklist items to be executed and documented for this step.",
    )
    dependency_ids = fields.Many2many(
        "clinic.procedure.step",
        "clinic_proc_step_dep_rel",
        "step_id",
        "depends_on_step_id",
        string="Depends On",
        help="This step requires these predecessor steps to be considered complete first.",
    )

    # Analitik Penggunaan (ringan)
    plan_count = fields.Integer(
        string="Plans Using Procedure",
        compute="_compute_usage_counters",
        store=False,
        help="Number of encounter procedure lines that reference this step's procedure.",
    )
    session_count = fields.Integer(
        string="Sessions of Procedure",
        compute="_compute_usage_counters",
        store=False,
        help="Number of sessions created for this step's procedure (if linked).",
    )

    color = fields.Integer(string="Color Index")

    # ------------------------------------------------------------
    # Komputasi
    # ------------------------------------------------------------
    def _compute_usage_counters(self):
        Plan = self.env["clinic.encounter.procedure"]
        Session = self.env["clinic.procedure.session"]
        for rec in self:
            # Hitung entitas yang menggunakan procedure terkait (bukan by-step, karena step adalah template)
            rec.plan_count = Plan.search_count([("procedure_id", "=", rec.procedure_id.id)]) if rec.procedure_id else 0
            rec.session_count = Session.search_count([("procedure_id", "=", rec.procedure_id.id)]) if rec.procedure_id and "procedure_id" in Session._fields else 0

    # ------------------------------------------------------------
    # Onchange
    # ------------------------------------------------------------
    @api.onchange("procedure_id")
    def _onchange_procedure_id(self):
        # Sinkron default durasi dari katalog jika kosong
        if self.procedure_id and not self.duration_min and self.procedure_id.default_duration_min:
            self.duration_min = self.procedure_id.default_duration_min

    # ------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------
    _constraint_check_duration = models.Constraint(
        'CHECK (duration_min >= 0)',
        'Duration must be positive or zero.',
    )

    @api.constrains("dependency_ids")
    def _check_dependency_cycle(self):
        """Cegah dependensi diri sendiri & siklus sederhana."""
        for rec in self:
            if rec in rec.dependency_ids:
                raise ValidationError(_("A step cannot depend on itself."))

            # Cek siklus sederhana: if A depends on B and B depends on A
            for dep in rec.dependency_ids:
                if rec in dep.dependency_ids:
                    raise ValidationError(_("Circular dependency detected between '%s' and '%s'.") % (rec.display_name, dep.display_name))

    # ------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            # Aktivitas ringan untuk melengkapi checklist bila kosong
            if not rec.checklist_ids:
                try:
                    rec.activity_schedule(
                        "mail.mail_activity_data_todo",
                        summary=_("Add checklist to step '%s'") % (rec.display_name or rec.name,),
                        user_id=self.env.user.id,
                        date_deadline=fields.Date.today(),
                    )
                except Exception:
                    pass
        return recs

    # ------------------------------------------------------------
    # Actions (Smart Buttons / Helper)
    # ------------------------------------------------------------
    def action_open_procedure(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_procedure_catalog").read()[0]
        action["res_id"] = self.procedure_id.id
        action["domain"] = [("id", "=", self.procedure_id.id)]
        action["view_mode"] = "form"
        return action

    def action_open_related_plans(self):
        """Lihat semua rencana prosedur yang memakai procedure terkait step ini."""
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_encounter_procedure").read()[0]
        action["domain"] = [("procedure_id", "=", self.procedure_id.id)]
        return action

    def action_open_related_sessions(self):
        """Lihat semua sesi tindakan untuk procedure terkait step ini (jika linked)."""
        self.ensure_one()
        Session = self.env["clinic.procedure.session"]
        if "procedure_id" not in Session._fields:
            raise UserError(_("Session model doesn't link to procedure catalog in this configuration."))
        action = self.env.ref("clinic_encounter.action_clinic_procedure_session").read()[0]
        action["domain"] = [("procedure_id", "=", self.procedure_id.id)]
        return action

    # ------------------------------------------------------------
    # Helpers untuk instansiasi Step ke Sesi (soft-coupled)
    # ------------------------------------------------------------
    def prepare_session_step_vals(self, session, index=1):
        """
        Siapkan nilai default untuk membuat record langkah di dalam suatu sesi.
        Metode ini tidak membuat record apa pun — hanya menyiapkan dict.
        Aman dipanggil meski model session-step belum ada.
        Diharapkan model target kurang-lebih memiliki field:
          - session_id (M2o clinic.procedure.session)
          - procedure_id (M2o clinic.procedure.catalog)
          - step_template_id (M2o clinic.procedure.step)
          - sequence, name, mandatory, is_critical, qc_checkpoint
          - required_equipment, required_ppe
          - duration_planned (float, menit)
          - use_timer (bool)
        """
        self.ensure_one()
        if not session or not getattr(session, "id", False):
            raise UserError(_("Session is required to prepare a session step."))

        return {
            "session_id": session.id,
            "procedure_id": self.procedure_id.id if self.procedure_id else False,
            "step_template_id": self.id,
            "sequence": (self.sequence or 10) + (index - 1) * 10,
            "name": self.name,
            "mandatory": self.mandatory,
            "is_critical": self.is_critical,
            "qc_checkpoint": self.qc_checkpoint,
            "required_equipment": self.required_equipment,
            "required_ppe": self.required_ppe,
            "duration_planned": self.duration_min or (self.procedure_id.default_duration_min if self.procedure_id else 0.0),
            "use_timer": self.use_timer,
            # Checklist template akan diinstansiasi terpisah (lihat helper di bawah).
        }

    def prepare_session_step_checklist_vals(self, session_step):
        """
        Siapkan list of dict untuk membuat checklist pada session-step berdasarkan template checklist_ids.
        Diharapkan model target memiliki field:
          - session_step_id (M2o ke session-step)
          - sequence, name, is_required, instruction
        """
        self.ensure_one()
        if not session_step or not getattr(session_step, "id", False):
            raise UserError(_("Session step is required to prepare checklist items."))

        vals_list = []
        for i, item in enumerate(self.checklist_ids.sorted(lambda c: c.sequence)):
            vals_list.append({
                "session_step_id": session_step.id,
                "sequence": (item.sequence or 10) + i,
                "name": item.name,
                "is_required": item.is_required,
                "instruction": item.instruction,
            })
        return vals_list

    # ------------------------------------------------------------
    # Name & Search
    # ------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            label = rec.name
            if rec.procedure_id:
                label = f"{rec.procedure_id.display_name or rec.procedure_id.name} • {rec.sequence:02d} {rec.name}"
            res.append((rec.id, label))
        return res

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        extra_domain = list(domain or [])
        name_domain = ["|", "|",
                  ("name", operator, name),
                  ("code", operator, name),
                  ("procedure_id.name", operator, name)]
        recs = self.search(name_domain + extra_domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]


# ---------------------------------------------------------------------------
# Checklist Item Template untuk Step
# ---------------------------------------------------------------------------
class ClinicProcedureStepChecklist(models.Model):
    _name = "clinic.procedure.step.checklist"
    _description = "Procedure Step Checklist (Template)"
    _order = "step_id, sequence, id"
    _check_company_auto = True

    sequence = fields.Integer(default=10, index=True)
    active = fields.Boolean(default=True)

    step_id = fields.Many2one(
        "clinic.procedure.step",
        string="Step",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="step_id.company_id",
        store=True,
        readonly=True,
    )

    name = fields.Char(string="Checklist Item", required=True, translate=True)
    instruction = fields.Char(
        string="Instruction",
        help="Short instruction/criteria for this checklist item.",
    )
    is_required = fields.Boolean(
        string="Required",
        default=True,
        help="If enabled, this item must be checked/filled in sessions.",
    )

    # Visual
    color = fields.Integer(string="Color Index")

    # Constraint
    _constraint_name_not_empty = models.Constraint(
        "CHECK (char_length(coalesce(name, '')) > 0)",
        'Checklist item must have a name.',
    )


# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/procedure_session.py
#
# Gabungan penuh:
# - BASE clinic.procedure.session (timer, performer, billing, inventory bridges)
# - + Result bridges (result_ids, result_count, actions)
# - + Consent bridges (consent_valid compute)
# - + Checklist bridges (checklist_ids, compliant, actions, preflight check)
# - + Adverse Event bridges (ae_ids, actions)
# - + Execution Log hooks (auto-log create/start/pause/resume/done/cancel, log_note)
#
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicProcedureSession(models.Model):
    _name = "clinic.procedure.session"
    _description = "Procedure Session"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identitas & Perusahaan
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Session #",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        index=True,
        tracking=True,
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10, index=True)

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Konteks Encounter & Rencana
    # -------------------------------------------------------------------------
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Encounter",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    encounter_procedure_id = fields.Many2one(
        "clinic.encounter.procedure",
        string="Plan Line",
        ondelete="set null",
        index=True,
        help="The plan line this session belongs to.",
    )
    diagnosis_id = fields.Many2one(
        "clinic.diagnosis",
        string="Diagnosis",
        ondelete="set null",
        index=True,
    )

    # Master procedure (untuk referensi/label/report)
    procedure_id = fields.Many2one(
        "clinic.procedure.catalog",
        string="Procedure",
        ondelete="restrict",
        index=True,
        help="The catalog procedure being executed.",
    )
    # Produk & harga (diizinkan override per session)
    product_id = fields.Many2one("product.product", string="Product")
    uom_id = fields.Many2one("uom.uom", string="UoM")
    quantity = fields.Float(string="Quantity", default=1.0, digits="Product Unit of Measure")

    # -------------------------------------------------------------------------
    # Performer, Room, & Scheduling
    # -------------------------------------------------------------------------
    performer_user_id = fields.Many2one("res.users", string="Performer (User)", tracking=True)
    performer_doctor_id = fields.Many2one("clinic.doctor", string="Performer (Doctor)", tracking=True)
    room_id = fields.Many2one("clinic.room", string="Room")

    planned_start = fields.Datetime(string="Planned Start")
    planned_end = fields.Datetime(string="Planned End")
    planned_duration = fields.Float(string="Planned Duration (min)")

    date_start = fields.Datetime(string="Start", tracking=True)
    date_end = fields.Datetime(string="End", tracking=True)
    actual_duration = fields.Float(
        string="Actual Duration (min)",
        compute="_compute_actual_duration",
        store=True,
    )

    # State machine
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("paused", "Paused"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
    )

    # -------------------------------------------------------------------------
    # Consent, Checklist, Hasil
    # -------------------------------------------------------------------------
    require_consent = fields.Boolean(
        string="Require Consent",
        compute="_compute_requirements",
        store=True,
        help="Derived from catalog. Start is blocked if True and there is no valid consent covering this procedure.",
    )
    require_checklist = fields.Boolean(
        string="Require Checklist",
        compute="_compute_requirements",
        store=True,
    )
    # VALIDITAS consent yang relevan dengan prosedur di sesi ini
    consent_valid = fields.Boolean(
        string="Consent Valid for Session",
        compute="_compute_consent_valid_for_session",
        store=False,
        help="True if the encounter has a signed, non-expired consent that covers this session's procedure (or is generic).",
    )
    # CHECKLIST bridges
    # checklist_ids = fields.One2many("clinic.checklist", "session_id", string="Checklists")
    checklist_count = fields.Integer(compute="_compute_checklist_count", string="Checklists", store=False)
    checklist_compliant = fields.Boolean(
        string="Checklist Compliant",
        compute="_compute_checklist_compliant",
        store=False,
        help="True if there exists at least one DONE & PASSED checklist linked to this session.",
    )
    # RESULT bridges
    result_ids = fields.One2many("clinic.result.document", "session_id", string="Results")
    result_count = fields.Integer(compute="_compute_result_count", string="Results", store=False)
    # AE bridges
    # ae_ids = fields.One2many("clinic.adverse.event", "session_id", string="Adverse Events")
    ae_count = fields.Integer(string="Adverse Events", compute="_compute_ae_count", store=False)

    # Catatan outcome sesi
    result_text = fields.Html(string="Result / Outcome")
    adverse_event_note = fields.Text(string="Adverse Event Note")
    internal_note = fields.Text(string="Internal Notes")

    # -------------------------------------------------------------------------
    # Penagihan (Per-Session) & Pajak
    # -------------------------------------------------------------------------
    billing_policy = fields.Selection(
        [
            ("per_plan", "Bill per Plan Line"),
            ("per_session", "Bill per Session"),
            ("no_bill", "Do Not Bill"),
        ],
        string="Billing Policy",
        default="per_session",
        help="Default follows plan/catalog; can be overridden for this session.",
    )
    price_unit = fields.Monetary(
        string="Unit Price (Override)",
        currency_field="currency_id",
        help="Leave empty to inherit price from plan line; filled to override.",
    )
    discount = fields.Float(string="Discount (%)", digits=(16, 4))
    tax_ids = fields.Many2many(
        "account.tax",
        "clinic_proc_session_tax_rel",
        "session_id",
        "tax_id",
        string="Customer Taxes",
        domain=[("type_tax_use", "in", ["sale", "none"])],
    )

    price_unit_effective = fields.Monetary(
        string="Effective Unit Price",
        currency_field="currency_id",
        compute="_compute_effective_price",
        store=True,
    )
    price_subtotal = fields.Monetary(string="Subtotal", currency_field="currency_id", compute="_compute_amount", store=True)
    price_tax = fields.Monetary(string="Tax", currency_field="currency_id", compute="_compute_amount", store=True)
    price_total = fields.Monetary(string="Total", currency_field="currency_id", compute="_compute_amount", store=True)

    invoice_line_ids = fields.Many2many(
        "account.move.line",
        "clinic_session_invoice_line_rel",
        "session_id",
        "aml_id",
        string="Invoice Lines",
        help="Billing lines generated from this session.",
    )
    invoice_count = fields.Integer(string="Invoices", compute="_compute_invoice_count", store=False)

    # -------------------------------------------------------------------------
    # Inventory Bridge (opsional melalui aksi)
    # -------------------------------------------------------------------------
    stock_move_ids = fields.Many2many(
        "stock.move",
        "clinic_session_stock_move_rel",
        "session_id",
        "move_id",
        string="Stock Moves",
        help="Consumption/transfer moves linked to this session.",
    )
    stock_move_count = fields.Integer(string="Stock Moves", compute="_compute_stock_move_count", store=False)

    # UI
    color = fields.Integer(string="Color Index")
    priority = fields.Selection([("0", "Normal"), ("1", "High"), ("2", "Urgent")], default="0", index=True)

    # treatment_id = fields.Many2one(
    #     "clinic.treatment.catalog",
    #     string="Treatment (Compatibility)",
    #     ondelete="set null",
    #     index=True,
    #     help="Compatibility alias for legacy modules expecting 'treatment_id'. "
    #          "New workflow uses 'procedure_id' to 'clinic.procedure.catalog'."
    # )

    # Kompatibilitas untuk modul lama yang punya One2many(..., 'treatment_id')
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment (Legacy Link)",
        index=True,
        ondelete="set null",
        help="Compatibility anchor for modules that define One2many to clinic.procedure.session via 'treatment_id'."
    )

    # -------------------------------------------------------------------------
    # Komputasi
    # -------------------------------------------------------------------------
    @api.depends("date_start", "date_end")
    def _compute_actual_duration(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end >= rec.date_start:
                delta = rec.date_end - rec.date_start
                rec.actual_duration = delta.total_seconds() / 60.0
            else:
                rec.actual_duration = 0.0

    @api.depends("procedure_id.require_consent", "procedure_id.require_checklist")
    def _compute_requirements(self):
        for rec in self:
            rec.require_consent = bool(rec.procedure_id and rec.procedure_id.require_consent)
            rec.require_checklist = bool(rec.procedure_id and rec.procedure_id.require_checklist)

    @api.depends("price_unit", "encounter_procedure_id.price_unit", "procedure_id.list_price")
    def _compute_effective_price(self):
        for rec in self:
            if rec.price_unit:
                rec.price_unit_effective = rec.price_unit
            elif rec.encounter_procedure_id and rec.encounter_procedure_id.price_unit:
                rec.price_unit_effective = rec.encounter_procedure_id.price_unit
            elif rec.procedure_id and rec.procedure_id.list_price:
                rec.price_unit_effective = rec.procedure_id.list_price
            else:
                rec.price_unit_effective = 0.0

    @api.depends("price_unit_effective", "quantity", "discount", "tax_ids", "currency_id", "product_id", "encounter_id.partner_id")
    def _compute_amount(self):
        for rec in self:
            qty = rec.quantity or 0.0
            unit = rec.price_unit_effective or 0.0
            effective_price = unit * (1 - (rec.discount or 0.0) / 100.0)

            if rec.tax_ids:
                taxes = rec.tax_ids.compute_all(
                    effective_price,
                    currency=rec.currency_id,
                    quantity=qty,
                    product=rec.product_id,
                    partner=rec.encounter_id.partner_id if rec.encounter_id else None,
                )
                rec.price_subtotal = taxes["total_excluded"]
                rec.price_total = taxes["total_included"]
                rec.price_tax = sum(t["amount"] for t in taxes.get("taxes", []))
            else:
                rec.price_subtotal = effective_price * qty
                rec.price_total = effective_price * qty
                rec.price_tax = 0.0

    def _compute_invoice_count(self):
        AccountMove = self.env["account.move"]
        for rec in self:
            moves = AccountMove.search([
                ("line_ids", "in", rec.invoice_line_ids.ids or [0]),
                ("company_id", "=", rec.company_id.id),
                ("move_type", "in", ["out_invoice", "out_refund"]),
            ])
            rec.invoice_count = len(moves)

    def _compute_stock_move_count(self):
        for rec in self:
            rec.stock_move_count = len(rec.stock_move_ids)

    def _compute_result_count(self):
        for rec in self:
            rec.result_count = len(rec.result_ids)

    def _compute_ae_count(self):
        for rec in self:
            rec.ae_count = len(rec.ae_ids)

    def _compute_checklist_count(self):
        for rec in self:
            rec.checklist_count = len(rec.checklist_ids)

    @api.depends("checklist_ids.state", "checklist_ids.passed")
    def _compute_checklist_compliant(self):
        for rec in self:
            ok = any(cl.state == "done" and cl.passed for cl in rec.checklist_ids)
            rec.checklist_compliant = ok

    @api.depends("encounter_id.consent_ids.state", "encounter_id.consent_ids.date_expiry", "procedure_id")
    def _compute_consent_valid_for_session(self):
        for rec in self:
            valid = False
            enc = rec.encounter_id
            if enc:
                for c in enc.consent_ids.filtered(lambda r: r.state == "signed" and not r.is_expired):
                    if c.covers_procedure(rec.procedure_id):
                        valid = True
                        break
            rec.consent_valid = valid

    # -------------------------------------------------------------------------
    # Onchange
    # -------------------------------------------------------------------------
    @api.onchange("encounter_procedure_id")
    def _onchange_plan_line(self):
        line = self.encounter_procedure_id
        if not line:
            return
        vals = {}
        # Tarik konteks dari plan
        vals.update({
            "procedure_id": line.procedure_id.id if line.procedure_id else False,
            "product_id": line.product_id.id if line.product_id else False,
            "uom_id": line.uom_id.id if line.uom_id else False,
            "quantity": 1.0,  # per-session default qty 1
            "billing_policy": line.billing_policy or "per_session",
            "tax_ids": [(6, 0, line.tax_ids.ids)] if line.tax_ids else [],
        })
        # Durasi dari plan jika ada
        if line.planned_duration and not self.planned_duration:
            vals["planned_duration"] = line.planned_duration
        # Performer/room preferensi
        if line.performer_user_id and not self.performer_user_id:
            vals["performer_user_id"] = line.performer_user_id.id
        if line.performer_doctor_id and not self.performer_doctor_id:
            vals["performer_doctor_id"] = line.performer_doctor_id.id
        if line.room_id and not self.room_id:
            vals["room_id"] = line.room_id.id
        # Diagnosis dari plan jika ada
        if line.diagnosis_id and not self.diagnosis_id:
            vals["diagnosis_id"] = line.diagnosis_id.id
        self.update(vals)

    @api.onchange("procedure_id")
    def _onchange_procedure(self):
        proc = self.procedure_id
        if not proc:
            return
        vals = {}
        # Isi product/uom bila kosong
        if proc.product_id and not self.product_id:
            vals["product_id"] = proc.product_id.id
        if not self.uom_id:
            vals["uom_id"] = proc.uom_id.id if proc.uom_id else (proc.product_id.uom_id.id if proc.product_id else False)
        # Pajak default
        if proc.tax_ids and not self.tax_ids:
            vals["tax_ids"] = [(6, 0, proc.tax_ids.ids)]
        # Durasi default
        if proc.default_duration_min and not self.planned_duration:
            vals["planned_duration"] = proc.default_duration_min
        # Billing policy default bila kosong
        if not self.billing_policy:
            vals["billing_policy"] = proc.billing_policy or "per_session"
        self.update(vals)

    @api.onchange("product_id")
    def _onchange_product(self):
        prod = self.product_id
        if not prod:
            return
        vals = {}
        if not self.uom_id:
            vals["uom_id"] = prod.uom_id.id
        if prod.taxes_id and not self.tax_ids:
            vals["tax_ids"] = [(6, 0, prod.taxes_id.ids)]
        self.update(vals)

    # -------------------------------------------------------------------------
    # Constraint & Validasi
    # -------------------------------------------------------------------------
    _constraint_uniq_session_name_company = models.Constraint(
        'unique(name, company_id)',
        'Session number must be unique per company.',
    )
    _constraint_qty_nonneg = models.Constraint(
        'CHECK (quantity >= 0)',
        'Quantity must be positive or zero.',
    )

    @api.constrains("company_id", "encounter_id")
    def _check_company_consistency(self):
        for rec in self:
            if rec.encounter_id and rec.company_id and rec.company_id != rec.encounter_id.company_id:
                raise ValidationError(_("Session company must match Encounter company."))

    @api.constrains("planned_start", "planned_end")
    def _check_planned_window(self):
        for rec in self:
            if rec.planned_start and rec.planned_end and rec.planned_end < rec.planned_start:
                raise ValidationError(_("Planned End cannot be earlier than Planned Start."))

    @api.constrains("date_start", "date_end")
    def _check_actual_window(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_("End cannot be earlier than Start."))

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if vals.get("name", _("New")) in (False, _("New")):
                vals["name"] = seq.next_by_code("clinic.procedure.session") or _("New")
            # Warisi encounter dari plan jika belum diisi
            if not vals.get("encounter_id") and vals.get("encounter_procedure_id"):
                line = self.env["clinic.encounter.procedure"].browse(vals["encounter_procedure_id"])
                if line and line.encounter_id:
                    vals["encounter_id"] = line.encounter_id.id
        recs = super().create(vals_list)
        # Aktivitas default: minta start/eksekusi + EXEC-LOG create
        for rec in recs:
            try:
                rec.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Execute procedure session"),
                    user_id=rec.performer_user_id.id or (rec.encounter_id.user_id.id if rec.encounter_id and rec.encounter_id.user_id else self.env.user.id),
                    date_deadline=fields.Date.today(),
                )
            except Exception:
                pass
            # Auto-log "create"
            try:
                rec._log_event("create", message=_("Session created"), role="system")
            except Exception:
                pass
        return recs

    # -------------------------------------------------------------------------
    # Workflow Actions (+Execution Log hooks)
    # -------------------------------------------------------------------------
    def _preflight_start_checks(self):
        """
        Validasi pra-mulai:
        - Consent: jika diwajibkan oleh catalog, harus ada consent yang valid & mencakup prosedur.
        - Checklist: jika diwajibkan, harus ada checklist DONE & PASSED untuk session ini.
        """
        for rec in self:
            # Consent
            if rec.require_consent and not rec.consent_valid:
                raise UserError(_("Consent is required (valid and covering the procedure) before starting this session."))
            # Checklist
            if rec.require_checklist:
                ok = any(cl.state == "done" and cl.passed for cl in rec.checklist_ids)
                if not ok:
                    raise UserError(_("Checklist is required before starting this session. Please complete the required checklist."))
            # Catatan jika billing per session tapi tidak ada product/procedure
            if rec.billing_policy == "per_session" and not rec.product_id and not rec.procedure_id:
                rec.message_post(body=_("Billing policy is per session but product/procedure is not set."))

    def action_start(self):
        self._preflight_start_checks()
        now = fields.Datetime.now()
        for rec in self:
            updates = {"state": "in_progress"}
            if not rec.date_start:
                updates["date_start"] = now
            # Jika encounter masih draft, ubah ke in_progress
            try:
                if rec.encounter_id and rec.encounter_id.state == "draft":
                    rec.encounter_id.action_start()
            except Exception:
                pass
            rec.write(updates)
            # EXEC-LOG
            try:
                rec._log_event("start", message=_("Session started"), role="performer")
            except Exception:
                pass
        return True

    def action_pause(self, reason=None):
        for rec in self:
            if rec.state != "in_progress":
                raise UserError(_("Only 'In Progress' sessions can be paused."))
            rec.write({"state": "paused"})
            if reason:
                rec.message_post(body=_("Session paused: %s") % reason)
            # EXEC-LOG
            try:
                msg = _("Session paused") + (": %s" % reason if reason else "")
                rec._log_event("pause", message=msg, role="performer")
            except Exception:
                pass
        return True

    def action_resume(self):
        for rec in self:
            if rec.state != "paused":
                raise UserError(_("Only 'Paused' sessions can be resumed."))
            rec.write({"state": "in_progress"})
            # EXEC-LOG
            try:
                rec._log_event("resume", message=_("Session resumed"), role="performer")
            except Exception:
                pass
        return True

    def action_done(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.state not in ("in_progress", "paused", "draft"):
                raise UserError(_("Only Draft/In Progress/Paused sessions can be completed."))
            updates = {"state": "done"}
            if not rec.date_start:
                updates["date_start"] = now
            if not rec.date_end:
                updates["date_end"] = now
            rec.write(updates)

            # Tandai plan line done bila semua sesi pada line selesai
            line = rec.encounter_procedure_id
            if line:
                other_open = line.session_ids.filtered(lambda s: s.state not in ("done", "cancelled") and s.id != rec.id)
                if not other_open:
                    try:
                        line.action_done()
                    except Exception:
                        pass

            # Jadwalkan follow-up activity (opsional)
            try:
                rec.encounter_id.push_activity_followup(
                    summary=_("Review session results"),
                    days=1,
                    user=rec.encounter_id.user_id or rec.performer_user_id,
                )
            except Exception:
                pass
            # EXEC-LOG
            try:
                rec._log_event("done", message=_("Session completed"), role="performer")
            except Exception:
                pass
        return True

    def action_cancel(self, reason=None):
        for rec in self:
            rec.write({"state": "cancelled"})
            if reason:
                rec.message_post(body=_("Session cancelled: %s") % reason)
            # EXEC-LOG
            try:
                msg = _("Session cancelled") + (": %s" % reason if reason else "")
                rec._log_event("cancel", message=msg, role="performer")
            except Exception:
                pass
        return True

    # -------------------------------------------------------------------------
    # Billing Bridges
    # -------------------------------------------------------------------------
    def action_prepare_invoice_line_vals(self):
        """
        Kembalikan list of dict untuk pembuatan account.move.line.
        - Hanya aktif jika billing_policy == 'per_session'.
        - Qty default 1.0 (jumlah sesi), bisa diganti dengan rec.quantity bila diinginkan.
        """
        self.ensure_one()
        if self.billing_policy != "per_session":
            return []

        partner = self.encounter_id.partner_id if self.encounter_id else None
        if not partner:
            raise UserError(_("Patient partner is not set on the Encounter."))

        # Map pajak via fiscal position
        taxes = self.tax_ids
        fpos = partner.property_account_position_id if partner else False
        if fpos:
            taxes = fpos.map_tax(taxes, product=self.product_id, partner=partner)

        # Ambil account income dari product/category bila ada
        account_id = False
        if self.product_id and getattr(self.product_id, "property_account_income_id", False) and self.product_id.property_account_income_id:
            account_id = self.product_id.property_account_income_id.id
        elif self.product_id and self.product_id.categ_id and self.product_id.categ_id.property_account_income_categ_id:
            account_id = self.product_id.categ_id.property_account_income_categ_id.id

        price_unit = (self.price_unit_effective or 0.0) * (1 - (self.discount or 0.0) / 100.0)
        descr = self._default_invoice_line_description()

        return [{
            "name": descr,
            "quantity": self.quantity or 1.0,
            "price_unit": price_unit,
            "discount": 0.0,  # diskon sudah dihitung
            "product_id": self.product_id.id if self.product_id else False,
            "product_uom_id": self.uom_id.id if self.uom_id else (self.product_id.uom_id.id if self.product_id else False),
            "tax_ids": [(6, 0, taxes.ids)] if taxes else [],
            "account_id": account_id,
            "currency_id": self.currency_id.id,
        }]

    def _default_invoice_line_description(self):
        self.ensure_one()
        base = self.procedure_id.display_name if self.procedure_id else (self.product_id.display_name if self.product_id else self.name)
        parts = [base, self.name]
        if self.diagnosis_id:
            parts.append(_("Dx: %s") % (self.diagnosis_id.display_code or self.diagnosis_id.name))
        return " — ".join([p for p in parts if p])

    def action_open_billing(self):
        """Buka invoice yang terkait (berdasarkan invoice_line_ids atau invoice_origin encounter)."""
        self.ensure_one()
        AccountMove = self.env["account.move"]
        moves = AccountMove.search([
            ("line_ids", "in", self.invoice_line_ids.ids or [0]),
            ("company_id", "=", self.company_id.id),
            ("move_type", "in", ["out_invoice", "out_refund"]),
        ])
        if not moves:
            # Fallback via invoice_origin = encounter.name
            moves = AccountMove.search([
                ("invoice_origin", "=", self.encounter_id.name if self.encounter_id else False),
                ("move_type", "in", ["out_invoice", "out_refund"]),
                ("company_id", "=", self.company_id.id),
            ])
        if not moves:
            # Arahkan ke wizard generate bill (punya modul ini)
            action = self.env.ref("clinic_encounter.action_generate_bill_wizard").read()[0]
            action["context"] = {"default_encounter_id": self.encounter_id.id}
            return action
        action = self.env.ref("account.action_move_out_invoice_type").read()[0]
        action["domain"] = [("id", "in", moves.ids)]
        return action

    # -------------------------------------------------------------------------
    # Inventory Bridges (opsional di-trigger manual)
    # -------------------------------------------------------------------------
    def action_issue_consumables(self):
        """
        Buat draft picking & stock moves untuk konsumsi default procedure.consumable_ids.
        Membutuhkan konfigurasi lokasi & picking type.
        - System Parameters (optional):
            clinic.inventory.location_src_id     -> ID lokasi sumber (Many2one stock.location)
            clinic.inventory.location_consume_id -> ID lokasi tujuan konsumsi (Many2one stock.location)
            clinic.inventory.picking_type_int_id -> ID picking type internal (Many2one stock.picking.type)
        """
        StockPicking = self.env["stock.picking"]
        StockMove = self.env["stock.move"]
        Param = self.env["ir.config_parameter"].sudo()

        for rec in self:
            proc = rec.procedure_id
            if not proc or not proc.consumable_ids:
                raise UserError(_("No default consumables defined on the procedure."))

            # Ambil konfigurasi lokasi
            try:
                src_id = int(Param.get_param("clinic.inventory.location_src_id", 0)) or False
                dst_id = int(Param.get_param("clinic.inventory.location_consume_id", 0)) or False
                ptype_id = int(Param.get_param("clinic.inventory.picking_type_int_id", 0)) or False
            except Exception:
                src_id = dst_id = ptype_id = False

            if not (src_id and dst_id and ptype_id):
                raise UserError(_(
                    "Inventory configuration is missing.\n"
                    "Please set System Parameters: clinic.inventory.location_src_id, "
                    "clinic.inventory.location_consume_id, clinic.inventory.picking_type_int_id."
                ))

            picking_vals = {
                "picking_type_id": ptype_id,
                "location_id": src_id,
                "location_dest_id": dst_id,
                "origin": rec.encounter_id.name if rec.encounter_id else rec.name,
                "company_id": rec.company_id.id,
                "note": _("Consumables for %s") % (rec.display_name or rec.name),
            }
            picking = StockPicking.create(picking_vals)

            # Buat moves sesuai consumables
            for cons in proc.consumable_ids:
                if not cons.product_id:
                    continue
                uom = cons.uom_id or cons.product_id.uom_id
                qty = (cons.quantity or 0.0) * (rec.quantity or 1.0)
                if qty <= 0.0:
                    continue
                move_vals = {
                    "name": "%s — %s" % (rec.name, cons.product_id.display_name),
                    "product_id": cons.product_id.id,
                    "product_uom_qty": qty,
                    "product_uom": uom.id,
                    "location_id": src_id,
                    "location_dest_id": dst_id,
                    "picking_id": picking.id,
                    "company_id": rec.company_id.id,
                    "origin": picking.origin,
                }
                move = StockMove.create(move_vals)
                rec.stock_move_ids = [(4, move.id)]
            # Tampilkan picking
            action = self.env.ref("stock.action_picking_tree_all").read()[0]
            action["domain"] = [("id", "=", picking.id)]
            return action

    def action_open_stock_moves(self):
        self.ensure_one()
        if not self.stock_move_ids:
            raise UserError(_("No stock moves linked to this session."))
        action = self.env.ref("stock.action_move_form").read()[0]
        action["domain"] = [("id", "in", self.stock_move_ids.ids)]
        return action

    # -------------------------------------------------------------------------
    # Result / Checklist / AE Actions
    # -------------------------------------------------------------------------
    def action_open_results(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_result_document").read()[0]
        action["domain"] = [("session_id", "=", self.id)]
        action["context"] = {"default_session_id": self.id, "default_encounter_id": self.encounter_id.id}
        return action

    def action_create_quick_result(self):
        """Buat hasil kosong terhubung ke sesi ini (helper cepat)."""
        self.ensure_one()
        res = self.env["clinic.result.document"].create({
            "encounter_id": self.encounter_id.id,
            "session_id": self.id,
            "procedure_id": self.procedure_id.id if self.procedure_id else False,
            "title": _("Result — %s") % (self.procedure_id.display_name if self.procedure_id else self.name),
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Result"),
            "res_model": "clinic.result.document",
            "res_id": res.id,
            "view_mode": "form",
        }

    def action_open_checklists(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_checklist").read()[0]
        action["domain"] = [("session_id", "=", self.id)]
        action["context"] = {
            "default_session_id": self.id,
            "default_encounter_id": self.encounter_id.id,
            "default_procedure_id": self.procedure_id.id if self.procedure_id else False,
        }
        return action

    # def action_create_checklist_from_template(self, template):
    #     """
    #     Helper: buat satu checklist instance untuk session dari template tertentu.
    #     """
    #     self.ensure_one()
    #     if not template or template._name != "clinic.checklist.template":
    #         raise UserError(_("A Checklist Template is required."))
    #     vals = template.prepare_instance_vals(
    #         encounter=self.encounter_id, session=self, procedure=self.procedure_id
    #     )
    #     cl = self.env["clinic.checklist"].create(vals)
    #     return {
    #         "type": "ir.actions.act_window",
    #         "name": _("Checklist"),
    #         "res_model": "clinic.checklist",
    #         "res_id": cl.id,
    #         "view_mode": "form",
    #     }

    def action_open_adverse_events(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_adverse_event").read()[0]
        action["domain"] = [("session_id", "=", self.id)]
        action["context"] = {
            "default_session_id": self.id,
            "default_encounter_id": self.encounter_id.id,
            "default_procedure_id": self.procedure_id.id if self.procedure_id else False,
            "default_diagnosis_id": self.diagnosis_id.id if self.diagnosis_id else False,
        }
        return action

    # -------------------------------------------------------------------------
    # Execution Log helper (dipanggil dari workflow)
    # -------------------------------------------------------------------------
    def _log_event(self, event_type, message=None, role="user", **kwargs):
        """
        Panggil helper log untuk session ini (single).
        event_type: start/pause/resume/done/cancel/note/create
        """
        self.ensure_one()
        Log = self.env["clinic.execution.log"].sudo()
        try:
            Log.log_for_session(self, event_type=event_type, message=message, role=role, **kwargs)
        except Exception:
            # Jangan gagalkan workflow hanya karena gagal log
            pass

    # Utilitas publik agar UI/otomasi dapat mencatat catatan bebas
    def log_note(self, message, role="user", **extra_vals):
        """
        Catat event 'note' ke log sesi.
        Use case: operator menambahkan catatan manual, sistem perangkat mengirim telemetry, dsb.
        """
        self.ensure_one()
        if not message:
            raise UserError(_("Message is required to create a note log."))
        self._log_event("note", message=message, role=role, **extra_vals)
        return True

    # -------------------------------------------------------------------------
    # Name & Smart Buttons
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            label = rec.name
            if rec.procedure_id:
                label = f"{rec.name} • {rec.procedure_id.display_name or rec.procedure_id.name}"
            res.append((rec.id, label))
        return res

    def action_open_encounter(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_encounter").read()[0]
        action["res_id"] = self.encounter_id.id
        action["domain"] = [("id", "=", self.encounter_id.id)]
        action["view_mode"] = "form"
        return action

    def action_open_plan_line(self):
        self.ensure_one()
        if not self.encounter_procedure_id:
            raise UserError(_("This session is not linked to a plan line."))
        action = self.env.ref("clinic_encounter.action_clinic_encounter_procedure").read()[0]
        action["res_id"] = self.encounter_procedure_id.id
        action["domain"] = [("id", "=", self.encounter_procedure_id.id)]
        action["view_mode"] = "form"
        return action



# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/procedure_catalog.py
#
# Fungsi:
# - Master katalog prosedur klinis (harga, durasi, pajak, jumlah sesi).
# - Mapping ke product.product untuk pricing & pajak (opsional).
# - Consumables (bahan/alat) default per prosedur (opsional).
# - Billing policy default (per_plan/per_session/no_bill) yang diturunkan ke rencana prosedur.
# - Integrasi “soft-coupled” dengan Encounter → Procedure Plan → Session.
#
# Catatan:
# - Tidak memaksa dependensi ke modul room/device/stock lanjutan; hanya menyediakan hook/field umum.
# - actions helper untuk melihat rencana/sesi terkait prosedur ini.
#
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# -----------------------------------------------------------------------------
# Tag & Kategori Prosedur (opsional untuk pelabelan & pelaporan)
# -----------------------------------------------------------------------------
class ClinicProcedureTag(models.Model):
    _name = "clinic.procedure.tag"
    _description = "Procedure Tag"
    _order = "name"

    name = fields.Char(required=True, translate=True, index=True)
    color = fields.Integer(string="Color Index")
    active = fields.Boolean(default=True)
    description = fields.Text()


class ClinicProcedureCategory(models.Model):
    _name = "clinic.procedure.category"
    _description = "Procedure Category"
    _order = "sequence, name"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True, index=True)
    code = fields.Char(index=True, help="Optional code for external mapping.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, index=True)
    parent_id = fields.Many2one("clinic.procedure.category", string="Parent", index=True)
    child_ids = fields.One2many("clinic.procedure.category", "parent_id", string="Children")
    description = fields.Text()


# -----------------------------------------------------------------------------
# Master Katalog Prosedur
# -----------------------------------------------------------------------------
class ClinicProcedureCatalog(models.Model):
    _name = "clinic.procedure.catalog"
    _description = "Procedure Catalog"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identitas & Perusahaan
    # -------------------------------------------------------------------------
    name = fields.Char(required=True, translate=True, tracking=True, index=True)
    code = fields.Char(
        string="Procedure Code",
        copy=False,
        index=True,
        help="Internal/External code. If empty, will be filled by sequence.",
    )
    display_name = fields.Char(string="Display", compute="_compute_display_name", store=True)
    sequence = fields.Integer(default=10, index=True)
    active = fields.Boolean(default=True, tracking=True)

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Kategori & Tag
    # -------------------------------------------------------------------------
    category_id = fields.Many2one("clinic.procedure.category", string="Category", ondelete="set null", index=True)
    tag_ids = fields.Many2many("clinic.procedure.tag", string="Tags")

    # -------------------------------------------------------------------------
    # Mapping ke Produk & Satuan
    # -------------------------------------------------------------------------
    product_id = fields.Many2one(
        "product.product",
        string="Product (Pricing)",
        help="Mapped product/service for pricing and taxation. Optional but recommended.",
        ondelete="set null",
        index=True,
        tracking=True,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        help="Default UoM for billing/quantity on procedure plan.",
    )

    # -------------------------------------------------------------------------
    # Pricing & Pajak
    # -------------------------------------------------------------------------
    list_price = fields.Monetary(
        string="List Price",
        help="Default unit price used on encounter procedure line. If product is set, initialized from product.",
        currency_field="currency_id",
        tracking=True,
    )
    standard_price = fields.Monetary(
        string="Cost",
        help="Optional internal cost reference (not used in billing).",
        currency_field="currency_id",
    )
    tax_ids = fields.Many2many(
        "account.tax",
        "clinic_proc_catalog_tax_rel",
        "catalog_id",
        "tax_id",
        string="Customer Taxes",
        domain=[("type_tax_use", "in", ["sale", "none"])],
        help="Default taxes applied for patient/customer billing.",
    )
    billing_policy = fields.Selection(
        [
            ("per_plan", "Bill per Plan Line"),
            ("per_session", "Bill per Session"),
            ("no_bill", "Do Not Bill"),
        ],
        string="Default Billing Policy",
        default="per_plan",
        help="Default policy propagated to encounter procedure lines.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Waktu & Sesi Default
    # -------------------------------------------------------------------------
    default_duration_min = fields.Float(
        string="Default Duration (min)",
        help="Estimated duration per session (minutes).",
    )
    default_sessions = fields.Integer(
        string="Default Sessions",
        default=1,
        help="How many sessions are typically planned for this procedure.",
    )

    # -------------------------------------------------------------------------
    # Kebijakan Klinis
    # -------------------------------------------------------------------------
    require_consent = fields.Boolean(
        string="Require Consent",
        help="If enabled, encounter stage may enforce consent before execution.",
        tracking=True,
    )
    require_checklist = fields.Boolean(
        string="Require Checklist",
        help="If enabled, a pre/post checklist is expected during session.",
    )
    instructions_pre = fields.Html(string="Pre-Procedure Instructions")
    instructions_post = fields.Html(string="Post-Procedure Instructions")
    risks = fields.Html(string="Risks / Adverse Events (Info)")

    # -------------------------------------------------------------------------
    # Consumables (Bahan/Alat) Default
    # -------------------------------------------------------------------------
    consumable_ids = fields.One2many(
        "clinic.procedure.consumable",
        "procedure_id",
        string="Default Consumables",
        help="Default materials/equipment consumed during the procedure (for inventory bridge).",
    )

    # -------------------------------------------------------------------------
    # Relasi ke Langkah (Step) — didefinisikan di models/procedure_step.py
    # -------------------------------------------------------------------------
    step_ids = fields.One2many(
        "clinic.procedure.step",
        "procedure_id",
        string="Steps",
        help="Structured steps of this procedure.",
    )

    # -------------------------------------------------------------------------
    # Analitik & Penggunaan
    # -------------------------------------------------------------------------
    plan_count = fields.Integer(string="Procedure Plans", compute="_compute_usage_counters", store=False)
    session_count = fields.Integer(string="Sessions", compute="_compute_usage_counters", store=False)

    color = fields.Integer(string="Color Index")
    note = fields.Text(string="Internal Note")

    # -------------------------------------------------------------------------
    # Komputasi
    # -------------------------------------------------------------------------
    @api.depends("code", "name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "[%s] %s" % (rec.code, rec.name) if rec.code else (rec.name or "")

    def _compute_usage_counters(self):
        Plan = self.env["clinic.encounter.procedure"]
        Session = self.env["clinic.procedure.session"]
        for rec in self:
            rec.plan_count = Plan.search_count([("procedure_id", "=", rec.id)])
            rec.session_count = Session.search_count([("procedure_id", "=", rec.id)]) if "procedure_id" in Session._fields else 0

    # -------------------------------------------------------------------------
    # Onchange
    # -------------------------------------------------------------------------
    @api.onchange("product_id")
    def _onchange_product_id(self):
        """Prefill UoM, List Price, Cost, Taxes from product."""
        prod = self.product_id
        if not prod:
            return
        vals = {}
        if prod.uom_id:
            vals["uom_id"] = prod.uom_id.id
        # Harga
        vals["list_price"] = prod.lst_price
        if "standard_price" in prod._fields and prod.standard_price is not False:
            vals["standard_price"] = prod.standard_price
        # Pajak customer
        if prod.taxes_id:
            vals["tax_ids"] = [(6, 0, prod.taxes_id.ids)]
        self.update(vals)

    # -------------------------------------------------------------------------
    # Constraint
    # -------------------------------------------------------------------------
    _constraint_uniq_code_company = models.Constraint(
        'unique(code, company_id)',
        'Procedure Code must be unique per company.',
    )
    _constraint_check_default_sessions = models.Constraint(
        'CHECK (default_sessions >= 0)',
        'Default Sessions must be positive or zero.',
    )
    _constraint_check_duration = models.Constraint(
        'CHECK (default_duration_min >= 0)',
        'Duration must be positive or zero.',
    )

    @api.constrains("uom_id", "product_id")
    def _check_uom_category(self):
        for rec in self:
            if rec.product_id and rec.uom_id and rec.product_id.uom_id.category_id != rec.uom_id.category_id:
                raise ValidationError(_("The selected Unit of Measure is not compatible with the product's UoM."))

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            # Isi code dari sequence bila kosong
            if not vals.get("code"):
                vals["code"] = seq.next_by_code("clinic.procedure.catalog") or False
            # Prefill list_price/tax dari product jika belum ada
            if vals.get("product_id"):
                prod = self.env["product.product"].browse(vals["product_id"])
                vals.setdefault("uom_id", prod.uom_id.id)
                vals.setdefault("list_price", prod.lst_price)
                if "standard_price" in prod._fields:
                    vals.setdefault("standard_price", prod.standard_price)
                if prod.taxes_id and not vals.get("tax_ids"):
                    vals["tax_ids"] = [(6, 0, prod.taxes_id.ids)]
        recs = super().create(vals_list)
        # Jadwalkan aktivitas ringan untuk melengkapi langkah/consumables (opsional)
        for rec in recs:
            try:
                rec.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Complete procedure steps/consumables"),
                    user_id=self.env.user.id,
                    date_deadline=fields.Date.today(),
                )
            except Exception:
                pass
        return recs

    def write(self, vals):
        # Bila product diganti dan uom belum diset di vals, sinkronkan uom & pajak default
        if "product_id" in vals:
            prod = self.env["product.product"].browse(vals["product_id"]) if vals.get("product_id") else False
            if prod:
                vals.setdefault("uom_id", prod.uom_id.id)
                vals.setdefault("list_price", prod.lst_price)
                if "standard_price" in prod._fields:
                    vals.setdefault("standard_price", prod.standard_price)
                if prod.taxes_id and "tax_ids" not in vals:
                    vals["tax_ids"] = [(6, 0, prod.taxes_id.ids)]
        return super().write(vals)

    # -------------------------------------------------------------------------
    # Helper untuk Encounter → Procedure Plan
    # -------------------------------------------------------------------------
    def prepare_plan_vals(self, encounter, quantity=1.0, diagnosis=None, price_unit=None, uom=None):
        """
        Siapkan vals untuk pembuatan record clinic.encounter.procedure dari katalog ini.
        - encounter: record clinic.encounter
        - quantity: default 1.0 (atau sesuai kebutuhan)
        - diagnosis: optional clinic.diagnosis
        - price_unit: override harga (jika None → pakai list_price)
        - uom: override uom (jika None → pakai uom_id / product.uom_id)
        """
        self.ensure_one()
        if not encounter:
            raise UserError(_("Encounter is required to prepare a procedure plan."))
        if quantity is None:
            quantity = 1.0

        # Tentukan UoM dan pajak default
        uom_id = uom.id if getattr(uom, "id", False) else (self.uom_id.id or (self.product_id.uom_id.id if self.product_id else False))
        taxes = self.tax_ids
        partner = encounter.partner_id
        # Map tax via fiscal position partner (jika ada)
        if partner and partner.property_account_position_id:
            taxes = partner.property_account_position_id.map_tax(taxes, product=self.product_id, partner=partner)

        vals = {
            "encounter_id": encounter.id,
            "diagnosis_id": diagnosis.id if diagnosis else False,
            "procedure_id": self.id,
            "product_id": self.product_id.id if self.product_id else False,
            "uom_id": uom_id,
            "quantity": quantity,
            "planned_sessions": (self.default_sessions or 1),
            "planned_duration": (self.default_duration_min or 0.0),
            "price_unit": price_unit if price_unit is not None else (self.list_price or 0.0),
            "discount": 0.0,
            "tax_ids": [(6, 0, taxes.ids)] if taxes else [],
            "billing_policy": self.billing_policy or "per_plan",
        }
        return vals

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------
    def action_open_related_plans(self):
        """Lihat semua rencana prosedur (clinic.encounter.procedure) yang memakai katalog ini."""
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_encounter_procedure").read()[0]
        action["domain"] = [("procedure_id", "=", self.id)]
        return action

    def action_open_related_sessions(self):
        """Lihat semua sesi tindakan (clinic.procedure.session) yang memakai katalog ini (jika field tersedia)."""
        self.ensure_one()
        Session = self.env["clinic.procedure.session"]
        if "procedure_id" not in Session._fields:
            raise UserError(_("Session model doesn't link to procedure catalog in this configuration."))
        action = self.env.ref("clinic_encounter.action_clinic_procedure_session").read()[0]
        action["domain"] = [("procedure_id", "=", self.id)]
        return action

    def action_quick_plan_for_encounter(self):
        """
        Buka action rencana prosedur dengan context default terisi dari katalog ini.
        Dipakai dari smart button 'Plan in Encounter'.
        """
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_encounter_procedure").read()[0]
        ctx = {
            "default_procedure_id": self.id,
            "default_product_id": self.product_id.id if self.product_id else False,
            "default_uom_id": self.uom_id.id if self.uom_id else (self.product_id.uom_id.id if self.product_id else False),
            "default_price_unit": self.list_price or 0.0,
            "default_planned_sessions": (self.default_sessions or 1),
            "default_planned_duration": (self.default_duration_min or 0.0),
            "default_billing_policy": self.billing_policy or "per_plan",
        }
        action["context"] = ctx
        return action

    # -------------------------------------------------------------------------
    # Name & Search
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            label = rec.display_name or rec.name or ""
            res.append((rec.id, label))
        return res

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        extra_domain = list(domain or [])
        name_domain = ["|", ("name", operator, name), ("code", operator, name)]
        recs = self.search(name_domain + extra_domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]


# -----------------------------------------------------------------------------
# Child: Default Consumables for a Procedure
# -----------------------------------------------------------------------------
class ClinicProcedureConsumable(models.Model):
    _name = "clinic.procedure.consumable"
    _description = "Procedure Consumable"
    _order = "sequence, id"
    _check_company_auto = True

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    procedure_id = fields.Many2one(
        "clinic.procedure.catalog",
        string="Procedure",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="procedure_id.company_id",
        store=True,
        readonly=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        ondelete="restrict",
        index=True,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        help="If empty, the product's UoM will be used.",
    )
    quantity = fields.Float(
        string="Quantity",
        default=1.0,
        digits="Product Unit of Measure",
        help="Default quantity to be consumed per session (or per plan, depending on implementation).",
    )
    auto_issue = fields.Boolean(
        string="Auto Issue",
        default=True,
        help="If enabled, stock can be auto-issued when the session starts/finishes (inventory bridge needed).",
    )
    required = fields.Boolean(
        string="Required",
        default=True,
        help="If enabled, this consumable is required (session may warn if not available).",
    )
    notes = fields.Char(string="Notes")

    # Visual
    color = fields.Integer(string="Color Index")

    # Onchange
    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id and not self.uom_id:
            self.uom_id = self.product_id.uom_id

    # Constraints
    _constraint_check_qty = models.Constraint(
        'CHECK (quantity >= 0)',
        'Quantity must be positive or zero.',
    )

    @api.constrains("uom_id", "product_id")
    def _check_uom_category(self):
        for rec in self:
            if rec.product_id and rec.uom_id and rec.product_id.uom_id.category_id != rec.uom_id.category_id:
                raise ValidationError(_("The selected Unit of Measure is not compatible with the product's UoM."))



# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/mixin_audit.py
#
# Fitur utama:
# - Abstract mixin (clinic.audit.mixin) untuk auto-audit create/write.
# - Log audit generik (clinic.audit.log) dengan reference model/id + diff JSON.
# - Deteksi transisi state/stage_id; helper untuk log custom & attachment events.
# - Konfigurasi enable/disable via System Parameter: clinic.audit.enabled (default: true).
# - Soft-coupled: aman walau modul lain tidak aktif; tidak memaksa mail.thread.
#
import json
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# =============================================================================
# MODEL: Audit Log (Generic)
# =============================================================================
class ClinicAuditLog(models.Model):
    _name = "clinic.audit.log"
    _description = "ClinicOne Audit Log"
    _order = "date_event desc, id desc"
    _check_company_auto = True

    # Identitas & perusahaan
    name = fields.Char(
        string="Log #",
        required=True,
        copy=False,
        default=lambda s: _("New"),
        index=True,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company, index=True
    )
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", store=True, readonly=True)

    # Referensi — simpan sebagai field terstruktur & reference
    ref_model = fields.Char(string="Model", required=True, index=True)
    ref_res_id = fields.Integer(string="Record ID", required=True, index=True)
    ref = fields.Reference(
        string="Record",
        selection="_referenceable_models",
        compute="_compute_ref",
        store=False,
    )
    ref_display_name = fields.Char(string="Record Display", compute="_compute_ref_display", store=False)

    # Event
    category = fields.Selection(
        [
            ("create", "Create"),
            ("update", "Update"),
            ("state", "State Transition"),
            ("stage", "Stage Transition"),
            ("attach", "Attachment"),
            ("comment", "Comment"),
            ("custom", "Custom"),
        ],
        string="Category",
        required=True,
        index=True,
        default="update",
    )
    date_event = fields.Datetime(string="When", required=True, default=lambda s: fields.Datetime.now(), index=True)
    user_id = fields.Many2one("res.users", string="Who", default=lambda s: s.env.user, index=True)
    role = fields.Selection(
        [
            ("system", "System"),
            ("user", "User"),
            ("performer", "Performer"),
            ("supervisor", "Supervisor"),
        ],
        string="Role",
        default="user",
        index=True,
    )

    # Ringkasan & alasan
    summary = fields.Char(string="Summary")
    reason_code = fields.Selection(
        [
            ("initial", "Initial"),
            ("edit", "Edit"),
            ("correction", "Correction"),
            ("approval", "Approval"),
            ("rejection", "Rejection"),
            ("auto", "Automated"),
            ("other", "Other"),
        ],
        string="Reason",
        default="edit",
        index=True,
    )
    note = fields.Text(string="Note")

    # Diff konten
    field_name = fields.Char(string="Field (Single)")
    old_value_text = fields.Char(string="Old (text)")
    new_value_text = fields.Char(string="New (text)")

    # Versi agregat (multi-field write)
    changes_json = fields.Text(
        string="Changes (JSON)",
        help='JSON object: {"field": {"old": "...", "new": "..."}, ...}',
    )

    # Metadata tambahan (opsional dari ctx)
    client_ip = fields.Char(string="Client IP")
    user_agent = fields.Char(string="User Agent")

    color = fields.Integer(string="Color Index")

    # -------------------------------------------------------------------------
    # Compute
    # -------------------------------------------------------------------------
    def _referenceable_models(self):
        """
        Daftar model yang bisa direferensikan. Ambil semua model yang dimulai "clinic."
        + beberapa model Odoo umum bila diperlukan.
        """
        IrModel = self.env["ir.model"].sudo()
        models = IrModel.search([("model", "like", "clinic.%")]).mapped(lambda m: (m.model, m.name))
        # Tambahkan opsi umum (opsional)
        models += [("account.move", "Journal Entry / Invoice"), ("stock.picking", "Stock Picking")]
        # Hilangkan duplikat mempertahankan urutan
        seen = set()
        sel = []
        for m in models:
            if m[0] not in seen:
                sel.append(m)
                seen.add(m[0])
        return sel

    def _compute_ref(self):
        for rec in self:
            rec.ref = (rec.ref_model, rec.ref_res_id)

    def _compute_ref_display(self):
        for rec in self:
            name = False
            try:
                if rec.ref_model and rec.ref_res_id:
                    rec_obj = self.env[rec.ref_model].browse(rec.ref_res_id)
                    if rec_obj.exists():
                        name = rec_obj.display_name
            except Exception:
                pass
            rec.ref_display_name = name

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if vals.get("name", _("New")) in (False, _("New")):
                vals["name"] = seq.next_by_code("clinic.audit.log") or _("New")
            # Sanitasi JSON agar selalu string
            if isinstance(vals.get("changes_json"), dict):
                vals["changes_json"] = json.dumps(vals["changes_json"], ensure_ascii=False)
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # Action helpers
    # -------------------------------------------------------------------------
    def action_open_record(self):
        self.ensure_one()
        if not (self.ref_model and self.ref_res_id):
            raise UserError(_("No referenced record."))
        # Cari action bawaan model
        try:
            # Konvensi action xml id
            xml_map = {
                "clinic.encounter": "clinic_encounter.action_clinic_encounter",
                "clinic.procedure.session": "clinic_encounter.action_clinic_procedure_session",
                "clinic.result.document": "clinic_encounter.action_clinic_result_document",
                "clinic.consent.document": "clinic_encounter.action_clinic_consent_document",
                "clinic.anesthesia.case": "clinic_encounter.action_clinic_anesthesia_case",
                "clinic.adverse.event": "clinic_encounter.action_clinic_adverse_event",
                "clinic.checklist": "clinic_encounter.action_clinic_checklist",
            }
            xmlid = xml_map.get(self.ref_model)
            if xmlid:
                action = self.env.ref(xmlid).read()[0]
                action["res_id"] = self.ref_res_id
                action["domain"] = [("id", "=", self.ref_res_id)]
                action["view_mode"] = "form"
                return action
        except Exception:
            pass
        # Fallback generic
        return {
            "type": "ir.actions.act_window",
            "name": _("Record"),
            "res_model": self.ref_model,
            "res_id": self.ref_res_id,
            "view_mode": "form",
        }


# =============================================================================
# MIXIN: Audit
# =============================================================================
class ClinicAuditMixin(models.AbstractModel):
    _name = "clinic.audit.mixin"
    _description = "Audit Mixin (ClinicOne)"
    _inherit = []
    _check_company_auto = True
    _abstract = True

    # Counter & quick-open
    audit_log_count = fields.Integer(string="Audit Logs", compute="_compute_audit_log_count", store=False)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------
    def action_view_audit_logs(self):
        """Open audit logs for current records."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Audit Logs"),
            "res_model": "clinic.audit.log",
            "view_mode": "list,form",
            "domain": [("ref_model", "=", self._name), ("ref_res_id", "=", self.id)],
            "context": {"search_default_group_by_category": 1},
        }

    def audit_log_custom(self, summary=None, note=None, category="custom", reason="other", changes=None, role="user"):
        """
        Tulis log audit kustom dari kode bisnis.
        - summary: ringkasan singkat
        - note: detail
        - category: custom/state/stage/attach/comment/...
        - reason: initial/edit/correction/approval/rejection/auto/other
        - changes: dict {'field': {'old': x, 'new': y}}
        """
        self.ensure_one()
        if not self._audit_is_enabled():
            return False
        vals = self._audit_base_vals(category=category, reason=reason, role=role)
        vals.update({
            "summary": summary or _("Custom event"),
            "note": note or False,
            "changes_json": json.dumps(changes or {}, ensure_ascii=False),
        })
        return self.env["clinic.audit.log"].sudo().create(vals)

    # -------------------------------------------------------------------------
    # Compute
    # -------------------------------------------------------------------------
    def _compute_audit_log_count(self):
        Audit = self.env["clinic.audit.log"]
        for rec in self:
            rec.audit_log_count = Audit.search_count([("ref_model", "=", rec._name), ("ref_res_id", "=", rec.id)])

    # -------------------------------------------------------------------------
    # Config & policy
    # -------------------------------------------------------------------------
    def _audit_is_enabled(self):
        """
        Audit bisa dimatikan:
        - context['no_audit'] / context['audit_skip'] → True = skip
        - System Parameter 'clinic.audit.enabled' = 'false'
        """
        ctx = self.env.context or {}
        if ctx.get("no_audit") or ctx.get("audit_skip"):
            return False
        Param = self.env["ir.config_parameter"].sudo()
        enabled = Param.get_param("clinic.audit.enabled", "true").strip().lower()
        return enabled not in ("0", "false", "no")

    def _audit_excluded_fields(self):
        """
        Field yang dikecualikan dari diff (chatter, komputasi umum, timestamp).
        Tambahkan field-field khusus model Anda melalui override (return superset).
        """
        base = {
            "id", "create_uid", "create_date", "write_uid", "write_date",
            "display_name", "message_ids", "message_follower_ids",
            "activity_ids", "activity_state", "activity_user_id",
            "activity_date_deadline", "activity_summary", "activity_exception_icon",
            "__last_update",
            # Komputasi amount/total yang diproduksi ulang dari baris
            "price_subtotal", "price_total", "price_tax",
            "actual_duration", "anesthesia_duration_min", "percent_complete",
            "score_total", "score_max", "score_percent", "required_ok",
            "abnormal_count", "critical_count",
            # Warna/tag yang tidak kritikal
            "color",
        }
        # Exclude fields starting with 'x_'? (custom) — jangan, biarkan tercatat.
        return base

    def _audit_included_fields(self):
        """
        Jika diset (return set non-empty), maka hanya field-field ini yang dicatat.
        Default: kosong → catat semua (kecuali excluded).
        """
        return set()

    def _audit_stage_fields(self):
        """
        Field yang diperlakukan sebagai 'stage transition': default: stage_id bila ada.
        """
        fields = []
        if "stage_id" in self._fields:
            fields.append("stage_id")
        return fields

    def _audit_state_fields(self):
        """
        Field yang diperlakukan sebagai 'state transition': default: 'state' bila ada.
        """
        return ["state"] if "state" in self._fields else []

    def _audit_user_role(self):
        """
        Heuristik sederhana menentukan role untuk log.
        Bisa dioverride (misal mengacu ke performer_user_id/doctor_id).
        """
        return "user"

    # -------------------------------------------------------------------------
    # Create/Write overrides
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self._audit_is_enabled():
            return records
        for rec, vals in zip(records, vals_list):
            try:
                # Log initial snapshot (tanpa diff field-by-field agar ringan)
                summary = _("Record created")
                stage_info = []
                for f in rec._audit_state_fields():
                    if f in vals or rec[f]:
                        stage_info.append("%s=%s" % (f, rec._audit_fmt_value(f, rec[f])))
                for f in rec._audit_stage_fields():
                    if f in vals or rec[f]:
                        stage_info.append("%s=%s" % (f, rec._audit_fmt_value(f, rec[f])))
                if stage_info:
                    summary += " (" + ", ".join(stage_info) + ")"

                rec._audit_create_log(category="create", reason="initial", summary=summary, changes=self._audit_pack_changes({}, rec.read()[0]))
            except Exception:
                # Jangan menggagalkan create karena audit
                pass
        return records

    def write(self, vals):
        # Simpan old values per-record untuk diff
        if not self:
            return super().write(vals)

        # Jika audit disabled → langsung write
        if not self._audit_is_enabled():
            return super().write(vals)

        excluded = self._audit_excluded_fields()
        included = self._audit_included_fields()
        interesting_keys = [k for k in vals.keys() if (k not in excluded) and (not included or k in included)]
        if not interesting_keys:
            return super().write(vals)

        # Baca nilai lama yang relevan
        old_snap = {rec.id: rec.read(interesting_keys)[0] for rec in self}
        # Jalankan write
        res = super().write(vals)

        # Untuk tiap record, hitung diff dan tulis audit
        for rec in self:
            try:
                new_snap = rec.read(interesting_keys)[0]
                changes = {}
                category = "update"
                summary_parts = []

                # Deteksi state/stage
                for st_field in rec._audit_state_fields():
                    if st_field in old_snap[rec.id] and st_field in new_snap:
                        if old_snap[rec.id].get(st_field) != new_snap.get(st_field):
                            category = "state"
                            old_txt = rec._audit_fmt_value(st_field, old_snap[rec.id].get(st_field))
                            new_txt = rec._audit_fmt_value(st_field, new_snap.get(st_field))
                            summary_parts.append(_("%s: %s → %s") % (st_field, old_txt, new_txt))
                            changes[st_field] = {"old": old_txt, "new": new_txt}

                for sg_field in rec._audit_stage_fields():
                    if sg_field in old_snap[rec.id] and sg_field in new_snap:
                        if old_snap[rec.id].get(sg_field) != new_snap.get(sg_field):
                            category = "stage" if category == "update" else category
                            old_txt = rec._audit_fmt_value(sg_field, old_snap[rec.id].get(sg_field))
                            new_txt = rec._audit_fmt_value(sg_field, new_snap.get(sg_field))
                            summary_parts.append(_("%s: %s → %s") % (sg_field, old_txt, new_txt))
                            changes[sg_field] = {"old": old_txt, "new": new_txt}

                # Field biasa
                for f in interesting_keys:
                    if f in changes:
                        continue
                    if old_snap[rec.id].get(f) != new_snap.get(f):
                        old_txt = rec._audit_fmt_value(f, old_snap[rec.id].get(f))
                        new_txt = rec._audit_fmt_value(f, new_snap.get(f))
                        changes[f] = {"old": old_txt, "new": new_txt}

                if not changes:
                    continue

                summary = " | ".join(summary_parts) if summary_parts else _("Fields updated")
                rec._audit_create_log(category=category, summary=summary, changes=changes)
            except Exception:
                # Jangan menggagalkan bisnis karena audit
                pass

        return res

    # -------------------------------------------------------------------------
    # Helpers (internal)
    # -------------------------------------------------------------------------
    def _audit_base_vals(self, category="update", reason="edit", role=None):
        self.ensure_one()
        ctx = self.env.context or {}
        vals = {
            "company_id": self.env.company.id,
            "ref_model": self._name,
            "ref_res_id": self.id,
            "category": category,
            "reason_code": reason,
            "date_event": fields.Datetime.now(),
            "user_id": self.env.user.id,
            "role": role or self._audit_user_role(),
            "client_ip": ctx.get("client_ip") or ctx.get("audit_ip") or False,
            "user_agent": ctx.get("user_agent") or ctx.get("http_user_agent") or False,
        }
        return vals

    def _audit_create_log(self, category="update", summary=None, changes=None, reason="edit", role=None, note=None):
        self.ensure_one()
        Audit = self.env["clinic.audit.log"].sudo()
        vals = self._audit_base_vals(category=category, reason=reason, role=role)
        vals.update({
            "summary": summary or False,
            "note": note or False,
            "changes_json": json.dumps(changes or {}, ensure_ascii=False),
        })
        return Audit.create(vals)

    def _audit_pack_changes(self, old_dict, new_dict):
        """Bungkus perbandingan dict lama→baru menjadi dict JSON sederhana."""
        excluded = self._audit_excluded_fields()
        included = self._audit_included_fields()
        changes = {}
        keys = set(new_dict.keys()) | set(old_dict.keys())
        for f in keys:
            if f in excluded:
                continue
            if included and f not in included:
                continue
            if old_dict.get(f) != new_dict.get(f):
                old_txt = self._audit_fmt_value(f, old_dict.get(f))
                new_txt = self._audit_fmt_value(f, new_dict.get(f))
                changes[f] = {"old": old_txt, "new": new_txt}
        return changes

    def _audit_fmt_value(self, field_name, value):
        """Ubah value mentah menjadi string ringkas untuk audit."""
        field = self._fields.get(field_name)
        if not field:
            return self._safe_str(value)

        # Selection → label
        if field.type == "selection":
            sel = dict(field.selection(self) if callable(field.selection) else field.selection or [])
            return self._safe_str(sel.get(value, value))

        # Many2one → display_name
        if field.type == "many2one":
            if isinstance(value, tuple):
                # read() of many2one returns (id, display_name)
                return self._safe_str(value[1])
            if isinstance(value, int) and value:
                try:
                    return self._safe_str(self.env[field.comodel_name].browse(value).display_name)
                except Exception:
                    return self._safe_str(value)
            return ""

        # Date/Datetime → ISO
        if field.type in ("date", "datetime"):
            return self._safe_str(value)

        # Boolean/Float/Char/Html/Text
        if field.type in ("boolean", "float", "char", "html", "text", "integer", "monetary"):
            return self._safe_str(value)

        # Many2many/One2many → tampilkan ringkas jumlah
        if field.type in ("many2many", "one2many"):
            # read() biasanya kembalikan list of ids
            if isinstance(value, list):
                return _("%s items") % len(value)
            return _("[list]")

        # JSON/serialized
        return self._safe_str(value)

    @staticmethod
    def _safe_str(v):
        if v in (None, False):
            return ""
        try:
            return str(v)
        except Exception:
            try:
                return json.dumps(v, ensure_ascii=False)
            except Exception:
                return "<unserializable>"

    # -------------------------------------------------------------------------
    # Convenience hooks yang bisa dipanggil model
    # -------------------------------------------------------------------------
    def audit_log_state_transition(self, old_state, new_state, reason="edit", note=None):
        """Catat transisi state eksplisit (bisa dipanggil dalam action_*)"""
        self.ensure_one()
        if not self._audit_is_enabled():
            return False
        summary = _("State: %s → %s") % (old_state, new_state)
        return self._audit_create_log(category="state", summary=summary, reason=reason, note=note,
                                      changes={"state": {"old": old_state, "new": new_state}})

    def audit_log_stage_transition(self, field_name="stage_id", old_stage=None, new_stage=None, reason="edit", note=None):
        self.ensure_one()
        if not self._audit_is_enabled():
            return False
        old_txt = self._audit_fmt_value(field_name, old_stage)
        new_txt = self._audit_fmt_value(field_name, new_stage)
        summary = _("%s: %s → %s") % (field_name, old_txt, new_txt)
        return self._audit_create_log(category="stage", summary=summary, reason=reason, note=note,
                                      changes={field_name: {"old": old_txt, "new": new_txt}})

    def audit_log_attachment(self, attachments, added=True, note=None):
        """Catat penambahan/penghapusan lampiran."""
        self.ensure_one()
        if not self._audit_is_enabled():
            return False
        names = []
        try:
            if hasattr(attachments, "mapped"):
                names = attachments.mapped("name")
            elif isinstance(attachments, list):
                names = [getattr(a, "name", str(a)) for a in attachments]
        except Exception:
            pass
        summary = _("Attachments %s: %s") % ("added" if added else "removed", ", ".join(names[:5]))
        return self._audit_create_log(category="attach", summary=summary, note=note,
                                      changes={"attachments": {"old": "" if added else ", ".join(names),
                                                               "new": ", ".join(names) if added else ""}})

    def audit_log_comment(self, text):
        """Catat komentar singkat ke audit (bukan chatter)."""
        self.ensure_one()
        if not self._audit_is_enabled():
            return False
        return self._audit_create_log(category="comment", summary=_("Comment"), note=text, changes={})


# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/execution_log.py
#
# Tujuan:
# - Merekam event eksekusi sesi prosedur (start/pause/resume/done/cancel/note).
# - Memberi snapshot status saat event, delta durasi sejak event sebelumnya, dan konteks aktor/ruangan.
# - Menyediakan helper untuk mencatat event kustom dan lampiran.
# - Override ringan model clinic.procedure.session: create/start/pause/resume/done/cancel ⇒ auto-log.
#
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# =============================================================================
# MODEL: Execution Log
# =============================================================================
class ClinicExecutionLog(models.Model):
    _name = "clinic.execution.log"
    _description = "Procedure Session Execution Log"
    _order = "date_event asc, id asc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identitas & Perusahaan
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Log #",
        required=True,
        copy=False,
        index=True,
        default=lambda self: _("New"),
        help="Sequence number of this log entry.",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Relasi Utama
    # -------------------------------------------------------------------------
    session_id = fields.Many2one(
        "clinic.procedure.session",
        string="Session",
        required=True,
        ondelete="cascade",
        index=True,
    )
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Encounter",
        related="session_id.encounter_id",
        store=True,
        readonly=True,
        index=True,
    )
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        related="encounter_id.patient_id",
        store=True,
        readonly=True,
        index=True,
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor (Encounter)",
        related="encounter_id.doctor_id",
        store=True,
        readonly=True,
        index=True,
    )
    procedure_id = fields.Many2one(
        "clinic.procedure.catalog",
        string="Procedure",
        related="session_id.procedure_id",
        store=True,
        readonly=True,
        index=True,
    )
    room_id = fields.Many2one(
        "clinic.room",
        string="Room",
        related="session_id.room_id",
        store=True,
        readonly=True,
        index=True,
    )

    # -------------------------------------------------------------------------
    # Event & Snapshot
    # -------------------------------------------------------------------------
    event_type = fields.Selection(
        [
            ("create", "Created"),
            ("start", "Start"),
            ("pause", "Pause"),
            ("resume", "Resume"),
            ("done", "Done"),
            ("cancel", "Cancel"),
            ("note", "Note"),
        ],
        string="Event",
        required=True,
        index=True,
    )
    date_event = fields.Datetime(
        string="Event Time",
        required=True,
        default=lambda self: fields.Datetime.now(),
        index=True,
        help="When this event occurred.",
    )
    state_after = fields.Selection(
        selection=lambda self: self.env["clinic.procedure.session"]._fields["state"].selection,
        string="State After",
        help="Session state immediately after this event.",
    )
    performer_user_id = fields.Many2one(
        "res.users",
        string="Performed By",
        default=lambda self: self.env.user,
        help="User who triggered this event.",
        index=True,
    )
    performer_role = fields.Selection(
        [
            ("system", "System"),
            ("user", "User"),
            ("performer", "Performer"),
            ("supervisor", "Supervisor"),
        ],
        string="Performer Role",
        default="user",
        help="Optional performer role for analytics.",
        index=True,
    )

    # -------------------------------------------------------------------------
    # Konten & Lampiran
    # -------------------------------------------------------------------------
    message = fields.Text(string="Message / Note")
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "clinic_exec_log_attachment_rel",
        "log_id",
        "attachment_id",
        string="Attachments",
    )
    # Payload bebas untuk device/alat: simpan JSON (sebagai teks) bila diperlukan
    payload = fields.Text(
        string="Payload (JSON)",
        help="Optional JSON payload from devices/bridges.",
    )

    # -------------------------------------------------------------------------
    # Durasi & Analitik
    # -------------------------------------------------------------------------
    is_timer_event = fields.Boolean(
        string="Timer Event",
        compute="_compute_flags",
        store=True,
        help="True for start/pause/resume/done events.",
    )
    delta_minutes_from_prev = fields.Float(
        string="Δ minutes from previous",
        compute="_compute_deltas",
        store=True,
        help="Time elapsed since previous log for this session (minutes).",
    )
    cumulative_runtime_minutes = fields.Float(
        string="Cumulative Runtime (min)",
        compute="_compute_deltas",
        store=True,
        help="Accrued running time within this session up to this event (minutes).",
    )

    color = fields.Integer(string="Color Index")

    # -------------------------------------------------------------------------
    # Compute
    # -------------------------------------------------------------------------
    @api.depends("event_type")
    def _compute_flags(self):
        timer_events = {"start", "pause", "resume", "done"}
        for rec in self:
            rec.is_timer_event = rec.event_type in timer_events

    @api.depends("date_event", "event_type", "session_id")
    def _compute_deltas(self):
        """
        Hitung:
          - delta_minutes_from_prev: selisih waktu dari log sebelumnya pada session yang sama
          - cumulative_runtime_minutes: akumulasi menit hanya saat status 'in_progress' (dari pasangan start/resume → pause/done)
        """
        for rec in self:
            rec.delta_minutes_from_prev = 0.0
            rec.cumulative_runtime_minutes = 0.0
            if not rec.session_id or not rec.date_event:
                continue

            # Temukan log sebelumnya di session yang sama
            prev_log = self.search(
                [("session_id", "=", rec.session_id.id), ("date_event", "<", rec.date_event)],
                order="date_event desc, id desc",
                limit=1,
            )
            # Delta dari prev
            if prev_log:
                delta = rec.date_event - prev_log.date_event
                rec.delta_minutes_from_prev = max(delta.total_seconds() / 60.0, 0.0)

            # Hitung akumulasi runtime: cari semua log <= current, akumulasi interval in_progress
            logs = self.search(
                [("session_id", "=", rec.session_id.id), ("date_event", "<=", rec.date_event)],
                order="date_event asc, id asc",
            )
            runtime = 0.0
            running_since = None
            # Kita asumsikan 'in_progress' dimulai pada event 'start' atau 'resume', berhenti pada 'pause' atau 'done'
            for lg in logs:
                if lg.event_type in ("start", "resume"):
                    running_since = lg.date_event
                elif lg.event_type in ("pause", "done"):
                    if running_since:
                        interval = lg.date_event - running_since
                        runtime += max(interval.total_seconds() / 60.0, 0.0)
                        running_since = None
            rec.cumulative_runtime_minutes = runtime

    # -------------------------------------------------------------------------
    # Constraint & Validasi
    # -------------------------------------------------------------------------
    _constraint_uniq_log_name_company = models.Constraint(
        'unique(name, company_id)',
        'Log number must be unique per company.',
    )

    @api.constrains("company_id", "encounter_id")
    def _check_company_consistency(self):
        for rec in self:
            if rec.encounter_id and rec.company_id and rec.company_id != rec.encounter_id.company_id:
                raise ValidationError(_("Log company must match Encounter company."))

    @api.constrains("date_event", "session_id")
    def _check_date_sequence(self):
        # Longgar: izinkan back-date, tapi cegah event yang terlalu jauh di masa depan?
        # Di sini hanya pastikan date_event ada (wajib) dan tidak null, validasi lain melalui UI/workflow.
        for rec in self:
            if not rec.date_event:
                raise ValidationError(_("Event time is required."))

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if vals.get("name", _("New")) in (False, _("New")):
                vals["name"] = seq.next_by_code("clinic.execution.log") or _("New")
        recs = super().create(vals_list)
        return recs

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    @api.model
    def log_for_session(self, session, event_type, message=None, role="user", **extra_vals):
        """
        Helper sederhana untuk mencatat satu event pada sebuah session.
        - session: record clinic.procedure.session
        - event_type: start/pause/resume/done/cancel/note/create
        - message: catatan singkat
        - role: system/user/performer/supervisor
        - extra_vals: payload, attachment_ids [(6,0,ids)], date_event override, dll.
        """
        if not session or session._name != "clinic.procedure.session":
            raise UserError(_("A valid Procedure Session is required to log events."))

        vals = {
            "session_id": session.id,
            "company_id": session.company_id.id,
            "event_type": event_type,
            "state_after": session.state,  # snapshot seketika
            "performer_user_id": self.env.user.id,
            "performer_role": role or "user",
            "date_event": extra_vals.pop("date_event", fields.Datetime.now()),
            "message": message or False,
        }
        # merge ekstra (payload, attachments, dsb.)
        vals.update(extra_vals or {})
        return self.create([vals])[0]

    def action_open_session(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_procedure_session").read()[0]
        action["res_id"] = self.session_id.id
        action["domain"] = [("id", "=", self.session_id.id)]
        action["view_mode"] = "form"
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
    def name_get(self):
        res = []
        for rec in self:
            label = f"{rec.name} • {dict(self._fields['event_type'].selection).get(rec.event_type)}"
            if rec.session_id:
                label = f"{label} • {rec.session_id.name}"
            res.append((rec.id, label))
        return res

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        extra_domain = list(domain or [])
        name_domain = ["|", "|",
                  ("name", operator, name),
                  ("session_id.name", operator, name),
                  ("message", operator, name)]
        recs = self.search(name_domain + extra_domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]


# # =============================================================================
# # EXTENSION: Auto-logging pada clinic.procedure.session
# # =============================================================================
# class ClinicProcedureSession_ExecutionLog(models.Model):
#     _inherit = "clinic.procedure.session"

#     def _log_event(self, event_type, message=None, role="user", **kwargs):
#         """Panggil helper log untuk session ini (single)."""
#         self.ensure_one()
#         Log = self.env["clinic.execution.log"].sudo()
#         try:
#             Log.log_for_session(self, event_type=event_type, message=message, role=role, **kwargs)
#         except Exception:
#             # Jangan gagalkan workflow hanya karena gagal log
#             pass

#     @api.model_create_multi
#     def create(self, vals_list):
#         recs = super().create(vals_list)
#         # Auto-log "create"
#         for rec in recs:
#             rec._log_event("create", message=_("Session created"), role="system")
#         return recs

#     # Override workflow untuk injeksi log
#     def action_start(self):
#         res = super().action_start()
#         for rec in self:
#             rec._log_event("start", message=_("Session started"), role="performer")
#         return res

#     def action_pause(self, reason=None):
#         res = super().action_pause(reason=reason)
#         for rec in self:
#             msg = _("Session paused") + (": %s" % reason if reason else "")
#             rec._log_event("pause", message=msg, role="performer")
#         return res

#     def action_resume(self):
#         res = super().action_resume()
#         for rec in self:
#             rec._log_event("resume", message=_("Session resumed"), role="performer")
#         return res

#     def action_done(self):
#         res = super().action_done()
#         for rec in self:
#             rec._log_event("done", message=_("Session completed"), role="performer")
#         return res

#     def action_cancel(self, reason=None):
#         res = super().action_cancel(reason=reason)
#         for rec in self:
#             msg = _("Session cancelled") + (": %s" % reason if reason else "")
#             rec._log_event("cancel", message=msg, role="performer")
#         return res

#     # Utilitas publik agar UI/otomasi dapat mencatat catatan bebas
#     def log_note(self, message, role="user", **extra_vals):
#         """
#         Catat event 'note' ke log sesi.
#         Use case: operator menambahkan catatan manual, sistem perangkat mengirim telemetry, dsb.
#         """
#         self.ensure_one()
#         if not message:
#             raise UserError(_("Message is required to create a note log."))
#         self._log_event("note", message=message, role=role, **extra_vals)
#         return True



# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/encounter.py
#
# Satu header Encounter yang menyatukan:
# - SOAP/Assessment, Rencana Prosedur (clinic.encounter.procedure), Sesi Tindakan (clinic.procedure.session)
# - Consent, Checklist, Result Document, Adverse Event (digabung dari class _inherit ke clinic.encounter)
# - Roll-up Billing & Smart Buttons portal/billing
#
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicEncounter(models.Model):
    _name = "clinic.encounter"
    _description = "Clinic Encounter"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Company
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Encounter #",
        required=True,
        copy=False,
        index=True,
        default=lambda self: _("New"),
        tracking=True,
    )
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Patient & Clinical Context
    # -------------------------------------------------------------------------
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
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
        ondelete="restrict",
        index=True,
        tracking=True,
        help="Primary provider responsible for this encounter.",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        default=lambda self: self.env.user,
        tracking=True,
        help="Staff responsible (owner) for workflow & coordination.",
    )
    appointment_id = fields.Many2one(
        "booking.booking",
        string="Appointment",
        ondelete="set null",
        index=True,
        help="If this encounter originates from an appointment/booking.",
    )

    # Tautan data klinis lain (diisi modul lain atau wizard)
    vital_ids = fields.One2many("clinic.patient.vital", "encounter_id", string="Vitals")
    diagnosis_note = fields.Text(string="Initial Assessment", help="Short free-text note (complementary to SOAP).")

    # -------------------------------------------------------------------------
    # Scheduling & Progress (Stage-driven)
    # -------------------------------------------------------------------------
    stage_id = fields.Many2one(
        "clinic.encounter.stage",
        string="Stage",
        ondelete="restrict",
        tracking=True,
        index=True,
        help="Functional stage of the encounter (Draft/In Progress/Done/Cancelled).",
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        compute="_compute_state",
        store=True,
        tracking=True,
        help="Derived from the selected stage.",
    )

    date_planned_start = fields.Datetime(string="Planned Start", help="Planned start (from booking/triage).")
    date_planned_end = fields.Datetime(string="Planned End", help="Planned end of the encounter.")
    date_start = fields.Datetime(string="Check-in / Start", tracking=True, help="Set when starting.")
    date_end = fields.Datetime(string="Check-out / End", tracking=True, help="Set when finishing.")
    planned_duration = fields.Float(string="Planned Duration (min)", help="Estimated duration in minutes.")
    actual_duration = fields.Float(
        string="Actual Duration (min)",
        compute="_compute_actual_duration",
        store=True,
        help="Computed from Start → End in minutes.",
    )

    # Visual (Kanban)
    color = fields.Integer(string="Color Index")
    priority = fields.Selection(
        [("0", "Normal"), ("1", "High"), ("2", "Urgent")],
        string="Priority",
        default="0",
        index=True,
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Planning (Procedures) & Execution (Sessions)
    # -------------------------------------------------------------------------
    procedure_line_ids = fields.One2many(
        "clinic.encounter.procedure",
        "encounter_id",
        string="Planned Procedures",
        help="Planned clinical procedures for this encounter.",
    )
    session_ids = fields.One2many(
        "clinic.procedure.session",
        "encounter_id",
        string="Procedure Sessions",
        help="Execution sessions spawned from planned procedures.",
    )
    procedure_count = fields.Integer(compute="_compute_counts", string="Procedure Plans", store=True)
    session_count = fields.Integer(compute="_compute_counts", string="Sessions", store=True)

    # -------------------------------------------------------------------------
    # MERGED: Consent / Checklist / Result / Adverse Event (dari *_inherit)
    # -------------------------------------------------------------------------
    # Consent
    consent_ok = fields.Boolean(
        string="Consent Obtained",
        tracking=True,
        help="Checked when patient consent has been captured for the planned procedures.",
    )
    consent_ids = fields.One2many("clinic.consent.document", "encounter_id", string="Consents")
    consent_count = fields.Integer(compute="_compute_consent_count", string="Consents", store=False)

    # Checklist
    # checklist_ids = fields.One2many("clinic.checklist", "encounter_id", string="Checklists")
    checklist_count = fields.Integer(compute="_compute_checklist_count", string="Checklists", store=False)

    # Results
    result_ids = fields.One2many("clinic.result.document", "encounter_id", string="Results")
    result_count = fields.Integer(compute="_compute_result_count", string="Results", store=False)

    # Adverse Events
    # ae_ids = fields.One2many("clinic.adverse.event", "encounter_id", string="Adverse Events")
    ae_count = fields.Integer(string="Adverse Events", compute="_compute_ae_count", store=False)

    # -------------------------------------------------------------------------
    # Financials (roll-up dari procedure/session)
    # -------------------------------------------------------------------------
    amount_untaxed = fields.Monetary(
        string="Untaxed Amount", compute="_compute_amounts", store=True, currency_field="currency_id"
    )
    amount_tax = fields.Monetary(
        string="Taxes", compute="_compute_amounts", store=True, currency_field="currency_id"
    )
    amount_total = fields.Monetary(
        string="Total", compute="_compute_amounts", store=True, currency_field="currency_id"
    )
    amount_invoiced = fields.Monetary(
        string="Invoiced", compute="_compute_billing_progress", store=True, currency_field="currency_id"
    )
    amount_to_invoice = fields.Monetary(
        string="To Invoice", compute="_compute_billing_progress", store=True, currency_field="currency_id"
    )
    invoice_count = fields.Integer(compute="_compute_billing_progress", string="Invoices", store=True)

    # -------------------------------------------------------------------------
    # Notes
    # -------------------------------------------------------------------------
    internal_note = fields.Text(string="Internal Notes")

    # -------------------------------------------------------------------------
    # Computations
    # -------------------------------------------------------------------------
    @api.depends("stage_id.state")
    def _compute_state(self):
        for rec in self:
            rec.state = rec.stage_id.state if rec.stage_id and rec.stage_id.state else "draft"

    @api.depends("date_start", "date_end")
    def _compute_actual_duration(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end >= rec.date_start:
                delta = rec.date_end - rec.date_start
                rec.actual_duration = (delta.total_seconds() / 60.0)
            else:
                rec.actual_duration = 0.0

    @api.depends("procedure_line_ids.price_subtotal", "procedure_line_ids.price_tax", "procedure_line_ids.currency_id")
    def _compute_amounts(self):
        for rec in self:
            untaxed = 0.0
            tax = 0.0
            for line in rec.procedure_line_ids:
                untaxed += (line.price_subtotal or 0.0)
                tax += (getattr(line, "price_tax", 0.0) or 0.0)
            rec.amount_untaxed = untaxed
            rec.amount_tax = tax
            rec.amount_total = untaxed + tax

    @api.depends("procedure_line_ids.invoice_line_ids.move_id.state")
    def _compute_billing_progress(self):
        for rec in self:
            invoices = self.env["account.move"]
            amount_invoiced = 0.0
            for line in rec.procedure_line_ids:
                for invl in getattr(line, "invoice_line_ids", []):
                    if invl.move_id and invl.move_id.state not in ("draft", "cancel"):
                        invoices |= invl.move_id
                        if invl.currency_id == rec.currency_id:
                            amount_invoiced += invl.price_subtotal
                        else:
                            amount_invoiced += invl.currency_id._convert(
                                invl.price_subtotal, rec.currency_id, rec.company_id, invl.move_id.invoice_date or fields.Date.today()
                            )
            rec.invoice_count = len(invoices)
            rec.amount_invoiced = amount_invoiced
            rec.amount_to_invoice = max(rec.amount_total - amount_invoiced, 0.0)

    @api.depends("procedure_line_ids", "session_ids")
    def _compute_counts(self):
        for rec in self:
            rec.procedure_count = len(rec.procedure_line_ids)
            rec.session_count = len(rec.session_ids)

    # Merged counters
    def _compute_consent_count(self):
        for rec in self:
            rec.consent_count = len(rec.consent_ids)

    def _compute_checklist_count(self):
        for rec in self:
            rec.checklist_count = len(rec.checklist_ids)

    def _compute_result_count(self):
        for rec in self:
            rec.result_count = len(rec.result_ids)

    def _compute_ae_count(self):
        for rec in self:
            rec.ae_count = len(rec.ae_ids)

    # -------------------------------------------------------------------------
    # Onchange & Defaults
    # -------------------------------------------------------------------------
    @api.onchange("patient_id")
    def _onchange_patient(self):
        if self.patient_id and self.appointment_id and getattr(self.appointment_id, "doctor_id", False):
            self.doctor_id = self.appointment_id.doctor_id

    @api.onchange("appointment_id")
    def _onchange_appointment(self):
        appt = self.appointment_id
        if appt:
            if getattr(appt, "scheduled_start", False) and not self.date_planned_start:
                self.date_planned_start = appt.scheduled_start
            if getattr(appt, "scheduled_end", False) and not self.date_planned_end:
                self.date_planned_end = appt.scheduled_end
            if getattr(appt, "doctor_id", False) and not self.doctor_id:
                self.doctor_id = appt.doctor_id
            if getattr(appt, "priority", False) and not self.priority:
                self.priority = appt.priority

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    _constraint_uniq_encounter_name_company = models.Constraint(
        'unique(name, company_id)',
        'Encounter number must be unique per company.',
    )

    @api.constrains("date_planned_start", "date_planned_end")
    def _check_planned_dates(self):
        for rec in self:
            if rec.date_planned_start and rec.date_planned_end and rec.date_planned_end < rec.date_planned_start:
                raise ValidationError(_("Planned End cannot be earlier than Planned Start."))

    @api.constrains("date_start", "date_end")
    def _check_actual_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_("Check-out / End cannot be earlier than Check-in / Start."))

    @api.constrains("patient_id", "state")
    def _check_open_encounter_uniqueness(self):
        for rec in self:
            if rec.state in ("draft", "in_progress"):
                domain = [
                    ("id", "!=", rec.id),
                    ("patient_id", "=", rec.patient_id.id),
                    ("state", "in", ["draft", "in_progress"]),
                    ("company_id", "=", rec.company_id.id),
                ]
                if self.search_count(domain):
                    raise ValidationError(_("This patient already has an open encounter (Draft/In Progress) in this company."))

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if vals.get("name", _("New")) in (False, _("New")):
                vals["name"] = seq.next_by_code("clinic.encounter") or _("New")
        recs = super().create(vals_list)
        for rec in recs:
            try:
                rec.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Review Encounter"),
                    user_id=rec.user_id.id or self.env.user.id,
                    date_deadline=fields.Date.today(),
                )
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if "stage_id" in vals and rec.state == "done" and not rec.date_end:
                rec.date_end = fields.Datetime.now()
        return res

    # -------------------------------------------------------------------------
    # Button Actions / Workflow
    # -------------------------------------------------------------------------
    def action_set_to_draft(self):
        self._ensure_can_edit()
        stage = self._get_stage_by_state("draft")
        for rec in self:
            rec.write({"stage_id": stage.id if stage else rec.stage_id.id})
        return True

    def action_start(self):
        self._ensure_can_edit()
        stage = self._get_stage_by_state("in_progress")
        now = fields.Datetime.now()
        for rec in self:
            updates = {"stage_id": stage.id if stage else rec.stage_id.id}
            if not rec.date_start:
                updates["date_start"] = now
            rec.write(updates)
        return True

    def action_done(self):
        stage = self._get_stage_by_state("done")
        for rec in self:
            if not rec.procedure_line_ids and not rec.diagnosis_note:
                raise UserError(_("Cannot complete: please add at least a procedure plan or a clinical assessment."))
            updates = {"stage_id": stage.id if stage else rec.stage_id.id}
            if not rec.date_end:
                updates["date_end"] = fields.Datetime.now()
            rec.write(updates)
        return True

    def action_cancel(self, reason=None):
        stage = self._get_stage_by_state("cancelled")
        for rec in self:
            rec.write({"stage_id": stage.id if stage else rec.stage_id.id})
            if reason:
                note = (rec.internal_note or "") + "\n" + _("Cancelled: %s") % reason
                rec.internal_note = note.strip()
        return True

    # -------------------------------------------------------------------------
    # Smart Buttons & External Actions
    # -------------------------------------------------------------------------
    def action_open_procedures(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_encounter_procedure").read()[0]
        action["domain"] = [("encounter_id", "=", self.id)]
        action["context"] = {"default_encounter_id": self.id, "search_default_encounter_id": self.id}
        return action

    def action_open_sessions(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_procedure_session").read()[0]
        action["domain"] = [("encounter_id", "=", self.id)]
        action["context"] = {"default_encounter_id": self.id, "search_default_encounter_id": self.id}
        return action

    def action_open_billing(self):
        self.ensure_one()
        AccountMove = self.env["account.move"]
        invoices = AccountMove.search([
            ("invoice_origin", "=", self.name),
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("company_id", "=", self.company_id.id),
        ])
        if invoices:
            action = self.env.ref("account.action_move_out_invoice_type").read()[0]
            action["domain"] = [("id", "in", invoices.ids)]
            return action
        action = self.env.ref("clinic_encounter.action_generate_bill_wizard").read()[0]
        action["context"] = {"default_encounter_id": self.id}
        return action

    # MERGED: open* actions
    def action_open_consents(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_consent_document").read()[0]
        action["domain"] = [("encounter_id", "=", self.id)]
        action["context"] = {"default_encounter_id": self.id}
        return action

    def action_open_checklists(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_checklist").read()[0]
        action["domain"] = [("encounter_id", "=", self.id)]
        action["context"] = {"default_encounter_id": self.id}
        return action

    def action_open_results(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_result_document").read()[0]
        action["domain"] = [("encounter_id", "=", self.id)]
        action["context"] = {"default_encounter_id": self.id}
        return action

    def action_open_adverse_events(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_adverse_event").read()[0]
        action["domain"] = [("encounter_id", "=", self.id)]
        action["context"] = {"default_encounter_id": self.id}
        return action

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _ensure_can_edit(self):
        for rec in self:
            if rec.state in ("done", "cancelled"):
                raise UserError(_("Cannot change a completed/cancelled encounter."))

    def _get_stage_by_state(self, state_code):
        return self.env["clinic.encounter.stage"].search([("state", "=", state_code)], limit=1)

    def estimate_end_from_planned(self):
        for rec in self:
            if rec.date_planned_start and not rec.date_planned_end and rec.planned_duration:
                rec.date_planned_end = rec.date_planned_start + timedelta(minutes=rec.planned_duration)
        return True

    def push_activity_followup(self, summary=None, days=1, user=None):
        for rec in self:
            rec.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=summary or _("Follow up encounter"),
                user_id=(user.id if isinstance(user, models.BaseModel) else user) or rec.user_id.id or self.env.user.id,
                date_deadline=fields.Date.today() + timedelta(days=days),
            )
        return True

    # MERGED: Consent flag recompute
    def _recompute_consent_ok(self):
        """
        Set consent_ok = True jika ada consent SIGNED & belum expired untuk encounter ini.
        Consent generik atau yang mencakup prosedur mana pun dianggap valid untuk encounter-level gate.
        """
        Consent = self.env["clinic.consent.document"]
        for rec in self:
            valid_exists = bool(Consent.search_count([
                ("encounter_id", "=", rec.id),
                ("state", "=", "signed"),
                "|", ("date_expiry", "=", False), ("date_expiry", ">", fields.Datetime.now()),
            ]))
            rec.write({"consent_ok": valid_exists})

    # -------------------------------------------------------------------------
    # Name & Search
    # -------------------------------------------------------------------------
    def name_get(self):
        result = []
        for rec in self:
            parts = [rec.name or ""]
            if rec.patient_id:
                parts.append(rec.patient_id.display_name)
            if rec.doctor_id:
                parts.append(_("by %s") % rec.doctor_id.display_name)
            result.append((rec.id, " — ".join([p for p in parts if p])))
        return result

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        extra_domain = list(domain or [])
        name_domain = ["|", ("name", operator, name), ("patient_id.display_name", operator, name)]
        recs = self.search(name_domain + extra_domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]



# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/encounter_stage.py
#
# Fungsi:
# - Mendefinisikan stage/tahap Encounter (Draft, In Progress, Done, Cancelled).
# - Menyediakan kontrol akses per stage (opsional via res.groups).
# - Kanban fold untuk stage yang "selesai/tertutup".
# - Hook saat masuk stage: jadwalkan aktivitas &/atau jalankan Server Action.
#
# Catatan integrasi:
# - Encounter (models/encounter.py) menggunakan field stage_id.state untuk derive 'state'.
# - Hook 'action_server_id' memungkinkan integrasi ringan ke:
#     • Reservasi room/queue ketika masuk 'In Progress'
#     • Notifikasi billing ketika 'Done'
#     • Pencatatan audit/QA ketika 'Cancelled'
#
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


_STAGE_SELECTION = [
    ("draft", "Draft"),
    ("in_progress", "In Progress"),
    ("done", "Done"),
    ("cancelled", "Cancelled"),
]


class ClinicEncounterStage(models.Model):
    _name = "clinic.encounter.stage"
    _description = "Encounter Stage"
    _order = "sequence, id"
    _check_company_auto = True

    # --------------------------------------------------------------------------------
    # Identitas & Perusahaan
    # --------------------------------------------------------------------------------
    name = fields.Char(required=True, index=True, translate=True)
    sequence = fields.Integer(default=10, index=True, help="Ordering for pipelines and kanban.")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        index=True,
        help="If empty, the stage is global (usable by all companies).",
    )

    # --------------------------------------------------------------------------------
    # Status Fungsional (dipakai oleh clinic.encounter.state)
    # --------------------------------------------------------------------------------
    state = fields.Selection(
        selection=_STAGE_SELECTION,
        required=True,
        default="draft",
        index=True,
        help="Functional state reflected into encounter.state.",
    )
    is_closed = fields.Boolean(
        string="Closed Stage",
        compute="_compute_is_closed",
        store=True,
        help="True for 'done' or 'cancelled' stages.",
    )
    fold = fields.Boolean(
        string="Folded in Kanban",
        help="Fold this stage in kanban view.",
    )
    color = fields.Integer(string="Color Index")
    description = fields.Text(string="Description / SLA / Notes")

    # --------------------------------------------------------------------------------
    # Kebijakan & Validasi Opsional
    # --------------------------------------------------------------------------------
    allow_edit = fields.Boolean(
        string="Allow Editing in This Stage",
        default=True,
        help="If disabled, records in this stage should be treated as read-only by business logic.",
    )
    require_consent = fields.Boolean(
        string="Require Consent Before Enter",
        help="Block moving encounters to this stage unless patient consent_ok is set.",
    )
    require_procedures = fields.Boolean(
        string="Require Procedures Before Enter",
        help="Block moving encounters to this stage unless at least one planned procedure exists.",
    )

    # --------------------------------------------------------------------------------
    # Akses Berbasis Grup (opsional)
    # --------------------------------------------------------------------------------
    allowed_group_ids = fields.Many2many(
        "res.groups",
        "clinic_encounter_stage_group_rel",
        "stage_id",
        "group_id",
        string="Allowed Groups to Enter",
        help="If set, only users in these groups can move an encounter to this stage.",
    )

    # --------------------------------------------------------------------------------
    # Hook saat Memasuki Stage
    # --------------------------------------------------------------------------------
    activity_type_id = fields.Many2one(
        "mail.activity.type",
        string="Default Activity on Enter",
        help="Schedule this activity for the encounter owner when entering this stage.",
    )
    activity_summary = fields.Char(
        string="Activity Summary",
        help="Summary used when creating the default activity.",
        default=lambda self: _("Follow up Encounter Stage"),
    )
    action_server_id = fields.Many2one(
        "ir.actions.server",
        string="Server Action on Enter",
        domain=[("state", "=", "code")],
        help="Optional server action to execute when an encounter enters this stage.",
    )

    # --------------------------------------------------------------------------------
    # Komputasi & Onchange
    # --------------------------------------------------------------------------------
    @api.depends("state")
    def _compute_is_closed(self):
        for rec in self:
            rec.is_closed = rec.state in ("done", "cancelled")

    @api.onchange("state")
    def _onchange_state(self):
        # Default: fold-kanban untuk stage closed
        if self.state in ("done", "cancelled"):
            self.fold = True

    # --------------------------------------------------------------------------------
    # Validasi & Constraint
    # --------------------------------------------------------------------------------
    _constraint_uniq_stage_name_company = models.Constraint(
        'unique(name, company_id)',
        'Stage name must be unique per company.',
    )

    @api.constrains("require_consent", "state")
    def _check_require_consent_consistency(self):
        # Tidak ada larangan, ini placeholder jika ingin aturan tambahan.
        for _rec in self:
            pass

    # --------------------------------------------------------------------------------
    # Utilitas untuk Encounter (dipanggil oleh model encounter)
    # --------------------------------------------------------------------------------
    def check_user_can_enter(self, user=None):
        """Validasi grup yang diizinkan memasuki stage ini."""
        self.ensure_one()
        user = user or self.env.user
        if self.allowed_group_ids:
            if not (user.groups_id & self.allowed_group_ids):
                raise UserError(
                    _(
                        "You are not allowed to move encounters to the stage '%s'."
                    )
                    % (self.display_name,)
                )
        return True

    def check_business_requirements(self, encounter):
        """Validasi bisnis ketika encounter akan dipindahkan ke stage ini."""
        self.ensure_one()
        if self.require_consent and not getattr(encounter, "consent_ok", False):
            raise ValidationError(
                _("Consent is required before moving to stage '%s'.") % self.display_name
            )
        if self.require_procedures and not encounter.procedure_line_ids:
            raise ValidationError(
                _("At least one planned procedure is required before moving to stage '%s'.")
                % self.display_name
            )
        # Jika stage scoped by company, pastikan company sesuai
        if self.company_id and encounter.company_id and self.company_id != encounter.company_id:
            raise ValidationError(
                _("Stage '%s' belongs to another company.") % self.display_name
            )
        return True

    def trigger_on_enter(self, encounter):
        """
        Dipanggil saat encounter memasuki stage ini.
        - Jadwalkan aktivitas default (jika di-set).
        - Jalankan server action (jika di-set).
        """
        self.ensure_one()
        # Aktivitas default
        if self.activity_type_id:
            try:
                encounter.activity_schedule(
                    self.activity_type_id.xml_id or self.activity_type_id.id,
                    summary=self.activity_summary or _("Follow up"),
                    user_id=encounter.user_id.id or self.env.user.id,
                )
            except Exception:
                # Jangan blok workflow hanya karena gagal aktivitas
                pass

        # Jalankan server action (kode python aman yang dikelola admin)
        if self.action_server_id:
            try:
                # Context membawa active_model/active_id untuk server action
                ctx = dict(self.env.context, active_model=encounter._name, active_id=encounter.id, active_ids=encounter.ids)
                self.action_server_id.with_context(ctx).run()
            except Exception as e:
                # Untuk safety, bungkus sebagai UserError agar admin tahu
                raise UserError(_("Server Action failed on stage enter: %s") % e)

    # --------------------------------------------------------------------------------
    # Batch Helper (opsional untuk mass-stage update)
    # --------------------------------------------------------------------------------
    def apply_to_encounters(self, encounter_ids):
        """
        Ubah stage untuk sekumpulan encounter (IDs atau recordset).
        Melakukan validasi grup & business requirement per encounter dan trigger hook.
        """
        self.ensure_one()
        encounters = encounter_ids
        if not isinstance(encounter_ids, models.BaseModel):
            encounters = self.env["clinic.encounter"].browse(encounter_ids)

        # Validasi akses user untuk stage ini
        self.check_user_can_enter()

        # Validasi & apply
        for enc in encounters:
            self.check_business_requirements(enc)
            enc.write({"stage_id": self.id})
            self.trigger_on_enter(enc)
        return True

    # --------------------------------------------------------------------------------
    # Name & Label
    # --------------------------------------------------------------------------------
    def name_get(self):
        label_by_state = {
            "draft": _("Draft"),
            "in_progress": _("In Progress"),
            "done": _("Done"),
            "cancelled": _("Cancelled"),
        }
        result = []
        for rec in self:
            badge = label_by_state.get(rec.state, rec.state or "")
            # Tambahkan badge kecil untuk memperjelas status fungsional
            result.append((rec.id, f"{rec.name} [{badge}]"))
        return result

    # --------------------------------------------------------------------------------
    # Unlink Proteksi
    # --------------------------------------------------------------------------------
    def unlink(self):
        # Cegah penghapusan jika stage dipakai encounter
        Encounter = self.env["clinic.encounter"]
        for stage in self:
            used = Encounter.search_count([("stage_id", "=", stage.id)], limit=1)
            if used:
                raise UserError(
                    _("Cannot delete stage '%s' because it is in use by encounters.") % stage.display_name
                )
        return super().unlink()

    # --------------------------------------------------------------------------------
    # Default Stage Utilities (opsional)
    # --------------------------------------------------------------------------------
    @api.model
    def stage_for_state(self, state_code, company=None):
        """Cari stage pertama untuk state tertentu. Jika tidak ada, return False."""
        company = company or self.env.company
        stage = self.search(
            [("state", "=", state_code), ("company_id", "in", [False, company.id])],
            order="company_id, sequence",
            limit=1,
        )
        return stage


# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/encounter_procedure.py
#
# Fungsi utama:
# - Menyimpan rencana/proposal prosedur klinis pada sebuah Encounter.
# - Integrasi ke katalog prosedur (clinic.procedure.catalog) & diagnosis.
# - Penjadwalan sesi tindakan (clinic.procedure.session) per rencana prosedur.
# - Perhitungan harga, pajak, dan total — siap dipakai untuk penagihan.
# - Many2many ke account.move.line (invoice lines) sebagai jejak billing.
#
# Catatan Integrasi:
# - encounter_id: header Encounter (models/encounter.py)
# - procedure_id: master prosedur (models/procedure_catalog.py)
# - diagnosis_id: opsional, mengikat rencana prosedur ke diagnosis tertentu
# - session_ids: sesi eksekusi tindakan (models/procedure_session.py) → asumsi field
#       'encounter_procedure_id' pada session (lihat _prepare_session_vals)
# - invoice_line_ids: keterkaitan ke penagihan berbasis account.move.line
# - konvensi invoice: invoice_origin == encounter.name
#
from math import isclose

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicEncounterProcedure(models.Model):
    _name = "clinic.encounter.procedure"
    _description = "Encounter Procedure Plan"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, id"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identitas & Perusahaan
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Line #",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        index=True,
        tracking=True,
    )
    sequence = fields.Integer(default=10, index=True)
    active = fields.Boolean(default=True, tracking=True)

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Konteks Encounter & Diagnosis
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
    diagnosis_id = fields.Many2one(
        "clinic.diagnosis",
        string="Linked Diagnosis",
        ondelete="set null",
        index=True,
        help="Optional diagnosis associated with this procedure plan.",
    )

    # -------------------------------------------------------------------------
    # Master Prosedur & Produk (Pricing)
    # -------------------------------------------------------------------------
    procedure_id = fields.Many2one(
        "clinic.procedure.catalog",
        string="Procedure",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        help="Mapped product/service for pricing and taxation.",
    )
    uom_id = fields.Many2one("uom.uom", string="Unit of Measure")
    quantity = fields.Float(string="Quantity", default=1.0, digits="Product Unit of Measure")
    planned_sessions = fields.Integer(
        string="Planned Sessions",
        default=1,
        help="Default number of sessions to generate from this plan.",
    )
    planned_duration = fields.Float(
        string="Planned Duration (min)",
        help="Estimated duration per session (minutes). Pulled from procedure if available.",
    )
    price_unit = fields.Monetary(string="Unit Price", currency_field="currency_id")
    discount = fields.Float(string="Discount (%)", digits=(16, 4), help="Percentage discount per unit.")
    tax_ids = fields.Many2many(
        "account.tax",
        "clinic_encounter_proc_tax_rel",
        "line_id",
        "tax_id",
        string="Customer Taxes",
        domain=[("type_tax_use", "in", ["sale", "none"])],
        help="Taxes applied for patient/customer billing.",
    )
    price_subtotal = fields.Monetary(string="Subtotal", compute="_compute_amount", store=True)
    price_tax = fields.Monetary(string="Tax", compute="_compute_amount", store=True)
    price_total = fields.Monetary(string="Total", compute="_compute_amount", store=True)

    billing_policy = fields.Selection(
        [
            ("per_plan", "Bill per Plan Line"),
            ("per_session", "Bill per Session"),
            ("no_bill", "Do Not Bill"),
        ],
        string="Billing Policy",
        default="per_plan",
        help="Billing approach for this procedure plan."
    )
    invoice_line_ids = fields.Many2many(
        "account.move.line",
        "clinic_enc_proc_invoice_line_rel",
        "proc_line_id",
        "aml_id",
        string="Invoice Lines",
        help="Billing lines generated from this plan (or its sessions).",
    )

    # -------------------------------------------------------------------------
    # Status & Eksekusi
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("planned", "Planned"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
    )
    session_ids = fields.One2many(
        "clinic.procedure.session",
        "encounter_procedure_id",
        string="Sessions",
        help="Execution sessions generated from this plan.",
    )
    session_count = fields.Integer(string="Sessions", compute="_compute_session_count", store=False)
    done_session_count = fields.Integer(string="Sessions Done", compute="_compute_session_done_count", store=False)

    performer_user_id = fields.Many2one(
        "res.users",
        string="Performer (User)",
        help="Default performer when generating sessions (optional).",
    )
    performer_doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Performer (Doctor)",
        help="Default doctor/clinician for sessions (optional).",
    )
    room_id = fields.Many2one(
        "clinic.room",
        string="Room",
        help="Preferred room if available (soft-coupled with queue/room module).",
    )

    notes = fields.Text(string="Notes for Performer")
    internal_note = fields.Text(string="Internal Notes")

    # UI
    color = fields.Integer(string="Color Index")
    priority = fields.Selection(
        [("0", "Normal"), ("1", "High"), ("2", "Urgent")],
        string="Priority",
        default="0",
        index=True,
    )

    # -------------------------------------------------------------------------
    # KOMPUTASI JUMLAH
    # -------------------------------------------------------------------------
    @api.depends("price_unit", "quantity", "discount", "tax_ids", "currency_id")
    def _compute_amount(self):
        """Hitung subtotal, pajak, total — menggunakan account.tax.compute_all."""
        for rec in self:
            qty = rec.quantity or 0.0
            unit = rec.price_unit or 0.0
            # Diskon persen
            effective_price = unit * (1 - (rec.discount or 0.0) / 100.0)
            taxes = rec.tax_ids.compute_all(
                effective_price,
                currency=rec.currency_id,
                quantity=qty,
                product=rec.product_id,
                partner=rec.partner_id,
            ) if rec.tax_ids else {
                "total_excluded": effective_price * qty,
                "total_included": effective_price * qty,
                "taxes": [],
            }
            rec.price_subtotal = taxes["total_excluded"]
            rec.price_total = taxes["total_included"]
            # Akumulasi pajak
            rec.price_tax = sum(t["amount"] for t in taxes.get("taxes", []))

    @api.depends("session_ids")
    def _compute_session_count(self):
        for rec in self:
            rec.session_count = len(rec.session_ids)

    @api.depends("session_ids.state")
    def _compute_session_done_count(self):
        for rec in self:
            rec.done_session_count = len(rec.session_ids.filtered(lambda s: s.state == "done"))

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("procedure_id")
    def _onchange_procedure_id(self):
        """Prefill produk, UoM, durasi, harga, dan pajak dari master prosedur."""
        proc = self.procedure_id
        if not proc:
            return
        vals = {}
        # Map product & UOM
        if getattr(proc, "product_id", False):
            vals["product_id"] = proc.product_id.id
            if not self.uom_id:
                vals["uom_id"] = proc.product_id.uom_id.id
        elif getattr(proc, "uom_id", False) and not self.uom_id:
            vals["uom_id"] = proc.uom_id.id

        # Durasi default
        if getattr(proc, "default_duration_min", False) and not self.planned_duration:
            vals["planned_duration"] = proc.default_duration_min

        # Harga default dari procedure (prioritas) lalu fallback ke product.list_price
        price = False
        if getattr(proc, "list_price", False):
            price = proc.list_price
        elif getattr(proc, "product_id", False):
            price = proc.product_id.lst_price
        if price is not False:
            vals["price_unit"] = price

        # Pajak dari product (customer taxes)
        if getattr(proc, "product_id", False) and proc.product_id.taxes_id:
            vals["tax_ids"] = [(6, 0, proc.product_id.taxes_id.ids)]

        # Billing policy dari master (jika ada)
        if getattr(proc, "billing_policy", False) and not self.billing_policy:
            vals["billing_policy"] = proc.billing_policy

        if vals:
            self.update(vals)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        """Sinkronisasi UoM, pajak, dan harga bila user memilih produk langsung."""
        prod = self.product_id
        if not prod:
            return
        vals = {}
        if not self.uom_id:
            vals["uom_id"] = prod.uom_id.id
        if prod.taxes_id:
            vals["tax_ids"] = [(6, 0, prod.taxes_id.ids)]
        # Jika price_unit belum diisi atau 0, ambil dari list_price
        if not self.price_unit or isclose(self.price_unit, 0.0, rel_tol=1e-9, abs_tol=1e-9):
            vals["price_unit"] = prod.lst_price
        if vals:
            self.update(vals)

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    _constraint_qty_positive = models.Constraint(
        'CHECK (quantity >= 0)',
        'Quantity must be positive.',
    )
    _constraint_uniq_line_name_company = models.Constraint(
        'unique(name, company_id)',
        'Line number must be unique per company.',
    )

    @api.constrains("encounter_id", "company_id")
    def _check_company_consistency(self):
        for rec in self:
            if rec.encounter_id and rec.company_id and rec.company_id != rec.encounter_id.company_id:
                raise ValidationError(_("Procedure line company must match Encounter company."))

    @api.constrains("uom_id", "product_id")
    def _check_uom_category(self):
        for rec in self:
            if rec.product_id and rec.uom_id and rec.product_id.uom_id.category_id != rec.uom_id.category_id:
                raise ValidationError(_("The selected Unit of Measure is not compatible with the product's UoM."))

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if vals.get("name", _("New")) in (False, _("New")):
                vals["name"] = seq.next_by_code("clinic.encounter.procedure") or _("New")
        recs = super().create(vals_list)
        # Activity default
        for rec in recs:
            try:
                rec.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Prepare procedure plan"),
                    user_id=(rec.encounter_id.user_id.id if rec.encounter_id and rec.encounter_id.user_id else self.env.user.id),
                    date_deadline=fields.Date.today(),
                )
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        # Jika quantity diubah dan sudah ada sesi, bisa beri peringatan ringan via chatter
        if "quantity" in vals or "planned_sessions" in vals:
            for rec in self.filtered(lambda r: r.session_ids):
                rec.message_post(body=_("Quantity/Sessions changed after sessions were generated. Please reconcile scheduling."))
        return res

    def unlink(self):
        for rec in self:
            if rec.invoice_line_ids:
                raise UserError(_("Cannot delete a billed procedure line. Consider cancelling instead."))
            if any(s.state in ("in_progress", "done") for s in rec.session_ids):
                raise UserError(_("Cannot delete a procedure line with in-progress/done sessions."))
        return super().unlink()

    # -------------------------------------------------------------------------
    # WORKFLOW
    # -------------------------------------------------------------------------
    def action_plan(self):
        """Set status Planned; biasa dipanggil setelah melengkapi detail rencana."""
        for rec in self:
            rec.write({"state": "planned"})
        return True

    def action_start(self):
        """Tandai In Progress. Biasanya saat sesi pertama dimulai."""
        for rec in self:
            rec.write({"state": "in_progress"})
        return True

    def action_done(self):
        """Tandai Done. Biasanya setelah semua sesi tuntas (atau secara manual)."""
        for rec in self:
            # Validasi: bila ada planned sessions, pastikan minimal ada sesi selesai
            if rec.planned_sessions and not rec.session_ids.filtered(lambda s: s.state == "done"):
                rec.message_post(body=_("Marked done without any completed sessions."))
            rec.write({"state": "done"})
        return True

    def action_cancel(self, reason=None):
        for rec in self:
            rec.write({"state": "cancelled"})
            if reason:
                rec.message_post(body=_("Cancelled: %s") % reason)
        return True

    # -------------------------------------------------------------------------
    # SESSIONS
    # -------------------------------------------------------------------------
    def action_generate_sessions(self):
        """
        Generate sessions sebanyak 'planned_sessions'.
        Bila sesi sudah ada, tidak digandakan — gunakan tambah manual kalau perlu.
        """
        Session = self.env["clinic.procedure.session"]
        generated = self.env[self._name]
        for rec in self:
            remain = max(rec.planned_sessions - len(rec.session_ids), 0)
            for i in range(remain):
                vals = rec._prepare_session_vals(index=i + 1)
                sess = Session.create(vals)
                generated |= rec
            # Autoplan status
            if rec.state == "draft":
                rec.state = "planned"
        return {
            "type": "ir.actions.act_window",
            "name": _("Sessions"),
            "res_model": "clinic.procedure.session",
            "view_mode": "list,form,calendar,kanban",
            "domain": [("encounter_procedure_id", "in", self.ids)],
            "context": {"search_default_encounter_procedure_id": self.ids},
        }

    def _prepare_session_vals(self, index=1):
        """
        Siapkan nilai default pembuatan session dari rencana ini.
        Asumsi di model session terdapat field:
        - encounter_id, encounter_procedure_id, diagnosis_id
        - performer_user_id, performer_doctor_id
        - room_id
        - planned_duration (menit)
        - billing_policy (inherit dari line)
        """
        self.ensure_one()
        return {
            "name": "%s • S%02d" % (self.procedure_id.display_name if self.procedure_id else self.name, index),
            "encounter_id": self.encounter_id.id,
            "encounter_procedure_id": self.id,
            "diagnosis_id": self.diagnosis_id.id if self.diagnosis_id else False,
            "performer_user_id": self.performer_user_id.id if self.performer_user_id else False,
            "performer_doctor_id": self.performer_doctor_id.id if self.performer_doctor_id else False,
            "room_id": self.room_id.id if self.room_id else False,
            "planned_duration": self.planned_duration or 0.0,
            "billing_policy": self.billing_policy,
            # Bridge ke inventory/billing dapat ditangani di model session saat start/done
        }

    def action_open_sessions(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_procedure_session").read()[0]
        action["domain"] = [("encounter_procedure_id", "=", self.id)]
        action["context"] = {
            "default_encounter_id": self.encounter_id.id,
            "default_encounter_procedure_id": self.id,
            "default_diagnosis_id": self.diagnosis_id.id if self.diagnosis_id else False,
        }
        return action

    # -------------------------------------------------------------------------
    # BILLING (BRIDGES)
    # -------------------------------------------------------------------------
    def action_prepare_invoice_line_vals(self):
        """
        Kembalikan list of dict vals untuk pembuatan account.move.line berdasarkan
        kebijakan billing line ini. Dipakai wizard Generate Bill.
        - per_plan  : 1 line dari plan
        - per_session: 1 line per session (yang eligible) → di sini hanya siapkan untuk sesi yang 'done'
        - no_bill   : return []
        """
        self.ensure_one()
        if self.billing_policy == "no_bill":
            return []

        if not self.partner_id:
            raise UserError(_("Patient partner is not set on the Encounter."))

        if self.billing_policy == "per_session":
            lines = []
            sessions = self.session_ids.filtered(lambda s: s.state == "done")
            if not sessions:
                # Masih kembalikan kosong, wizard bisa tampilkan info ke user
                return []
            for s in sessions:
                vals = self._prepare_single_invoice_line(
                    description="%s — %s" % (self.procedure_id.display_name, s.display_name or s.name),
                    qty=1.0,
                )
                lines.append(vals)
            return lines

        # per_plan
        return [self._prepare_single_invoice_line(description=self._get_default_description(), qty=self.quantity or 1.0)]

    def _prepare_single_invoice_line(self, description, qty=1.0):
        """
        Siapkan 1 baris account.move.line (dalam konteks pembuatan invoice customer).
        """
        self.ensure_one()
        # Pemetaan pajak berdasarkan fiscal position partner (jika ada)
        partner = self.partner_id
        fpos = partner.property_account_position_id if partner else False
        taxes = self.tax_ids
        if fpos:
            taxes = fpos.map_tax(taxes, product=self.product_id, partner=partner)

        # Harga bersih setelah diskon
        price_unit = (self.price_unit or 0.0) * (1 - (self.discount or 0.0) / 100.0)

        # Akun pendapatan (ambil dari product atau kategori)
        account_id = False
        if self.product_id and getattr(self.product_id, "property_account_income_id", False) and self.product_id.property_account_income_id:
            account_id = self.product_id.property_account_income_id.id
        elif self.product_id and self.product_id.categ_id and self.product_id.categ_id.property_account_income_categ_id:
            account_id = self.product_id.categ_id.property_account_income_categ_id.id
        else:
            # fallback: cari account income default perusahaan
            account_id = self.company_id.account_sale_tax_id and self.company_id.account_sale_tax_id.id or False
            # jika tetap False, biarkan account diisi otomatis oleh akun default di invoice

        return {
            "name": description,
            "quantity": qty,
            "price_unit": price_unit,
            "discount": 0.0,  # diskon sudah dihitung ke price_unit
            "product_id": self.product_id.id if self.product_id else False,
            "product_uom_id": self.uom_id.id if self.uom_id else (self.product_id.uom_id.id if self.product_id else False),
            "tax_ids": [(6, 0, taxes.ids)] if taxes else [],
            "account_id": account_id,
            "currency_id": self.currency_id.id,
            # Relasi balik — akan dihubungkan oleh wizard setelah line dibuat
        }

    def _get_default_description(self):
        self.ensure_one()
        base = self.procedure_id.display_name if self.procedure_id else (self.product_id.display_name if self.product_id else self.name)
        if self.diagnosis_id:
            return "%s — Dx: %s" % (base, self.diagnosis_id.display_code or self.diagnosis_id.name)
        return base

    def action_open_billing(self):
        """Buka invoice yang berasal dari Encounter (konvensi invoice_origin)."""
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

    # -------------------------------------------------------------------------
    # SMART BUTTONS
    # -------------------------------------------------------------------------
    def action_view_invoices(self):
        return self.action_open_billing()

    # -------------------------------------------------------------------------
    # NAME & SEARCH
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            base = rec.procedure_id.display_name if rec.procedure_id else (rec.product_id.display_name if rec.product_id else rec.name)
            label = f"{rec.name} • {base}"
            res.append((rec.id, label))
        return res

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        extra_domain = list(domain or [])
        name_domain = ["|", "|",
                  ("name", operator, name),
                  ("procedure_id.display_name", operator, name),
                  ("encounter_id.name", operator, name)]
        recs = self.search(name_domain + extra_domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]



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
    def name_get(self):
        res = []
        for rec in self:
            label = rec.display_code or rec.name or ""
            # Tambahkan flag kecil untuk primary / certainty
            badges = []
            if rec.type == "primary":
                badges.append(_("Primary"))
            if rec.certainty:
                badges.append(dict(self._fields["certainty"].selection).get(rec.certainty))
            if badges:
                label = f"{label} ({', '.join(badges)})"
            res.append((rec.id, label))
        return res

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        extra_domain = list(domain or [])
        name_domain = ["|", "|", ("name", operator, name), ("code", operator, name), ("display_code", operator, name)]
        recs = self.search(name_domain + extra_domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]



# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/consent.py
#
# Fitur:
# - Template persetujuan (multi-company, multi-procedure, risiko default, masa berlaku).
# - Dokumen persetujuan (encounter/session/procedure): tanda tangan pasien/guardian, saksi, lampiran.
# - Workflow: Draft → Signed → (Expired) / Revoked / Cancelled.
# - Hitung masa berlaku, flag is_valid/is_expired.
# - Integrasi: Encounter (auto set consent_ok), Procedure/Session/Diagnosis linkage, Stage policy.
# - Portal-ready dan audit (mail.thread/activity).
#
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =============================================================================
# TEMPLATE: Risk/Disclosure Items
# =============================================================================
class ClinicConsentRiskTemplate(models.Model):
    _name = "clinic.consent.risk.template"
    _description = "Consent Risk/Disclosure (Template)"
    _order = "sequence, id"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True, index=True, help="Risk/complication or disclosure item title.")
    description = fields.Text(string="Description / Details")
    sequence = fields.Integer(default=10, index=True)
    active = fields.Boolean(default=True)
    required = fields.Boolean(
        string="Required Acknowledgement",
        default=True,
        help="If enabled, the patient/guardian must acknowledge this item on the consent document.",
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )


# =============================================================================
# TEMPLATE: Consent Template (Master)
# =============================================================================
class ClinicConsentTemplate(models.Model):
    _name = "clinic.consent.template"
    _description = "Consent Template"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True, tracking=True, index=True)
    sequence = fields.Integer(default=10, index=True)
    active = fields.Boolean(default=True, tracking=True)

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    language = fields.Selection(
        selection=lambda self: self.env["res.lang"].get_installed(),
        string="Language",
        help="Preferred language of the consent body.",
    )

    # Ruang lingkup template
    procedure_ids = fields.Many2many(
        "clinic.procedure.catalog",
        "clinic_consent_tmpl_procedure_rel",
        "template_id",
        "procedure_id",
        string="Applicable Procedures",
        help="If empty, template is generic and can be used for any procedure.",
    )
    category = fields.Char(string="Category/Use", help="E.g., Surgery, Radiology, Minor procedure.")

    # Isi & tampilan
    title = fields.Char(string="Default Title")
    body_html = fields.Html(
        string="Consent Body (HTML)",
        help="Main body of the consent. You can use variables like ${patient}, ${procedure}, ${doctor}, ${date}.",
    )
    footer_html = fields.Html(string="Footer / Additional Notes")

    # Pengaturan & Kebijakan
    validity_days = fields.Integer(
        string="Default Validity (days)",
        default=365,
        help="Signed consents created from this template will expire after this number of days.",
    )
    require_witness = fields.Boolean(
        string="Require Witness",
        default=False,
        help="If enabled, at least one witness signature is expected for documents derived from this template.",
    )
    require_guardian_if_minor = fields.Boolean(
        string="Require Guardian if Minor",
        default=True,
        help="If enabled, consent should be signed by guardian when patient is under legal age.",
    )
    risk_item_ids = fields.Many2many(
        "clinic.consent.risk.template",
        "clinic_consent_tmpl_risk_rel",
        "template_id",
        "risk_tmpl_id",
        string="Default Risk/Disclosure Items",
    )

    note_internal = fields.Text(string="Internal Notes")

    _constraint_uniq_template_name_company = models.Constraint(
        'unique(name, company_id)',
        'Consent Template name must be unique per company.',
    )

    def action_preview_variables(self):
        """Helper kecil untuk admin melihat variabel yang tersedia (chatter message)."""
        self.ensure_one()
        msg = _(
            "Available placeholders: ${patient}, ${patient_age}, ${procedure}, ${doctor}, ${date}, ${encounter}, ${company}."
        )
        self.message_post(body=msg)
        return True


# =============================================================================
# DOCUMENT: Consent Document (Header)
# =============================================================================
class ClinicConsentDocument(models.Model):
    _name = "clinic.consent.document"
    _description = "Consent Document"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _order = "date_signed desc, id desc"
    _check_company_auto = True

    # Identitas
    name = fields.Char(
        string="Consent #",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        tracking=True,
        index=True,
    )
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )

    # Konteks Klinis
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Encounter",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    session_id = fields.Many2one(
        "clinic.procedure.session",
        string="Session",
        ondelete="set null",
        index=True,
        help="If consent is captured specific to a session.",
    )
    procedure_ids = fields.Many2many(
        "clinic.procedure.catalog",
        "clinic_consent_proc_rel",
        "consent_id",
        "procedure_id",
        string="Procedures Covered",
        help="If empty, the consent is generic for the encounter.",
    )
    diagnosis_id = fields.Many2one("clinic.diagnosis", string="Diagnosis", ondelete="set null", index=True)

    patient_id = fields.Many2one(
        "clinic.patient",
        related="encounter_id.patient_id",
        store=True,
        readonly=True,
        index=True,
    )
    partner_id = fields.Many2one("res.partner", related="patient_id.partner_id", store=True, readonly=True)
    doctor_id = fields.Many2one("clinic.doctor", related="encounter_id.doctor_id", store=True, readonly=True)

    # Template & Konten
    template_id = fields.Many2one("clinic.consent.template", string="Template", ondelete="set null", index=True)
    title = fields.Char(string="Title")
    body_html = fields.Html(string="Consent Body")
    footer_html = fields.Html(string="Footer")

    language = fields.Selection(
        selection=lambda self: self.env["res.lang"].get_installed(),
        string="Language",
        help="Language of this document.",
    )

    # Status & Masa Berlaku
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("signed", "Signed"),
            ("expired", "Expired"),
            ("revoked", "Revoked"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        index=True,
        tracking=True,
    )
    validity_days = fields.Integer(string="Validity (days)", default=365)
    date_signed = fields.Datetime(string="Signed On", tracking=True)
    date_expiry = fields.Datetime(string="Expires On", compute="_compute_expiry", store=True)
    is_expired = fields.Boolean(string="Is Expired?", compute="_compute_is_expired", store=True)
    is_valid = fields.Boolean(string="Is Valid?", compute="_compute_is_valid", store=True)

    # Penandatangan & Saksi
    sign_by_patient = fields.Boolean(string="Signed by Patient", default=True)
    is_guardian = fields.Boolean(string="Signed by Guardian", default=False)
    guardian_name = fields.Char(string="Guardian Name")
    guardian_relation = fields.Char(string="Relation to Patient")

    signer_name = fields.Char(string="Signer Name")
    signer_partner_id = fields.Many2one("res.partner", string="Signer Contact")
    signer_document_no = fields.Char(string="Signer ID/Document No.")

    witness1_name = fields.Char(string="Witness #1 Name")
    witness1_signature = fields.Binary(string="Witness #1 Signature", attachment=True)
    witness2_name = fields.Char(string="Witness #2 Name")
    witness2_signature = fields.Binary(string="Witness #2 Signature", attachment=True)

    # Tanda tangan digital (widget signature)
    signature = fields.Binary(string="Signature", attachment=True)
    signature_guardian = fields.Binary(string="Guardian Signature", attachment=True)
    signature_ip = fields.Char(string="Signed IP")
    signature_note = fields.Char(string="Signature Note")

    # Lampiran & Tag
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "clinic_consent_attachment_rel",
        "consent_id",
        "attachment_id",
        string="Attachments",
    )
    tag_ids = fields.Many2many("clinic.soap.tag", string="Tags")

    # Risiko / item yang harus di-ack (akan di-clone dari template)
    risk_line_ids = fields.One2many("clinic.consent.risk", "consent_id", string="Risk/Disclosure Acknowledgements")

    # Ringkas
    summary = fields.Char(string="Summary", compute="_compute_summary", store=True)

    # Billing bridge (opsional)
    invoice_line_ids = fields.Many2many(
        "account.move.line",
        "clinic_consent_invoice_line_rel",
        "consent_id",
        "aml_id",
        string="Invoice Lines",
        help="Billing lines if consent capture is billable in your flow.",
    )

    color = fields.Integer(string="Color Index")
    note_internal = fields.Text(string="Internal Notes")

    # -------------------------------------------------------------------------
    # Komputasi
    # -------------------------------------------------------------------------
    @api.depends("date_signed", "validity_days")
    def _compute_expiry(self):
        for rec in self:
            if rec.date_signed and rec.validity_days and rec.validity_days > 0:
                rec.date_expiry = rec.date_signed + timedelta(days=rec.validity_days)
            else:
                rec.date_expiry = False

    @api.depends("state", "date_expiry")
    def _compute_is_expired(self):
        today = fields.Datetime.now()
        for rec in self:
            rec.is_expired = bool(rec.state in ("signed", "expired") and rec.date_expiry and rec.date_expiry < today)

    @api.depends("state", "is_expired")
    def _compute_is_valid(self):
        for rec in self:
            rec.is_valid = bool(rec.state == "signed" and not rec.is_expired)

    @api.depends("title", "procedure_ids", "guardian_name", "is_guardian")
    def _compute_summary(self):
        def short(txt, n=100):
            if not txt:
                return ""
            s = " ".join(txt.split())
            return (s[: n - 1] + "…") if len(s) > n else s

        for rec in self:
            parts = [rec.title or _("Consent")]
            if rec.procedure_ids:
                parts.append(", ".join(rec.procedure_ids.mapped("display_name")[:3]))
            if rec.is_guardian and rec.guardian_name:
                parts.append(_("by %s (guardian)") % rec.guardian_name)
            rec.summary = " — ".join([p for p in parts if p]) or False

    # -------------------------------------------------------------------------
    # Onchange
    # -------------------------------------------------------------------------
    @api.onchange("template_id")
    def _onchange_template(self):
        tmpl = self.template_id
        if not tmpl:
            return
        vals = {}
        if tmpl.title and not self.title:
            vals["title"] = tmpl.title
        if tmpl.body_html and not self.body_html:
            vals["body_html"] = self._render_template_body(tmpl.body_html)
        if tmpl.footer_html and not self.footer_html:
            vals["footer_html"] = tmpl.footer_html
        if tmpl.validity_days and (not self.validity_days or self.validity_days == 365):
            vals["validity_days"] = tmpl.validity_days
        if tmpl.language and not self.language:
            vals["language"] = tmpl.language
        if tmpl.procedure_ids and not self.procedure_ids:
            vals["procedure_ids"] = [(6, 0, tmpl.procedure_ids.ids)]
        self.update(vals)
        # Clone risk items jika belum ada
        if tmpl.risk_item_ids and not self.risk_line_ids:
            self._clone_risk_from_template()

    @api.onchange("session_id")
    def _onchange_session(self):
        sess = self.session_id
        if not sess:
            return
        vals = {}
        if sess.procedure_id and not self.procedure_ids:
            vals["procedure_ids"] = [(6, 0, [sess.procedure_id.id])]
        if not self.title and sess.procedure_id:
            vals["title"] = _("Consent — %s") % (sess.procedure_id.display_name or sess.procedure_id.name)
        if sess.diagnosis_id and not self.diagnosis_id:
            vals["diagnosis_id"] = sess.diagnosis_id.id
        self.update(vals)

    # -------------------------------------------------------------------------
    # Constraint
    # -------------------------------------------------------------------------
    _constraint_uniq_consent_name_company = models.Constraint(
        'unique(name, company_id)',
        'Consent number must be unique per company.',
    )

    @api.constrains("company_id", "encounter_id")
    def _check_company_consistency(self):
        for rec in self:
            if rec.encounter_id and rec.company_id and rec.company_id != rec.encounter_id.company_id:
                raise ValidationError(_("Consent company must match Encounter company."))

    @api.constrains("signature", "sign_by_patient", "is_guardian", "signature_guardian")
    def _check_signature_presence(self):
        for rec in self:
            if rec.state == "signed":
                # setidaknya ada satu tanda tangan valid
                if rec.sign_by_patient and not rec.signature:
                    raise ValidationError(_("Patient signature is required."))
                if rec.is_guardian and not rec.signature_guardian:
                    raise ValidationError(_("Guardian signature is required."))

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if vals.get("name", _("New")) in (False, _("New")):
                vals["name"] = seq.next_by_code("clinic.consent.document") or _("New")
            # Prefill body dari template bila ada
            if vals.get("template_id") and not vals.get("body_html"):
                tmpl = self.env["clinic.consent.template"].browse(vals["template_id"])
                if tmpl and tmpl.body_html:
                    # Render sederhana placeholder; var lain diselesaikan on-change/compute
                    vals["body_html"] = tmpl.body_html
            # Tarik encounter dari session jika belum terisi
            if not vals.get("encounter_id") and vals.get("session_id"):
                sess = self.env["clinic.procedure.session"].browse(vals["session_id"])
                if sess and sess.encounter_id:
                    vals["encounter_id"] = sess.encounter_id.id
        recs = super().create(vals_list)
        # Clone risk items dari template
        for rec in recs:
            if rec.template_id and not rec.risk_line_ids:
                rec._clone_risk_from_template()
            # Activity: minta tanda tangan
            try:
                rec.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Collect consent signature"),
                    user_id=rec.encounter_id.user_id.id if rec.encounter_id and rec.encounter_id.user_id else self.env.user.id,
                    date_deadline=fields.Date.today(),
                )
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        # Setelah perubahan state/tanda tangan, upsert consent_ok pada encounter
        if {"state", "signature", "signature_guardian", "date_signed", "validity_days"} & set(vals.keys()):
            for rec in self:
                rec._update_encounter_consent_flag()
        return res

    # -------------------------------------------------------------------------
    # Workflow Actions
    # -------------------------------------------------------------------------
    def action_set_draft(self):
        for rec in self:
            if rec.state in ("revoked", "cancelled"):
                raise UserError(_("Cannot reset a revoked/cancelled consent to draft."))
            rec.write({"state": "draft"})
        return True

    def action_sign(self):
        """
        Tandai sebagai 'signed'. Validasi acknowledgement item yang required.
        Gunakan widget signature di form untuk mengisi signature/signature_guardian lebih dahulu.
        """
        for rec in self:
            # Periksa ack risiko wajib
            missing = rec.risk_line_ids.filtered(lambda r: r.required and not r.acknowledged)
            if missing:
                names = ", ".join(missing.mapped("name")[:5])
                raise UserError(_("Please acknowledge all required items before signing: %s") % names)

            # Validasi minimal isi
            if not (rec.signature or rec.signature_guardian):
                raise UserError(_("Please capture the signature (patient or guardian) before signing."))

            updates = {
                "state": "signed",
                "date_signed": rec.date_signed or fields.Datetime.now(),
            }
            rec.write(updates)
            # Set flag consent_ok di encounter
            rec._update_encounter_consent_flag()
            # Follow-up ke owner encounter
            try:
                rec.encounter_id.push_activity_followup(
                    summary=_("Consent signed"),
                    days=0,
                    user=rec.encounter_id.user_id or self.env.user,
                )
            except Exception:
                pass
        return True

    def action_mark_expired(self):
        for rec in self:
            if rec.state == "signed" and rec.is_expired:
                rec.write({"state": "expired"})
                rec._update_encounter_consent_flag()
        return True

    def action_revoke(self, reason=None):
        for rec in self:
            rec.write({"state": "revoked"})
            if reason:
                rec.message_post(body=_("Consent revoked: %s") % reason)
            rec._update_encounter_consent_flag()
        return True

    def action_cancel(self, reason=None):
        for rec in self:
            rec.write({"state": "cancelled"})
            if reason:
                rec.message_post(body=_("Consent cancelled: %s") % reason)
            rec._update_encounter_consent_flag()
        return True

    def action_print_report(self):
        """Cetak QWeb report bila tersedia (opsional)."""
        self.ensure_one()
        try:
            return self.env.ref("clinic_encounter.action_report_consent_document").report_action(self)
        except Exception:
            raise UserError(_("Consent report template is not configured."))

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def covers_procedure(self, procedure):
        """Kembalikan True jika consent ini mencakup prosedur yang diberikan (atau generik)."""
        self.ensure_one()
        if not procedure:
            return True
        return not self.procedure_ids or procedure.id in self.procedure_ids.ids

    def is_currently_valid(self, for_procedure=None):
        """True jika state=Signed, belum expired, dan (opsional) mencakup prosedur tertentu."""
        self.ensure_one()
        return bool(self.is_valid and self.covers_procedure(for_procedure))

    def _clone_risk_from_template(self):
        self.ensure_one()
        if not self.template_id or not self.template_id.risk_item_ids:
            return
        vals_list = []
        for i, tmpl in enumerate(self.template_id.risk_item_ids.sorted(lambda r: r.sequence)):
            vals_list.append({
                "consent_id": self.id,
                "sequence": (tmpl.sequence or 10) + i,
                "name": tmpl.name,
                "description": tmpl.description,
                "required": tmpl.required,
            })
        if vals_list:
            self.env["clinic.consent.risk"].create(vals_list)

    def _render_template_body(self, html):
        """Render placeholder sederhana di body template (tanpa Jinja; aman)."""
        self.ensure_one()
        patient = self.patient_id and self.patient_id.display_name or ""
        doctor = self.doctor_id and self.doctor_id.display_name or ""
        procedure = ", ".join(self.procedure_ids.mapped("display_name")) if self.procedure_ids else _("(General)")
        company = self.company_id and self.company_id.display_name or ""
        encounter = self.encounter_id and self.encounter_id.name or ""
        today = fields.Date.context_today(self)
        mapping = {
            "${patient}": patient,
            "${doctor}": doctor,
            "${procedure}": procedure,
            "${company}": company,
            "${encounter}": encounter,
            "${date}": today.strftime("%Y-%m-%d") if hasattr(today, "strftime") else str(today),
            "${patient_age}": getattr(self.patient_id, "age_display", "") or "",
        }
        rendered = html
        for k, v in mapping.items():
            rendered = (rendered or "").replace(k, v)
        return rendered

    def _update_encounter_consent_flag(self):
        """Set encounter.consent_ok = True jika ada consent valid di encounter ini."""
        for rec in self:
            if not rec.encounter_id:
                continue
            rec.encounter_id._recompute_consent_ok()

    # Portal mixin
    def _get_report_base_filename(self):
        self.ensure_one()
        return f"{self.name} - {self.patient_id.display_name or ''}".strip()


# =============================================================================
# DOCUMENT: Consent Risk/Disclosure (Instance Lines)
# =============================================================================
class ClinicConsentRisk(models.Model):
    _name = "clinic.consent.risk"
    _description = "Consent Risk/Disclosure (Document Line)"
    _order = "consent_id, sequence, id"
    _check_company_auto = True

    consent_id = fields.Many2one("clinic.consent.document", string="Consent", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", related="consent_id.company_id", store=True, readonly=True)

    sequence = fields.Integer(default=10, index=True)
    name = fields.Char(required=True, translate=True, index=True)
    description = fields.Text(string="Description / Details")
    required = fields.Boolean(string="Required", default=True)
    acknowledged = fields.Boolean(
        string="Acknowledged",
        help="Tick to confirm the signer has acknowledged this item.",
        default=False,
    )
    note = fields.Char(string="Note")

    color = fields.Integer(string="Color Index")

    _constraint_name_not_empty = models.Constraint(
        "CHECK (char_length(coalesce(name, '')) > 0)",
        'Item must have a name.',
    )


# # =============================================================================
# # EXTENSIONS: Encounter & Session bridges
# # =============================================================================
# class ClinicEncounter_Consent(models.Model):
#     _inherit = "clinic.encounter"

#     consent_ids = fields.One2many("clinic.consent.document", "encounter_id", string="Consents")
#     consent_count = fields.Integer(compute="_compute_consent_count", string="Consents", store=False)

#     def _compute_consent_count(self):
#         for rec in self:
#             rec.consent_count = len(rec.consent_ids)

#     def action_open_consents(self):
#         self.ensure_one()
#         action = self.env.ref("clinic_encounter.action_clinic_consent_document").read()[0]
#         action["domain"] = [("encounter_id", "=", self.id)]
#         action["context"] = {"default_encounter_id": self.id}
#         return action

#     def _recompute_consent_ok(self):
#         """
#         Set consent_ok = True jika ada consent SIGNED & belum expired untuk encounter ini.
#         Consent generik atau yang mencakup prosedur mana pun dianggap valid untuk encounter-level gate.
#         """
#         for rec in self:
#             Consent = self.env["clinic.consent.document"]
#             valid_exists = bool(Consent.search_count([
#                 ("encounter_id", "=", rec.id),
#                 ("state", "=", "signed"),
#                 "|", ("date_expiry", "=", False), ("date_expiry", ">", fields.Datetime.now()),
#             ]))
#             # langsung tulis (hindari tracking berlebih)
#             super(ClinicEncounter_Consent, rec).write({"consent_ok": valid_exists})
#         return True


# class ClinicProcedureSession_Consent(models.Model):
#     _inherit = "clinic.procedure.session"

#     consent_valid = fields.Boolean(
#         string="Consent Valid for Session",
#         compute="_compute_consent_valid_for_session",
#         store=False,
#         help="True if the encounter has a signed, non-expired consent that covers this session's procedure (or is generic).",
#     )

#     @api.depends("encounter_id.consent_ids.state", "encounter_id.consent_ids.date_expiry", "procedure_id")
#     def _compute_consent_valid_for_session(self):
#         for rec in self:
#             valid = False
#             for c in rec.encounter_id.consent_ids.filtered(lambda r: r.state == "signed" and not r.is_expired):
#                 if c.covers_procedure(rec.procedure_id):
#                     valid = True
#                     break
#             rec.consent_valid = valid



# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/checklist.py
#
# Fitur:
# - Template Checklist (multi-scope), item & opsi jawaban.
# - Checklist Instance (encounter/session/procedure/anesthesia/adverse/result/consent).
# - Jawaban: yes/no, select (opsi), number, text, date/datetime, signature, attachment.
# - Skoring total & persentase, kelulusan berdasarkan ambang (threshold), dan validasi "required".
# - Integrasi: Encounter & Session memiliki smart button/counter; Session.start akan memeriksa
#   kepatuhan checklist jika procedure/catalog mengharuskannya.
#
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =============================================================================
# MASTER: Template Checklist
# =============================================================================
class ClinicChecklistTemplate(models.Model):
    _name = "clinic.checklist.template"
    _description = "Checklist Template"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True, index=True, tracking=True)
    code = fields.Char(index=True, help="Optional template code (external mapping).")
    sequence = fields.Integer(default=10, index=True)
    active = fields.Boolean(default=True, tracking=True)

    company_id = fields.Many2one("res.company", default=lambda s: s.env.company, required=True, index=True)
    language = fields.Selection(
        selection=lambda self: self.env["res.lang"].get_installed(),
        string="Language",
        help="Preferred language of checklist display texts.",
    )

    # Scope penggunaan
    scope = fields.Selection(
        [
            ("encounter", "Encounter"),
            ("session", "Procedure Session"),
            ("procedure", "Procedure Plan"),
            ("anesthesia", "Anesthesia Case"),
            ("consent", "Consent"),
            ("adverse", "Adverse Event"),
            ("result", "Result Document"),
            ("generic", "Generic"),
        ],
        string="Scope",
        default="encounter",
        index=True,
        help="Primary intended usage; instances can still be linked broadly.",
    )

    # Pengikat opsional untuk otomatisasi
    encounter_stage_ids = fields.Many2many(
        "clinic.encounter.stage",
        "clinic_checklist_tmpl_stage_rel",
        "template_id",
        "stage_id",
        string="Auto on Stages",
        help="When Encounter enters one of these stages, a checklist instance may be created (if automation is enabled in your process).",
    )
    procedure_category_ids = fields.Many2many(
        "clinic.procedure.category",
        "clinic_checklist_tmpl_proc_cat_rel",
        "template_id",
        "category_id",
        string="Procedure Categories",
        help="If set, recommend this template for procedures in these categories.",
    )

    # Kebijakan & kelulusan
    require_all_required = fields.Boolean(
        string="All Required Must Be Answered",
        default=True,
        help="If enabled, all required items must be answered to complete/pass the checklist.",
    )
    min_required = fields.Integer(
        string="Minimum Required Answered",
        default=0,
        help="Optional minimal number of required items that must be answered (in addition to scoring).",
    )
    pass_threshold_percent = fields.Float(
        string="Pass Threshold (%)",
        default=100.0,
        help="Checklist passes if score_percent >= threshold. Use 0 for no scoring threshold.",
    )
    require_signature_to_complete = fields.Boolean(
        string="Require Signature to Complete",
        help="If enabled, a signature on checklist instance is required to mark 'Done'.",
        default=False,
    )

    # Konten
    description = fields.Text(string="Description / Purpose")
    item_ids = fields.One2many("clinic.checklist.template.item", "template_id", string="Items")
    item_count = fields.Integer(compute="_compute_item_count", store=False)

    tag_ids = fields.Many2many("clinic.soap.tag", string="Tags")
    color = fields.Integer(string="Color Index")

    # Komputasi
    def _compute_item_count(self):
        for rec in self:
            rec.item_count = len(rec.item_ids)

    # ORM
    _constraint_uniq_template_code_company = models.Constraint(
        'unique(code, company_id)',
        'Template code must be unique per company.',
    )

    # Helpers
    def prepare_instance_vals(self, encounter=None, session=None, procedure=None, anesthesia=None,
                              consent=None, adverse=None, result=None):
        """Siapkan vals untuk membuat checklist instance dari template ini."""
        self.ensure_one()
        if not (encounter or session):
            raise UserError(_("Encounter or Session is required to prepare a checklist instance."))

        vals = {
            "template_id": self.id,
            "name": False,  # sequence on create
            "company_id": (encounter or session).company_id.id,
            "scope": self.scope,
            "encounter_id": encounter.id if encounter else (session.encounter_id.id if session else False),
            "session_id": session.id if session else False,
            "procedure_id": procedure.id if getattr(procedure, "id", False) else False,
            "anesthesia_case_id": anesthesia.id if getattr(anesthesia, "id", False) else False,
            "consent_id": consent.id if getattr(consent, "id", False) else False,
            "adverse_event_id": adverse.id if getattr(adverse, "id", False) else False,
            "result_id": result.id if getattr(result, "id", False) else False,
            "title": self.name,
            "require_all_required": self.require_all_required,
            "min_required": self.min_required,
            "pass_threshold_percent": self.pass_threshold_percent,
            "require_signature_to_complete": self.require_signature_to_complete,
        }
        return vals

    def action_open_instances(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_checklist").read()[0]
        action["domain"] = [("template_id", "=", self.id)]
        return action


class ClinicChecklistTemplateItem(models.Model):
    _name = "clinic.checklist.template.item"
    _description = "Checklist Template Item"
    _order = "template_id, sequence, id"
    _check_company_auto = True

    template_id = fields.Many2one("clinic.checklist.template", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", related="template_id.company_id", store=True, readonly=True)

    sequence = fields.Integer(default=10, index=True)
    name = fields.Char(required=True, translate=True, index=True)
    code = fields.Char(index=True)
    description = fields.Text(string="Instruction / Detail")

    # Tipe jawaban
    answer_type = fields.Selection(
        [
            ("yesno", "Yes/No"),
            ("select", "Select"),
            ("number", "Number"),
            ("text", "Text"),
            ("date", "Date"),
            ("datetime", "Datetime"),
            ("signature", "Signature"),
            ("attachment", "Attachment"),
        ],
        string="Answer Type",
        required=True,
        default="yesno",
        index=True,
    )
    required = fields.Boolean(default=True, help="Must be answered if required.")
    allow_na = fields.Boolean(string="Allow N/A", default=False)
    weight = fields.Float(
        string="Weight",
        default=1.0,
        help="Item weight in scoring. For yes/no: Yes=weight (score), No=0 by default. For select: see options. For number: compared with ranges.",
    )

    # Untuk validasi/penilaian numeric/text
    min_value = fields.Float(string="Min Value", help="Minimum acceptable numeric value (for number type).")
    max_value = fields.Float(string="Max Value", help="Maximum acceptable numeric value (for number type).")
    regex = fields.Char(string="Text Pattern (regex)", help="Optional regex to validate text value.")

    option_ids = fields.One2many("clinic.checklist.template.item.option", "item_id", string="Options (for Select)")
    guidance = fields.Char(string="Guidance / Hint")

    color = fields.Integer(string="Color Index")

    _constraint_name_not_empty = models.Constraint(
        "CHECK (char_length(coalesce(name, '')) > 0)",
        'Item must have a name.',
    )


class ClinicChecklistTemplateItemOption(models.Model):
    _name = "clinic.checklist.template.item.option"
    _description = "Checklist Template Item Option"
    _order = "item_id, sequence, id"
    _check_company_auto = True

    item_id = fields.Many2one("clinic.checklist.template.item", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", related="item_id.company_id", store=True, readonly=True)

    sequence = fields.Integer(default=10, index=True)
    code = fields.Char(string="Code", index=True)
    name = fields.Char(string="Label", required=True, translate=True)
    score = fields.Float(string="Score", default=0.0, help="Score awarded if this option is selected.")
    is_pass = fields.Boolean(string="Pass?", default=True, help="If unchecked, selecting this option will fail the item.")
    note = fields.Char(string="Note")


# =============================================================================
# INSTANCE: Checklist yang diisi
# =============================================================================
class ClinicChecklist(models.Model):
    _name = "clinic.checklist"
    _description = "Checklist"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_done desc, id desc"
    _check_company_auto = True

    # Identitas & perusahaan
    name = fields.Char(
        string="Checklist #",
        required=True,
        copy=False,
        default=lambda s: _("New"),
        index=True,
        tracking=True,
    )
    title = fields.Char(string="Title")
    active = fields.Boolean(default=True, tracking=True)

    company_id = fields.Many2one("res.company", required=True, default=lambda s: s.env.company, index=True)
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", store=True, readonly=True)

    # Konteks klinis
    template_id = fields.Many2one("clinic.checklist.template", string="Template", ondelete="set null", index=True)
    scope = fields.Selection(related="template_id.scope", store=True, readonly=False)

    encounter_id = fields.Many2one("clinic.encounter", required=True, ondelete="cascade", index=True, tracking=True)
    session_id = fields.Many2one("clinic.procedure.session", ondelete="set null", index=True)
    procedure_id = fields.Many2one("clinic.procedure.catalog", ondelete="set null", index=True)
    anesthesia_case_id = fields.Many2one("clinic.anesthesia.case", ondelete="set null", index=True)
    consent_id = fields.Many2one("clinic.consent.document", ondelete="set null", index=True)
    adverse_event_id = fields.Many2one("clinic.adverse.event", ondelete="set null", index=True)
    result_id = fields.Many2one("clinic.result.document", ondelete="set null", index=True)

    patient_id = fields.Many2one("clinic.patient", related="encounter_id.patient_id", store=True, readonly=True, index=True)
    partner_id = fields.Many2one("res.partner", related="patient_id.partner_id", store=True, readonly=True)

    # Workflow & waktu
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        index=True,
        tracking=True,
    )
    started_by_id = fields.Many2one("res.users", string="Started By", index=True)
    date_start = fields.Datetime(string="Started On", tracking=True)
    date_done = fields.Datetime(string="Completed On", tracking=True)

    # Tanda tangan/otorisasi checklist instance
    signed_by = fields.Char(string="Signed By")
    signature = fields.Binary(string="Signature", attachment=True)
    signature_note = fields.Char(string="Signature Note")

    # Kebijakan kelulusan (snapshot dari template saat create)
    require_all_required = fields.Boolean(default=True)
    min_required = fields.Integer(default=0)
    pass_threshold_percent = fields.Float(default=100.0)
    require_signature_to_complete = fields.Boolean(default=False)

    # Nilai & kelulusan
    line_ids = fields.One2many("clinic.checklist.item", "checklist_id", string="Items")
    completed_required = fields.Integer(string="Required Answered", compute="_compute_progress", store=True)
    total_required = fields.Integer(string="Required Items", compute="_compute_progress", store=True)
    percent_complete = fields.Float(string="% Complete", compute="_compute_progress", store=True)
    score_total = fields.Float(string="Score", compute="_compute_score", store=True)
    score_max = fields.Float(string="Max Score", compute="_compute_score", store=True)
    score_percent = fields.Float(string="Score %", compute="_compute_score", store=True)
    passed = fields.Boolean(string="Passed?", compute="_compute_score", store=True)
    required_ok = fields.Boolean(string="All Required OK?", compute="_compute_progress", store=True)

    tag_ids = fields.Many2many("clinic.soap.tag", string="Tags")
    color = fields.Integer(string="Color Index")
    note_internal = fields.Text(string="Internal Notes")

    # -------------------------------------------------------------------------
    # Komputasi
    # -------------------------------------------------------------------------
    @api.depends("line_ids", "line_ids.required", "line_ids.answered", "line_ids.is_passed")
    def _compute_progress(self):
        for rec in self:
            req_lines = rec.line_ids.filtered(lambda l: l.required)
            ans_req = req_lines.filtered(lambda l: l.answered)
            rec.total_required = len(req_lines)
            rec.completed_required = len(ans_req)
            rec.required_ok = (rec.completed_required >= (rec.min_required or 0)) and (
                (not rec.require_all_required) or (rec.completed_required == rec.total_required)
            )
            total = len(rec.line_ids)
            done = len(rec.line_ids.filtered(lambda l: l.answered))
            rec.percent_complete = (100.0 * done / total) if total else 0.0

    @api.depends(
        "line_ids.score_value",
        "line_ids.score_max",
        "pass_threshold_percent",
        "required_ok",
    )
    def _compute_score(self):
        for rec in self:
            rec.score_total = sum(l.score_value for l in rec.line_ids)
            rec.score_max = sum(l.score_max for l in rec.line_ids)
            rec.score_percent = (100.0 * rec.score_total / rec.score_max) if rec.score_max else 0.0
            # Lulus jika: syarat required_ok terpenuhi & persentase di atas threshold (atau threshold 0)
            pass_threshold = rec.pass_threshold_percent or 0.0
            rec.passed = bool(rec.required_ok and (rec.score_percent >= pass_threshold))

    # -------------------------------------------------------------------------
    # Onchange
    # -------------------------------------------------------------------------
    @api.onchange("template_id")
    def _onchange_template(self):
        tmpl = self.template_id
        if not tmpl:
            return
        vals = {
            "title": tmpl.name if not self.title else self.title,
            "require_all_required": tmpl.require_all_required,
            "min_required": tmpl.min_required,
            "pass_threshold_percent": tmpl.pass_threshold_percent,
            "require_signature_to_complete": tmpl.require_signature_to_complete,
        }
        # Prefill procedure dari session jika kosong
        if self.session_id and self.session_id.procedure_id and not self.procedure_id:
            vals["procedure_id"] = self.session_id.procedure_id.id
        self.update(vals)

    # -------------------------------------------------------------------------
    # Constraints & ORM
    # -------------------------------------------------------------------------
    _constraint_uniq_checklist_name_company = models.Constraint(
        'unique(name, company_id)',
        'Checklist number must be unique per company.',
    )

    @api.constrains("company_id", "encounter_id")
    def _check_company_consistency(self):
        for rec in self:
            if rec.encounter_id and rec.company_id and rec.company_id != rec.encounter_id.company_id:
                raise ValidationError(_("Checklist company must match Encounter company."))

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        recs_to_init_lines = []
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if vals.get("name", _("New")) in (False, _("New")):
                vals["name"] = seq.next_by_code("clinic.checklist") or _("New")
            # Wajib encounter_id; fallback dari session_id bila ada
            if not vals.get("encounter_id") and vals.get("session_id"):
                sess = self.env["clinic.procedure.session"].browse(vals["session_id"])
                if sess and sess.encounter_id:
                    vals["encounter_id"] = sess.encounter_id.id
            recs_to_init_lines.append(vals)
        recs = super().create(recs_to_init_lines)
        # Clone item dari template
        for rec in recs:
            if rec.template_id:
                rec._instantiate_from_template()
            # Activity
            try:
                rec.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Complete checklist"),
                    user_id=rec.encounter_id.user_id.id if rec.encounter_id and rec.encounter_id.user_id else self.env.user.id,
                    date_deadline=fields.Date.today(),
                )
            except Exception:
                pass
        return recs

    def write(self, vals):
        # Cegah penggantian template setelah ada jawaban
        if "template_id" in vals:
            for rec in self:
                if rec.line_ids.filtered(lambda l: l.answered):
                    raise UserError(_("Cannot change template after answers exist."))
        return super().write(vals)

    # -------------------------------------------------------------------------
    # Helper & Workflow
    # -------------------------------------------------------------------------
    def _instantiate_from_template(self):
        """Clone items from template to lines (snapshot minimal)."""
        self.ensure_one()
        if not self.template_id:
            return
        Item = self.env["clinic.checklist.item"]
        vals_list = []
        for i, it in enumerate(self.template_id.item_ids.sorted(lambda r: r.sequence)):
            vals_list.append({
                "checklist_id": self.id,
                "template_item_id": it.id,
                "sequence": (it.sequence or 10) + i,
                "name": it.name,
                "description": it.description,
                "answer_type": it.answer_type,
                "required": it.required,
                "allow_na": it.allow_na,
                "weight": it.weight,
                "min_value": it.min_value,
                "max_value": it.max_value,
                "regex": it.regex,
                "guidance": it.guidance,
                "score_max": self._default_item_score_max(it),
            })
        if vals_list:
            Item.create(vals_list)

    def _default_item_score_max(self, tmpl_item):
        """Tentukan skor maksimal per item berdasarkan template."""
        if tmpl_item.answer_type == "yesno":
            return max(tmpl_item.weight or 0.0, 0.0)
        elif tmpl_item.answer_type == "select":
            # maksimum dari opsi
            return max([opt.score or 0.0 for opt in tmpl_item.option_ids] or [0.0])
        elif tmpl_item.answer_type == "number":
            # jika ada range, skenario sederhana: skor penuh bila di dalam range
            return max(tmpl_item.weight or 0.0, 0.0)
        elif tmpl_item.answer_type in ("text", "date", "datetime", "signature", "attachment"):
            # skor penuh bila dijawab (untuk text/date/...), kecuali logika tambahan di item
            return max(tmpl_item.weight or 0.0, 0.0)
        return 0.0

    def action_start(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.write({"state": "in_progress", "date_start": rec.date_start or now, "started_by_id": rec.started_by_id.id or rec.env.user.id})
        return True

    def _validate_completion(self):
        self.ensure_one()
        # Signature required?
        if self.require_signature_to_complete and not self.signature:
            raise UserError(_("Signature is required to complete this checklist."))
        # Required answers?
        if self.require_all_required:
            missing = self.line_ids.filtered(lambda l: l.required and not l.answered)
            if missing:
                raise UserError(_("Please answer all required items before completion."))
        # Min required count?
        if self.min_required and self.completed_required < self.min_required:
            raise UserError(_("Minimum required answered items is %s.") % int(self.min_required))
        # Pass threshold?
        if (self.pass_threshold_percent or 0.0) > 0.0 and not self.passed:
            raise UserError(_("Checklist has not met the pass threshold (%s%%).") % self.pass_threshold_percent)

    def action_done(self):
        now = fields.Datetime.now()
        for rec in self:
            rec._validate_completion()
            rec.write({"state": "done", "date_done": rec.date_done or now})
            # Follow-up ke Encounter owner
            try:
                rec.encounter_id.push_activity_followup(
                    summary=_("Checklist completed"),
                    days=0,
                    user=rec.encounter_id.user_id or self.env.user,
                )
            except Exception:
                pass
        return True

    def action_cancel(self, reason=None):
        for rec in self:
            rec.write({"state": "cancelled"})
            if reason:
                rec.message_post(body=_("Checklist cancelled: %s") % reason)
        return True

    # Kepatuhan untuk preflight session
    def is_compliant_for_session(self, session):
        """True jika checklist sudah 'done' & passed untuk session terkait."""
        self.ensure_one()
        if not session or session._name != "clinic.procedure.session":
            return False
        return bool(self.state == "done" and self.passed and self.session_id.id == session.id)

    # Actions
    def action_open_encounter(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_encounter").read()[0]
        action["res_id"] = self.encounter_id.id
        action["domain"] = [("id", "=", self.encounter_id.id)]
        action["view_mode"] = "form"
        return action

    def action_open_session(self):
        self.ensure_one()
        if not self.session_id:
            raise UserError(_("This checklist is not linked to a session."))
        action = self.env.ref("clinic_encounter.action_clinic_procedure_session").read()[0]
        action["res_id"] = self.session_id.id
        action["domain"] = [("id", "=", self.session_id.id)]
        action["view_mode"] = "form"
        return action


class ClinicChecklistItem(models.Model):
    _name = "clinic.checklist.item"
    _description = "Checklist Item"
    _order = "checklist_id, sequence, id"
    _check_company_auto = True

    checklist_id = fields.Many2one("clinic.checklist", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", related="checklist_id.company_id", store=True, readonly=True)
    template_item_id = fields.Many2one("clinic.checklist.template.item", ondelete="set null", index=True)

    sequence = fields.Integer(default=10, index=True)
    name = fields.Char(required=True, translate=True)
    description = fields.Text(string="Instruction / Detail")
    guidance = fields.Char(string="Guidance / Hint")

    answer_type = fields.Selection(related="template_item_id.answer_type", store=True, readonly=False)
    required = fields.Boolean(default=True)
    allow_na = fields.Boolean(default=False)
    weight = fields.Float(default=1.0)

    # Kriteria numeric/text
    min_value = fields.Float()
    max_value = fields.Float()
    regex = fields.Char()

    # Jawaban
    is_na = fields.Boolean(string="N/A")
    value_bool = fields.Boolean(string="Yes?")
    value_select_id = fields.Many2one(
        "clinic.checklist.template.item.option",
        string="Selected Option",
        ondelete="set null",
        domain="[('item_id', '=', template_item_id)]",
    )
    value_number = fields.Float(string="Number", digits=(16, 4))
    value_text = fields.Char(string="Text Value")
    value_date = fields.Date(string="Date")
    value_datetime = fields.Datetime(string="Datetime")
    value_attachment_ids = fields.Many2many(
        "ir.attachment",
        "clinic_checklist_item_attach_rel",
        "item_id",
        "attachment_id",
        string="Attachments",
    )
    value_signature = fields.Binary(string="Signature", attachment=True)

    answered = fields.Boolean(string="Answered?", compute="_compute_answered_and_score", store=True)
    is_passed = fields.Boolean(string="Item Passed?", compute="_compute_answered_and_score", store=True)

    score_value = fields.Float(string="Score", compute="_compute_answered_and_score", store=True)
    score_max = fields.Float(string="Score Max", default=0.0)

    color = fields.Integer(string="Color Index")

    # Komputasi
    @api.depends(
        "answer_type", "is_na", "required",
        "value_bool", "value_select_id", "value_number", "value_text",
        "value_date", "value_datetime", "value_attachment_ids", "value_signature",
        "weight", "min_value", "max_value",
    )
    def _compute_answered_and_score(self):
        for rec in self:
            answered = False
            passed = True
            score = 0.0
            # NA
            if rec.is_na and rec.allow_na:
                answered = True
                passed = True
                score = rec.weight or 0.0  # NA treated as neutral/full or 0? Kita beri full agar tidak menghukum
            else:
                t = rec.answer_type
                if t == "yesno":
                    answered = rec.value_bool in (True, False)  # boolean default False counts as answered
                    # Konvensi: Yes -> skor & pass, No -> skor 0 & fail
                    if answered:
                        if rec.value_bool:
                            score = rec.weight or 0.0
                            passed = True
                        else:
                            score = 0.0
                            passed = False if rec.required else True
                elif t == "select":
                    answered = bool(rec.value_select_id)
                    if answered:
                        score = rec.value_select_id.score or 0.0
                        passed = bool(rec.value_select_id.is_pass)
                    else:
                        passed = False if rec.required else True
                elif t == "number":
                    answered = rec.value_number is not None
                    if answered:
                        # skor penuh bila di dalam range; jika tidak ada range → skor penuh
                        in_range = True
                        if rec.min_value not in (None, False):
                            in_range = in_range and rec.value_number >= rec.min_value
                        if rec.max_value not in (None, False):
                            in_range = in_range and rec.value_number <= rec.max_value
                        passed = in_range
                        score = (rec.weight or 0.0) if in_range else 0.0
                    else:
                        passed = False if rec.required else True
                elif t == "text":
                    answered = bool(rec.value_text)
                    if answered:
                        ok = True
                        if rec.regex:
                            import re
                            try:
                                if not re.search(rec.regex, rec.value_text or ""):
                                    ok = False
                            except Exception:
                                # regex invalid: jangan blokir, anggap ok
                                ok = True
                        passed = ok
                        score = (rec.weight or 0.0) if ok else 0.0
                    else:
                        passed = False if rec.required else True
                elif t == "date":
                    answered = bool(rec.value_date)
                    passed = True if answered else (False if rec.required else True)
                    score = (rec.weight or 0.0) if answered else 0.0
                elif t == "datetime":
                    answered = bool(rec.value_datetime)
                    passed = True if answered else (False if rec.required else True)
                    score = (rec.weight or 0.0) if answered else 0.0
                elif t == "signature":
                    answered = bool(rec.value_signature)
                    passed = True if answered else (False if rec.required else True)
                    score = (rec.weight or 0.0) if answered else 0.0
                elif t == "attachment":
                    answered = bool(rec.value_attachment_ids)
                    passed = True if answered else (False if rec.required else True)
                    score = (rec.weight or 0.0) if answered else 0.0
                else:
                    answered = False
                    passed = False if rec.required else True

            rec.answered = answered
            rec.is_passed = passed
            rec.score_value = score

    # Constraint
    _constraint_name_not_empty = models.Constraint(
        "CHECK (char_length(coalesce(name, '')) > 0)",
        'Checklist item must have a name.',
    )


# =============================================================================
# Bridges: Encounter / Session
# =============================================================================
# class ClinicEncounter_Checklist(models.Model):
#     _inherit = "clinic.encounter"

#     checklist_ids = fields.One2many("clinic.checklist", "encounter_id", string="Checklists")
#     checklist_count = fields.Integer(compute="_compute_checklist_count", string="Checklists", store=False)

#     def _compute_checklist_count(self):
#         for rec in self:
#             rec.checklist_count = len(rec.checklist_ids)

#     def action_open_checklists(self):
#         self.ensure_one()
#         action = self.env.ref("clinic_encounter.action_clinic_checklist").read()[0]
#         action["domain"] = [("encounter_id", "=", self.id)]
#         action["context"] = {"default_encounter_id": self.id}
#         return action


# class ClinicProcedureSession_Checklist(models.Model):
#     _inherit = "clinic.procedure.session"

    # checklist_ids = fields.One2many("clinic.checklist", "session_id", string="Checklists")
    # checklist_count = fields.Integer(compute="_compute_checklist_count", string="Checklists", store=False)
    # checklist_compliant = fields.Boolean(
    #     string="Checklist Compliant",
    #     compute="_compute_checklist_compliant",
    #     store=False,
    #     help="True if there exists at least one DONE & PASSED checklist linked to this session.",
    # )

    # def _compute_checklist_count(self):
    #     for rec in self:
    #         rec.checklist_count = len(rec.checklist_ids)

    # @api.depends("checklist_ids.state", "checklist_ids.passed")
    # def _compute_checklist_compliant(self):
    #     for rec in self:
    #         ok = any(cl.state == "done" and cl.passed for cl in rec.checklist_ids)
    #         rec.checklist_compliant = ok

    # def action_open_checklists(self):
    #     self.ensure_one()
    #     action = self.env.ref("clinic_encounter.action_clinic_checklist").read()[0]
    #     action["domain"] = [("session_id", "=", self.id)]
    #     action["context"] = {
    #         "default_session_id": self.id,
    #         "default_encounter_id": self.encounter_id.id,
    #         "default_procedure_id": self.procedure_id.id if self.procedure_id else False,
    #     }
    #     return action

    # def action_create_checklist_from_template(self, template):
    #     """
    #     Helper: buat satu checklist instance untuk session dari template tertentu.
    #     """
    #     self.ensure_one()
    #     if not template or template._name != "clinic.checklist.template":
    #         raise UserError(_("A Checklist Template is required."))
    #     vals = template.prepare_instance_vals(
    #         encounter=self.encounter_id, session=self, procedure=self.procedure_id
    #     )
    #     cl = self.env["clinic.checklist"].create(vals)
    #     return {
    #         "type": "ir.actions.act_window",
    #         "name": _("Checklist"),
    #         "res_model": "clinic.checklist",
    #         "res_id": cl.id,
    #         "view_mode": "form",
    #     }

    # # Perkuat preflight session start agar memeriksa checklist bila diwajibkan
    # def _preflight_start_checks(self):
    #     res = super()._preflight_start_checks()
    #     for rec in self:
    #         if rec.require_checklist:
    #             # Lolos jika ada minimal satu checklist DONE & PASSED untuk session ini
    #             ok = any(cl.state == "done" and cl.passed for cl in rec.checklist_ids)
    #             if not ok:
    #                 raise UserError(_("Checklist is required before starting this session. Please complete the required checklist."))
    #     return res



# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/anesthesia.py
#
# Fitur utama:
# - Anesthesia Case (pra → intra → pasca/PACU) terhubung Encounter/Session/Procedure.
# - Preop assessment (ASA, Mallampati, airway), checklist, consent indicator.
# - Intraop timeline: obat, vital signs berkala, airway events, cairan (in/out), estimasi perdarahan.
# - Postop: Aldrete score, nyeri, PONV, komplikasi, readiness discharge.
# - Durasi, net fluid balance, indikator abnormal; workflow start/pause/resume/done/cancel.
# - Billing bridge: per-case / per-time (unit menit) / no-bill.
# - Interop: memanfaatkan Execution Log (jika Session tersedia) & Result Document (opsional).
#
import math
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =============================================================================
# Header: Anesthesia Case
# =============================================================================
class ClinicAnesthesiaCase(models.Model):
    _name = "clinic.anesthesia.case"
    _description = "Anesthesia Case"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identitas & Konteks
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Anesthesia #",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        index=True,
        tracking=True,
    )
    active = fields.Boolean(default=True, tracking=True)

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Encounter",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    session_id = fields.Many2one(
        "clinic.procedure.session",
        string="Procedure Session",
        ondelete="set null",
        index=True,
        help="If linked to a specific surgical/operative session.",
    )
    procedure_id = fields.Many2one(
        "clinic.procedure.catalog",
        string="Procedure",
        ondelete="set null",
        index=True,
    )
    diagnosis_id = fields.Many2one("clinic.diagnosis", string="Diagnosis", ondelete="set null", index=True)

    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        related="encounter_id.patient_id",
        store=True,
        readonly=True,
        index=True,
    )
    partner_id = fields.Many2one("res.partner", related="patient_id.partner_id", store=True, readonly=True)
    doctor_id = fields.Many2one("clinic.doctor", string="Responsible Surgeon/Doctor", related="encounter_id.doctor_id", store=True, readonly=True)
    anesthetist_id = fields.Many2one("clinic.doctor", string="Anesthetist", index=True, tracking=True)
    performer_user_id = fields.Many2one("res.users", string="Operator (User)", default=lambda s: s.env.user)
    room_id = fields.Many2one("clinic.room", string="Room/OR")

    # Consent awareness (read-only indikator dari encounter/session)
    consent_required = fields.Boolean(
        string="Consent Required",
        compute="_compute_consent_required",
        store=True,
        help="Derived from procedure template/policy; start will be blocked if not valid.",
    )
    consent_ok = fields.Boolean(
        string="Consent OK",
        compute="_compute_consent_ok",
        store=True,
        help="Encounter-level consent validity indicator.",
    )

    # -------------------------------------------------------------------------
    # Waktu & Status
    # -------------------------------------------------------------------------
    planned_start = fields.Datetime(string="Planned Start")
    planned_end = fields.Datetime(string="Planned End")

    date_start = fields.Datetime(string="Start", tracking=True)
    date_end = fields.Datetime(string="End", tracking=True)
    anesthesia_duration_min = fields.Float(
        string="Duration (min)",
        compute="_compute_duration",
        store=True,
        help="End - Start in minutes.",
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("paused", "Paused"),
            ("done", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
    )

    # -------------------------------------------------------------------------
    # PREOP — Assessment & Checklist
    # -------------------------------------------------------------------------
    asa_class = fields.Selection(
        [
            ("1", "ASA I"),
            ("2", "ASA II"),
            ("3", "ASA III"),
            ("4", "ASA IV"),
            ("5", "ASA V"),
            ("6", "ASA VI"),
        ],
        string="ASA Class",
        index=True,
        help="American Society of Anesthesiologists physical status classification.",
    )
    asa_emergency = fields.Boolean(string="Emergency (E)", help="Append E for emergency cases.")
    mallampati = fields.Selection(
        [("1", "I"), ("2", "II"), ("3", "III"), ("4", "IV")],
        string="Mallampati Score",
        help="Oropharyngeal view classification.",
    )
    airway_difficult_predicted = fields.Boolean(string="Predicted Difficult Airway")
    airway_findings = fields.Char(string="Airway Notes")
    thyromental_distance_cm = fields.Float(string="Thyromental Distance (cm)")
    mouth_opening_cm = fields.Float(string="Mouth Opening (cm)")
    neck_mobility = fields.Selection(
        [("normal", "Normal"), ("limited", "Limited")],
        string="Neck Mobility",
    )
    allergies = fields.Text(string="Allergies")
    fasting_since = fields.Datetime(string="Fasting Since")
    preop_checklist_ok = fields.Boolean(string="Preop Checklist OK")
    preop_notes = fields.Text(string="Preoperative Notes")

    # -------------------------------------------------------------------------
    # TEKNIK — Plan & Technique
    # -------------------------------------------------------------------------
    anesthesia_type = fields.Selection(
        [
            ("general", "General"),
            ("regional", "Regional"),
            ("neuraxial", "Neuraxial (Spinal/Epidural)"),
            ("sedation", "Monitored Anesthesia Care/ Sedation"),
            ("local", "Local"),
            ("combined", "Combined"),
        ],
        string="Anesthesia Type",
        index=True,
    )
    technique_notes = fields.Text(string="Technique Notes")
    airway_device = fields.Selection(
        [
            ("mask", "Face Mask"),
            ("lma", "Laryngeal Mask Airway"),
            ("ett", "Endotracheal Tube"),
            ("trach", "Tracheostomy"),
            ("none", "None / Nasal Cannula"),
        ],
        string="Airway Device (Primary)",
    )
    airway_device_size = fields.Char(string="Device Size")
    laryngoscopy_grade = fields.Selection(
        [("1", "Cormack-Lehane I"), ("2", "II"), ("3", "III"), ("4", "IV")],
        string="Laryngoscopy Grade",
        help="Worst grade during intubation.",
    )
    intubation_attempts = fields.Integer(string="Intubation Attempts")
    intubation_success = fields.Boolean(string="Intubation Successful")

    # -------------------------------------------------------------------------
    # INTRAOP — Lines
    # -------------------------------------------------------------------------
    medication_ids = fields.One2many("clinic.anesthesia.medication", "case_id", string="Medications")
    vital_ids = fields.One2many("clinic.anesthesia.vital", "case_id", string="Vitals Timeline")
    fluid_ids = fields.One2many("clinic.anesthesia.fluid", "case_id", string="Fluids In/Out")
    airway_ids = fields.One2many("clinic.anesthesia.airway", "case_id", string="Airway Events")
    event_ids = fields.One2many("clinic.anesthesia.event", "case_id", string="Intraop Events/Notes")

    total_fluid_in_ml = fields.Float(string="Total In (ml)", compute="_compute_fluid_totals", store=True)
    total_fluid_out_ml = fields.Float(string="Total Out (ml)", compute="_compute_fluid_totals", store=True)
    net_fluid_balance_ml = fields.Float(string="Net Balance (ml)", compute="_compute_fluid_totals", store=True)
    total_blood_loss_ml = fields.Float(string="Total Blood Loss (ml)", compute="_compute_fluid_totals", store=True)
    total_urine_ml = fields.Float(string="Urine Output (ml)", compute="_compute_fluid_totals", store=True)

    intraop_complication = fields.Boolean(string="Any Intraop Complication?")
    intraop_complication_note = fields.Text(string="Complication Details")

    # -------------------------------------------------------------------------
    # POSTOP / PACU
    # -------------------------------------------------------------------------
    pain_scale = fields.Selection([(str(i), str(i)) for i in range(0, 11)], string="Pain Scale (0–10)")
    nausea_vomiting = fields.Selection(
        [("none", "None"), ("mild", "Mild"), ("moderate", "Moderate"), ("severe", "Severe")],
        string="Nausea/Vomiting",
    )
    rass_score = fields.Integer(string="RASS (−5..+4)", help="Richmond Agitation-Sedation Scale")
    aldrete_activity = fields.Selection([("0", "0"), ("1", "1"), ("2", "2")], string="Aldrete: Activity", default="2")
    aldrete_respiration = fields.Selection([("0", "0"), ("1", "1"), ("2", "2")], string="Aldrete: Respiration", default="2")
    aldrete_circulation = fields.Selection([("0", "0"), ("1", "1"), ("2", "2")], string="Aldrete: Circulation", default="2")
    aldrete_consciousness = fields.Selection([("0", "0"), ("1", "1"), ("2", "2")], string="Aldrete: Consciousness", default="2")
    aldrete_color = fields.Selection([("0", "0"), ("1", "1"), ("2", "2")], string="Aldrete: O2 Sat/Color", default="2")
    aldrete_total = fields.Integer(string="Aldrete Total", compute="_compute_aldrete", store=True)
    ready_for_discharge = fields.Boolean(string="Ready for Discharge")

    postop_complication = fields.Boolean(string="Any Postop Complication?")
    postop_complication_note = fields.Text(string="Postop Complication Details")

    # -------------------------------------------------------------------------
    # Billing (soft-coupled)
    # -------------------------------------------------------------------------
    billing_policy = fields.Selection(
        [
            ("per_case", "Bill per Case"),
            ("per_time", "Bill by Time Unit"),
            ("no_bill", "Do Not Bill"),
        ],
        string="Billing Policy",
        default="per_case",
        help="Control how invoice lines are prepared for this anesthesia case.",
    )
    product_case_id = fields.Many2one("product.product", string="Product (Case)")
    product_time_id = fields.Many2one("product.product", string="Product (Time Unit)")
    time_unit_minutes = fields.Integer(string="Time Unit (min)", default=15)
    base_units = fields.Integer(string="Base Units", default=0, help="Optional fixed units billed per case (anesthesia base units).")
    invoice_line_ids = fields.Many2many(
        "account.move.line",
        "clinic_anesthesia_invoice_line_rel",
        "case_id",
        "aml_id",
        string="Invoice Lines",
        help="Billing lines associated with this anesthesia case.",
    )
    invoice_count = fields.Integer(string="Invoices", compute="_compute_invoice_count", store=False)

    # UI
    tag_ids = fields.Many2many("clinic.soap.tag", string="Tags")
    color = fields.Integer(string="Color Index")
    note_internal = fields.Text(string="Internal Notes")

    # -------------------------------------------------------------------------
    # Compute
    # -------------------------------------------------------------------------
    @api.depends("procedure_id.require_consent", "session_id", "session_id.require_consent")
    def _compute_consent_required(self):
        for rec in self:
            # Prioritaskan policy dari procedure catalog atau session
            need = False
            if rec.session_id and rec.session_id.require_consent:
                need = True
            elif rec.procedure_id and rec.procedure_id.require_consent:
                need = True
            rec.consent_required = need

    @api.depends("encounter_id.consent_ok")
    def _compute_consent_ok(self):
        for rec in self:
            rec.consent_ok = bool(rec.encounter_id and rec.encounter_id.consent_ok)

    @api.depends("date_start", "date_end")
    def _compute_duration(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end >= rec.date_start:
                delta = rec.date_end - rec.date_start
                rec.anesthesia_duration_min = delta.total_seconds() / 60.0
            else:
                rec.anesthesia_duration_min = 0.0

    @api.depends(
        "fluid_ids.direction",
        "fluid_ids.volume_ml",
        "fluid_ids.is_blood_loss",
        "fluid_ids.is_urine"
    )
    def _compute_fluid_totals(self):
        for rec in self:
            ins = sum(l.volume_ml for l in rec.fluid_ids.filtered(lambda x: x.direction == "in"))
            outs = sum(l.volume_ml for l in rec.fluid_ids.filtered(lambda x: x.direction == "out"))
            blood = sum(l.volume_ml for l in rec.fluid_ids.filtered(lambda x: x.is_blood_loss))
            urine = sum(l.volume_ml for l in rec.fluid_ids.filtered(lambda x: x.is_urine))
            rec.total_fluid_in_ml = ins
            rec.total_fluid_out_ml = outs
            rec.net_fluid_balance_ml = ins - outs
            rec.total_blood_loss_ml = blood
            rec.total_urine_ml = urine

    @api.depends(
        "aldrete_activity",
        "aldrete_respiration",
        "aldrete_circulation",
        "aldrete_consciousness",
        "aldrete_color",
    )
    def _compute_aldrete(self):
        for rec in self:
            def v(x): return int(x or 0)
            rec.aldrete_total = v(rec.aldrete_activity) + v(rec.aldrete_respiration) + v(rec.aldrete_circulation) + v(rec.aldrete_consciousness) + v(rec.aldrete_color)

    def _compute_invoice_count(self):
        AccountMove = self.env["account.move"]
        for rec in self:
            moves = AccountMove.search([
                ("line_ids", "in", rec.invoice_line_ids.ids or [0]),
                ("company_id", "=", rec.company_id.id),
                ("move_type", "in", ["out_invoice", "out_refund"]),
            ])
            rec.invoice_count = len(moves)

    # -------------------------------------------------------------------------
    # Onchange
    # -------------------------------------------------------------------------
    @api.onchange("session_id")
    def _onchange_session(self):
        sess = self.session_id
        if not sess:
            return
        vals = {}
        if sess.procedure_id and not self.procedure_id:
            vals["procedure_id"] = sess.procedure_id.id
        if sess.room_id and not self.room_id:
            vals["room_id"] = sess.room_id.id
        if sess.performer_doctor_id and not self.anesthetist_id:
            # Jika modul anesthetist terpisah tidak ada, gunakan field doctor umum
            vals["anesthetist_id"] = sess.performer_doctor_id.id
        if sess.diagnosis_id and not self.diagnosis_id:
            vals["diagnosis_id"] = sess.diagnosis_id.id
        self.update(vals)

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    _constraint_uniq_anesthesia_name_company = models.Constraint(
        'unique(name, company_id)',
        'Anesthesia number must be unique per company.',
    )
    _constraint_check_time_unit = models.Constraint(
        'CHECK (time_unit_minutes > 0)',
        'Time unit must be positive.',
    )

    @api.constrains("company_id", "encounter_id")
    def _check_company_consistency(self):
        for rec in self:
            if rec.encounter_id and rec.company_id and rec.company_id != rec.encounter_id.company_id:
                raise ValidationError(_("Anesthesia company must match Encounter company."))

    @api.constrains("planned_start", "planned_end")
    def _check_planned_window(self):
        for rec in self:
            if rec.planned_start and rec.planned_end and rec.planned_end < rec.planned_start:
                raise ValidationError(_("Planned End cannot be earlier than Planned Start."))

    @api.constrains("date_start", "date_end")
    def _check_actual_window(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_("End cannot be earlier than Start."))

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if vals.get("name", _("New")) in (False, _("New")):
                vals["name"] = seq.next_by_code("clinic.anesthesia.case") or _("New")
            # Backfill encounter dari session bila perlu
            if not vals.get("encounter_id") and vals.get("session_id"):
                sess = self.env["clinic.procedure.session"].browse(vals["session_id"])
                if sess and sess.encounter_id:
                    vals["encounter_id"] = sess.encounter_id.id
        recs = super().create(vals_list)
        # Activity default
        for rec in recs:
            try:
                rec.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Prepare anesthesia preop assessment"),
                    user_id=rec.performer_user_id.id or self.env.user.id,
                    date_deadline=fields.Date.today(),
                )
            except Exception:
                pass
        return recs

    # -------------------------------------------------------------------------
    # Workflow
    # -------------------------------------------------------------------------
    def _preflight_start(self):
        for rec in self:
            if rec.consent_required and not rec.consent_ok:
                raise UserError(_("Consent is required before starting anesthesia."))
            if rec.asa_class in (False, None):
                rec.message_post(body=_("Starting without ASA classification."))

    def action_start(self):
        self._preflight_start()
        now = fields.Datetime.now()
        for rec in self:
            updates = {"state": "in_progress"}
            if not rec.date_start:
                updates["date_start"] = now
            rec.write(updates)
            # Log ke execution log (jika punya session)
            try:
                if rec.session_id:
                    rec.session_id._log_event("note", message=_("Anesthesia started"), role="performer")
            except Exception:
                pass
        return True

    def action_pause(self, reason=None):
        for rec in self:
            if rec.state != "in_progress":
                raise UserError(_("Only 'In Progress' case can be paused."))
            rec.write({"state": "paused"})
            if reason:
                rec.message_post(body=_("Paused: %s") % reason)
        return True

    def action_resume(self):
        for rec in self:
            if rec.state != "paused":
                raise UserError(_("Only 'Paused' case can be resumed."))
            rec.write({"state": "in_progress"})
        return True

    def action_done(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.state not in ("in_progress", "paused", "draft"):
                raise UserError(_("Only Draft/In Progress/Paused case can be completed."))
            updates = {"state": "done"}
            if not rec.date_start:
                updates["date_start"] = now
            if not rec.date_end:
                updates["date_end"] = now
            rec.write(updates)
            # Tandai session done bila relevan (tidak memaksa)
            try:
                if rec.session_id and rec.session_id.state not in ("done", "cancelled"):
                    rec.session_id.action_done()
            except Exception:
                pass
            # Follow-up ke owner encounter
            try:
                rec.encounter_id.push_activity_followup(
                    summary=_("Review anesthesia record"),
                    days=1,
                    user=rec.encounter_id.user_id or rec.performer_user_id,
                )
            except Exception:
                pass
        return True

    def action_cancel(self, reason=None):
        for rec in self:
            rec.write({"state": "cancelled"})
            if reason:
                rec.message_post(body=_("Cancelled: %s") % reason)
        return True

    # -------------------------------------------------------------------------
    # Billing Bridges
    # -------------------------------------------------------------------------
    def _map_taxes(self, taxes, partner, product=None):
        fpos = partner.property_account_position_id if partner else False
        return fpos.map_tax(taxes, product=product, partner=partner) if fpos else taxes

    def _income_account_from_product(self, product):
        if not product:
            return False
        if getattr(product, "property_account_income_id", False) and product.property_account_income_id:
            return product.property_account_income_id.id
        if product.categ_id and product.categ_id.property_account_income_categ_id:
            return product.categ_id.property_account_income_categ_id.id
        return False

    def action_prepare_invoice_line_vals(self):
        """
        Siapkan list of dict untuk pembuatan account.move.line:
        - per_case: 1 baris menggunakan product_case_id
        - per_time: base_units (opsional) + ceil(durasi/time_unit_minutes) time units menggunakan product_time_id
        - no_bill : []
        """
        lines = []
        for rec in self:
            if rec.billing_policy == "no_bill":
                continue
            partner = rec.partner_id
            if not partner:
                raise UserError(_("Patient partner is not set on the Encounter."))

            # per_case
            if rec.billing_policy == "per_case":
                if not rec.product_case_id:
                    rec.message_post(body=_("Billing per case but product_case is not set."))
                    continue
                taxes = rec._map_taxes(rec.product_case_id.taxes_id, partner, rec.product_case_id)
                account_id = rec._income_account_from_product(rec.product_case_id)
                lines.append({
                    "name": _("Anesthesia Case — %s") % (rec.procedure_id.display_name if rec.procedure_id else rec.name),
                    "quantity": 1.0,
                    "price_unit": rec.product_case_id.lst_price,
                    "discount": 0.0,
                    "product_id": rec.product_case_id.id,
                    "product_uom_id": rec.product_case_id.uom_id.id,
                    "tax_ids": [(6, 0, taxes.ids)] if taxes else [],
                    "account_id": account_id,
                    "currency_id": rec.currency_id.id,
                })

            # per_time
            if rec.billing_policy == "per_time":
                if not rec.product_time_id:
                    rec.message_post(body=_("Billing by time but product_time is not set."))
                    continue
                units = 0
                # Base units opsional
                units += max(int(rec.base_units or 0), 0)
                # Time units dari durasi
                if rec.time_unit_minutes > 0 and rec.anesthesia_duration_min > 0:
                    units += int(math.ceil(rec.anesthesia_duration_min / float(rec.time_unit_minutes)))
                if units <= 0:
                    continue
                taxes = rec._map_taxes(rec.product_time_id.taxes_id, partner, rec.product_time_id)
                account_id = rec._income_account_from_product(rec.product_time_id)
                lines.append({
                    "name": _("Anesthesia Time Units — %s min units") % rec.time_unit_minutes,
                    "quantity": units,
                    "price_unit": rec.product_time_id.lst_price,
                    "discount": 0.0,
                    "product_id": rec.product_time_id.id,
                    "product_uom_id": rec.product_time_id.uom_id.id,
                    "tax_ids": [(6, 0, taxes.ids)] if taxes else [],
                    "account_id": account_id,
                    "currency_id": rec.currency_id.id,
                })
        return lines

    def action_open_billing(self):
        """Buka invoice terkait; fallback ke invoice_origin encounter."""
        self.ensure_one()
        AccountMove = self.env["account.move"]
        moves = AccountMove.search([
            ("line_ids", "in", self.invoice_line_ids.ids or [0]),
            ("company_id", "=", self.company_id.id),
            ("move_type", "in", ["out_invoice", "out_refund"]),
        ])
        if not moves and self.encounter_id:
            moves = AccountMove.search([
                ("invoice_origin", "=", self.encounter_id.name),
                ("move_type", "in", ["out_invoice", "out_refund"]),
                ("company_id", "=", self.company_id.id),
            ])
        if not moves:
            raise UserError(_("No related invoices found."))
        action = self.env.ref("account.action_move_out_invoice_type").read()[0]
        action["domain"] = [("id", "in", moves.ids)]
        return action

    # -------------------------------------------------------------------------
    # Result document (opsional)
    # -------------------------------------------------------------------------
    def action_generate_result_document(self):
        """
        Buat result document ringkas dari data anesthesia (opsional).
        """
        self.ensure_one()
        Result = self.env["clinic.result.document"]
        title = _("Anesthesia Report — %s") % (self.procedure_id.display_name if self.procedure_id else self.name)
        # Ringkasan sederhana
        summary = "<p><b>Type:</b> %s</p>" % dict(self._fields["anesthesia_type"].selection).get(self.anesthesia_type, _("N/A"))
        summary += "<p><b>ASA:</b> %s%s</p>" % (
            self.asa_class or "-",
            "E" if self.asa_emergency else "",
        )
        summary += "<p><b>Duration:</b> %.0f min</p>" % (self.anesthesia_duration_min or 0)
        res = Result.create({
            "encounter_id": self.encounter_id.id,
            "session_id": self.session_id.id if self.session_id else False,
            "procedure_id": self.procedure_id.id if self.procedure_id else False,
            "diagnosis_id": self.diagnosis_id.id if self.diagnosis_id else False,
            "title": title,
            "summary": summary,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Result"),
            "res_model": "clinic.result.document",
            "res_id": res.id,
            "view_mode": "form",
        }

    # -------------------------------------------------------------------------
    # Name & Search
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            label = rec.name
            if rec.procedure_id:
                label = f"{rec.name} • {rec.procedure_id.display_name or rec.procedure_id.name}"
            res.append((rec.id, label))
        return res

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        extra_domain = list(domain or [])
        name_domain = ["|", "|",
                  ("name", operator, name),
                  ("procedure_id.name", operator, name),
                  ("encounter_id.name", operator, name)]
        recs = self.search(name_domain + extra_domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]


# =============================================================================
# Lines: Medications
# =============================================================================
class ClinicAnesthesiaMedication(models.Model):
    _name = "clinic.anesthesia.medication"
    _description = "Anesthesia Medication Line"
    _order = "case_id, time_admin, id"
    _check_company_auto = True

    case_id = fields.Many2one("clinic.anesthesia.case", string="Anesthesia Case", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", related="case_id.company_id", store=True, readonly=True)

    time_admin = fields.Datetime(string="Time", default=lambda s: fields.Datetime.now(), index=True)
    product_id = fields.Many2one("product.product", string="Drug/Product", required=True, ondelete="restrict", index=True)
    dose = fields.Float(string="Dose")
    dose_uom = fields.Many2one("uom.uom", string="Dose UoM")
    route = fields.Selection(
        [("iv", "IV"), ("im", "IM"), ("po", "PO"), ("inh", "Inhalation"), ("sc", "SC"), ("topical", "Topical"), ("other", "Other")],
        string="Route",
        default="iv",
    )
    remark = fields.Char(string="Remark / Purpose")

    @api.onchange("product_id")
    def _onchange_product(self):
        if self.product_id and not self.dose_uom:
            self.dose_uom = self.product_id.uom_id


# =============================================================================
# Lines: Vitals Timeline
# =============================================================================
class ClinicAnesthesiaVital(models.Model):
    _name = "clinic.anesthesia.vital"
    _description = "Anesthesia Vital Sign"
    _order = "case_id, time_point asc, id asc"
    _check_company_auto = True

    case_id = fields.Many2one("clinic.anesthesia.case", string="Anesthesia Case", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", related="case_id.company_id", store=True, readonly=True)

    time_point = fields.Datetime(string="Time", required=True, default=lambda s: fields.Datetime.now(), index=True)
    hr = fields.Integer(string="HR")
    rr = fields.Integer(string="RR")
    spo2 = fields.Integer(string="SpO₂ (%)")
    sbp = fields.Integer(string="SBP")
    dbp = fields.Integer(string="DBP")
    map = fields.Integer(string="MAP")
    temp = fields.Float(string="Temp (°C)", digits=(16, 2))
    etco2 = fields.Integer(string="EtCO₂ (mmHg)")
    fio2 = fields.Integer(string="FiO₂ (%)")
    agent = fields.Char(string="Agent (End-tidal)")
    agent_et = fields.Float(string="Agent ET (%)", digits=(16, 2))

    note = fields.Char(string="Note")


# =============================================================================
# Lines: Fluids In/Out
# =============================================================================
class ClinicAnesthesiaFluid(models.Model):
    _name = "clinic.anesthesia.fluid"
    _description = "Anesthesia Fluid In/Out"
    _order = "case_id, time_move, id"
    _check_company_auto = True

    case_id = fields.Many2one("clinic.anesthesia.case", string="Anesthesia Case", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", related="case_id.company_id", store=True, readonly=True)
    time_move = fields.Datetime(string="Time", default=lambda s: fields.Datetime.now(), index=True)

    direction = fields.Selection([("in", "In"), ("out", "Out")], string="Direction", required=True, default="in", index=True)
    product_id = fields.Many2one("product.product", string="Fluid/Blood Product", ondelete="restrict", index=True)
    volume_ml = fields.Float(string="Volume (ml)", required=True)
    is_blood_loss = fields.Boolean(string="Blood Loss?")
    is_urine = fields.Boolean(string="Urine?")

    remark = fields.Char(string="Remark")

    _constraint_qty_nonneg = models.Constraint(
        'CHECK (volume_ml >= 0)',
        'Volume must be positive or zero.',
    )


# =============================================================================
# Lines: Airway Events
# =============================================================================
class ClinicAnesthesiaAirway(models.Model):
    _name = "clinic.anesthesia.airway"
    _description = "Anesthesia Airway Event"
    _order = "case_id, time_event, id"
    _check_company_auto = True

    case_id = fields.Many2one("clinic.anesthesia.case", string="Anesthesia Case", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", related="case_id.company_id", store=True, readonly=True)

    time_event = fields.Datetime(string="Time", default=lambda s: fields.Datetime.now(), index=True)
    event = fields.Selection(
        [
            ("preoxygenation", "Preoxygenation"),
            ("induction", "Induction"),
            ("laryngoscopy", "Laryngoscopy"),
            ("intubation", "Intubation"),
            ("lma_insertion", "LMA Insertion"),
            ("airway_change", "Airway Device Change"),
            ("extubation", "Extubation"),
            ("emergence", "Emergence"),
            ("other", "Other"),
        ],
        string="Event",
        required=True,
    )
    device = fields.Selection(
        [("mask", "Face Mask"), ("lma", "LMA"), ("ett", "ETT"), ("nc", "Nasal Cannula"), ("other", "Other")],
        string="Device",
    )
    device_size = fields.Char(string="Size")
    attempts = fields.Integer(string="Attempts")
    success = fields.Boolean(string="Successful?")
    grade = fields.Selection([("1", "CL I"), ("2", "CL II"), ("3", "CL III"), ("4", "CL IV")], string="Laryngoscopy Grade")
    confirmation = fields.Selection(
        [("capno", "EtCO₂"), ("ausc", "Auscultation"), ("chest", "Chest Rise"), ("other", "Other")],
        string="Confirmation",
    )
    note = fields.Char(string="Note")


# =============================================================================
# Lines: Generic Intraop Event/Note
# =============================================================================
class ClinicAnesthesiaEvent(models.Model):
    _name = "clinic.anesthesia.event"
    _description = "Anesthesia Intraop Event/Note"
    _order = "case_id, time_event, id"
    _check_company_auto = True

    case_id = fields.Many2one("clinic.anesthesia.case", string="Anesthesia Case", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", related="case_id.company_id", store=True, readonly=True)

    time_event = fields.Datetime(string="Time", default=lambda s: fields.Datetime.now(), index=True)
    category = fields.Selection(
        [
            ("induction", "Induction"),
            ("maintenance", "Maintenance"),
            ("emergence", "Emergence"),
            ("positioning", "Positioning"),
            ("device", "Device"),
            ("complication", "Complication"),
            ("communication", "Communication"),
            ("other", "Other"),
        ],
        string="Category",
        default="other",
        required=True,
    )
    description = fields.Text(string="Description")
    critical = fields.Boolean(string="Critical?")



# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/adverse_event.py
#
# Tujuan:
# - Mencatat Adverse Event / Near Miss terhubung Encounter/Session/Procedure/Diagnosis/Result/Anesthesia.
# - Klasifikasi (category, type), severity, outcome, kausalitas, faktor kontribusi.
# - Workflow: draft → under_review → closed / cancelled.
# - CAPA (Corrective & Preventive Actions), lampiran, saksi, notifikasi, dan pelaporan regulator.
# - Indikator seriousness & needs_reporting (computed).
#
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =============================================================================
# Master: Kategori dan Tipe Kejadian
# =============================================================================
class ClinicAdverseEventCategory(models.Model):
    _name = "clinic.ae.category"
    _description = "Adverse Event Category"
    _order = "sequence, name"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True, index=True)
    code = fields.Char(index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text()
    company_id = fields.Many2one("res.company", default=lambda s: s.env.company, required=True, index=True)

    _constraint_uniq_code_company = models.Constraint(
        'unique(code, company_id)',
        'Category code must be unique per company.',
    )


class ClinicAdverseEventType(models.Model):
    _name = "clinic.ae.type"
    _description = "Adverse Event Type"
    _order = "sequence, name"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True, index=True)
    code = fields.Char(index=True)
    category_id = fields.Many2one("clinic.ae.category", string="Category", index=True, ondelete="set null")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text()
    company_id = fields.Many2one("res.company", default=lambda s: s.env.company, required=True, index=True)


# =============================================================================
# Master: Faktor Kontribusi (People, Process, Equipment, Environment, etc.)
# =============================================================================
class ClinicAdverseEventFactor(models.Model):
    _name = "clinic.ae.factor"
    _description = "Adverse Event Contributing Factor"
    _order = "sequence, name"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True, index=True)
    code = fields.Char(index=True)
    group = fields.Selection(
        [
            ("people", "People"),
            ("process", "Process/Protocol"),
            ("equipment", "Equipment/Device"),
            ("medication", "Medication"),
            ("environment", "Environment"),
            ("communication", "Communication"),
            ("other", "Other"),
        ],
        string="Group",
        default="other",
        index=True,
    )
    description = fields.Text()
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda s: s.env.company, required=True, index=True)


# =============================================================================
# Header: Adverse Event
# =============================================================================
class ClinicAdverseEvent(models.Model):
    _name = "clinic.adverse.event"
    _description = "Adverse Event / Near Miss"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_occurred desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identitas & Konteks
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="AE #",
        required=True,
        copy=False,
        default=lambda s: _("New"),
        index=True,
        tracking=True,
    )
    active = fields.Boolean(default=True, tracking=True)

    company_id = fields.Many2one("res.company", required=True, default=lambda s: s.env.company, index=True)
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", store=True, readonly=True)

    # Konteks klinis
    encounter_id = fields.Many2one(
        "clinic.encounter", string="Encounter", required=True, ondelete="cascade", index=True, tracking=True
    )
    session_id = fields.Many2one(
        "clinic.procedure.session", string="Procedure Session", ondelete="set null", index=True
    )
    procedure_id = fields.Many2one("clinic.procedure.catalog", string="Procedure", ondelete="set null", index=True)
    diagnosis_id = fields.Many2one("clinic.diagnosis", string="Diagnosis", ondelete="set null", index=True)
    result_id = fields.Many2one("clinic.result.document", string="Related Result", ondelete="set null", index=True)
    anesthesia_case_id = fields.Many2one("clinic.anesthesia.case", string="Anesthesia Case", ondelete="set null", index=True)

    patient_id = fields.Many2one("clinic.patient", related="encounter_id.patient_id", store=True, readonly=True, index=True)
    partner_id = fields.Many2one("res.partner", related="patient_id.partner_id", store=True, readonly=True)
    doctor_id = fields.Many2one("clinic.doctor", related="encounter_id.doctor_id", store=True, readonly=True, index=True)
    room_id = fields.Many2one("clinic.room", string="Location/Room")

    # -------------------------------------------------------------------------
    # Waktu, Pelapor, Saksi
    # -------------------------------------------------------------------------
    date_occurred = fields.Datetime(string="Occurred On", required=True, index=True, tracking=True)
    date_detected = fields.Datetime(string="Detected On", index=True, help="If different from occurrence time.")
    reported_by_id = fields.Many2one("res.users", string="Reported By", default=lambda s: s.env.user, index=True)
    reporter_role = fields.Selection(
        [("staff", "Staff"), ("performer", "Performer"), ("supervisor", "Supervisor"), ("patient", "Patient/Family"), ("other", "Other")],
        string="Reporter Role",
        default="staff",
        index=True,
    )
    witness_partner_ids = fields.Many2many("res.partner", string="Witnesses")

    # -------------------------------------------------------------------------
    # Klasifikasi
    # -------------------------------------------------------------------------
    category_id = fields.Many2one("clinic.ae.category", string="Category", index=True)
    type_id = fields.Many2one("clinic.ae.type", string="Type", index=True)
    factor_ids = fields.Many2many("clinic.ae.factor", string="Contributing Factors")

    classification = fields.Selection(
        [
            ("near_miss", "Near Miss (No Harm)"),
            ("no_harm", "No Harm Incident"),
            ("harm", "Harmful Incident"),
            ("sentinel", "Sentinel Event"),
        ],
        string="Classification",
        default="no_harm",
        index=True,
        tracking=True,
    )
    severity = fields.Selection(
        [
            ("none", "No Harm"),
            ("minor", "Minor"),
            ("moderate", "Moderate"),
            ("severe", "Severe"),
            ("death", "Death"),
        ],
        string="Severity",
        default="none",
        index=True,
        tracking=True,
    )
    outcome = fields.Selection(
        [
            ("recovered", "Recovered"),
            ("recovering", "Recovering"),
            ("sequelae", "Sequelae"),
            ("death", "Death"),
            ("not_applicable", "Not Applicable"),
            ("unknown", "Unknown"),
        ],
        string="Outcome",
        default="unknown",
        index=True,
    )

    # Skala harm (opsional WHO A–I; A–B no harm, C–I harm)
    harm_scale = fields.Selection(
        [
            ("A", "A – Circumstances"),
            ("B", "B – Near Miss"),
            ("C", "C – Reached patient, no harm"),
            ("D", "D – Monitoring/Intervention required"),
            ("E", "E – Temporary harm"),
            ("F", "F – Temporary harm, hospitalization"),
            ("G", "G – Permanent harm"),
            ("H", "H – Intervention to sustain life"),
            ("I", "I – Death"),
        ],
        string="WHO Harm Scale",
        index=True,
    )

    causality = fields.Selection(
        [
            ("certain", "Certain"),
            ("probable", "Probable/Likely"),
            ("possible", "Possible"),
            ("unlikely", "Unlikely"),
            ("conditional", "Conditional/Unclassified"),
            ("unassessable", "Unassessable/Unclassifiable"),
        ],
        string="Causality (WHO-UMC)",
        index=True,
    )

    # Flag seriousness dan kebutuhan pelaporan
    is_serious = fields.Boolean(string="Serious?", compute="_compute_flags", store=True)
    needs_reporting = fields.Boolean(
        string="Needs Regulatory Reporting?",
        compute="_compute_flags",
        store=True,
        help="Computed from severity/classification/outcome; can be overridden.",
    )

    # -------------------------------------------------------------------------
    # Detail klinis & paparan
    # -------------------------------------------------------------------------
    description = fields.Html(string="Description / Narrative", required=True, help="What happened?")
    immediate_action = fields.Text(string="Immediate Actions Taken")
    patient_impact = fields.Text(string="Patient Impact / Symptoms")
    recurrence_risk = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")],
        string="Recurrence Risk",
        default="low",
        index=True,
    )

    # Produk obat / alat (opsional)
    drug_product_id = fields.Many2one("product.product", string="Suspected Drug/Product", ondelete="set null", index=True)
    device_product_id = fields.Many2one("product.product", string="Suspected Device", ondelete="set null", index=True)
    device_lot = fields.Char(string="Device Lot/Serial")
    medication_line_note = fields.Char(string="Dose/Time (if drug-related)")

    # Lampiran & Tag
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "clinic_ae_attachment_rel",
        "ae_id",
        "attachment_id",
        string="Attachments",
    )
    tag_ids = fields.Many2many("clinic.soap.tag", string="Tags")

    # -------------------------------------------------------------------------
    # Workflow & Pelaporan Regulator
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("under_review", "Under Review"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        index=True,
        tracking=True,
    )
    reviewer_id = fields.Many2one("res.users", string="Reviewer/QA", index=True)
    date_closed = fields.Datetime(string="Closed On")
    resolution_summary = fields.Text(string="Resolution / Root Cause Summary")

    # Pelaporan regulator
    to_regulator = fields.Boolean(string="Report to Regulator?")
    regulator_body = fields.Char(string="Regulatory Body")
    regulator_reference = fields.Char(string="Regulator Ref #")
    date_reported = fields.Datetime(string="Reported On")

    # CAPA
    action_ids = fields.One2many("clinic.ae.action", "ae_id", string="Actions (CAPA)")
    followup_ids = fields.One2many("clinic.ae.followup", "ae_id", string="Follow-ups / Notes")

    color = fields.Integer(string="Color Index")
    note_internal = fields.Text(string="Internal Notes")

    # -------------------------------------------------------------------------
    # Komputasi Flag
    # -------------------------------------------------------------------------
    @api.depends("severity", "classification", "outcome", "harm_scale", "to_regulator")
    def _compute_flags(self):
        for rec in self:
            # Serious jika: severity ∈ {severe, death} atau classification sentinel, atau harm_scale ∈ {G,H,I} atau outcome death
            serious = False
            if rec.severity in ("severe", "death"):
                serious = True
            if rec.classification == "sentinel":
                serious = True
            if rec.harm_scale in ("G", "H", "I"):
                serious = True
            if rec.outcome == "death":
                serious = True
            rec.is_serious = serious

            # needs_reporting: jika serious atau explicit to_regulator = True
            rec.needs_reporting = bool(serious or rec.to_regulator)

    # -------------------------------------------------------------------------
    # Onchange
    # -------------------------------------------------------------------------
    @api.onchange("session_id")
    def _onchange_session(self):
        sess = self.session_id
        if not sess:
            return
        vals = {}
        if sess.procedure_id and not self.procedure_id:
            vals["procedure_id"] = sess.procedure_id.id
        if sess.diagnosis_id and not self.diagnosis_id:
            vals["diagnosis_id"] = sess.diagnosis_id.id
        if sess.room_id and not self.room_id:
            vals["room_id"] = sess.room_id.id
        self.update(vals)

    @api.onchange("type_id")
    def _onchange_type(self):
        if self.type_id and self.type_id.category_id and not self.category_id:
            self.category_id = self.type_id.category_id

    # -------------------------------------------------------------------------
    # Constraint & Validasi
    # -------------------------------------------------------------------------
    _constraint_uniq_ae_name_company = models.Constraint(
        'unique(name, company_id)',
        'AE number must be unique per company.',
    )

    @api.constrains("company_id", "encounter_id")
    def _check_company_consistency(self):
        for rec in self:
            if rec.encounter_id and rec.company_id and rec.company_id != rec.encounter_id.company_id:
                raise ValidationError(_("Adverse Event company must match Encounter company."))

    @api.constrains("date_occurred", "date_detected")
    def _check_dates(self):
        for rec in self:
            if rec.date_occurred and rec.date_detected and rec.date_detected < rec.date_occurred:
                raise ValidationError(_("Detected On cannot be earlier than Occurred On."))

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if vals.get("name", _("New")) in (False, _("New")):
                vals["name"] = seq.next_by_code("clinic.adverse.event") or _("New")
            # Backfill encounter dari session
            if not vals.get("encounter_id") and vals.get("session_id"):
                sess = self.env["clinic.procedure.session"].browse(vals["session_id"])
                if sess and sess.encounter_id:
                    vals["encounter_id"] = sess.encounter_id.id
        recs = super().create(vals_list)
        # Aktivitas default untuk QA review
        for rec in recs:
            try:
                rec.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Triage adverse event"),
                    user_id=rec.reviewer_id.id or (rec.encounter_id.user_id.id if rec.encounter_id and rec.encounter_id.user_id else self.env.user.id),
                    date_deadline=fields.Date.today(),
                )
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        # Auto escalate jika serius
        if {"severity", "classification", "harm_scale", "outcome"} & set(vals.keys()):
            for rec in self:
                if rec.is_serious and rec.state == "draft":
                    try:
                        rec.activity_schedule(
                            "mail.mail_activity_data_todo",
                            summary=_("Serious event: start investigation"),
                            user_id=rec.reviewer_id.id or self.env.user.id,
                            date_deadline=fields.Date.today(),
                        )
                    except Exception:
                        pass
        return res

    # -------------------------------------------------------------------------
    # Workflow Actions
    # -------------------------------------------------------------------------
    def action_submit_review(self):
        for rec in self:
            if rec.state not in ("draft", "under_review"):
                raise UserError(_("Only Draft or Under Review can be submitted."))
            rec.write({"state": "under_review"})
        return True

    def action_close(self):
        for rec in self:
            if rec.state not in ("draft", "under_review"):
                raise UserError(_("Only Draft/Under Review can be closed."))
            if not rec.resolution_summary:
                raise UserError(_("Please provide a resolution/root cause summary before closing."))
            rec.write({"state": "closed", "date_closed": fields.Datetime.now()})
        return True

    def action_cancel(self, reason=None):
        for rec in self:
            rec.write({"state": "cancelled"})
            if reason:
                rec.message_post(body=_("Cancelled: %s") % reason)
        return True

    def action_mark_reported(self):
        for rec in self:
            if not rec.regulator_body:
                raise UserError(_("Please fill Regulatory Body before marking reported."))
            rec.write({"date_reported": fields.Datetime.now(), "to_regulator": True})
        return True

    # -------------------------------------------------------------------------
    # Smart Buttons / Actions
    # -------------------------------------------------------------------------
    def action_open_encounter(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_encounter").read()[0]
        action["res_id"] = self.encounter_id.id
        action["domain"] = [("id", "=", self.encounter_id.id)]
        action["view_mode"] = "form"
        return action

    def action_open_session(self):
        self.ensure_one()
        if not self.session_id:
            raise UserError(_("This adverse event is not linked to a session."))
        action = self.env.ref("clinic_encounter.action_clinic_procedure_session").read()[0]
        action["res_id"] = self.session_id.id
        action["domain"] = [("id", "=", self.session_id.id)]
        action["view_mode"] = "form"
        return action

    def action_open_result(self):
        self.ensure_one()
        if not self.result_id:
            raise UserError(_("This adverse event is not linked to a result."))
        action = self.env.ref("clinic_encounter.action_clinic_result_document").read()[0]
        action["res_id"] = self.result_id.id
        action["domain"] = [("id", "=", self.result_id.id)]
        action["view_mode"] = "form"
        return action

    def action_open_anesthesia(self):
        self.ensure_one()
        if not self.anesthesia_case_id:
            raise UserError(_("This adverse event is not linked to an anesthesia case."))
        action = self.env.ref("clinic_encounter.action_clinic_anesthesia_case").read()[0]
        action["res_id"] = self.anesthesia_case_id.id
        action["domain"] = [("id", "=", self.anesthesia_case_id.id)]
        action["view_mode"] = "form"
        return action

    # -------------------------------------------------------------------------
    # Name & Search
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            parts = [rec.name]
            if rec.severity and rec.severity != "none":
                parts.append(dict(self._fields["severity"].selection).get(rec.severity))
            if rec.type_id:
                parts.append(rec.type_id.name)
            res.append((rec.id, " • ".join([p for p in parts if p])))
        return res

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        extra_domain = list(domain or [])
        name_domain = ["|", "|", "|",
                  ("name", operator, name),
                  ("type_id.name", operator, name),
                  ("category_id.name", operator, name),
                  ("encounter_id.name", operator, name)]
        recs = self.search(name_domain + extra_domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]


# =============================================================================
# CAPA (Corrective/Preventive) & Follow-ups
# =============================================================================
class ClinicAdverseEventAction(models.Model):
    _name = "clinic.ae.action"
    _description = "Adverse Event Action (CAPA)"
    _order = "ae_id, deadline, id"
    _check_company_auto = True

    ae_id = fields.Many2one("clinic.adverse.event", string="Adverse Event", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", related="ae_id.company_id", store=True, readonly=True)

    name = fields.Char(string="Action", required=True, translate=True)
    type = fields.Selection(
        [("corrective", "Corrective"), ("preventive", "Preventive"), ("mitigation", "Mitigation"), ("training", "Training"), ("other", "Other")],
        string="Type",
        default="corrective",
        index=True,
    )
    owner_id = fields.Many2one("res.users", string="Owner", index=True)
    deadline = fields.Datetime(string="Deadline")
    done = fields.Boolean(string="Done?")
    date_done = fields.Datetime(string="Done On")
    effectiveness_note = fields.Text(string="Effectiveness / Verification")
    attachment_ids = fields.Many2many("ir.attachment", string="Attachments")

    @api.onchange("done")
    def _onchange_done(self):
        if self.done and not self.date_done:
            self.date_done = fields.Datetime.now()


class ClinicAdverseEventFollowup(models.Model):
    _name = "clinic.ae.followup"
    _description = "Adverse Event Follow-up / Note"
    _order = "ae_id, date_note, id"
    _check_company_auto = True

    ae_id = fields.Many2one("clinic.adverse.event", string="Adverse Event", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", related="ae_id.company_id", store=True, readonly=True)

    date_note = fields.Datetime(string="Date", default=lambda s: fields.Datetime.now(), index=True)
    user_id = fields.Many2one("res.users", string="By", default=lambda s: s.env.user, index=True)
    note = fields.Text(string="Note / Investigation Step", required=True)
    attachment_ids = fields.Many2many("ir.attachment", string="Attachments")


# # =============================================================================
# # Extensions: Encounter & Session bridges
# # =============================================================================
# class ClinicEncounter_AdverseEvent(models.Model):
#     _inherit = "clinic.encounter"

#     ae_ids = fields.One2many("clinic.adverse.event", "encounter_id", string="Adverse Events")
#     ae_count = fields.Integer(string="Adverse Events", compute="_compute_ae_count", store=False)

#     def _compute_ae_count(self):
#         for rec in self:
#             rec.ae_count = len(rec.ae_ids)

#     def action_open_adverse_events(self):
#         self.ensure_one()
#         action = self.env.ref("clinic_encounter.action_clinic_adverse_event").read()[0]
#         action["domain"] = [("encounter_id", "=", self.id)]
#         action["context"] = {"default_encounter_id": self.id}
#         return action


# class ClinicProcedureSession_AdverseEvent(models.Model):
#     _inherit = "clinic.procedure.session"

#     ae_ids = fields.One2many("clinic.adverse.event", "session_id", string="Adverse Events")
#     ae_count = fields.Integer(string="Adverse Events", compute="_compute_ae_count", store=False)

#     def _compute_ae_count(self):
#         for rec in self:
#             rec.ae_count = len(rec.ae_ids)

#     def action_open_adverse_events(self):
#         self.ensure_one()
#         action = self.env.ref("clinic_encounter.action_clinic_adverse_event").read()[0]
#         action["domain"] = [("session_id", "=", self.id)]
#         action["context"] = {
#             "default_session_id": self.id,
#             "default_encounter_id": self.encounter_id.id,
#             "default_procedure_id": self.procedure_id.id if self.procedure_id else False,
#             "default_diagnosis_id": self.diagnosis_id.id if self.diagnosis_id else False,
#         }
#         return action

