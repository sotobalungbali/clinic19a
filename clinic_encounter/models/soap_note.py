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

    # Legacy bridge to clinic.treatment (compat)
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment (Legacy)",
        index=True,
        ondelete="set null",
        help="Compatibility field for legacy One2many(..., inverse_name='treatment_id')."
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
    @api.depends("name", "encounter_id", "chief_complaint")
    def _compute_display_name(self):
        for rec in self:
            label = rec.name or ""
            if rec.encounter_id:
                label = f"{label} ⸺ {rec.encounter_id.name}"
            if rec.chief_complaint:
                label = f"{label} ⸺ {rec.chief_complaint}"
            rec.display_name = label.strip(" ⸺")

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        extra_domain = list(domain or [])
        name_domain = ["|", "|",
                  ("name", operator, name),
                  ("encounter_id.name", operator, name),
                  ("chief_complaint", operator, name)]
        recs = self.search(name_domain + extra_domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]
