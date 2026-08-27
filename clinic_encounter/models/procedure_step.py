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
    @api.depends("name", "procedure_id", "sequence")
    def _compute_display_name(self):
        for rec in self:
            label = rec.name or ""
            if rec.procedure_id:
                label = f"{rec.procedure_id.display_name or rec.procedure_id.name} • {rec.sequence:02d} {rec.name or ''}"
            rec.display_name = label

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
