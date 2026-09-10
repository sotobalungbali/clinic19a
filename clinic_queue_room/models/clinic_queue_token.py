
# -*- coding: utf-8 -*-
# ClinicOne — Clinical Queue & Room Management (Odoo 18 CE)
# File: models/clinic_queue_token.py
# License: LGPL-3.0

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import date


class ClinicQueueToken(models.Model):
    _name = "clinic.queue.token"
    _description = "Queue Token"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "token_date desc, series asc, token_number asc, id asc"
    # By default Odoo will create table 'clinic_queue_token'

    # -------------------------------------------------------------------------
    # Identity & Display
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Token Reference",
        default="New",
        copy=False,
        index=True,
        tracking=True,
        help="Internal reference generated from a sequence (not the printed token code)."
    )
    code = fields.Char(
        string="Printed Token Code",
        copy=False,
        index=True,
        tracking=True,
        help="Human-facing token code printed on tickets (e.g., A-023)."
    )
    series = fields.Char(
        string="Series",
        size=8,
        default=lambda self: self._default_series(),
        index=True,
        tracking=True,
        help=(
            "Series/prefix for token grouping (e.g., A, B, VIP). "
            "Usually derived from Queue Type or business line."
        ),
    )
    queue_type = fields.Selection(
        selection=[
            ("general", "General"),
            ("treatment", "Treatment"),
            ("procedure", "Procedure"),
            ("telemedicine", "Telemedicine"),
            ("vip", "VIP"),
        ],
        string="Queue Type",
        default="general",
        required=True,
        index=True,
        help="Functional category that produced this token. Often influences the token series.",
    )

    # -------------------------------------------------------------------------
    # Scoping & Dates
    # -------------------------------------------------------------------------
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        help="Company scope for this token."
    )
    token_date = fields.Date(
        string="Token Date",
        default=lambda self: fields.Date.context_today(self),
        required=True,
        index=True,
        tracking=True,
        help="Business date of the token. Counters reset per date, company, and series."
    )
    token_number = fields.Integer(
        string="Token Number",
        index=True,
        help="Sequential number for this token within (Company, Date, Series)."
    )

    # -------------------------------------------------------------------------
    # Subject & Intent (who/what this token is for)
    # -------------------------------------------------------------------------
    patient_id = fields.Many2one(
        comodel_name="res.partner",
        string="Patient",
        index=True,
        tracking=True,
        domain=[("is_company", "=", False)],
        help="Patient who received this token."
    )
    appointment_id = fields.Many2one(
        comodel_name="clinic.appointment",
        string="Appointment",
        index=True,
        help="Linked appointment if this token was issued from an appointment."
    )
    # booking_id = fields.Many2one(
    #     comodel_name="booking.booking",
    #     string="Booking",
    #     index=True,
    #     help="Linked booking if created via booking module."
    # )
    treatment_id = fields.Many2one(
        comodel_name="clinic.treatment",
        string="Requested Treatment",
        index=True,
        help="Intended treatment associated with this token (if known)."
    )
    priority = fields.Selection(
        selection=[("0", "Low"), ("1", "Normal"), ("2", "High"), ("3", "Urgent")],
        string="Priority",
        default="1",
        index=True,
        tracking=True,
        help="Priority level that may be considered when calling tokens."
    )
    channel = fields.Selection(
        selection=[
            ("walkin", "Walk-in"),
            ("online", "Online"),
            ("referral", "Referral"),
            ("telemedicine", "Telemedicine"),
            ("vip", "VIP"),
        ],
        string="Intake Channel",
        default="walkin",
        index=True,
        help="How the patient acquired this token."
    )

    # -------------------------------------------------------------------------
    # Operational Links (Queue / Room / Staff / Stage)
    # -------------------------------------------------------------------------
    queue_id = fields.Many2one(
        comodel_name="clinic.queue",
        string="Queue",
        index=True,
        help="Queue record generated or linked from this token."
    )
    stage_id = fields.Many2one(
        comodel_name="clinic.queue.stage",
        string="Queue Stage (Hint)",
        help="Preferred stage to place the queue into when it is created from this token."
    )
    doctor_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Preferred Doctor",
        index=True,
        domain=[("is_doctor", "=", True)],
        help="Preferred doctor (if any)."
    )
    room_type_id = fields.Many2one(
        comodel_name="clinic.room.type",
        string="Preferred Room Type",
        help="Room type hint for auto-assignment."
    )
    room_id = fields.Many2one(
        comodel_name="clinic.room",
        string="Preferred Room",
        help="Room hint for calling/assignment."
    )

    # -------------------------------------------------------------------------
    # Lifecycle & Timing
    # -------------------------------------------------------------------------
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("issued", "Issued"),
            ("called", "Called"),
            ("skipped", "Skipped"),
            ("served", "Served"),
            ("cancelled", "Cancelled"),
            ("expired", "Expired"),
        ],
        string="Status",
        default="draft",
        index=True,
        tracking=True,
        help="Operational state of the token."
    )
    issued_at = fields.Datetime(
        string="Issued At",
        tracking=True,
        help="Timestamp when the token was issued."
    )
    called_at = fields.Datetime(
        string="Called At",
        tracking=True,
        help="Timestamp when the token was called."
    )
    served_at = fields.Datetime(
        string="Served At",
        tracking=True,
        help="Timestamp when the token was marked as served."
    )
    cancelled_at = fields.Datetime(
        string="Cancelled At",
        tracking=True,
        help="Timestamp when the token was cancelled."
    )
    expired_at = fields.Datetime(
        string="Expired At",
        tracking=True,
        help="Timestamp when the token was expired."
    )

    called_by_id = fields.Many2one(
        comodel_name="res.users",
        string="Called By",
        help="User who called the token."
    )
    served_by_id = fields.Many2one(
        comodel_name="res.users",
        string="Served By",
        help="User who marked the token as served."
    )

    # Printing & Display
    printed = fields.Boolean(
        string="Printed",
        help="Indicates whether the token ticket has been printed."
    )
    print_count = fields.Integer(
        string="Print Count",
        default=0,
        help="Number of times the token has been printed."
    )
    last_printed_at = fields.Datetime(
        string="Last Printed At",
        help="Timestamp of the last print operation."
    )
    display_channel = fields.Char(
        string="Display Channel",
        help="Optional display channel/screen identifier for signage systems."
    )
    kiosk_ref = fields.Char(
        string="Kiosk Reference",
        help="External kiosk reference (if issued via kiosk)."
    )

    # Positioning in series (for dashboard display)
    position_in_series = fields.Integer(
        string="Position in Series",
        compute="_compute_position_in_series",
        help="Approximate position among tokens of the same date/series still waiting to be served."
    )

    # Misc
    notes = fields.Text(
        string="Notes",
        help="Internal notes related to this token."
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS & SQL
    # -------------------------------------------------------------------------
    _uniq_company_date_series_number = models.Constraint(
        "unique(company_id, token_date, series, token_number)",
        "Token Number must be unique per Company, Date, and Series.",
    )

    # -------------------------------------------------------------------------
    # DEFAULTS / HELPERS
    # -------------------------------------------------------------------------
    @api.model
    def _default_series(self):
        """Provide a small default series depending on queue type (fallback 'A')."""
        # Cannot read queue_type here (field default order). Use 'A' as generic default.
        return "A"

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("company_id", "token_date", "series", "state", "token_number")
    def _compute_position_in_series(self):
        """
        Compute a rough 'queue position' among tokens with same (company, date, series)
        still pending service. Lower numbers first. States considered waiting:
        issued, called, skipped (re-callable).
        """
        pending_states = ("issued", "called", "skipped")
        for rec in self:
            rec.position_in_series = 0
            if not rec.company_id or not rec.token_date or not rec.series or not rec.token_number:
                continue
            domain = [
                ("company_id", "=", rec.company_id.id),
                ("token_date", "=", rec.token_date),
                ("series", "=ilike", rec.series),
                ("state", "in", pending_states),
                ("token_number", "<=", rec.token_number),
            ]
            count = self.search_count(domain)
            rec.position_in_series = max(count, 0)

    # -------------------------------------------------------------------------
    # CREATE / WRITE
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """
        - Assign sequence-based 'name' (internal reference).
        - Allocate next token_number atomically per (company, date, series).
        - Build 'code' as SERIES-#### (e.g., A-0023).
        - Set issued timestamps if state preset to 'issued'.
        """
        # Fill defaults/basics first
        for vals in vals_list:
            # Normalise basics
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if not vals.get("token_date"):
                vals["token_date"] = fields.Date.context_today(self)
            if not vals.get("series"):
                vals["series"] = "A"
            # Internal name sequence
            if not vals.get("name") or vals.get("name") == "New":
                # Use a generic sequence; ensure one exists in data as 'clinic.queue.token'
                seq = self.env["ir.sequence"].next_by_code("clinic.queue.token")
                vals["name"] = seq or _("New")

        # Allocate numbers and codes with DB-level locking to avoid race
        for vals in vals_list:
            if not vals.get("token_number"):
                next_num = self._lock_and_get_next_number(
                    company_id=vals["company_id"],
                    token_date=vals["token_date"],
                    series=vals["series"],
                )
                vals["token_number"] = next_num
            # Build printed code if missing
            if not vals.get("code"):
                vals["code"] = self._format_code(vals["series"], vals["token_number"])

            # If creator intended immediate issue
            if vals.get("state") == "issued" and not vals.get("issued_at"):
                vals["issued_at"] = fields.Datetime.now()

        records = super().create(vals_list)

        # Auto-subscribe patient to chatter
        for rec in records:
            subs = []
            if rec.patient_id and rec.patient_id.exists() and not rec.patient_id.partner_share:
                subs.append(rec.patient_id.id)
            if subs:
                rec.message_subscribe(partner_ids=list(set(subs)))

        return records

    def write(self, vals):
        # Prevent illegal state changes checks can be added here if needed
        res = super().write(vals)
        # Update printed flags
        if "printed" in vals and vals["printed"]:
            now = fields.Datetime.now()
            for rec in self:
                rec.last_printed_at = now
                rec.print_count = (rec.print_count or 0) + 1
        return res

    # -------------------------------------------------------------------------
    # INTERNALS — TOKEN NUMBERING
    # -------------------------------------------------------------------------
    @api.model
    def _format_code(self, series, number):
        """Format the human-facing token code."""
        # 4 digits zero-padded by default; adjust if you expect >9999 per day.
        return f"{(series or 'A').upper()}-{int(number):04d}"

    @api.model
    def _lock_and_get_next_number(self, company_id, token_date, series):
        """
        Get the next token number with database-level row locking (safe for concurrency).
        We lock on the tuple (company_id, token_date, series) by selecting MAX(token_number) FOR UPDATE.
        """
        if isinstance(token_date, str):
            # ensure date object for SQL driver safety; Odoo usually handles, but be explicit
            token_date = fields.Date.from_string(token_date)
        # Lock the company row first. PostgreSQL does not allow FOR UPDATE on
        # an aggregate row (MAX), and the company-row lock serializes token
        # allocation safely within one company.
        self.env.cr.execute(
            "SELECT id FROM res_company WHERE id = %s FOR UPDATE",
            (company_id,),
        )
        self.env.cr.execute(
            """
            SELECT MAX(token_number)
              FROM clinic_queue_token
             WHERE company_id = %s
               AND token_date = %s
               AND UPPER(series) = UPPER(%s)
            """,
            (company_id, token_date, series or "A"),
        )
        row = self.env.cr.fetchone()
        current_max = int(row[0]) if row and row[0] is not None else 0
        return current_max + 1

    # -------------------------------------------------------------------------
    # ACTIONS — LIFECYCLE
    # -------------------------------------------------------------------------
    def action_issue(self):
        for rec in self:
            if rec.state not in ("draft", "cancelled", "expired"):
                raise UserError(_("Only Draft/Cancelled/Expired tokens can be issued."))
            rec.write({
                "state": "issued",
                "issued_at": fields.Datetime.now(),
            })
        return True

    def action_call(self):
        for rec in self:
            if rec.state not in ("issued", "skipped"):
                raise UserError(_("Only Issued/Skipped tokens can be called."))
            rec.write({
                "state": "called",
                "called_at": fields.Datetime.now(),
                "called_by_id": self.env.user.id,
            })
        return True

    def action_skip(self):
        for rec in self:
            if rec.state != "called":
                raise UserError(_("Only Called tokens can be skipped."))
            rec.write({"state": "skipped"})
        return True

    def action_serve(self):
        for rec in self:
            if rec.state not in ("called",):
                raise UserError(_("Only Called tokens can be marked as served."))
            rec.write({
                "state": "served",
                "served_at": fields.Datetime.now(),
                "served_by_id": self.env.user.id,
            })
            # Optionally: move the linked queue to 'in_progress' or 'done' via policy
            if rec.queue_id and rec.queue_id.state in ("waiting", "on_hold"):
                try:
                    rec.queue_id.action_start()
                except Exception as e:
                    rec.message_post(body=_("Queue start from token serve failed: %s") % e)
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state in ("served",):
                raise UserError(_("Served tokens cannot be cancelled."))
            rec.write({
                "state": "cancelled",
                "cancelled_at": fields.Datetime.now(),
            })
        return True

    def action_expire(self):
        for rec in self:
            if rec.state in ("served", "cancelled", "expired"):
                continue
            rec.write({
                "state": "expired",
                "expired_at": fields.Datetime.now(),
            })
        return True

    # -------------------------------------------------------------------------
    # ACTIONS — CREATE QUEUE FROM TOKEN
    # -------------------------------------------------------------------------
    def action_create_queue(self):
        """
        Create a clinic.queue from this token if not yet linked.
        Applies stage hints and integration hints (doctor/room/treatment).
        """
        self.ensure_one()
        if self.queue_id:
            return self._action_view_queue()

        Queue = self.env["clinic.queue"]
        # Determine default stage for the queue
        target_stage = self.stage_id
        if not target_stage:
            target_stage = self.env["clinic.queue.stage"].get_default_stage(
                company_id=self.company_id.id,
                queue_type=self.queue_type or "general",
            )
        vals = {
            "patient_id": self.patient_id.id if self.patient_id else False,
            "doctor_id": self.doctor_id.id if self.doctor_id else False,
            "treatment_id": self.treatment_id.id if self.treatment_id else False,
            "room_id": self.room_id.id if self.room_id else False,
            "stage_id": target_stage.id if target_stage else False,
            "company_id": self.company_id.id,
            "channel": self.channel or "walkin",
            "appointment_id": self.appointment_id.id if self.appointment_id else False,
            "token_id": self.id,
        }
        queue = Queue.create({k: v for k, v in vals.items() if v or k in ("company_id", "channel", "patient_id")})

        # If the stage requires auto actions, run them
        if queue.stage_id:
            try:
                queue.stage_id.validate_requirements(queue)
                queue.stage_id._run_on_enter_hooks(queue)
            except Exception as e:
                queue.message_post(body=_("Stage enter hooks failed: %s") % e)

        self.queue_id = queue.id
        return self._action_view_queue()

    def _action_view_queue(self):
        """Return an action to open the linked queue."""
        self.ensure_one()
        if not self.queue_id:
            return False
        action = self.env.ref("clinic_queue_room.action_clinic_queue_form", raise_if_not_found=False)
        if action:
            res = action.read()[0]
            res.update({"res_id": self.queue_id.id, "view_mode": "form"})
            return res
        # Fallback generic
        return {
            "type": "ir.actions.act_window",
            "name": _("Queue"),
            "res_model": "clinic.queue",
            "res_id": self.queue_id.id,
            "view_mode": "form",
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # DISPLAY (Odoo 19)
    # -------------------------------------------------------------------------
    @api.depends("code", "name", "patient_id", "patient_id.name")
    def _compute_display_name(self):
        for rec in self:
            label = rec.code or rec.name or _("Token")
            if rec.patient_id:
                label = f"{label} — {rec.patient_id.display_name}"
            rec.display_name = label

    def name_get(self):
        """Compatibility wrapper for older ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        domain = domain or []
        criteria = []
        if name:
            criteria = ["|", ("code", operator, name), ("name", operator, name)]
        recs = self.search(domain + criteria, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]

    # -------------------------------------------------------------------------
    # VALIDATIONS
    # -------------------------------------------------------------------------
    @api.constrains("series")
    def _check_series(self):
        for rec in self:
            if rec.series:
                s = rec.series.strip()
                if not s:
                    raise ValidationError(_("Series cannot be empty."))
                if len(s) > 8:
                    raise ValidationError(_("Series length must be <= 8 characters."))

    @api.constrains("token_number")
    def _check_token_number(self):
        for rec in self:
            if rec.token_number is not None and rec.token_number < 1:
                raise ValidationError(_("Token Number must be a positive integer."))

    # -------------------------------------------------------------------------
    # UTILITIES
    # -------------------------------------------------------------------------
    def as_display_payload(self):
        """
        Build a minimal payload for signage/display systems (controllers/display_api.py).
        """
        self.ensure_one()
        return {
            "code": self.code,
            "series": self.series,
            "number": self.token_number,
            "state": self.state,
            "patient": self.patient_id.display_name if self.patient_id else "",
            "room": self.room_id.name if self.room_id else "",
            "doctor": self.doctor_id.name if self.doctor_id else "",
            "called_at": self.called_at and fields.Datetime.to_string(self.called_at) or "",
        }


# -----------------------------------------------------------------------------
# Backward-compatibility alias (legacy model name)
# Keep while other modules still reference 'clinicone.clinical.queue.token'
# -----------------------------------------------------------------------------
# class LegacyCliniconeClinicalQueueToken(models.Model):
#     _name = "clinicone.clinical.queue.token"
#     _inherit = "clinic.queue.token"
#     _description = "Queue Token (Legacy Alias)"
#     _register = False
