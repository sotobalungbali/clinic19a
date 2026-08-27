
# -*- coding: utf-8 -*-
# File: models/triage_session.py
#
# ClinicOne - Triage & Vitals Intake
# Model: clinic.triage.session
#
# Integration touchpoints:
# - Patient Management:        clinic.patient (or partner inheritance in clinic_patient)
# - Doctor & Scheduling:       clinic.doctor, clinic.appointment
# - Clinical Encounter:        clinic.encounter
# - Queue & Rooms:             clinic.queue.stage, clinic.room.type
# - Billing & Accounting:      account.move, product.product (fee hooks)
# - Tags & Levels (this add-on): clinic.triage.tag, clinic.triage.level
# - Vitals Intake (this add-on): clinic.vitals.intake (one2many child)
#
# All field labels, help texts, and messages are in English.

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicTriageSession(models.Model):
    _name = "clinic.triage.session"
    _description = "Clinic Triage Session"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "arrival_datetime desc, id desc"

    # -------------------------------------------------------------------------
    # Identity & Audit
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Triage Reference",
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _("New"),
        help="Unique reference generated from a sequence for each triage session."
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="If unchecked, the triage session will be hidden without being deleted."
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        help="Owning company for this triage session."
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True
    )

    # -------------------------------------------------------------------------
    # Core Links (integration hooks to other ClinicOne modules)
    # -------------------------------------------------------------------------
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        required=True,
        index=True,
        tracking=True,
        help="Patient being triaged. Provided by the Patient Management module."
    )
    # encounter_id = fields.Many2one(
    #     "clinic.encounter",
    #     string="Clinical Encounter",
    #     index=True,
    #     tracking=True,
    #     help="Linked clinical encounter that will consume this triage data."
    # )
    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Appointment",
        index=True,
        help="Appointment record to which this triage belongs, if any."
    )
    assigned_nurse_id = fields.Many2one(
        "res.users",
        string="Assigned Nurse",
        default=lambda self: self.env.user,
        tracking=True,
        help="User responsible for performing the triage."
    )
    assigned_doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Assigned Doctor",
        tracking=True,
        help="Doctor assigned to review triage results and continue the care."
    )

    # -------------------------------------------------------------------------
    # Triage Classification
    # -------------------------------------------------------------------------
    triage_level_id = fields.Many2one(
        "clinic.triage.level",
        string="Triage Level",
        index=True,
        tracking=True,
        help="Category describing urgency and target response time (e.g., Red, Yellow, Green, Blue)."
    )
    triage_tag_ids = fields.Many2many(
        "clinic.triage.tag",
        "clinic_triage_session_tag_rel",
        "session_id",
        "tag_id",
        string="Triage Tags",
        help="Optional tags for categorization (e.g., Trauma, Allergy, Pediatric)."
    )
    priority_score = fields.Integer(
        string="Priority Score",
        compute="_compute_priority_score",
        store=True,
        help="Auto-computed priority score; extendable to include vitals or custom rules."
    )

    # -------------------------------------------------------------------------
    # Timings & SLA
    # -------------------------------------------------------------------------
    arrival_datetime = fields.Datetime(
        string="Arrival Time",
        default=fields.Datetime.now,
        required=True,
        tracking=True,
        index=True,
        help="Time when the patient arrived/was registered for triage."
    )
    start_datetime = fields.Datetime(
        string="Triage Start",
        tracking=True,
        help="Time when triage assessment actually started."
    )
    end_datetime = fields.Datetime(
        string="Triage End",
        tracking=True,
        help="Time when triage assessment completed."
    )
    wait_time_minutes = fields.Float(
        string="Waiting Time (min)",
        compute="_compute_wait_and_duration",
        store=True,
        help="Minutes from Arrival Time to Triage Start."
    )
    triage_duration_minutes = fields.Float(
        string="Triage Duration (min)",
        compute="_compute_wait_and_duration",
        store=True,
        help="Minutes from Triage Start to Triage End."
    )

    sla_target_datetime = fields.Datetime(
        string="SLA Target Time",
        compute="_compute_sla_fields",
        store=True,
        help="Deadline derived from triage level SLA (Arrival Time + SLA minutes)."
    )
    sla_breached = fields.Boolean(
        string="SLA Breached",
        compute="_compute_sla_fields",
        store=True,
        help="True if triage started after the SLA target time."
    )

    # -------------------------------------------------------------------------
    # Clinical Information (basic intake)
    # -------------------------------------------------------------------------
    reason_for_visit = fields.Text(
        string="Reason for Visit",
        help="Short description of the patient's reason for visit as communicated at intake."
    )
    chief_complaint = fields.Text(
        string="Chief Complaint",
        help="Primary complaint summarizing the patient's symptoms."
    )
    allergies = fields.Text(
        string="Known Allergies",
        help="Known allergies declared during intake or sourced from patient record."
    )
    current_medications = fields.Text(
        string="Current Medications",
        help="Current medications declared during intake or sourced from patient record."
    )
    internal_notes = fields.Html(
        string="Internal Notes",
        help="Internal notes for caregivers; not intended for patient-facing documents."
    )

    # -------------------------------------------------------------------------
    # Vitals Link (child records to be defined in clinic.vitals.intake)
    # -------------------------------------------------------------------------
    vitals_ids = fields.One2many(
        "clinic.vitals.intake",
        "triage_session_id",
        string="Vital Signs",
        help="Captured vital signs linked to this triage session."
    )
    has_abnormal_vitals = fields.Boolean(
        string="Abnormal Vitals",
        compute="_compute_has_abnormal_vitals",
        store=True,
        help="True if any linked vital sign is marked as abnormal."
    )

    # -------------------------------------------------------------------------
    # Queue & Rooms Hints (optional)
    # -------------------------------------------------------------------------
    recommended_room_type_id = fields.Many2one(
        "clinic.room.type",
        string="Recommended Room Type",
        help="Recommended room type suggested by the triage level and tags."
    )
    queue_stage_id = fields.Many2one(
        "clinic.queue.stage",
        string="Queue Stage",
        help="Current stage in queue management, if queue module is used."
    )

    # -------------------------------------------------------------------------
    # Billing Hooks (optional)
    # -------------------------------------------------------------------------
    is_billable = fields.Boolean(
        string="Billable",
        default=False,
        help="Enable if triage assessment should be billed."
    )
    triage_fee = fields.Monetary(
        string="Triage Fee",
        help="Optional triage fee to charge if Billable is enabled (defaults from level or tags)."
    )
    invoice_id = fields.Many2one(
        "account.move",
        string="Customer Invoice",
        help="Generated invoice for this triage session, if applicable."
    )

    # -------------------------------------------------------------------------
    # State Machine
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("referred", "Referred"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
        help="Lifecycle status of the triage session."
    )

    # -------------------------------------------------------------------------
    # SQL Constraints
    # -------------------------------------------------------------------------
    _name_uniq = models.Constraint(
        "UNIQUE(name)",
        "Triage Reference must be unique.",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    @api.constrains("arrival_datetime", "start_datetime", "end_datetime")
    def _check_timings(self):
        for rec in self:
            if rec.start_datetime and rec.arrival_datetime and rec.start_datetime < rec.arrival_datetime:
                raise ValidationError(_("Triage Start cannot be earlier than Arrival Time."))
            if rec.end_datetime and rec.start_datetime and rec.end_datetime < rec.start_datetime:
                raise ValidationError(_("Triage End cannot be earlier than Triage Start."))

    @api.constrains("patient_id", "company_id")
    def _check_company_consistency(self):
        for rec in self:
            # If the patient record carries a company, enforce match.
            patient_company = getattr(rec.patient_id, "company_id", False)
            if patient_company and rec.company_id and patient_company != rec.company_id:
                raise ValidationError(_("Patient's company must match the triage session company."))

    # -------------------------------------------------------------------------
    # Compute Methods
    # -------------------------------------------------------------------------
    @api.depends("arrival_datetime", "start_datetime", "end_datetime")
    def _compute_wait_and_duration(self):
        for rec in self:
            wait = 0.0
            duration = 0.0
            if rec.arrival_datetime and rec.start_datetime:
                delta = fields.Datetime.to_datetime(rec.start_datetime) - fields.Datetime.to_datetime(rec.arrival_datetime)
                wait = max(delta.total_seconds() / 60.0, 0.0)
            if rec.start_datetime and rec.end_datetime:
                delta = fields.Datetime.to_datetime(rec.end_datetime) - fields.Datetime.to_datetime(rec.start_datetime)
                duration = max(delta.total_seconds() / 60.0, 0.0)
            rec.wait_time_minutes = wait
            rec.triage_duration_minutes = duration

    @api.depends("triage_level_id", "triage_level_id.sla_minutes", "arrival_datetime", "start_datetime")
    def _compute_sla_fields(self):
        for rec in self:
            sla_deadline = False
            breached = False
            sla_minutes = int(getattr(rec.triage_level_id, "sla_minutes", 0) or 0)
            if rec.arrival_datetime and sla_minutes > 0:
                sla_deadline = fields.Datetime.to_datetime(rec.arrival_datetime) + timedelta(minutes=sla_minutes)
                if rec.start_datetime and rec.start_datetime > sla_deadline:
                    breached = True
            rec.sla_target_datetime = sla_deadline
            rec.sla_breached = breached

    @api.depends("vitals_ids.is_abnormal")
    def _compute_has_abnormal_vitals(self):
        for rec in self:
            rec.has_abnormal_vitals = any(v.is_abnormal for v in rec.vitals_ids)

    @api.depends("triage_level_id", "triage_level_id.weight", "has_abnormal_vitals")
    def _compute_priority_score(self):
        for rec in self:
            base = int(getattr(rec.triage_level_id, "weight", 0) or 0)
            bonus = 5 if rec.has_abnormal_vitals else 0
            rec.priority_score = base + bonus

    # -------------------------------------------------------------------------
    # Defaulting & Onchange helpers
    # -------------------------------------------------------------------------
    def _get_level_defaults(self, level):
        """Return dict of defaults inferred from triage level."""
        if not level:
            return {}
        vals = {}
        # SLA & queue/room hints
        if level.default_queue_stage_id:
            vals["queue_stage_id"] = level.default_queue_stage_id.id
        if level.recommended_room_type_id:
            vals["recommended_room_type_id"] = level.recommended_room_type_id.id
        # Billing defaults
        if level.billable:
            vals["is_billable"] = True
            if level.default_fee:
                vals["triage_fee"] = level.default_fee
        return vals

    @api.onchange("triage_level_id")
    def _onchange_triage_level_id(self):
        """When level changes, apply non-destructive defaults."""
        if self.triage_level_id:
            vals = self._get_level_defaults(self.triage_level_id)
            for k, v in vals.items():
                # Do not override if already set by user
                if not getattr(self, k):
                    setattr(self, k, v)

    # -------------------------------------------------------------------------
    # CRUD Overrides
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq_code = "clinic.triage.session"  # defined in data/triage_sequence.xml
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            # Sequence
            if vals.get("name", _("New")) in (False, _("New")):
                vals["name"] = self.env["ir.sequence"].next_by_code(seq_code) or _("New")
            # Apply level defaults on create
            level = None
            if vals.get("triage_level_id"):
                level = self.env["clinic.triage.level"].browse(vals["triage_level_id"])
                vals.update({k: v for k, v in self._get_level_defaults(level).items() if k not in vals})
        records = super().create(vals_list)
        for rec in records:
            # Post creation note
            rec.message_post(
                body=_("Triage session created with reference: <b>%s</b>.") % (rec.name,),
                subtype_xmlid="mail.mt_note",
            )
            # Optionally create a default activity from the level
            level = rec.triage_level_id
            if level and level.default_activity_type_id:
                rec.activity_schedule(
                    activity_type_id=level.default_activity_type_id.id,
                    summary=_("Follow-up for triage level %s") % (level.display_name,),
                )
        return records

    def write(self, vals):
        res = super().write(vals)
        # Post concise change logs for key fields
        tracked_fields = {"state", "triage_level_id", "assigned_nurse_id", "assigned_doctor_id", "queue_stage_id"}
        if tracked_fields.intersection(vals.keys()):
            for rec in self:
                msg_parts = []
                if "state" in vals:
                    msg_parts.append(_("Status changed to: %s") % dict(self._fields["state"].selection).get(rec.state))
                if "triage_level_id" in vals and rec.triage_level_id:
                    msg_parts.append(_("Triage Level: %s") % rec.triage_level_id.display_name)
                if "assigned_nurse_id" in vals and rec.assigned_nurse_id:
                    msg_parts.append(_("Assigned Nurse: %s") % rec.assigned_nurse_id.name)
                if "assigned_doctor_id" in vals and rec.assigned_doctor_id:
                    msg_parts.append(_("Assigned Doctor: %s") % rec.assigned_doctor_id.display_name)
                if "queue_stage_id" in vals and rec.queue_stage_id:
                    msg_parts.append(_("Queue Stage: %s") % rec.queue_stage_id.display_name)
                if msg_parts:
                    rec.message_post(body="<br/>".join(msg_parts), subtype_xmlid="mail.mt_note")
        # If triage level changed, apply defaults (non-destructive)
        if "triage_level_id" in vals and vals["triage_level_id"]:
            for rec in self:
                defaults = rec._get_level_defaults(rec.triage_level_id)
                to_write = {}
                for k, v in defaults.items():
                    if not getattr(rec, k):
                        to_write[k] = v
                if to_write:
                    super(ClinicTriageSession, rec).write(to_write)
        return res

    # -------------------------------------------------------------------------
    # Actions (State Transitions)
    # -------------------------------------------------------------------------
    def action_start(self):
        for rec in self:
            if rec.state not in ("draft", "referred"):
                raise ValidationError(_("Only Draft or Referred sessions can be started."))
            values = {"state": "in_progress"}
            if not rec.start_datetime:
                values["start_datetime"] = fields.Datetime.now()
            rec.write(values)

    def action_complete(self):
        for rec in self:
            if rec.state != "in_progress":
                raise ValidationError(_("Only In Progress sessions can be completed."))
            values = {"state": "completed"}
            if not rec.end_datetime:
                values["end_datetime"] = fields.Datetime.now()
            rec.write(values)

    def action_refer(self):
        for rec in self:
            if rec.state not in ("draft", "in_progress"):
                raise ValidationError(_("Only Draft or In Progress sessions can be referred."))
            rec.write({"state": "referred"})

    def action_cancel(self):
        for rec in self:
            if rec.state == "completed":
                raise ValidationError(_("Completed sessions cannot be cancelled."))
            rec.write({"state": "cancelled"})

    def action_reopen(self):
        for rec in self:
            if rec.state not in ("completed", "cancelled"):
                raise ValidationError(_("Only Completed or Cancelled sessions can be reopened."))
            rec.write({"state": "draft"})

    # Optional: quick invoice creation if billable
    def action_create_invoice(self):
        """Create a customer invoice for the triage session if billable.
        This method assumes standard Odoo accounting flows.
        """
        for rec in self:
            if rec.invoice_id:
                raise ValidationError(_("An invoice already exists for this triage session."))
            if not rec.is_billable:
                raise ValidationError(_("This triage session is not marked as billable."))
            # Resolve product/price: from level or tags (first billable tag), fallback to triage_fee only
            product = False
            price = rec.triage_fee or 0.0

            if rec.triage_level_id and rec.triage_level_id.billable and rec.triage_level_id.product_id:
                product = rec.triage_level_id.product_id
                price = rec.triage_level_id.default_fee or price

            if not product:
                billable_tag = next((t for t in rec.triage_tag_ids if t.billable and t.product_id), False)
                if billable_tag:
                    product = billable_tag.product_id
                    price = billable_tag.default_fee or price

            if not product and not price:
                raise ValidationError(_("No product or fee is configured for billing this triage session."))

            # Determine partner/customer
            partner = getattr(rec.patient_id, "partner_id", False) or getattr(rec.patient_id, "id", False)
            if not partner:
                raise ValidationError(_("Cannot determine the customer partner from the patient."))

            # Prepare invoice values
            move_vals = {
                "move_type": "out_invoice",
                "partner_id": partner.id if hasattr(partner, "id") else partner,
                "invoice_origin": rec.name,
                "invoice_line_ids": [],
                "company_id": rec.company_id.id,
            }

            # Prepare line
            if product:
                line_vals = {
                    "product_id": product.id,
                    "name": product.display_name or _("Triage Service"),
                    "quantity": 1.0,
                    "price_unit": price or product.lst_price,
                }
            else:
                # Service without product
                line_vals = {
                    "name": _("Triage Service"),
                    "quantity": 1.0,
                    "price_unit": price,
                }

            move_vals["invoice_line_ids"].append((0, 0, line_vals))

            invoice = self.env["account.move"].create(move_vals)
            rec.write({"invoice_id": invoice.id})
            rec.message_post(
                body=_("Invoice created: <b>%s</b>.") % (invoice.display_name,),
                subtype_xmlid="mail.mt_note",
            )
        return True

    def action_open_invoice(self):
        """Open the invoice linked to this triage session."""
        self.ensure_one()
        if not self.invoice_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.invoice_id.id,
            "view_mode": "form",
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # UI Helpers
    # -------------------------------------------------------------------------
    @api.depends("name", "patient_id", "patient_id.name", "triage_level_id", "triage_level_id.name")
    def _compute_display_name(self):
        """Build a useful Odoo 19 display label for triage sessions."""
        for rec in self:
            parts = [rec.name or _("New")]
            if rec.patient_id:
                parts.append(rec.patient_id.display_name)
            if rec.triage_level_id:
                parts.append("[%s]" % rec.triage_level_id.display_name)
            rec.display_name = " - ".join(parts)

    def name_get(self):
        """Compatibility wrapper for older ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]

    @api.model
    def _name_search_domain(self, name, operator="ilike"):
        """Search by triage reference or patient display name."""
        return ["|", ("name", operator, name), ("patient_id", operator, name)]

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        """Odoo 19-compatible name search while preserving ClinicOne behavior."""
        search_domain = list(domain or [])
        if name:
            search_domain = self._name_search_domain(name, operator=operator) + search_domain
        records = self.search(search_domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in records]
