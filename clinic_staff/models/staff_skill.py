

# -*- coding: utf-8 -*-
# Copyright (C) ClinicOne
# Models: clinic.skill (master), clinic.staff.skill (per-staff skill record)
# Catatan (ID): File ini mencakup master skill dan relasi skill per staff
# agar tidak terjadi missing model untuk master data skills. Disusun untuk
# mendukung integrasi lintas modul (procedure requirement, telemed routing, dsb).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


# ============================================================
# Master Skill
# ============================================================
class ClinicSkill(models.Model):
    _name = "clinic.skill"
    _description = "Clinical Skill"
    _rec_name = "name"
    _order = "category, name"

    # Identitas dasar
    name = fields.Char(
        string="Skill Name",
        required=True,
        index=True,
        help="Human-readable skill name, e.g., 'IV Insertion', 'Facial Treatment A'.",
        translate=True,
    )

    code = fields.Char(
        string="Skill Code",
        required=True,
        copy=False,
        default="/",
        index=True,
        help="Unique code generated from sequence for the skill.",
    )

    category = fields.Selection(
        selection=[
            ("nursing", "Nursing"),
            ("therapy", "Therapy"),
            ("medical", "Medical"),
            ("device", "Medical Device Operation"),
            ("safety", "Patient Safety"),
            ("cosmetology", "Cosmetology"),
            ("general", "General"),
            ("other", "Other"),
        ],
        string="Category",
        default="general",
        help="Skill category for grouping and access routing.",
        index=True,
    )

    description = fields.Text(
        string="Description",
        help="Long description or competency definition.",
        translate=True,
    )

    # Applicability per role
    applicable_to_nurse = fields.Boolean(
        string="Applicable to Nurse",
        default=True,
        help="Indicates whether this skill applies to Nurse role.",
    )
    applicable_to_therapist = fields.Boolean(
        string="Applicable to Therapist",
        default=True,
        help="Indicates whether this skill applies to Therapist role.",
    )
    applicable_to_doctor = fields.Boolean(
        string="Applicable to Doctor",
        default=False,
        help="Indicates whether this skill applies to Doctor role.",
    )

    # Persyaratan & compliance
    requires_license = fields.Boolean(
        string="Requires License",
        help="If enabled, staff must have at least one active license to be considered compliant for this skill.",
        default=False,
    )

    minimum_grade = fields.Selection(
        selection=[
            ("junior", "Junior"),
            ("mid", "Mid"),
            ("senior", "Senior"),
            ("lead", "Lead"),
            ("principal", "Principal"),
        ],
        string="Minimum Grade",
        help="Minimum staff grade required to perform this skill independently.",
    )

    is_active = fields.Boolean(
        string="Active",
        default=True,
        help="If unchecked, the skill will be hidden from selection and planning.",
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company.id,
        help="Company for multi-company environments.",
    )

    # Back-refs (informasi non-stored, tidak membebani performa)
    staff_skill_ids = fields.One2many(
        comodel_name="clinic.staff.skill",
        inverse_name="skill_id",
        string="Staff Skills",
        help="Staff who are registered with this skill.",
    )

    _skill_code_unique = models.Constraint(
        'unique(code)',
        'Skill Code must be unique.',
    )

    _skill_name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Skill name must be unique per company.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence untuk code bila '/'."""
        for vals in vals_list:
            if not vals.get("code") or vals.get("code") in ("/",):
                vals["code"] = self.env["ir.sequence"].next_by_code("clinic.skill") or "/"
        return super().create(vals_list)


# ============================================================
# Staff Skill (Competency Matrix per Staff)
# ============================================================
class ClinicStaffSkill(models.Model):
    _name = "clinic.staff.skill"
    _description = "Staff Skill"
    _inherit = ["mail.thread", "mail.activity.mixin"]  # catat perubahan kompetensi
    _rec_name = "display_name"
    _order = "staff_id, skill_id"

    # Relasi utama
    staff_id = fields.Many2one(
        comodel_name="clinic.staff",
        string="Staff",
        required=True,
        index=True,
        ondelete="cascade",
        help="Staff who owns this competency record.",
        tracking=True,
    )

    skill_id = fields.Many2one(
        comodel_name="clinic.skill",
        string="Skill",
        required=True,
        index=True,
        ondelete="restrict",
        help="Skill definition linked to this record.",
        tracking=True,
    )

    # Tampilan gabungan
    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
        help="Composite label: Staff / Skill (Level).",
    )

    # Level kompetensi (berdasarkan Dreyfus 1..5)
    level = fields.Selection(
        selection=[
            ("1", "Novice"),
            ("2", "Advanced Beginner"),
            ("3", "Competent"),
            ("4", "Proficient"),
            ("5", "Expert"),
        ],
        string="Competency Level",
        required=True,
        default="2",
        index=True,
        help="Competency level based on Dreyfus model.",
        tracking=True,
    )

    # Penilaian & validitas
    last_assessed_date = fields.Date(
        string="Last Assessed On",
        help="Date when the competency was last assessed.",
        tracking=True,
    )
    assessor_id = fields.Many2one(
        comodel_name="res.users",
        string="Assessed By",
        help="Assessor who performed the evaluation.",
        tracking=True,
    )

    valid_from = fields.Date(
        string="Valid From",
        help="Start date of competency validity window (for compliance tracking).",
        tracking=True,
    )
    valid_to = fields.Date(
        string="Valid To",
        help="End date of competency validity window (for compliance tracking).",
        tracking=True,
    )

    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("valid", "Valid"),
            ("expired", "Expired"),
            ("suspended", "Suspended"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        help="Lifecycle state of the staff skill record.",
        index=True,
    )

    # Evidence & catatan
    evidence_attachment_ids = fields.Many2many(
        comodel_name="ir.attachment",
        relation="clinic_staff_skill_ir_attachment_rel",
        column1="staff_skill_id",
        column2="attachment_id",
        string="Evidence Attachments",
        help="Certificates, photos, logs, or documents supporting the skill.",
    )

    notes = fields.Text(
        string="Notes",
        help="Additional notes regarding assessment details or limitations.",
    )

    # Compliance helpers
    requires_license = fields.Boolean(
        string="Requires License",
        related="skill_id.requires_license",
        store=True,
        readonly=True,
        help="If true, the staff must maintain at least one active license.",
    )

    minimum_grade = fields.Selection(
        selection=[
            ("junior", "Junior"),
            ("mid", "Mid"),
            ("senior", "Senior"),
            ("lead", "Lead"),
            ("principal", "Principal"),
        ],
        string="Minimum Grade",
        related="skill_id.minimum_grade",
        store=True,
        readonly=True,
        help="Minimum grade requirement inherited from the skill.",
    )

    is_within_validity_window = fields.Boolean(
        string="Within Validity Window",
        compute="_compute_validity",
        store=False,
        help="True if today is within the validity window (Valid From/To).",
    )

    is_compliant = fields.Boolean(
        string="Compliant",
        compute="_compute_compliance",
        store=False,
        help="True if grade, license (if required), and validity window are satisfied.",
    )

    # Audit & multi-company
    company_id = fields.Many2one(
        comodel_name="res.company",
        related="staff_id.company_id",
        store=True,
        readonly=True,
        string="Company",
    )

    _staff_skill_unique = models.Constraint(
        'unique(staff_id, skill_id)',
        'A staff cannot have duplicate skill records.',
    )

    # =========================
    # Compute & Helpers
    # =========================
    @api.depends("staff_id.display_name", "skill_id.name", "level")
    def _compute_display_name(self):
        """Bangun display_name gabungan: Staff / Skill (Level)"""
        level_map = dict(self._fields["level"].selection)
        for rec in self:
            parts = []
            if rec.staff_id:
                parts.append(rec.staff_id.display_name or _("(No Staff)"))
            if rec.skill_id:
                parts.append(rec.skill_id.name or _("(No Skill)"))
            if rec.level:
                parts.append("(%s)" % level_map.get(rec.level, rec.level))
            rec.display_name = " / ".join(parts) if parts else _("Staff Skill")

    def _today(self):
        """Abstraksi tanggal hari ini agar mudah di-mock pada unit test."""
        return fields.Date.context_today(self)

    def _staff_grade_meets_minimum(self, staff_grade, minimum_grade):
        """Bandingkan urutan grade staff vs minimum yang dipersyaratkan."""
        if not minimum_grade:
            return True
        order = ["junior", "mid", "senior", "lead", "principal"]
        try:
            return order.index(staff_grade or "") >= order.index(minimum_grade)
        except ValueError:
            return False

    @api.depends("valid_from", "valid_to")
    def _compute_validity(self):
        """Validitas berdasarkan rentang tanggal."""
        today = self._today()
        for rec in self:
            valid = True
            if rec.valid_from and today < rec.valid_from:
                valid = False
            if rec.valid_to and today > rec.valid_to:
                valid = False
            rec.is_within_validity_window = valid

    @api.depends(
        "requires_license",
        "is_within_validity_window",
        "staff_id.employment_status",
        "staff_id.is_active",
        "minimum_grade",
        "staff_id.grade",
        "staff_id.license_ids.state",
    )
    def _compute_compliance(self):
        """Compliance jika: employment aktif, valid window terpenuhi, grade memenuhi,
        dan jika perlu, punya lisensi aktif."""
        for rec in self:
            compliant = (
                rec.staff_id.employment_status == "active"
                and rec.staff_id.is_active
                and rec.is_within_validity_window
                and rec._staff_grade_meets_minimum(rec.staff_id.grade, rec.minimum_grade)
            )
            if rec.requires_license:
                has_active_license = any(l.state == "active" for l in rec.staff_id.license_ids)
                compliant = compliant and has_active_license
            rec.is_compliant = bool(compliant)

    # =========================
    # CRUD Overrides
    # =========================
    @api.model_create_multi
    def create(self, vals_list):
        """Normalisasi state & penjadwalan activity jika perlu evidence."""
        records = super().create(vals_list)
        today = self._today()
        for rec in records:
            # Otomatis set state berdasarkan masa berlaku (jika ada)
            if rec.valid_to and today > rec.valid_to:
                rec.state = "expired"
            elif rec.valid_from and today < rec.valid_from:
                rec.state = "draft"
            else:
                rec.state = "valid"

            # Kirim aktivitas jika skill butuh license tapi staff belum punya
            if rec.requires_license and not any(l.state == "active" for l in rec.staff_id.license_ids):
                rec.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Ensure active professional license"),
                    note=_("This skill requires an active license. Please update the staff license records."),
                )
        return records

    def write(self, vals):
        res = super().write(vals)
        # Re-evaluasi state sederhana saat tanggal berlaku berubah
        if "valid_from" in vals or "valid_to" in vals:
            today = self._today()
            for rec in self:
                if rec.valid_to and today > rec.valid_to:
                    rec.state = "expired"
                elif rec.valid_from and today < rec.valid_from:
                    rec.state = "draft"
                else:
                    rec.state = "valid"
        return res

    # =========================
    # Constraints
    # =========================
    @api.constrains("valid_from", "valid_to")
    def _check_validity_range(self):
        for rec in self:
            if rec.valid_from and rec.valid_to and rec.valid_to < rec.valid_from:
                raise ValidationError(_("The 'Valid To' date cannot be earlier than 'Valid From'."))

    # =========================
    # Actions (Smart Buttons / Wizards)
    # =========================
    def action_open_evidence(self):
        """Buka attachment evidence."""
        self.ensure_one()
        return {
            "name": _("Evidence Attachments"),
            "type": "ir.actions.act_window",
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "domain": [("id", "in", self.evidence_attachment_ids.ids)],
            "context": {"default_res_model": self._name, "default_res_id": self.id},
        }

    # =========================
    # Business Helpers (Integrasi Lintas Modul)
    # =========================
    def is_eligible_for_procedure(self, procedure_id=None, procedure_code=None):
        """Cek kelayakan skill untuk prosedur tertentu.
        - Mengacu pada (opsional) model mapping kebutuhan skill prosedur:
          'clinic.procedure.skill' dengan field:
            - procedure_id (m2o clinic.procedure)
            - skill_id (m2o clinic.skill)
            - minimum_level (selection '1'..'5')
        - Jika model/record tidak ada, fallback True (tidak memblok).
        """
        self.ensure_one()
        ProcSkill = self.env.get("clinic.procedure.skill")
        if not ProcSkill:
            return True  # fallback bila modul belum terpasang

        domain = []
        if procedure_id:
            domain.append(("procedure_id", "=", procedure_id))
        elif procedure_code:
            # Coba resolve dari model procedure bila tersedia
            Proc = self.env.get("clinic.procedure")
            if Proc and procedure_code:
                proc = Proc.search([("code", "=", procedure_code)], limit=1)
                if not proc:
                    return True  # tidak memblok jika prosedur tidak ditemukan
                domain.append(("procedure_id", "=", proc.id))
            else:
                return True
        else:
            return True

        reqs = ProcSkill.search(domain)
        if not reqs:
            return True  # tidak ada requirement, berarti lolos

        level_order = ["1", "2", "3", "4", "5"]
        my_level_idx = level_order.index(self.level or "1")
        for req in reqs:
            if req.skill_id.id == self.skill_id.id:
                # Jika requirement menetapkan minimum level
                if req.minimum_level and level_order.index(req.minimum_level) > my_level_idx:
                    return False
        return True

    def eligible_for_role_routing(self):
        """Dipakai untuk routing telemedicine/queue berdasarkan role & skill applicability."""
        self.ensure_one()
        role = self.staff_id.role
        sk = self.skill_id
        if role == "nurse" and not sk.applicable_to_nurse:
            return False
        if role == "therapist" and not sk.applicable_to_therapist:
            return False
        if role == "doctor" and not sk.applicable_to_doctor:
            return False
        return True

