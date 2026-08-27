# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# =============================================================================
# Clinical Imaging Request (header/master)
# =============================================================================
class ClinicalImagingRequest(models.Model):
    """
    Represents a physician's request/order for one or more imaging procedures.
    Each request comprises one or more lines (requested imaging types), and can
    generate one or multiple clinical.imaging records upon approval.

    Integration points (cross-module):
      - Patient (clinic_patient / res.partner with is_patient)
      - Doctor & Technician (clinic_doctor / hr.employee with flags)
      - Appointment (clinic_booking)
      - Encounter (clinic_encounter)
      - Treatment & Procedure Session (clinic_treatment / clinic_procedure)
      - eMAR / Prescription Order (clinic_prescription)
      - Consent (clinic_consent)
      - Billing (account / clinic_billing / clinic_finance / clinic_accounting)
      - Membership / Coverage (clinic_membership)
      - Portal publishing (clinic_portal)
    """
    _name = "clinical.imaging.request"
    _description = "Clinical Imaging Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "request_datetime desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Company
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Request Number",
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
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="If unchecked, the request is archived from regular views.",
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
    ordering_doctor_id = fields.Many2one(
        "hr.employee",
        string="Ordering Doctor",
        domain=[("is_doctor", "=", True)],
        help="Doctor who ordered this imaging request.",
        tracking=True,
    )
    responsible_doctor_id = fields.Many2one(
        "hr.employee",
        string="Responsible Doctor",
        domain=[("is_doctor", "=", True)],
        help="Doctor in charge for review/approval (radiologist or assigned MD).",
        tracking=True,
    )
    technician_id = fields.Many2one(
        "hr.employee",
        string="Preferred Technician",
        domain=[("is_imaging_technician", "=", True)],
        help="Preferred technician to perform imaging (optional).",
        tracking=True,
    )
    # membership_id = fields.Many2one(
    #     "clinic.membership",
    #     string="Membership",
    #     help="Membership used for benefits/coverage for this request (if any).",
    #     tracking=True,
    # )

    # -------------------------------------------------------------------------
    # Clinical Context (cross-module references)
    # -------------------------------------------------------------------------
    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Appointment",
        help="Appointment related to this request (if scheduled via booking).",
    )
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Clinical Encounter",
        help="Encounter during which the imaging is requested.",
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        help="Treatment plan associated with this request.",
    )
    # TUNGGU Addon ACTIVE
    procedure_session_id = fields.Many2one(
        "clinic.procedure.session",
        string="Procedure Session",
        help="Related procedure/treatment session, if applicable.",
    )
    prescription_order_id = fields.Many2one(
        "clinic.emar.order",
        string="Prescription/Order (eMAR)",
        help="eMAR/Prescription record authorizing this request.",
    )
    consent_id = fields.Many2one(
        "clinic.consent.form",
        string="Consent",
        help="Patient consent record linked to this request.",
    )

    # -------------------------------------------------------------------------
    # Request Details
    # -------------------------------------------------------------------------
    request_datetime = fields.Datetime(
        string="Requested At",
        required=True,
        default=fields.Datetime.now,
        help="Datetime when the request was created.",
        tracking=True,
    )
    desired_datetime = fields.Datetime(
        string="Desired Date/Time",
        help="Preferred datetime to schedule imaging.",
        tracking=True,
    )
    expiry_date = fields.Date(
        string="Order Expiry Date",
        help="Date after which the request/order is considered expired.",
        tracking=True,
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
        help="Clinical urgency of this request.",
        tracking=True,
    )
    clinical_indication = fields.Text(
        string="Clinical Indication",
        help="Reason for imaging; the clinical question to be answered.",
        tracking=True,
    )
    notes = fields.Text(
        string="Internal Notes",
        help="Additional notes for staff.",
    )

    # -------------------------------------------------------------------------
    # Lines & Imaging linkage
    # -------------------------------------------------------------------------
    line_ids = fields.One2many(
        "clinical.imaging.request.line",
        "request_id",
        string="Requested Procedures",
        help="One or more requested imaging procedures.",
        copy=True,
    )
    created_imaging_ids = fields.Many2many(
        "clinical.imaging",
        "clinical_imaging_request_rel",
        "request_id",
        "imaging_id",
        string="Created Imaging Records",
        help="Imaging records generated from this request.",
        copy=False,
    )
    line_count = fields.Integer(
        string="Line Count",
        compute="_compute_counts",
        store=False,
    )
    created_imaging_count = fields.Integer(
        string="Created Imaging Count",
        compute="_compute_counts",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Billing & Currency
    # -------------------------------------------------------------------------
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )
    fiscal_position_id = fields.Many2one(
        "account.fiscal.position",
        string="Fiscal Position",
        help="Fiscal position used to map taxes based on the patient/partner.",
    )
    amount_untaxed = fields.Monetary(
        string="Untaxed Amount",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
        help="Sum of line subtotals without taxes.",
    )
    amount_tax = fields.Monetary(
        string="Taxes",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
        help="Total tax amount from all lines.",
    )
    amount_total = fields.Monetary(
        string="Total",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
        help="Grand total including taxes.",
    )
    is_billable = fields.Boolean(
        string="Billable",
        default=True,
        help="If checked, this request is billable and can generate a draft invoice.",
    )
    invoice_id = fields.Many2one(
        "account.move",
        string="Invoice",
        domain=[("move_type", "in", ["out_invoice", "out_refund"])],
        help="Linked invoice if the request has been billed.",
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
        help="Derived from the linked invoice state.",
    )

    # -------------------------------------------------------------------------
    # Portal & Attachments
    # -------------------------------------------------------------------------
    portal_published = fields.Boolean(
        string="Visible on Portal",
        help="If checked, the patient can view this request via the portal (subject to rules).",
        tracking=True,
    )
    attachment_count = fields.Integer(
        string="Attachment Count",
        compute="_compute_attachment_count",
        store=False,
    )

    # -------------------------------------------------------------------------
    # State Machine
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("in_progress", "In Progress"),
            ("imaging_created", "Imaging Created"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
            ("done", "Done"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
        help="Lifecycle status of the imaging request.",
    )
    is_overdue = fields.Boolean(
        string="Overdue",
        compute="_compute_is_overdue",
        store=True,
        help="Checked when desired/expiry SLA is missed and the request is still open.",
    )

    plan_id = fields.Many2one(
        "clinic.treatment.imaging.plan",
        string="Originating Plan",
        index=True,
        ondelete="set null",
        help="If this request was generated from a treatment imaging plan, link it here.",
    )


    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("line_ids.price_subtotal", "line_ids.price_tax")
    def _compute_amounts(self):
        for rec in self:
            untaxed = sum(rec.line_ids.mapped("price_subtotal"))
            tax = sum(rec.line_ids.mapped("price_tax"))
            rec.amount_untaxed = untaxed
            rec.amount_tax = tax
            rec.amount_total = untaxed + tax

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

    @api.depends("desired_datetime", "expiry_date", "state")
    def _compute_is_overdue(self):
        now_dt = fields.Datetime.now()
        today = fields.Date.context_today(self)
        for rec in self:
            overdue = False
            if rec.state in ("submitted", "approved", "in_progress"):
                if rec.desired_datetime and now_dt > rec.desired_datetime:
                    overdue = True
                if rec.expiry_date and today > rec.expiry_date:
                    overdue = True
            rec.is_overdue = overdue

    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = self.env["ir.attachment"].sudo().search_count(
                [("res_model", "=", rec._name), ("res_id", "=", rec.id)]
            )

    def _compute_counts(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.created_imaging_count = len(rec.created_imaging_ids)

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("patient_id")
    def _onchange_patient_id(self):
        """Set fiscal position from patient and suggest membership if available."""
        for rec in self:
            partner = rec.patient_id and rec.patient_id.commercial_partner_id or False
            if partner:
                rec.fiscal_position_id = partner.property_account_position_id
            # Membership suggestion hook (if patient has default membership logic)
            # Keep non-destructive (do not override if already set)
            if not rec.membership_id and getattr(rec.patient_id, "default_membership_id", False):
                rec.membership_id = rec.patient_id.default_membership_id.id

    @api.onchange("appointment_id")
    def _onchange_appointment_id(self):
        for rec in self:
            if rec.appointment_id and not rec.desired_datetime:
                start_dt = getattr(rec.appointment_id, "start_datetime", False)
                if start_dt:
                    rec.desired_datetime = start_dt

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("line_ids")
    def _check_has_lines(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError(_("Please add at least one request line."))

    @api.constrains("expiry_date", "request_datetime")
    def _check_expiry_not_before_request(self):
        for rec in self:
            if rec.expiry_date and rec.request_datetime:
                if fields.Date.to_date(rec.expiry_date) < fields.Date.to_date(rec.request_datetime):
                    raise ValidationError(_("Order Expiry Date cannot be earlier than Requested At."))

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            vals.setdefault("company_id", self.env.company.id)
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = seq.next_by_code("clinical.imaging.request") or _("New")
        records = super().create(vals_list)
        # Auto-subscribe ordering/responsible doctors to chatter
        for rec in records:
            partner_ids = []
            if rec.ordering_doctor_id and rec.ordering_doctor_id.work_contact_id:
                partner_ids.append(rec.ordering_doctor_id.work_contact_id.id)
            if rec.responsible_doctor_id and rec.responsible_doctor_id.work_contact_id:
                partner_ids.append(rec.responsible_doctor_id.work_contact_id.id)
            if partner_ids:
                rec.message_subscribe(partner_ids=list(set(partner_ids)))
        return records

    def write(self, vals):
        # Prevent company changes after creation if invoiced
        if "company_id" in vals:
            for rec in self:
                if rec.invoice_id:
                    raise UserError(_("You cannot change the Company once an invoice is linked."))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.invoice_id and rec.invoice_id.state == "posted":
                raise UserError(_("You cannot delete a request that has a posted invoice."))
        return super().unlink()

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("name", _("New"))
        default.setdefault("state", "draft")
        default.setdefault("invoice_id", False)
        default.setdefault("created_imaging_ids", False)
        return super().copy(default)

    # -------------------------------------------------------------------------
    # ACTIONS / WORKFLOW
    # -------------------------------------------------------------------------
    def action_submit(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only Draft requests can be submitted."))
            rec.state = "submitted"
            rec.message_post(body=_("Imaging request has been submitted."))

    def action_approve(self):
        for rec in self:
            if rec.state not in ("submitted",):
                raise UserError(_("Only Submitted requests can be approved."))
            if not rec.responsible_doctor_id:
                raise UserError(_("Please set a Responsible Doctor before approval."))
            rec.state = "approved"
            rec.message_post(body=_("Imaging request has been approved by the doctor."))

    def action_reject(self, reason=None):
        for rec in self:
            if rec.state not in ("submitted", "approved"):
                raise UserError(_("Only Submitted/Approved requests can be rejected."))
            rec.state = "rejected"
            body = _("Imaging request has been rejected.")
            if reason:
                body += " " + _("Reason: %s") % reason
            rec.message_post(body=body)

    def action_cancel(self):
        for rec in self:
            if rec.state in ("done",):
                raise UserError(_("Completed requests cannot be cancelled."))
            rec.state = "cancelled"
            rec.message_post(body=_("Imaging request has been cancelled."))

    def action_set_in_progress(self):
        for rec in self:
            if rec.state not in ("approved",):
                raise UserError(_("Only Approved requests can be set In Progress."))
            rec.state = "in_progress"
            rec.message_post(body=_("Imaging request is now In Progress."))

    def action_create_imaging(self):
        """
        Generate one or multiple 'clinical.imaging' records from approved requests.
        Typically creates one imaging per line (and per quantity if >1).
        """
        Imaging = self.env["clinical.imaging"]
        created_map = {}
        for rec in self:
            if rec.state not in ("approved", "in_progress", "submitted"):
                raise UserError(_("Only Submitted/Approved/In Progress requests can create imaging records."))
            if not rec.patient_id:
                raise UserError(_("Patient is required to create imaging records."))

            imaging_records = self.env["clinical.imaging"]
            for line in rec.line_ids:
                if not line.imaging_type_id:
                    raise UserError(_("Each line must have an Imaging Type."))
                qty = max(1, int(line.quantity or 1))
                for _i in range(qty):
                    vals = {
                        "company_id": rec.company_id.id,
                        "patient_id": rec.patient_id.id,
                        "doctor_id": rec.responsible_doctor_id.id if rec.responsible_doctor_id else False,
                        "technician_id": rec.technician_id.id if rec.technician_id else False,
                        "membership_id": rec.membership_id.id if rec.membership_id else False,
                        "appointment_id": rec.appointment_id.id if rec.appointment_id else False,
                        "encounter_id": rec.encounter_id.id if rec.encounter_id else False,
                        "treatment_id": rec.treatment_id.id if rec.treatment_id else False,
                        "procedure_session_id": rec.procedure_session_id.id if rec.procedure_session_id else False,
                        "prescription_order_id": rec.prescription_order_id.id if rec.prescription_order_id else False,
                        "consent_id": rec.consent_id.id if rec.consent_id else False,
                        "imaging_type_id": line.imaging_type_id.id,
                        "device_id": line.device_id.id if line.device_id else False,
                        "product_id": line.product_id.id if line.product_id else False,
                        "priority": rec.priority,
                        "request_datetime": rec.request_datetime,
                        "scheduled_datetime": rec.desired_datetime or False,
                        "clinical_indication": rec.clinical_indication,
                        "notes": line.notes or rec.notes,
                        "quantity": 1.0,
                        "price_unit": line.price_unit or (line.product_id and line.product_id.lst_price) or 0.0,
                        "currency_id": rec.currency_id.id,
                        "portal_published": False,
                    }
                    new_imaging = Imaging.create(vals)
                    imaging_records |= new_imaging
                    # Link back to request line
                    line.imaging_ids = [(4, new_imaging.id)]
            if imaging_records:
                # link at header level
                rec.created_imaging_ids = [(6, 0, imaging_records.ids)]
                rec.state = "imaging_created"
                rec.message_post(body=_("Created %s imaging record(s).") % len(imaging_records))
            created_map[rec.id] = imaging_records.ids
        # Return an action to show all created imaging for the last request if single
        if len(self) == 1 and self.created_imaging_ids:
            return self.action_open_created_imaging()
        return created_map

    def action_open_created_imaging(self):
        self.ensure_one()
        return {
            "name": _("Created Imaging"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging",
            "view_mode": "list,form,kanban,calendar",
            "domain": [("id", "in", self.created_imaging_ids.ids)],
            "target": "current",
        }

    def action_mark_done(self):
        for rec in self:
            if rec.state not in ("imaging_created", "in_progress", "approved"):
                raise UserError(_("Only Approved/In Progress/Imaging Created requests can be marked Done."))
            rec.state = "done"
            rec.message_post(body=_("Imaging request is marked as Done."))

    # -------------------------------------------------------------------------
    # BILLING INTEGRATION (optional)
    # -------------------------------------------------------------------------
    def _get_invoice_partner(self):
        self.ensure_one()
        if not self.patient_id:
            raise UserError(_("Patient is required for billing."))
        return self.patient_id.commercial_partner_id

    def _prepare_invoice_vals(self):
        self.ensure_one()
        partner = self._get_invoice_partner()
        return {
            "move_type": "out_invoice",
            "partner_id": partner.id,
            "invoice_origin": self.name,
            "invoice_user_id": self.env.user.id,
            "invoice_date": fields.Date.context_today(self),
            "currency_id": self.currency_id.id,
            "invoice_line_ids": [(0, 0, line._prepare_invoice_line_vals(self)) for line in self.line_ids],
            "invoice_payment_ref": self.name,
            "invoice_payment_term_id": partner.property_payment_term_id.id or False,
        }

    def action_create_invoice(self):
        for rec in self:
            if not rec.is_billable:
                raise UserError(_("This request is marked as not billable."))
            if rec.invoice_id:
                raise UserError(_("An invoice has already been linked to this request."))
            if not rec.line_ids:
                raise UserError(_("Please add at least one request line to bill."))
            move = self.env["account.move"].create(rec._prepare_invoice_vals())
            rec.invoice_id = move.id
            rec.message_post(body=_("Draft invoice created: %s") % move.display_name)
        return self.action_open_invoice()

    def action_open_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_("No invoice linked to this request."))
        return {
            "name": _("Invoice"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.invoice_id.id,
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # PORTAL / NAVIGATION HELPERS
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

    def action_toggle_portal(self):
        for rec in self:
            rec.portal_published = not rec.portal_published

    @api.depends("name", "patient_id")
    def _compute_display_name(self):
        for rec in self:
            display = rec.name or _("Request")
            if rec.patient_id:
                display = f"{display} - {rec.patient_id.display_name}"
            rec.display_name = display

    # -------------------------------------------------------------------------
    # SQL CONSTRAINTS
    # -------------------------------------------------------------------------
    _name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'Request Number must be unique per company.',
    )


# =============================================================================
# Clinical Imaging Request Line (detail)
# =============================================================================
class ClinicalImagingRequestLine(models.Model):
    """
    A single requested imaging procedure within a request.
    Each line may generate one or more clinical.imaging records (per quantity).
    """
    _name = "clinical.imaging.request.line"
    _description = "Clinical Imaging Request Line"
    _order = "sequence, id"

    # Header relation
    request_id = fields.Many2one(
        "clinical.imaging.request",
        string="Request",
        required=True,
        ondelete="cascade",
        index=True,
    )

    sequence = fields.Integer(string="Sequence", default=10)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="request_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="request_id.currency_id",
        store=True,
        readonly=True,
    )

    # Imaging specification
    imaging_type_id = fields.Many2one(
        "clinical.imaging.type",
        string="Imaging Type",
        required=True,
        help="Imaging type to be performed for this line (e.g., X-Ray, CT, MRI).",
    )
    device_id = fields.Many2one(
        "clinical.imaging.device",
        string="Preferred Device",
        help="Preferred device to perform this imaging (optional).",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Billable Service",
        domain=[("type", "=", "service")],
        help="Service product used for pricing/invoicing this line.",
    )
    quantity = fields.Float(
        string="Quantity",
        default=1.0,
        help="Number of times this imaging is requested for this line.",
    )
    duration_minutes = fields.Integer(
        string="Expected Duration (min)",
        help="Expected duration for this imaging; used for scheduling.",
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
        help="Line-level priority (defaults to request's priority if unset).",
    )
    notes = fields.Text(
        string="Line Notes",
        help="Additional notes specific to this line.",
    )

    # Billing & Taxes
    price_unit = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
        help="Unit price for billing; prefilled from product or imaging type default service.",
    )
    tax_ids = fields.Many2many(
        "account.tax",
        "clinical_imaging_request_line_tax_rel",
        "line_id",
        "tax_id",
        string="Taxes",
        help="Taxes applicable to this line.",
    )

    # Totals
    price_subtotal = fields.Monetary(
        string="Subtotal",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
        help="Subtotal without taxes for this line.",
    )
    price_tax = fields.Monetary(
        string="Tax",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
        help="Tax amount for this line.",
    )
    price_total = fields.Monetary(
        string="Total",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
        help="Total including taxes for this line.",
    )

    # Link to created imaging (one line may produce many imaging records)
    imaging_ids = fields.Many2many(
        "clinical.imaging",
        "clinical_imaging_request_line_rel",
        "line_id",
        "imaging_id",
        string="Imaging Records",
        help="Imaging records created from this line.",
        copy=False,
    )
    imaging_count = fields.Integer(
        string="Imaging Count",
        compute="_compute_imaging_count",
        store=False,
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("quantity", "price_unit", "tax_ids", "request_id.fiscal_position_id")
    def _compute_amounts(self):
        for line in self:
            qty = line.quantity or 0.0
            price_unit = line.price_unit or 0.0
            currency = line.currency_id or line.request_id.currency_id
            partner = line.request_id.patient_id and line.request_id.patient_id.commercial_partner_id or False
            fpos = line.request_id.fiscal_position_id or (partner and partner.property_account_position_id) or False

            taxes = line.tax_ids
            if fpos:
                taxes = fpos.map_tax(taxes, partner)
            res = taxes.compute_all(
                price_unit,
                currency=currency,
                quantity=qty,
                product=line.product_id,
                partner=partner,
            ) if taxes else {
                "total_excluded": price_unit * qty,
                "total_included": price_unit * qty,
                "taxes": [],
            }
            line.price_subtotal = currency.round(res["total_excluded"]) if currency else res["total_excluded"]
            line.price_total = currency.round(res["total_included"]) if currency else res["total_included"]
            # Derive tax amount
            line.price_tax = line.price_total - line.price_subtotal

    def _compute_imaging_count(self):
        for line in self:
            line.imaging_count = len(line.imaging_ids)

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("imaging_type_id")
    def _onchange_imaging_type_id(self):
        for line in self:
            if line.imaging_type_id:
                # Prefill product and duration from imaging type defaults
                if line.imaging_type_id.default_product_id and not line.product_id:
                    line.product_id = line.imaging_type_id.default_product_id.id
                if line.imaging_type_id.default_duration_minutes and not line.duration_minutes:
                    line.duration_minutes = line.imaging_type_id.default_duration_minutes

    @api.onchange("product_id")
    def _onchange_product_id_set_price_and_taxes(self):
        for line in self:
            if line.product_id:
                # Set price if empty
                if not line.price_unit or line.price_unit == 0.0:
                    line.price_unit = line.product_id.lst_price
                # Map taxes from product
                taxes = line.product_id.taxes_id
                partner = line.request_id.patient_id and line.request_id.patient_id.commercial_partner_id or False
                fpos = line.request_id.fiscal_position_id or (partner and partner.property_account_position_id) or False
                if fpos:
                    taxes = fpos.map_tax(taxes, partner)
                line.tax_ids = [(6, 0, taxes.ids)]

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("quantity")
    def _check_quantity_positive(self):
        for line in self:
            if (line.quantity or 0.0) <= 0.0:
                raise ValidationError(_("Quantity must be greater than zero."))

    # -------------------------------------------------------------------------
    # INVOICE LINE PREPARATION
    # -------------------------------------------------------------------------
    def _prepare_invoice_line_vals(self, request):
        self.ensure_one()
        if not self.product_id:
            raise UserError(_("Please set a Billable Service (product) on each line before invoicing."))
        partner = request._get_invoice_partner()
        # Ensure taxes mapped with fiscal position
        taxes = self.tax_ids
        if request.fiscal_position_id:
            taxes = request.fiscal_position_id.map_tax(taxes, partner)
        name_parts = [
            _("Imaging Request"),
            request.name or "",
            ("[%s]" % self.imaging_type_id.display_name) if self.imaging_type_id else "",
            ("- %s" % request.patient_id.display_name) if request.patient_id else "",
        ]
        return {
            "name": " ".join([p for p in name_parts if p]),
            "product_id": self.product_id.id,
            "quantity": self.quantity or 1.0,
            "price_unit": self.price_unit or self.product_id.lst_price,
            "currency_id": request.currency_id.id,
            "tax_ids": [(6, 0, taxes.ids)],
        }

    # -------------------------------------------------------------------------
    # NAVIGATION
    # -------------------------------------------------------------------------
    def action_open_imaging(self):
        self.ensure_one()
        return {
            "name": _("Imaging Records"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging",
            "view_mode": "list,form,kanban,calendar",
            "domain": [("id", "in", self.imaging_ids.ids)],
            "target": "current",
        }
