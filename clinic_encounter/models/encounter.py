# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/encounter.py
#
# Satu header Encounter yang menyatukan:
# - SOAP/Assessment, Rencana Prosedur (clinic.encounter.procedure), Sesi Tindakan (clinic.procedure.session)
# - Consent, Checklist, Result Document, Adverse Event (digabung dari class _inherit ke clinic.encounter)
# - Roll-up Billing & Smart Buttons portal/billing
#
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicEncounter(models.Model):
    _name = "clinic.encounter"
    _description = "Clinic Encounter"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Company
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Encounter #",
        required=True,
        copy=False,
        index=True,
        default=lambda self: _("New"),
        tracking=True,
    )
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Patient & Clinical Context
    # -------------------------------------------------------------------------
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Patient Partner",
        related="patient_id.partner_id",
        store=True,
        readonly=True,
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Provider/Doctor",
        ondelete="restrict",
        index=True,
        tracking=True,
        help="Primary provider responsible for this encounter.",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        default=lambda self: self.env.user,
        tracking=True,
        help="Staff responsible (owner) for workflow & coordination.",
    )
    appointment_id = fields.Many2one(
        "booking.booking",
        string="Appointment",
        ondelete="set null",
        index=True,
        help="If this encounter originates from an appointment/booking.",
    )

    # Tautan data klinis lain (diisi modul lain atau wizard)
    vital_ids = fields.One2many("clinic.patient.vital", "encounter_id", string="Vitals")
    diagnosis_note = fields.Text(string="Initial Assessment", help="Short free-text note (complementary to SOAP).")

    # -------------------------------------------------------------------------
    # Scheduling & Progress (Stage-driven)
    # -------------------------------------------------------------------------
    stage_id = fields.Many2one(
        "clinic.encounter.stage",
        string="Stage",
        ondelete="restrict",
        tracking=True,
        index=True,
        help="Functional stage of the encounter (Draft/In Progress/Done/Cancelled).",
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        compute="_compute_state",
        store=True,
        tracking=True,
        help="Derived from the selected stage.",
    )

    date_planned_start = fields.Datetime(string="Planned Start", help="Planned start (from booking/triage).")
    date_planned_end = fields.Datetime(string="Planned End", help="Planned end of the encounter.")
    date_start = fields.Datetime(string="Check-in / Start", tracking=True, help="Set when starting.")
    date_end = fields.Datetime(string="Check-out / End", tracking=True, help="Set when finishing.")
    planned_duration = fields.Float(string="Planned Duration (min)", help="Estimated duration in minutes.")
    actual_duration = fields.Float(
        string="Actual Duration (min)",
        compute="_compute_actual_duration",
        store=True,
        help="Computed from Start → End in minutes.",
    )

    # Visual (Kanban)
    color = fields.Integer(string="Color Index")
    priority = fields.Selection(
        [("0", "Normal"), ("1", "High"), ("2", "Urgent")],
        string="Priority",
        default="0",
        index=True,
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Planning (Procedures) & Execution (Sessions)
    # -------------------------------------------------------------------------
    procedure_line_ids = fields.One2many(
        "clinic.encounter.procedure",
        "encounter_id",
        string="Planned Procedures",
        help="Planned clinical procedures for this encounter.",
    )
    session_ids = fields.One2many(
        "clinic.procedure.session",
        "encounter_id",
        string="Procedure Sessions",
        help="Execution sessions spawned from planned procedures.",
    )
    procedure_count = fields.Integer(compute="_compute_counts", string="Procedure Plans", store=True)
    session_count = fields.Integer(compute="_compute_counts", string="Sessions", store=True)

    # -------------------------------------------------------------------------
    # MERGED: Consent / Checklist / Result / Adverse Event (dari *_inherit)
    # -------------------------------------------------------------------------
    # Consent
    consent_ok = fields.Boolean(
        string="Consent Obtained",
        tracking=True,
        help="Checked when patient consent has been captured for the planned procedures.",
    )
    consent_ids = fields.One2many("clinic.consent.document", "encounter_id", string="Consents")
    consent_count = fields.Integer(compute="_compute_consent_count", string="Consents", store=False)

    # Checklist
    checklist_ids = fields.One2many("clinic.checklist", "encounter_id", string="Checklists")
    checklist_count = fields.Integer(compute="_compute_checklist_count", string="Checklists", store=False)

    # Results
    result_ids = fields.One2many("clinic.result.document", "encounter_id", string="Results")
    result_count = fields.Integer(compute="_compute_result_count", string="Results", store=False)

    # Adverse Events
    ae_ids = fields.One2many("clinic.adverse.event", "encounter_id", string="Adverse Events")
    ae_count = fields.Integer(string="Adverse Events", compute="_compute_ae_count", store=False)

    # -------------------------------------------------------------------------
    # Financials (roll-up dari procedure/session)
    # -------------------------------------------------------------------------
    amount_untaxed = fields.Monetary(
        string="Untaxed Amount", compute="_compute_amounts", store=True, currency_field="currency_id"
    )
    amount_tax = fields.Monetary(
        string="Taxes", compute="_compute_amounts", store=True, currency_field="currency_id"
    )
    amount_total = fields.Monetary(
        string="Total", compute="_compute_amounts", store=True, currency_field="currency_id"
    )
    amount_invoiced = fields.Monetary(
        string="Invoiced", compute="_compute_billing_progress", store=True, currency_field="currency_id"
    )
    amount_to_invoice = fields.Monetary(
        string="To Invoice", compute="_compute_billing_progress", store=True, currency_field="currency_id"
    )
    invoice_count = fields.Integer(compute="_compute_billing_progress", string="Invoices", store=True)

    # -------------------------------------------------------------------------
    # Notes
    # -------------------------------------------------------------------------
    internal_note = fields.Text(string="Internal Notes")

    # --- Legacy bridge to clinic.treatment (compat) ---
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment (Legacy)",
        index=True,
        ondelete="set null",
        help="Compatibility field for legacy modules that reference encounters via One2many(..., inverse_name='treatment_id')."
    )

    # -------------------------------------------------------------------------
    # Computations
    # -------------------------------------------------------------------------
    @api.depends("stage_id.state")
    def _compute_state(self):
        for rec in self:
            rec.state = rec.stage_id.state if rec.stage_id and rec.stage_id.state else "draft"

    @api.depends("date_start", "date_end")
    def _compute_actual_duration(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end >= rec.date_start:
                delta = rec.date_end - rec.date_start
                rec.actual_duration = (delta.total_seconds() / 60.0)
            else:
                rec.actual_duration = 0.0

    @api.depends("procedure_line_ids.price_subtotal", "procedure_line_ids.price_tax", "procedure_line_ids.currency_id")
    def _compute_amounts(self):
        for rec in self:
            untaxed = 0.0
            tax = 0.0
            for line in rec.procedure_line_ids:
                untaxed += (line.price_subtotal or 0.0)
                tax += (getattr(line, "price_tax", 0.0) or 0.0)
            rec.amount_untaxed = untaxed
            rec.amount_tax = tax
            rec.amount_total = untaxed + tax

    @api.depends("procedure_line_ids.invoice_line_ids.move_id.state")
    def _compute_billing_progress(self):
        for rec in self:
            invoices = self.env["account.move"]
            amount_invoiced = 0.0
            for line in rec.procedure_line_ids:
                for invl in getattr(line, "invoice_line_ids", []):
                    if invl.move_id and invl.move_id.state not in ("draft", "cancel"):
                        invoices |= invl.move_id
                        if invl.currency_id == rec.currency_id:
                            amount_invoiced += invl.price_subtotal
                        else:
                            amount_invoiced += invl.currency_id._convert(
                                invl.price_subtotal, rec.currency_id, rec.company_id, invl.move_id.invoice_date or fields.Date.today()
                            )
            rec.invoice_count = len(invoices)
            rec.amount_invoiced = amount_invoiced
            rec.amount_to_invoice = max(rec.amount_total - amount_invoiced, 0.0)

    @api.depends("procedure_line_ids", "session_ids")
    def _compute_counts(self):
        for rec in self:
            rec.procedure_count = len(rec.procedure_line_ids)
            rec.session_count = len(rec.session_ids)

    # Merged counters
    def _compute_consent_count(self):
        for rec in self:
            rec.consent_count = len(rec.consent_ids)

    def _compute_checklist_count(self):
        for rec in self:
            rec.checklist_count = len(rec.checklist_ids)

    def _compute_result_count(self):
        for rec in self:
            rec.result_count = len(rec.result_ids)

    def _compute_ae_count(self):
        for rec in self:
            rec.ae_count = len(rec.ae_ids)

    # -------------------------------------------------------------------------
    # Onchange & Defaults
    # -------------------------------------------------------------------------
    @api.onchange("patient_id")
    def _onchange_patient(self):
        if self.patient_id and self.appointment_id and getattr(self.appointment_id, "doctor_id", False):
            self.doctor_id = self.appointment_id.doctor_id

    @api.onchange("appointment_id")
    def _onchange_appointment(self):
        appt = self.appointment_id
        if appt:
            if getattr(appt, "scheduled_start", False) and not self.date_planned_start:
                self.date_planned_start = appt.scheduled_start
            if getattr(appt, "scheduled_end", False) and not self.date_planned_end:
                self.date_planned_end = appt.scheduled_end
            if getattr(appt, "doctor_id", False) and not self.doctor_id:
                self.doctor_id = appt.doctor_id
            if getattr(appt, "priority", False) and not self.priority:
                self.priority = appt.priority

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    _constraint_uniq_encounter_name_company = models.Constraint(
        'unique(name, company_id)',
        'Encounter number must be unique per company.',
    )

    @api.constrains("date_planned_start", "date_planned_end")
    def _check_planned_dates(self):
        for rec in self:
            if rec.date_planned_start and rec.date_planned_end and rec.date_planned_end < rec.date_planned_start:
                raise ValidationError(_("Planned End cannot be earlier than Planned Start."))

    @api.constrains("date_start", "date_end")
    def _check_actual_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_("Check-out / End cannot be earlier than Check-in / Start."))

    @api.constrains("patient_id", "state")
    def _check_open_encounter_uniqueness(self):
        for rec in self:
            if rec.state in ("draft", "in_progress"):
                domain = [
                    ("id", "!=", rec.id),
                    ("patient_id", "=", rec.patient_id.id),
                    ("state", "in", ["draft", "in_progress"]),
                    ("company_id", "=", rec.company_id.id),
                ]
                if self.search_count(domain):
                    raise ValidationError(_("This patient already has an open encounter (Draft/In Progress) in this company."))

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if vals.get("name", _("New")) in (False, _("New")):
                vals["name"] = seq.next_by_code("clinic.encounter") or _("New")
        recs = super().create(vals_list)
        for rec in recs:
            try:
                rec.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Review Encounter"),
                    user_id=rec.user_id.id or self.env.user.id,
                    date_deadline=fields.Date.today(),
                )
            except Exception:
                pass
        return recs

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if "stage_id" in vals and rec.state == "done" and not rec.date_end:
                rec.date_end = fields.Datetime.now()
        return res

    # -------------------------------------------------------------------------
    # Button Actions / Workflow
    # -------------------------------------------------------------------------
    def action_set_to_draft(self):
        self._ensure_can_edit()
        stage = self._get_stage_by_state("draft")
        for rec in self:
            rec.write({"stage_id": stage.id if stage else rec.stage_id.id})
        return True

    def action_start(self):
        self._ensure_can_edit()
        stage = self._get_stage_by_state("in_progress")
        now = fields.Datetime.now()
        for rec in self:
            updates = {"stage_id": stage.id if stage else rec.stage_id.id}
            if not rec.date_start:
                updates["date_start"] = now
            rec.write(updates)
        return True

    def action_done(self):
        stage = self._get_stage_by_state("done")
        for rec in self:
            if not rec.procedure_line_ids and not rec.diagnosis_note:
                raise UserError(_("Cannot complete: please add at least a procedure plan or a clinical assessment."))
            updates = {"stage_id": stage.id if stage else rec.stage_id.id}
            if not rec.date_end:
                updates["date_end"] = fields.Datetime.now()
            rec.write(updates)
        return True

    def action_cancel(self, reason=None):
        stage = self._get_stage_by_state("cancelled")
        for rec in self:
            rec.write({"stage_id": stage.id if stage else rec.stage_id.id})
            if reason:
                note = (rec.internal_note or "") + "\n" + _("Cancelled: %s") % reason
                rec.internal_note = note.strip()
        return True

    # -------------------------------------------------------------------------
    # Smart Buttons & External Actions
    # -------------------------------------------------------------------------
    def action_open_procedures(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_encounter_procedure").read()[0]
        action["domain"] = [("encounter_id", "=", self.id)]
        action["context"] = {"default_encounter_id": self.id, "search_default_encounter_id": self.id}
        return action

    def action_open_sessions(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_procedure_session").read()[0]
        action["domain"] = [("encounter_id", "=", self.id)]
        action["context"] = {"default_encounter_id": self.id, "search_default_encounter_id": self.id}
        return action

    def action_open_billing(self):
        self.ensure_one()
        AccountMove = self.env["account.move"]
        invoices = AccountMove.search([
            ("invoice_origin", "=", self.name),
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("company_id", "=", self.company_id.id),
        ])
        if invoices:
            action = self.env.ref("account.action_move_out_invoice_type").read()[0]
            action["domain"] = [("id", "in", invoices.ids)]
            return action
        action = self.env.ref("clinic_encounter.action_generate_bill_wizard").read()[0]
        action["context"] = {"default_encounter_id": self.id}
        return action

    # MERGED: open* actions
    def action_open_consents(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_consent_document").read()[0]
        action["domain"] = [("encounter_id", "=", self.id)]
        action["context"] = {"default_encounter_id": self.id}
        return action

    def action_open_checklists(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_checklist").read()[0]
        action["domain"] = [("encounter_id", "=", self.id)]
        action["context"] = {"default_encounter_id": self.id}
        return action

    def action_open_results(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_result_document").read()[0]
        action["domain"] = [("encounter_id", "=", self.id)]
        action["context"] = {"default_encounter_id": self.id}
        return action

    def action_open_adverse_events(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_adverse_event").read()[0]
        action["domain"] = [("encounter_id", "=", self.id)]
        action["context"] = {"default_encounter_id": self.id}
        return action

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _ensure_can_edit(self):
        for rec in self:
            if rec.state in ("done", "cancelled"):
                raise UserError(_("Cannot change a completed/cancelled encounter."))

    def _get_stage_by_state(self, state_code):
        return self.env["clinic.encounter.stage"].search([("state", "=", state_code)], limit=1)

    def estimate_end_from_planned(self):
        for rec in self:
            if rec.date_planned_start and not rec.date_planned_end and rec.planned_duration:
                rec.date_planned_end = rec.date_planned_start + timedelta(minutes=rec.planned_duration)
        return True

    def push_activity_followup(self, summary=None, days=1, user=None):
        for rec in self:
            rec.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=summary or _("Follow up encounter"),
                user_id=(user.id if isinstance(user, models.BaseModel) else user) or rec.user_id.id or self.env.user.id,
                date_deadline=fields.Date.today() + timedelta(days=days),
            )
        return True

    # MERGED: Consent flag recompute
    def _recompute_consent_ok(self):
        """
        Set consent_ok = True jika ada consent SIGNED & belum expired untuk encounter ini.
        Consent generik atau yang mencakup prosedur mana pun dianggap valid untuk encounter-level gate.
        """
        Consent = self.env["clinic.consent.document"]
        for rec in self:
            valid_exists = bool(Consent.search_count([
                ("encounter_id", "=", rec.id),
                ("state", "=", "signed"),
                "|", ("date_expiry", "=", False), ("date_expiry", ">", fields.Datetime.now()),
            ]))
            rec.write({"consent_ok": valid_exists})

    # -------------------------------------------------------------------------
    # Name & Search
    # -------------------------------------------------------------------------
    @api.depends("name", "patient_id", "doctor_id")
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.name or ""]
            if rec.patient_id:
                parts.append(rec.patient_id.display_name)
            if rec.doctor_id:
                parts.append(_("by %s") % rec.doctor_id.display_name)
            rec.display_name = " — ".join([part for part in parts if part])

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        extra_domain = list(domain or [])
        name_domain = ["|", ("name", operator, name), ("patient_id.display_name", operator, name)]
        recs = self.search(name_domain + extra_domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]
