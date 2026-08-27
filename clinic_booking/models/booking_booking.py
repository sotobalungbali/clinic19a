# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/booking_booking.py
#
# Core reservation record used by Front Office.
# Separation of concerns:
# - Booking (this file) = front-desk reservation object
# - Appointment (clinic_doctor) = clinical schedule object
#
# Key fields: patient, doctor, treatment, time window, room, resources, channel, policy
# Lifecycle: draft → confirmed → in_progress → done → cancelled (with optional no_show flag)
#
# Soft integrations:
# - clinic_doctor (clinic.appointment) via optional link at confirmation
# - clinic_treatment (defaults & pricing info, if available)
# - clinic_patient (patient profile history shown there)
# - booking.room / booking.resource (availability / capacity / buffers)
# - booking.slot (prefill template & capacity)
# - booking.channel / booking.policy (defaults, deposits, fee rules)
# - account.move (invoice linkage)
# - stock (optional consumption in other flows), portal (tokens/URLs handled elsewhere)

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta


class BookingBooking(models.Model):
    _name = "booking.booking"
    _description = "Booking"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        # Abstract mixins defined in this module set (optional but useful)
        "booking.policy.mixin",
        "booking.resource.mixin",
        "booking.channel.mixin",
        "booking.slot.mixin",
        "booking.feedback.link.mixin",
    ]
    _order = "start_datetime asc, id asc"
    _rec_name = "name"

    # -------------------------------------------------------------------------
    # BASIC / IDENTITY
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Booking Number",
        required=True,
        readonly=True,
        default="/",
        copy=False,
        help="Auto-generated sequence for the booking.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to archive the booking.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        help="Company owning this booking.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # Parties
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        required=True,
        index=True,
        help="Patient for whom this reservation is made.",
        tracking=True,
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        index=True,
        tracking=True,
        help="Assigned doctor for this booking. Availability will be checked at confirmation.",
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        index=True,
        help="Primary treatment planned for this booking (optional).",
        tracking=True,
    )

    # Room / Resources / Slot (from inherited mixins we already have resource_ids & slot_id)
    room_id = fields.Many2one(
        "booking.room",
        string="Room",
        index=True,
        help="Allocated clinical room for this booking.",
        tracking=True,
    )

    # Timing
    start_datetime = fields.Datetime(
        string="Start Time",
        required=True,
        index=True,
        tracking=True,
        help="Planned start time in server timezone.",
    )
    end_datetime = fields.Datetime(
        string="End Time",
        required=True,
        index=True,
        tracking=True,
        help="Planned end time in server timezone.",
    )
    duration_minutes = fields.Integer(
        string="Duration (min)",
        compute="_compute_duration_minutes",
        inverse="_inverse_duration_minutes",
        store=True,
        help="Computed duration in minutes. You can adjust this to recompute End Time.",
    )

    # Lifecycle
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        required=True,
        default="draft",
        tracking=True,
        help="Lifecycle status of the booking.",
    )
    is_no_show = fields.Boolean(
        string="No-show",
        help="Enable if patient did not show up for the booking.",
        tracking=True,
    )
    checkin_time = fields.Datetime(
        string="Check-in Time",
        help="Actual check-in time when the patient arrives.",
        tracking=True,
    )
    checkout_time = fields.Datetime(
        string="Check-out Time",
        help="Actual check-out time when the patient leaves.",
        tracking=True,
    )

    # Channel/Policy (from mixins): channel_id, policy_id
    auto_create_appointment = fields.Boolean(
        string="Create Appointment on Confirm",
        help="If enabled, confirmation will attempt to create/link a clinic.appointment in clinic_doctor.",
        default=True,
    )
    lock_slot_on_confirm = fields.Boolean(
        string="Lock Slot on Confirm",
        help="Lock the selected slot to avoid parallel double-booking.",
        default=False,
    )

    # Optional handshake with clinic_doctor (soft)
    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Linked Appointment",
        help="Clinical appointment created/linked upon confirmation (lives in clinic_doctor).",
        ondelete="set null",
        copy=False,
        index=True,
    )

    # Financials (summary-level; details live in booking lines)
    line_ids = fields.One2many(
        "booking.line",
        "booking_id",
        string="Lines",
        help="Detailed items/services/consumables for this booking.",
        copy=True,
    )

    amount_untaxed = fields.Monetary(
        string="Untaxed Amount",
        compute="_compute_amounts",
        store=True,
        help="Sum of line subtotals without taxes.",
    )
    amount_tax = fields.Monetary(
        string="Taxes",
        compute="_compute_amounts",
        store=True,
        help="Total taxes from lines.",
    )
    amount_total = fields.Monetary(
        string="Total",
        compute="_compute_amounts",
        store=True,
        help="Grand total amount.",
    )

    # Deposit (policy/channel-driven; stored for audit)
    allow_prepaid_deposit = fields.Boolean(
        string="Allow Prepaid Deposit",
        help="Enable deposit processing for this booking.",
    )
    deposit_is_required = fields.Boolean(
        string="Deposit Required",
        help="If enabled, a deposit must be collected as per policy/channel.",
    )
    deposit_fixed_amount = fields.Monetary(
        string="Deposit Fixed Amount",
        help="Fixed deposit amount if configured.",
        currency_field="currency_id",
    )
    deposit_percent = fields.Float(
        string="Deposit Percentage",
        help="Deposit percent (0..100) if configured.",
    )
    deposit_amount = fields.Monetary(
        string="Deposit Amount",
        compute="_compute_deposit_amount",
        store=True,
        help="Computed deposit payable according to fixed or percentage rule.",
        currency_field="currency_id",
    )
    deposit_status = fields.Selection(
        selection=[
            ("none", "None"),
            ("required", "Required"),
            ("paid", "Paid"),
            ("waived", "Waived"),
        ],
        string="Deposit Status",
        default="none",
        tracking=True,
        help="Operational status for deposit processing.",
    )

    # Accounting link
    invoice_id = fields.Many2one(
        "account.move",
        string="Invoice",
        help="Invoice created from this booking.",
        copy=False,
        index=True,
    )
    # (Optional) Many2one to picking if inventory flow is used; left for stock inherits

    # UX / Notes
    notes = fields.Text(
        string="Notes",
        help="Internal notes for the booking.",
    )

    # Tags (optional taxonomy coming from data/booking_tag_data.xml)
    tag_ids = fields.Many2many(
        "booking.tag",
        "booking_booking_tag_rel",
        "booking_id",
        "tag_id",
        string="Tags",
        help="Optional tags for search and reporting.",
    )

    # -------------------------------------------------------------------------
    # DEFAULTS / CREATE / WRITE
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env.ref("clinic_booking.sequence_booking", raise_if_not_found=False)
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if not vals.get("name") or vals.get("name") == "/":
                vals["name"] = seq._next() if seq else self.env["ir.sequence"].next_by_code("booking.booking")
        records = super().create(vals_list)

        # Apply defaults from channel/slot after create, then re-validate
        for rec in records:
            if rec.channel_id:
                try:
                    rec.channel_id.apply_defaults_to_booking(rec)
                except Exception:
                    # keep robust
                    pass
            # Attach watcher activities for draft new bookings
            rec._schedule_initial_activities()
        return records

    def write(self, vals):
        # Normalizations
        if "deposit_percent" in vals and vals["deposit_percent"]:
            if vals["deposit_percent"] < 0.0 or vals["deposit_percent"] > 100.0:
                raise ValidationError(_("Deposit Percentage must be between 0 and 100."))

        # Prevent illegal changes in certain states
        for rec in self:
            if rec.state in ("in_progress", "done", "cancelled"):
                blocked = {"patient_id", "doctor_id", "room_id", "start_datetime", "end_datetime"}
                if blocked & set(vals.keys()):
                    raise UserError(_("You cannot change patient/doctor/room/time after the service has started or completed."))

        res = super().write(vals)
        return res

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("start_datetime", "end_datetime")
    def _compute_duration_minutes(self):
        for rec in self:
            dur = 0
            if rec.start_datetime and rec.end_datetime and rec.end_datetime > rec.start_datetime:
                delta = fields.Datetime.from_string(rec.end_datetime) - fields.Datetime.from_string(rec.start_datetime)
                dur = int(delta.total_seconds() // 60)
            rec.duration_minutes = max(0, dur)

    def _inverse_duration_minutes(self):
        for rec in self:
            if rec.start_datetime and rec.duration_minutes and rec.duration_minutes > 0:
                start = fields.Datetime.from_string(rec.start_datetime)
                rec.end_datetime = start + timedelta(minutes=int(rec.duration_minutes))

    @api.depends("line_ids.price_subtotal", "line_ids.price_tax", "line_ids.currency_id")
    def _compute_amounts(self):
        for rec in self:
            untaxed = tax = 0.0
            for line in rec.line_ids:
                # We assume booking.line exposes price_subtotal and price_tax as in sale.order.line
                untaxed += getattr(line, "price_subtotal", 0.0) or 0.0
                tax += getattr(line, "price_tax", 0.0) or 0.0
            rec.amount_untaxed = untaxed
            rec.amount_tax = tax
            rec.amount_total = untaxed + tax

    @api.depends("amount_total", "deposit_fixed_amount", "deposit_percent", "deposit_is_required", "allow_prepaid_deposit")
    def _compute_deposit_amount(self):
        for rec in self:
            if not rec.allow_prepaid_deposit:
                rec.deposit_amount = 0.0
                continue
            amt = 0.0
            if rec.deposit_percent:
                amt = (rec.deposit_percent / 100.0) * (rec.amount_total or 0.0)
            elif rec.deposit_fixed_amount:
                amt = rec.deposit_fixed_amount
            rec.deposit_amount = amt or 0.0

    # -------------------------------------------------------------------------
    # CONSTRAINTS / VALIDATION
    # -------------------------------------------------------------------------
    @api.constrains("start_datetime", "end_datetime")
    def _check_time_range(self):
        for rec in self:
            if rec.start_datetime and rec.end_datetime and rec.end_datetime <= rec.start_datetime:
                raise ValidationError(_("End Time must be greater than Start Time."))

    @api.constrains("doctor_id", "room_id", "start_datetime", "end_datetime", "state")
    def _check_overlaps(self):
        """Prevent double-booking when confirmed/in_progress."""
        for rec in self:
            if rec.state not in ("confirmed", "in_progress"):
                continue
            if not rec.start_datetime or not rec.end_datetime:
                continue

            # Room overlap
            if rec.room_id:
                room_busy = rec.room_id._has_overlapping_booking(
                    rec.start_datetime, rec.end_datetime, ignore_booking_id=rec.id
                )
                if room_busy:
                    raise ValidationError(_("The selected Room is not available for the requested time."))

            # Doctor overlap
            if rec.doctor_id:
                if rec._doctor_overlaps(ignore_booking_id=rec.id):
                    raise ValidationError(_("The selected Doctor is not available for the requested time."))

            # Slot capacity overlap (if slot set)
            if rec.slot_id:
                overlaps = rec.slot_id._count_overlapping_bookings(
                    rec.start_datetime, rec.end_datetime, ignore_booking_id=rec.id
                )
                if overlaps >= max(1, rec.slot_id.capacity or 1):
                    raise ValidationError(_("The selected Slot capacity has been reached in this period."))

            # Resources capacity overlap
            for resource in rec.resource_ids:
                # If any resource cannot support another concurrent usage, block
                if not resource.is_available(rec.start_datetime, rec.end_datetime, ignore_booking_id=rec.id):
                    raise ValidationError(_("At least one required Resource is not available at this time."))

    @api.constrains("doctor_id", "treatment_id")
    def _check_doctor_can_do_treatment(self):
        """Optional guard if doctor holds an 'allowed_treatment_ids' domain."""
        for rec in self:
            if rec.doctor_id and rec.treatment_id and hasattr(rec.doctor_id, "allowed_treatment_ids"):
                if rec.doctor_id.allowed_treatment_ids and rec.treatment_id not in rec.doctor_id.allowed_treatment_ids:
                    raise ValidationError(_("Selected doctor is not configured to perform this treatment."))

    # -------------------------------------------------------------------------
    # NAME / DISPLAY
    # -------------------------------------------------------------------------
    @api.depends('name', 'patient_id')
    def _compute_display_name(self):
        """Odoo 19 display-name bridge preserving the existing ClinicOne label."""
        labels = dict(self.name_get())
        for rec in self:
            rec.display_name = labels.get(rec.id) or rec.name or str(rec.id)

    def name_get(self):
        res = []
        for rec in self:
            label = rec.name or _("Booking")
            if rec.patient_id:
                label = f"{label} - {rec.patient_id.name}"
            res.append((rec.id, label))
        return res

    # -------------------------------------------------------------------------
    # ACTIONS: LIFECYCLE
    # -------------------------------------------------------------------------
    def action_confirm(self):
        """Validate availability, apply policy/channel, lock slot if needed, and (optionally) create appointment."""
        for rec in self:
            if rec.state != "draft":
                continue
            if not rec.start_datetime or not rec.end_datetime:
                raise UserError(_("Please set Start and End Time before confirming."))

            # Room availability
            if rec.room_id and not rec.room_id.is_available(rec.start_datetime, rec.end_datetime, ignore_booking_id=rec.id):
                raise UserError(_("Selected Room is not available for the requested time."))

            # Doctor availability
            if rec.doctor_id and rec._doctor_overlaps(ignore_booking_id=rec.id):
                raise UserError(_("Selected Doctor is not available for the requested time."))

            # Resource availability
            for resource in rec.resource_ids:
                if not resource.is_available(rec.start_datetime, rec.end_datetime, ignore_booking_id=rec.id):
                    raise UserError(_("A required Resource is not available at the requested time."))

            # Policy default decisions (fees/deposits)
            if rec.policy_id:
                dep = rec.policy_id.compute_deposit(rec)
                rec.allow_prepaid_deposit = rec.allow_prepaid_deposit or bool(dep.get("amount"))
                rec.deposit_is_required = bool(dep.get("required"))
                # Only prefill fixed/percent if unset, so manual overrides survive
                if not rec.deposit_fixed_amount and rec.deposit_percent == 0.0:
                    # Mirror source (choose fixed if amount given explicitly)
                    if rec.policy_id.deposit_percent:
                        rec.deposit_percent = rec.policy_id.deposit_percent
                    if rec.policy_id.deposit_fixed_amount:
                        rec.deposit_fixed_amount = rec.policy_id.deposit_fixed_amount

            # Lock slot hint (kept as flag; actual lock depends on UI logic)
            if rec.lock_slot_on_confirm or (rec.channel_id and rec.channel_id.lock_slot_on_confirm):
                # No global lock registry here; rely on capacity/overlap guards.
                pass

            # Handshake with clinic_doctor
            if rec.auto_create_appointment or (rec.channel_id and rec.channel_id.auto_create_appointment):
                try:
                    rec._create_or_link_appointment()
                except Exception as e:
                    # Fail-fast or soft? Choose soft with warning in chatter.
                    rec.message_post(
                        body=_("Appointment handshake failed during confirmation: %s") % (str(e),)
                    )

            rec.state = "confirmed"
            rec.message_post(body=_("Booking confirmed."))

    def action_start(self):
        for rec in self:
            if rec.state != "confirmed":
                raise UserError(_("Only confirmed bookings can be started."))
            rec.checkin_time = fields.Datetime.now()
            rec.state = "in_progress"
            rec.message_post(body=_("Service started."))

    def action_done(self):
        for rec in self:
            if rec.state not in ("confirmed", "in_progress"):
                raise UserError(_("Only confirmed or in-progress bookings can be marked as done."))
            if not rec.checkout_time:
                rec.checkout_time = fields.Datetime.now()
            rec.state = "done"
            rec.is_no_show = False  # cannot be both done and no-show
            rec.message_post(body=_("Service completed."))
            # Trigger post-care workflows (feedback/marketing) via server actions or mail templates (in data/)

    def action_cancel(self, reason=None):
        """Cancel booking, respecting policy if needed (fee handling is up to caller workflow)."""
        for rec in self:
            if rec.state == "cancelled":
                continue
            # Policy decision
            fee_info = {}
            if rec.policy_id:
                fee_info = rec.policy_id.can_cancel(rec)
                # The fee_info can be turned into invoice lines by a wizard or flow.

            rec.state = "cancelled"
            if reason:
                rec.message_post(body=_("Booking cancelled: %s") % reason)
            else:
                rec.message_post(body=_("Booking cancelled."))
            # Optionally, cascade to appointment if linked
            rec._cancel_linked_appointment()

    def action_mark_no_show(self):
        for rec in self:
            if rec.state not in ("confirmed",):
                raise UserError(_("Only confirmed bookings can be marked as no-show."))
            if not rec.policy_id:
                rec.is_no_show = True
                rec.message_post(body=_("Marked as no-show."))
                return
            check = rec.policy_id.can_mark_no_show(rec)
            if not check.get("allowed"):
                raise UserError(check.get("reason") or _("Cannot mark as no-show yet."))
            rec.is_no_show = True
            rec.message_post(body=_("Marked as no-show. A fee may apply."))

    # -------------------------------------------------------------------------
    # ACTIONS: ACCOUNTING
    # -------------------------------------------------------------------------
    def action_create_invoice(self):
        """Create an invoice for this booking (one invoice per booking)."""
        AccountMove = self.env["account.move"]
        AccountMoveLine = self.env["account.move.line"]

        for rec in self:
            if rec.invoice_id:
                raise UserError(_("Invoice already exists for this booking."))

            if not rec.patient_id:
                raise UserError(_("A Patient (customer) is required to create an invoice."))

            # Determine partner receivable company / journal is left to Odoo defaults
            move_vals = {
                "move_type": "out_invoice",
                "partner_id": rec.patient_id.id,
                "invoice_origin": rec.name,
                "invoice_payment_term_id": False,
                "invoice_line_ids": [],
                "company_id": rec.company_id.id,
            }

            # Build invoice lines from booking lines; if none, try from treatment
            if rec.line_ids:
                for line in rec.line_ids:
                    inv_line = rec._prepare_invoice_line_from_booking_line(line)
                    if inv_line:
                        move_vals["invoice_line_ids"].append((0, 0, inv_line))
            elif rec.treatment_id and hasattr(rec.treatment_id, "product_id") and rec.treatment_id.product_id:
                product = rec.treatment_id.product_id
                inv_line = {
                    "name": product.display_name or rec.treatment_id.name or _("Treatment"),
                    "product_id": product.id,
                    "quantity": 1.0,
                    "price_unit": product.lst_price,
                    "tax_ids": [(6, 0, product.taxes_id.ids)],
                    "currency_id": rec.currency_id.id,
                }
                move_vals["invoice_line_ids"].append((0, 0, inv_line))
            else:
                raise UserError(_("No billable lines or treatment found to create an invoice."))

            move = AccountMove.create(move_vals)
            rec.invoice_id = move.id
            rec.message_post(body=_("Invoice created: <a href=# data-oe-model='account.move' data-oe-id='%d'>%s</a>") % (move.id, move.name or move.ref or move.id))
        return True

    def _prepare_invoice_line_from_booking_line(self, line):
        """Map booking line to account.move.line values. Kept generic."""
        product = getattr(line, "product_id", False)
        quantity = getattr(line, "product_uom_qty", 1.0) or 1.0
        name = getattr(line, "name", False) or (product and product.display_name) or _("Booking Line")
        price_unit = getattr(line, "price_unit", None)
        taxes = getattr(line, "tax_ids", self.env["account.tax"])
        if not price_unit and product:
            price_unit = product.lst_price
        return {
            "name": name,
            "product_id": product.id if product else False,
            "quantity": quantity,
            "price_unit": price_unit or 0.0,
            "tax_ids": [(6, 0, taxes.ids)] if taxes else False,
            "currency_id": self.currency_id.id,
        }

    def action_view_invoice(self):
        """Open the primary invoice linked to this booking."""
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_("No invoice is linked to this booking."))
        return {
            "name": _("Invoice"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.invoice_id.id,
            "target": "current",
        }

    def action_view_appointment(self):
        """Open the clinical appointment linked to this booking."""
        self.ensure_one()
        if not self.appointment_id:
            raise UserError(_("No clinical appointment is linked to this booking."))
        return {
            "name": _("Appointment"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.appointment",
            "view_mode": "form",
            "res_id": self.appointment_id.id,
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # HELPER: DOCTOR OVERLAP
    # -------------------------------------------------------------------------
    def _doctor_overlaps(self, ignore_booking_id=None):
        self.ensure_one()
        if not self.doctor_id:
            return False
        domain = [
            ("doctor_id", "=", self.doctor_id.id),
            ("state", "in", ["confirmed", "in_progress"]),
            ("start_datetime", "<", self.end_datetime),
            ("end_datetime", ">", self.start_datetime),
        ]
        if ignore_booking_id:
            domain.append(("id", "!=", ignore_booking_id))
        return bool(self.search_count(domain))

    # -------------------------------------------------------------------------
    # SLOT & CHANNEL ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("slot_id")
    def _onchange_slot_id(self):
        """When selecting a slot, pull sensible defaults."""
        for rec in self:
            slot = rec.slot_id
            if not slot:
                continue
            # Suggest default window if user hasn't set times
            if not rec.start_datetime or not rec.end_datetime:
                s, e = slot._suggest_next_window()
                if s and e:
                    rec.start_datetime = s
                    rec.end_datetime = e
            # Apply defaults onto record (doctor/room/resources/treatment/channel/policy)
            vals = slot.apply_defaults_to_booking_vals(
                {
                    "doctor_id": rec.doctor_id.id if rec.doctor_id else False,
                    "room_id": rec.room_id.id if rec.room_id else False,
                    "treatment_id": rec.treatment_id.id if rec.treatment_id else False,
                    "channel_id": rec.channel_id.id if rec.channel_id else False,
                    "policy_id": rec.policy_id.id if rec.policy_id else False,
                    "resource_ids": [(6, 0, rec.resource_ids.ids)] if rec.resource_ids else False,
                    "start_datetime": rec.start_datetime,
                    "end_datetime": rec.end_datetime,
                }
            )
            for k, v in vals.items():
                # assign only when current value empty/False to respect user input
                if getattr(rec, k, False) in (False, None, 0, []):
                    setattr(rec, k, v)

    @api.onchange("channel_id")
    def _onchange_channel_id(self):
        for rec in self:
            if rec.channel_id:
                try:
                    rec.channel_id.apply_defaults_to_booking(rec)
                except Exception:
                    pass

    # -------------------------------------------------------------------------
    # APPOINTMENT HANDSHAKE (soft integration with clinic_doctor)
    # -------------------------------------------------------------------------
    def _create_or_link_appointment(self):
        """Create or link clinic.appointment record if not present."""
        for rec in self:
            if rec.appointment_id:
                continue
            Appointment = self.env["clinic.appointment"].sudo()
            # Prepare values; this assumes clinic_doctor defines these fields
            vals = {
                "name": rec.name,
                "company_id": rec.company_id.id,
                "patient_id": rec.patient_id.id,
                "doctor_id": rec.doctor_id.id if rec.doctor_id else False,
                "room_id": rec.room_id.clinic_room_id.id if rec.room_id and hasattr(rec.room_id, "clinic_room_id") else False,
                "treatment_id": rec.treatment_id.id if rec.treatment_id else False,
                "start_datetime": rec.start_datetime,
                "end_datetime": rec.end_datetime,
                "booking_id": rec.id,  # back-reference (if clinic_doctor inherits it)
            }
            app = Appointment.create(vals)
            rec.appointment_id = app.id
            rec.message_post(
                body=_("Appointment created: <a href=# data-oe-model='clinic.appointment' data-oe-id='%d'>%s</a>")
                % (app.id, app.name or app.id)
            )

    def _cancel_linked_appointment(self):
        for rec in self:
            if rec.appointment_id:
                try:
                    # attempt to call a standard cancel if exists
                    if hasattr(rec.appointment_id, "action_cancel"):
                        rec.appointment_id.action_cancel()
                    else:
                        rec.appointment_id.write({"active": False})
                    rec.message_post(body=_("Linked appointment has been cancelled/archived."))
                except Exception:
                    rec.message_post(body=_("Failed to cancel the linked appointment (manual review needed)."))

    # -------------------------------------------------------------------------
    # ACTIVITIES
    # -------------------------------------------------------------------------
    def _schedule_initial_activities(self):
        """Schedule reminder/checklist activities upon creation (optional)."""
        for rec in self:
            try:
                # Example: activity to verify patient contact if treatment is invasive
                if rec.treatment_id and hasattr(rec.treatment_id, "is_invasive") and rec.treatment_id.is_invasive:
                    rec.activity_schedule(
                        "mail.mail_activity_data_todo",
                        summary=_("Pre-procedure checklist"),
                        note=_("Verify contraindications and obtain medical consent."),
                        user_id=self.env.user.id,
                    )
            except Exception:
                # keep silent to avoid breaking creation
                pass

    # -------------------------------------------------------------------------
    # UTILITIES
    # -------------------------------------------------------------------------
    def can_reschedule_to(self, new_start, new_end):
        """Return (bool, reason) if this booking can be moved to the new window."""
        self.ensure_one()
        if not new_start or not new_end or new_end <= new_start:
            return (False, _("Invalid target time window."))

        # Room
        if self.room_id and not self.room_id.is_available(new_start, new_end, ignore_booking_id=self.id):
            return (False, _("Room is not available for the selected time."))

        # Doctor
        if self.doctor_id:
            domain = [
                ("doctor_id", "=", self.doctor_id.id),
                ("state", "in", ["confirmed", "in_progress"]),
                ("start_datetime", "<", new_end),
                ("end_datetime", ">", new_start),
                ("id", "!=", self.id),
            ]
            if self.search_count(domain):
                return (False, _("Doctor is not available for the selected time."))

        # Resources
        for resource in self.resource_ids:
            if not resource.is_available(new_start, new_end, ignore_booking_id=self.id):
                return (False, _("A required resource is not available for the selected time."))

        # Slot capacity (if linked)
        if self.slot_id:
            overlaps = self.env["booking.booking"].search_count([
                ("slot_id", "=", self.slot_id.id),
                ("state", "in", ["confirmed", "in_progress"]),
                ("start_datetime", "<", new_end),
                ("end_datetime", ">", new_start),
                ("id", "!=", self.id),
            ])
            if overlaps >= max(1, self.slot_id.capacity or 1):
                return (False, _("Slot capacity has been reached for the selected time."))

        # Policy (reschedule cutoff)
        if self.policy_id:
            info = self.policy_id.can_reschedule(self, at_dt=fields.Datetime.now(), current_reschedules_count=0)
            if not info.get("allowed"):
                return (False, info.get("reason") or _("Rescheduling is not allowed by policy."))

        return (True, _("Allowed."))

    def action_apply_reschedule(self, new_start, new_end):
        """Apply reschedule immediately if allowed."""
        for rec in self:
            ok, reason = rec.can_reschedule_to(new_start, new_end)
            if not ok:
                raise UserError(reason)
            rec.write({"start_datetime": new_start, "end_datetime": new_end})
            rec.message_post(body=_("Booking rescheduled to %s - %s") % (
                fields.Datetime.to_string(new_start), fields.Datetime.to_string(new_end))
            )
            # Optional: sync appointment
            if rec.appointment_id and hasattr(rec.appointment_id, "action_reschedule"):
                try:
                    rec.appointment_id.action_reschedule(new_start, new_end)
                except Exception:
                    rec.message_post(body=_("Failed to reschedule the linked appointment (manual review needed)."))

