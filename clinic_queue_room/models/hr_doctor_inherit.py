# -*- coding: utf-8 -*-
# ClinicOne — Clinical Queue & Room Management (Odoo 18/19 CE)
# File: models/hr_doctor_inherit.py
# License: LGPL-3.0

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # -------------------------------------------------------------------------
    # Doctor Identity & Flags
    # -------------------------------------------------------------------------
    is_doctor = fields.Boolean(
        string="Is a Doctor",
        help="Enable this if the employee is a practicing clinician (doctor).",
        tracking=True,
    )
    doctor_code = fields.Char(
        string="Doctor Code",
        index=True,
        tracking=True,
        help="Unique code/identifier for the doctor within the company.",
    )
    license_number = fields.Char(
        string="Medical License Number",
        help="Official medical license number.",
        tracking=True,
    )
    license_expiry_date = fields.Date(
        string="License Expiry Date",
        help="Date when the medical license expires.",
        tracking=True,
    )
    board_certification = fields.Char(
        string="Board Certification",
        help="Board/college certification (free text).",
    )

    # -------------------------------------------------------------------------
    # Specialties & Skills (soft-coupled with clinic_doctor/clinic_hr)
    # -------------------------------------------------------------------------
    specialty_ids = fields.Many2many(
        comodel_name="clinic.specialty",
        relation="clinic_specialty_employee_rel",
        column1="employee_id",
        column2="specialty_id",
        string="Clinical Specialties",
        help="Clinical specialties of the doctor.",
    )
    skill_note = fields.Text(
        string="Skill Notes",
        help="Free text notes about clinical skills and scopes of practice.",
    )

    # -------------------------------------------------------------------------
    # Operational Availability & Capacity
    # -------------------------------------------------------------------------
    availability_status = fields.Selection(
        selection=[
            ("off_duty", "Off Duty"),
            ("on_call", "On Call"),
            ("on_duty", "On Duty"),
            ("in_service", "In Service"),
            ("on_break", "On Break"),
            ("unavailable", "Temporarily Unavailable"),
        ],
        string="Availability Status",
        default="off_duty",
        index=True,
        tracking=True,
        help="Operational availability used by queue assignment and routing.",
    )
    max_parallel_cases = fields.Integer(
        string="Max Parallel Cases",
        default=1,
        help="Maximum number of concurrent active cases the doctor is allowed to handle.",
    )
    is_available_for_queue = fields.Boolean(
        string="Available For Queue",
        compute="_compute_is_available_for_queue",
        help="True if doctor can take new cases based on availability and license validity.",
    )
    allow_auto_assignment = fields.Boolean(
        string="Allow Auto-Assignment",
        default=True,
        help="If enabled, the routing engine may auto-assign queues to this doctor.",
    )

    # -------------------------------------------------------------------------
    # Rooming & Devices (soft-coupled with clinic_room_* modules)
    # -------------------------------------------------------------------------
    preferred_room_type_ids = fields.Many2many(
        comodel_name="clinic.room.type",
        relation="clinic_doctor_room_type_rel",
        column1="employee_id",
        column2="room_type_id",
        string="Preferred Room Types",
        help="Room types where the doctor prefers to serve patients.",
    )

    qualified_device_ids = fields.Many2many(
        comodel_name="clinic.device",  # if your device model is clinic.room.device, change this to that model name
        relation="clinic_doctor_device_rel",
        column1="employee_id",
        column2="device_id",
        string="Qualified Devices",
        help="Devices that the doctor is qualified to operate.",
    )

    # -------------------------------------------------------------------------
    # Work Scheduling (uses standard HR fields; soft helpers)
    # -------------------------------------------------------------------------
    service_calendar_id = fields.Many2one(
        comodel_name="resource.calendar",
        string="Clinical Service Calendar",
        help="Work schedule used for clinical services (defaults to the employee's resource calendar).",
        default=lambda self: self.resource_calendar_id.id if self.resource_calendar_id else False,
    )
    default_appointment_slot_min = fields.Integer(
        string="Default Appointment Slot (min)",
        default=30,
        help="Default slot length for appointments, used by booking/kiosk.",
    )

    # -------------------------------------------------------------------------
    # Live Metrics / Operational Stats
    # -------------------------------------------------------------------------
    queue_active_count = fields.Integer(
        string="Active Queues",
        compute="_compute_queue_stats",
        help="Number of active queues (Waiting/In Progress/On Hold) handled by this doctor.",
    )
    queue_today_count = fields.Integer(
        string="Queues Today",
        compute="_compute_queue_stats",
        help="Total queues created today assigned to this doctor.",
    )
    queue_waiting_count = fields.Integer(
        string="Waiting Patients",
        compute="_compute_queue_stats",
        help="Number of waiting queues currently assigned to this doctor.",
    )
    assignment_active_count = fields.Integer(
        string="Active Room Assignments",
        compute="_compute_assignment_stats",
        help="Number of active room assignments for this doctor.",
    )
    next_appointment_id = fields.Many2one(
        comodel_name="clinic.appointment",
        string="Next Appointment",
        compute="_compute_next_appointment",
        help="Nearest upcoming appointment for this doctor.",
    )

    # -------------------------------------------------------------------------
    # Billing / Analytics Hooks (soft-coupled)
    # -------------------------------------------------------------------------
    analytic_account_id = fields.Many2one(
        comodel_name="account.analytic.account",
        string="Analytic Account",
        help="Default analytic account to attribute revenue/cost for this doctor.",
    )
    commission_percent = fields.Float(
        string="Commission %",
        default=0.0,
        help="Default commission percent for this doctor (used by pricing/billing automation).",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    _doctor_code_company_uniq = models.Constraint(
        "unique(company_id, doctor_code)",
        "Doctor Code must be unique per company.",
    )
    _max_parallel_cases_nonneg = models.Constraint(
        "CHECK (max_parallel_cases >= 0)",
        "Max Parallel Cases cannot be negative.",
    )

    @api.constrains("is_doctor", "license_expiry_date")
    def _check_license_validity(self):
        for rec in self:
            if rec.is_doctor and rec.license_expiry_date and rec.license_expiry_date < fields.Date.context_today(self):
                raise ValidationError(_("Medical license is expired for doctor %s.") % (rec.name or rec.display_name))

    # -------------------------------------------------------------------------
    # Computes
    # -------------------------------------------------------------------------
    @api.depends("availability_status", "license_expiry_date", "is_doctor", "max_parallel_cases")
    def _compute_is_available_for_queue(self):
        today = fields.Date.context_today(self)
        for rec in self:
            license_ok = (not rec.license_expiry_date) or (rec.license_expiry_date >= today)
            status_ok = rec.availability_status in ("on_call", "on_duty")
            capacity_ok = (rec.max_parallel_cases or 0) >= 1
            rec.is_available_for_queue = bool(rec.is_doctor and license_ok and status_ok and capacity_ok)

    @api.depends("company_id")
    def _compute_queue_stats(self):
        """
        Compute counts using read_group for performance:
        - Active queues: state in waiting/in_progress/on_hold
        - Queues today: checkin_date == today
        - Waiting queues: state == waiting
        """
        Queue = self.env["clinic.queue"]
        today = fields.Date.context_today(self)

        # Init zeros
        for d in self:
            d.queue_active_count = d.queue_today_count = d.queue_waiting_count = 0

        doctors = self.filtered(lambda e: e.is_doctor and e.id)
        if not doctors:
            return

        doc_ids = doctors.ids
        company_id = self.env.company.id

        def map_counts(domain):
            rows = Queue._read_group(
                domain=domain,
                groupby=["doctor_id"],
                aggregates=["__count"],
            )
            return {doctor.id: count for doctor, count in rows if doctor}

        # Active
        active_domain = [
            ("doctor_id", "in", doc_ids),
            ("company_id", "=", company_id),
            ("state", "in", ["waiting", "in_progress", "on_hold"]),
        ]
        active_map = map_counts(active_domain)

        # Today
        today_domain = [
            ("doctor_id", "in", doc_ids),
            ("company_id", "=", company_id),
            ("checkin_time", ">=", fields.Datetime.to_datetime(f"{today} 00:00:00")),
            ("checkin_time", "<=", fields.Datetime.to_datetime(f"{today} 23:59:59")),
        ]
        today_map = map_counts(today_domain)

        # Waiting
        waiting_domain = [
            ("doctor_id", "in", doc_ids),
            ("company_id", "=", company_id),
            ("state", "=", "waiting"),
        ]
        waiting_map = map_counts(waiting_domain)

        for d in doctors:
            d.queue_active_count = int(active_map.get(d.id, 0))
            d.queue_today_count = int(today_map.get(d.id, 0))
            d.queue_waiting_count = int(waiting_map.get(d.id, 0))

    @api.depends("company_id")
    def _compute_assignment_stats(self):
        """
        Active room assignments for this doctor.
        clinic.room.assignment stores doctor_id as related(queue_id.doctor_id) [store=True].
        """
        Assign = self.env["clinic.room.assignment"]
        for d in self:
            if not d.is_doctor or not d.id:
                d.assignment_active_count = 0
                continue
            dom = [
                ("doctor_id", "=", d.id),
                ("company_id", "=", self.env.company.id),
                ("released_at", "=", False),
                ("active", "=", True),
            ]
            d.assignment_active_count = Assign.search_count(dom)

    @api.depends("company_id")
    def _compute_next_appointment(self):
        """
        Next upcoming appointment for doctor. We try common date fields.
        """
        App = self.env["clinic.appointment"]
        start_field = "start_datetime" if "start_datetime" in App._fields else \
                      ("start_time" if "start_time" in App._fields else None)
        now = fields.Datetime.now()
        for d in self:
            d.next_appointment_id = False
            if not d.is_doctor or not d.id or not start_field:
                continue
            dom = [
                ("doctor_id", "=", d.id),
                ("company_id", "=", self.env.company.id),
                (start_field, ">", now),
            ]
            nxt = App.search(dom, limit=1, order=f"{start_field} asc, id asc")
            if nxt:
                d.next_appointment_id = nxt.id

    # -------------------------------------------------------------------------
    # Business Helpers
    # -------------------------------------------------------------------------
    def can_take_new_case(self):
        """
        Check if doctor can take a new active case considering availability and current load.
        """
        self.ensure_one()
        if not self.is_available_for_queue:
            return False
        # Capacity check via active queues
        if self.max_parallel_cases:
            if self.queue_active_count >= self.max_parallel_cases:
                return False
        return True

    def action_set_on_duty(self):
        for rec in self:
            rec.write({"availability_status": "on_duty"})
            rec.message_post(body=_("Doctor set to <b>On Duty</b>."))
        return True

    def action_set_on_call(self):
        for rec in self:
            rec.write({"availability_status": "on_call"})
            rec.message_post(body=_("Doctor set to <b>On Call</b>."))
        return True

    def action_set_on_break(self):
        for rec in self:
            rec.write({"availability_status": "on_break"})
            rec.message_post(body=_("Doctor set to <b>On Break</b>."))
        return True

    def action_set_in_service(self):
        for rec in self:
            rec.write({"availability_status": "in_service"})
            rec.message_post(body=_("Doctor set to <b>In Service</b>."))
        return True

    def action_set_off_duty(self):
        for rec in self:
            rec.write({"availability_status": "off_duty"})
            rec.message_post(body=_("Doctor set to <b>Off Duty</b>."))
        return True

    # -------------------------------------------------------------------------
    # UI Actions (Smart Buttons / Menu)
    # -------------------------------------------------------------------------
    def action_view_queues(self):
        self.ensure_one()
        action = self.env.ref("clinic_queue_room.action_clinic_queue_tree", raise_if_not_found=False)
        domain = [("doctor_id", "=", self.id)]
        if action:
            res = action.read()[0]
            res.update({"domain": domain, "context": {"search_default_active_states": 1}})
            return res
        return {
            "type": "ir.actions.act_window",
            "name": _("Queues"),
            "res_model": "clinic.queue",
            "view_mode": "list,form,kanban",
            "domain": domain,
        }

    def action_view_active_queues(self):
        self.ensure_one()
        action = self.env.ref("clinic_queue_room.action_clinic_queue_tree", raise_if_not_found=False)
        domain = [("doctor_id", "=", self.id), ("state", "in", ["waiting", "in_progress", "on_hold"])]
        if action:
            res = action.read()[0]
            res.update({"domain": domain})
            return res
        return {
            "type": "ir.actions.act_window",
            "name": _("Active Queues"),
            "res_model": "clinic.queue",
            "view_mode": "list,form,kanban",
            "domain": domain,
        }

    def action_view_room_assignments(self):
        self.ensure_one()
        action = self.env.ref("clinic_queue_room.action_clinic_room_assignment_tree", raise_if_not_found=False)
        domain = [("doctor_id", "=", self.id), ("released_at", "=", False)]
        if action:
            res = action.read()[0]
            res.update({"domain": domain})
            return res
        return {
            "type": "ir.actions.act_window",
            "name": _("Room Assignments"),
            "res_model": "clinic.room.assignment",
            "view_mode": "list,form",
            "domain": domain,
        }

    def action_view_next_appointment(self):
        self.ensure_one()
        if not self.next_appointment_id:
            raise UserError(_("No upcoming appointment found for this doctor."))
        act = self.env.ref("clinic_queue_room.action_clinic_appointment_form", raise_if_not_found=False)
        if act:
            data = act.read()[0]
            data.update({"res_id": self.next_appointment_id.id, "view_mode": "form"})
            return data
        return {
            "type": "ir.actions.act_window",
            "name": _("Appointment"),
            "res_model": "clinic.appointment",
            "view_mode": "form,list",
            "res_id": self.next_appointment_id.id,
            "target": "current",
        }

    def action_open_schedule(self):
        """Open the calendar view (resource calendar) for this doctor if configured."""
        self.ensure_one()
        if not self.service_calendar_id:
            raise UserError(_("No Clinical Service Calendar is set for this doctor."))
        action = self.env.ref("hr_holidays.action_hr_employee_schedule", raise_if_not_found=False)
        if action:
            data = action.read()[0]
            return data
        return {
            "type": "ir.actions.act_window",
            "name": _("Calendar"),
            "res_model": "resource.calendar",
            "view_mode": "form,list",
            "res_id": self.service_calendar_id.id,
        }

    # -------------------------------------------------------------------------
    # CRUD Overrides (Light)
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            if rec.is_doctor and not rec.doctor_code:
                seq = self.env["ir.sequence"].next_by_code("clinic.doctor.code") or False
                rec.doctor_code = seq or (f"D-{rec.id:05d}")
        return recs

    def write(self, vals):
        if "doctor_code" in vals and vals["doctor_code"]:
            vals["doctor_code"] = (vals["doctor_code"] or "").strip().upper()
        return super().write(vals)

    # -------------------------------------------------------------------------
    # Display Helpers (Odoo 19)
    # -------------------------------------------------------------------------
    @api.depends("name", "is_doctor", "doctor_code")
    def _compute_display_name(self):
        super()._compute_display_name()
        for rec in self:
            if rec.is_doctor and rec.doctor_code:
                rec.display_name = f"{rec.display_name} [{rec.doctor_code}]"

    def name_get(self):
        """Compatibility wrapper for older ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]
