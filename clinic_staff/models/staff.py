

# -*- coding: utf-8 -*-
# Copyright (C) ClinicOne
# Model: clinic.staff (basic core model)
# Catatan (ID): File ini adalah model dasar "Staff" yang akan menjadi pondasi
# integrasi ke 24 modul lain (Queue/Room, Encounter, Procedure, eMAR, Post-Care,
# Incident, Telemedicine, Billing/Finance/Accounting, Inventory, Insurance, Consent, dsb).
# Semua label/help dalam Bahasa Inggris; komentar penjelas menggunakan Bahasa Indonesia.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicStaff(models.Model):
    _name = "clinic.staff"
    _description = "Clinical Staff"
    _inherit = ["mail.thread", "mail.activity.mixin"]  # chatter & aktivitas
    _rec_name = "display_name"  # nama tampilan gabungan
    _order = "is_active desc, role, name asc"

    # =========================
    # Delegation ke res.partner
    # =========================
    # Catatan: Kita menggunakan delegation agar info kontak (nama, email, phone, address)
    # reuse dari partner. Ini memudahkan integrasi lintas modul (Appointment, Telemedicine, dsb).
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Contact",
        required=True,
        ondelete="restrict",
        help="Linked partner record holding contact details.",
        index=True,
        tracking=True,
    )

    # Enterprise identity bridge used by ClinicOne presentation actors.
    # The links are additive: existing Staff records remain valid with both fields empty.
    user_id = fields.Many2one(
        "res.users",
        string="System User",
        ondelete="set null",
        index=True,
        tracking=True,
        help="Internal user representing the same staff identity, when login access is required.",
    )

    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        ondelete="set null",
        index=True,
        tracking=True,
        help="HR employee representing the same staff identity.",
    )

    # Field related untuk akses cepat ke nama partner (tidak disimpan)
    name = fields.Char(
        string="Name",
        related="partner_id.name",
        store=False,
        readonly=True,
    )

    # Display name (gabungan code + nama + role), disimpan untuk pencarian cepat
    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
        help="Composite label including code, name, and role.",
    )

    # =========================
    # Identitas & Status Staff
    # =========================
    staff_code = fields.Char(
        string="Staff Code",
        required=True,
        copy=False,
        default="/",
        index=True,
        help="Unique staff code generated from sequence.",
        tracking=True,
    )

    role = fields.Selection(
        selection=[
            ("nurse", "Nurse"),
            ("therapist", "Therapist"),
            ("doctor", "Doctor"),
            ("admin", "Admin"),
            ("manager", "Manager"),
            ("other", "Other"),
        ],
        string="Role",
        required=True,
        help="Primary role of the staff for access and routing.",
        tracking=True,
    )

    grade = fields.Selection(
        selection=[
            ("junior", "Junior"),
            ("mid", "Mid"),
            ("senior", "Senior"),
            ("lead", "Lead"),
            ("principal", "Principal"),
        ],
        string="Grade/Level",
        help="Job grade/level used for workload planning and KPIs.",
        tracking=True,
    )

    employment_status = fields.Selection(
        selection=[
            ("probation", "Probation"),
            ("active", "Active"),
            ("on_leave", "On Leave"),
            ("terminated", "Terminated"),
        ],
        string="Employment Status",
        default="active",
        help="Employment status used for scheduling eligibility.",
        tracking=True,
        index=True,
    )

    is_active = fields.Boolean(
        string="Is Active",
        help="Technical active flag for operational scheduling.",
        default=True,
        tracking=True,
    )

    hire_date = fields.Date(
        string="Hire Date",
        help="Date when the staff officially joined.",
    )

    termination_date = fields.Date(
        string="Termination Date",
        help="Date when the staff employment ended.",
    )

    # Perusahaan & Unit (multi-company siap)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company.id,
        index=True,
        help="Company in multi-company environment.",
    )

    # Opsional: cabang/unit operasional (disiapkan untuk modul branch jika ada)
    branch_id = fields.Many2one(
        comodel_name="clinic.branch",
        string="Branch",
        help="Operational branch where the staff is primarily assigned.",
    )

    # Foto profil standar Odoo
    image_1920 = fields.Image(
        string="Photo",
        help="Profile photo.",
        max_width=1920,
        max_height=1920,
    )

    # =========================
    # Kompetensi & Lisensi
    # =========================
    # Catatan: Relasi ke model lain (akan dibuat di file terpisah).
    skill_ids = fields.One2many(
        comodel_name="clinic.staff.skill",
        inverse_name="staff_id",
        string="Skills",
        help="Skill matrix and competency levels.",
    )

    license_ids = fields.One2many(
        comodel_name="clinic.staff.license",
        inverse_name="staff_id",
        string="Licenses",
        help="Professional licenses and certifications with expiry.",
    )

    license_count = fields.Integer(
        string="License Count",
        compute="_compute_counts",
        store=False,
        help="Number of active and archived licenses.",
    )

    # =========================
    # Ketersediaan, Roster, Assignment
    # =========================
    availability_ids = fields.One2many(
        comodel_name="clinic.staff.availability",
        inverse_name="staff_id",
        string="Availability",
        help="Availability calendar for scheduling.",
    )

    roster_ids = fields.One2many(
        comodel_name="clinic.staff.roster",
        inverse_name="staff_id",
        string="Rosters",
        help="Roster entries (shifts) for this staff.",
    )

    assignment_ids = fields.One2many(
        comodel_name="clinic.staff.assignment",
        inverse_name="staff_id",
        string="Assignments",
        help="Room/queue/procedure assignments.",
    )

    roster_count = fields.Integer(
        string="Roster Count",
        compute="_compute_counts",
        store=False,
        help="Number of roster entries.",
    )

    assignment_count = fields.Integer(
        string="Assignment Count",
        compute="_compute_counts",
        store=False,
        help="Number of active assignments.",
    )

    # =========================
    # KPI & Monitoring
    # =========================
    kpi_ids = fields.One2many(
        comodel_name="clinic.staff.kpi",
        inverse_name="staff_id",
        string="KPIs",
        help="Operational and clinical performance indicators.",
    )

    kpi_count = fields.Integer(
        string="KPI Count",
        compute="_compute_counts",
        store=False,
        help="Number of KPI snapshots.",
    )

    # =========================
    # Linkage ke Modul Klinis Lain
    # =========================
    # Catatan: Field count di bawah membantu navigasi (smart buttons).
    incident_count = fields.Integer(
        string="Incident Count",
        compute="_compute_counts",
        help="Number of linked incidents/adverse events.",
        store=False,
    )

    postcare_task_count = fields.Integer(
        string="Post-Care Task Count",
        compute="_compute_counts",
        help="Number of assigned post-care tasks.",
        store=False,
    )

    telemed_thread_count = fields.Integer(
        string="Telemedicine Thread Count",
        compute="_compute_counts",
        help="Number of telemedicine threads linked to this staff.",
        store=False,
    )

    # =========================
    # Helper/Computed
    # =========================
    can_be_scheduled = fields.Boolean(
        string="Eligible for Scheduling",
        compute="_compute_can_be_scheduled",
        help="True if role, licenses, and status allow scheduling.",
        store=False,
    )

    # ================
    # SQL Constraints
    # ================
    _staff_code_unique = models.Constraint(
        'unique(staff_code)',
        'Staff Code must be unique.',
    )

    _staff_user_unique = models.Constraint(
        'unique(user_id)',
        'A System User can only be linked to one ClinicOne Staff record.',
    )

    _staff_employee_unique = models.Constraint(
        'unique(employee_id)',
        'An Employee can only be linked to one ClinicOne Staff record.',
    )


    # =========================
    # Compute Methods
    # =========================
    @api.depends("staff_code", "partner_id.name", "role")
    def _compute_display_name(self):
        """Bangun display_name: [CODE] Name (Role)"""
        for rec in self:
            parts = []
            if rec.staff_code and rec.staff_code not in ("/",):
                parts.append("[%s]" % rec.staff_code)
            if rec.partner_id and rec.partner_id.name:
                parts.append(rec.partner_id.name)
            if rec.role:
                parts.append("(%s)" % rec._get_role_label(rec.role))
            rec.display_name = " ".join(parts) if parts else (rec.staff_code or "/")

    # Default: eligible jika Active & is_active
    # Untuk role klinis, butuh minimal satu lisensi Active (jika model lisensi mewajibkan)
    @api.depends(
        "license_ids.state",
        "employment_status",
        "role",
    )
    def _compute_can_be_scheduled(self):
        """Eligibility tergantung status bekerja aktif dan lisensi (untuk role klinis)."""
        for rec in self:            
            eligible = rec.employment_status == "active" and rec.is_active            
            if rec.role in ("nurse", "therapist", "doctor"):
                active_lic = any(l.state == "active" for l in rec.license_ids)
                eligible = eligible and active_lic
            rec.can_be_scheduled = bool(eligible)

    def _compute_counts(self):
        """Hitung berbagai jumlah terkait untuk smart buttons (roster, assignment, dsb)."""
        # Optimisasi sederhana: gunakan search_count per record (bisa diimprove jadi read_group)
        for rec in self:
            rec.license_count = self.env["clinic.staff.license"].sudo().search_count(
                [("staff_id", "=", rec.id)]
            )
            rec.roster_count = self.env["clinic.staff.roster"].sudo().search_count(
                [("staff_id", "=", rec.id)]
            )
            rec.assignment_count = self.env["clinic.staff.assignment"].sudo().search_count(
                [("staff_id", "=", rec.id), ("state", "!=", "closed")]
            )
            rec.kpi_count = self.env["clinic.staff.kpi"].sudo().search_count(
                [("staff_id", "=", rec.id)]
            )
            rec.incident_count = 0
            # self.env["clinic.incident"].sudo().search_count(
            #     [("involved_staff_ids", "in", rec.id)]
            # )
            rec.postcare_task_count = 0
            # self.env["clinic.postcare.task"].sudo().search_count(
            #     [("assignee_id", "=", rec.id), ("state", "!=", "done")]
            # )
            rec.telemed_thread_count = 0
            # self.env["clinic.telemedicine.thread"].sudo().search_count(
            #     [("handler_id", "=", rec.id)]
            # )

    # =========================
    # Helper Methods
    # =========================
    def _get_role_label(self, role_value):
        """Kembalikan label human-readable untuk role (untuk display)."""
        mapping = dict(self._fields["role"].selection)
        return mapping.get(role_value, role_value or "")

    # =========================
    # CRUD Overrides
    # =========================
    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence untuk staff_code jika default '/'."""
        seq = self.env.ref("clinic_staff.seq_clinic_staff", raise_if_not_found=False)
        for vals in vals_list:
            if not vals.get("staff_code") or vals.get("staff_code") in ("/",):
                # Jika sequence tersedia, gunakan; jika tidak, fallback ke ir.sequence code
                if seq:
                    vals["staff_code"] = self.env["ir.sequence"].next_by_code(
                        "clinic.staff"
                    ) or "/"
                else:
                    vals["staff_code"] = self.env["ir.sequence"].next_by_code(
                        "clinic.staff"
                    ) or "/"
        records = super().create(vals_list)
        # Tulis activity jika staff belum punya lisensi (untuk role klinis)
        # for rec in records:
        #     if rec.role in ("nurse", "therapist", "doctor") and not rec.license_ids:
        #         rec.activity_schedule(
        #             "mail.mail_activity_data_todo",
        #             summary=_("Complete license information"),
        #             note=_("Please add at least one active license for clinical scheduling eligibility."),
        #         )
        return records

    def write(self, vals):
        """Validasi ringan saat perubahan status/role."""
        res = super().write(vals)
        # Jika employment_status berubah ke terminated, nonaktifkan scheduling
        if "employment_status" in vals and vals["employment_status"] == "terminated":
            for rec in self:
                rec.is_active = False
        return res

    # =========================
    # Constraints (Python-level)
    # =========================
    @api.constrains("partner_id", "user_id", "employee_id", "company_id", "branch_id")
    def _check_identity_consistency(self):
        """Keep partner/user/employee/branch as one enterprise staff identity."""
        for rec in self:
            if rec.branch_id and rec.company_id and rec.branch_id.company_id != rec.company_id:
                raise ValidationError(_("Staff branch must belong to the Staff company."))
            if rec.user_id:
                if rec.user_id.partner_id and rec.user_id.partner_id != rec.partner_id:
                    raise ValidationError(_("Staff Contact must match the linked System User contact."))
                if rec.company_id and rec.company_id not in rec.user_id.company_ids:
                    raise ValidationError(_("Staff company must be allowed for the linked System User."))
            if rec.employee_id:
                if rec.employee_id.company_id and rec.company_id and rec.employee_id.company_id != rec.company_id:
                    raise ValidationError(_("Staff company must match the linked Employee company."))
                if "user_id" in rec.employee_id._fields and rec.employee_id.user_id and rec.user_id and rec.employee_id.user_id != rec.user_id:
                    raise ValidationError(_("Staff System User must match the linked Employee user."))
                if "branch_id" in rec.employee_id._fields and rec.employee_id.branch_id and rec.branch_id and rec.employee_id.branch_id != rec.branch_id:
                    raise ValidationError(_("Staff branch must match the linked Employee branch."))

    @api.constrains("termination_date", "hire_date")
    def _check_dates(self):
        """Validasi tanggal masuk/keluar."""
        for rec in self:
            if rec.termination_date and rec.hire_date and rec.termination_date < rec.hire_date:
                raise ValidationError(_("Termination Date cannot be earlier than Hire Date."))

    # =========================
    # Smart Button Actions
    # =========================
    def action_open_licenses(self):
        """Buka lisensi milik staff."""
        self.ensure_one()
        return {
            "name": _("Licenses"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.staff.license",
            "view_mode": "list,form",
            "domain": [("staff_id", "=", self.id)],
            "context": {"default_staff_id": self.id},
        }

    def action_open_rosters(self):
        """Buka roster/shift staff."""
        self.ensure_one()
        return {
            "name": _("Rosters"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.staff.roster",
            "view_mode": "calendar,list,form,gantt",
            "domain": [("staff_id", "=", self.id)],
            "context": {"default_staff_id": self.id},
        }

    def action_open_assignments(self):
        """Buka assignment staff."""
        self.ensure_one()
        return {
            "name": _("Assignments"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.staff.assignment",
            "view_mode": "list,form,kanban",
            "domain": [("staff_id", "=", self.id)],
            "context": {"default_staff_id": self.id},
        }

    def action_open_kpis(self):
        """Buka KPI staff."""
        self.ensure_one()
        return {
            "name": _("KPIs"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.staff.kpi",
            "view_mode": "list,form,graph,pivot",
            "domain": [("staff_id", "=", self.id)],
            "context": {"default_staff_id": self.id},
        }

    def action_open_incidents(self):
        """Buka insiden yang melibatkan staff."""
        self.ensure_one()
        return {
            "name": _("Incidents"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.incident",
            "view_mode": "list,form,kanban",
            "domain": [("involved_staff_ids", "in", self.id)],
            "context": {},
        }

    def action_open_postcare_tasks(self):
        """Buka tugas Post-Care yang ditugaskan ke staff."""
        self.ensure_one()
        return {
            "name": _("Post-Care Tasks"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.postcare.task",
            "view_mode": "list,form,kanban",
            "domain": [("assignee_id", "=", self.id)],
            "context": {},
        }

    def action_open_telemedicine_threads(self):
        """Buka thread Telemedicine yang ditangani staff."""
        self.ensure_one()
        return {
            "name": _("Telemedicine Threads"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.telemedicine.thread",
            "view_mode": "list,form,kanban",
            "domain": [("handler_id", "=", self.id)],
            "context": {},
        }

    # =========================
    # Business Helpers
    # =========================
    def toggle_active_operational(self):
        """Tombol bantu untuk mengaktifkan/nonaktifkan operasional staff."""
        for rec in self:
            rec.is_active = not rec.is_active

    def ensure_clinical_eligibility(self):
        """Validasi eligibility sebelum penjadwalan klinis (dipanggil dari wizard/cron)."""
        for rec in self:
            if not rec.can_be_scheduled:
                raise ValidationError(
                    _("Staff '%s' is not eligible for clinical scheduling.") % (rec.display_name,)
                )
        return True

