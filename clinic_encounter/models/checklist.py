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

    # di tambahkan, untuk cari error
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment (Legacy)",
        index=True,
        ondelete="set null",
        help="Compatibility field for legacy modules that reference checklists via 'treatment_id'."
    )


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
