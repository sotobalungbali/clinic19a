

# -*- coding: utf-8 -*-
# File: clinic_doctor/models/doctor.py
# Module: clinic_doctor
#
# Core model for Doctor Management & Scheduling in ClinicOne (Odoo 19 CE ready).
#
# Design goals:
# - Keep this core model lean and stable; avoid hard dependencies on non-core apps.
# - Use res.partner as the primary identity (contacts, portal, comms).
# - Room awareness is provided via clinic_queue_room (clinic.room).
# - Rich, but optional, cross-module integrations via guarded env checks and hook methods.
#
# Notes:
# - HR/Payroll linkage is provided by the bridge module "clinic_doctor_hr" (employee_id, strict mode, sync).
# - Treatment/Billing/Inventory/etc. may extend this model or consume it; we keep optional references via actions/hooks.
# - All strings are in English per the product requirement.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicDoctor(models.Model):
    _name = "clinic.doctor"
    _description = "Doctor"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name, id"

    # -------------------------------------------------------------------------
    # CORE LINKS & IDENTITY
    # -------------------------------------------------------------------------
    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        help="Linked contact for this doctor. The contact should represent an individual person."
    )
    user_id = fields.Many2one(
        "res.users",
        ondelete="set null",
        tracking=True,
        help="Optional system user associated with the doctor for calendar/portal/back-office access."
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
        help="Company that this doctor belongs to."
    )

    staff_id = fields.Many2one(
        "clinic.staff",
        string="Linked Staff",
        ondelete="restrict",
        index=True,
        tracking=True,
        help="ClinicOne Staff identity representing this doctor for workforce and provider operations.",
    )
    branch_id = fields.Many2one(
        "clinic.branch",
        string="Branch",
        related="staff_id.branch_id",
        store=True,
        readonly=True,
        index=True,
        help="Operational branch inherited from the linked Staff identity.",
    )

    # Mirror partner's name for fast search/sort
    name = fields.Char(
        related="partner_id.name",
        store=True,
        readonly=True,
        help="Display name of the doctor (mirrors the linked contact's name)."
    )

    # Professional identity
    license_no = fields.Char(
        required=True,
        index=True,
        tracking=True,
        help="Professional license number of the doctor; must be unique per company."
    )
    license_authority = fields.Char(
        help="Issuing authority/board of the professional license."
    )
    specialty_ids = fields.Many2many(
        "clinic.specialty",
        "clinic_doctor_specialty_rel",   # relation table must match the one used in clinic.specialty
        "doctor_id",
        "specialty_id",
        string="Specialties",
        help="Medical specialties practiced by this doctor."
    )
    seniority_level = fields.Selection(
        [
            ("resident", "Resident"),
            ("junior", "Junior"),
            ("senior", "Senior"),
            ("consultant", "Consultant"),
        ],
        default="junior",
        tracking=True,
        help="Seniority level used for scheduling priority, pricing policies, or reporting."
    )

    # Profile flags (kept generic to avoid hard depends)
    allow_portal_booking = fields.Boolean(
        default=False,
        help="If enabled, the doctor can be exposed for patient self-service booking on the portal."
    )
    telemedicine_enabled = fields.Boolean(
        default=False,
        help="If enabled, the doctor supports telemedicine/remote consultations."
    )
    rating_enabled = fields.Boolean(
        default=False,
        help="If enabled and rating module(s) are installed, patients can submit ratings for the doctor."
    )

    # -------------------------------------------------------------------------
    # CONTACT (RELATED FROM PARTNER) & PRESENTATION
    # -------------------------------------------------------------------------
    work_email = fields.Char(related="partner_id.email", string="Email", store=True, readonly=True)
    work_phone = fields.Char(related="partner_id.phone", string="Phone", store=True, readonly=True)
    mobile = fields.Char(related="partner_id.phone", string="Mobile", store=True, readonly=True)
    street = fields.Char(related="partner_id.street", store=True, readonly=True)
    city = fields.Char(related="partner_id.city", store=True, readonly=True)
    state_id = fields.Many2one(related="partner_id.state_id", store=True, readonly=True)
    zip = fields.Char(related="partner_id.zip", store=True, readonly=True)
    country_id = fields.Many2one(related="partner_id.country_id", store=True, readonly=True)
    image_1920 = fields.Image(related="partner_id.image_1920", readonly=True)
    color = fields.Integer(
        help="Color index used in kanban/calendar views to visually distinguish doctors."
    )
    notes = fields.Text(
        help="Internal notes such as credentials, languages, or procedure preferences."
    )

    # -------------------------------------------------------------------------
    # SCHEDULING & AVAILABILITY
    # -------------------------------------------------------------------------
    calendar_id = fields.Many2one(
        "resource.calendar",
        string="Working Hours",
        help="Working hours template used to compute default availability patterns."
    )
    default_room_id = fields.Many2one(
        "clinic.room",
        ondelete="set null",
        help="Preferred room for this doctor when scheduling appointments or treatments."
    )
    capacity_per_slot = fields.Integer(
        default=1,
        tracking=True,
        help="Maximum number of concurrent patients allowed per time slot for this doctor."
    )
    min_lead_time_hours = fields.Integer(
        default=0,
        help="Minimum lead time (in hours) required before a new booking can be made."
    )
    max_lead_time_days = fields.Integer(
        default=180,
        help="Maximum lead time (in days) allowed for future bookings."
    )

    schedule_rule_ids = fields.One2many(
        "clinic.schedule.rule",
        "doctor_id",
        string="Schedule Rules",
        help="Weekly/recurring templates that generate concrete availability slots."
    )
    availability_slot_ids = fields.One2many(
        "clinic.availability.slot",
        "doctor_id",
        string="Availability Slots",
        help="Concrete generated availability slots ready for booking."
    )
    leave_ids = fields.One2many(
        "clinic.doctor.leave",
        "doctor_id",
        string="Leaves",
        help="Leaves/holidays/blackout periods during which the doctor is not available."
    )

    # High-level state & next availability
    availability_state = fields.Selection(
        [
            ("available", "Available"),
            ("on_leave", "On Leave"),
            ("inactive", "Inactive"),
            ("unknown", "Unknown"),
        ],
        compute="_compute_availability_state",
        store=False,
        help="High-level availability indicator for quick triage and scheduling."
    )
    next_available_slot = fields.Datetime(
        compute="_compute_next_available_slot",
        store=False,
        help="Next available time slot for this doctor (server time)."
    )

    # -------------------------------------------------------------------------
    # APPOINTMENT & TREATMENT INTEGRATIONS (COUNTERS)
    # -------------------------------------------------------------------------
    # appointment_ids = fields.One2many(
    #     "clinic.appointment",
    #     "doctor_id",
    #     string="Appointments",
    #     help="Appointments linked to this doctor."
    # )
    # appointment_count = fields.Integer(
    #     compute="_compute_counts",
    #     store=False,
    #     help="Number of appointments for this doctor (all states)."
    # )
    # open_appointment_count = fields.Integer(
    #     compute="_compute_counts",
    #     store=False,
    #     help="Number of non-closed appointments (e.g., draft/confirmed/checked-in/in-treatment)."
    # )
    # treatment_count = fields.Integer(
    #     compute="_compute_counts",
    #     store=False,
    #     help="Number of treatment sessions associated to this doctor (if the model exists)."
    # )

    # Optional KPI placeholders (other modules may update/write these)
    kpi_utilization_rate = fields.Float(
        digits=(16, 2),
        help="Utilization rate (%) within the configured reporting window (maintained by reports/jobs)."
    )
    kpi_no_show_rate = fields.Float(
        digits=(16, 2),
        help="No-show rate (%) within the configured reporting window (maintained by reports/jobs)."
    )
    
    # dari patient_link.py \\\///
    patient_ids = fields.Many2many(
        "clinic.patient",
        "clinic_patient_doctor_rel",      # same M2M table
        "doctor_id",
        "patient_id",
        string="Patients",
        help="Patients that marked this doctor as preferred (or primary)."
    )
    patient_count = fields.Integer(
        compute="_compute_patient_count",
        store=False,
        help="Number of patients that prefer this doctor."
    )

    def _compute_patient_count(self):
        for rec in self:
            rec.patient_count = len(rec.patient_ids)

    def action_view_patients(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patients"),
            "res_model": "clinic.patient",
            "view_mode": "list,form,kanban",
            "domain": [("id", "in", self.patient_ids.ids)],
            "target": "current",
        }

    def action_view_primary_patients(self):
        """Open patients for whom this doctor is the primary doctor."""
        self.ensure_one()
        Patient = self.env["clinic.patient"]
        if "primary_doctor_id" not in Patient._fields:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Primary Doctor Link Not Available"),
                    "message": _(
                        "The installed Clinic Patient model does not provide "
                        "the optional primary_doctor_id field."
                    ),
                    "sticky": False,
                },
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Primary Patients"),
            "res_model": "clinic.patient",
            "view_mode": "list,form,kanban",
            "domain": [("primary_doctor_id", "=", self.id)],
            "target": "current",
        }
    # dari patient_link.py ///\\\

    # dari file queue.py \\\///
    # queue_waiting_count = fields.Integer(
    #     compute="_compute_queue_counts",
    #     store=False,
    #     help="Number of waiting queue tokens for this doctor."
    # )
    # queue_in_service_count = fields.Integer(
    #     compute="_compute_queue_counts",
    #     store=False,
    #     help="Number of in-service queue tokens for this doctor."
    # )
    # last_queue_token_id = fields.Many2one(
    #     "clinic.queue.token",
    #     compute="_compute_queue_counts",
    #     store=False,
    #     help="Most recent queue token for this doctor."
    # )

    # def _compute_queue_counts(self):
    #     Token = self.env["clinic.queue.token"] if "clinic.queue.token" in self.env else False
    #     for rec in self:
    #         rec.queue_waiting_count = 0
    #         rec.queue_in_service_count = 0
    #         rec.last_queue_token_id = False
    #         if not Token or "doctor_id" not in Token._fields:
    #             continue

    #         dom_base = [("doctor_id", "=", rec.id)]
    #         # Waiting: states that represent belum dipanggil/menunggu
    #         dom_wait = dom_base + [("state", "in", ["new", "waiting", "queued", "called"])] if "state" in Token._fields else dom_base
    #         # In service
    #         dom_srv = dom_base + [("state", "in", ["in_service", "serving"])] if "state" in Token._fields else dom_base

    #         rec.queue_waiting_count = Token.search_count(dom_wait)
    #         rec.queue_in_service_count = Token.search_count(dom_srv)

    #         # Last token (by write_date/create_date)
    #         token_last = Token.search(dom_base, order="write_date desc, create_date desc", limit=1)
    #         rec.last_queue_token_id = token_last.id if token_last else False

    # Actions (open tokens by state)
    # def action_view_queue_tokens(self):
    #     self.ensure_one()
    #     if "clinic.queue.token" not in self.env:
    #         return {
    #             "type": "ir.actions.client",
    #             "tag": "display_notification",
    #             "params": {"title": _("Not Available"),
    #                        "message": _("Queue module is not installed."),
    #                        "sticky": False},
    #         }
    #     domain = [("doctor_id", "=", self.id)]
    #     return {
    #         "type": "ir.actions.act_window",
    #         "name": _("Queue Tokens"),
    #         "res_model": "clinic.queue.token",
    #         "view_mode": "list,form,kanban",
    #         "domain": domain,
    #         "target": "current",
    #         "context": {"search_default_doctor_id": self.id},
    #     }

    # def action_view_waiting_tokens(self):
    #     self.ensure_one()
    #     if "clinic.queue.token" not in self.env:
    #         return {"type": "ir.actions.client", "tag": "display_notification",
    #                 "params": {"title": _("Not Available"), "message": _("Queue module is not installed."), "sticky": False}}
    #     domain = [("doctor_id", "=", self.id)]
    #     if "state" in self.env["clinic.queue.token"]._fields:
    #         domain += [("state", "in", ["new", "waiting", "queued", "called"])]
    #     return {
    #         "type": "ir.actions.act_window",
    #         "name": _("Waiting Tokens"),
    #         "res_model": "clinic.queue.token",
    #         "view_mode": "list,form,kanban",
    #         "domain": domain,
    #         "target": "current",
    #     }

    # def action_view_in_service_tokens(self):
    #     self.ensure_one()
    #     if "clinic.queue.token" not in self.env:
    #         return {"type": "ir.actions.client", "tag": "display_notification",
    #                 "params": {"title": _("Not Available"), "message": _("Queue module is not installed."), "sticky": False}}
    #     domain = [("doctor_id", "=", self.id)]
    #     if "state" in self.env["clinic.queue.token"]._fields:
    #         domain += [("state", "in", ["in_service", "serving"])]
    #     return {
    #         "type": "ir.actions.act_window",
    #         "name": _("In-service Tokens"),
    #         "res_model": "clinic.queue.token",
    #         "view_mode": "list,form,kanban",
    #         "domain": domain,
    #         "target": "current",
    #     }
    # dari file queue.py ///\\\

    # -------------------------------------------------------------------------
    # LIFECYCLE
    # -------------------------------------------------------------------------
    active = fields.Boolean(
        default=True,
        help="Deactivating a doctor hides it from selection and new scheduling, "
             "but preserves historical data."
    )

    _license_company_uniq = models.Constraint(
        "UNIQUE (license_no, company_id)",
        "License number must be unique per company.",
    )
    _partner_company_uniq = models.Constraint(
        "UNIQUE (partner_id, company_id)",
        "A doctor for the same contact already exists in this company.",
    )

    _staff_unique = models.Constraint(
        "UNIQUE (staff_id)",
        "A Staff identity can only be linked to one Doctor record.",
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    # @api.depends("appointment_ids.state")
    # def _compute_counts(self):
    #     """Compute appointment/treatment counters via read_group (fast & safe)."""
    #     Appointment = self.env["clinic.appointment"]

    #     # All appointments
    #     groups_all = Appointment.read_group(
    #         [("doctor_id", "in", self.ids)],
    #         ["doctor_id"],
    #         ["doctor_id"],
    #     )
    #     count_all_map = {g["doctor_id"][0]: g["doctor_id_count"] for g in groups_all}

    #     # Open appointments (exclude terminal states)
    #     groups_open = Appointment.read_group(
    #         [("doctor_id", "in", self.ids), ("state", "not in", ["canceled", "done", "no_show"])],
    #         ["doctor_id"],
    #         ["doctor_id"],
    #     )
    #     count_open_map = {g["doctor_id"][0]: g["doctor_id_count"] for g in groups_open}

    #     # Treatment sessions (optional model)
    #     treatment_map = {}
    #     if "clinic.procedure.session" in self.env:
    #         t_groups = self.env["clinic.procedure.session"].read_group(
    #             [("doctor_id", "in", self.ids)], ["doctor_id"], ["doctor_id"]
    #         )
    #         treatment_map = {g["doctor_id"][0]: g["doctor_id_count"] for g in t_groups}

    #     for rec in self:
    #         rec.appointment_count = count_all_map.get(rec.id, 0)
    #         rec.open_appointment_count = count_open_map.get(rec.id, 0)
    #         rec.treatment_count = treatment_map.get(rec.id, 0)

    def _compute_next_available_slot(self):
        """Find the earliest open availability slot from now."""
        Slot = self.env["clinic.availability.slot"]
        now = fields.Datetime.now()
        for rec in self:
            next_slot = Slot.search([
                ("doctor_id", "=", rec.id),
                ("state", "=", "open"),
                ("start", ">=", now),
            ], order="start asc", limit=1)
            rec.next_available_slot = next_slot.start if next_slot else False

    def _compute_availability_state(self):
        """Coarse availability based on active flag, overlapping leave, and presence of schedule/slots."""
        now = fields.Datetime.now()
        for rec in self:
            if not rec.active:
                rec.availability_state = "inactive"
                continue
            # On leave if any leave covers now
            leave_now = rec.leave_ids.filtered(
                lambda l: (not l.date_from or l.date_from <= now) and (not l.date_to or l.date_to >= now)
            )
            if leave_now:
                rec.availability_state = "on_leave"
            elif not rec.schedule_rule_ids and not rec.availability_slot_ids:
                rec.availability_state = "unknown"
            else:
                rec.availability_state = "available"

    # -------------------------------------------------------------------------
    # PY CONSTRAINTS & ONCHANGES
    # -------------------------------------------------------------------------
    @api.constrains("staff_id", "partner_id", "user_id", "company_id")
    def _check_staff_identity_consistency(self):
        """A Doctor and its linked Staff must describe the same person/company."""
        for rec in self:
            if not rec.staff_id:
                continue
            staff = rec.staff_id
            if staff.role != "doctor":
                raise ValidationError(_("Linked Staff must have the Doctor role."))
            if staff.partner_id != rec.partner_id:
                raise ValidationError(_("Doctor Contact must match the linked Staff Contact."))
            if staff.company_id and rec.company_id and staff.company_id != rec.company_id:
                raise ValidationError(_("Doctor company must match the linked Staff company."))
            if rec.user_id or staff.user_id:
                if rec.user_id != staff.user_id:
                    raise ValidationError(_("Doctor System User must match the linked Staff System User."))
            if staff.branch_id and staff.branch_id.company_id != rec.company_id:
                raise ValidationError(_("Doctor Staff branch must belong to the Doctor company."))

    @api.constrains("capacity_per_slot")
    def _check_capacity(self):
        for rec in self:
            if rec.capacity_per_slot < 1:
                raise ValidationError(_("Capacity per slot must be at least 1."))

    @api.constrains("min_lead_time_hours", "max_lead_time_days")
    def _check_lead_times(self):
        for rec in self:
            if rec.min_lead_time_hours < 0:
                raise ValidationError(_("Minimum lead time cannot be negative."))
            if rec.max_lead_time_days < 0:
                raise ValidationError(_("Maximum lead time cannot be negative."))

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id and self.partner_id.is_company:
            return {
                "warning": {
                    "title": _("Contact is a Company"),
                    "message": _("The linked contact is a company. "
                                 "It is recommended to use an individual contact for a doctor.")
                }
            }

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            # Mark partner as doctor if the custom flag exists on res.partner
            if rec.partner_id and "is_doctor" in rec.partner_id._fields:
                rec.partner_id.sudo().write({"is_doctor": True})

            # Auto-subscribe the associated user/partner for chatter
            partner_ids = []
            if rec.partner_id:
                partner_ids.append(rec.partner_id.id)
            if rec.user_id and rec.user_id.partner_id:
                partner_ids.append(rec.user_id.partner_id.id)
            if partner_ids:
                rec.message_subscribe(partner_ids=list(set(partner_ids)))

            # Hook for bridge modules (e.g., HR auto-create, marketing profile, etc.)
            rec._post_create_integrations_hook()
        return records

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            # Keep partner doctor flag in sync if present
            if rec.partner_id and "is_doctor" in rec.partner_id._fields:
                rec.partner_id.sudo().write({"is_doctor": True})

            # Let bridge modules react to updates (sync to employee, pricing cache, etc.)
            rec._post_write_integrations_hook(vals)
        return res

    # def unlink(self):
    #     # Prevent deletion when linked to any (non-canceled) appointment to keep integrity
    #     blocked = self.env["clinic.appointment"].search_count([
    #         ("doctor_id", "in", self.ids),
    #         ("state", "!=", "canceled"),
    #     ])
    #     if blocked:
    #         raise UserError(_(
    #             "You cannot delete a doctor that has related appointments. "
    #             "Consider deactivating the doctor instead."
    #         ))

    #     # Give bridges a chance to clean downstream references
    #     for rec in self:
    #         rec._pre_unlink_integrations_hook()

    #     return super().unlink()

    # -------------------------------------------------------------------------
    # INTEGRATION HOOKS (to be overridden by bridge modules)
    # -------------------------------------------------------------------------
    def _post_create_integrations_hook(self):
        """
        Hook for bridge modules to react after Doctor creation.
        Example bridges:
          - clinic_doctor_hr: auto-create hr.employee, enforce strict HR policy.
          - clinic_marketing: initialize UTM/segments, opt-ins.
          - clinic_portal: set portal access or welcome message.
        """
        # Intentionally empty in core. Bridges may override.
        return True

    def _post_write_integrations_hook(self, vals):
        """
        Hook for bridge modules to react to Doctor updates.
        Example bridges:
          - Sync user/employee data.
          - Invalidate availability caches or pricing caches.
        """
        # Intentionally empty in core. Bridges may override.
        return True

    def _pre_unlink_integrations_hook(self):
        """
        Hook for bridge modules to clean related resources before deletion.
        Example bridges:
          - Remove marketing subscriptions or external identities.
        """
        # Intentionally empty in core. Bridges may override.
        return True

    # -------------------------------------------------------------------------
    # ACTIONS (UI HELPERS)
    # -------------------------------------------------------------------------
    # def action_view_appointments(self):
    #     """Open the doctor's appointments."""
    #     self.ensure_one()
    #     return {
    #         "type": "ir.actions.act_window",
    #         "name": _("Appointments"),
    #         "res_model": "clinic.appointment",
    #         "view_mode": "calendar,list,form,pivot,graph",
    #         "domain": [("doctor_id", "=", self.id)],
    #         "context": {
    #             "default_doctor_id": self.id,
    #         },
    #         "target": "current",
    #     }

    def action_view_schedule_rules(self):
        """Open schedule rules for this doctor."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Schedule Rules"),
            "res_model": "clinic.schedule.rule",
            "view_mode": "list,form,calendar",
            "domain": [("doctor_id", "=", self.id)],
            "context": {"default_doctor_id": self.id},
            "target": "current",
        }

    def action_view_availability(self):
        """Open availability slots for this doctor."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Availability"),
            "res_model": "clinic.availability.slot",
            "view_mode": "calendar,list,form",
            "domain": [("doctor_id", "=", self.id)],
            "context": {"default_doctor_id": self.id},
            "target": "current",
        }

    def action_view_next_available_slot(self):
        """Jump to calendar filtered on the next available slot."""
        self.ensure_one()
        domain = [("doctor_id", "=", self.id)]
        if self.next_available_slot:
            domain.append(("start", ">=", self.next_available_slot))
        return {
            "type": "ir.actions.act_window",
            "name": _("Next Availability"),
            "res_model": "clinic.availability.slot",
            "view_mode": "calendar,list,form",
            "domain": domain,
            "target": "current",
        }

    def action_view_leaves(self):
        """Open the doctor's leaves/blackouts."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Leaves"),
            "res_model": "clinic.doctor.leave",
            "view_mode": "list,form,calendar",
            "domain": [("doctor_id", "=", self.id)],
            "context": {"default_doctor_id": self.id},
            "target": "current",
        }

    # def action_view_treatments(self):
    #     """Open treatments handled by this doctor (if the model exists)."""
    #     self.ensure_one()
    #     model_name = "clinic.procedure.session"
    #     if model_name not in self.env:
    #         return {
    #             "type": "ir.actions.client",
    #             "tag": "display_notification",
    #             "params": {
    #                 "title": _("Not Available"),
    #                 "message": _("Treatment module is not installed."),
    #                 "sticky": False,
    #             },
    #         }
    #     return {
    #         "type": "ir.actions.act_window",
    #         "name": _("Treatment Sessions"),
    #         "res_model": model_name,
    #         "view_mode": "list,form,kanban,pivot,graph",
    #         "domain": [("doctor_id", "=", self.id)],
    #         "target": "current",
    #     }

    def action_quick_create_appointment(self):
        """
        Open the quick create appointment wizard (if available).
        """
        self.ensure_one()
        model_name = "clinic.quick.create.appointment.wizard"
        if model_name not in self.env:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Wizard Not Installed"),
                    "message": _("Quick Create Appointment wizard is not available."),
                    "sticky": False,
                },
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Quick Create Appointment"),
            "res_model": model_name,
            "view_mode": "form",
            "target": "new",
            "context": {"default_doctor_id": self.id},
        }

    # -------------------------------------------------------------------------
    # DISPLAY
    # -------------------------------------------------------------------------
    @api.depends("name", "license_no")
    def _compute_display_name(self):
        """Preserve ClinicOne doctor labels through the Odoo 19 display-name API."""
        for rec in self:
            display = rec.name or _("Unnamed")
            if rec.license_no:
                display = f"{display} [{rec.license_no}]"
            rec.display_name = display

    def name_get(self):
        """Compatibility wrapper for existing ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        """Improve search by license number and partner name (Odoo 19 signature)."""
        domain = list(domain or [])
        if name:
            domain = ["|", ("license_no", operator, name), ("name", operator, name)] + domain
        records = self.search(domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in records.sudo()]

