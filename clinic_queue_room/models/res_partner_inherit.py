
# -*- coding: utf-8 -*-
# ClinicOne — Clinical Queue & Room Management (Odoo 18/19 CE)
# File: models/res_partner_inherit.py
# License: LGPL-3.0

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    # -------------------------------------------------------------------------
    # Queue Preferences / Flags (Patient-centric)
    # -------------------------------------------------------------------------
    default_queue_type = fields.Selection(
        selection=[
            ("general", "General"),
            ("treatment", "Treatment"),
            ("procedure", "Procedure"),
            ("telemedicine", "Telemedicine"),
            ("vip", "VIP"),
        ],
        string="Default Queue Type",
        help="Preferred queue type for this patient. Used as a default when issuing tokens or creating queues."
    )
    default_channel = fields.Selection(
        selection=[
            ("walkin", "Walk-in"),
            ("online", "Online"),
            ("referral", "Referral"),
            ("telemedicine", "Telemedicine"),
            ("vip", "VIP"),
        ],
        string="Default Intake Channel",
        help="Preferred intake channel when a new queue/token is created for this patient."
    )
    default_priority = fields.Selection(
        selection=[("0", "Low"), ("1", "Normal"), ("2", "High"), ("3", "Urgent")],
        string="Default Queue Priority",
        default="1",
        help="Default queue priority for this patient."
    )
    preferred_room_type_id = fields.Many2one(
        comodel_name="clinic.room.type",
        string="Preferred Room Type",
        help="Preferred room type to serve this patient."
    )
    preferred_doctor_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Preferred Doctor",
        domain=[("is_doctor", "=", True)],
        help="Preferred doctor for this patient (if applicable)."
    )
    queue_blacklisted = fields.Boolean(
        string="Queue Blacklist",
        help="If enabled, this patient should not be allowed to receive a queue/token (frontdesk/kiosk may block)."
    )
    is_vip = fields.Boolean(
        string="VIP Patient",
        help="Flag this patient as VIP. Can be used by pricing/priority/room routing rules."
    )

    # Optional membership/insurance links (soft-coupled)
    membership_id = fields.Many2one(
        comodel_name="clinic.membership",
        string="Membership",
        help="Membership record of this patient (if any)."
    )
    insurance_policy_id = fields.Many2one(
        comodel_name="clinic.insurance.policy",
        string="Insurance Policy",
        help="Primary insurance policy for this patient (if any)."
    )

    # -------------------------------------------------------------------------
    # Live Metrics & Last Activities
    # -------------------------------------------------------------------------
    queue_active_count = fields.Integer(
        string="Active Queues",
        compute="_compute_queue_stats",
        help="Number of active queues (Waiting/In Progress/On Hold) for this patient (current company)."
    )
    queue_total_count = fields.Integer(
        string="Total Queues",
        compute="_compute_queue_stats",
        help="Total queues ever created for this patient (current company)."
    )
    queue_last_id = fields.Many2one(
        comodel_name="clinic.queue",
        string="Last Queue",
        compute="_compute_last_records",
        help="Most recent queue for this patient."
    )
    last_visit_time = fields.Datetime(
        string="Last Visit Time",
        compute="_compute_last_records",
        help="Timestamp of the most recent visit activity (queue start/end/check-in)."
    )
    avg_wait_min = fields.Float(
        string="Avg. Waiting (min, last 10)",
        compute="_compute_last_records",
        help="Average waiting time (Check-in → Start) from the last 10 queues."
    )
    token_today_count = fields.Integer(
        string="Tokens Today",
        compute="_compute_token_stats",
        help="Number of tokens issued today for this patient (current company)."
    )
    token_last_id = fields.Many2one(
        comodel_name="clinic.queue.token",
        string="Last Token",
        compute="_compute_token_stats",
        help="Most recent token for this patient."
    )
    next_appointment_id = fields.Many2one(
        comodel_name="clinic.appointment",
        string="Next Appointment",
        compute="_compute_next_appointment",
        help="Next scheduled appointment for this patient (current company)."
    )

    # Convenience booleans
    has_active_queue = fields.Boolean(
        string="Has Active Queue",
        compute="_compute_flags",
        help="True if the patient currently has at least one active queue."
    )

    # -------------------------------------------------------------------------
    # COMPUTES — Batch-friendly
    # -------------------------------------------------------------------------
    @api.depends("company_id")
    def _compute_queue_stats(self):
        """
        Compute active/total queue counts with read_group for efficiency.
        Active states: waiting, in_progress, on_hold.
        """
        recs = self.filtered(lambda p: p.id)
        for p in self:
            p.queue_active_count = 0
            p.queue_total_count = 0
        if not recs:
            return

        Queue = self.env["clinic.queue"]
        partner_ids = recs.ids
        company_id = self.env.company.id

        # Active queues
        active_domain = [
            ("patient_id", "in", partner_ids),
            ("company_id", "=", company_id),
            ("state", "in", ["waiting", "in_progress", "on_hold"]),
        ]
        active_rows = Queue._read_group(
            domain=active_domain,
            groupby=["patient_id"],
            aggregates=["__count"],
        )
        active_map = {patient.id: count for patient, count in active_rows if patient}

        # Total queues
        total_domain = [
            ("patient_id", "in", partner_ids),
            ("company_id", "=", company_id),
        ]
        total_rows = Queue._read_group(
            domain=total_domain,
            groupby=["patient_id"],
            aggregates=["__count"],
        )
        total_map = {patient.id: count for patient, count in total_rows if patient}

        for p in recs:
            p.queue_active_count = int(active_map.get(p.id, 0))
            p.queue_total_count = int(total_map.get(p.id, 0))

    @api.depends("company_id")
    def _compute_last_records(self):
        """
        Compute last queue, last visit time, and average waiting minutes from last 10 queues.
        """
        Queue = self.env["clinic.queue"]
        for p in self:
            p.queue_last_id = False
            p.last_visit_time = False
            p.avg_wait_min = 0.0
            if not p.id:
                continue

            domain = [("patient_id", "=", p.id), ("company_id", "=", self.env.company.id)]
            last_q = Queue.search(domain, limit=1, order="checkin_time desc, id desc")
            if last_q:
                p.queue_last_id = last_q.id
                # Last visit time preference: end_time > start_time > checkin_time
                p.last_visit_time = last_q.end_time or last_q.start_time or last_q.checkin_time

            # Average waiting of last 10 queues
            qs = Queue.search(domain, limit=10, order="checkin_time desc, id desc")
            waits = []
            for q in qs:
                if q.waiting_duration_min:
                    waits.append(q.waiting_duration_min)
                else:
                    # compute on the fly if not stored yet
                    def minutes(a, b):
                        if not a or not b:
                            return 0.0
                        delta = fields.Datetime.to_datetime(b) - fields.Datetime.to_datetime(a)
                        return max(delta.total_seconds() / 60.0, 0.0)
                    waits.append(minutes(q.checkin_time, q.start_time))
            p.avg_wait_min = round(sum(waits) / len(waits), 2) if waits else 0.0

    @api.depends("company_id")
    def _compute_token_stats(self):
        Token = self.env["clinic.queue.token"]
        today = fields.Date.context_today(self)
        for p in self:
            p.token_today_count = 0
            p.token_last_id = False
            if not p.id:
                continue

            # Tokens today
            dom_today = [
                ("patient_id", "=", p.id),
                ("company_id", "=", self.env.company.id),
                ("token_date", "=", today),
            ]
            p.token_today_count = Token.search_count(dom_today)

            # Last token
            dom_last = [
                ("patient_id", "=", p.id),
                ("company_id", "=", self.env.company.id),
            ]
            last_tok = Token.search(dom_last, limit=1, order="token_date desc, token_number desc, id desc")
            if last_tok:
                p.token_last_id = last_tok.id

    @api.depends("company_id")
    def _compute_next_appointment(self):
        """
        Find the next appointment in the future for this patient (current company).
        Assumes model clinic.appointment provides a datetime field, commonly 'start_datetime' or 'start_time'.
        We will try common field names defensively.
        """
        App = self.env["clinic.appointment"]
        now = fields.Datetime.now()
        # Determine best-guess start field
        start_field = "start_datetime" if "start_datetime" in App._fields else \
                      ("start_time" if "start_time" in App._fields else None)

        for p in self:
            p.next_appointment_id = False
            if not start_field or not p.id:
                continue
            dom = [
                ("patient_id", "=", p.id),
                ("company_id", "=", self.env.company.id),
                (start_field, ">", now),
            ]
            nxt = App.search(dom, limit=1, order=f"{start_field} asc, id asc")
            if nxt:
                p.next_appointment_id = nxt.id

    @api.depends("queue_active_count")
    def _compute_flags(self):
        for p in self:
            p.has_active_queue = p.queue_active_count > 0

    # -------------------------------------------------------------------------
    # ONCHANGE / VALIDATIONS
    # -------------------------------------------------------------------------
    @api.constrains("preferred_doctor_id")
    def _check_preferred_doctor(self):
        for rec in self:
            if rec.preferred_doctor_id and not getattr(rec.preferred_doctor_id, "is_doctor", False):
                raise ValidationError(_("Preferred Doctor must be a doctor (is_doctor = True)."))

    # -------------------------------------------------------------------------
    # QUICK ACTIONS / SHORTCUTS
    # -------------------------------------------------------------------------
    def _default_queue_vals(self):
        """Compose default queue values using partner preferences."""
        self.ensure_one()
        vals = {
            "patient_id": self.id,
            "company_id": self.env.company.id,
            "queue_type": self.default_queue_type or "general",
            "channel": self.default_channel or ("telemedicine" if self.is_company else "walkin"),
            "priority": self.default_priority or "1",
        }
        if self.preferred_doctor_id:
            vals["doctor_id"] = self.preferred_doctor_id.id
        if self.preferred_room_type_id:
            # stage may auto-assign a room type; we pass hint via stage or keep as context
            pass
        return vals

    def action_quick_issue_token(self):
        """
        Create and issue a queue token for this patient (no queue yet).
        Returns an action opening the token form.
        """
        self.ensure_one()
        if self.queue_blacklisted:
            raise UserError(_("This patient is blacklisted from receiving tokens/queues."))

        Token = self.env["clinic.queue.token"]
        vals = {
            "patient_id": self.id,
            "company_id": self.env.company.id,
            "queue_type": self.default_queue_type or "general",
            "channel": self.default_channel or ("telemedicine" if self.is_company else "walkin"),
            "priority": self.default_priority or "1",
            "doctor_id": self.preferred_doctor_id.id if self.preferred_doctor_id else False,
            "stage_id": False,  # let queue creation decide default stage later
            "state": "issued",
        }
        tok = Token.create({k: v for k, v in vals.items() if v or k in ("company_id", "queue_type", "channel")})
        # Return action
        act = self.env.ref("clinic_queue_room.action_clinic_queue_token_form", raise_if_not_found=False)
        if act:
            data = act.read()[0]
            data.update({"res_id": tok.id, "view_mode": "form"})
            return data
        return {
            "type": "ir.actions.act_window",
            "name": _("Token"),
            "res_model": "clinic.queue.token",
            "view_mode": "form,list",
            "res_id": tok.id,
            "target": "current",
        }

    def action_create_queue(self):
        """
        Create a queue for this patient directly (without token).
        """
        self.ensure_one()
        if self.queue_blacklisted:
            raise UserError(_("This patient is blacklisted from receiving tokens/queues."))

        Queue = self.env["clinic.queue"]
        vals = self._default_queue_vals()
        if self.preferred_doctor_id:
            vals["doctor_id"] = self.preferred_doctor_id.id
        if self.preferred_room_type_id:
            # We don't set room here; stage hooks may auto-assign based on type.
            pass

        q = Queue.create(vals)
        # Run stage enter hooks if any
        try:
            if q.stage_id and hasattr(q.stage_id, "_run_on_enter_hooks"):
                q.stage_id._run_on_enter_hooks(q)
        except Exception as e:
            q.message_post(body=_("Stage enter hooks failed: %s") % e)

        # Open form
        act = self.env.ref("clinic_queue_room.action_clinic_queue_form", raise_if_not_found=False)
        if act:
            data = act.read()[0]
            data.update({"res_id": q.id, "view_mode": "form"})
            return data
        return {
            "type": "ir.actions.act_window",
            "name": _("Queue"),
            "res_model": "clinic.queue",
            "view_mode": "form,list,kanban",
            "res_id": q.id,
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # SMART BUTTONS — Views
    # -------------------------------------------------------------------------
    def action_view_queues(self):
        self.ensure_one()
        action = self.env.ref("clinic_queue_room.action_clinic_queue_tree", raise_if_not_found=False)
        domain = [("patient_id", "=", self.id)]
        if action:
            res = action.read()[0]
            res.update({"domain": domain, "context": {"default_patient_id": self.id}})
            return res
        return {
            "type": "ir.actions.act_window",
            "name": _("Queues"),
            "res_model": "clinic.queue",
            "view_mode": "list,form,kanban",
            "domain": domain,
            "context": {"default_patient_id": self.id},
        }

    def action_view_active_queues(self):
        self.ensure_one()
        action = self.env.ref("clinic_queue_room.action_clinic_queue_tree", raise_if_not_found=False)
        domain = [
            ("patient_id", "=", self.id),
            ("state", "in", ["waiting", "in_progress", "on_hold"]),
        ]
        if action:
            res = action.read()[0]
            res.update({"domain": domain, "context": {"default_patient_id": self.id}})
            return res
        return {
            "type": "ir.actions.act_window",
            "name": _("Active Queues"),
            "res_model": "clinic.queue",
            "view_mode": "list,form,kanban",
            "domain": domain,
        }

    def action_view_tokens(self):
        self.ensure_one()
        action = self.env.ref("clinic_queue_room.action_clinic_queue_token_tree", raise_if_not_found=False)
        domain = [("patient_id", "=", self.id)]
        if action:
            res = action.read()[0]
            res.update({"domain": domain, "context": {"default_patient_id": self.id}})
            return res
        return {
            "type": "ir.actions.act_window",
            "name": _("Tokens"),
            "res_model": "clinic.queue.token",
            "view_mode": "list,form",
            "domain": domain,
            "context": {"default_patient_id": self.id},
        }

    def action_view_room_assignments(self):
        self.ensure_one()
        action = self.env.ref("clinic_queue_room.action_clinic_room_assignment_tree", raise_if_not_found=False)
        domain = [("patient_id", "=", self.id)]
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
            raise UserError(_("No upcoming appointment found for this patient."))
        act = self.env.ref("clinic_queue_room.action_clinic_appointment_form", raise_if_not_found=False)
        if act:
            data = act.read()[0]
            data.update({"res_id": self.next_appointment_id.id, "view_mode": "form"})
            return data
        # fallback (if action is not provided by this addon)
        return {
            "type": "ir.actions.act_window",
            "name": _("Appointment"),
            "res_model": "clinic.appointment",
            "view_mode": "form,list",
            "res_id": self.next_appointment_id.id,
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # DISPLAY HELPERS
    # -------------------------------------------------------------------------
    def _clinic_display_badges(self):
        """
        Optional helper for kanban badges (can be used by qweb views).
        Returns a dict of small flags (e.g., VIP, Active Queue, Blacklisted)
        """
        self.ensure_one()
        return {
            "vip": bool(self.is_vip),
            "active_queue": bool(self.has_active_queue),
            "blacklisted": bool(self.queue_blacklisted),
            "tokens_today": int(self.token_today_count or 0),
        }
