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

    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment (Legacy)",
        index=True,
        ondelete="set null",
        help="Compatibility field for legacy modules that reference results via 'treatment_id'."
    )

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

