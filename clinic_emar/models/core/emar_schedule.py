# -*- coding: utf-8 -*-
"""
ClinicOne eMAR - Core Model: Schedule
Model: clinic.emar.schedule

Purpose
-------
Plan and track scheduled administrations generated from eMAR Orders (and indirectly
from Prescriptions). Each schedule entry represents a single planned dose/action.

Key features
------------
- One-file-per-core-model: NO other file in this addon _inherit this model.
- Links to Order, Prescription Line (via Medication Line), Patient, Doctor, Product.
- Windowing (early/late tolerance), overdue & due flags, reschedule & cancel flows.
- Action to spawn Administration record(s), leaving inventory/billing to that model.
- Generation helper 'generate_from_order(order)' with simple frequency parsing.

Soft coupling
-------------
- room/session references are optional; guarded access for external models.
- Administration model is expected within the same addon; if absent, a clear error is raised.

Compatibility
-------------
- Odoo 19 CE
- ClinicOne ecosystem (~38 addons)

"""

from datetime import datetime, timedelta, time, date
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)


# =============================================================================
# Small utilities
# =============================================================================
def _get_model(env, model_name):
    try:
        return env[model_name]
    except Exception:
        return None


def _has_field(record_or_model, field_name):
    return hasattr(record_or_model, "_fields") and field_name in record_or_model._fields


def _ensure_dt(value):
    """Normalize datetime value (string or datetime) into datetime."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return fields.Datetime.from_string(value)
        except Exception:
            pass
    # Fallback: now (shouldn't happen in normal flows)
    return fields.Datetime.now()


def _daterange_days(start_dt, end_dt):
    """Yield dates (00:00) between start/end inclusive."""
    if not (start_dt and end_dt):
        return
    d0 = start_dt.date() if isinstance(start_dt, datetime) else start_dt
    d1 = end_dt.date() if isinstance(end_dt, datetime) else end_dt
    cur = d0
    while cur <= d1:
        yield cur
        cur = cur + timedelta(days=1)


# =============================================================================
# Core Model
# =============================================================================
class ClinicEmarSchedule(models.Model):
    _name = "clinic.emar.schedule"
    _description = "ClinicOne eMAR Schedule"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "clinic.emar.mixin.audit",   # abstract, safe
    ]
    _order = "planned_datetime asc, id asc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Schedule",
        compute="_compute_name",
        store=True,
        help="Human-readable title: <Order/Prescription> - <Product> @ <Planned>",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to archive the schedule."
    )

    # -------------------------------------------------------------------------
    # Linkage
    # -------------------------------------------------------------------------
    order_id = fields.Many2one(
        "clinic.emar.order",
        string="Order",
        index=True,
        help="Owning Order from which this schedule is generated.",
    )
    line_id = fields.Many2one(
        "clinic.emar.medication.line",
        string="Medication Line",
        index=True,
        help="Medication line that this schedule refers to.",
    )
    prescription_id = fields.Many2one(
        "clinic.emar.prescription",
        string="Prescription",
        compute="_compute_context_refs",
        store=True,
        help="Prescription context derived from the Order/Line.",
    )

    # Context mirrors for reporting & security
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        compute="_compute_context_refs",
        store=True,
        index=True,
    )
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        compute="_compute_context_refs",
        store=True,
        index=True,
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        compute="_compute_context_refs",
        store=True,
        index=True,
    )

    # Product snapshot
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        index=True,
        help="Medication/consumable/service scheduled for administration.",
    )
    dose_qty = fields.Float(
        string="Dose Qty",
        default=1.0,
        digits="Product Unit",
        help="Dose quantity planned for this schedule entry.",
    )
    dose_uom_id = fields.Many2one(
        "uom.uom",
        string="Dose UoM",
        help="Unit of measure for the dose quantity.",
    )

    # Clinical snapshot
    dosage = fields.Char(
        string="Dosage",
        help="Free-text dosage (e.g., '500 mg', '2 pumps').",
    )
    route = fields.Char(
        string="Route",
        help="Administration route (e.g., 'IM', 'IV', 'Topical', 'Oral').",
    )
    notes = fields.Text(
        string="Notes",
        help="Operational or clinical notes for this schedule entry.",
    )

    # -------------------------------------------------------------------------
    # Timing & Window
    # -------------------------------------------------------------------------
    planned_datetime = fields.Datetime(
        string="Planned Date/Time",
        required=True,
        index=True,
        tracking=True,
        help="Target date/time when this dose should be administered.",
    )
    window_before_min = fields.Integer(
        string="Early Window (min)",
        default=30,
        help="How many minutes before the planned time the administration is considered on-time."
    )
    window_after_min = fields.Integer(
        string="Late Window (min)",
        default=60,
        help="How many minutes after the planned time the administration is still considered on-time."
    )
    window_start = fields.Datetime(
        string="Window Start",
        compute="_compute_window",
        store=True,
        help="Earliest acceptable time to administer this schedule."
    )
    window_end = fields.Datetime(
        string="Window End",
        compute="_compute_window",
        store=True,
        help="Latest acceptable time to administer this schedule."
    )

    # Timing flags (computed)
    is_due = fields.Boolean(
        string="Due Now",
        compute="_compute_due_flags",
        help="True if current time falls within the acceptable window."
    )
    is_overdue = fields.Boolean(
        string="Overdue",
        compute="_compute_due_flags",
        help="True if current time is past window end while schedule still not administered/cancelled."
    )

    # -------------------------------------------------------------------------
    # Assignment & Location (soft-coupled)
    # -------------------------------------------------------------------------
    assigned_user_id = fields.Many2one(
        "res.users",
        string="Assigned User",
        help="User responsible for administering this schedule."
    )
    assigned_employee_id = fields.Many2one(
        "hr.employee",
        string="Assigned Employee",
        help="Employee responsible for administering this schedule."
    )
    assigned_role = fields.Selection(
        [("nurse", "Nurse"), ("doctor", "Doctor"), ("pharmacist", "Pharmacist"), ("other", "Other")],
        string="Assigned Role",
        default="nurse",
        help="Role expected to perform this administration.",
    )
    # Optional room/session link if the model exists in ClinicOne
    room_session_id = fields.Many2one(
        "clinic.room.session",
        string="Room Session",
        help="Room session where this administration is planned to occur.",
    )
    location_note = fields.Char(
        string="Location Note",
        help="Free-text location information if room/session is not available."
    )

    # -------------------------------------------------------------------------
    # Lifecycle & Relations
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("scheduled", "Scheduled"),
            ("due", "Due"),
            ("administered", "Administered"),
            ("missed", "Missed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
    )
    administration_ids = fields.One2many(
        "clinic.emar.administration",
        "schedule_id",
        string="Administrations",
        help="Administration records executed for this schedule entry."
    )
    administration_count = fields.Integer(
        string="Administrations",
        compute="_compute_admin_count"
    )

    cancel_reason = fields.Char(
        string="Cancellation Reason",
        help="Reason why this schedule was cancelled."
    )
    reschedule_origin_id = fields.Many2one(
        "clinic.emar.schedule",
        string="Reschedule Origin",
        help="If this schedule is created as a reschedule of another one, keep reference here."
    )
    reschedule_reason = fields.Char(
        string="Reschedule Reason",
        help="Why the schedule was rescheduled."
    )

    # Odoo 19 SQL constraint declaration.
    _uniq_order_line_datetime = models.Constraint(
        "UNIQUE(order_id, line_id, planned_datetime)",
        "A schedule for this order, line, and planned date/time already exists.",
    )

    # =========================================================================
    # COMPUTES
    # =========================================================================
    @api.depends(
        "order_id", "line_id",
        "order_id.clinic_patient_id", "order_id.clinic_doctor_id", "order_id.company_id",
        "line_id.patient_id", "line_id.doctor_id", "line_id.order_id", "line_id.prescription_id",
    )
    def _compute_context_refs(self):
        for rec in self:
            # Company
            company = None
            if rec.order_id and rec.order_id.company_id:
                company = rec.order_id.company_id
            elif rec.line_id:
                # try to resolve from order first, else prescription
                if rec.line_id.order_id and rec.line_id.order_id.company_id:
                    company = rec.line_id.order_id.company_id
                elif rec.line_id.prescription_id and rec.line_id.prescription_id.company_id:
                    company = rec.line_id.prescription_id.company_id
            rec.company_id = company or rec.company_id or rec.env.company

            # Canonical clinical identity.  Order.patient_id/doctor_id are
            # compatibility fields (res.partner/hr.employee), so never copy their
            # raw IDs into clinic.patient/clinic.doctor mirrors.
            patient = rec.order_id.clinic_patient_id if rec.order_id else False
            if not patient and rec.line_id:
                patient = rec.line_id.patient_id or (
                    rec.line_id.prescription_id.patient_id if rec.line_id.prescription_id else False
                )
            rec.patient_id = patient

            doctor = rec.order_id.clinic_doctor_id if rec.order_id else False
            if not doctor and rec.line_id:
                doctor = rec.line_id.doctor_id or (
                    rec.line_id.prescription_id.doctor_id if rec.line_id.prescription_id else False
                )
            rec.doctor_id = doctor

            # Prescription (context)
            rx = None
            if rec.line_id and rec.line_id.prescription_id:
                rx = rec.line_id.prescription_id
            elif rec.order_id and rec.order_id.prescription_id:
                rx = rec.order_id.prescription_id
            rec.prescription_id = rx

    @api.depends("order_id.name", "line_id.product_id", "product_id", "planned_datetime")
    def _compute_name(self):
        for rec in self:
            prod = rec.product_id or (rec.line_id and rec.line_id.product_id)
            head = rec.order_id and rec.order_id.name or (rec.prescription_id and rec.prescription_id.name) or _("eMAR")
            dt = rec.planned_datetime and fields.Datetime.to_string(rec.planned_datetime) or "?"
            rec.name = "%s - %s @ %s" % (head, prod.display_name if prod else _("Item"), dt)

    @api.depends("planned_datetime", "window_before_min", "window_after_min")
    def _compute_window(self):
        for rec in self:
            if rec.planned_datetime:
                start = rec.planned_datetime - timedelta(minutes=rec.window_before_min or 0)
                end = rec.planned_datetime + timedelta(minutes=rec.window_after_min or 0)
                rec.window_start = start
                rec.window_end = end
            else:
                rec.window_start = False
                rec.window_end = False

    @api.depends("state", "window_start", "window_end")
    def _compute_due_flags(self):
        """Pure presentation compute; lifecycle transitions are handled by cron/actions."""
        now = fields.Datetime.now()
        for rec in self:
            active = rec.state in ("scheduled", "due")
            rec.is_due = bool(active and rec.window_start and rec.window_start <= now <= (rec.window_end or now))
            rec.is_overdue = bool(active and rec.window_end and now > rec.window_end)

    @api.model
    def _cron_schema_ready(self):
        """Return whether cron-owned eMAR tables exist in the current schema.

        During a controlled source replacement, Python can be visible before a
        module upgrade has materialized the corresponding PostgreSQL tables.
        ``to_regclass`` is deliberately used because it returns NULL instead of
        aborting the transaction when a table is absent.
        """
        required_tables = (
            self._table,
            self.env["clinic.emar.alert"]._table,
        )
        for table_name in required_tables:
            self.env.cr.execute("SELECT to_regclass(%s)", (table_name,))
            if not self.env.cr.fetchone()[0]:
                _logger.warning(
                    "[clinic_emar] eMAR schedule cron skipped because table %s "
                    "does not exist yet. Upgrade clinic_emar to synchronize the schema.",
                    table_name,
                )
                return False
        return True

    @api.model
    def _cron_update_schedule_status(self):
        """Advance planned doses to Due/Missed and raise a deduplicated alert."""
        if not self._cron_schema_ready():
            return True

        now = fields.Datetime.now()
        schedules = self.search([
            ("state", "in", ("scheduled", "due")),
            ("window_start", "!=", False),
        ])
        Alert = self.env["clinic.emar.alert"]
        for rec in schedules:
            grace = rec.company_id.emar_overdue_grace_minutes or 0
            missed_after = rec.window_end + timedelta(minutes=grace) if rec.window_end else False
            if missed_after and now > missed_after:
                if rec.state != "missed":
                    rec._emar_guarded_write({"state": "missed"})
                    Alert.raise_time_window(rec, kind="missed_dose")
            elif rec.window_start <= now and rec.state == "scheduled":
                rec._emar_guarded_write({"state": "due"})
        return True

    def _compute_admin_count(self):
        for rec in self:
            rec.administration_count = len(rec.administration_ids)

    # =========================================================================
    # ONCHANGE & CONSTRAINTS
    # =========================================================================
    @api.onchange("line_id")
    def _onchange_line(self):
        for rec in self:
            if rec.line_id:
                if not rec.product_id and rec.line_id.product_id:
                    rec.product_id = rec.line_id.product_id
                if not rec.dose_uom_id:
                    # prefer line's uom; else product's uom
                    if _has_field(rec.line_id, "product_uom_id") and rec.line_id.product_uom_id:
                        rec.dose_uom_id = rec.line_id.product_uom_id
                    elif rec.product_id and rec.product_id.uom_id:
                        rec.dose_uom_id = rec.product_id.uom_id
                # Mirror useful clinical fields
                if not rec.dosage and _has_field(rec.line_id, "dosage"):
                    rec.dosage = rec.line_id.dosage
                if not rec.route and _has_field(rec.line_id, "route"):
                    rec.route = rec.line_id.route
                if not rec.notes and _has_field(rec.line_id, "notes"):
                    rec.notes = rec.line_id.notes

    @api.constrains("planned_datetime")
    def _check_planned_datetime(self):
        for rec in self:
            if not rec.planned_datetime:
                raise ValidationError(_("Planned Date/Time is required."))

    @api.constrains("dose_qty")
    def _check_dose_qty(self):
        for rec in self:
            if rec.dose_qty is not None and rec.dose_qty < 0:
                raise ValidationError(_("Dose quantity must be greater than or equal to 0."))

    @api.constrains("company_id", "order_id", "line_id")
    def _check_company_alignment(self):
        for rec in self:
            # Ensure schedule company consistent with order/line company contexts
            cmp = None
            if rec.order_id and rec.order_id.company_id:
                cmp = rec.order_id.company_id
            elif rec.line_id:
                if rec.line_id.order_id and rec.line_id.order_id.company_id:
                    cmp = rec.line_id.order_id.company_id
                elif rec.line_id.prescription_id and rec.line_id.prescription_id.company_id:
                    cmp = rec.line_id.prescription_id.company_id
            if cmp and rec.company_id and cmp != rec.company_id:
                raise ValidationError(_("Company mismatch between the schedule and its header context."))

    # =========================================================================
    # ACTIONS: Lifecycle
    # =========================================================================
    def action_schedule(self):
        for rec in self:
            if rec.state in ("draft", "missed"):
                rec._emar_guarded_write({"state": "scheduled"})
                rec._audit_log("state_change", message=_("Schedule set to Scheduled."))
        return True

    def action_mark_due(self):
        for rec in self:
            if rec.state in ("draft", "scheduled"):
                rec._emar_guarded_write({"state": "due"})
                rec._audit_log("state_change", message=_("Schedule is due now."))
        return True

    def action_mark_missed(self):
        for rec in self:
            if rec.state in ("scheduled", "due"):
                rec._emar_guarded_write({"state": "missed"})
                rec._audit_log("state_change", message=_("Schedule marked as missed."))
        return True

    def action_cancel(self, reason=None):
        for rec in self:
            if rec.state in ("administered", "cancelled"):
                continue
            rec._emar_guarded_write({"state": "cancelled"})
            if reason:
                rec.cancel_reason = reason
            rec._audit_log("state_change", message=_("Schedule cancelled."))
        return True

    def action_open_reschedule_wizard(self):
        self.ensure_one()
        if self.state in ("administered", "cancelled"):
            raise UserError(_("An administered or cancelled schedule cannot be rescheduled."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Reschedule Medication Administration"),
            "res_model": "clinic.emar.reschedule.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_schedule_id": self.id,
                "default_new_datetime": self.planned_datetime,
            },
        }

    def action_reschedule(self, new_datetime, reason=None):
        """
        Create a new schedule cloned from this one with a different planned time,
        and cancel the original (keeping traceability).
        """
        Sched = self.env["clinic.emar.schedule"]
        created = self.env["clinic.emar.schedule"]
        for rec in self:
            vals = {
                "order_id": rec.order_id.id if rec.order_id else False,
                "line_id": rec.line_id.id if rec.line_id else False,
                "product_id": rec.product_id.id if rec.product_id else False,
                "dose_qty": rec.dose_qty,
                "dose_uom_id": rec.dose_uom_id.id if rec.dose_uom_id else False,
                "dosage": rec.dosage,
                "route": rec.route,
                "notes": rec.notes,
                "planned_datetime": _ensure_dt(new_datetime),
                "window_before_min": rec.window_before_min,
                "window_after_min": rec.window_after_min,
                "assigned_user_id": rec.assigned_user_id.id if rec.assigned_user_id else False,
                "assigned_employee_id": rec.assigned_employee_id.id if rec.assigned_employee_id else False,
                "assigned_role": rec.assigned_role,
                "room_session_id": rec.room_session_id.id if rec.room_session_id else False,
                "location_note": rec.location_note,
                "reschedule_origin_id": rec.id,
                "reschedule_reason": reason or _("Rescheduled"),
                "state": "scheduled",
            }
            new_s = Sched.create(vals)
            created |= new_s
            # cancel original
            rec.action_cancel(reason=reason or _("Rescheduled"))
        # Open the new schedule if single
        if len(created) == 1:
            return {
                "name": _("Schedule"),
                "type": "ir.actions.act_window",
                "res_model": "clinic.emar.schedule",
                "view_mode": "form",
                "res_id": created.id,
            }
        return True

    # =========================================================================
    # ACTION: Administration creation
    # =========================================================================
    def action_administer(self):
        """
        Create an Administration record and (optionally) let it handle inventory/billing.
        """
        Admin = _get_model(self.env, "clinic.emar.administration")
        if not Admin:
            raise UserError(_("Administration model is not available."))

        created = self.env["clinic.emar.administration"]
        for rec in self:
            if rec.state in ("cancelled",):
                raise UserError(_("Cannot administer a cancelled schedule."))
            vals = {
                "company_id": rec.company_id.id if rec.company_id else self.env.company.id,
                "order_id": rec.order_id.id if rec.order_id else False,
                "schedule_id": rec.id,
                "line_id": rec.line_id.id if rec.line_id else False,
                "product_id": rec.product_id.id if rec.product_id else False,
                "dose_qty": rec.dose_qty,
                "dose_uom_id": rec.dose_uom_id.id if rec.dose_uom_id else False,
                "inventory_qty": rec.line_id.quantity if rec.line_id else 1.0,
                "inventory_uom_id": rec.line_id.product_uom_id.id if rec.line_id and rec.line_id.product_uom_id else (rec.product_id.uom_id.id if rec.product_id and rec.product_id.uom_id else False),
                "route": rec.route,
                "notes": rec.notes,
                "administered_datetime": fields.Datetime.now(),
                "state": "draft",  # let administration workflow confirm/validate
            }
            admin = Admin.create(vals)
            created |= admin
            # Creating a draft administration is not the same as administering a dose.
            # The schedule becomes administered only when administration.action_done()
            # completes its ORM safety and inventory gates.
            if rec.state == "draft":
                rec._emar_guarded_write({"state": "scheduled"})
            rec._audit_log("state_change", message=_("Draft administration created from schedule."))

        if len(created) == 1:
            return {
                "name": _("Administration"),
                "type": "ir.actions.act_window",
                "res_model": "clinic.emar.administration",
                "view_mode": "form",
                "res_id": created.id,
            }
        return True

    def action_view_administrations(self):
        self.ensure_one()
        return {
            "name": _("Administrations"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.emar.administration",
            "view_mode": "list,form",
            "domain": [("schedule_id", "=", self.id)],
            "context": {"default_schedule_id": self.id},
        }

    # =========================================================================
    # GENERATION: from Order
    # =========================================================================
    @api.model
    def _parse_frequency(self, freq_str):
        """
        Parse common frequency strings into anchor times or hourly intervals.

        Returns dict:
          {
            "anchors": [time(8,0), time(20,0)]  # specific clock times in a day, OR
            "interval_hours": 6,                # repeating every N hours
            "count_per_day": 3,                 # optional hint
          }

        Supported patterns (case-insensitive):
          - "qd", "od", "once daily"      → [09:00]
          - "bid"                         → [08:00, 20:00]
          - "tid"                         → [08:00, 14:00, 20:00]
          - "qid"                         → [06:00, 12:00, 18:00, 22:00]
          - "q4h", "q6h", "q8h", "q12h"   → interval_hours = 4/6/8/12
          - unknown/empty                 → [09:00]
        """
        if not freq_str:
            return {"anchors": [time(9, 0)], "count_per_day": 1}
        s = (freq_str or "").strip().lower()
        if s == "once":
            return {"once": True, "count_per_day": 1}
        if s == "prn":
            return {"prn": True, "count_per_day": 0}
        if s == "weekly":
            return {"interval_days": 7, "count_per_day": 0}
        if s in ("qd", "od", "once daily", "q.d.", "o.d."):
            return {"anchors": [time(9, 0)], "count_per_day": 1}
        if s == "bid":
            return {"anchors": [time(8, 0), time(20, 0)], "count_per_day": 2}
        if s == "tid":
            return {"anchors": [time(8, 0), time(14, 0), time(20, 0)], "count_per_day": 3}
        if s in ("qid", "q.i.d"):
            return {"anchors": [time(6, 0), time(12, 0), time(18, 0), time(22, 0)], "count_per_day": 4}
        if s.startswith("q") and s.endswith("h"):
            try:
                h = int(s[1:-1])
                if h in (4, 6, 8, 12):
                    return {"interval_hours": h, "count_per_day": max(1, int(24 / h))}
            except Exception:
                pass
        # Default: once daily at 09:00
        return {"anchors": [time(9, 0)], "count_per_day": 1}

    @api.model
    def _build_day_datetimes(self, day: date, pattern: dict, start_dt: datetime, end_dt: datetime):
        """
        Build datetimes for a single day inside [start_dt, end_dt] using the parsed pattern.
        """
        dts = []
        if "anchors" in pattern and pattern["anchors"]:
            for t in pattern["anchors"]:
                dt = datetime.combine(day, t)
                if start_dt <= dt <= end_dt:
                    dts.append(dt)
        elif pattern.get("interval_hours"):
            # Start from the left boundary of the day or start_dt, whichever is later
            first = max(datetime.combine(day, time.min), start_dt)
            # Round up to next interval from midnight for simplicity
            h = pattern["interval_hours"]
            cur = datetime.combine(day, time(0, 0))
            while cur < first:
                cur += timedelta(hours=h)
            # Generate while within the day and end_dt
            while cur.date() == day and cur <= end_dt:
                if cur >= start_dt:
                    dts.append(cur)
                cur += timedelta(hours=h)
        return dts

    @api.model
    def generate_from_order(self, order):
        """
        Generate schedule entries from an eMAR Order using each Medication Line's frequency.

        Policy:
        - Date range = [order.date_start, order.date_end] (if empty, uses today only).
        - For each line:
            * 'frequency' parsed by _parse_frequency(); if unknown → once daily 09:00.
            * dose_qty defaults to 1.0 (projects can extend to compute per-dose).
            * Avoid exact duplicates by unique SQL constraint (order, line, planned).
        - Returns recordset of created schedules.
        """
        Order = _get_model(self.env, "clinic.emar.order")
        Line = _get_model(self.env, "clinic.emar.medication.line")
        if not Order or not Line:
            raise UserError(_("Order/Line models are not available."))

        if isinstance(order, int):
            order = Order.browse(order)
        if not order or len(order) != 1:
            raise UserError(_("Please provide a single Order record."))

        start_dt = order.date_start or fields.Datetime.now()
        end_dt = order.date_end or (start_dt + timedelta(days=0))
        start_dt = _ensure_dt(start_dt)
        end_dt = _ensure_dt(end_dt)
        if end_dt < start_dt:
            end_dt = start_dt

        created = self.env[self._name]
        for ln in order.line_ids:
            product = ln.product_id
            if not product:
                continue
            pattern = self._parse_frequency(getattr(ln, "frequency", None))
            if pattern.get("prn"):
                # PRN medication is intentionally not materialized into timed doses.
                continue
            if pattern.get("once"):
                planned_datetimes = [start_dt]
            elif pattern.get("interval_days"):
                planned_datetimes = []
                cur = start_dt
                while cur <= end_dt:
                    planned_datetimes.append(cur)
                    cur += timedelta(days=pattern["interval_days"])
            else:
                planned_datetimes = []
                for day in _daterange_days(start_dt, end_dt):
                    planned_datetimes.extend(
                        self._build_day_datetimes(day, pattern, start_dt, end_dt)
                    )
                if not planned_datetimes:
                    planned_datetimes = [start_dt]

            for dtp in planned_datetimes:
                duplicate = self.search_count([
                    ("order_id", "=", order.id),
                    ("line_id", "=", ln.id),
                    ("planned_datetime", "=", dtp),
                ])
                if duplicate:
                    continue
                dose_uom = getattr(ln, "dose_uom_id", False) or getattr(ln, "product_uom_id", False) or product.uom_id
                vals = {
                    "order_id": order.id,
                    "line_id": ln.id,
                    "product_id": product.id,
                    "dose_qty": float(getattr(ln, "dose", 0.0) or getattr(ln, "quantity", 1.0) or 1.0),
                    "dose_uom_id": dose_uom.id if dose_uom else False,
                    "dosage": getattr(ln, "dosage", False),
                    "route": getattr(ln, "route", False),
                    "notes": getattr(ln, "notes", False),
                    "planned_datetime": dtp,
                    "state": "scheduled",
                }
                created |= self.create(vals)

        # Chatter notifications
        if hasattr(order, "message_post"):
            try:
                order.message_post(body=_("Schedules generated: %s") % len(created))
            except Exception:
                pass
        return created

    # =========================================================================
    # VIEWS / ACTIONS HELPERS
    # =========================================================================
    def action_open_order(self):
        self.ensure_one()
        if not self.order_id:
            raise UserError(_("No related order."))
        return {
            "name": _("Order"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.emar.order",
            "view_mode": "form",
            "res_id": self.order_id.id,
        }

    def action_open_line(self):
        self.ensure_one()
        if not self.line_id:
            raise UserError(_("No related medication line."))
        return {
            "name": _("Medication Line"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.emar.medication.line",
            "view_mode": "form",
            "res_id": self.line_id.id,
        }

