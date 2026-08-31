

# -*- coding: utf-8 -*-
# File: clinic_doctor/models/leave.py
# Module: clinic_doctor
#
# ClinicOne — Doctor Leave / Blackout (Odoo 19 CE ready)
#
# Purpose
# -------
# Manage doctor leaves/blackout windows which affect:
# - Schedule Rule generation (rules skip occurrences that hit leaves)
# - Availability Slots (block/close/delete-open policy on approval)
# - Appointments (optional: notify/cancel/flag for reschedule)
# - Calendar leaves (optional: propagate to resource calendar)
# - HR leave (optional: sync to hr.leave via clinic_doctor_hr bridge)
#
# Notes
# -----
# * All labels/help/messages in English.
# * Uses mail.thread/activity for collaboration & audit trail.
# * Multi-company aware.
# * Safe cross-module behavior via presence checks and config parameters.

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


LEAVE_STATE = [
    ("draft", "Draft"),
    ("confirm", "Confirmed"),
    ("approve", "Approved"),
    ("refuse", "Refused"),
    ("cancel", "Cancelled"),
]

LEAVE_REASON = [
    ("vacation", "Vacation / Annual Leave"),
    ("sick", "Sick Leave"),
    ("training", "Training / Conference"),
    ("personal", "Personal Matters"),
    ("maintenance", "Facility Maintenance"),
    ("other", "Other"),
]

SLOT_POLICY = [
    ("block", "Block overlapping slots"),
    ("close", "Close overlapping slots"),
    ("delete_open", "Delete open & empty slots only"),
]

APPOINTMENT_POLICY = [
    ("notify", "Notify & flag for reschedule"),
    ("cancel", "Cancel overlapping appointments"),
    ("nothing", "Do nothing"),
]


class ClinicDoctorLeave(models.Model):
    _name = "clinic.doctor.leave"
    _description = "Doctor Leave / Blackout"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_from asc, doctor_id, id"

    # -------------------------------------------------------------------------
    # IDENTITY & SCOPE
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Subject",
        tracking=True,
        help="Short description of the leave (e.g., Annual Leave, Sick Leave)."
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
        help="Doctor who is on leave."
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        help="Company this leave belongs to."
    )
    reason = fields.Selection(
        LEAVE_REASON,
        default="other",
        tracking=True,
        help="Purpose/category of the leave."
    )
    details = fields.Text(
        string="Details",
        help="Additional information about the leave."
    )
    color = fields.Integer(
        help="Color index for quick visual reference in list/kanban views."
    )

    # -------------------------------------------------------------------------
    # TIME WINDOW (UTC naive datetimes, as per Odoo storage)
    # -------------------------------------------------------------------------
    date_from = fields.Datetime(
        required=True,
        tracking=True,
        index=True,
        help="Leave start (stored in UTC)."
    )
    date_to = fields.Datetime(
        required=True,
        tracking=True,
        index=True,
        help="Leave end (stored in UTC). Must be greater than start."
    )
    duration_hours = fields.Float(
        compute="_compute_duration_hours",
        store=False,
        help="Duration of the leave in hours (computed)."
    )

    # -------------------------------------------------------------------------
    # POLICIES (what to do when leave is approved)
    # -------------------------------------------------------------------------
    slot_policy = fields.Selection(
        SLOT_POLICY,
        default="block",
        help="How to handle overlapping availability slots when the leave is approved."
    )
    appointment_policy = fields.Selection(
        APPOINTMENT_POLICY,
        default="notify",
        help="How to handle overlapping appointments when the leave is approved."
    )
    apply_to_rooms = fields.Boolean(
        default=True,
        help="When true, the slot policy is applied irrespective of room assignment."
    )

    # -------------------------------------------------------------------------
    # STATE
    # -------------------------------------------------------------------------
    state = fields.Selection(
        LEAVE_STATE,
        default="draft",
        tracking=True,
        index=True,
        help="Workflow state of the leave."
    )
    active = fields.Boolean(
        default=True,
        help="Disable to hide this leave from standard views without removing history."
    )

    # -------------------------------------------------------------------------
    # COMPUTES & CONSTRAINTS
    # -------------------------------------------------------------------------
    def _compute_duration_hours(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to > rec.date_from:
                delta = rec.date_to - rec.date_from
                rec.duration_hours = round(delta.total_seconds() / 3600.0, 2)
            else:
                rec.duration_hours = 0.0

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for rec in self:
            if not rec.date_from or not rec.date_to:
                raise ValidationError(_("Both start and end datetimes are required."))
            if rec.date_to <= rec.date_from:
                raise ValidationError(_("End datetime must be greater than start datetime."))

    @api.constrains("doctor_id", "date_from", "date_to", "state")
    def _check_overlap_with_other_leaves(self):
        """
        Avoid overlapping *active* leaves for the same doctor (except Cancelled/Refused).
        """
        for rec in self:
            if not rec.doctor_id or not rec.date_from or not rec.date_to:
                continue
            dom = [
                ("id", "!=", rec.id),
                ("doctor_id", "=", rec.doctor_id.id),
                ("state", "in", ["draft", "confirm", "approve"]),  # active-ish
                ("date_from", "<", rec.date_to),
                ("date_to", ">", rec.date_from),
            ]
            if self.search_count(dom):
                raise ValidationError(_("Overlapping leaves are not allowed for the same doctor."))

    # -------------------------------------------------------------------------
    # DISPLAY
    # -------------------------------------------------------------------------
    @api.depends("name", "reason", "doctor_id")
    def _compute_display_name(self):
        """Preserve ClinicOne leave labels through the Odoo 19 display-name API."""
        for rec in self:
            label = rec.name or dict(LEAVE_REASON).get(rec.reason, "Leave")
            rec.display_name = f"{label} — {rec.doctor_id.display_name}" if rec.doctor_id else label

    def name_get(self):
        """Compatibility wrapper for existing ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]

    # -------------------------------------------------------------------------
    # HELPERS — DOMAINS & LOOKUPS
    # -------------------------------------------------------------------------
    def _domain_slots_overlap(self):
        """
        Domain for availability slots overlapping this leave's window.
        Will be guarded by presence check when used.
        """
        self.ensure_one()
        dom = [
            ("doctor_id", "=", self.doctor_id.id),
            ("start", "<", self.date_to),
            ("end", ">", self.date_from),
        ]
        if not self.apply_to_rooms and "room_id" in self.env["clinic.availability.slot"]._fields:
            dom.append(("room_id", "=", False))
        return dom

    def _domain_appointments_overlap(self):
        """
        Domain for appointments overlapping this leave's window (non-terminal).
        """
        self.ensure_one()
        dom = [
            ("doctor_id", "=", self.doctor_id.id),
            ("state", "not in", ["canceled", "done", "no_show"]),
            ("start", "<", self.date_to),
            ("end", ">", self.date_from),
        ]
        return dom

    # -------------------------------------------------------------------------
    # APPLY EFFECTS (SLOTS, APPOINTMENTS, CALENDAR, HR)
    # -------------------------------------------------------------------------
    def _apply_on_slots(self):
        """
        Apply slot policy to overlapping availability slots:
            - block:      set state=blocked & reason
            - close:      set state=closed
            - delete_open: delete only if no active bookings/reservations
        Safe-guarded if 'clinic.availability.slot' is absent.
        """
        if "clinic.availability.slot" not in self.env:
            return {"affected": 0, "deleted": 0}

        Slot = self.env["clinic.availability.slot"].sudo()
        affected = deleted = 0

        for rec in self:
            dom = rec._domain_slots_overlap()
            slots = Slot.search(dom)
            if not slots:
                continue

            if rec.slot_policy == "block":
                # Only block if not already closed; set reason
                for s in slots:
                    if s.state != "closed":
                        s.write({"state": "blocked", "block_reason": _("Doctor on leave")})
                        affected += 1

            elif rec.slot_policy == "close":
                for s in slots:
                    if s.state != "closed":
                        s.write({"state": "closed"})
                        affected += 1

            # elif rec.slot_policy == "delete_open":
                # Delete only open slots with no reservations/appointments
                # for s in slots:
                #     # If appointment linkage exists, ensure no open/active appointments
                #     if "clinic.appointment" in self.env and "slot_id" in self.env["clinic.appointment"]._fields:
                #         has_appt = bool(self.env["clinic.appointment"].search_count(
                #             [("slot_id", "=", s.id), ("state", "not in", ["canceled", "no_show"])]
                #         ))
                #         if has_appt:
                #             continue
                #     # Also ensure no manual reserved seats
                #     if s.state in ("open", "reserved") and (s.manual_reserved or 0) == 0:
                #         s.unlink()
                #         deleted += 1

        return {"affected": affected, "deleted": deleted}

    def _apply_on_appointments(self):
        """
        Apply appointment policy on overlapping appointments:
            - notify: message_post + (set need_reschedule if field exists)
            - cancel: set state='canceled' (if field exists), else message_post
            - nothing: skip
        """
        # if "clinic.appointment" not in self.env:
        #     return {"notified": 0, "canceled": 0, "flagged": 0}

        # App = self.env["clinic.appointment"].sudo()
        notified = canceled = flagged = 0

        # for rec in self:
        #     appts = App.search(rec._domain_appointments_overlap())
        #     for a in appts:
        #         if rec.appointment_policy == "notify":
        #             a.message_post(body=_("Appointment impacted by doctor leave: %s") % (rec.name or rec.reason))
        #             notified += 1
        #             if "need_reschedule" in a._fields:
        #                 a.write({"need_reschedule": True})
        #                 flagged += 1

        #         elif rec.appointment_policy == "cancel":
        #             if "state" in a._fields:
        #                 a.write({"state": "canceled"})
        #                 canceled += 1
        #             else:
        #                 a.message_post(body=_("Canceled due to doctor leave: %s") % (rec.name or rec.reason))
        #                 notified += 1

        #         else:  # nothing
        #             continue

        return {"notified": notified, "canceled": canceled, "flagged": flagged}

    def _apply_calendar_leave(self):
        """
        Optionally create a resource calendar leave entry for the doctor's calendar.
        Controlled by system parameter: clinic_doctor.propagate_calendar_leave = True/False
        """
        Param = self.env["ir.config_parameter"].sudo()
        propagate = Param.get_param("clinic_doctor.propagate_calendar_leave", "True") == "True"
        if not propagate:
            return False

        # Needs a calendar on doctor
        for rec in self:
            cal = rec.doctor_id.calendar_id
            if not cal or "resource.calendar.leaves" not in self.env:
                continue
            CalLeave = self.env["resource.calendar.leaves"].sudo()
            CalLeave.create({
                "name": rec.name or _("Doctor Leave"),
                "company_id": rec.company_id.id,
                "calendar_id": cal.id,
                "date_from": rec.date_from,
                "date_to": rec.date_to,
            })
        return True

    def _apply_hr_leave(self):
        """
        Optionally create hr.leave for the linked employee (bridge clinic_doctor_hr).
        Controlled by system parameter: clinic_doctor.sync_hr_leave = True/False
        Safely guarded if HR not installed or doctor has no employee link.
        """
        Param = self.env["ir.config_parameter"].sudo()
        sync_hr = Param.get_param("clinic_doctor.sync_hr_leave", "False") == "True"
        if not sync_hr or "hr.leave" not in self.env:
            return False

        for rec in self:
            # bridge provides doctor.employee_id
            if "employee_id" not in rec.doctor_id._fields or not rec.doctor_id.employee_id:
                continue
            vals = {
                "name": rec.name or _("Doctor Leave"),
                "employee_id": rec.doctor_id.employee_id.id,
                "request_date_from": fields.Date.to_date(rec.date_from),
                "request_date_to": fields.Date.to_date(rec.date_to),
                # hr.leave uses date_from/date_to (datetime) on records too; safest is to set both
                "date_from": rec.date_from,
                "date_to": rec.date_to,
                "holiday_status_id": self._get_default_hr_leave_type(),
            }
            self.env["hr.leave"].sudo().create(vals)
        return True

    def _get_default_hr_leave_type(self):
        """
        Helper: choose a default hr.leave type (holiday_status_id).
        Best-effort: pick first type or map by reason if you have such mapping in your HR module.
        """
        if "hr.leave.type" not in self.env:
            return False
        LeaveType = self.env["hr.leave.type"].sudo()
        lt = LeaveType.search([], limit=1)
        return lt.id if lt else False

    # -------------------------------------------------------------------------
    # WORKFLOW ACTIONS
    # -------------------------------------------------------------------------
    def action_confirm(self):
        for rec in self:
            if rec.state != "draft":
                continue
            rec.state = "confirm"
        return True

    def action_approve(self):
        """
        On approval:
          - Apply effects on slots and appointments (according to policy)
          - Optionally create calendar leave
          - Optionally sync HR leave
        """
        results = []
        for rec in self:
            if rec.state not in ("draft", "confirm"):
                continue
            # Apply effects
            slot_res = rec._apply_on_slots()
            appt_res = rec._apply_on_appointments()
            rec._apply_calendar_leave()
            rec._apply_hr_leave()

            rec.state = "approve"
            # Build user feedback
            msg = _(
                "Leave approved and applied.\n"
                "Slots affected: %(a)s, deleted: %(d)s\n"
                "Appointments notified: %(n)s, canceled: %(c)s, flagged: %(f)s",
                a=slot_res.get("affected", 0),
                d=slot_res.get("deleted", 0),
                n=appt_res.get("notified", 0),
                c=appt_res.get("canceled", 0),
                f=appt_res.get("flagged", 0),
            )
            rec.message_post(body=msg)
            results.append((rec.id, msg))

        # Optional: surface a toast
        if results:
            last = results[-1][1]
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"title": _("Doctor Leave"), "message": last, "sticky": False},
            }
        return True

    def action_refuse(self):
        for rec in self:
            if rec.state in ("approve",):
                # Business choice: allow refuse after approve? If not, raise:
                raise UserError(_("You cannot refuse a leave that is already approved."))
            rec.state = "refuse"
        return True

    def action_cancel(self):
        """
        Cancel the leave:
          - Optionally reopen previously-blocked slots that have no other conflicts.
            (Best-effort heuristic: only those with block_reason='Doctor on leave' and within window)
        """
        if "clinic.availability.slot" in self.env:
            Slot = self.env["clinic.availability.slot"].sudo()
            for rec in self:
                slots = Slot.search([
                    ("doctor_id", "=", rec.doctor_id.id),
                    ("start", "<", rec.date_to),
                    ("end", ">", rec.date_from),
                    ("state", "=", "blocked"),
                    ("block_reason", "=", _("Doctor on leave")),
                ])
                for s in slots:
                    # Reopen only if capacity allows and no active appointment makes it booked
                    s.write({"state": "open", "block_reason": False})
                    s._update_state_from_capacity()
        for rec in self:
            rec.state = "cancel"
        return True

    def action_reset_to_draft(self):
        for rec in self:
            rec.state = "draft"
        return True

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Autoname if not provided
        for rec in records:
            if not rec.name:
                label = dict(LEAVE_REASON).get(rec.reason, "Leave")
                rec.name = f"{label} — {rec.doctor_id.display_name}"
        return records

    def write(self, vals):
        # If window changes after approval, re-apply slot/appointment effects
        reapply = False
        if any(k in vals for k in ("date_from", "date_to", "slot_policy", "appointment_policy")):
            reapply = True
        res = super().write(vals)
        if reapply:
            for rec in self.filtered(lambda r: r.state == "approve"):
                slot_res = rec._apply_on_slots()
                appt_res = rec._apply_on_appointments()
                rec.message_post(body=_(
                    "Leave window/policy updated.\n"
                    "Slots affected: %(a)s, deleted: %(d)s\n"
                    "Appointments notified: %(n)s, canceled: %(c)s, flagged: %(f)s",
                    a=slot_res.get("affected", 0),
                    d=slot_res.get("deleted", 0),
                    n=appt_res.get("notified", 0),
                    c=appt_res.get("canceled", 0),
                    f=appt_res.get("flagged", 0),
                ))
        return res

    def unlink(self):
        # Business rule: prevent deleting approved leaves to preserve audit log
        if any(rec.state == "approve" for rec in self):
            raise UserError(_("You cannot delete an approved leave. Cancel it instead to preserve history."))
        return super().unlink()

