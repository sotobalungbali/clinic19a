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
    
    # Legacy bridge to clinic.treatment (compat)
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment (Legacy)",
        index=True,
        ondelete="set null",
        help="Compatibility field for legacy One2many(..., inverse_name='treatment_id')."
    )

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )


# =============================================================================
# TEMPLATE: Consent Template (Master)
# =============================================================================
class ClinicConsentTemplate(models.Model):
    """Encounter-specific extension of the canonical consent template.

    Model ownership is intentionally preserved upstream:
    - ``clinic_treatment_catalog`` owns the canonical template identity.
    - ``clinic_consent_legal`` adds legal governance/versioning.
    - ``clinic_encounter`` adds procedure/encounter execution metadata only.

    Do not redefine canonical fields such as ``name``, ``category``,
    ``validity_days``, ``company_id`` or ``treatment_id`` here.
    """

    _name = "clinic.consent.template"
    _inherit = [
        "clinic.consent.template",
        "mail.thread",
        "mail.activity.mixin",
    ]
    _check_company_auto = True

    language = fields.Selection(
        selection=lambda self: self.env["res.lang"].get_installed(),
        string="Encounter Language",
        help="Preferred language of the encounter-facing consent body.",
    )
    procedure_ids = fields.Many2many(
        "clinic.procedure.catalog",
        "clinic_encounter_consent_tmpl_procedure_rel",
        "template_id",
        "procedure_id",
        string="Applicable Encounter Procedures",
        help="If empty, the encounter extension treats the template as generic.",
    )
    body_html = fields.Html(
        string="Encounter Consent Body",
        help=(
            "Encounter-facing body. Legal-governed templates may continue to "
            "use their canonical legal content fields independently."
        ),
    )
    footer_html = fields.Html(
        string="Encounter Footer / Additional Notes",
    )
    require_witness = fields.Boolean(
        string="Require Encounter Witness",
        default=False,
        help="Require at least one witness for encounter consent execution.",
    )
    require_guardian_if_minor = fields.Boolean(
        string="Require Guardian if Minor (Encounter)",
        default=True,
        help="Encounter workflow policy for minor patients.",
    )
    risk_item_ids = fields.Many2many(
        "clinic.consent.risk.template",
        "clinic_encounter_consent_tmpl_risk_rel",
        "template_id",
        "risk_tmpl_id",
        string="Encounter Risk / Disclosure Items",
    )
    note_internal = fields.Text(string="Encounter Internal Notes")

    _constraint_uniq_template_name_company = models.Constraint(
        "unique(name, company_id)",
        "Consent Template name must be unique per company.",
    )

    def action_preview_variables(self):
        """Show placeholders supported by the encounter consent renderer."""
        self.ensure_one()
        self.message_post(
            body=_(
                "Available placeholders: ${patient}, ${patient_age}, "
                "${procedure}, ${doctor}, ${date}, ${encounter}, ${company}."
            )
        )
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
    
    # Legacy bridge to clinic.treatment (compat)
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment (Legacy)",
        index=True,
        ondelete="set null",
        help="Compatibility field for legacy One2many(..., inverse_name='treatment_id')."
    )

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

