
# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/account_move_inherit.py
#
# Purpose
# -------
# Extend accounting documents to be aware of Bookings:
# - Link invoice/bill (account.move) to a booking
# - Pull lines from booking lines (on demand)
# - Enforce patient/partner and company consistency with the booking
# - Optional deposit/fee labeling for analytics (deposit, cancellation fee, no-show fee, reschedule fee)
# - Gentle back-linking to booking.invoice_id on post
#
# Integrations (soft-coupled)
# ---------------------------
# - booking.booking  (M2O link; push/pull lines; handshake on post)
# - booking.line     (per-line link on account.move.line)
# - clinic.treatment (indirect via booking lines/products)
# - booking.policy   (deposit/cancellation/no-show semantics live there; here we only tag/account them)
#
# Notes
# -----
# - All user-facing strings are in English.
# - We avoid enforcing "one invoice per booking" because deposits and follow-up
#   charges may require multiple invoices; the booking header already stores one
#   primary invoice_id (usually the "final" invoice).
# - No hard dependency on controllers or wizards; helpers are callable from UIs or server actions.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =============================================================================
# account.move — Inherit
# =============================================================================
class AccountMove(models.Model):
    _inherit = "account.move"

    # -------------------------------------------------------------------------
    # RELATIONS WITH BOOKING
    # -------------------------------------------------------------------------
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking",
        index=True,
        help="The booking this invoice is related to.",
        copy=False,
    )
    booking_state = fields.Selection( # 002
        related="booking_id.state",
        string="Booking Status",
        store=True,
        readonly=True,
    )
    booking_patient_id = fields.Many2one(
        "res.partner",
        related="booking_id.patient_id",
        string="Patient",
        store=True,
        readonly=True,
    )

    # Labeling for analytics/reporting (optional)
    booking_charge_kind = fields.Selection(
        selection=[
            ("standard", "Standard"),
            ("deposit", "Deposit"),
            ("cancellation_fee", "Cancellation Fee"),
            ("no_show_fee", "No-show Fee"),
            ("reschedule_fee", "Reschedule Fee"),
        ],
        string="Booking Charge Kind",
        default="standard",
        help="Label this invoice for reporting. Does not affect accounting logic.",
    )
    booking_deposit_amount = fields.Monetary(
        string="Deposit Amount",
        currency_field="currency_id",
        compute="_compute_booking_deposit_amount",
        store=True,
        help="Total untaxed amount when this invoice is labeled as a Deposit.",
    )

    # Convenience copy of channel/policy (not enforced; filled from booking if present)
    booking_channel_id = fields.Many2one(
        "booking.channel",
        string="Booking Channel",
        help="Channel context copied from the booking for reporting.",
        copy=False,
    )
    booking_policy_id = fields.Many2one(
        "booking.policy",
        string="Booking Policy",
        help="Policy context copied from the booking for reporting.",
        copy=False,
    )

    # -------------------------------------------------------------------------
    # DEFAULTS / ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("booking_id")
    def _onchange_booking_id(self):
        """
        When a booking is selected:
        - Ensure partner is the patient (if empty), and set invoice_origin
        - Copy channel/policy for reporting
        - Align company to booking's company if not set (common in draft)
        """
        for rec in self:
            b = rec.booking_id
            if not b:
                continue
            # Partner
            if not rec.partner_id and b.patient_id:
                rec.partner_id = b.patient_id.id
            # Origin reference
            if not rec.invoice_origin:
                rec.invoice_origin = b.name
            # Company (only if empty; otherwise enforce via constraint)
            if not rec.company_id and b.company_id:
                rec.company_id = b.company_id.id
            # Channel/Policy snapshot
            if b.channel_id:
                rec.booking_channel_id = b.channel_id.id
            if b.policy_id:
                rec.booking_policy_id = b.policy_id.id

    @api.onchange("partner_id")
    def _onchange_partner_id_booking_guard(self):
        """
        Guard: If booking is selected and partner differs from patient,
        keep it but show a warning (hard enforcement is done via constraint).
        """
        for rec in self:
            if rec.booking_id and rec.partner_id and rec.partner_id != rec.booking_id.patient_id:
                return {
                    "warning": {
                        "title": _("Partner / Patient Mismatch"),
                        "message": _(
                            "Selected partner differs from the booking patient (%s). "
                            "You can keep it, but posting will enforce consistency."
                        ) % (rec.booking_id.patient_id.display_name,),
                    }
                }
        return {}

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("booking_id", "partner_id")
    def _check_partner_patient_consistency(self):
        """
        When a booking is linked, partner must be that booking's patient.
        """
        for rec in self:
            if rec.booking_id and rec.partner_id and rec.partner_id != rec.booking_id.patient_id:
                raise ValidationError(_("Partner must match the Booking's Patient."))

    @api.constrains("booking_id", "company_id")
    def _check_company_consistency(self):
        for rec in self:
            if rec.booking_id and rec.company_id and rec.company_id != rec.booking_id.company_id:
                raise ValidationError(_("Company must match the Booking's Company."))

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("booking_charge_kind", "invoice_line_ids.price_subtotal", "move_type")
    def _compute_booking_deposit_amount(self):
        for rec in self:
            if rec.booking_charge_kind == "deposit" and rec.is_invoice(include_receipts=True):
                # Sum untaxed line amounts (same as 'amount_untaxed' but kept independent)
                rec.booking_deposit_amount = sum(rec.invoice_line_ids.mapped("price_subtotal"))
            else:
                rec.booking_deposit_amount = 0.0

    # -------------------------------------------------------------------------
    # ACTIONS / HOOKS
    # -------------------------------------------------------------------------
    def action_post(self):
        """
        On posting:
        - Ensure Booking link handshake (set booking.invoice_id if empty)
        - Post a message on the booking for traceability
        """
        res = super().action_post()
        for rec in self:
            b = rec.booking_id
            if not b:
                continue
            try:
                # Handshake: set booking.invoice_id if empty
                if not b.invoice_id:
                    b.invoice_id = rec.id
                # Chatter note on booking
                b.message_post(
                    body=_("Invoice posted: <a href='#' data-oe-model='account.move' data-oe-id='%d'>%s</a>")
                         % (rec.id, rec.name or rec.ref or rec.id)
                )
            except Exception:
                # Never block posting due to handshake issues
                pass
        return res

    def action_pull_lines_from_booking(self):
        """
        Create invoice lines from linked booking lines.
        Safe-guard:
        - Does nothing if no booking or there are already non-display invoice lines
        - Raises if move is not draft
        """
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("You can only pull lines on a draft invoice."))
            if not rec.booking_id:
                raise UserError(_("Please link a Booking first."))
            if any(not l.display_type for l in rec.invoice_line_ids):
                raise UserError(_("This invoice already has commercial lines."))

            inv_lines_vals = []
            for bline in rec.booking_id.line_ids:
                vals = rec._prepare_invoice_line_from_booking_line(bline)
                if vals:
                    inv_lines_vals.append((0, 0, vals))
            if not inv_lines_vals and rec.booking_id.treatment_id and hasattr(rec.booking_id.treatment_id, "product_id"):
                # Fallback: use treatment's product
                product = rec.booking_id.treatment_id.product_id
                if product:
                    inv_lines_vals.append((0, 0, {
                        "name": product.display_name or rec.booking_id.treatment_id.name or _("Treatment"),
                        "product_id": product.id,
                        "quantity": 1.0,
                        "price_unit": product.lst_price,
                        "tax_ids": [(6, 0, product.taxes_id.ids)],
                        "booking_line_id": False,
                    }))

            if not inv_lines_vals:
                raise UserError(_("No billable booking lines or treatment found."))

            rec.write({"invoice_line_ids": inv_lines_vals})

            # Copy channel/policy snapshot if missing
            if rec.booking_id.channel_id and not rec.booking_channel_id:
                rec.booking_channel_id = rec.booking_id.channel_id.id
            if rec.booking_id.policy_id and not rec.booking_policy_id:
                rec.booking_policy_id = rec.booking_id.policy_id.id

    def _prepare_invoice_line_from_booking_line(self, bline):
        """
        Map booking.line to account.move.line values.
        This is similar to booking_booking._prepare_invoice_line_from_booking_line,
        but includes a back-link (booking_line_id) for analytics.
        """
        product = getattr(bline, "product_id", False)
        quantity = getattr(bline, "product_uom_qty", 1.0) or 1.0
        name = getattr(bline, "name", False) or (product and product.display_name) or _("Booking Line")
        price_unit = getattr(bline, "price_unit", product and product.lst_price or 0.0)
        taxes = getattr(bline, "tax_ids", self.env["account.tax"])
        return {
            "name": name,
            "product_id": product.id if product else False,
            "quantity": quantity,
            "price_unit": price_unit or 0.0,
            "tax_ids": [(6, 0, taxes.ids)] if taxes else False,
            "booking_line_id": bline.id,
        }

    # -------------------------------------------------------------------------
    # NAVIGATION
    # -------------------------------------------------------------------------
    def action_view_booking(self):
        """
        Open the linked booking (convenience from invoice).
        """
        self.ensure_one()
        if not self.booking_id:
            raise UserError(_("This document is not linked to any booking."))
        return {
            "name": _("Booking"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "form",
            "res_id": self.booking_id.id,
            "target": "current",
        }


# =============================================================================
# account.move.line — Inherit
# =============================================================================
class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # Link back to Booking & Booking Line
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking",
        related="move_id.booking_id",
        store=True,
        readonly=True,
    )
    booking_line_id = fields.Many2one(
        "booking.line",
        string="Booking Line",
        index=True,
        help="Original booking line this invoice line corresponds to.",
        copy=False,
    )

    # Fee labeling at line level (optional, for analytics; does not alter accounting)
    is_booking_fee = fields.Boolean(
        string="Is Booking Fee",
        help="Enable to mark this line as a fee (e.g., cancellation, no-show, reschedule).",
        default=False,
    )
    booking_fee_type = fields.Selection(
        selection=[
            ("deposit", "Deposit"),
            ("cancellation_fee", "Cancellation Fee"),
            ("no_show_fee", "No-show Fee"),
            ("reschedule_fee", "Reschedule Fee"),
            ("other", "Other"),
        ],
        string="Booking Fee Type",
        help="Type of fee represented by this line (for reporting).",
    )

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("booking_line_id")
    def _onchange_booking_line_id(self):
        """
        When a booking line is selected, prefill product/qty/price/taxes/description.
        """
        for rec in self:
            bl = rec.booking_line_id
            if not bl:
                continue
            product = bl.product_id
            rec.name = bl.name or (product and product.display_name) or _("Booking Line")
            rec.product_id = product.id if product else False
            rec.quantity = bl.product_uom_qty or 1.0
            rec.price_unit = (bl.price_unit or (product and product.lst_price) or 0.0)
            rec.tax_ids = [(6, 0, bl.tax_ids.ids)] if bl.tax_ids else False

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("booking_line_id", "move_id")
    def _check_booking_line_company_and_header(self):
        """
        Ensure the booking line belongs to the same booking as the invoice header.
        """
        for rec in self:
            if rec.booking_line_id and rec.move_id and rec.move_id.booking_id:
                if rec.booking_line_id.booking_id != rec.move_id.booking_id:
                    raise ValidationError(
                        _("The selected Booking Line does not belong to the invoice's Booking.")
                    )

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
        "ir.tags",
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


# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/booking_channel.py
#
# Purpose:
# - Define booking channels (Walk-in, Phone, Website, Portal, WhatsApp, etc.)
# - Centralize rules/policies per channel (deposit, cancellation, default mail templates)
# - Provide safe hooks for applying channel defaults into bookings
#
# Key integrations (soft-coupled):
# - booking.booking (channel_id -> this model)
# - booking.policy (channel-level default policy)
# - mail.template (reminder/feedback templates)
# - website (website_published flag for online channels)
# - account/currency/company awareness for deposit handling
#
# Notes:
# - All user-facing strings are in English, as requested.
# - Avoids external dependencies beyond what clinic_booking already declares.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class BookingChannel(models.Model):
    _name = "booking.channel"
    _description = "Booking Channel"
    _order = "sequence, name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # -------------------------------------------------------------------------
    # BASIC / IDENTITY
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Channel Name",
        required=True,
        tracking=True,
        help="Human-friendly name of the booking channel (e.g., Walk-in, Phone, Website, Portal).",
    )

    code = fields.Char(
        string="Technical Code",
        required=True,
        index=True,
        tracking=True,
        help="Unique, URL-safe technical code for this channel, e.g. 'walkin', 'phone', 'website'.",
    )

    channel_type = fields.Selection(
        selection=[
            ("walkin", "Walk-in"),
            ("phone", "Phone"),
            ("website", "Website"),
            ("portal", "Portal"),
            ("whatsapp", "WhatsApp"),
            ("marketplace", "Marketplace"),
            ("kiosk", "Kiosk"),
            ("mobile_app", "Mobile App"),
            ("other", "Other"),
        ],
        string="Type",
        required=True,
        default="walkin",
        tracking=True,
        help="Classify the channel to enable type-specific behaviors (online flags, defaults, etc.).",
    )

    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to hide this channel from selection while keeping historical references.",
    )

    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Lower is earlier in lists. Used to order channels in selection widgets.",
    )

    color = fields.Integer(
        string="Color Index",
        help="Optional color used in Kanban/Calendar indicators for quick visual grouping.",
    )

    description = fields.Text(
        string="Description",
        help="Optional description or internal notes about this channel.",
    )

    # -------------------------------------------------------------------------
    # COMPANY / CURRENCY CONTEXT
    # -------------------------------------------------------------------------
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
        required=True,
        help="Company to which this channel belongs.",
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # ONLINE FLAGS & WEBSITE EXPOSURE
    # -------------------------------------------------------------------------
    is_online = fields.Boolean(
        string="Online Channel",
        compute="_compute_is_online",
        store=True,
        help="True when the channel is used online (Website, Portal, Mobile App, Marketplace).",
    )

    website_published = fields.Boolean(
        string="Show on Website",
        help="If enabled, expose this channel to website features (forms/flows).",
    )

    website_route = fields.Char(
        string="Website Route",
        help="Optional website route/endpoint where this channel is used, e.g. '/book/clinic'.",
    )

    # -------------------------------------------------------------------------
    # DEFAULT POLICY & COMMUNICATION TEMPLATES
    # -------------------------------------------------------------------------
    policy_id = fields.Many2one(
        "booking.policy",
        string="Default Policy",
        index=True,
        help="Default policy to be applied when a booking is created with this channel.",
    )

    reminder_template_id = fields.Many2one(
        "mail.template",
        string="Reminder Email Template",
        domain=[("model", "=", "booking.booking")],
        help="Default reminder email template used for bookings of this channel.",
    )

    feedback_template_id = fields.Many2one(
        "mail.template",
        string="Feedback Email Template",
        domain=[("model", "=", "booking.booking")],
        help="Default feedback email template used after the booking is done.",
    )

    # -------------------------------------------------------------------------
    # DEPOSIT / PREPAID SETTINGS (OPTIONAL)
    # -------------------------------------------------------------------------
    allow_prepaid_deposit = fields.Boolean(
        string="Allow Prepaid Deposit",
        help="Enable this to require or allow a deposit for bookings from this channel.",
    )

    deposit_is_required = fields.Boolean(
        string="Deposit Required",
        help="If enabled, a deposit is mandatory for bookings from this channel.",
    )

    deposit_fixed_amount = fields.Monetary(
        string="Deposit Fixed Amount",
        currency_field="currency_id",
        help="Fixed deposit amount to request for bookings in this channel. "
             "Leave 0.0 if using percentage.",
    )

    deposit_percent = fields.Float(
        string="Deposit Percentage",
        help="Deposit percentage to request for bookings in this channel (0 - 100). "
             "Leave 0.0 if using fixed amount.",
    )

    # -------------------------------------------------------------------------
    # AUTOMATION & BEHAVIOR
    # -------------------------------------------------------------------------
    auto_create_appointment = fields.Boolean(
        string="Auto-create Appointment on Confirm",
        help="When enabled, confirming a booking will attempt to create/link a clinic.appointment "
             "in the clinic_doctor module following configured handshake rules.",
    )

    lock_slot_on_confirm = fields.Boolean(
        string="Lock Slot on Confirm",
        help="If enabled, the selected slot becomes locked to prevent double-booking in parallel flows.",
    )

    # -------------------------------------------------------------------------
    # STATS / LINKS
    # -------------------------------------------------------------------------
    bookings_count = fields.Integer(
        string="Bookings",
        compute="_compute_bookings_count",
        help="Number of bookings created under this channel (excluding archived).",
    )

    last_booking_id = fields.Many2one(
        "booking.booking",
        string="Last Booking",
        compute="_compute_last_booking",
        help="Most recent booking made via this channel (by create date).",
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    _code_company_unique = models.Constraint(
        'unique(code, company_id)',
        'Channel Technical Code must be unique per company.',
    )

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Channel Name must be unique per company.',
    )

    @api.constrains("code")
    def _check_code_format(self):
        for rec in self:
            if rec.code:
                if " " in rec.code:
                    raise ValidationError(_("Channel Technical Code must not contain spaces."))
                if not rec.code.replace("_", "").replace("-", "").isalnum():
                    raise ValidationError(_("Channel Technical Code must be alphanumeric (underscores/dashes allowed)."))

    @api.constrains("deposit_percent")
    def _check_deposit_percent(self):
        for rec in self:
            if rec.deposit_percent and (rec.deposit_percent < 0.0 or rec.deposit_percent > 100.0):
                raise ValidationError(_("Deposit Percentage must be between 0 and 100."))

    @api.constrains("allow_prepaid_deposit", "deposit_is_required", "deposit_fixed_amount", "deposit_percent")
    def _check_deposit_config(self):
        for rec in self:
            if not rec.allow_prepaid_deposit:
                # Reset enforced values (not strictly necessary but avoids confusion)
                if rec.deposit_is_required or rec.deposit_fixed_amount or rec.deposit_percent:
                    # No hard error; allow values to remain for quick toggling.
                    continue
            else:
                # At least one of fixed or percent should be non-zero when required
                if rec.deposit_is_required and not (rec.deposit_fixed_amount or rec.deposit_percent):
                    raise ValidationError(
                        _("When 'Deposit Required' is enabled, either a Fixed Amount or a Percentage must be set.")
                    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("channel_type")
    def _compute_is_online(self):
        online_types = {"website", "portal", "mobile_app", "marketplace"}
        for rec in self:
            rec.is_online = rec.channel_type in online_types

    def _domain_bookings(self):
        """Common domain for counting bookings of this channel."""
        return [("channel_id", "=", self.id), ("active", "=", True)]

    def _compute_bookings_count(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            rec.bookings_count = Booking.search_count(rec._domain_bookings())

    def _compute_last_booking(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            last = Booking.search(rec._domain_bookings(), order="create_date desc, id desc", limit=1)
            rec.last_booking_id = last.id if last else False

    # -------------------------------------------------------------------------
    # NAME / DISPLAY
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        type_map = dict(self._fields["channel_type"].selection)
        for rec in self:
            tlabel = type_map.get(rec.channel_type, rec.channel_type)
            label = f"{rec.name} [{tlabel}]"
            if rec.company_id and self.env.companies and len(self.env.companies) > 1:
                label = f"{label} - {rec.company_id.name}"
            res.append((rec.id, label))
        return res

    # -------------------------------------------------------------------------
    # ACTIONS / HOOKS
    # -------------------------------------------------------------------------
    def action_view_bookings(self):
        """Open bookings filtered by this channel."""
        self.ensure_one()
        action = {
            "name": _("Bookings"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "list,form,calendar,kanban,pivot,graph,activity",
            "domain": [("channel_id", "=", self.id)],
            "context": {"default_channel_id": self.id},
        }
        # Try to use a predefined action (if present) for consistent view layouts
        try:
            action_def = self.env.ref("clinic_booking.action_booking_list", raise_if_not_found=False)
            if action_def:
                action = action_def.read()[0]
                # Override domain/context to focus on this channel
                action.update({"domain": [("channel_id", "=", self.id)]})
                ctx = action.get("context", {}) or {}
                ctx.update({"default_channel_id": self.id})
                action["context"] = ctx
        except Exception:
            # Fall back to generic action dict above
            pass
        return action

    def apply_defaults_to_booking(self, booking):
        """Apply channel defaults into a booking record (not saved).
        This is a safe hook that can be called from booking.onchange/channel onchange.
        Only set fields when not already specified by the user or upstream logic."""
        self.ensure_one()
        if not booking:
            return

        # Policy
        if self.policy_id and not booking.policy_id:
            booking.policy_id = self.policy_id

        # Templates (store on booking if fields exist; otherwise, they will be picked by mail rules)
        if hasattr(booking, "reminder_template_id") and not booking.reminder_template_id and self.reminder_template_id:
            booking.reminder_template_id = self.reminder_template_id
        if hasattr(booking, "feedback_template_id") and not booking.feedback_template_id and self.feedback_template_id:
            booking.feedback_template_id = self.feedback_template_id

        # Optional flags (store if booking has these fields)
        if hasattr(booking, "lock_slot_on_confirm") and booking.lock_slot_on_confirm is None:
            booking.lock_slot_on_confirm = self.lock_slot_on_confirm
        if hasattr(booking, "auto_create_appointment") and booking.auto_create_appointment is None:
            booking.auto_create_appointment = self.auto_create_appointment

        # Deposit hints: only if booking has such fields (we keep this generic to avoid tight coupling)
        for fname, value in [
            ("allow_prepaid_deposit", self.allow_prepaid_deposit),
            ("deposit_is_required", self.deposit_is_required),
            ("deposit_fixed_amount", self.deposit_fixed_amount),
            ("deposit_percent", self.deposit_percent),
        ]:
            if hasattr(booking, fname):
                current = getattr(booking, fname)
                # Populate only if not explicitly set
                if current in (False, 0.0, None):
                    setattr(booking, fname, value)

    # -------------------------------------------------------------------------
    # DEFAULTS (HELPERS)
    # -------------------------------------------------------------------------
    @api.model
    def create(self, vals):
        # If no policy is provided, try to pick a sensible default by channel type
        if not vals.get("policy_id"):
            default_policy = self._find_default_policy_for_channel(vals.get("channel_type"))
            if default_policy:
                vals["policy_id"] = default_policy.id
        rec = super().create(vals)
        return rec

    def write(self, vals):
        # Small guard rails: normalize code
        if "code" in vals and vals["code"]:
            vals["code"] = vals["code"].strip()
        return super().write(vals)

    def _find_default_policy_for_channel(self, channel_type):
        """Find a default policy record suitable for a given channel type.
        We keep it resilient by trying known XML IDs then falling back to any active policy."""
        Policy = self.env["booking.policy"].sudo()
        # Try by XML-ID convention (if the data file defines them)
        xml_candidates_by_type = {
            "website": "clinic_booking.policy_online_default",
            "portal": "clinic_booking.policy_online_default",
            "mobile_app": "clinic_booking.policy_online_default",
            "marketplace": "clinic_booking.policy_online_default",
            "walkin": "clinic_booking.policy_walkin_default",
            "phone": "clinic_booking.policy_phone_default",
            "kiosk": "clinic_booking.policy_walkin_default",
        }
        xml_id = xml_candidates_by_type.get(channel_type or "", "clinic_booking.policy_default")
        rec = self.env.ref(xml_id, raise_if_not_found=False)
        if rec:
            return rec

        # Fallback: any active policy for the company
        company = self.env.company
        fallback = Policy.search([("company_id", "=", company.id), ("active", "=", True)], limit=1)
        return fallback

    # -------------------------------------------------------------------------
    # ONCHANGE & UX HELPERS
    # -------------------------------------------------------------------------
    @api.onchange("channel_type")
    def _onchange_channel_type(self):
        # Auto-toggle online flag and website exposure hint
        if self.channel_type in {"website", "portal", "mobile_app", "marketplace"}:
            self.website_published = True
        else:
            # Do not force-disable; user may choose to publish routing pages
            self.website_published = self.website_published

        # Suggest policy if none
        if not self.policy_id:
            pol = self._find_default_policy_for_channel(self.channel_type)
            if pol:
                self.policy_id = pol

    @api.onchange("allow_prepaid_deposit")
    def _onchange_allow_prepaid_deposit(self):
        if not self.allow_prepaid_deposit:
            # Keep values as-is; do not erase to avoid losing config upon toggling.
            pass

    @api.onchange("deposit_fixed_amount", "deposit_percent", "deposit_is_required")
    def _onchange_deposit_values(self):
        # Gentle user guidance; hard validation is in constrains
        if self.deposit_is_required and not (self.deposit_fixed_amount or self.deposit_percent):
            return {
                "warning": {
                    "title": _("Deposit Configuration"),
                    "message": _(
                        "When a deposit is required, please set either a Fixed Amount or a Percentage."
                    ),
                }
            }
        return {}

    # -------------------------------------------------------------------------
    # MESSAGING SHORTCUTS
    # -------------------------------------------------------------------------
    def message_post_channel_note(self, body):
        """Convenience helper for consistent chatter messages."""
        if not body:
            return False
        for rec in self:
            rec.message_post(body=body)
        return True


class BookingChannelMixin(models.AbstractModel):
    """
    Abstract mixin to provide a reusable channel_id field to other models
    (e.g., booking lines, wizards, or related objects) without redefining it.
    """
    _name = "booking.channel.mixin"
    _description = "Booking Channel Mixin"

    channel_id = fields.Many2one(
        "booking.channel",
        string="Channel",
        index=True,
        help="Booking channel associated with this record.",
    )

    @api.onchange("channel_id")
    def _onchange_channel_id(self):
        """Hook for inheriting models: apply channel defaults if the target model provides
        an 'apply_defaults_from_channel' method, otherwise do nothing."""
        if self.channel_id and hasattr(self, "apply_defaults_from_channel"):
            # implementors can define apply_defaults_from_channel(self, channel)
            try:
                self.apply_defaults_from_channel(self.channel_id)
            except Exception:
                # Silently ignore to keep the mixin generic/safe.
                pass

# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/booking_feedback_link.py
#
# Purpose
# -------
# Manage post-visit feedback invitations:
# - Generate secure tokenized links per booking/patient
# - Build public URL (portal/website) to collect feedback
# - Send email/SMS (email implemented via mail.template)
# - Track lifecycle: draft → queued → sent → opened → submitted / expired / revoked
# - Optional reminders; auto-expire by cron
#
# Integrations (soft-coupled)
# ---------------------------
# - booking.booking (mandatory link) / patient/doctor/treatment (related)
# - booking.channel (default feedback template + optional website route)
# - booking.policy (for retention rules; optional)
# - mail.template / mail.mail (outbound email)
# - portal/website controller should validate token and call 'action_mark_opened' / 'action_submit_feedback'
#
# Notes
# -----
# - All user-facing strings are in English.
# - Controllers/views/templates are defined elsewhere (controllers/ & data/ XML).
# - This model is safe to use even if website/portal is not installed; link builds from base URL.

import uuid
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class BookingFeedbackLink(models.Model):
    _name = "booking.feedback.link"
    _description = "Booking Feedback Link"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    # -------------------------------------------------------------------------
    # CORE RELATIONS / CONTEXT
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        default="/",
        help="Internal reference for this feedback invitation.",
        tracking=True,
    )
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking",
        required=True,
        ondelete="cascade",
        index=True,
        help="The booking for which this feedback is requested.",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="booking_id.company_id",
        store=True,
        readonly=True,
    )
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="booking_id.patient_id",
        store=True,
        readonly=True,
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        related="booking_id.doctor_id",
        store=True,
        readonly=True,
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        related="booking_id.treatment_id",
        store=True,
        readonly=True,
    )
    channel_id = fields.Many2one(
        "booking.channel",
        string="Channel",
        help="Channel driving default templates and website route, if any.",
    )
    policy_id = fields.Many2one(
        "booking.policy",
        string="Policy",
        help="Optional policy context for retention/terms.",
    )

    # -------------------------------------------------------------------------
    # TOKEN & ACCESS
    # -------------------------------------------------------------------------
    token = fields.Char(
        string="Access Token",
        required=True,
        copy=False,
        index=True,
        help="Opaque token used for secure public access.",
    )
    access_path = fields.Char(
        string="Access Path",
        compute="_compute_access_path",
        store=True,
        help="Relative path used to build the public URL (includes token).",
    )
    access_url = fields.Char(
        string="Public URL",
        compute="_compute_access_url",
        help="Absolute URL constructed from base URL + Access Path.",
    )

    allow_anonymous_update = fields.Boolean(
        string="Allow Anonymous Update",
        default=True,
        help="If enabled, public visitors can submit feedback using only the token.",
    )

    # -------------------------------------------------------------------------
    # LIFECYCLE / STATUS
    # -------------------------------------------------------------------------
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("queued", "Queued"),
            ("sent", "Sent"),
            ("opened", "Opened"),
            ("submitted", "Submitted"),
            ("expired", "Expired"),
            ("revoked", "Revoked"),
        ],
        string="Status",
        required=True,
        default="draft",
        tracking=True,
        help="Lifecycle status of the feedback invitation.",
    )
    sent_at = fields.Datetime(
        string="Sent At",
        help="Timestamp when the invitation was sent.",
        tracking=True,
    )
    opened_at = fields.Datetime(
        string="First Opened At",
        help="Timestamp when the public link was first opened.",
        tracking=True,
    )
    submitted_at = fields.Datetime(
        string="Submitted At",
        help="Timestamp when feedback was submitted.",
        tracking=True,
    )
    expiration_days = fields.Integer(
        string="Valid For (days)",
        default=14,
        help="Number of days after which the link expires.",
    )
    expire_at = fields.Datetime(
        string="Expires At",
        compute="_compute_expire_at",
        store=True,
        help="Datetime when the link becomes invalid.",
    )
    is_expired = fields.Boolean(
        string="Is Expired",
        compute="_compute_is_expired",
        store=True,
        help="True if current time is past the expiration time.",
    )

    # Reminders (basic counters)
    reminder_count = fields.Integer(
        string="Reminders Sent",
        default=0,
        help="How many reminder emails were sent for this feedback link.",
    )
    last_reminder_at = fields.Datetime(
        string="Last Reminder At",
        help="Timestamp when the last reminder was sent.",
    )

    # -------------------------------------------------------------------------
    # COMMUNICATION TEMPLATES
    # -------------------------------------------------------------------------
    mail_template_id = fields.Many2one(
        "mail.template",
        string="Email Template",
        domain=[("model", "=", "booking.feedback.link")],
        help="Template used when sending the feedback invitation.",
    )
    # Fallback to channel.feedback_template_id if not set

    # For audit/reference
    last_mail_id = fields.Many2one(
        "mail.mail",
        string="Last Mail",
        help="Technical link to the last mail sent for this invitation.",
        copy=False,
    )

    # -------------------------------------------------------------------------
    # FEEDBACK CONTENT
    # -------------------------------------------------------------------------
    rating_value = fields.Selection(
        selection=[
            ("1", "1 - Very Dissatisfied"),
            ("2", "2 - Dissatisfied"),
            ("3", "3 - Neutral"),
            ("4", "4 - Satisfied"),
            ("5", "5 - Very Satisfied"),
        ],
        string="Rating",
        help="Overall rating given by the patient.",
    )
    comment = fields.Text(
        string="Comment",
        help="Free text feedback from the patient.",
    )
    would_recommend = fields.Selection(
        selection=[("yes", "Yes"), ("no", "No"), ("na", "Prefer not to say")],
        string="Would Recommend",
        help="Whether the patient would recommend our clinic to others.",
        default="na",
    )

    # Optional tags/labels for analytics
    tag_ids = fields.Many2many(
        "ir.tags",
        "booking_feedback_tag_rel",
        "link_id",
        "tag_id",
        string="Tags",
        help="Optional tags for grouping and reporting.",
    )

    # -------------------------------------------------------------------------
    # SQL CONSTRAINTS
    # -------------------------------------------------------------------------
    _token_uniq = models.Constraint(
        'unique(token)',
        'Access Token must be unique.',
    )

    # -------------------------------------------------------------------------
    # DEFAULTS / CREATE / WRITE
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env.ref("clinic_booking.sequence_booking_feedback", raise_if_not_found=False)
        for vals in vals_list:
            # Name
            if not vals.get("name") or vals.get("name") == "/":
                vals["name"] = seq._next() if seq else self.env["ir.sequence"].next_by_code("booking.feedback.link")
            # Token
            if not vals.get("token"):
                vals["token"] = uuid.uuid4().hex  # 32 chars, URL-safe
            # Defaults from booking if not set
            if vals.get("booking_id"):
                booking = self.env["booking.booking"].browse(vals["booking_id"])
                if booking:
                    vals.setdefault("channel_id", booking.channel_id.id or False)
                    vals.setdefault("policy_id", booking.policy_id.id or False)
            # Template fallback to channel
            if not vals.get("mail_template_id") and vals.get("channel_id"):
                channel = self.env["booking.channel"].browse(vals["channel_id"])
                if channel and channel.feedback_template_id:
                    vals["mail_template_id"] = channel.feedback_template_id.id
        recs = super().create(vals_list)
        return recs

    def write(self, vals):
        # Prevent altering token after sending (safety)
        for rec in self:
            if rec.state in ("sent", "opened", "submitted") and "token" in vals:
                raise UserError(_("Token cannot be changed after the invitation has been sent."))
        return super().write(vals)

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("booking_id.end_datetime", "expiration_days", "state")
    def _compute_expire_at(self):
        for rec in self:
            base = rec.booking_id.end_datetime or fields.Datetime.now()
            if not rec.expiration_days or rec.expiration_days <= 0:
                # Infinite validity not recommended; cap at 365d for safety
                rec.expire_at = fields.Datetime.to_string(
                    fields.Datetime.from_string(base) + timedelta(days=365)
                )
            else:
                rec.expire_at = fields.Datetime.to_string(
                    fields.Datetime.from_string(base) + timedelta(days=rec.expiration_days)
                )

    @api.depends("expire_at", "state")
    def _compute_is_expired(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.is_expired = bool(rec.expire_at and fields.Datetime.from_string(rec.expire_at) < now)
            # Optionally auto-mark state, but leave to cron to avoid surprise state flips in UI

    @api.depends("token", "channel_id.website_route")
    def _compute_access_path(self):
        """
        Build relative path for feedback collection:
        - Prefer channel.website_route if provided (e.g., '/clinic/feedback/')
        - Default to '/clinic/feedback/'
        Rules:
          - If route ends with '?', append 'token=...'
          - If route ends with '/', append token as path segment
          - Else, append '/{token}'
        """
        for rec in self:
            token = rec.token or ""
            route = (rec.channel_id.website_route or "/clinic/feedback/").strip()
            if not route.startswith("/"):
                route = "/" + route
            if route.endswith("?"):
                rec.access_path = f"{route}token={token}"
            elif route.endswith("/"):
                rec.access_path = f"{route}{token}"
            else:
                rec.access_path = f"{route}/{token}"

    def _get_base_url(self):
        ICP = self.env["ir.config_parameter"].sudo()
        return ICP.get_param("web.base.url", default="http://localhost:8069")

    @api.depends("access_path")
    def _compute_access_url(self):
        base = self._get_base_url()
        for rec in self:
            rec.access_url = base.rstrip("/") + (rec.access_path or "")

    # -------------------------------------------------------------------------
    # ACTIONS — GENERATION & SENDING
    # -------------------------------------------------------------------------
    def action_generate_link(self):
        """Ensure token/path/url are generated and set state to queued."""
        for rec in self:
            if not rec.token:
                rec.token = uuid.uuid4().hex
            # Trigger compute
            rec._compute_access_path()
            rec._compute_access_url()
            if rec.state == "draft":
                rec.state = "queued"
            rec.message_post(body=_("Feedback link generated: <a href='%s' target='_blank'>Open</a>") % (rec.access_url,))

    def _get_mail_template(self):
        self.ensure_one()
        # Priority: record → channel.feedback_template → module default
        tmpl = self.mail_template_id
        if not tmpl and self.channel_id and self.channel_id.feedback_template_id:
            tmpl = self.channel_id.feedback_template_id
        if not tmpl:
            tmpl = self.env.ref("clinic_booking.booking_feedback_email_template", raise_if_not_found=False)
        return tmpl

    def _prepare_mail_context(self):
        self.ensure_one()
        # Context variables usable in qweb template
        return {
            "feedback_link": self,
            "booking": self.booking_id,
            "patient": self.patient_id,
            "doctor": self.doctor_id,
            "treatment": self.treatment_id,
            "access_url": self.access_url,
            "token": self.token,
            "company": self.company_id,
        }

    def action_send_invitation(self, force_send=True):
        """Send the feedback invitation via email using the selected template."""
        for rec in self:
            if rec.is_expired or rec.state in ("expired", "revoked"):
                raise UserError(_("Cannot send an expired or revoked invitation."))
            if not rec.patient_id or not rec.patient_id.email:
                raise UserError(_("Patient has no email address."))

            tmpl = rec._get_mail_template()
            if not tmpl:
                raise UserError(_("No email template configured for feedback invitations."))

            # Ensure link
            if not rec.token:
                rec.token = uuid.uuid4().hex
                rec._compute_access_path()
                rec._compute_access_url()

            email_values = {"email_to": rec.patient_id.email}
            ctx = {"default_model": "booking.feedback.link", "default_res_id": rec.id}
            ctx.update(rec._prepare_mail_context())

            mail_id = tmpl.with_context(ctx).send_mail(rec.id, force_send=force_send, email_values=email_values)
            if mail_id:
                rec.last_mail_id = mail_id
            rec.sent_at = fields.Datetime.now()
            rec.state = "sent"
            rec.message_post(
                body=_("Feedback invitation sent to %s. <a href='%s' target='_blank'>Public link</a>") %
                     (rec.patient_id.email, rec.access_url)
            )
        return True

    def action_send_reminder(self, force_send=True):
        """Send a reminder email if not submitted and not expired."""
        for rec in self:
            if rec.state in ("submitted", "revoked"):
                raise UserError(_("This feedback link has already been completed or revoked."))
            if rec.is_expired:
                raise UserError(_("This feedback link is already expired."))
            rec.action_send_invitation(force_send=force_send)
            rec.reminder_count += 1
            rec.last_reminder_at = fields.Datetime.now()
            rec.message_post(body=_("Reminder sent."))

    # -------------------------------------------------------------------------
    # PUBLIC ENTRYPOINTS — called by controllers
    # -------------------------------------------------------------------------
    def action_mark_opened(self):
        """Mark as opened (first open only)."""
        for rec in self:
            if not rec.opened_at:
                rec.opened_at = fields.Datetime.now()
            if rec.state in ("sent", "queued", "draft"):
                rec.state = "opened"
            rec.message_post(body=_("Feedback link opened by recipient."))

    def action_submit_feedback(self, rating_value=None, comment=None, would_recommend=None):
        """Persist submitted feedback and mark as submitted."""
        for rec in self:
            if rec.is_expired or rec.state in ("expired", "revoked"):
                raise UserError(_("This feedback link is expired or revoked."))
            if rec.state == "submitted":
                # Idempotent updates allowed (overwrite if provided)
                pass

            # Apply values
            write_vals = {}
            if rating_value is not None:
                # Normalize to defined choices ('1'..'5' as strings)
                rating_value = str(rating_value)
                if rating_value not in dict(self._fields["rating_value"].selection):
                    raise UserError(_("Invalid rating value."))
                write_vals["rating_value"] = rating_value
            if comment is not None:
                write_vals["comment"] = comment
            if would_recommend is not None:
                would_recommend = str(would_recommend)
                if would_recommend not in dict(self._fields["would_recommend"].selection):
                    raise UserError(_("Invalid recommendation value."))
                write_vals["would_recommend"] = would_recommend

            write_vals["submitted_at"] = fields.Datetime.now()
            write_vals["state"] = "submitted"
            rec.write(write_vals)
            rec.message_post(body=_("Feedback submitted."))

    # -------------------------------------------------------------------------
    # UTILITIES
    # -------------------------------------------------------------------------
    @api.model
    def sudo_find_by_token(self, token):
        """Public-safe lookup by token for use in controllers."""
        if not token:
            return self.browse()
        return self.sudo().search([("token", "=", token)], limit=1)

    def action_open_public(self):
        """Open the public URL in a new tab (staff convenience)."""
        self.ensure_one()
        if not self.access_url:
            self.action_generate_link()
        return {
            "type": "ir.actions.act_url",
            "url": self.access_url,
            "target": "new",
        }

    def action_revoke(self, reason=None):
        """Invalidate the link (cannot be used anymore)."""
        for rec in self:
            rec.state = "revoked"
            if reason:
                rec.message_post(body=_("Feedback link revoked: %s") % reason)
            else:
                rec.message_post(body=_("Feedback link revoked."))

    # -------------------------------------------------------------------------
    # CRON — EXPIRATION
    # -------------------------------------------------------------------------
    @api.model
    def cron_expire_feedback_links(self):
        """Auto-expire links past 'expire_at' that are not yet submitted/revoked."""
        now = fields.Datetime.now()
        domain = [
            ("state", "in", ["draft", "queued", "sent", "opened"]),
            ("expire_at", "!=", False),
            ("expire_at", "<", now),
        ]
        to_expire = self.search(domain)
        for rec in to_expire:
            rec.state = "expired"
            rec.message_post(body=_("Feedback link expired automatically."))

    # -------------------------------------------------------------------------
    # NAME / DISPLAY
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            label = rec.name or _("Feedback")
            if rec.booking_id:
                label = f"{label} - {rec.booking_id.name}"
            res.append((rec.id, label))
        return res

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("expiration_days")
    def _check_expiration_days(self):
        for rec in self:
            if rec.expiration_days is not None and rec.expiration_days < 0:
                raise ValidationError(_("Valid For (days) must be 0 or a positive number."))

    @api.constrains("patient_id")
    def _check_patient_email(self):
        for rec in self:
            # Not hard error: allow creating without email (could be SMS-only in future),
            # but if sending via email we will block there. Keep as soft guard if desired.
            pass


# -----------------------------------------------------------------------------
# OPTIONAL MIXIN — attach feedback to other models if needed
# -----------------------------------------------------------------------------
class BookingFeedbackLinkMixin(models.AbstractModel):
    _name = "booking.feedback.link.mixin"
    _description = "Feedback Link Mixin"

    feedback_link_ids = fields.One2many(
        "booking.feedback.link",
        "booking_id",
        string="Feedback Links",
        help="All feedback invitations associated with this record.",
    )

    def action_new_feedback_link(self):
        """Convenience action to create a feedback link from an inheriting record."""
        self.ensure_one()
        if self._name != "booking.booking":
            raise UserError(_("This helper is intended to be used from Booking."))
        vals = {
            "booking_id": self.id,
            "channel_id": self.channel_id.id if hasattr(self, "channel_id") and self.channel_id else False,
            "policy_id": self.policy_id.id if hasattr(self, "policy_id") and self.policy_id else False,
        }
        link = self.env["booking.feedback.link"].create(vals)
        return {
            "type": "ir.actions.act_window",
            "res_model": "booking.feedback.link",
            "view_mode": "form",
            "res_id": link.id,
            "target": "current",
        }

# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/booking_line.py
#
# Purpose
# -------
# Line items for a Booking:
# - Products/services/consumables tied to a booking
# - Tax/amount computations (subtotal, tax, total) similar to sale.order.line
# - Optional linkage to treatments and resources
#
# Integrations (soft-coupled)
# ---------------------------
# - booking.booking (reverse O2M: line_ids)
# - product.product / uom.uom / account.tax
# - clinic.treatment (reference)
# - booking.resource (optional line-level resources, in addition to booking-level)
# - account.move creation is done by booking via _prepare_invoice_line_from_booking_line()
#
# All user-facing strings are in English.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class BookingLine(models.Model):
    _name = "booking.line"
    _description = "Booking Line"
    _order = "sequence, id"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # ---------------------------------------------------------------------
    # RELATIONS / CONTEXT
    # ---------------------------------------------------------------------
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking",
        required=True,
        ondelete="cascade",
        index=True,
        help="Parent booking document.",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="booking_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="booking_id.currency_id",
        store=True,
        readonly=True,
    )
    state = fields.Selection(
        related="booking_id.state",
        string="Booking Status",
        store=True,
        readonly=True,
    )
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="booking_id.patient_id",
        store=True,
        readonly=True,
    )

    # ---------------------------------------------------------------------
    # DISPLAY / CLASSIFICATION
    # ---------------------------------------------------------------------
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Lower values appear first.",
    )

    display_type = fields.Selection(
        selection=[("line_section", "Section"), ("line_note", "Note")],
        string="Display Type",
        help="Technical field for UX sections/notes. Non-commercial line (no amount).",
    )
    is_display_type = fields.Boolean(
        string="Is Display Type",
        compute="_compute_is_display_type",
        help="Technical helper to flag section/note lines.",
        store=True,
    )

    tag_ids = fields.Many2many(
        "ir.tags",
        "booking_line_tag_rel",
        "line_id",
        "tag_id",
        string="Tags",
        help="Optional tags for search and reporting.",
    )

    # ---------------------------------------------------------------------
    # PRODUCT / TREATMENT / RESOURCES
    # ---------------------------------------------------------------------
    name = fields.Text(
        string="Description",
        required=False,
        help="Line description shown on documents.",
        tracking=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        domain=[("sale_ok", "=", True)],
        help="Product/service for this booking line.",
        tracking=True,
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        help="Optional treatment reference for this line.",
    )
    resource_ids = fields.Many2many(
        "booking.resource",
        "booking_line_resource_rel",
        "line_id",
        "resource_id",
        string="Resources",
        help="Resources used for this specific line (optional, complements booking-level resources).",
    )

    # UoM / Quantity / Pricing
    product_uom = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        help="Unit of Measure for the product.",
    )
    product_uom_qty = fields.Float(
        string="Quantity",
        default=1.0,
        help="Ordered quantity for this line.",
    )
    price_unit = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
        help="Unit price before discount and taxes.",
    )
    discount = fields.Float(
        string="Discount (%)",
        help="Discount percentage to apply on the unit price.",
        default=0.0,
    )
    tax_ids = fields.Many2many(
        "account.tax",
        "booking_line_tax_rel",
        "line_id",
        "tax_id",
        string="Taxes",
        help="Customer taxes applied to this line.",
    )

    # Amounts (computed)
    price_subtotal = fields.Monetary(
        string="Subtotal",
        currency_field="currency_id",
        compute="_compute_amount",
        store=True,
        help="Subtotal without taxes.",
    )
    price_tax = fields.Monetary(
        string="Tax",
        currency_field="currency_id",
        compute="_compute_amount",
        store=True,
        help="Tax amount for this line.",
    )
    price_total = fields.Monetary(
        string="Total",
        currency_field="currency_id",
        compute="_compute_amount",
        store=True,
        help="Total including taxes.",
    )

    # Accounting helpers (for future extensions)
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Analytic Account",
        help="Optional analytic account for this line.",
    )
    # Odoo 19 CE: account.analytic.tag no longer exists.
    # Keep the historical field intent documented, but do not register an
    # invalid comodel even in this preserved dormant aggregate source.
    # analytic_tag_ids = fields.Many2many(
    #     "account.analytic.tag",
    #     string="Analytic Tags",
    #     help="Optional analytic tags for this line.",
    # )

    # ---------------------------------------------------------------------
    # COMPUTES
    # ---------------------------------------------------------------------
    @api.depends("display_type")
    def _compute_is_display_type(self):
        for rec in self:
            rec.is_display_type = bool(rec.display_type)

    @api.depends(
        "product_uom_qty",
        "discount",
        "price_unit",
        "tax_ids",
        "currency_id",
        "product_id",
        "booking_id.patient_id",
    )
    def _compute_amount(self):
        """
        Compute price_subtotal, price_tax, price_total using account.tax.compute_all,
        similar to sale.order.line logic.
        """
        for rec in self:
            if rec.is_display_type:
                rec.price_subtotal = 0.0
                rec.price_tax = 0.0
                rec.price_total = 0.0
                continue

            qty = rec.product_uom_qty or 0.0
            unit = rec.price_unit or 0.0
            disc = rec.discount or 0.0

            # Apply percentage discount
            effective_unit = unit * (1.0 - (disc / 100.0))

            taxes = rec.tax_ids
            currency = rec.currency_id or (rec.booking_id and rec.booking_id.currency_id)
            partner = rec.booking_id and rec.booking_id.patient_id or False

            if taxes:
                tax_res = taxes._origin.compute_all(
                    effective_unit,
                    currency=currency,
                    quantity=qty,
                    product=rec.product_id,
                    partner=partner,
                )
                rec.price_subtotal = tax_res["total_excluded"]
                rec.price_total = tax_res["total_included"]
                rec.price_tax = rec.price_total - rec.price_subtotal
            else:
                rec.price_subtotal = effective_unit * qty
                rec.price_total = rec.price_subtotal
                rec.price_tax = 0.0

    # ---------------------------------------------------------------------
    # ONCHANGE
    # ---------------------------------------------------------------------
    @api.onchange("product_id")
    def _onchange_product_id(self):
        """
        Prefill UoM, taxes, description, and unit price from the selected product.
        We keep it simple: use product's sales description, list price, and customer taxes.
        """
        for rec in self:
            if not rec.product_id:
                continue

            product = rec.product_id.with_context(lang=self.env.user.lang or "en_US")
            # Description
            name = product.display_name or ""
            if product.description_sale:
                name += "\n" + product.description_sale
            rec.name = name

            # UoM
            rec.product_uom = product.uom_id

            # Taxes (customer taxes)
            company = rec.company_id or self.env.company
            if company and product.taxes_id:
                rec.tax_ids = product.taxes_id.filtered(lambda t: t.company_id == company)
            else:
                rec.tax_ids = [(5, 0, 0)]

            # Price Unit (basic strategy: list price; pricing engine can override externally)
            rec.price_unit = product.lst_price or 0.0

            # If treatment default exists, try to suggest
            if not rec.treatment_id and hasattr(product, "treatment_id") and product.treatment_id:
                rec.treatment_id = product.treatment_id.id

    @api.onchange("product_uom", "product_uom_qty")
    def _onchange_qty_uom(self):
        """
        Basic guardrails; more complex UoM pricelist logic is intentionally left out
        to keep module lightweight (sale module handles it in its own domain).
        """
        for rec in self:
            if rec.product_uom_qty is not None and rec.product_uom_qty < 0:
                return {
                    "warning": {
                        "title": _("Quantity Warning"),
                        "message": _("Quantity should not be negative."),
                    }
                }
        return {}

    # ---------------------------------------------------------------------
    # CONSTRAINTS
    # ---------------------------------------------------------------------
    @api.constrains("product_uom_qty", "price_unit", "discount")
    def _check_numbers(self):
        for rec in self:
            if rec.is_display_type:
                continue
            if rec.product_uom_qty is None or rec.product_uom_qty <= 0.0:
                raise ValidationError(_("Quantity must be greater than 0."))
            if rec.price_unit is None or rec.price_unit < 0.0:
                raise ValidationError(_("Unit Price cannot be negative."))
            if rec.discount is not None and (rec.discount < 0.0 or rec.discount > 100.0):
                raise ValidationError(_("Discount must be between 0 and 100."))

    @api.constrains("product_id", "name")
    def _check_content_presence(self):
        """
        Require at least a product or a non-empty description for commercial lines.
        """
        for rec in self:
            if rec.is_display_type:
                continue
            if not rec.product_id and not rec.name:
                raise ValidationError(_("Please set a Product or a Description for the line."))

    # ---------------------------------------------------------------------
    # HELPERS — INVOICING & STOCK
    # ---------------------------------------------------------------------
    def prepare_invoice_line_vals(self):
        """
        Optional helper if callers want to use line's own mapping.
        The booking currently calls its own mapper; this mirrors that structure.
        """
        self.ensure_one()
        taxes = self.tax_ids
        return {
            "name": self.name or (self.product_id and self.product_id.display_name) or _("Booking Line"),
            "product_id": self.product_id.id if self.product_id else False,
            "quantity": self.product_uom_qty or 1.0,
            "price_unit": self.price_unit or 0.0,
            "discount": self.discount or 0.0,
            "tax_ids": [(6, 0, taxes.ids)] if taxes else False,
            "currency_id": self.currency_id.id,
            "analytic_account_id": self.analytic_account_id.id if self.analytic_account_id else False,
            "analytic_tag_ids": [(6, 0, self.analytic_tag_ids.ids)] if self.analytic_tag_ids else False,
        }

    def prepare_resource_consumption(self):
        """
        Prepare stock moves for resource consumption at line level (optional).
        This delegates to each resource's prepare_stock_moves().
        """
        moves = []
        for rec in self:
            if not rec.resource_ids:
                continue
            for resource in rec.resource_ids:
                qty = None
                # If the product equals the resource.product, you might derive qty from line qty
                if resource.track_consumption and resource.product_id and rec.product_id == resource.product_id:
                    qty = rec.product_uom_qty
                mv_vals = resource.prepare_stock_moves(booking=rec.booking_id, qty=qty)
                moves += mv_vals
        return moves

    # ---------------------------------------------------------------------
    # ACTIONS
    # ---------------------------------------------------------------------
    def action_view_booking(self):
        self.ensure_one()
        action = {
            "name": _("Booking"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "form",
            "res_id": self.booking_id.id,
        }
        return action

    # ---------------------------------------------------------------------
    # COPY / DEFAULTS
    # ---------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # If created from booking form, booking_id is in context
        if not res.get("booking_id"):
            ctx_booking = self.env.context.get("default_booking_id")
            if ctx_booking:
                res["booking_id"] = ctx_booking
        return res

    def copy_data(self, default=None):
        """
        Keep a sensible copy, reset amounts (recompute), keep the same product/taxes.
        """
        self.ensure_one()
        default = dict(default or {})
        default.setdefault("price_subtotal", 0.0)
        default.setdefault("price_tax", 0.0)
        default.setdefault("price_total", 0.0)
        return super().copy_data(default)

# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/booking_policy.py
#
# Purpose:
# - Define booking policies used to govern cancellation/reschedule windows,
#   deposits, no-show penalties, and refund behaviors.
# - Provide generic helper APIs that other modules (booking, channel, portal)
#   can call to check permissions and compute fees/deposits.
#
# Integrations (soft-coupled):
# - booking.booking (policy_id on booking)
# - booking.channel (default policy on channel)
# - account/accounting (fees/deposits will be turned into invoice lines by the caller)
# - mail (chatter tracking)
#
# Notes:
# - Keep dependencies minimal and avoid hard-coding XML IDs.
# - All user-facing strings are in English.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta


class BookingPolicy(models.Model):
    _name = "booking.policy"
    _description = "Booking Policy"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"

    # -------------------------------------------------------------------------
    # BASIC / IDENTITY
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Policy Name",
        required=True,
        tracking=True,
        help="Human-friendly name of the policy, e.g., 'Default Online Policy'.",
    )
    code = fields.Char(
        string="Technical Code",
        required=True,
        index=True,
        tracking=True,
        help="Unique, URL-safe technical code. Example: 'online_default', 'walkin_default'.",
    )
    description = fields.Text(
        string="Description",
        help="Optional description or internal notes about this policy.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Disable to stop future usage while preserving historical references.",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Lower values appear first in selection lists.",
    )
    color = fields.Integer(
        string="Color Index",
        help="Optional color used in Kanban indicators.",
    )

    # -------------------------------------------------------------------------
    # COMPANY / CURRENCY CONTEXT
    # -------------------------------------------------------------------------
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
        help="Company to which this policy belongs.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # EFFECTIVITY WINDOW
    # -------------------------------------------------------------------------
    date_start = fields.Date(
        string="Effective From",
        help="Optional start date when the policy becomes effective.",
    )
    date_end = fields.Date(
        string="Effective Until",
        help="Optional end date after which the policy no longer applies.",
    )

    # -------------------------------------------------------------------------
    # CANCELLATION RULES
    # -------------------------------------------------------------------------
    allow_cancel = fields.Boolean(
        string="Allow Cancellation",
        default=True,
        help="Allow customers/staff to cancel a booking under this policy.",
    )
    cancel_cutoff_unit = fields.Selection(
        selection=[("hours", "Hours"), ("days", "Days")],
        string="Cancellation Cutoff Unit",
        default="hours",
        help="Measure unit for the cancellation cutoff window.",
    )
    cancel_cutoff_value = fields.Float(
        string="Cancellation Cutoff Value",
        default=24.0,
        help=(
            "Minimum time before the booking start when cancellation is still allowed "
            "(e.g., 24 hours). If 0, cancellation is allowed until start time."
        ),
    )
    cancel_fee_type = fields.Selection(
        selection=[("none", "None"), ("fixed", "Fixed Amount"), ("percent", "Percentage")],
        string="Cancellation Fee Type",
        default="none",
        help="Fee type applied when cancelling within allowed window (or per exception rules).",
    )
    cancel_fee_fixed = fields.Monetary(
        string="Cancellation Fee (Fixed)",
        currency_field="currency_id",
        help="Fixed cancellation fee. Used when fee type is 'Fixed Amount'.",
    )
    cancel_fee_percent = fields.Float(
        string="Cancellation Fee (%)",
        help="Percentage of booking total as cancellation fee. Used when fee type is 'Percentage'.",
    )

    # -------------------------------------------------------------------------
    # RESCHEDULE RULES
    # -------------------------------------------------------------------------
    allow_reschedule = fields.Boolean(
        string="Allow Reschedule",
        default=True,
        help="Allow moving a booking to a different date/time under this policy.",
    )
    reschedule_cutoff_unit = fields.Selection(
        selection=[("hours", "Hours"), ("days", "Days")],
        string="Reschedule Cutoff Unit",
        default="hours",
        help="Measure unit for the reschedule cutoff window.",
    )
    reschedule_cutoff_value = fields.Float(
        string="Reschedule Cutoff Value",
        default=12.0,
        help=(
            "Minimum time before the booking start when rescheduling is still allowed. "
            "If 0, rescheduling is allowed until start time."
        ),
    )
    reschedule_limit = fields.Integer(
        string="Max Reschedules",
        default=0,
        help="Maximum number of reschedules allowed (0 = unlimited).",
    )
    reschedule_fee_type = fields.Selection(
        selection=[("none", "None"), ("fixed", "Fixed Amount"), ("percent", "Percentage")],
        string="Reschedule Fee Type",
        default="none",
        help="Fee type applied when rescheduling within allowed window.",
    )
    reschedule_fee_fixed = fields.Monetary(
        string="Reschedule Fee (Fixed)",
        currency_field="currency_id",
        help="Fixed reschedule fee. Used when fee type is 'Fixed Amount'.",
    )
    reschedule_fee_percent = fields.Float(
        string="Reschedule Fee (%)",
        help="Percentage of booking total as reschedule fee. Used when fee type is 'Percentage'.",
    )

    # -------------------------------------------------------------------------
    # NO-SHOW RULES
    # -------------------------------------------------------------------------
    no_show_fee_type = fields.Selection(
        selection=[("none", "None"), ("fixed", "Fixed Amount"), ("percent", "Percentage")],
        string="No-show Fee Type",
        default="fixed",
        help="Fee type applied when the patient does not show up (no check-in).",
    )
    no_show_fee_fixed = fields.Monetary(
        string="No-show Fee (Fixed)",
        currency_field="currency_id",
        default=0.0,
        help="Fixed no-show fee. Used when fee type is 'Fixed Amount'.",
    )
    no_show_fee_percent = fields.Float(
        string="No-show Fee (%)",
        help="Percentage of booking total as no-show fee. Used when fee type is 'Percentage'.",
    )
    no_show_grace_minutes = fields.Integer(
        string="No-show Grace (minutes)",
        default=15,
        help="Minutes after start time before the booking is considered a no-show.",
    )

    # -------------------------------------------------------------------------
    # DEPOSIT RULES
    # -------------------------------------------------------------------------
    allow_prepaid_deposit = fields.Boolean(
        string="Allow Prepaid Deposit",
        help="Enable deposit for bookings under this policy.",
    )
    deposit_is_required = fields.Boolean(
        string="Deposit Required",
        help="If enabled, a deposit must be collected under this policy.",
    )
    deposit_fixed_amount = fields.Monetary(
        string="Deposit Fixed Amount",
        currency_field="currency_id",
        help="Fixed deposit amount to request. Leave 0 if using percentage.",
    )
    deposit_percent = fields.Float(
        string="Deposit Percentage",
        help="Deposit percentage (0 - 100). Leave 0 if using fixed amount.",
    )
    deposit_due_timing = fields.Selection(
        selection=[("on_booking", "On Booking"), ("before_start", "Before Start"), ("on_checkin", "On Check-in")],
        string="Deposit Due Timing",
        default="on_booking",
        help="When the deposit must be collected.",
    )
    deposit_before_start_hours = fields.Float(
        string="Hours Before Start (Deposit)",
        default=0.0,
        help="If 'Before Start' is used, how many hours prior to start deposit must be paid.",
    )
    deposit_refund_policy = fields.Selection(
        selection=[
            ("refundable", "Refundable"),
            ("non_refundable", "Non-refundable"),
            ("conditional", "Conditional"),
        ],
        string="Deposit Refund Policy",
        default="conditional",
        help="Refund policy for collected deposits.",
    )

    # -------------------------------------------------------------------------
    # REFUND RULES
    # -------------------------------------------------------------------------
    refund_method = fields.Selection(
        selection=[("original", "Original Payment"), ("wallet", "Wallet/Credit"), ("manual", "Manual Refund")],
        string="Preferred Refund Method",
        default="original",
        help="Preferred method for refunding fees or deposits. Implemented by the caller.",
    )
    refund_delay_days = fields.Integer(
        string="Refund Delay (days)",
        default=0,
        help="Informational delay before refund is processed.",
    )

    # -------------------------------------------------------------------------
    # LINKS / STATS
    # -------------------------------------------------------------------------
    channel_ids = fields.Many2many(
        "booking.channel",
        "booking_policy_channel_rel",
        "policy_id",
        "channel_id",
        string="Channels",
        help="Default channels associated to this policy.",
    )
    bookings_count = fields.Integer(
        string="Bookings",
        compute="_compute_bookings_count",
        help="Number of active bookings using this policy.",
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    _code_company_unique = models.Constraint(
        'unique(code, company_id)',
        'Policy Technical Code must be unique per company.',
    )

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Policy Name must be unique per company.',
    )

    @api.constrains("date_start", "date_end")
    def _check_date_range(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_("Effective Until date cannot be earlier than Effective From date."))

    @api.constrains("cancel_fee_percent", "reschedule_fee_percent", "no_show_fee_percent", "deposit_percent")
    def _check_percentages(self):
        for rec in self:
            for field_name in ("cancel_fee_percent", "reschedule_fee_percent", "no_show_fee_percent", "deposit_percent"):
                val = getattr(rec, field_name)
                if val and (val < 0.0 or val > 100.0):
                    raise ValidationError(_("Percent values must be between 0 and 100."))

    @api.constrains("allow_prepaid_deposit", "deposit_is_required", "deposit_fixed_amount", "deposit_percent")
    def _check_deposit_config(self):
        for rec in self:
            if rec.allow_prepaid_deposit and rec.deposit_is_required:
                if not (rec.deposit_fixed_amount or rec.deposit_percent):
                    raise ValidationError(
                        _("When 'Deposit Required' is enabled, either a Fixed Amount or a Percentage must be set.")
                    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _domain_bookings(self):
        return [("policy_id", "=", self.id), ("active", "=", True)]

    def _compute_bookings_count(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            rec.bookings_count = Booking.search_count(rec._domain_bookings())

    # -------------------------------------------------------------------------
    # UTILS
    # -------------------------------------------------------------------------
    def _get_now(self):
        """Wrapper to ease testing/mocking."""
        return fields.Datetime.now()

    def _hours_to_start(self, booking, at_dt=None):
        """Return hours from 'at_dt' to booking start (can be negative)."""
        if not booking or not booking.start_datetime:
            return None
        at = fields.Datetime.from_string(at_dt) if at_dt else self._get_now()
        start = fields.Datetime.from_string(booking.start_datetime)
        delta = start - at
        return delta.total_seconds() / 3600.0

    def _unit_to_hours(self, unit, value):
        value = value or 0.0
        if unit == "days":
            return value * 24.0
        return value

    def _compute_fee(self, fee_type, fixed, percent, base_amount):
        """Compute fee value based on fee type/values and a base amount."""
        base = base_amount or 0.0
        if fee_type == "fixed":
            return fixed or 0.0
        if fee_type == "percent":
            return ((percent or 0.0) / 100.0) * base
        return 0.0

    def _is_within_effective_dates(self, at_dt=None):
        at = fields.Datetime.from_string(at_dt) if at_dt else self._get_now()
        at_date = at.date()
        for rec in self:
            if rec.date_start and at_date < rec.date_start:
                return False
            if rec.date_end and at_date > rec.date_end:
                return False
        return True

    # -------------------------------------------------------------------------
    # PUBLIC API — DECISION HELPERS
    # -------------------------------------------------------------------------
    def can_cancel(self, booking, at_dt=None, channel=None):
        """
        Check whether cancellation is allowed and compute the fee.
        Returns a dict:
            {
                'allowed': bool,
                'reason': str,         # human-readable
                'fee': float,          # numeric amount (in company currency)
                'currency_id': id,
                'policy_id': id,
            }
        """
        self.ensure_one()
        if not self.allow_cancel:
            return {
                "allowed": False,
                "reason": _("Cancellation is disabled by this policy."),
                "fee": 0.0,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
            }
        if not self._is_within_effective_dates(at_dt=at_dt):
            return {
                "allowed": True,
                "reason": _("Policy date range not applicable; fallback allows cancellation."),
                "fee": 0.0,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
            }

        # Apply exception rule if any, otherwise use policy-level cutoff/fee
        ex = self._match_exception(action_type="cancel", channel=channel, at_dt=at_dt)
        cutoff_hours = None
        fee_type = None
        fee_fixed = 0.0
        fee_percent = 0.0

        if ex:
            cutoff_hours = self._unit_to_hours(ex.cutoff_unit, ex.cutoff_value)
            fee_type = ex.fee_type or "none"
            fee_fixed = ex.fee_fixed or 0.0
            fee_percent = ex.fee_percent or 0.0
        else:
            cutoff_hours = self._unit_to_hours(self.cancel_cutoff_unit, self.cancel_cutoff_value)
            fee_type = self.cancel_fee_type or "none"
            fee_fixed = self.cancel_fee_fixed or 0.0
            fee_percent = self.cancel_fee_percent or 0.0

        hours_to_start = self._hours_to_start(booking, at_dt=at_dt)
        if hours_to_start is None:
            return {
                "allowed": False,
                "reason": _("Booking has no start time."),
                "fee": 0.0,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
            }

        if cutoff_hours and hours_to_start < cutoff_hours:
            # Still allowed (policy says allow_cancel=True) but within cutoff → fee applies
            fee = self._compute_fee(fee_type, fee_fixed, fee_percent, booking.amount_total)
            return {
                "allowed": True,
                "reason": _("Cancellation is within cutoff window; a fee may apply."),
                "fee": fee,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
            }
        return {
            "allowed": True,
            "reason": _("Cancellation is allowed without fee."),
            "fee": 0.0,
            "currency_id": self.currency_id.id,
            "policy_id": self.id,
        }

    def can_reschedule(self, booking, at_dt=None, channel=None, current_reschedules_count=0):
        """
        Check whether reschedule is allowed and compute the fee.
        Returns a dict like can_cancel().
        """
        self.ensure_one()
        if not self.allow_reschedule:
            return {
                "allowed": False,
                "reason": _("Rescheduling is disabled by this policy."),
                "fee": 0.0,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
            }
        if self.reschedule_limit and current_reschedules_count >= self.reschedule_limit:
            return {
                "allowed": False,
                "reason": _("Maximum number of reschedules reached."),
                "fee": 0.0,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
            }
        if not self._is_within_effective_dates(at_dt=at_dt):
            return {
                "allowed": True,
                "reason": _("Policy date range not applicable; fallback allows rescheduling."),
                "fee": 0.0,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
            }

        ex = self._match_exception(action_type="reschedule", channel=channel, at_dt=at_dt)
        cutoff_hours = None
        fee_type = None
        fee_fixed = 0.0
        fee_percent = 0.0

        if ex:
            cutoff_hours = self._unit_to_hours(ex.cutoff_unit, ex.cutoff_value)
            fee_type = ex.fee_type or "none"
            fee_fixed = ex.fee_fixed or 0.0
            fee_percent = ex.fee_percent or 0.0
        else:
            cutoff_hours = self._unit_to_hours(self.reschedule_cutoff_unit, self.reschedule_cutoff_value)
            fee_type = self.reschedule_fee_type or "none"
            fee_fixed = self.reschedule_fee_fixed or 0.0
            fee_percent = self.reschedule_fee_percent or 0.0

        hours_to_start = self._hours_to_start(booking, at_dt=at_dt)
        if hours_to_start is None:
            return {
                "allowed": False,
                "reason": _("Booking has no start time."),
                "fee": 0.0,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
            }

        if cutoff_hours and hours_to_start < cutoff_hours:
            fee = self._compute_fee(fee_type, fee_fixed, fee_percent, booking.amount_total)
            return {
                "allowed": True,
                "reason": _("Rescheduling is within cutoff window; a fee may apply."),
                "fee": fee,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
            }
        return {
            "allowed": True,
            "reason": _("Rescheduling is allowed without fee."),
            "fee": 0.0,
            "currency_id": self.currency_id.id,
            "policy_id": self.id,
        }

    def compute_deposit(self, booking):
        """
        Compute deposit amount for the given booking.
        Returns a dict:
            {'required': bool, 'amount': float, 'currency_id': id, 'policy_id': id, 'refund_policy': 'refundable'|'non_refundable'|'conditional'}
        """
        self.ensure_one()
        if not self.allow_prepaid_deposit:
            return {
                "required": False,
                "amount": 0.0,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
                "refund_policy": self.deposit_refund_policy,
            }
        if self.deposit_is_required and not (self.deposit_fixed_amount or self.deposit_percent):
            # Guard rail; should be prevented by constrains
            raise UserError(_("Deposit is required but no amount/percentage is configured on the policy."))

        amount = 0.0
        base = getattr(booking, "amount_total", 0.0) or 0.0
        if self.deposit_percent:
            amount = (self.deposit_percent / 100.0) * base
        elif self.deposit_fixed_amount:
            amount = self.deposit_fixed_amount

        return {
            "required": bool(self.deposit_is_required),
            "amount": amount or 0.0,
            "currency_id": self.currency_id.id,
            "policy_id": self.id,
            "refund_policy": self.deposit_refund_policy,
        }

    def can_mark_no_show(self, booking, at_dt=None):
        """
        Determine whether a booking can be marked as 'no-show' according to grace time.
        Returns a dict similar to can_cancel()/can_reschedule().
        """
        self.ensure_one()
        if not booking or not booking.start_datetime:
            return {
                "allowed": False,
                "reason": _("Booking has no start time."),
                "fee": 0.0,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
            }
        now = fields.Datetime.from_string(at_dt) if at_dt else self._get_now()
        start = fields.Datetime.from_string(booking.start_datetime)
        grace = timedelta(minutes=self.no_show_grace_minutes or 0)
        if now < (start + grace):
            return {
                "allowed": False,
                "reason": _("No-show cannot be marked before grace time elapses."),
                "fee": 0.0,
                "currency_id": self.currency_id.id,
                "policy_id": self.id,
            }

        fee = self._compute_fee(self.no_show_fee_type, self.no_show_fee_fixed, self.no_show_fee_percent, booking.amount_total)
        return {
            "allowed": True,
            "reason": _("No-show can be marked; a fee may apply."),
            "fee": fee,
            "currency_id": self.currency_id.id,
            "policy_id": self.id,
        }

    # -------------------------------------------------------------------------
    # EXCEPTIONS (PER CHANNEL / DATE RANGE)
    # -------------------------------------------------------------------------
    exception_ids = fields.One2many(
        "booking.policy.exception",
        "policy_id",
        string="Exceptions",
        help="Optional per-channel/date exceptions overriding default cutoff/fees.",
    )

    def _match_exception(self, action_type, channel=None, at_dt=None):
        """
        Return the first matching exception for the given action/channel/date.
        Priority: exact channel match in current date, then generic (no channel) in current date.
        """
        self.ensure_one()
        at = fields.Datetime.from_string(at_dt) if at_dt else self._get_now()
        at_date = at.date()
        candidates = self.exception_ids.filtered(lambda e: e.action_type == action_type and
                                                          (not e.date_start or at_date >= e.date_start) and
                                                          (not e.date_end or at_date <= e.date_end))
        # Prefer exact channel match
        if channel:
            channel_matches = candidates.filtered(lambda e: e.channel_id and e.channel_id.id == channel.id)
            if channel_matches:
                return channel_matches.sorted(lambda e: (e.sequence, e.id))[0]
        # Fallback to generic exception (no channel)
        generic = candidates.filtered(lambda e: not e.channel_id)
        if generic:
            return generic.sorted(lambda e: (e.sequence, e.id))[0]
        return None

    # -------------------------------------------------------------------------
    # ACTIONS / VIEWS
    # -------------------------------------------------------------------------
    def action_view_bookings(self):
        """Open bookings filtered by this policy."""
        self.ensure_one()
        action = {
            "name": _("Bookings"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "list,form,calendar,kanban,pivot,graph,activity",
            "domain": [("policy_id", "=", self.id)],
            "context": {"default_policy_id": self.id},
        }
        try:
            action_def = self.env.ref("clinic_booking.action_booking_list", raise_if_not_found=False)
            if action_def:
                action = action_def.read()[0]
                action.update({"domain": [("policy_id", "=", self.id)]})
                ctx = action.get("context", {}) or {}
                ctx.update({"default_policy_id": self.id})
                action["context"] = ctx
        except Exception:
            pass
        return action

    # -------------------------------------------------------------------------
    # NAME / DISPLAY
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            label = rec.name
            if rec.company_id and self.env.companies and len(self.env.companies) > 1:
                label = f"{label} - {rec.company_id.name}"
            res.append((rec.id, label))
        return res


class BookingPolicyException(models.Model):
    _name = "booking.policy.exception"
    _description = "Booking Policy Exception"
    _order = "sequence, id"

    # Link back to policy
    policy_id = fields.Many2one(
        "booking.policy",
        string="Policy",
        required=True,
        ondelete="cascade",
        index=True,
        help="Policy to which this exception belongs.",
    )

    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Lower values are applied first.",
    )

    # Scope
    channel_id = fields.Many2one(
        "booking.channel",
        string="Channel",
        help="Optional channel where this exception applies. Leave empty for generic exception.",
    )
    date_start = fields.Date(
        string="Effective From",
        help="Optional start date for this exception.",
    )
    date_end = fields.Date(
        string="Effective Until",
        help="Optional end date for this exception.",
    )

    # Action-specific settings
    action_type = fields.Selection(
        selection=[("cancel", "Cancel"), ("reschedule", "Reschedule")],
        string="Action",
        required=True,
        help="Which action this exception targets.",
    )
    cutoff_unit = fields.Selection(
        selection=[("hours", "Hours"), ("days", "Days")],
        string="Cutoff Unit",
        default="hours",
        help="Unit for the cutoff window.",
    )
    cutoff_value = fields.Float(
        string="Cutoff Value",
        default=0.0,
        help="Minimum time before the booking start when action is still allowed under this exception.",
    )
    fee_type = fields.Selection(
        selection=[("none", "None"), ("fixed", "Fixed Amount"), ("percent", "Percentage")],
        string="Fee Type",
        default="none",
        help="Fee type applied when action occurs within the cutoff window.",
    )
    fee_fixed = fields.Monetary(
        string="Fee (Fixed)",
        currency_field="currency_id",
        help="Fixed fee applied by this exception.",
    )
    fee_percent = fields.Float(
        string="Fee (%)",
        help="Percentage fee applied by this exception.",
    )

    # Currency / Company context (copied from policy for convenience)
    company_id = fields.Many2one(
        "res.company",
        related="policy_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="policy_id.currency_id",
        store=True,
        readonly=True,
    )

    @api.constrains("fee_percent")
    def _check_percent(self):
        for rec in self:
            if rec.fee_percent and (rec.fee_percent < 0.0 or rec.fee_percent > 100.0):
                raise ValidationError(_("Percent values must be between 0 and 100."))

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_("Effective Until date cannot be earlier than Effective From date."))


class BookingPolicyMixin(models.AbstractModel):
    """
    Abstract mixin to attach a policy reference and helper calls on other models
    (e.g., booking.booking). This keeps import/coupling low while enabling
    reuse of decision helpers.
    """
    _name = "booking.policy.mixin"
    _description = "Booking Policy Mixin"

    policy_id = fields.Many2one(
        "booking.policy",
        string="Policy",
        index=True,
        help="Policy applied to this record. Controls cancellation, reschedule, and deposit rules.",
    )

    @api.onchange("policy_id")
    def _onchange_policy_id(self):
        # Hook left intentionally light; inheriting models may override
        # to prefill deposit flags/values or to refresh computed fields.
        return

# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/booking_recurring_rule.py
#
# Purpose
# -------
# Provide a reusable, lightweight recurrence engine (RRULE-lite) to define
# repeatable availability windows (dates or datetimes) for Slots, Templates,
# or other booking constructs.
#
# Scope
# -----
# FREQ: Daily / Weekly / Monthly  (+ interval)
# WEEKLY: by weekday(s)
# MONTHLY: by monthday(s) and/or by weekday(s) with setpos (e.g., 1st Monday, last Friday)
# LIMITS: until date and/or count
# EXDATE: explicit exclusion dates
#
# Integration (soft-coupled)
# --------------------------
# - booking.slot.recurring_rule_id (M2O to this rule)
# - Any model can reuse the mixin/iterators to build occurrences
#
# Notes
# -----
# - All user-facing strings are in English.
# - No external libraries; pure Python + Odoo fields/methods.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import date as dt_date, datetime, timedelta
import calendar


# -----------------------------------------------------------------------------
# booking.recurring.rule
# -----------------------------------------------------------------------------
class BookingRecurringRule(models.Model):
    _name = "booking.recurring.rule"
    _description = "Booking Recurring Rule"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"

    # Identity
    name = fields.Char(
        string="Rule Name",
        required=True,
        tracking=True,
        help="Human-friendly name of this recurring rule.",
    )
    code = fields.Char(
        string="Technical Code",
        required=True,
        index=True,
        tracking=True,
        help="Unique, URL-safe technical code for this rule.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Disable to stop usage while keeping historical references.",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Lower values sort earlier in lists.",
    )

    # Company context
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # Frequency & interval
    freq = fields.Selection(
        selection=[("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly")],
        string="Frequency",
        required=True,
        default="weekly",
        help="Overall recurrence frequency.",
    )
    interval = fields.Integer(
        string="Interval",
        default=1,
        help="Repeat every N days/weeks/months depending on the frequency.",
    )

    # Effective date range
    date_start = fields.Date(
        string="Effective From",
        required=True,
        default=lambda self: fields.Date.context_today(self),
        help="The first day this rule can produce occurrences.",
    )
    date_end = fields.Date(
        string="Effective Until",
        help="Optional last day this rule can produce occurrences.",
    )

    # Limiters
    count = fields.Integer(
        string="Max Occurrences",
        default=0,
        help="If > 0, stop after producing this many occurrences.",
    )

    # Time window (optional, for models that want start/end datetime directly)
    hour_from = fields.Float(
        string="From (hour)",
        default=9.0,
        help="Optional start time for each occurrence (0.0 - 24.0).",
    )
    hour_to = fields.Float(
        string="To (hour)",
        default=10.0,
        help="Optional end time for each occurrence (0.0 - 24.0). Must be greater than start.",
    )
    duration_minutes = fields.Integer(
        string="Default Duration (min)",
        default=60,
        help="Default duration for a single occurrence. Used when hour_to is not set.",
    )

    # WEEKLY selectors
    weekday_ids = fields.One2many(
        "booking.recurring.weekday",
        "rule_id",
        string="Weekly Weekdays",
        help="For WEEKLY rules: choose one or more weekdays.",
    )

    # MONTHLY selectors
    monthday_ids = fields.One2many(
        "booking.recurring.monthday",
        "rule_id",
        string="Monthly Monthdays",
        help="For MONTHLY rules: one or more month days (1..31).",
    )
    byweekday_ids = fields.One2many(
        "booking.recurring.byweekday",
        "rule_id",
        string="Monthly Weekdays",
        help="For MONTHLY rules: one or more weekdays (e.g., Monday, Friday).",
    )
    bysetpos = fields.Integer(
        string="Set Position (Monthly)",
        default=0,
        help="When using Monthly with weekdays, choose Nth occurrence in the month. "
             "Supported values: -1 (last) or 1..5. 0 means 'all occurrences'.",
    )

    # Exclusions
    exdate_ids = fields.One2many(
        "booking.recurring.exdate",
        "rule_id",
        string="Exception Dates",
        help="Explicit dates to exclude from the recurrence.",
    )

    # Reverse many2one to slots (for convenience navigation)
    slot_ids = fields.One2many(
        "booking.slot",
        "recurring_rule_id",
        string="Linked Slots",
        help="Slots that use this rule for advanced recurrence.",
    )
    slots_count = fields.Integer(
        string="Slots",
        compute="_compute_slots_count",
    )

    # Preview helpers
    next_occurrence_date = fields.Date(
        string="Next Occurrence (Date)",
        compute="_compute_next_occurrence_date",
        help="Next occurrence date on/after today within rule limits.",
    )

    _code_company_unique = models.Constraint(
        'unique(code, company_id)',
        'Rule Technical Code must be unique per company.',
    )

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Rule Name must be unique per company.',
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS & COMPUTES
    # -------------------------------------------------------------------------
    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for rec in self:
            if rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_("Effective Until date cannot be earlier than Effective From date."))

    @api.constrains("interval", "duration_minutes", "hour_from", "hour_to", "bysetpos")
    def _check_numeric(self):
        for rec in self:
            if rec.interval < 1:
                raise ValidationError(_("Interval must be at least 1."))
            if rec.duration_minutes is not None and rec.duration_minutes <= 0:
                raise ValidationError(_("Default Duration must be greater than 0 minutes."))
            if rec.hour_from is not None and (rec.hour_from < 0.0 or rec.hour_from > 24.0):
                raise ValidationError(_("Start hour must be within 0.0 and 24.0."))
            if rec.hour_to is not None and (rec.hour_to < 0.0 or rec.hour_to > 24.0):
                raise ValidationError(_("End hour must be within 0.0 and 24.0."))
            if rec.hour_from is not None and rec.hour_to is not None and rec.hour_to <= rec.hour_from:
                raise ValidationError(_("End hour must be greater than start hour."))
            if rec.bysetpos not in (-1, 0, 1, 2, 3, 4, 5):
                raise ValidationError(_("Set Position must be -1 (last) or 0/1/2/3/4/5."))

    @api.constrains("freq", "weekday_ids", "monthday_ids", "byweekday_ids")
    def _check_selector_requirements(self):
        for rec in self:
            if rec.freq == "weekly" and not rec.weekday_ids:
                raise ValidationError(_("Weekly rules require at least one weekday."))
            if rec.freq == "monthly":
                # Need at least one of monthday or weekday
                if not rec.monthday_ids and not rec.byweekday_ids:
                    raise ValidationError(_("Monthly rules require Monthdays and/or Weekdays."))
                # Monthday must be valid 1..31
                for md in rec.monthday_ids:
                    if md.day < 1 or md.day > 31:
                        raise ValidationError(_("Monthday must be between 1 and 31."))

    def _compute_slots_count(self):
        for rec in self:
            rec.slots_count = len(rec.slot_ids)

    def _compute_next_occurrence_date(self):
        today = fields.Date.context_today(self)
        for rec in self:
            nxt = rec._next_date_on_or_after(today)
            rec.next_occurrence_date = nxt

    # -------------------------------------------------------------------------
    # NAME / DISPLAY
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            label = rec.name
            if rec.company_id and self.env.companies and len(self.env.companies) > 1:
                label = f"{label} - {rec.company_id.name}"
            res.append((rec.id, label))
        return res

    # -------------------------------------------------------------------------
    # PUBLIC API — DATE GENERATION
    # -------------------------------------------------------------------------
    def iter_dates(self, date_from, date_to=None, max_count=None):
        """
        Yield dt_date occurrences within [date_from, date_to] applying:
        - freq/interval
        - weekly/monthly selectors
        - date_start/date_end
        - exdate
        - count limiter

        If date_to is None, generate until date_end or max_count (whichever comes first).
        """
        self.ensure_one()
        if not date_from:
            return
        start = max(date_from, self.date_start or date_from)

        # Guardrails to avoid runaway loops in misconfiguration
        max_count = int(max_count or 0)
        hard_cap = 2000  # safety
        yielded = 0

        cursor = start
        while True:
            # Stop conditions
            if date_to and cursor > date_to:
                break
            if self.date_end and cursor > self.date_end:
                break
            if max_count and yielded >= max_count:
                break
            if yielded >= hard_cap:
                break

            # Test cursor date for match
            if self._matches(cursor) and not self._is_exdate(cursor):
                yield cursor
                yielded += 1

            # Advance cursor based on frequency
            cursor = self._advance(cursor)

    def iter_windows(self, date_from, date_to=None, max_count=None, hour_from=None, hour_to=None, duration_minutes=None):
        """
        Yield (start_dt, end_dt) windows for each occurrence date,
        using the rule's configured time or provided overrides.
        """
        self.ensure_one()
        hour_from = self._sanitize_hour(hour_from, self.hour_from or 9.0)
        hour_to = self._sanitize_hour(hour_to, self.hour_to or None)
        duration_minutes = duration_minutes if duration_minutes is not None else (self.duration_minutes or 60)

        for occ_date in self.iter_dates(date_from=date_from, date_to=date_to, max_count=max_count):
            start_dt = self._combine_date_hour(occ_date, hour_from)
            if hour_to is not None:
                end_dt = self._combine_date_hour(occ_date, hour_to)
            else:
                end_dt = start_dt + timedelta(minutes=max(1, duration_minutes))
            yield (start_dt, end_dt)

    def next_date(self, after_date=None):
        """
        Return the next occurrence date strictly AFTER 'after_date'.
        If after_date is None, use today-1 to get the first date on/after today.
        """
        self.ensure_one()
        if not after_date:
            after_date = (self.date_start or fields.Date.context_today(self)) - timedelta(days=1)
        probe = after_date + timedelta(days=1)
        nxt = self._next_date_on_or_after(probe)
        return nxt

    # -------------------------------------------------------------------------
    # CORE MATCHING / ADVANCE
    # -------------------------------------------------------------------------
    def _matches(self, d: dt_date) -> bool:
        """Return True if date 'd' matches the rule selectors (freq, weekly, monthly)."""
        if d < (self.date_start or d):
            return False
        if self.date_end and d > self.date_end:
            return False

        if self.freq == "daily":
            # date interval aligned to start
            return self._is_daily_match(d)

        if self.freq == "weekly":
            if not self.weekday_ids:
                return False
            return self._is_weekly_match(d)

        if self.freq == "monthly":
            # By monthday and/or weekdays (+ optional bysetpos)
            return self._is_monthly_match(d)

        return False

    def _is_daily_match(self, d: dt_date) -> bool:
        base = self.date_start or d
        delta_days = (d - base).days
        return (delta_days % max(1, self.interval)) == 0 and delta_days >= 0

    def _is_weekly_match(self, d: dt_date) -> bool:
        # interval measured in weeks from the week of date_start (ISO Monday=0..Sunday=6)
        base = self.date_start or d
        # Monday of base week
        base_monday = base - timedelta(days=base.weekday())
        d_monday = d - timedelta(days=d.weekday())
        weeks = (d_monday - base_monday).days // 7
        if weeks < 0 or (weeks % max(1, self.interval)) != 0:
            return False
        wds = set(self.weekday_ids.mapped("weekday"))
        return str(d.weekday()) in wds

    def _is_monthly_match(self, d: dt_date) -> bool:
        base = self.date_start or d
        # difference in months from base (year*12 + month index)
        months = (d.year - base.year) * 12 + (d.month - base.month)
        if months < 0 or (months % max(1, self.interval)) != 0:
            return False

        # 1) Monthday rule
        md_ok = False
        if self.monthday_ids:
            days = set(mo.day for mo in self.monthday_ids if 1 <= mo.day <= 31)
            last_day = calendar.monthrange(d.year, d.month)[1]
            md_ok = (d.day in days and d.day <= last_day)

        # 2) Weekday rule (optionally with bysetpos)
        wd_ok = False
        if self.byweekday_ids:
            target_wds = set(bw.weekday for bw in self.byweekday_ids)  # '0'..'6'
            if self.bysetpos:
                # Build list of all dates in month matching the weekdays, pick nth or last
                occs = []
                for day in range(1, calendar.monthrange(d.year, d.month)[1] + 1):
                    cand = dt_date(d.year, d.month, day)
                    if str(cand.weekday()) in target_wds:
                        occs.append(cand)
                if occs:
                    if self.bysetpos == -1:
                        wd_ok = (d == occs[-1])
                    else:
                        idx = self.bysetpos - 1
                        wd_ok = (0 <= idx < len(occs) and d == occs[idx])
            else:
                # No setpos: any weekday match in month
                wd_ok = (str(d.weekday()) in target_wds)

        if self.monthday_ids and self.byweekday_ids:
            # If both provided, either condition can validate the date (common expectation)
            return md_ok or wd_ok
        elif self.monthday_ids:
            return md_ok
        elif self.byweekday_ids:
            return wd_ok
        return False

    def _advance(self, d: dt_date) -> dt_date:
        """Advance cursor date by one 'tick' according to frequency, preserving limits."""
        if self.freq == "daily":
            return d + timedelta(days=max(1, self.interval))
        if self.freq == "weekly":
            return d + timedelta(weeks=max(1, self.interval))
        if self.freq == "monthly":
            # Advance month by 'interval'
            months = max(1, self.interval)
            y, m = d.year, d.month
            m += months
            y += (m - 1) // 12
            m = ((m - 1) % 12) + 1
            # Preserve day when possible; clamp to last day of target month
            last = calendar.monthrange(y, m)[1]
            day = min(d.day, last)
            return dt_date(y, m, day)
        # default fallback
        return d + timedelta(days=1)

    def _is_exdate(self, d: dt_date) -> bool:
        return bool(self.exdate_ids.filtered(lambda e: e.date == d and e.active))

    def _next_date_on_or_after(self, start_date: dt_date):
        """Find the next occurrence ON or AFTER 'start_date' (None if none)."""
        # Short-circuit with iter_dates
        it = self.iter_dates(date_from=start_date, date_to=None, max_count=1 if not self.count else self.count)
        for d in it:
            return d
        return None

    # -------------------------------------------------------------------------
    # PUBLIC API — DATETIME HELPERS
    # -------------------------------------------------------------------------
    def _sanitize_hour(self, val, default_val):
        if val is None:
            return default_val
        return max(0.0, min(24.0, float(val)))

    def _combine_date_hour(self, d: dt_date, hour_float: float) -> datetime:
        h = int(hour_float or 0.0)
        m = int(round(((hour_float or 0.0) - h) * 60.0))
        return datetime(d.year, d.month, d.day, h, m, 0)

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_view_slots(self):
        """Open slots linked to this recurring rule."""
        self.ensure_one()
        action = {
            "name": _("Slots"),
            "type": "ir.actions.act_window",
            "res_model": "booking.slot",
            "view_mode": "list,form,calendar,kanban",
            "domain": [("recurring_rule_id", "=", self.id)],
            "context": {"default_recurring_rule_id": self.id},
        }
        act_ref = self.env.ref("clinic_booking.action_booking_slot_list", raise_if_not_found=False)
        if act_ref:
            data = act_ref.read()[0]
            data.update(action)
            return data
        return action


# -----------------------------------------------------------------------------
# WEEKLY SELECTOR LINE (weekday)
# -----------------------------------------------------------------------------
class BookingRecurringWeekday(models.Model):
    _name = "booking.recurring.weekday"
    _description = "Recurring Rule Weekday"
    _order = "rule_id, weekday, id"

    rule_id = fields.Many2one(
        "booking.recurring.rule",
        string="Rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="rule_id.company_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
    )

    # Monday=0 .. Sunday=6 (string storage to simplify domains)
    weekday = fields.Selection(
        selection=[
            ("0", "Monday"), ("1", "Tuesday"), ("2", "Wednesday"),
            ("3", "Thursday"), ("4", "Friday"), ("5", "Saturday"), ("6", "Sunday"),
        ],
        string="Weekday",
        required=True,
        default="0",
        help="Day of the week included in the recurrence.",
    )

    _weekday_unique = models.Constraint(
        'unique(rule_id, weekday)',
        'Weekday already added to this rule.',
    )


# -----------------------------------------------------------------------------
# MONTHLY SELECTOR LINE (monthday 1..31)
# -----------------------------------------------------------------------------
class BookingRecurringMonthday(models.Model):
    _name = "booking.recurring.monthday"
    _description = "Recurring Rule Monthday"
    _order = "rule_id, day, id"

    rule_id = fields.Many2one(
        "booking.recurring.rule",
        string="Rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="rule_id.company_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
    )

    day = fields.Integer(
        string="Day of Month",
        required=True,
        help="Day of the month (1..31). Values above the month length will be ignored.",
    )

    @api.constrains("day")
    def _check_day(self):
        for rec in self:
            if rec.day < 1 or rec.day > 31:
                raise ValidationError(_("Day of month must be between 1 and 31."))

    _monthday_unique = models.Constraint(
        'unique(rule_id, day)',
        'This day is already included for the rule.',
    )


# -----------------------------------------------------------------------------
# MONTHLY SELECTOR LINE (weekday)
# -----------------------------------------------------------------------------
class BookingRecurringByWeekday(models.Model):
    _name = "booking.recurring.byweekday"
    _description = "Recurring Rule Monthly Weekday"
    _order = "rule_id, weekday, id"

    rule_id = fields.Many2one(
        "booking.recurring.rule",
        string="Rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="rule_id.company_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
    )

    weekday = fields.Selection(
        selection=[
            ("0", "Monday"), ("1", "Tuesday"), ("2", "Wednesday"),
            ("3", "Thursday"), ("4", "Friday"), ("5", "Saturday"), ("6", "Sunday"),
        ],
        string="Weekday",
        required=True,
        default="0",
        help="Weekday selector to be used for Monthly rules (optionally with Set Position).",
    )

    _byweekday_unique = models.Constraint(
        'unique(rule_id, weekday)',
        'This weekday is already included for the rule.',
    )


# -----------------------------------------------------------------------------
# EXDATE (exclusion date)
# -----------------------------------------------------------------------------
class BookingRecurringExdate(models.Model):
    _name = "booking.recurring.exdate"
    _description = "Recurring Rule Exclusion Date"
    _order = "date, id"

    rule_id = fields.Many2one(
        "booking.recurring.rule",
        string="Rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="rule_id.company_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Disable to temporarily ignore this exclusion date.",
    )

    date = fields.Date(
        string="Date",
        required=True,
        help="Date to exclude from occurrence generation.",
    )
    reason = fields.Char(
        string="Reason",
        help="Optional reason or note for this exclusion.",
    )

    _exdate_unique = models.Constraint(
        'unique(rule_id, date)',
        'This date is already excluded for the rule.',
    )


# -----------------------------------------------------------------------------
# (Optional) Abstract Mixin to attach recurrence to other models
# -----------------------------------------------------------------------------
class BookingRecurringRuleMixin(models.AbstractModel):
    _name = "booking.recurring.rule.mixin"
    _description = "Recurring Rule Mixin"

    recurring_rule_id = fields.Many2one(
        "booking.recurring.rule",
        string="Recurring Rule",
        index=True,
        help="Advanced recurrence rule used to generate occurrences.",
    )

    def generate_occurrence_windows(self, date_from, date_to=None, max_count=None,
                                    hour_from=None, hour_to=None, duration_minutes=None):
        """
        Convenience wrapper to iterate (start_dt, end_dt) from attached rule.
        """
        self.ensure_one()
        rule = self.recurring_rule_id
        if not rule:
            return []
        return list(rule.iter_windows(
            date_from=date_from,
            date_to=date_to,
            max_count=max_count,
            hour_from=hour_from,
            hour_to=hour_to,
            duration_minutes=duration_minutes,
        ))

# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/booking_resource.py
#
# Purpose
# -------
# Define clinical resources (devices, tools, consumables) used in bookings:
# - Availability checks with buffers, weekly schedules, and blackouts
# - Concurrency capacity (how many parallel bookings a resource supports)
# - Optional stock/consumable linkage (soft-coupled to stock/account flows)
#
# Models
# ------
# - booking.resource           : main resource entity
# - booking.resource.tag       : taxonomy for filtering/grouping resources
# - booking.resource.schedule  : weekly availability windows
# - booking.resource.blackout  : closures/maintenance windows
# - booking.resource.mixin     : reusable M2M field helper for other models
#
# Integrations (soft-coupled)
# ---------------------------
# - booking.booking.resource_ids (M2M)
# - booking.room.resource_ids (M2M, shared relation table with booking_room.py)
# - clinic_treatment (allowed_treatment_ids)
# - clinic_doctor (allowed_doctor_ids)
# - stock/product (product_id for consumables/equipment, optional)
#
# Notes
# -----
# - All user-facing strings are in English (per project requirement).
# - No hard-coded dependencies beyond what clinic_booking already declares.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta, time as dt_time


# -----------------------------------------------------------------------------
# booking.resource.tag (simple taxonomy)
# -----------------------------------------------------------------------------
class BookingResourceTag(models.Model):
    _name = "booking.resource.tag"
    _description = "Booking Resource Tag"
    _order = "name"

    name = fields.Char(
        string="Tag Name",
        required=True,
        help="Human-friendly tag name to classify resources (e.g., Laser, RF, Cryo).",
    )
    color = fields.Integer(
        string="Color Index",
        help="Optional color used in Kanban and list indicators.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        help="Company that owns this tag.",
    )

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Tag Name must be unique per company.',
    )


# -----------------------------------------------------------------------------
# booking.resource (main entity)
# -----------------------------------------------------------------------------
class BookingResource(models.Model):
    _name = "booking.resource"
    _description = "Booking Resource"
    _order = "sequence, name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # Identity
    name = fields.Char(
        string="Resource Name",
        required=True,
        tracking=True,
        help="Human-friendly name of the resource (e.g., 'Laser XYZ', 'RF Device #2').",
    )
    code = fields.Char(
        string="Resource Code",
        required=True,
        index=True,
        tracking=True,
        help="Unique technical code for this resource (URL-safe).",
    )
    resource_type = fields.Selection(
        selection=[
            ("device", "Device"),
            ("tool", "Tool"),
            ("consumable", "Consumable"),
            ("other", "Other"),
        ],
        string="Type",
        required=True,
        default="device",
        tracking=True,
        help="Classify the resource to enable type-specific behaviors.",
    )
    description = fields.Text(
        string="Description",
        help="Optional internal description of the resource.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Disable to hide this resource while preserving historical references.",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Lower values appear earlier in lists and suggestions.",
    )
    color = fields.Integer(
        string="Color Index",
        help="Optional color used in calendar/kanban indicators.",
    )

    # Company/Currency
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
        help="Company that owns this resource.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # Concurrency & Buffers
    capacity_concurrent = fields.Integer(
        string="Concurrent Capacity",
        default=1,
        help="How many bookings can use this resource simultaneously.",
    )
    buffer_before_minutes = fields.Integer(
        string="Buffer Before (min)",
        default=0,
        help="Preparation time reserved before the session.",
    )
    buffer_after_minutes = fields.Integer(
        string="Buffer After (min)",
        default=0,
        help="Cleaning/reset time reserved after the session.",
    )

    # Compatibility & Relations
    allowed_treatment_ids = fields.Many2many(
        "clinic.treatment",
        "booking_resource_treatment_rel",
        "resource_id",
        "treatment_id",
        string="Allowed Treatments",
        help="Restrict which treatments can use this resource. Leave empty for all.",
    )
    allowed_doctor_ids = fields.Many2many(
        "clinic.doctor",
        "booking_resource_doctor_rel",
        "resource_id",
        "doctor_id",
        string="Allowed Doctors",
        help="Restrict which doctors can use this resource. Leave empty for all.",
    )
    tag_ids = fields.Many2many(
        "booking.resource.tag",
        "booking_resource_tag_rel",
        "resource_id",
        "tag_id",
        string="Tags",
        help="Classify this resource for filtering and reporting.",
    )

    # Cross-link to Rooms (symmetric M2M defined also in booking_room.py)
    room_ids = fields.Many2many(
        "booking.room",
        "booking_room_resource_rel",
        "resource_id",
        "room_id",
        string="Rooms",
        help="Rooms where this resource is typically available.",
    )

    # Scheduling aids
    schedule_ids = fields.One2many(
        "booking.resource.schedule",
        "resource_id",
        string="Weekly Schedules",
        help="Weekly opening hours for this resource. Leave empty to allow all hours.",
    )
    blackout_ids = fields.One2many(
        "booking.resource.blackout",
        "resource_id",
        string="Blackouts",
        help="Ad-hoc closures (maintenance/cleaning) when the resource is not available.",
    )

    # Optional stock/product linkage
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        help="Product representing this device/consumable for inventory/accounting integration.",
    )
    product_tracking = fields.Selection(
        selection=[("none", "No Tracking"), ("lot", "By Lot"), ("serial", "By Unique Serial")],
        string="Product Tracking",
        compute="_compute_product_tracking",
        store=True,
        help="Tracking policy derived from the linked product.",
    )
    track_consumption = fields.Boolean(
        string="Track Consumption",
        help="Enable if the resource is a consumable and needs stock deduction.",
    )
    consumption_qty_per_booking = fields.Float(
        string="Consumption per Booking",
        default=0.0,
        help="Default quantity to consume per booking (for consumables).",
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        related="product_id.uom_id",
        store=True,
        readonly=True,
    )

    # Stats / Links
    bookings_count = fields.Integer(
        string="Bookings",
        compute="_compute_bookings_count",
        help="Number of active bookings using this resource.",
    )
    last_booking_id = fields.Many2one(
        "booking.booking",
        string="Last Booking",
        compute="_compute_last_booking",
        help="Most recently created booking that uses this resource.",
    )
    next_available_from = fields.Datetime(
        string="Next Available From",
        compute="_compute_next_available_from",
        help="Approximate next available time based on current bookings and blackouts.",
    )

    _code_company_unique = models.Constraint(
        'unique(code, company_id)',
        'Resource Code must be unique per company.',
    )

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Resource Name must be unique per company.',
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("product_id", "product_id.tracking")
    def _compute_product_tracking(self):
        for rec in self:
            tracking = (rec.product_id and rec.product_id.tracking) or "none"
            # product.tracking values in Odoo: 'none', 'lot', 'serial'
            rec.product_tracking = tracking or "none"

    def _domain_bookings(self):
        # Count confirmed/in_progress bookings that include this resource
        return [
            ("resource_ids", "in", self.id),
            ("state", "in", ["confirmed", "in_progress"]),
            ("active", "=", True),
        ]

    def _compute_bookings_count(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            rec.bookings_count = Booking.search_count(rec._domain_bookings())

    def _compute_last_booking(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            last = Booking.search([("resource_ids", "in", rec.id)], order="create_date desc, id desc", limit=1)
            rec.last_booking_id = last.id if last else False

    def _compute_next_available_from(self):
        """Heuristic probing (15-min steps up to 14 hours) to suggest next free time."""
        for rec in self:
            now = fields.Datetime.now()
            if rec.is_available(now, now + timedelta(minutes=1)):
                rec.next_available_from = now
                continue

            step = timedelta(minutes=15)
            probe = now
            for _i in range(0, int((14 * 60) / 15)):
                window_end = probe + step
                if rec.is_available(probe, window_end):
                    rec.next_available_from = probe
                    break
                probe = window_end
            else:
                rec.next_available_from = False

    # -------------------------------------------------------------------------
    # NAME / DISPLAY
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            label = rec.name or _("Resource")
            code = rec.code and f"[{rec.code}] " or ""
            if rec.company_id and self.env.companies and len(self.env.companies) > 1:
                label = f"{code}{label} - {rec.company_id.name}"
            else:
                label = f"{code}{label}"
            res.append((rec.id, label))
        return res

    # -------------------------------------------------------------------------
    # AVAILABILITY LOGIC
    # -------------------------------------------------------------------------
    def is_available(self, start_dt, end_dt, ignore_booking_id=None, required_units=1, consider_capacity=True):
        """
        Check if the resource is available between start_dt and end_dt.

        :param start_dt: datetime or string
        :param end_dt: datetime or string
        :param ignore_booking_id: optional booking id to exclude from overlap checks
        :param required_units: how many concurrent units are needed (>=1)
        :param consider_capacity: if False, only returns True when no overlap at all
        :return: bool
        """
        self.ensure_one()
        if not start_dt or not end_dt:
            return False

        start = fields.Datetime.from_string(start_dt) if isinstance(start_dt, str) else start_dt
        end = fields.Datetime.from_string(end_dt) if isinstance(end_dt, str) else end_dt
        if end <= start:
            return False

        # Apply buffers around requested window
        start_with_buffer = start - timedelta(minutes=self.buffer_before_minutes or 0)
        end_with_buffer = end + timedelta(minutes=self.buffer_after_minutes or 0)

        # Blackouts
        if self._overlaps_blackout(start_with_buffer, end_with_buffer):
            return False

        # Weekly schedules
        if not self._fits_weekly_schedule(start_with_buffer, end_with_buffer):
            return False

        # Overlapping bookings
        if consider_capacity:
            overlaps = self._count_overlapping_bookings(start_with_buffer, end_with_buffer, ignore_booking_id)
            cap = max(1, self.capacity_concurrent or 1)
            need = max(1, required_units or 1)
            # Available if concurrent overlaps + need <= capacity
            return (overlaps + need) <= cap
        else:
            return not self._has_overlapping_booking(start_with_buffer, end_with_buffer, ignore_booking_id)

    def _overlaps_blackout(self, start, end):
        Blackout = self.env["booking.resource.blackout"]
        overlapped = Blackout.search_count([
            ("resource_id", "=", self.id),
            ("active", "=", True),
            ("start_datetime", "<", end),
            ("end_datetime", ">", start),
        ])
        return bool(overlapped)

    def _fits_weekly_schedule(self, start, end):
        schedules = self.schedule_ids.filtered(lambda s: s.active)
        if not schedules:
            return True

        cursor = start
        while cursor < end:
            day_end = datetime.combine(cursor.date(), dt_time.max).replace(microsecond=0)
            segment_end = min(end, day_end)
            weekday = cursor.weekday()  # Monday=0..Sunday=6
            start_hours = cursor.hour + cursor.minute / 60.0
            end_hours = segment_end.hour + segment_end.minute / 60.0

            day_schedules = schedules.filtered(lambda s: s.weekday == str(weekday))
            fits = any((start_hours >= s.hour_from and end_hours <= s.hour_to) for s in day_schedules)
            if not fits:
                return False
            cursor = segment_end + timedelta(seconds=1)
        return True

    def _has_overlapping_booking(self, start, end, ignore_booking_id=None):
        Booking = self.env["booking.booking"]
        domain = [
            ("resource_ids", "in", self.id),
            ("state", "in", ["confirmed", "in_progress"]),
            ("start_datetime", "<", fields.Datetime.to_string(end)),
            ("end_datetime", ">", fields.Datetime.to_string(start)),
        ]
        if ignore_booking_id:
            domain.append(("id", "!=", ignore_booking_id))
        return bool(Booking.search_count(domain))

    def _count_overlapping_bookings(self, start, end, ignore_booking_id=None):
        Booking = self.env["booking.booking"]
        domain = [
            ("resource_ids", "in", self.id),
            ("state", "in", ["confirmed", "in_progress"]),
            ("start_datetime", "<", fields.Datetime.to_string(end)),
            ("end_datetime", ">", fields.Datetime.to_string(start)),
        ]
        if ignore_booking_id:
            domain.append(("id", "!=", ignore_booking_id))
        return Booking.search_count(domain)

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_view_bookings(self):
        self.ensure_one()
        action = {
            "name": _("Bookings"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "list,form,calendar,kanban,activity,pivot,graph",
            "domain": [("resource_ids", "in", self.id)],
            "context": {"default_resource_ids": [(6, 0, [self.id])]},
        }
        act_ref = self.env.ref("clinic_booking.action_booking_list", raise_if_not_found=False)
        if act_ref:
            data = act_ref.read()[0]
            data.update(action)
            return data
        return action

    def action_new_booking(self):
        self.ensure_one()
        return {
            "name": _("New Booking"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "form",
            "context": {"default_resource_ids": [(6, 0, [self.id])]},
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # VALIDATIONS
    # -------------------------------------------------------------------------
    @api.constrains("capacity_concurrent")
    def _check_capacity(self):
        for rec in self:
            if rec.capacity_concurrent and rec.capacity_concurrent < 1:
                raise ValidationError(_("Concurrent capacity must be at least 1."))

    @api.constrains("resource_type", "track_consumption", "product_id", "consumption_qty_per_booking")
    def _check_consumption_config(self):
        for rec in self:
            if rec.track_consumption:
                if not rec.product_id:
                    raise ValidationError(_("Tracking consumption requires a linked Product."))
                if rec.consumption_qty_per_booking <= 0.0:
                    raise ValidationError(_("Consumption per Booking must be greater than 0."))
                if rec.resource_type != "consumable":
                    # Not an error, but warn users to align type with behavior
                    pass

    # -------------------------------------------------------------------------
    # STOCK HELPERS (SOFT-COUPLED)
    # -------------------------------------------------------------------------
    def prepare_stock_moves(self, booking, location_id=None, dest_location_id=None, qty=None):
        """
        Prepare stock.move values to consume this resource for a given booking.
        This does not create any records; callers must handle creation/posting.
        Intended for consumables. For devices (non-consumable), use maintenance flows.
        """
        self.ensure_one()
        if not self.track_consumption or not self.product_id:
            return []
        if not booking:
            return []

        # Determine quantity
        quantity = qty if qty is not None else (self.consumption_qty_per_booking or 0.0)
        if quantity <= 0.0:
            return []

        # Guess locations if not provided (very installation-specific; keep safe)
        StockLocation = self.env["stock.location"]
        if not location_id:
            src = StockLocation.search([("usage", "=", "internal"), ("company_id", "=", self.company_id.id)], limit=1)
            location_id = src.id if src else False
        if not dest_location_id:
            # For consumptions, destination could be a 'Customer' or 'Production' or 'Inventory loss' location.
            # Keep None to let caller decide; or pick first 'customer' as soft default.
            dest = StockLocation.search([("usage", "=", "customer")], limit=1)
            dest_location_id = dest.id if dest else False

        move_vals = {
            "name": f"[{self.product_id.display_name}] Booking {booking.name}",
            "product_id": self.product_id.id,
            "product_uom": self.uom_id.id or self.product_id.uom_id.id,
            "product_uom_qty": quantity,
            "location_id": location_id,
            "location_dest_id": dest_location_id,
            "company_id": self.company_id.id,
            "origin": booking.name,
            # link to picking (optional) left to caller
        }
        return [move_vals]


# -----------------------------------------------------------------------------
# booking.resource.schedule (weekly availability windows)
# -----------------------------------------------------------------------------
class BookingResourceSchedule(models.Model):
    _name = "booking.resource.schedule"
    _description = "Booking Resource Weekly Schedule"
    _order = "resource_id, weekday, hour_from"

    resource_id = fields.Many2one(
        "booking.resource",
        string="Resource",
        required=True,
        ondelete="cascade",
        index=True,
        help="Resource to which this schedule applies.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="resource_id.company_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Disable to temporarily ignore this schedule window.",
    )

    weekday = fields.Selection(
        selection=[
            ("0", "Monday"), ("1", "Tuesday"), ("2", "Wednesday"),
            ("3", "Thursday"), ("4", "Friday"), ("5", "Saturday"), ("6", "Sunday"),
        ],
        string="Weekday",
        required=True,
        default="0",
        help="Day of the week when this schedule applies.",
    )
    hour_from = fields.Float(
        string="From (hour)",
        required=True,
        default=9.0,
        help="Start time (0.0 - 24.0). Example: 9.0 = 09:00.",
    )
    hour_to = fields.Float(
        string="To (hour)",
        required=True,
        default=17.0,
        help="End time (0.0 - 24.0). Example: 17.0 = 17:00.",
    )
    note = fields.Char(
        string="Note",
        help="Optional note (e.g., 'Nurse required', 'Only after calibration').",
    )

    @api.constrains("hour_from", "hour_to")
    def _check_hours(self):
        for rec in self:
            if rec.hour_from < 0.0 or rec.hour_to > 24.0:
                raise ValidationError(_("Schedule hours must be within 0.0 and 24.0."))
            if rec.hour_to <= rec.hour_from:
                raise ValidationError(_("End hour must be greater than start hour."))


# -----------------------------------------------------------------------------
# booking.resource.blackout (closures / maintenance windows)
# -----------------------------------------------------------------------------
class BookingResourceBlackout(models.Model):
    _name = "booking.resource.blackout"
    _description = "Booking Resource Blackout"
    _order = "start_datetime desc"

    resource_id = fields.Many2one(
        "booking.resource",
        string="Resource",
        required=True,
        ondelete="cascade",
        index=True,
        help="Resource that is not available during this blackout window.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="resource_id.company_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Disable to ignore this blackout without deleting it.",
    )
    start_datetime = fields.Datetime(
        string="Start",
        required=True,
        help="Start datetime of the blackout window.",
    )
    end_datetime = fields.Datetime(
        string="End",
        required=True,
        help="End datetime of the blackout window.",
    )
    reason = fields.Char(
        string="Reason",
        help="Short reason for the blackout (e.g., 'Maintenance', 'Calibration').",
    )
    internal_notes = fields.Text(
        string="Internal Notes",
        help="Additional notes for staff about this blackout.",
    )

    @api.constrains("start_datetime", "end_datetime")
    def _check_range(self):
        for rec in self:
            if rec.start_datetime and rec.end_datetime and rec.end_datetime <= rec.start_datetime:
                raise ValidationError(_("End time must be greater than start time."))

    def action_view_conflicting_bookings(self):
        self.ensure_one()
        action = {
            "name": _("Conflicting Bookings"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "list,form,calendar,kanban,activity",
            "domain": [
                ("resource_ids", "in", self.resource_id.id),
                ("state", "in", ["confirmed", "in_progress"]),
                ("start_datetime", "<", self.end_datetime),
                ("end_datetime", ">", self.start_datetime),
            ],
        }
        act_ref = self.env.ref("clinic_booking.action_booking_list", raise_if_not_found=False)
        if act_ref:
            data = act_ref.read()[0]
            data.update(action)
            return data
        return action


# -----------------------------------------------------------------------------
# booking.resource.mixin (reusable field for other models)
# -----------------------------------------------------------------------------
class BookingResourceMixin(models.AbstractModel):
    _name = "booking.resource.mixin"
    _description = "Booking Resource Mixin"

    resource_ids = fields.Many2many(
        "booking.resource",
        "booking_resource_rel",
        "booking_id",
        "resource_id",
        string="Resources",
        help="Resources (devices/tools/consumables) associated with this record.",
    )

    @api.onchange("resource_ids")
    def _onchange_resource_ids(self):
        """Hook for inheriting models: validate compatibility or apply defaults."""
        # Example: clear resources not allowed for selected treatment/doctor if those fields exist
        for rec in self:
            if not rec.resource_ids:
                continue

            # If the model has treatment_id/doctor_id, validate compatibility
            treatment = getattr(rec, "treatment_id", False)
            doctor = getattr(rec, "doctor_id", False)
            cleaned = rec.resource_ids
            if treatment:
                cleaned = cleaned.filtered(lambda r: not r.allowed_treatment_ids or treatment in r.allowed_treatment_ids)
            if doctor:
                cleaned = cleaned.filtered(lambda r: not r.allowed_doctor_ids or doctor in r.allowed_doctor_ids)
            if cleaned != rec.resource_ids:
                rec.resource_ids = cleaned
                return {
                    "warning": {
                        "title": _("Resource Compatibility"),
                        "message": _(
                            "Some resources were removed because they are not compatible with the selected "
                            "treatment or doctor."
                        ),
                    }
                }
        return {}

# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/booking_room.py
#
# Goal
# ----
# Provide a booking-focused wrapper around core clinical rooms by delegating to
# `clinic.room`, adding scheduling/availability rules, buffers, compatibility,
# and convenience actions for the booking workflow.
#
# Key points
# ----------
# - `booking.room` uses `_inherits` to delegate fields to `clinic.room`
#   (via `clinic_room_id`) to avoid data duplication and keep a single source
#   of truth for rooms across the ecosystem (queueing, encounters, etc.).
# - Adds booking-specific settings: buffers, compatibility, capacity overrides,
#   schedules/blackouts, resources, and quick availability checks.
# - Integrates softly with booking, doctor, treatment, inventory, and queueing
#   (without hard circular dependencies).
#
# Models
# ------
# - booking.room               : main booking wrapper for clinic.room
# - booking.room.schedule      : weekly opening hours / availability windows
# - booking.room.blackout      : ad-hoc or ranged closures (maintenance/cleaning)
# - booking.room.tag           : simple tagging for filtering and grouping
#
# Notes
# -----
# - All user-facing strings are in English (as requested).
# - Avoids hard-coded XML IDs except where guarded by raise_if_not_found=False.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta, time as dt_time


# ---------------------------------------------------------------------------
# booking.room.tag (optional helper taxonomy)
# ---------------------------------------------------------------------------
class BookingRoomTag(models.Model):
    _name = "booking.room.tag"
    _description = "Booking Room Tag"
    _order = "name"

    name = fields.Char(
        string="Tag Name",
        required=True,
        help="Human-friendly tag name to classify rooms (e.g., Laser, VIP, Isolation).",
    )
    color = fields.Integer(
        string="Color Index",
        help="Optional color used in Kanban and list indicators.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        help="Company that owns this tag.",
    )

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Tag Name must be unique per company.',
    )


# ---------------------------------------------------------------------------
# booking.room
# ---------------------------------------------------------------------------
class BookingRoom(models.Model):
    _name = "booking.room"
    _description = "Booking Room"
    _order = "sequence, name"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    # Delegate to clinic.room (keeps clinic.room as source of truth)
    _inherits = {"clinic.room": "clinic_room_id"}

    # Delegation handle
    clinic_room_id = fields.Many2one(
        "clinic.room",
        string="Clinic Room",
        required=True,
        ondelete="restrict",
        index=True,
        help="Backing clinical room record (delegated).",
    )

    # Basic mirrors / convenience
    name = fields.Char(
        string="Room Name",
        related="clinic_room_id.name",
        store=True,
        readonly=False,
        help="Display name of the room (delegated from Clinic Room).",
    )
    code = fields.Char(
        string="Room Code",
        related="clinic_room_id.code",
        store=True,
        readonly=False,
        help="Unique code of the room (delegated from Clinic Room).",
    )
    active = fields.Boolean(
        string="Active",
        related="clinic_room_id.active",
        store=True,
        readonly=False,
        help="If unchecked, the room is hidden from selection but kept historically.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="clinic_room_id.company_id",
        store=True,
        readonly=False,
    )

    # Booking-specific configuration
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Lower value → higher priority in suggestions and lists.",
    )
    color = fields.Integer(
        string="Color Index",
        help="Optional color used for calendar/kanban indicators.",
    )
    notes = fields.Text(
        string="Notes",
        help="Internal notes relevant for booking or preparation.",
    )

    # Capacity (can be delegated or overridden)
    capacity = fields.Integer(
        string="Capacity",
        default=1,
        help="How many patients can be booked simultaneously in this room.",
    )

    # Buffers (pre/post cleanup, preparation time)
    buffer_before_minutes = fields.Integer(
        string="Buffer Before (min)",
        default=0,
        help="Minimum minutes reserved before the session for preparation.",
    )
    buffer_after_minutes = fields.Integer(
        string="Buffer After (min)",
        default=10,
        help="Minimum minutes reserved after the session for cleaning/reset.",
    )

    # Compatibility and defaults
    allowed_treatment_ids = fields.Many2many(
        "clinic.treatment",
        "booking_room_treatment_rel",
        "room_id",
        "treatment_id",
        string="Allowed Treatments",
        help="Restrict which treatments can be performed in this room. Leave empty for all.",
    )
    allowed_doctor_ids = fields.Many2many(
        "clinic.doctor",
        "booking_room_doctor_rel",
        "room_id",
        "doctor_id",
        string="Allowed Doctors",
        help="Restrict which doctors can be assigned to this room. Leave empty for all.",
    )
    resource_ids = fields.Many2many(
        "booking.resource",
        "booking_room_resource_rel",
        "room_id",
        "resource_id",
        string="Required Resources",
        help="Devices/machines/tools usually required for this room.",
    )
    tag_ids = fields.Many2many(
        "booking.room.tag",
        "booking_room_tag_rel",
        "room_id",
        "tag_id",
        string="Tags",
        help="Classify this room for filtering and reporting.",
    )

    # Scheduling aids
    schedule_ids = fields.One2many(
        "booking.room.schedule",
        "room_id",
        string="Weekly Schedules",
        help="Weekly opening hours for this room. Leave empty to allow all hours.",
    )
    blackout_ids = fields.One2many(
        "booking.room.blackout",
        "room_id",
        string="Blackouts",
        help="Ad-hoc closures (maintenance/cleaning) when the room is not available.",
    )

    # Stats / Links
    bookings_count = fields.Integer(
        string="Bookings",
        compute="_compute_bookings_count",
        help="Number of active bookings assigned to this room.",
    )
    last_booking_id = fields.Many2one(
        "booking.booking",
        string="Last Booking",
        compute="_compute_last_booking",
        help="Most recently created booking for this room.",
    )
    next_available_from = fields.Datetime(
        string="Next Available From",
        compute="_compute_next_available_from",
        help="Approximate next available time based on current bookings and blackouts.",
    )

    _clinic_room_company_unique = models.Constraint(
        'unique(clinic_room_id, company_id)',
        'This Clinic Room is already wrapped for the company.',
    )

    # ---------------------------------------------------------------------
    # COMPUTES
    # ---------------------------------------------------------------------
    def _domain_bookings(self):
        return [("room_id", "=", self.id), ("state", "in", ["confirmed", "in_progress"]), ("active", "=", True)]

    def _compute_bookings_count(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            rec.bookings_count = Booking.search_count(rec._domain_bookings())

    def _compute_last_booking(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            last = Booking.search([("room_id", "=", rec.id)], order="create_date desc, id desc", limit=1)
            rec.last_booking_id = last.id if last else False

    def _compute_next_available_from(self):
        """A lightweight heuristic that returns now() if free, or end of the
        latest overlapping booking/blackout + buffer."""
        for rec in self:
            now = fields.Datetime.now()
            # If currently available, return now.
            if rec.is_available(now, now + timedelta(minutes=1)):
                rec.next_available_from = now
                continue

            # Find the smallest future time >= now where availability is true,
            # scanning in small steps (not too heavy).
            # NOTE: For performance in large DBs, a more sophisticated query is recommended.
            step = timedelta(minutes=15)
            probe = now
            # Cap the probing window to avoid long loops (e.g., 14 hours ahead)
            # Adjust as needed in real deployments.
            for _i in range(0, int((14 * 60) / 15)):
                window_end = probe + step
                if rec.is_available(probe, window_end):
                    rec.next_available_from = probe
                    break
                probe = window_end
            else:
                rec.next_available_from = False

    # ---------------------------------------------------------------------
    # NAME / DISPLAY
    # ---------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            label = rec.name or _("Room")
            # Add code and company name for clarity in multi-company contexts
            code = rec.code and f"[{rec.code}] " or ""
            if rec.company_id and self.env.companies and len(self.env.companies) > 1:
                label = f"{code}{label} - {rec.company_id.name}"
            else:
                label = f"{code}{label}"
            res.append((rec.id, label))
        return res

    # ---------------------------------------------------------------------
    # CORE LOGIC: Availability checks
    # ---------------------------------------------------------------------
    def is_available(self, start_dt, end_dt, ignore_booking_id=None, consider_capacity=True):
        """
        Check if the room is available between start_dt and end_dt,
        considering buffers, blackouts, weekly schedules, and overlapping bookings.

        :param start_dt: datetime or string (UTC-aware recommended)
        :param end_dt: datetime or string
        :param ignore_booking_id: optional booking id to exclude from overlap checks
        :param consider_capacity: if True, evaluates capacity (>= number of overlaps)
        :return: bool
        """
        self.ensure_one()
        if not start_dt or not end_dt:
            return False

        # Normalize to datetime objects
        start = fields.Datetime.from_string(start_dt) if isinstance(start_dt, str) else start_dt
        end = fields.Datetime.from_string(end_dt) if isinstance(end_dt, str) else end_dt
        if end <= start:
            return False

        # Apply buffers
        start_with_buffer = start - timedelta(minutes=self.buffer_before_minutes or 0)
        end_with_buffer = end + timedelta(minutes=self.buffer_after_minutes or 0)

        # Check blackouts first
        if self._overlaps_blackout(start_with_buffer, end_with_buffer):
            return False

        # Check weekly schedule windows
        if not self._fits_weekly_schedule(start_with_buffer, end_with_buffer):
            return False

        # Check overlapping bookings
        if consider_capacity:
            overlaps = self._count_overlapping_bookings(start_with_buffer, end_with_buffer, ignore_booking_id=ignore_booking_id)
            return overlaps < max(1, self.capacity or 1)
        else:
            return not self._has_overlapping_booking(start_with_buffer, end_with_buffer, ignore_booking_id=ignore_booking_id)

    def _overlaps_blackout(self, start, end):
        """Return True if any blackout overlaps with [start, end)."""
        Blackout = self.env["booking.room.blackout"]
        overlapped = Blackout.search_count([
            ("room_id", "=", self.id),
            ("active", "=", True),
            ("start_datetime", "<", end),
            ("end_datetime", ">", start),
        ])
        return bool(overlapped)

    def _fits_weekly_schedule(self, start, end):
        """
        If schedules are defined, require that the entire interval falls within at least
        one schedule window per day crossed. If no schedules -> allow all hours.
        """
        schedules = self.schedule_ids.filtered(lambda s: s.active)
        if not schedules:
            return True

        # Iterate day by day; require full fit within some window each day
        cursor = start
        # Use 1-minute step at day boundaries to ensure inclusive logic
        while cursor < end:
            day_end = datetime.combine(cursor.date(), dt_time.max).replace(microsecond=0)
            segment_end = min(end, day_end)
            # Convert to local day-of-week and times in hours
            weekday = cursor.weekday()  # Monday=0 .. Sunday=6
            start_hours = cursor.hour + cursor.minute / 60.0
            end_hours = segment_end.hour + segment_end.minute / 60.0

            day_schedules = schedules.filtered(lambda s: s.weekday == str(weekday))
            # The day's interval must be fully contained in at least one schedule window
            fits = any((start_hours >= s.hour_from and end_hours <= s.hour_to) for s in day_schedules)
            if not fits:
                return False

            cursor = segment_end + timedelta(seconds=1)
        return True

    def _has_overlapping_booking(self, start, end, ignore_booking_id=None):
        Booking = self.env["booking.booking"]
        domain = [
            ("room_id", "=", self.id),
            ("state", "in", ["confirmed", "in_progress"]),
            ("start_datetime", "<", fields.Datetime.to_string(end)),
            ("end_datetime", ">", fields.Datetime.to_string(start)),
        ]
        if ignore_booking_id:
            domain.append(("id", "!=", ignore_booking_id))
        return bool(Booking.search_count(domain))

    def _count_overlapping_bookings(self, start, end, ignore_booking_id=None):
        Booking = self.env["booking.booking"]
        domain = [
            ("room_id", "=", self.id),
            ("state", "in", ["confirmed", "in_progress"]),
            ("start_datetime", "<", fields.Datetime.to_string(end)),
            ("end_datetime", ">", fields.Datetime.to_string(start)),
        ]
        if ignore_booking_id:
            domain.append(("id", "!=", ignore_booking_id))
        return Booking.search_count(domain)

    # ---------------------------------------------------------------------
    # ACTIONS
    # ---------------------------------------------------------------------
    def action_view_bookings(self):
        self.ensure_one()
        action = {
            "name": _("Bookings"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "list,form,calendar,kanban,activity,pivot,graph",
            "domain": [("room_id", "=", self.id)],
            "context": {"default_room_id": self.id},
        }
        # Try to reuse predefined action if available
        act_ref = self.env.ref("clinic_booking.action_booking_list", raise_if_not_found=False)
        if act_ref:
            action = act_ref.read()[0]
            action.update({"domain": [("room_id", "=", self.id)]})
            ctx = action.get("context", {}) or {}
            ctx.update({"default_room_id": self.id})
            action["context"] = ctx
        return action

    def action_new_booking(self):
        """Quick-create action to start a booking with this room prefilled."""
        self.ensure_one()
        return {
            "name": _("New Booking"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "form",
            "context": {"default_room_id": self.id},
            "target": "current",
        }

    # ---------------------------------------------------------------------
    # VALIDATIONS / CONSTRAINS
    # ---------------------------------------------------------------------
    @api.constrains("capacity")
    def _check_capacity(self):
        for rec in self:
            if rec.capacity and rec.capacity < 1:
                raise ValidationError(_("Room capacity must be at least 1."))


# ---------------------------------------------------------------------------
# booking.room.schedule (weekly availability windows)
# ---------------------------------------------------------------------------
class BookingRoomSchedule(models.Model):
    _name = "booking.room.schedule"
    _description = "Booking Room Weekly Schedule"
    _order = "room_id, weekday, hour_from"

    room_id = fields.Many2one(
        "booking.room",
        string="Room",
        required=True,
        ondelete="cascade",
        index=True,
        help="Room to which this schedule applies.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="room_id.company_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Disable to temporarily ignore this schedule window.",
    )

    # Monday=0 .. Sunday=6 (string to ease domain filters in XML)
    weekday = fields.Selection(
        selection=[
            ("0", "Monday"), ("1", "Tuesday"), ("2", "Wednesday"),
            ("3", "Thursday"), ("4", "Friday"), ("5", "Saturday"), ("6", "Sunday"),
        ],
        string="Weekday",
        required=True,
        default="0",
        help="Day of the week when this schedule applies.",
    )
    hour_from = fields.Float(
        string="From (hour)",
        required=True,
        default=9.0,
        help="Start time (0.0 - 24.0). Example: 9.0 = 09:00.",
    )
    hour_to = fields.Float(
        string="To (hour)",
        required=True,
        default=17.0,
        help="End time (0.0 - 24.0). Example: 17.0 = 17:00.",
    )

    # Optional comments/notes about this window (e.g., lunch breaks, staff rotations)
    note = fields.Char(
        string="Note",
        help="Optional note (e.g., 'AM shift', 'Senior doctor required', etc.).",
    )

    @api.constrains("hour_from", "hour_to")
    def _check_hours(self):
        for rec in self:
            if rec.hour_from < 0.0 or rec.hour_to > 24.0:
                raise ValidationError(_("Schedule hours must be within 0.0 and 24.0."))
            if rec.hour_to <= rec.hour_from:
                raise ValidationError(_("End hour must be greater than start hour."))


# ---------------------------------------------------------------------------
# booking.room.blackout (closures / maintenance windows)
# ---------------------------------------------------------------------------
class BookingRoomBlackout(models.Model):
    _name = "booking.room.blackout"
    _description = "Booking Room Blackout"
    _order = "start_datetime desc"

    room_id = fields.Many2one(
        "booking.room",
        string="Room",
        required=True,
        ondelete="cascade",
        index=True,
        help="Room that is not available during this blackout window.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="room_id.company_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Disable to ignore this blackout without deleting it.",
    )
    start_datetime = fields.Datetime(
        string="Start",
        required=True,
        help="Start datetime of the blackout window.",
    )
    end_datetime = fields.Datetime(
        string="End",
        required=True,
        help="End datetime of the blackout window.",
    )
    reason = fields.Char(
        string="Reason",
        help="Short reason for the blackout (e.g., 'Maintenance', 'Deep cleaning').",
    )
    internal_notes = fields.Text(
        string="Internal Notes",
        help="Additional notes for staff about this blackout.",
    )

    @api.constrains("start_datetime", "end_datetime")
    def _check_range(self):
        for rec in self:
            if rec.start_datetime and rec.end_datetime and rec.end_datetime <= rec.start_datetime:
                raise ValidationError(_("End time must be greater than start time."))

    # Convenience action to view bookings colliding with this blackout
    def action_view_conflicting_bookings(self):
        self.ensure_one()
        action = {
            "name": _("Conflicting Bookings"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "list,form,calendar,kanban,activity",
            "domain": [
                ("room_id", "=", self.room_id.id),
                ("state", "in", ["confirmed", "in_progress"]),
                ("start_datetime", "<", self.end_datetime),
                ("end_datetime", ">", self.start_datetime),
            ],
        }
        act_ref = self.env.ref("clinic_booking.action_booking_list", raise_if_not_found=False)
        if act_ref:
            data = act_ref.read()[0]
            data.update(action)
            return data
        return action

# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/booking_slot.py
#
# Purpose
# -------
# Provide bookable time slots that can be attached to a booking or used as
# a template for recurring availability windows (per doctor/room/channel).
#
# Models
# ------
# - booking.slot            : primary slot definition (can be one-off or recurring)
# - booking.slot.exception  : per-date exceptions that disable or modify slots
#
# Key Integrations (soft-coupled, no circular deps)
# -------------------------------------------------
# - booking.booking.slot_id (prefill booking fields from slot)
# - clinic.doctor (doctor availability checks)
# - booking.room / booking.resource (availability checks with buffers/capacity)
# - booking.policy / booking.channel (defaults)
# - Optional: booking.recurring.rule (if present in this module set)
#
# Notes
# -----
# - All user-facing strings are in English (per project requirement).
# - We avoid hard-coded XML-IDs; where needed, guard with raise_if_not_found=False.
# - Recurrence is kept simple here (weekday + time window + date range). A richer
#   RRULE can be provided by 'booking.recurring.rule' (if implemented separately).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta, time as dt_time


# -----------------------------------------------------------------------------
# booking.slot (primary model)
# -----------------------------------------------------------------------------
class BookingSlot(models.Model):
    _name = "booking.slot"
    _description = "Booking Slot"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, weekday, hour_from, id"

    # Identity
    name = fields.Char(
        string="Slot Name",
        required=True,
        tracking=True,
        help="Human-friendly name of the slot (e.g., 'Morning Slot (Dr. A) Room 1').",
    )
    code = fields.Char(
        string="Technical Code",
        required=True,
        index=True,
        tracking=True,
        help="Unique, URL-safe technical code of this slot.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Disable the slot while preserving historical references.",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Lower values show earlier in lists and suggestions.",
    )
    color = fields.Integer(
        string="Color Index",
        help="Optional color used in calendar/kanban indicators.",
    )

    # Company / Currency
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # Scope / Participants / Defaults
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        index=True,
        help="Doctor primarily associated with this slot (optional).",
    )
    room_id = fields.Many2one(
        "booking.room",
        string="Room",
        index=True,
        help="Room primarily used by this slot (optional).",
    )
    resource_ids = fields.Many2many(
        "booking.resource",
        "booking_slot_resource_rel",
        "slot_id",
        "resource_id",
        string="Resources",
        help="Devices/tools typically needed in this slot (optional).",
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Default Treatment",
        help="Optional default treatment when booking is created from this slot.",
    )
    channel_id = fields.Many2one(
        "booking.channel",
        string="Default Channel",
        help="Default booking channel for bookings created from this slot.",
    )
    policy_id = fields.Many2one(
        "booking.policy",
        string="Default Policy",
        help="Default booking policy for bookings created from this slot.",
    )

    # Time window (weekday + hour range) — recurrence-lite
    weekday = fields.Selection(
        selection=[
            ("0", "Monday"), ("1", "Tuesday"), ("2", "Wednesday"),
            ("3", "Thursday"), ("4", "Friday"), ("5", "Saturday"), ("6", "Sunday"),
        ],
        string="Weekday",
        required=True,
        default="0",
        help="Day of the week when the slot is normally available.",
    )
    hour_from = fields.Float(
        string="From (hour)",
        required=True,
        default=9.0,
        help="Start time in 24-hour decimal (0.0 - 24.0). Example: 9.0 = 09:00.",
    )
    hour_to = fields.Float(
        string="To (hour)",
        required=True,
        default=12.0,
        help="End time in 24-hour decimal (0.0 - 24.0). Example: 12.0 = 12:00.",
    )
    duration_minutes = fields.Integer(
        string="Default Duration (min)",
        default=60,
        help="Default appointment duration created from this slot.",
    )

    # Effectivity range
    date_start = fields.Date(
        string="Effective From",
        help="Optional start date when this slot becomes effective.",
    )
    date_end = fields.Date(
        string="Effective Until",
        help="Optional end date after which this slot no longer applies.",
    )

    # Capacity & Buffers (override defaults of room/resources if needed)
    capacity = fields.Integer(
        string="Capacity",
        default=1,
        help="How many bookings can be created in parallel within this slot.",
    )
    buffer_before_minutes = fields.Integer(
        string="Buffer Before (min)",
        default=0,
        help="Preparation time before each booking created from this slot.",
    )
    buffer_after_minutes = fields.Integer(
        string="Buffer After (min)",
        default=0,
        help="Cleaning/reset time after each booking created from this slot.",
    )

    # Optional richer recurrence (if model exists)
    recurring_rule_id = fields.Many2one(
        "booking.recurring.rule",
        string="Recurring Rule",
        help="Optional advanced recurrence rule if available (daily/weekly/custom).",
    )

    # Stats / Links
    bookings_count = fields.Integer(
        string="Bookings",
        compute="_compute_bookings_count",
        help="Number of bookings linked to this slot (active ones).",
    )
    last_booking_id = fields.Many2one(
        "booking.booking",
        string="Last Booking",
        compute="_compute_last_booking",
        help="Most recently created booking made via this slot.",
    )

    # UI / Notes
    description = fields.Text(
        string="Description",
        help="Optional description or internal notes about this slot.",
    )

    _code_company_unique = models.Constraint(
        'unique(code, company_id)',
        'Slot Technical Code must be unique per company.',
    )

    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Slot Name must be unique per company.',
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("hour_from", "hour_to")
    def _check_hours(self):
        for rec in self:
            if rec.hour_from < 0.0 or rec.hour_to > 24.0:
                raise ValidationError(_("Slot hours must be within 0.0 and 24.0."))
            if rec.hour_to <= rec.hour_from:
                raise ValidationError(_("End hour must be greater than start hour."))

    @api.constrains("capacity", "duration_minutes", "buffer_before_minutes", "buffer_after_minutes")
    def _check_positive_values(self):
        for rec in self:
            if rec.capacity < 1:
                raise ValidationError(_("Capacity must be at least 1."))
            if rec.duration_minutes <= 0:
                raise ValidationError(_("Default Duration must be greater than 0 minutes."))
            if rec.buffer_before_minutes < 0 or rec.buffer_after_minutes < 0:
                raise ValidationError(_("Buffer values must not be negative."))

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_("Effective Until date cannot be earlier than Effective From date."))

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _domain_bookings(self):
        return [("slot_id", "=", self.id), ("active", "=", True)]

    def _compute_bookings_count(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            rec.bookings_count = Booking.search_count(rec._domain_bookings())

    def _compute_last_booking(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            last = Booking.search([("slot_id", "=", rec.id)], order="create_date desc, id desc", limit=1)
            rec.last_booking_id = last.id if last else False

    # -------------------------------------------------------------------------
    # NAME / DISPLAY
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        weekday_map = dict(self._fields["weekday"].selection)
        for rec in self:
            w = weekday_map.get(rec.weekday, rec.weekday)
            hh_from = self._float_hour_to_str(rec.hour_from)
            hh_to = self._float_hour_to_str(rec.hour_to)
            label = f"{rec.name} [{w} {hh_from}-{hh_to}]"
            if rec.company_id and self.env.companies and len(self.env.companies) > 1:
                label = f"{label} - {rec.company_id.name}"
            res.append((rec.id, label))
        return res

    # -------------------------------------------------------------------------
    # HELPERS: Time & Occurrence
    # -------------------------------------------------------------------------
    def _float_hour_to_str(self, value):
        """Convert 13.5 -> '13:30'"""
        hours = int(value or 0.0)
        minutes = int(round(((value or 0.0) - hours) * 60.0))
        return f"{hours:02d}:{minutes:02d}"

    def _make_datetime(self, any_date, hour_float):
        """Combine a date and float hour to a naive datetime (server TZ handling is delegated to Odoo)."""
        h = int(hour_float)
        m = int(round((hour_float - h) * 60.0))
        return datetime.combine(any_date, dt_time(hour=h, minute=m))

    def _is_effective_on(self, date_obj):
        """Return True if the slot is effective on this date according to weekday and date range."""
        if str(date_obj.weekday()) != (self.weekday or "0"):
            return False
        if self.date_start and date_obj < self.date_start:
            return False
        if self.date_end and date_obj > self.date_end:
            return False
        # Exceptions
        if self._is_exception_on(date_obj):
            return False
        return True

    def _is_exception_on(self, date_obj):
        ExceptionModel = self.env["booking.slot.exception"]
        count = ExceptionModel.search_count([
            ("slot_id", "=", self.id),
            ("date", "=", date_obj),
            ("active", "=", True),
        ])
        return bool(count)

    def iter_occurrences(self, date_from, date_to):
        """
        Yield (start_dt, end_dt) naive datetimes for each day within [date_from, date_to]
        where the slot is effective. This is a lightweight generator; heavy RRULE logic
        is intentionally left to 'booking.recurring.rule' if present.
        """
        self.ensure_one()
        if not date_from or not date_to or date_to < date_from:
            return
        cursor = date_from
        while cursor <= date_to:
            if self._is_effective_on(cursor):
                start_dt = self._make_datetime(cursor, self.hour_from)
                end_dt = self._make_datetime(cursor, self.hour_to)
                yield (start_dt, end_dt)
            cursor += timedelta(days=1)

    # -------------------------------------------------------------------------
    # AVAILABILITY: Doctor / Room / Resources / Capacity
    # -------------------------------------------------------------------------
    def is_bookable_window(self, start_dt, end_dt, ignore_booking_id=None):
        """
        Return (bool, reason) if the slot can accept a booking for [start_dt, end_dt].
        This checks:
          - the window falls inside slot's allowed hours on that day
          - slot still effective (date range and exceptions)
          - room availability (if provided)
          - doctor availability (if provided)
          - resources availability (if provided)
          - capacity overlap for existing bookings with this slot
        """
        self.ensure_one()
        if not start_dt or not end_dt or end_dt <= start_dt:
            return (False, _("Invalid start/end time."))

        date_obj = (fields.Datetime.from_string(start_dt) if isinstance(start_dt, str) else start_dt).date()
        if not self._is_effective_on(date_obj):
            return (False, _("Slot is not effective on this date."))

        # Inside slot hours?
        start_h = (start_dt.hour + start_dt.minute / 60.0) if isinstance(start_dt, datetime) else fields.Datetime.from_string(start_dt).hour
        end_h = (end_dt.hour + end_dt.minute / 60.0) if isinstance(end_dt, datetime) else fields.Datetime.from_string(end_dt).hour
        if not (start_h >= self.hour_from and end_h <= self.hour_to):
            return (False, _("Requested time is outside slot hours."))

        # Room availability
        if self.room_id:
            ok = self.room_id.is_available(
                start_dt, end_dt, ignore_booking_id=ignore_booking_id, consider_capacity=True
            )
            if not ok:
                return (False, _("Room is not available for the requested time."))

        # Doctor availability (search overlaps in booking.booking)
        if self.doctor_id:
            if self._doctor_overlaps(start_dt, end_dt, ignore_booking_id=ignore_booking_id):
                return (False, _("Doctor is not available for the requested time."))

        # Resources availability
        for res in self.resource_ids:
            ok = res.is_available(
                start_dt, end_dt, ignore_booking_id=ignore_booking_id, required_units=1, consider_capacity=True
            )
            if not ok:
                return (False, _("A required resource is not available."))

        # Capacity at slot level (other bookings linked to the same slot)
        overlaps = self._count_overlapping_bookings(start_dt, end_dt, ignore_booking_id=ignore_booking_id)
        if overlaps >= max(1, self.capacity or 1):
            return (False, _("Slot capacity has been reached for the requested time."))

        return (True, _("Available."))

    # Doctor overlap (confirmed/in_progress)
    def _doctor_overlaps(self, start_dt, end_dt, ignore_booking_id=None):
        if not self.doctor_id:
            return False
        Booking = self.env["booking.booking"]
        domain = [
            ("doctor_id", "=", self.doctor_id.id),
            ("state", "in", ["confirmed", "in_progress"]),
            ("start_datetime", "<", fields.Datetime.to_string(end_dt)),
            ("end_datetime", ">", fields.Datetime.to_string(start_dt)),
        ]
        if ignore_booking_id:
            domain.append(("id", "!=", ignore_booking_id))
        return bool(Booking.search_count(domain))

    def _count_overlapping_bookings(self, start_dt, end_dt, ignore_booking_id=None):
        Booking = self.env["booking.booking"]
        domain = [
            ("slot_id", "=", self.id),
            ("state", "in", ["confirmed", "in_progress"]),
            ("start_datetime", "<", fields.Datetime.to_string(end_dt)),
            ("end_datetime", ">", fields.Datetime.to_string(start_dt)),
        ]
        if ignore_booking_id:
            domain.append(("id", "!=", ignore_booking_id))
        return Booking.search_count(domain)

    # -------------------------------------------------------------------------
    # APPLY DEFAULTS TO BOOKING
    # -------------------------------------------------------------------------
    def apply_defaults_to_booking_vals(self, vals=None, start_dt=None, end_dt=None):
        """
        Return a dict of booking values prefilled from this slot.
        Caller can merge with manual input before create().
        """
        self.ensure_one()
        vals = dict(vals or {})
        if "slot_id" not in vals:
            vals["slot_id"] = self.id

        # Parties and context
        if self.doctor_id and not vals.get("doctor_id"):
            vals["doctor_id"] = self.doctor_id.id
        if self.room_id and not vals.get("room_id"):
            vals["room_id"] = self.room_id.id
        if self.treatment_id and not vals.get("treatment_id"):
            vals["treatment_id"] = self.treatment_id.id
        if self.channel_id and not vals.get("channel_id"):
            vals["channel_id"] = self.channel_id.id
        if self.policy_id and not vals.get("policy_id"):
            vals["policy_id"] = self.policy_id.id

        # Resources
        if self.resource_ids and not vals.get("resource_ids"):
            vals["resource_ids"] = [(6, 0, self.resource_ids.ids)]

        # Timing
        if start_dt and not vals.get("start_datetime"):
            vals["start_datetime"] = fields.Datetime.to_string(start_dt)
        if end_dt and not vals.get("end_datetime"):
            vals["end_datetime"] = fields.Datetime.to_string(end_dt)

        # Buffers: copy down only if target model has those fields later; otherwise ignored
        # (we keep them in slot; booking uses room/resource buffers at availability time)

        return vals

    # -------------------------------------------------------------------------
    # ACTIONS (Open related bookings / Create from slot)
    # -------------------------------------------------------------------------
    def action_view_bookings(self):
        self.ensure_one()
        action = {
            "name": _("Bookings"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "list,form,calendar,kanban,activity,pivot,graph",
            "domain": [("slot_id", "=", self.id)],
            "context": {"default_slot_id": self.id},
        }
        act_ref = self.env.ref("clinic_booking.action_booking_list", raise_if_not_found=False)
        if act_ref:
            data = act_ref.read()[0]
            data.update(action)
            return data
        return action

    def action_new_booking(self):
        """Open a new booking form prefilled with slot defaults and next occurrence time if available."""
        self.ensure_one()
        default_start, default_end = self._suggest_next_window()
        ctx = {
            "default_slot_id": self.id,
            "default_doctor_id": self.doctor_id.id if self.doctor_id else False,
            "default_room_id": self.room_id.id if self.room_id else False,
            "default_treatment_id": self.treatment_id.id if self.treatment_id else False,
            "default_channel_id": self.channel_id.id if self.channel_id else False,
            "default_policy_id": self.policy_id.id if self.policy_id else False,
        }
        if default_start and default_end:
            ctx.update({
                "default_start_datetime": fields.Datetime.to_string(default_start),
                "default_end_datetime": fields.Datetime.to_string(default_end),
            })
        return {
            "name": _("New Booking"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "form",
            "context": ctx,
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # SUGGESTION ENGINE
    # -------------------------------------------------------------------------
    def _suggest_next_window(self):
        """
        Suggest the next available [start, end] for this slot on or after today.
        We check today first; if not effective, we advance to the next matching weekday
        within the date range and test room/doctor/resources/capacity.
        """
        self.ensure_one()
        now = fields.Date.context_today(self)
        search_days = 21  # look ahead up to 3 weeks
        for i in range(search_days):
            day = now + timedelta(days=i)
            if not self._is_effective_on(day):
                continue
            start_dt = self._make_datetime(day, self.hour_from)
            # Use default duration when proposing a single booking window
            duration = timedelta(minutes=max(1, self.duration_minutes or 1))
            end_dt = start_dt + duration
            ok, _reason = self.is_bookable_window(start_dt, end_dt, ignore_booking_id=None)
            if ok:
                return (start_dt, end_dt)
        return (None, None)


# -----------------------------------------------------------------------------
# booking.slot.exception (per-date disable/modify)
# -----------------------------------------------------------------------------
class BookingSlotException(models.Model):
    _name = "booking.slot.exception"
    _description = "Booking Slot Exception"
    _order = "date, id"

    slot_id = fields.Many2one(
        "booking.slot",
        string="Slot",
        required=True,
        index=True,
        ondelete="cascade",
        help="Slot to which this exception applies.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="slot_id.company_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Disable to ignore this exception without deleting.",
    )

    date = fields.Date(
        string="Date",
        required=True,
        help="Date of the exception (slot is disabled or altered on this date).",
    )
    is_disabled = fields.Boolean(
        string="Disable Slot on Date",
        default=True,
        help="If enabled, the slot is disabled for the given date.",
    )
    # Optional hour override (if slot partially available on that date)
    hour_override_from = fields.Float(
        string="From (hour override)",
        help="Optional start time override (0.0 - 24.0) for this date only.",
    )
    hour_override_to = fields.Float(
        string="To (hour override)",
        help="Optional end time override (0.0 - 24.0) for this date only.",
    )
    capacity_override = fields.Integer(
        string="Capacity Override",
        help="Optional capacity override for this date only.",
    )
    note = fields.Char(
        string="Note",
        help="Optional note (e.g., 'Doctor in training', 'Room maintenance').",
    )

    @api.constrains("hour_override_from", "hour_override_to")
    def _check_hours(self):
        for rec in self:
            if rec.hour_override_from is not None:
                if rec.hour_override_from < 0.0 or rec.hour_override_from > 24.0:
                    raise ValidationError(_("Override hours must be between 0.0 and 24.0."))
            if rec.hour_override_to is not None:
                if rec.hour_override_to < 0.0 or rec.hour_override_to > 24.0:
                    raise ValidationError(_("Override hours must be between 0.0 and 24.0."))
            if rec.hour_override_from is not None and rec.hour_override_to is not None:
                if rec.hour_override_to <= rec.hour_override_from:
                    raise ValidationError(_("Override end hour must be greater than start hour."))

    @api.constrains("capacity_override")
    def _check_capacity(self):
        for rec in self:
            if rec.capacity_override is not None and rec.capacity_override < 1:
                raise ValidationError(_("Capacity Override must be at least 1."))

    # Future extension: method to return effective window/capacity for the date,
    # merging slot defaults with overrides. For now, slot uses simple 'disabled' check.


# -----------------------------------------------------------------------------
# OPTIONAL MIXIN (for other records that want to reference a slot)
# -----------------------------------------------------------------------------
class BookingSlotMixin(models.AbstractModel):
    _name = "booking.slot.mixin"
    _description = "Booking Slot Mixin"

    slot_id = fields.Many2one(
        "booking.slot",
        string="Slot",
        index=True,
        help="Slot associated with this record.",
    )

    @api.onchange("slot_id")
    def _onchange_slot_id(self):
        """Inheriting models (e.g., booking) can override or consume slot defaults."""
        # Example: for booking.booking we will fill defaults in form view onchange via RPC.
        return

# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/clinic_doctor_inherit.py
#
# Purpose
# -------
# Extend clinic.doctor with booking-oriented capabilities:
# - Doctor-level weekly schedules & blackout windows (optional to use)
# - Availability checks that consider bookings, (optional) appointments, schedules, and blackouts
# - Buffers (handover/cleanup) and convenience defaults (preferred room/resources/channel/policy)
# - Quick stats (counts, last booking, next available, busy now) and actions
#
# Integrations (soft-coupled)
# ---------------------------
# - booking.booking           (doctor_id overlap checks)
# - clinic.appointment        (optional overlap check if the module provides it)
# - booking.room / resource   (defaults/compatibility)
# - booking.channel / policy  (defaults)
# - booking.slot              (indirect; slot checks doctor availability)
#
# Notes
# -----
# - All user-facing strings are in English.
# - We DO NOT redefine fields that may exist in clinic_doctor (e.g., allowed_treatment_ids).
#   Booking code guards with hasattr(...) as needed.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta, time as dt_time


# =============================================================================
# Inherit clinic.doctor
# =============================================================================
class ClinicDoctor(models.Model):
    _inherit = "clinic.doctor"

    # -------------------------------------------------------------------------
    # Booking defaults & preferences (safe, non-conflicting names)
    # -------------------------------------------------------------------------
    booking_default_channel_id = fields.Many2one(
        "booking.channel",
        string="Default Booking Channel",
        help="Channel suggested when creating a booking for this doctor.",
        tracking=True,
    )
    booking_default_policy_id = fields.Many2one(
        "booking.policy",
        string="Default Booking Policy",
        help="Policy suggested when creating a booking for this doctor.",
        tracking=True,
    )
    booking_default_room_ids = fields.Many2many(
        "booking.room",
        "doctor_booking_room_rel",
        "doctor_id",
        "room_id",
        string="Preferred Rooms",
        help="Rooms commonly used by this doctor (for suggestions and filtering).",
    )
    booking_default_resource_ids = fields.Many2many(
        "booking.resource",
        "doctor_booking_resource_rel",
        "doctor_id",
        "resource_id",
        string="Preferred Resources",
        help="Devices/tools commonly needed by this doctor.",
    )

    # Buffers at the doctor level (handover/prep/cleanup)
    buffer_before_minutes = fields.Integer(
        string="Buffer Before (min)",
        default=0,
        help="Minimum minutes reserved before the session for preparation.",
        tracking=True,
    )
    buffer_after_minutes = fields.Integer(
        string="Buffer After (min)",
        default=0,
        help="Minimum minutes reserved after the session for handover/notes.",
        tracking=True,
    )

    # Scheduling aids (optional)
    schedule_ids = fields.One2many(
        "booking.doctor.schedule",
        "doctor_id",
        string="Weekly Schedules",
        help="Weekly working hours for this doctor (optional). Leave empty to allow all hours.",
    )
    blackout_ids = fields.One2many(
        "booking.doctor.blackout",
        "doctor_id",
        string="Blackouts",
        help="Ad-hoc closures (leave, meeting, training) when the doctor is not available.",
    )

    # Stats
    bookings_count = fields.Integer(
        string="Bookings",
        compute="_compute_booking_stats",
        help="Number of active bookings assigned to this doctor.",
    )
    last_booking_id = fields.Many2one(
        "booking.booking",
        string="Last Booking",
        compute="_compute_last_and_busy",
        help="Most recently created booking for this doctor.",
    )
    busy_now = fields.Boolean(
        string="Busy Now",
        compute="_compute_last_and_busy",
        help="True if the doctor is currently in a confirmed/in-progress booking.",
    )
    next_available_from = fields.Datetime(
        string="Next Available From",
        compute="_compute_next_available_from",
        help="Approximate next available time based on bookings, schedules, and blackouts.",
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _domain_bookings(self):
        return [
            ("doctor_id", "=", self.id),
            ("state", "in", ["confirmed", "in_progress"]),
            ("active", "=", True),
        ]

    def _compute_booking_stats(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            rec.bookings_count = Booking.search_count(rec._domain_bookings())

    def _compute_last_and_busy(self):
        Booking = self.env["booking.booking"]
        now = fields.Datetime.now()
        for rec in self:
            last = Booking.search([("doctor_id", "=", rec.id)], order="create_date desc, id desc", limit=1)
            rec.last_booking_id = last.id if last else False
            busy = Booking.search_count([
                ("doctor_id", "=", rec.id),
                ("state", "in", ["confirmed", "in_progress"]),
                ("start_datetime", "<=", now),
                ("end_datetime", ">", now),
            ])
            rec.busy_now = bool(busy)

    def _compute_next_available_from(self):
        """Heuristic probing: 15-minute steps up to 14 hours ahead."""
        for rec in self:
            now = fields.Datetime.now()
            # If now is already available, return now
            if rec.is_available(now, now + timedelta(minutes=1)):
                rec.next_available_from = now
                continue

            step = timedelta(minutes=15)
            probe = now
            for _i in range(0, int((14 * 60) / 15)):
                window_end = probe + step
                if rec.is_available(probe, window_end):
                    rec.next_available_from = probe
                    break
                probe = window_end
            else:
                rec.next_available_from = False

    # -------------------------------------------------------------------------
    # NAME / DISPLAY (optional enhancement)
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            label = super(ClinicDoctor, rec).name_get()[0][1] if hasattr(super(), "name_get") else (rec.name or _("Doctor"))
            # Add company suffix in multi-company contexts for clarity
            if rec.company_id and self.env.companies and len(self.env.companies) > 1:
                label = f"{label} - {rec.company_id.name}"
            res.append((rec.id, label))
        return res

    # -------------------------------------------------------------------------
    # AVAILABILITY
    # -------------------------------------------------------------------------
    def is_available(self, start_dt, end_dt, ignore_booking_id=None, check_appointments=True):
        """
        Check if the doctor is available between start_dt and end_dt, considering:
        - Doctor buffers (before/after)
        - Doctor blackouts
        - Doctor weekly schedules (if defined)
        - Overlapping bookings (confirmed/in_progress)
        - (Optional) Overlapping clinic.appointment (if model exists)
        """
        self.ensure_one()
        if not start_dt or not end_dt:
            return False

        # Normalize
        start = fields.Datetime.from_string(start_dt) if isinstance(start_dt, str) else start_dt
        end = fields.Datetime.from_string(end_dt) if isinstance(end_dt, str) else end_dt
        if end <= start:
            return False

        # Apply buffers
        start_with_buffer = start - timedelta(minutes=self.buffer_before_minutes or 0)
        end_with_buffer = end + timedelta(minutes=self.buffer_after_minutes or 0)

        # Blackouts
        if self._overlaps_blackout(start_with_buffer, end_with_buffer):
            return False

        # Weekly schedules
        if not self._fits_weekly_schedule(start_with_buffer, end_with_buffer):
            return False

        # Bookings overlap
        if self._has_overlapping_booking(start_with_buffer, end_with_buffer, ignore_booking_id=ignore_booking_id):
            return False

        # Appointments overlap (soft-coupled; only if model exists and check_appointments=True)
        if check_appointments and "clinic.appointment" in self.env:
            if self._has_overlapping_appointment(start_with_buffer, end_with_buffer):
                return False

        return True

    def _overlaps_blackout(self, start, end):
        Blackout = self.env["booking.doctor.blackout"]
        return bool(Blackout.search_count([
            ("doctor_id", "=", self.id),
            ("active", "=", True),
            ("start_datetime", "<", end),
            ("end_datetime", ">", start),
        ]))

    def _fits_weekly_schedule(self, start, end):
        """
        If schedules are defined, each day segment must be fully inside at least
        one schedule window for that weekday. If no schedules → allow all hours.
        """
        schedules = self.schedule_ids.filtered(lambda s: s.active)
        if not schedules:
            return True

        cursor = start
        while cursor < end:
            # Day segment
            day_end = datetime.combine(cursor.date(), dt_time.max).replace(microsecond=0)
            segment_end = min(end, day_end)

            weekday = str(cursor.weekday())  # '0'..'6'
            start_hours = cursor.hour + cursor.minute / 60.0
            end_hours = segment_end.hour + segment_end.minute / 60.0

            day_schedules = schedules.filtered(lambda s: s.weekday == weekday)
            fits = any((start_hours >= s.hour_from and end_hours <= s.hour_to) for s in day_schedules)
            if not fits:
                return False

            cursor = segment_end + timedelta(seconds=1)
        return True

    def _has_overlapping_booking(self, start, end, ignore_booking_id=None):
        Booking = self.env["booking.booking"]
        domain = [
            ("doctor_id", "=", self.id),
            ("state", "in", ["confirmed", "in_progress"]),
            ("start_datetime", "<", fields.Datetime.to_string(end)),
            ("end_datetime", ">", fields.Datetime.to_string(start)),
        ]
        if ignore_booking_id:
            domain.append(("id", "!=", ignore_booking_id))
        return bool(Booking.search_count(domain))

    def _has_overlapping_appointment(self, start, end):
        # Soft: only if clinic.appointment exists and has these fields
        if "clinic.appointment" not in self.env:
            return False
        Appointment = self.env["clinic.appointment"]
        domain = [
            ("doctor_id", "=", self.id),
            ("start_datetime", "<", fields.Datetime.to_string(end)),
            ("end_datetime", ">", fields.Datetime.to_string(start)),
            ("active", "=", True),
        ]
        return bool(Appointment.search_count(domain))

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_view_bookings(self):
        self.ensure_one()
        action = {
            "name": _("Bookings"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "list,form,calendar,kanban,activity,pivot,graph",
            "domain": [("doctor_id", "=", self.id)],
            "context": {
                "default_doctor_id": self.id,
                "default_channel_id": self.booking_default_channel_id.id if self.booking_default_channel_id else False,
                "default_policy_id": self.booking_default_policy_id.id if self.booking_default_policy_id else False,
                "default_room_id": self.booking_default_room_ids[:1].id if self.booking_default_room_ids else False,
                "default_resource_ids": [(6, 0, self.booking_default_resource_ids.ids)] if self.booking_default_resource_ids else False,
            },
        }
        act_ref = self.env.ref("clinic_booking.action_booking_list", raise_if_not_found=False)
        if act_ref:
            data = act_ref.read()[0]
            data.update(action)
            return data
        return action

    def action_new_booking(self):
        self.ensure_one()
        return {
            "name": _("New Booking"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "form",
            "context": {
                "default_doctor_id": self.id,
                "default_channel_id": self.booking_default_channel_id.id if self.booking_default_channel_id else False,
                "default_policy_id": self.booking_default_policy_id.id if self.booking_default_policy_id else False,
                "default_room_id": self.booking_default_room_ids[:1].id if self.booking_default_room_ids else False,
                "default_resource_ids": [(6, 0, self.booking_default_resource_ids.ids)] if self.booking_default_resource_ids else False,
            },
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("buffer_before_minutes", "buffer_after_minutes")
    def _check_buffers(self):
        for rec in self:
            if rec.buffer_before_minutes is not None and rec.buffer_before_minutes < 0:
                raise ValidationError(_("Buffer Before must be 0 or a positive number."))
            if rec.buffer_after_minutes is not None and rec.buffer_after_minutes < 0:
                raise ValidationError(_("Buffer After must be 0 or a positive number."))


# =============================================================================
# booking.doctor.schedule — Weekly schedules for doctor availability
# =============================================================================
class BookingDoctorSchedule(models.Model):
    _name = "booking.doctor.schedule"
    _description = "Booking Doctor Weekly Schedule"
    _order = "doctor_id, weekday, hour_from"

    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        required=True,
        ondelete="cascade",
        index=True,
        help="Doctor to which this schedule applies.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="doctor_id.company_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Disable to temporarily ignore this schedule window.",
    )

    weekday = fields.Selection(
        selection=[
            ("0", "Monday"), ("1", "Tuesday"), ("2", "Wednesday"),
            ("3", "Thursday"), ("4", "Friday"), ("5", "Saturday"), ("6", "Sunday"),
        ],
        string="Weekday",
        required=True,
        default="0",
        help="Day of the week when this schedule applies.",
    )
    hour_from = fields.Float(
        string="From (hour)",
        required=True,
        default=9.0,
        help="Start time (0.0 - 24.0). Example: 9.0 = 09:00.",
    )
    hour_to = fields.Float(
        string="To (hour)",
        required=True,
        default=17.0,
        help="End time (0.0 - 24.0). Example: 17.0 = 17:00.",
    )
    note = fields.Char(
        string="Note",
        help="Optional note (e.g., 'AM clinic', 'Telemedicine only').",
    )

    @api.constrains("hour_from", "hour_to")
    def _check_hours(self):
        for rec in self:
            if rec.hour_from < 0.0 or rec.hour_to > 24.0:
                raise ValidationError(_("Schedule hours must be within 0.0 and 24.0."))
            if rec.hour_to <= rec.hour_from:
                raise ValidationError(_("End hour must be greater than start hour."))


# =============================================================================
# booking.doctor.blackout — Ad-hoc closures for doctor availability
# =============================================================================
class BookingDoctorBlackout(models.Model):
    _name = "booking.doctor.blackout"
    _description = "Booking Doctor Blackout"
    _order = "start_datetime desc"

    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        required=True,
        ondelete="cascade",
        index=True,
        help="Doctor that is not available during this blackout window.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="doctor_id.company_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Disable to ignore this blackout without deleting it.",
    )

    start_datetime = fields.Datetime(
        string="Start",
        required=True,
        help="Start datetime of the blackout window.",
    )
    end_datetime = fields.Datetime(
        string="End",
        required=True,
        help="End datetime of the blackout window.",
    )
    reason = fields.Char(
        string="Reason",
        help="Short reason for the blackout (e.g., 'Leave', 'Training', 'Conference').",
    )
    internal_notes = fields.Text(
        string="Internal Notes",
        help="Additional notes for staff about this blackout.",
    )

    @api.constrains("start_datetime", "end_datetime")
    def _check_range(self):
        for rec in self:
            if rec.start_datetime and rec.end_datetime and rec.end_datetime <= rec.start_datetime:
                raise ValidationError(_("End time must be greater than start time."))

    def action_view_conflicting_bookings(self):
        self.ensure_one()
        action = {
            "name": _("Conflicting Bookings"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "list,form,calendar,kanban,activity",
            "domain": [
                ("doctor_id", "=", self.doctor_id.id),
                ("state", "in", ["confirmed", "in_progress"]),
                ("start_datetime", "<", self.end_datetime),
                ("end_datetime", ">", self.start_datetime),
            ],
        }
        act_ref = self.env.ref("clinic_booking.action_booking_list", raise_if_not_found=False)
        if act_ref:
            data = act_ref.read()[0]
            data.update(action)
            return data
        return action

# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/res_partner_inherit.py
#
# Purpose
# -------
# Extend res.partner (Patient/Customer) with booking-centric fields:
# - Preferences (doctor, treatment, channel, policy, reminders)
# - Quick statistics (counts, last/next booking, no-shows, cancellations)
# - Actions to view/create bookings with sensible defaults
# - Feedback summary (average rating from submitted feedback)
#
# Integrations (soft-coupled)
# ---------------------------
# - booking.booking (patient_id link)
# - booking.room / booking.resource (indirect through bookings)
# - booking.channel / booking.policy (defaults)
# - clinic.doctor / clinic.treatment (preferences & validations)
# - booking.feedback.link (feedback analytics)
#
# Notes
# -----
# - All user-facing strings are in English.
# - The model works even if some sibling modules are not installed; all cross-
#   model access is guarded to avoid hard crashes.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta


class ResPartner(models.Model):
    _inherit = "res.partner"

    # -------------------------------------------------------------------------
    # BOOKING RELATION / QUICK ACCESS
    # -------------------------------------------------------------------------
    booking_ids = fields.One2many(
        "booking.booking",
        "patient_id",
        string="Bookings",
        help="All bookings related to this patient.",
    )
    booking_count = fields.Integer(
        string="Bookings",
        compute="_compute_booking_stats",
        help="Total number of bookings for this patient.",
    )
    booking_confirmed_count = fields.Integer(
        string="Confirmed/In Progress",
        compute="_compute_booking_stats",
        help="Number of active (confirmed or in-progress) bookings.",
    )
    booking_done_count = fields.Integer(
        string="Completed",
        compute="_compute_booking_stats",
        help="Number of completed bookings.",
    )
    booking_cancel_count = fields.Integer(
        string="Cancelled",
        compute="_compute_booking_stats",
        help="Number of cancelled bookings.",
    )
    booking_noshow_count = fields.Integer(
        string="No-shows",
        compute="_compute_booking_stats",
        help="Number of bookings marked as no-show.",
    )

    last_booking_id = fields.Many2one(
        "booking.booking",
        string="Last Booking",
        compute="_compute_last_next_booking",
        help="Most recent booking in the past.",
    )
    next_booking_id = fields.Many2one(
        "booking.booking",
        string="Next Booking",
        compute="_compute_last_next_booking",
        help="Nearest upcoming booking.",
    )
    next_booking_start = fields.Datetime(
        string="Next Booking Start",
        compute="_compute_last_next_booking",
        help="Start time of the next booking.",
    )

    # -------------------------------------------------------------------------
    # PREFERENCES / DEFAULTS
    # -------------------------------------------------------------------------
    preferred_doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Preferred Doctor",
        help="Doctor preferred by the patient for new bookings.",
        tracking=True,
    )
    preferred_treatment_ids = fields.Many2many(
        "clinic.treatment",
        "partner_preferred_treatment_rel",
        "partner_id",
        "treatment_id",
        string="Preferred Treatments",
        help="Treatments commonly requested by the patient.",
        tracking=True,
    )
    preferred_channel_id = fields.Many2one(
        "booking.channel",
        string="Preferred Channel",
        help="Default booking channel used when creating a new booking for this patient.",
        tracking=True,
    )
    preferred_policy_id = fields.Many2one(
        "booking.policy",
        string="Preferred Policy",
        help="Default booking policy applied when creating a new booking for this patient.",
        tracking=True,
    )

    booking_reminder_method = fields.Selection(
        selection=[
            ("none", "None"),
            ("email", "Email"),
            ("sms", "SMS (if available)"),
            ("email_sms", "Email + SMS"),
        ],
        string="Reminder Method",
        default="email",
        help="Preferred reminder method for upcoming bookings. SMS requires an SMS module.",
        tracking=True,
    )
    booking_reminder_hours_before = fields.Float(
        string="Reminder Hours Before",
        default=24.0,
        help="How many hours before the start time a reminder should be sent (informational).",
        tracking=True,
    )
    allow_portal_booking = fields.Boolean(
        string="Allow Portal Booking",
        default=True,
        help="If enabled, the patient can create/manage bookings from the portal (subject to access).",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # FEEDBACK SUMMARY
    # -------------------------------------------------------------------------
    feedback_count = fields.Integer(
        string="Feedback Entries",
        compute="_compute_feedback_stats",
        help="Number of submitted feedback entries from this patient.",
    )
    feedback_avg_rating = fields.Float(
        string="Average Rating",
        compute="_compute_feedback_stats",
        help="Average 1..5 rating from submitted feedback links.",
        digits=(16, 2),
    )

    # -------------------------------------------------------------------------
    # COMPUTES — BOOKING STATS
    # -------------------------------------------------------------------------
    def _booking_domain_base(self):
        self.ensure_one()
        return [("patient_id", "=", self.id), ("active", "=", True)]

    def _compute_booking_stats(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            base = rec._booking_domain_base()
            rec.booking_count = Booking.search_count(base)
            rec.booking_confirmed_count = Booking.search_count(base + [("state", "in", ["confirmed", "in_progress"])])
            rec.booking_done_count = Booking.search_count(base + [("state", "=", "done")])
            rec.booking_cancel_count = Booking.search_count(base + [("state", "=", "cancelled")])
            rec.booking_noshow_count = Booking.search_count(base + [("is_no_show", "=", True)])

    def _compute_last_next_booking(self):
        Booking = self.env["booking.booking"]
        now = fields.Datetime.now()
        for rec in self:
            base = rec._booking_domain_base()
            # Last booking (past, not cancelled)
            last = Booking.search(
                base + [("start_datetime", "<", now), ("state", "!=", "cancelled")],
                order="start_datetime desc, id desc",
                limit=1,
            )
            # Next booking (future, not cancelled)
            nxt = Booking.search(
                base + [("start_datetime", ">=", now), ("state", "!=", "cancelled")],
                order="start_datetime asc, id asc",
                limit=1,
            )
            rec.last_booking_id = last.id if last else False
            rec.next_booking_id = nxt.id if nxt else False
            rec.next_booking_start = nxt.start_datetime if nxt else False

    # -------------------------------------------------------------------------
    # COMPUTES — FEEDBACK STATS
    # -------------------------------------------------------------------------
    def _compute_feedback_stats(self):
        Feedback = self.env["booking.feedback.link"]
        for rec in self:
            links = Feedback.search([("patient_id", "=", rec.id), ("state", "=", "submitted")])
            rec.feedback_count = len(links)
            if links:
                # rating_value stored as selection of strings '1'..'5'
                ratings = []
                for l in links:
                    try:
                        ratings.append(float(l.rating_value or 0))
                    except Exception:
                        pass
                rec.feedback_avg_rating = (sum(ratings) / len(ratings)) if ratings else 0.0
            else:
                rec.feedback_avg_rating = 0.0

    # -------------------------------------------------------------------------
    # ONCHANGE — CHAINED DEFAULTS
    # -------------------------------------------------------------------------
    @api.onchange("preferred_channel_id")
    def _onchange_preferred_channel_id(self):
        """
        If the selected channel has a default policy/template, use them as hints.
        """
        for rec in self:
            ch = rec.preferred_channel_id
            if not ch:
                continue
            # If channel defines default policy, adopt it (do not overwrite if already set)
            if hasattr(ch, "default_policy_id") and ch.default_policy_id and not rec.preferred_policy_id:
                rec.preferred_policy_id = ch.default_policy_id.id

    @api.onchange("preferred_doctor_id")
    def _onchange_preferred_doctor_id(self):
        """
        Optionally clean preferred treatments to those allowed by the doctor (if configured).
        """
        for rec in self:
            doc = rec.preferred_doctor_id
            if not doc:
                continue
            if hasattr(doc, "allowed_treatment_ids") and doc.allowed_treatment_ids and rec.preferred_treatment_ids:
                rec.preferred_treatment_ids = rec.preferred_treatment_ids.filtered(
                    lambda t: t in doc.allowed_treatment_ids
                )

    # -------------------------------------------------------------------------
    # CONSTRAINTS — PREFERENCES VALIDATION
    # -------------------------------------------------------------------------
    @api.constrains("preferred_doctor_id", "preferred_treatment_ids")
    def _check_preferred_pairs(self):
        """
        If doctor has an 'allowed_treatment_ids' policy, ensure preferred treatments don't violate it.
        """
        for rec in self:
            doc = rec.preferred_doctor_id
            if not doc or not hasattr(doc, "allowed_treatment_ids"):
                continue
            allowed = doc.allowed_treatment_ids
            if allowed and any(t not in allowed for t in rec.preferred_treatment_ids):
                raise ValidationError(_("Some preferred treatments are not allowed for the selected doctor."))

    @api.constrains("booking_reminder_hours_before")
    def _check_reminder_hours(self):
        for rec in self:
            if rec.booking_reminder_hours_before is not None and rec.booking_reminder_hours_before < 0.0:
                raise ValidationError(_("Reminder Hours Before must be 0 or a positive number."))

    # -------------------------------------------------------------------------
    # ACTIONS — NAVIGATION
    # -------------------------------------------------------------------------
    def action_view_bookings(self):
        """
        Open bookings list filtered to this patient.
        """
        self.ensure_one()
        action = {
            "name": _("Bookings"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "list,form,calendar,kanban,activity,pivot,graph",
            "domain": [("patient_id", "=", self.id)],
            "context": {"default_patient_id": self.id},
        }
        act_ref = self.env.ref("clinic_booking.action_booking_list", raise_if_not_found=False)
        if act_ref:
            data = act_ref.read()[0]
            data.update(action)
            return data
        return action

    def action_view_next_booking(self):
        """
        Open the next upcoming booking (if any).
        """
        self.ensure_one()
        if not self.next_booking_id:
            raise UserError(_("There is no upcoming booking for this patient."))
        return {
            "name": _("Next Booking"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "form",
            "res_id": self.next_booking_id.id,
            "target": "current",
        }

    def action_view_last_booking(self):
        """
        Open the latest past booking (if any).
        """
        self.ensure_one()
        if not self.last_booking_id:
            raise UserError(_("There is no past booking for this patient."))
        return {
            "name": _("Last Booking"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "form",
            "res_id": self.last_booking_id.id,
            "target": "current",
        }

    def action_new_booking(self):
        """
        Start a new booking form with patient & preferences pre-filled.
        """
        self.ensure_one()
        ctx = self._prepare_default_booking_context()
        return {
            "name": _("New Booking"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "form",
            "context": ctx,
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # HELPERS — DEFAULT CONTEXT/VALS FOR NEW BOOKING
    # -------------------------------------------------------------------------
    def _prepare_default_booking_context(self):
        """
        Prepare default context for creating a new booking from this partner.
        """
        self.ensure_one()
        ctx = {
            "default_patient_id": self.id,
            "default_channel_id": self.preferred_channel_id.id if self.preferred_channel_id else False,
            "default_policy_id": self.preferred_policy_id.id if self.preferred_policy_id else False,
            "default_doctor_id": self.preferred_doctor_id.id if self.preferred_doctor_id else False,
        }
        # Default treatment: if only one preferred, prefill
        if len(self.preferred_treatment_ids) == 1:
            ctx["default_treatment_id"] = self.preferred_treatment_ids.id
        # If the channel has 'apply_defaults_to_booking' mixin methods, they'll run on onchange in booking form
        return ctx

    # -------------------------------------------------------------------------
    # UTILITIES — COMMUNICATION
    # -------------------------------------------------------------------------
    def action_send_next_booking_reminder(self):
        """
        Minimal example: post a message to chatter with next booking time.
        Real email/SMS reminders should be implemented in a dedicated scheduler.
        """
        for rec in self:
            if not rec.next_booking_id:
                raise UserError(_("No upcoming booking to remind."))
            nb = rec.next_booking_id
            rec.message_post(
                body=_(
                    "Reminder — Next booking: <b>%s</b> with <b>%s</b> on <b>%s</b>."
                )
                % (
                    nb.name or _("Booking"),
                    (nb.doctor_id and nb.doctor_id.display_name) or _("(no doctor)"),
                    fields.Datetime.to_string(nb.start_datetime),
                )
            )

    # -------------------------------------------------------------------------
    # SMART BUTTON HELPERS (optional in views)
    # -------------------------------------------------------------------------
    def _get_smart_button_label(self):
        """
        Optional helper if you want to compute a smart button label dynamically.
        """
        self.ensure_one()
        if self.next_booking_id:
            return _("Next: %s") % (fields.Datetime.to_string(self.next_booking_id.start_datetime),)
        return _("Bookings")

# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/stock_move_inherit.py
#
# Purpose
# -------
# Make Inventory (Stock) aware of Bookings:
# - Link stock moves & pickings with booking and booking lines
# - Provide helpers to load consumption moves from booking and resources
# - Keep company/partner consistency with booking patient/company
# - Post informative chatter messages on Booking when pickings are validated
#
# Integrations (soft-coupled)
# ---------------------------
# - booking.booking / booking.line  : primary linkage
# - booking.resource                : optional, line/resource-level consumption helpers
# - clinic.treatment / clinic.doctor: related shortcuts for reporting
#
# Notes
# -----
# - This file assumes 'stock' is available (declared in module depends).
# - All user-facing strings are in English.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


# =============================================================================
# stock.move — Inherit
# =============================================================================
class StockMove(models.Model):
    _inherit = "stock.move"

    # -------------------------------------------------------------------------
    # BOOKING LINKS
    # -------------------------------------------------------------------------
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking",
        index=True,
        help="Booking associated with this stock move.",
        copy=False,
    )
    booking_line_id = fields.Many2one(
        "booking.line",
        string="Booking Line",
        index=True,
        help="Booking line associated with this move, if any.",
        copy=False,
    )
    resource_id = fields.Many2one(
        "booking.resource",
        string="Resource",
        help="Resource that triggers this consumption (optional).",
        copy=False,
    )

    # Convenience related fields (for filters/reports)
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="booking_id.patient_id",
        store=True,
        readonly=True,
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        related="booking_id.doctor_id",
        store=True,
        readonly=True,
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        related="booking_id.treatment_id",
        store=True,
        readonly=True,
    )

    # Labeling flag if this move is directly tied to a booking consumption
    is_booking_consumption = fields.Boolean(
        string="Is Booking Consumption",
        help="Enable to mark this move as a consumption generated for a booking.",
        default=False,
    )

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("booking_line_id")
    def _onchange_booking_line_id(self):
        """
        When selecting a booking line, prefill product, uom, quantity, and name.
        """
        for rec in self:
            bl = rec.booking_line_id
            if not bl:
                continue

            rec.booking_id = bl.booking_id.id
            # Product / UoM / Qty
            if bl.product_id:
                rec.product_id = bl.product_id.id
                rec.product_uom = bl.product_uom.id or bl.product_id.uom_id.id
            if bl.product_uom_qty:
                rec.product_uom_qty = bl.product_uom_qty
            # Description
            if bl.name:
                rec.name = bl.name

            # Company alignment (if move has no company yet, fill it)
            if not rec.company_id and bl.booking_id and bl.booking_id.company_id:
                rec.company_id = bl.booking_id.company_id.id

            # Default to mark as consumption
            rec.is_booking_consumption = True

    @api.onchange("booking_id")
    def _onchange_booking_id(self):
        """
        On choosing booking, help fill name/origin and company if empty.
        """
        for rec in self:
            b = rec.booking_id
            if not b:
                continue
            if not rec.reference and getattr(rec, "reference", False) is not None:
                rec.reference = b.name
            if not rec.name:
                rec.name = _("Consumption for %s") % (b.name,)
            if not rec.company_id and b.company_id:
                rec.company_id = b.company_id.id

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("booking_line_id", "booking_id")
    def _check_booking_line_header(self):
        for rec in self:
            if rec.booking_line_id and rec.booking_id and rec.booking_line_id.booking_id != rec.booking_id:
                raise ValidationError(_("The selected Booking Line does not belong to the chosen Booking."))

    @api.constrains("booking_id", "company_id")
    def _check_company_consistency(self):
        for rec in self:
            if rec.booking_id and rec.company_id and rec.company_id != rec.booking_id.company_id:
                raise ValidationError(_("Company must match the Booking's Company."))

    # -------------------------------------------------------------------------
    # HELPERS — PREPARE MOVE VALS FROM BOOKING LINE
    # -------------------------------------------------------------------------
    def _prepare_move_vals_from_booking_line(self, booking_line, picking=None, resource=None):
        """
        Return a dict of stock.move values prepared from a booking line,
        suitable for use in create() (optionally attached to a picking).
        """
        self.ensure_one() if self else None
        if not booking_line or not booking_line.product_id:
            return {}

        product = booking_line.product_id
        company = booking_line.booking_id.company_id if booking_line.booking_id else (picking.company_id if picking else self.env.company)
        uom = booking_line.product_uom or product.uom_id

        vals = {
            "name": booking_line.name or product.display_name or _("Booking Line"),
            "product_id": product.id,
            "product_uom": uom.id,
            "product_uom_qty": booking_line.product_uom_qty or 1.0,
            "company_id": company.id,
            "booking_id": booking_line.booking_id.id if booking_line.booking_id else False,
            "booking_line_id": booking_line.id,
            "is_booking_consumption": True,
        }
        if picking:
            vals.update({
                "picking_id": picking.id,
                "location_id": picking.location_id.id,
                "location_dest_id": picking.location_dest_id.id,
            })
        if resource:
            vals["resource_id"] = resource.id
        return vals


# =============================================================================
# stock.picking — Inherit
# =============================================================================
class StockPicking(models.Model):
    _inherit = "stock.picking"

    # -------------------------------------------------------------------------
    # BOOKING LINKS
    # -------------------------------------------------------------------------
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking",
        index=True,
        help="Booking related to this transfer.",
        copy=False,
    )
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="booking_id.patient_id",
        store=True,
        readonly=True,
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        related="booking_id.doctor_id",
        store=True,
        readonly=True,
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        related="booking_id.treatment_id",
        store=True,
        readonly=True,
    )

    # Labeling
    is_booking_consumption = fields.Boolean(
        string="Is Booking Consumption",
        help="Enable to mark this picking as a transfer generated for a booking.",
        default=False,
    )

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("booking_id")
    def _onchange_booking_id(self):
        """
        Keep partner (patient), origin, and company aligned when a booking is selected.
        """
        for rec in self:
            b = rec.booking_id
            if not b:
                continue
            # Partner is the patient
            if not rec.partner_id and b.patient_id:
                rec.partner_id = b.patient_id.id
            # Origin reference
            if not rec.origin:
                rec.origin = b.name
            # Company alignment
            if not rec.company_id and b.company_id:
                rec.company_id = b.company_id.id
            # Label
            rec.is_booking_consumption = True

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("booking_id", "company_id")
    def _check_booking_company(self):
        for rec in self:
            if rec.booking_id and rec.company_id and rec.company_id != rec.booking_id.company_id:
                raise ValidationError(_("Company must match the Booking's Company."))

    @api.constrains("booking_id", "move_ids_without_package")
    def _check_moves_booking_link(self):
        """
        If picking has a booking, ensure all moves (with booking set) point to the same booking.
        """
        for rec in self:
            if not rec.booking_id:
                continue
            wrong = rec.move_ids_without_package.filtered(lambda m: m.booking_id and m.booking_id != rec.booking_id)
            if wrong:
                raise ValidationError(_("All moves in this picking must belong to the same Booking."))

    # -------------------------------------------------------------------------
    # ACTIONS — LOAD MOVES FROM BOOKING
    # -------------------------------------------------------------------------
    def action_load_moves_from_booking(self, include_booking_lines=True, include_resource_consumption=True):
        """
        Create stock moves from the linked booking:
        - If include_booking_lines: convert each booking.line with a product to a stock move.
        - If include_resource_consumption: ask each booking.line to prepare resource moves (if any),
          and attach/infer missing locations from this picking.
        """
        for picking in self:
            if not picking.booking_id:
                raise UserError(_("Please link a Booking first."))
            if picking.state not in ("draft", "confirmed", "assigned"):
                raise UserError(_("You can only load moves on a draft/confirmed/assigned transfer."))

            Move = self.env["stock.move"]
            new_moves = []

            # 1) From booking lines
            if include_booking_lines:
                for bline in picking.booking_id.line_ids:
                    if not bline.product_id:
                        continue
                    vals = Move._prepare_move_vals_from_booking_line(bline, picking=picking)
                    if vals:
                        new_moves.append(vals)

            # 2) From resource consumption (delegation to booking.line → booking.resource)
            if include_resource_consumption:
                for bline in picking.booking_id.line_ids:
                    if hasattr(bline, "prepare_resource_consumption"):
                        move_vals_list = bline.prepare_resource_consumption() or []
                        for mv in move_vals_list:
                            # Ensure minimum fields exist and bind to current picking
                            mv.setdefault("name", bline.name or _("Resource Consumption"))
                            mv.setdefault("company_id", picking.company_id.id)
                            mv["picking_id"] = picking.id
                            mv.setdefault("booking_id", picking.booking_id.id)
                            mv.setdefault("booking_line_id", bline.id)
                            mv.setdefault("is_booking_consumption", True)
                            # Default locations from picking if not provided by resource
                            mv.setdefault("location_id", picking.location_id.id)
                            mv.setdefault("location_dest_id", picking.location_dest_id.id)
                            # Optional resource link carried by the resource helper
                            new_moves.append(mv)

            if not new_moves:
                raise UserError(_("No stock moves to create from this booking."))

            Move.create(new_moves)

            picking.message_post(body=_("Loaded %d move(s) from Booking %s.") % (len(new_moves), picking.booking_id.name))

        return True

    # -------------------------------------------------------------------------
    # VALIDATION HOOK — POST BACK TO BOOKING CHATTER
    # -------------------------------------------------------------------------
    def button_validate(self):
        """
        After validating the picking, post a summary message to the related booking (if any).
        """
        res = super().button_validate()
        for picking in self:
            if not picking.booking_id:
                continue
            try:
                # Build a small summary of products & done quantities
                lines = []
                for m in picking.move_ids:
                    if m.state in ("done",) and m.product_id:
                        qty = 0.0
                        # In modern stock, the 'quantity_done' is on move line(s)
                        if m.move_line_ids:
                            qty = sum(m.move_line_ids.mapped("quantity"))
                        else:
                            qty = m.quantity or 0.0
                        if qty:
                            lines.append(f"- {m.product_id.display_name}: {qty} {m.product_uom.display_name}")
                details = "<br/>".join(lines) if lines else _("No quantities validated.")
                picking.booking_id.message_post(
                    body=_("Inventory transfer validated: <b>%s</b><br/>%s") % (picking.name or picking.id, details)
                )
            except Exception:
                # Never block validation due to chatter issues
                pass
        return res

    # -------------------------------------------------------------------------
    # NAVIGATION
    # -------------------------------------------------------------------------
    def action_view_booking(self):
        self.ensure_one()
        if not self.booking_id:
            raise UserError(_("This transfer is not linked to any booking."))
        return {
            "name": _("Booking"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "form",
            "res_id": self.booking_id.id,
            "target": "current",
        }

# -*- coding: utf-8 -*-
# ClinicOne — Booking Management (Odoo 19 CE)
# File: models/treatment_inherit.py
#
# Purpose
# -------
# Extend clinic.treatment with booking-oriented capabilities:
# - Default duration & buffers for appointments created from the treatment
# - Preferred rooms/resources/channel/policy suggestions
# - Compatibility helpers with booking.resource & booking.room
# - Booking statistics and quick actions
#
# Integrations (soft-coupled)
# ---------------------------
# - booking.booking     : booking header uses treatment_id
# - booking.room        : preferred rooms for this treatment
# - booking.resource    : preferred resources; compatibility via allowed_treatment_ids on resource
# - booking.channel     : default booking channel suggestion
# - booking.policy      : default booking policy suggestion
# - account/product     : do not redefine pricing/product here; we only reference if present
#
# Notes
# -----
# - All user-facing strings are in English (per project requirement).
# - No hard dependency to sibling modules beyond those declared by clinic_booking.
# - Guards with hasattr / environment checks to avoid crashes if some modules are absent.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta


class ClinicTreatment(models.Model):
    _inherit = "clinic.treatment"

    # -------------------------------------------------------------------------
    # BOOKING DEFAULTS (safe field names prefixed with 'booking_')
    # -------------------------------------------------------------------------
    booking_default_duration_minutes = fields.Integer(
        string="Default Duration (min)",
        default=60,
        help="Suggested appointment duration when creating a booking from this treatment.",
        tracking=True,
    )
    booking_buffer_before_minutes = fields.Integer(
        string="Buffer Before (min)",
        default=0,
        help="Preparation time reserved before a session of this treatment.",
        tracking=True,
    )
    booking_buffer_after_minutes = fields.Integer(
        string="Buffer After (min)",
        default=0,
        help="Cleaning/reset time reserved after a session of this treatment.",
        tracking=True,
    )

    booking_default_channel_id = fields.Many2one(
        "booking.channel",
        string="Default Booking Channel",
        help="Channel to prefill when making a booking for this treatment.",
        tracking=True,
    )
    booking_default_policy_id = fields.Many2one(
        "booking.policy",
        string="Default Booking Policy",
        help="Policy to prefill when making a booking for this treatment.",
        tracking=True,
    )
    booking_default_room_ids = fields.Many2many(
        "booking.room",
        "treatment_booking_room_rel",
        "treatment_id",
        "room_id",
        string="Preferred Rooms",
        help="Rooms commonly used for this treatment. Used as suggestions when booking.",
    )
    booking_default_resource_ids = fields.Many2many(
        "booking.resource",
        "treatment_booking_resource_rel",
        "treatment_id",
        "resource_id",
        string="Preferred Resources",
        help="Devices/tools typically required for this treatment.",
    )

    # Optional compatibility constraint to certain doctors (kept soft; may not exist in base)
    allowed_doctor_ids = fields.Many2many(
        "clinic.doctor",
        "treatment_allowed_doctor_rel",
        "treatment_id",
        "doctor_id",
        string="Allowed Doctors",
        help="If set, only these doctors are considered compatible for this treatment.",
    )

    # Contraindications / internal notes for booking staff
    booking_contraindication_note = fields.Text(
        string="Contraindications / Notes",
        help="Internal notes for staff about contraindications, preparation, or special requirements.",
    )

    # -------------------------------------------------------------------------
    # STATS / LINKS
    # -------------------------------------------------------------------------
    bookings_count = fields.Integer(
        string="Bookings",
        compute="_compute_booking_stats",
        help="Number of active bookings referencing this treatment.",
    )
    last_booking_id = fields.Many2one(
        "booking.booking",
        string="Last Booking",
        compute="_compute_last_booking",
        help="Most recently created booking for this treatment.",
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("booking_default_duration_minutes", "booking_buffer_before_minutes", "booking_buffer_after_minutes")
    def _check_booking_numbers(self):
        for rec in self:
            if rec.booking_default_duration_minutes is not None and rec.booking_default_duration_minutes <= 0:
                raise ValidationError(_("Default Duration must be greater than 0 minutes."))
            if rec.booking_buffer_before_minutes is not None and rec.booking_buffer_before_minutes < 0:
                raise ValidationError(_("Buffer Before must be 0 or a positive number."))
            if rec.booking_buffer_after_minutes is not None and rec.booking_buffer_after_minutes < 0:
                raise ValidationError(_("Buffer After must be 0 or a positive number."))

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_booking_stats(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            rec.bookings_count = Booking.search_count([
                ("treatment_id", "=", rec.id),
                ("active", "=", True),
            ])

    def _compute_last_booking(self):
        Booking = self.env["booking.booking"]
        for rec in self:
            last = Booking.search([("treatment_id", "=", rec.id)], order="create_date desc, id desc", limit=1)
            rec.last_booking_id = last.id if last else False

    # -------------------------------------------------------------------------
    # ONCHANGE — KEEP DEFAULTS CONSISTENT
    # -------------------------------------------------------------------------
    @api.onchange("booking_default_resource_ids")
    def _onchange_booking_default_resource_ids(self):
        """
        Auto-clean preferred resources that are marked incompatible with this treatment.
        booking.resource has field 'allowed_treatment_ids'. Keep only resources where:
        - allowed_treatment_ids is empty or includes this treatment.
        """
        for rec in self:
            if not rec.booking_default_resource_ids:
                continue
            cleaned = rec.booking_default_resource_ids
            # Filter by resource.allowed_treatment_ids compatibility if field exists
            cleaned = cleaned.filtered(lambda r: not hasattr(r, "allowed_treatment_ids") or not r.allowed_treatment_ids or rec in r.allowed_treatment_ids)
            if cleaned != rec.booking_default_resource_ids:
                rec.booking_default_resource_ids = cleaned
                return {
                    "warning": {
                        "title": _("Resource Compatibility"),
                        "message": _(
                            "Some preferred resources were removed because they are not compatible with this treatment."
                        ),
                    }
                }
        return {}

    @api.onchange("allowed_doctor_ids")
    def _onchange_allowed_doctor_ids(self):
        """
        Informational: warn if allowed_doctor_ids conflicts with any doctor's own policy,
        but do not hard-block here (validations are done at booking time).
        """
        # Kept as placeholder hook; actual cross-model validation occurs when assigning doctor on booking.
        return {}

    # -------------------------------------------------------------------------
    # HELPERS — APPLY DEFAULTS TO BOOKING
    # -------------------------------------------------------------------------
    def apply_defaults_to_booking_vals(self, vals=None, start_dt=None, end_dt=None, doctor_id=None):
        """
        Return dict of booking values prefilled from this treatment.
        Caller can merge this with manual inputs before create().

        Intended keys:
          - treatment_id, channel_id, policy_id
          - room_id (first preferred room) and resource_ids (all preferred)
          - duration (only as guidance; booking derives end from start + duration)
        """
        self.ensure_one()
        vals = dict(vals or {})
        vals.setdefault("treatment_id", self.id)

        # Prefill channel/policy if not already set
        if self.booking_default_channel_id and not vals.get("channel_id"):
            vals["channel_id"] = self.booking_default_channel_id.id
        if self.booking_default_policy_id and not vals.get("policy_id"):
            vals["policy_id"] = self.booking_default_policy_id.id

        # Preferred room (take the first one as default)
        if self.booking_default_room_ids and not vals.get("room_id"):
            vals["room_id"] = self.booking_default_room_ids[0].id

        # Preferred resources (all)
        if self.booking_default_resource_ids and not vals.get("resource_ids"):
            # Filter by compatibility with selected doctor if given and resource has allowed_doctor_ids
            resources = self.booking_default_resource_ids
            if doctor_id:
                resources = resources.filtered(lambda r: not hasattr(r, "allowed_doctor_ids") or not r.allowed_doctor_ids or doctor_id in r.allowed_doctor_ids.ids)
            vals["resource_ids"] = [(6, 0, resources.ids)]

        # Timing suggestion (if caller wants to compute end from start)
        if start_dt and not vals.get("start_datetime"):
            vals["start_datetime"] = fields.Datetime.to_string(start_dt)
        if end_dt and not vals.get("end_datetime"):
            # If end given, use it. Otherwise, compute from default duration if start provided.
            vals["end_datetime"] = fields.Datetime.to_string(end_dt)
        elif start_dt and self.booking_default_duration_minutes:
            vals["end_datetime"] = fields.Datetime.to_string(
                fields.Datetime.from_string(vals["start_datetime"]) + timedelta(minutes=int(self.booking_default_duration_minutes))
            )

        return vals

    def filter_resources_for_doctor(self, resources, doctor):
        """
        Utility: filter a recordset of booking.resource by doctor compatibility
        and treatment compatibility if those fields exist.
        """
        self.ensure_one()
        if not resources:
            return resources
        res = resources
        # Doctor compatibility
        if doctor and hasattr(resources[:1], "allowed_doctor_ids"):
            res = res.filtered(lambda r: not r.allowed_doctor_ids or doctor in r.allowed_doctor_ids)
        # Treatment compatibility
        if hasattr(resources[:1], "allowed_treatment_ids"):
            res = res.filtered(lambda r: not r.allowed_treatment_ids or self in r.allowed_treatment_ids)
        return res

    # -------------------------------------------------------------------------
    # ACTIONS — NAVIGATION / QUICK BOOK
    # -------------------------------------------------------------------------
    def action_view_bookings(self):
        """
        Open bookings filtered by this treatment.
        """
        self.ensure_one()
        action = {
            "name": _("Bookings"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "list,form,calendar,kanban,activity,pivot,graph",
            "domain": [("treatment_id", "=", self.id)],
            "context": {
                "default_treatment_id": self.id,
                "default_channel_id": self.booking_default_channel_id.id if self.booking_default_channel_id else False,
                "default_policy_id": self.booking_default_policy_id.id if self.booking_default_policy_id else False,
                "default_room_id": self.booking_default_room_ids[:1].id if self.booking_default_room_ids else False,
                "default_resource_ids": [(6, 0, self.booking_default_resource_ids.ids)] if self.booking_default_resource_ids else False,
            },
        }
        act_ref = self.env.ref("clinic_booking.action_booking_list", raise_if_not_found=False)
        if act_ref:
            data = act_ref.read()[0]
            data.update(action)
            return data
        return action

    def action_new_booking(self):
        """
        Open a new booking form prefilled with this treatment's defaults.
        """
        self.ensure_one()
        ctx = {
            "default_treatment_id": self.id,
            "default_channel_id": self.booking_default_channel_id.id if self.booking_default_channel_id else False,
            "default_policy_id": self.booking_default_policy_id.id if self.booking_default_policy_id else False,
            "default_room_id": self.booking_default_room_ids[:1].id if self.booking_default_room_ids else False,
            "default_resource_ids": [(6, 0, self.booking_default_resource_ids.ids)] if self.booking_default_resource_ids else False,
        }
        return {
            "name": _("New Booking"),
            "type": "ir.actions.act_window",
            "res_model": "booking.booking",
            "view_mode": "form",
            "context": ctx,
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # VALIDATION UTILITIES (CAN DOCTOR PERFORM?)
    # -------------------------------------------------------------------------
    def check_doctor_allowed(self, doctor):
        """
        Return (bool, reason) whether a doctor is allowed for this treatment,
        considering both treatment.allowed_doctor_ids and doctor.allowed_treatment_ids (if present).
        """
        self.ensure_one()
        if not doctor:
            return (True, _("No doctor provided — cannot validate."))
        # Treatment-side constraint
        if self.allowed_doctor_ids and doctor not in self.allowed_doctor_ids:
            return (False, _("Doctor is not included in treatment's allowed doctors."))
        # Doctor-side constraint (if model has this field)
        if hasattr(doctor, "allowed_treatment_ids") and doctor.allowed_treatment_ids:
            if self not in doctor.allowed_treatment_ids:
                return (False, _("Treatment is not included in doctor's allowed treatments."))
        return (True, _("Allowed."))


