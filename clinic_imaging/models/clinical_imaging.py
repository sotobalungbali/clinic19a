# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# =============================================================================
# Core Clinical Imaging model
# =============================================================================
class ClinicalImaging(models.Model):
    """
    Core model for Clinical Imaging Management in ClinicOne (Odoo 18 CE).

    Represents a single clinical imaging order/record for a patient,
    covering lifecycle from request to review, with integration points
    to the broader ClinicOne suite (appointment, encounter, treatment,
    procedure session, eMAR/prescription order, consent, billing, portal).
    """
    _name = "clinical.imaging"
    _description = "Clinical Imaging"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "request_datetime desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Company
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Imaging Number",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        help="Unique identifier generated from sequence at creation time.",
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="If unchecked, the imaging record is archived from regular views.",
    )

    # -------------------------------------------------------------------------
    # Patient & Care Team
    # -------------------------------------------------------------------------
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        required=True,
        index=True,
        domain=[("is_company", "=", False), ("is_patient", "=", True)],
        help="Linked patient (res.partner) flagged with 'Is a Patient'.",
        tracking=True,
    )
    doctor_id = fields.Many2one(
        "hr.employee",
        string="Responsible Doctor",
        domain=[("is_doctor", "=", True)],
        help="Doctor in charge of this imaging order.",
        tracking=True,
    )
    technician_id = fields.Many2one(
        "hr.employee",
        string="Imaging Technician",
        domain=[("is_imaging_technician", "=", True)],
        help="Technician who performs the imaging acquisition.",
        tracking=True,
    )

    # Membership / coverage (optional)
    # membership_id = fields.Many2one(
    #     "clinic.membership",
    #     string="Membership",
    #     help="Membership used for coverage/benefit of this imaging, if any.",
    # )

    # -------------------------------------------------------------------------
    # Clinical Context (cross-module hooks)
    # -------------------------------------------------------------------------
    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Appointment",
        help="Appointment related to this imaging (if scheduled).",
    )
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Clinical Encounter",
        help="Encounter during which imaging is requested or reviewed.",
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        help="Treatment plan that references this imaging.",
    )
    procedure_session_id = fields.Many2one(
        "clinic.procedure.session",
        string="Procedure Session",
        help="Procedure/Treatment session tied to this imaging.",
    )
    prescription_order_id = fields.Many2one(
        "clinic.emar.order",
        string="Prescription/Order (eMAR)",
        help="Prescription/Order authorizing this imaging.",
    )
    consent_id = fields.Many2one(
        "clinic.consent.form",
        string="Consent",
        help="Patient consent record for the imaging procedure.",
    )

    # -------------------------------------------------------------------------
    # Imaging Specification
    # -------------------------------------------------------------------------
    imaging_type_id = fields.Many2one(
        "clinical.imaging.type",
        string="Imaging Type",
        required=True,
        help="Type of imaging (e.g., X-Ray, CT, MRI, Ultrasound).",
        tracking=True,
    )
    device_id = fields.Many2one(
        "clinical.imaging.device",
        string="Imaging Device",
        help="Imaging device used for acquisition.",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Billable Service",
        domain=[("type", "=", "service")],
        help="Service product used for pricing and invoicing.",
    )
    priority = fields.Selection(
        [
            ("0", "Normal"),
            ("1", "High"),
            ("2", "Urgent"),
            ("3", "Emergency"),
        ],
        string="Priority",
        default="0",
        help="Clinical priority to schedule and perform the imaging.",
        tracking=True,
    )

    # DICOM basics (high-level; detailed metadata lives in study/series/image models)
    dicom_study_uid = fields.Char(
        string="DICOM Study UID",
        help="DICOM Study Instance UID, if available from RIS/PACS.",
        copy=False,
        index=True,
    )
    dicom_accession_number = fields.Char(
        string="Accession Number",
        help="Accession Number assigned by RIS/PACS (if integrated).",
        copy=False,
        index=True,
    )

    # -------------------------------------------------------------------------
    # Dates & SLA
    # -------------------------------------------------------------------------
    request_datetime = fields.Datetime(
        string="Requested At",
        default=fields.Datetime.now,
        required=True,
        help="Datetime when the imaging was requested.",
        tracking=True,
    )
    scheduled_datetime = fields.Datetime(
        string="Scheduled At",
        help="Planned datetime to perform the imaging.",
        tracking=True,
    )
    performed_datetime = fields.Datetime(
        string="Performed At",
        help="Datetime when the imaging acquisition was completed.",
        tracking=True,
    )
    reviewed_datetime = fields.Datetime(
        string="Reviewed At",
        help="Datetime when the imaging was reviewed by the doctor.",
        tracking=True,
    )
    expected_done_datetime = fields.Datetime(
        string="Expected Completion",
        help="Expected completion time used for SLA tracking and reminders.",
    )
    duration_minutes = fields.Integer(
        string="Duration (min)",
        help="Actual duration in minutes for the acquisition.",
    )
    is_overdue = fields.Boolean(
        string="Overdue",
        compute="_compute_is_overdue",
        help="Checked when the record missed its expected completion or review time.",
        store=True,
    )

    # -------------------------------------------------------------------------
    # Clinical Content
    # -------------------------------------------------------------------------
    clinical_indication = fields.Text(
        string="Clinical Indication",
        help="Reason for imaging; the clinical question to be answered.",
    )
    notes = fields.Text(
        string="Internal Notes",
        help="Internal notes for staff.",
    )
    findings_summary = fields.Text(
        string="Findings (Summary)",
        help="Brief summary of key findings; the full report is kept in the report model.",
        tracking=True,
    )
    recommendations = fields.Text(
        string="Recommendations",
        help="Clinical recommendations based on the findings.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # Files & Attachments
    # -------------------------------------------------------------------------
    main_file = fields.Binary(
        string="Primary Image/File",
        attachment=True,
        help="Primary representative file (image/PDF). Full image sets are stored "
             "in child models (study/series/image) or as attachments.",
    )
    main_filename = fields.Char(
        string="File Name",
        help="Filename of the primary file."
    )
    attachment_count = fields.Integer(
        string="Attachment Count",
        compute="_compute_attachment_count",
        help="Number of attachments linked to this record.",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Billing (optional but common)
    # -------------------------------------------------------------------------
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id.id,
    )
    quantity = fields.Float(
        string="Quantity",
        default=1.0,
        help="Quantity for billing; typically 1.0 for a single imaging service.",
    )
    price_unit = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
        help="Unit price for billing; prefilled from product if available.",
    )
    price_subtotal = fields.Monetary(
        string="Subtotal",
        currency_field="currency_id",
        compute="_compute_price_subtotal",
        store=True,
        help="Computed as Quantity * Unit Price.",
    )
    is_billable = fields.Boolean(
        string="Billable",
        default=True,
        help="If checked, this imaging will be included in patient billing.",
    )
    invoice_id = fields.Many2one(
        "account.move",
        string="Invoice",
        domain=[("move_type", "in", ["out_invoice", "out_refund"])],
        help="Linked invoice if this imaging has been billed.",
        tracking=True,
    )
    billing_state = fields.Selection(
        [
            ("no", "Not Billed"),
            ("draft", "In Draft Invoice"),
            ("posted", "Billed"),
            ("refund", "Refunded"),
        ],
        string="Billing Status",
        compute="_compute_billing_state",
        store=True,
        help="Derived from the linked invoice.",
    )

    # -------------------------------------------------------------------------
    # Privacy & Portal
    # -------------------------------------------------------------------------
    portal_published = fields.Boolean(
        string="Visible on Portal",
        help="If checked, the patient can view this imaging in the portal (subject to access rules).",
        tracking=True,
    )
    privacy_level = fields.Selection(
        [
            ("normal", "Normal"),
            ("restricted", "Restricted"),
            ("high", "Highly Restricted"),
        ],
        string="Privacy Level",
        default="normal",
        help="Controls staff and portal accessibility level.",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # State Machine
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("requested", "Requested"),
            ("scheduled", "Scheduled"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("reviewed", "Reviewed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
        help="Lifecycle status of the imaging record.",
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("quantity", "price_unit", "currency_id")
    def _compute_price_subtotal(self):
        for rec in self:
            rec.price_subtotal = (rec.quantity or 0.0) * (rec.price_unit or 0.0)

    # @api.depends("id")
    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = self.env["ir.attachment"].sudo().search_count(
                [("res_model", "=", rec._name), ("res_id", "=", rec.id)]
            )

    @api.depends("expected_done_datetime", "reviewed_datetime", "state")
    def _compute_is_overdue(self):
        now = fields.Datetime.now()
        for rec in self:
            overdue = False
            # overdue if expected done has passed and not yet completed/reviewed
            if rec.state in ("requested", "scheduled", "in_progress", "completed"):
                if rec.expected_done_datetime and now > rec.expected_done_datetime:
                    # If already reviewed, not overdue.
                    if rec.state != "reviewed":
                        overdue = True
            rec.is_overdue = overdue

    @api.depends("invoice_id.state", "invoice_id.move_type")
    def _compute_billing_state(self):
        for rec in self:
            if not rec.invoice_id:
                rec.billing_state = "no"
            else:
                move = rec.invoice_id
                if move.state == "draft":
                    rec.billing_state = "draft"
                elif move.state == "posted" and move.move_type == "out_invoice":
                    rec.billing_state = "posted"
                elif move.state == "posted" and move.move_type == "out_refund":
                    rec.billing_state = "refund"
                else:
                    rec.billing_state = "no"

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("imaging_type_id")
    def _onchange_imaging_type_id(self):
        """Prefill product and duration from imaging type defaults."""
        for rec in self:
            if rec.imaging_type_id:
                if rec.imaging_type_id.default_product_id and not rec.product_id:
                    rec.product_id = rec.imaging_type_id.default_product_id.id
                if rec.imaging_type_id.default_duration_minutes and not rec.duration_minutes:
                    rec.duration_minutes = rec.imaging_type_id.default_duration_minutes

    @api.onchange("product_id")
    def _onchange_product_id_set_price(self):
        for rec in self:
            if rec.product_id and (not rec.price_unit or rec.price_unit == 0.0):
                rec.price_unit = rec.product_id.lst_price

    @api.onchange("appointment_id")
    def _onchange_appointment_id(self):
        """If linked to an appointment, align the schedule if empty."""
        for rec in self:
            appt = rec.appointment_id
            if appt and not rec.scheduled_datetime:
                # Expect appointment to have start datetime field 'start_datetime'
                start_dt = getattr(appt, "start_datetime", False)
                if start_dt:
                    rec.scheduled_datetime = start_dt

    @api.onchange("scheduled_datetime", "duration_minutes")
    def _onchange_schedule_duration(self):
        """Estimate expected completion when scheduled and duration known."""
        for rec in self:
            if rec.scheduled_datetime and rec.duration_minutes:
                rec.expected_done_datetime = fields.Datetime.add(
                    rec.scheduled_datetime, minutes=int(rec.duration_minutes)
                )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("performed_datetime", "scheduled_datetime")
    def _check_performed_after_scheduled(self):
        for rec in self:
            if rec.performed_datetime and rec.scheduled_datetime and rec.performed_datetime < rec.scheduled_datetime:
                raise ValidationError(_("‘Performed At’ must be on or after ‘Scheduled At’."))
    @api.constrains("reviewed_datetime", "performed_datetime")
    def _check_review_after_perform(self):
        for rec in self:
            if rec.reviewed_datetime and rec.performed_datetime and rec.reviewed_datetime < rec.performed_datetime:
                raise ValidationError(_("‘Reviewed At’ must be on or after ‘Performed At’."))
    @api.constrains("invoice_id", "is_billable")
    def _check_invoice_when_billable(self):
        for rec in self:
            if not rec.is_billable and rec.invoice_id:
                raise ValidationError(_("Non-billable imaging should not have an invoice linked."))

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = seq.next_by_code("clinical.imaging") or _("New")
        records = super().create(vals_list)
        # Auto-subscribe doctor/technician to chatter
        for rec in records:
            partner_ids = []
            if rec.doctor_id and rec.doctor_id.work_contact_id:
                partner_ids.append(rec.doctor_id.work_contact_id.id)
            if rec.technician_id and rec.technician_id.work_contact_id:
                partner_ids.append(rec.technician_id.work_contact_id.id)
            if partner_ids:
                rec.message_subscribe(partner_ids=list(set(partner_ids)))
        return records

    def write(self, vals):
        # Prevent modifying company after creation
        if "company_id" in vals:
            for rec in self:
                if rec.invoice_id:
                    raise UserError(_("You cannot change the Company once invoiced."))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.invoice_id and rec.invoice_id.state == "posted":
                raise UserError(_("You cannot delete an imaging record that has a posted invoice."))
        return super().unlink()

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("New"))
        default.setdefault("state", "draft")
        default.setdefault("invoice_id", False)
        default.setdefault("reviewed_datetime", False)
        default.setdefault("performed_datetime", False)
        return super().copy(default)

    # -------------------------------------------------------------------------
    # ACTIONS / STATE TRANSITIONS
    # -------------------------------------------------------------------------
    def action_request(self):
        for rec in self:
            if rec.state not in ("draft", "cancelled"):
                raise UserError(_("Only Draft/Cancelled records can be moved to Requested."))
            rec.state = "requested"
            rec.message_post(body=_("Imaging has been requested."))

    def action_schedule(self):
        for rec in self:
            if rec.state not in ("requested", "draft"):
                raise UserError(_("Only Draft/Requested records can be Scheduled."))
            if not rec.scheduled_datetime:
                raise UserError(_("Please set ‘Scheduled At’ before scheduling."))
            rec.state = "scheduled"
            rec.message_post(body=_("Imaging has been scheduled."))

    def action_start(self):
        for rec in self:
            if rec.state not in ("scheduled", "requested"):
                raise UserError(_("Only Scheduled/Requested records can be set In Progress."))
            rec.state = "in_progress"
            rec.message_post(body=_("Imaging acquisition started."))

    def action_complete(self):
        Activity = self.env["mail.activity"]
        for rec in self:
            if rec.state not in ("in_progress", "scheduled"):
                raise UserError(_("Only In Progress/Scheduled records can be completed."))
            if not rec.performed_datetime:
                rec.performed_datetime = fields.Datetime.now()
            rec.state = "completed"
            rec.message_post(body=_("Imaging acquisition completed."))
            # Schedule a Review activity for the doctor
            if rec.doctor_id and rec.doctor_id.user_id:
                Activity.create({
                    "res_model_id": self.env["ir.model"]._get_id(self._name),
                    "res_id": rec.id,
                    "user_id": rec.doctor_id.user_id.id,
                    "summary": _("Review Imaging"),
                    "note": _("Please review the imaging findings and add recommendations."),
                    "activity_type_id": self.env.ref("mail.mail_activity_data_todo").id,
                    "date_deadline": fields.Date.today(),
                })

    def action_review(self):
        for rec in self:
            if rec.state != "completed":
                raise UserError(_("Only Completed records can be Reviewed."))
            if not rec.findings_summary and not rec.recommendations:
                raise UserError(_("Add findings/recommendations before marking as Reviewed."))
            if not rec.reviewed_datetime:
                rec.reviewed_datetime = fields.Datetime.now()
            rec.state = "reviewed"
            rec.message_post(body=_("Imaging has been reviewed by the doctor."))

    def action_cancel(self):
        for rec in self:
            if rec.state == "reviewed" and rec.invoice_id and rec.invoice_id.state == "posted":
                raise UserError(_("Reviewed & billed records cannot be cancelled. Please handle billing first."))
            rec.state = "cancelled"
            rec.message_post(body=_("Imaging record has been cancelled."))

    # -------------------------------------------------------------------------
    # BILLING INTEGRATION
    # -------------------------------------------------------------------------
    def _get_invoice_partner(self):
        self.ensure_one()
        if not self.patient_id:
            raise UserError(_("Patient is required for billing."))
        return self.patient_id.commercial_partner_id

    def _get_invoice_description(self):
        self.ensure_one()
        parts = [_("Imaging")]
        if self.name:
            parts.append(self.name)
        if self.imaging_type_id:
            parts.append("[%s]" % self.imaging_type_id.display_name)
        if self.patient_id:
            parts.append("- %s" % self.patient_id.display_name)
        return " ".join(parts)

    def _prepare_invoice_vals(self):
        self.ensure_one()
        partner = self._get_invoice_partner()
        return {
            "move_type": "out_invoice",
            "partner_id": partner.id,
            "invoice_origin": self.name,
            "invoice_user_id": self.env.user.id,
            "invoice_date": fields.Date.context_today(self),
            "currency_id": self.currency_id.id or self.env.company.currency_id.id,
            "invoice_line_ids": [(0, 0, self._prepare_invoice_line_vals())],
            "invoice_payment_ref": self.name,
            "invoice_payment_term_id": partner.property_payment_term_id.id or False,
            "invoice_incoterm_id": False,
        }

    def _prepare_invoice_line_vals(self):
        self.ensure_one()
        if not self.product_id:
            raise UserError(_("Please set a Billable Service (product) before creating the invoice."))
        name = self._get_invoice_description()
        # Taxes from product, mapped by fiscal position if set on partner
        partner = self._get_invoice_partner()
        fpos = partner.property_account_position_id
        taxes = self.product_id.taxes_id
        if fpos:
            taxes = fpos.map_tax(taxes, partner)
        return {
            "name": name,
            "product_id": self.product_id.id,
            "quantity": self.quantity or 1.0,
            "price_unit": self.price_unit or self.product_id.lst_price,
            "currency_id": self.currency_id.id or self.env.company.currency_id.id,
            "tax_ids": [(6, 0, taxes.ids)],
        }

    def action_create_invoice(self):
        """Create a draft invoice if none exists."""
        for rec in self:
            if not rec.is_billable:
                raise UserError(_("This imaging is marked as not billable."))
            if rec.invoice_id:
                raise UserError(_("An invoice has already been linked to this imaging."))
            vals = rec._prepare_invoice_vals()
            move = self.env["account.move"].create(vals)
            rec.invoice_id = move.id
            rec.message_post(body=_("Draft invoice created: %s") % move.display_name)
        return self.action_open_invoice()

    def action_open_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_("No invoice linked to this imaging."))
        return {
            "name": _("Invoice"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.invoice_id.id,
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # QUICK NAVIGATION / HELPERS
    # -------------------------------------------------------------------------
    def action_view_attachments(self):
        self.ensure_one()
        return {
            "name": _("Attachments"),
            "type": "ir.actions.act_window",
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "context": {"default_res_model": self._name, "default_res_id": self.id},
        }

    def action_open_appointment(self):
        self.ensure_one()
        if not self.appointment_id:
            raise UserError(_("No appointment is linked."))
        return {
            "name": _("Appointment"),
            "type": "ir.actions.act_window",
            "res_model": self.appointment_id._name,
            "view_mode": "form",
            "res_id": self.appointment_id.id,
            "target": "current",
        }

    def action_open_encounter(self):
        self.ensure_one()
        if not self.encounter_id:
            raise UserError(_("No clinical encounter is linked."))
        return {
            "name": _("Clinical Encounter"),
            "type": "ir.actions.act_window",
            "res_model": self.encounter_id._name,
            "view_mode": "form",
            "res_id": self.encounter_id.id,
            "target": "current",
        }

    def action_toggle_portal(self):
        for rec in self:
            rec.portal_published = not rec.portal_published

    # -------------------------------------------------------------------------
    # DISPLAY
    # -------------------------------------------------------------------------
    @api.depends("name", "patient_id", "imaging_type_id")
    def _compute_display_name(self):
        for rec in self:
            display = rec.name or _("Imaging")
            if rec.patient_id:
                display = f"{display} - {rec.patient_id.display_name}"
            if rec.imaging_type_id:
                display = f"{display} [{rec.imaging_type_id.display_name}]"
            rec.display_name = display

    # -------------------------------------------------------------------------
    # SQL CONSTRAINTS
    # -------------------------------------------------------------------------
    _name_company_uniq = models.Constraint(
        'unique(name, company_id)',
        'Imaging Number must be unique per company.',
    )
    _dicom_study_uid_company_uniq = models.Constraint(
        'unique(dicom_study_uid, company_id)',
        'DICOM Study UID must be unique per company.',
    )


# =============================================================================
# Imaging Type (basic master data)
# =============================================================================
class ClinicalImagingType(models.Model):
    """Compatibility extension for the canonical Imaging Type master.

    The canonical owner is ``clinical_imaging_type.py``.  The historical
    duplicate declaration in this file added no unique fields, so it is kept
    as an explicit in-place extension instead of redefining the model.
    """
    _inherit = "clinical.imaging.type"


# =============================================================================
# Imaging Device (equipment master data)
# =============================================================================
class ClinicalImagingDevice(models.Model):
    """Compatibility extension for the canonical Imaging Device master.

    ``clinical_imaging_device.py`` owns the field surface.  This extension
    preserves the historical onchange helper without redeclaring/downgrading
    the canonical fields.
    """
    _inherit = "clinical.imaging.device"

    @api.onchange("last_maintenance_date", "maintenance_interval_days")
    def _onchange_maintenance_dates(self):
        for rec in self:
            if rec.last_maintenance_date and rec.maintenance_interval_days:
                rec.next_maintenance_date = fields.Date.add(
                    rec.last_maintenance_date,
                    days=int(rec.maintenance_interval_days),
                )
