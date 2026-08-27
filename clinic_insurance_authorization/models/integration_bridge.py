from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ResPartner(models.Model):
    """Payer identity extension; patient insurance ownership remains on Policy."""

    _inherit = "res.partner"

    is_insurer = fields.Boolean(
        string="Is Insurer / Payer",
        index=True,
        tracking=True,
    )
    insurer_code = fields.Char(
        string="Insurer Code",
        index=True,
        help="ClinicOne internal payer code.",
    )
    payer_external_id = fields.Char(
        string="Electronic Payer ID",
        index=True,
        help="Optional payer/EDI/API identifier.",
    )
    payer_authorization_email = fields.Char(string="Authorization Email")
    payer_claim_email = fields.Char(string="Claim Email")
    payer_portal_url = fields.Char(string="Payer Portal Reference")

    # The current clinic_queue_room source still contains an old
    # res_partner_inherit.py definition for this field, but that module is NOT
    # imported by clinic_queue_room/models/__init__.py.  Therefore the field is
    # not present in the live registry.  Addon 25 owns the active insurance
    # bridge explicitly instead of relying on dead/commented source.
    insurance_policy_id = fields.Many2one(
        "clinic.insurance.policy",
        string="Primary Insurance Policy",
        ondelete="set null",
        index=True,
        help="Primary active insurance policy for this patient/contact, when applicable.",
    )

    insurance_plan_count = fields.Integer(
        compute="_compute_insurance_plan_count",
    )

    def _compute_insurance_plan_count(self):
        Plan = self.env["clinic.insurance.plan"]
        for partner in self:
            partner.insurance_plan_count = Plan.search_count([
                ("insurer_partner_id", "=", partner.id),
            ])

    def action_open_insurance_plans(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Plans"),
            "res_model": "clinic.insurance.plan",
            "view_mode": "list,form",
            "domain": [("insurer_partner_id", "=", self.id)],
            "context": {
                "default_insurer_partner_id": self.id,
                "default_company_id": self.env.company.id,
            },
        }


class ClinicPatient(models.Model):
    """Patient-side insurance counters/actions using owned Policy/Authorization models."""

    _inherit = "clinic.patient"

    insurance_policy_ids = fields.One2many(
        "clinic.insurance.policy",
        "patient_id",
        string="Insurance Policies",
    )
    insurance_authorization_ids = fields.One2many(
        "clinic.insurance.authorization",
        "patient_id",
        string="Insurance Authorizations",
    )
    insurance_policy_count = fields.Integer(compute="_compute_insurance_counts")
    insurance_active_policy_count = fields.Integer(compute="_compute_insurance_counts")
    insurance_authorization_count = fields.Integer(compute="_compute_insurance_counts")
    insurance_open_authorization_count = fields.Integer(compute="_compute_insurance_counts")

    def _compute_insurance_counts(self):
        for patient in self:
            patient.insurance_policy_count = len(patient.insurance_policy_ids)
            patient.insurance_active_policy_count = len(
                patient.insurance_policy_ids.filtered(lambda policy: policy.state == "active")
            )
            patient.insurance_authorization_count = len(patient.insurance_authorization_ids)
            patient.insurance_open_authorization_count = len(
                patient.insurance_authorization_ids.filtered(
                    lambda auth: auth.state in ("draft", "prepared", "submitted", "pending")
                )
            )

    def action_open_insurance(self):
        """XML ID and method contract anticipated by the existing Patient addon."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Authorizations"),
            "res_model": "clinic.insurance.authorization",
            "view_mode": "list,form",
            "domain": [("patient_id", "=", self.id)],
            "context": {
                "default_patient_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }

    def action_open_insurance_policies(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Policies"),
            "res_model": "clinic.insurance.policy",
            "view_mode": "list,form",
            "domain": [("patient_id", "=", self.id)],
            "context": {
                "default_patient_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }


# Booking stores structured insurance context but remains the owner of scheduling/workflow.
class BookingBooking(models.Model):
    """Add explicit insurance coverage/pre-authorization context to main Booking."""

    _inherit = "booking.booking"

    insurance_policy_id = fields.Many2one(
        "clinic.insurance.policy",
        string="Insurance Policy",
        check_company=True,
        ondelete="set null",
        domain="[('partner_id', '=', patient_id), ('company_id', '=', company_id), ('state', '=', 'active')]",
    )
    insurance_authorization_id = fields.Many2one(
        "clinic.insurance.authorization",
        string="Insurance Authorization",
        check_company=True,
        ondelete="set null",
        domain="[('policy_id', '=', insurance_policy_id), ('state', 'in', ('approved','partial'))]",
    )
    # Insurance Booking search/group-by uses this state; store it so Odoo can
    # search and group safely instead of failing at runtime view validation.
    insurance_authorization_state = fields.Selection(
        related="insurance_authorization_id.state",
        store=True,
        index=True,
        readonly=True,
    )

    @api.onchange("patient_id")
    def _onchange_insurance_patient(self):
        for booking in self:
            if booking.insurance_policy_id and booking.insurance_policy_id.partner_id != booking.patient_id:
                booking.insurance_policy_id = False
                booking.insurance_authorization_id = False

    def _insurance_patient_card(self):
        self.ensure_one()
        patient = self.env["clinic.patient"].search([
            ("partner_id", "=", self.patient_id.id),
            ("company_id", "=", self.company_id.id),
        ], limit=1)
        if not patient:
            raise UserError(_("The Booking patient has no Clinic Patient Card for this company."))
        return patient

    def action_create_insurance_authorization(self):
        self.ensure_one()
        patient = self._insurance_patient_card()
        policy = self.insurance_policy_id or self.env["clinic.insurance.policy"].search([
            ("patient_id", "=", patient.id),
            ("company_id", "=", self.company_id.id),
            ("state", "=", "active"),
            ("currently_valid", "=", True),
        ], order="start_date desc, id desc", limit=1)
        if not policy:
            raise UserError(_("No active Insurance Policy is available for this Booking."))

        auth = self.env["clinic.insurance.authorization"].create({
            "policy_id": policy.id,
            "patient_id": patient.id,
            "company_id": self.company_id.id,
            "source_type": "booking",
            "booking_id": self.id,
            "treatment_id": self.treatment_id.id or False,
            "service_date": fields.Date.to_date(self.start_datetime) if self.start_datetime else fields.Date.context_today(self),
        })
        auth.action_prepare()
        self.insurance_policy_id = policy.id
        self.insurance_authorization_id = auth.id
        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Pre-Authorization"),
            "res_model": "clinic.insurance.authorization",
            "view_mode": "form",
            "res_id": auth.id,
        }

    def action_open_insurance_authorization(self):
        self.ensure_one()
        if not self.insurance_authorization_id:
            raise UserError(_("No Insurance Authorization is linked to this Booking."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Pre-Authorization"),
            "res_model": "clinic.insurance.authorization",
            "view_mode": "form",
            "res_id": self.insurance_authorization_id.id,
        }


class ClinicAppointment(models.Model):
    """Insurance bridge for Appointment.

    The user's current clinic_queue_room still contains historical definitions
    in appointment_inherit.py, but that file is commented out from
    models/__init__.py and therefore contributes no runtime fields.
    """

    _inherit = "clinic.appointment"

    insurance_policy_id = fields.Many2one(
        "clinic.insurance.policy",
        string="Insurance Policy",
        check_company=True,
        ondelete="set null",
        index=True,
        domain="[('partner_id', '=', patient_id), ('company_id', '=', company_id), ('state', '=', 'active')]",
        help="Insurance policy used for this appointment.",
    )
    authorization_id = fields.Many2one(
        "clinic.insurance.authorization",
        string="Insurance Authorization",
        check_company=True,
        ondelete="set null",
        index=True,
        domain="[('policy_id', '=', insurance_policy_id), ('state', 'in', ('approved','partial'))]",
        help="Approved insurance authorization used for this appointment.",
    )
    insurance_authorization_state = fields.Selection(
        related="authorization_id.state",
        readonly=True,
        string="Insurance Authorization State",
    )

    def action_create_insurance_authorization(self):
        self.ensure_one()
        partner = self.patient_id or self.partner_id
        patient = self.env["clinic.patient"].search([
            ("partner_id", "=", partner.id),
            ("company_id", "=", self.company_id.id),
        ], limit=1)
        if not patient:
            raise UserError(_("The Appointment patient has no Clinic Patient Card."))

        policy = self.insurance_policy_id or self.env["clinic.insurance.policy"].search([
            ("patient_id", "=", patient.id),
            ("company_id", "=", self.company_id.id),
            ("state", "=", "active"),
            ("currently_valid", "=", True),
        ], order="start_date desc, id desc", limit=1)
        if not policy:
            raise UserError(_("No active Insurance Policy is available for this Appointment."))

        service_date = (
            fields.Date.to_date(self.start)
            if "start" in self._fields and self.start
            else fields.Date.context_today(self)
        )
        auth = self.env["clinic.insurance.authorization"].create({
            "policy_id": policy.id,
            "patient_id": patient.id,
            "company_id": self.company_id.id,
            "source_type": "appointment",
            "appointment_id": self.id,
            "treatment_id": self.treatment_id.id or False,
            "service_date": service_date,
        })
        auth.action_prepare()
        self.insurance_policy_id = policy.id
        self.authorization_id = auth.id
        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Pre-Authorization"),
            "res_model": "clinic.insurance.authorization",
            "view_mode": "form",
            "res_id": auth.id,
        }


class ClinicTreatment(models.Model):
    """Insurance bridge for Treatment.

    clinic_queue_room/treatment_inherit.py contains historical insurance fields,
    but the current clinic_queue_room/models/__init__.py does not import that
    file.  These fields must therefore be defined by the Insurance addon itself.
    """

    _inherit = "clinic.treatment"

    insurance_policy_id = fields.Many2one(
        "clinic.insurance.policy",
        string="Insurance Policy",
        check_company=True,
        ondelete="set null",
        index=True,
        domain="[('partner_id', '=', patient_id), ('company_id', '=', company_id), ('state', '=', 'active')]",
        help="Insurance policy used for this treatment.",
    )
    authorization_id = fields.Many2one(
        "clinic.insurance.authorization",
        string="Insurance Authorization",
        check_company=True,
        ondelete="set null",
        index=True,
        domain="[('policy_id', '=', insurance_policy_id), ('state', 'in', ('approved','partial'))]",
        help="Approved insurance authorization used for this treatment.",
    )
    insurance_authorization_state = fields.Selection(
        related="authorization_id.state",
        readonly=True,
        string="Insurance Authorization State",
    )

    def action_create_insurance_authorization(self):
        self.ensure_one()
        patient = self.env["clinic.patient"].search([
            ("partner_id", "=", self.patient_id.id),
            ("company_id", "=", self.company_id.id),
        ], limit=1)
        if not patient:
            raise UserError(_("The Treatment patient has no Clinic Patient Card."))

        policy = self.insurance_policy_id or self.env["clinic.insurance.policy"].search([
            ("patient_id", "=", patient.id),
            ("company_id", "=", self.company_id.id),
            ("state", "=", "active"),
            ("currently_valid", "=", True),
        ], order="start_date desc, id desc", limit=1)
        if not policy:
            raise UserError(_("No active Insurance Policy is available for this Treatment."))

        auth = self.env["clinic.insurance.authorization"].create({
            "policy_id": policy.id,
            "patient_id": patient.id,
            "company_id": self.company_id.id,
            "source_type": "treatment",
            "treatment_id": self.id,
            "service_date": fields.Date.context_today(self),
        })
        auth.action_prepare()
        self.insurance_policy_id = policy.id
        self.authorization_id = auth.id
        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Pre-Authorization"),
            "res_model": "clinic.insurance.authorization",
            "view_mode": "form",
            "res_id": auth.id,
        }


class ClinicEncounter(models.Model):
    """Insurance Policy/Authorization traceability from the clinical Encounter."""

    _inherit = "clinic.encounter"

    insurance_policy_id = fields.Many2one(
        "clinic.insurance.policy",
        string="Insurance Policy",
        check_company=True,
        ondelete="set null",
        domain="[('patient_id', '=', patient_id), ('company_id', '=', company_id), ('state', '=', 'active')]",
    )
    insurance_authorization_id = fields.Many2one(
        "clinic.insurance.authorization",
        string="Insurance Authorization",
        check_company=True,
        ondelete="set null",
        domain="[('policy_id', '=', insurance_policy_id), ('state', 'in', ('approved','partial'))]",
    )
    insurance_authorization_state = fields.Selection(
        related="insurance_authorization_id.state",
        readonly=True,
    )

    def action_create_insurance_authorization(self):
        self.ensure_one()
        policy = self.insurance_policy_id or self.env["clinic.insurance.policy"].search([
            ("patient_id", "=", self.patient_id.id),
            ("company_id", "=", self.company_id.id),
            ("state", "=", "active"),
            ("currently_valid", "=", True),
        ], order="start_date desc, id desc", limit=1)
        if not policy:
            raise UserError(_("No active Insurance Policy is available for this Encounter."))

        service_date = (
            self.date_planned_start.date()
            if self.date_planned_start
            else fields.Date.context_today(self)
        )
        auth = self.env["clinic.insurance.authorization"].create({
            "policy_id": policy.id,
            "patient_id": self.patient_id.id,
            "company_id": self.company_id.id,
            "source_type": "encounter",
            "encounter_id": self.id,
            "treatment_id": self.treatment_id.id or False,
            "service_date": service_date,
        })
        auth.action_prepare()
        self.insurance_policy_id = policy.id
        self.insurance_authorization_id = auth.id
        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Pre-Authorization"),
            "res_model": "clinic.insurance.authorization",
            "view_mode": "form",
            "res_id": auth.id,
        }


# Billing remains owner of invoice lifecycle; this bridge only carries structured Policy/Authorization context.
class ClinicBillingInvoice(models.Model):
    """Structured Insurance Policy/Authorization linkage for Billing and Claims."""

    _inherit = "clinic.billing.invoice"

    insurance_policy_id = fields.Many2one(
        "clinic.insurance.policy",
        string="Insurance Policy",
        check_company=True,
        ondelete="set null",
        domain="[('partner_id', '=', patient_id), ('company_id', '=', company_id)]",
    )
    insurance_authorization_id = fields.Many2one(
        "clinic.insurance.authorization",
        string="Insurance Authorization",
        check_company=True,
        ondelete="set null",
        domain="[('policy_id', '=', insurance_policy_id)]",
    )

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company

            policy = self.env["clinic.insurance.policy"].browse(vals.get("insurance_policy_id"))
            authorization = self.env["clinic.insurance.authorization"].browse(
                vals.get("insurance_authorization_id")
            )

            if not policy and company.clinic_insurance_auto_link_policy_to_billing:
                booking = self.env["booking.booking"].browse(vals.get("booking_id"))
                encounter = self.env["clinic.encounter"].browse(vals.get("encounter_id"))

                if booking.exists():
                    policy = booking.insurance_policy_id
                    authorization = authorization or booking.insurance_authorization_id
                elif encounter.exists():
                    policy = encounter.insurance_policy_id
                    authorization = authorization or encounter.insurance_authorization_id

            if policy:
                vals.setdefault("insurance_policy_id", policy.id)
                vals.setdefault("insurer_partner_id", policy.insurer_partner_id.id)
                vals.setdefault("insurance_policy_number", policy.policy_number)
                vals.setdefault("insurance_coverage_percent", policy.coverage_percent)
                vals.setdefault("insurance_copay_percent", policy.copay_percent)
            if authorization:
                vals.setdefault("insurance_authorization_id", authorization.id)

            prepared.append(vals)

        return super().create(prepared)

    @api.onchange("insurance_policy_id")
    def _onchange_insurance_policy(self):
        for invoice in self:
            policy = invoice.insurance_policy_id
            if not policy:
                continue
            invoice.insurer_partner_id = policy.insurer_partner_id
            invoice.insurance_policy_number = policy.policy_number
            invoice.insurance_coverage_percent = policy.coverage_percent
            invoice.insurance_copay_percent = policy.copay_percent

    @api.constrains(
        "insurance_policy_id",
        "insurance_authorization_id",
        "patient_id",
        "company_id",
    )
    def _check_insurance_billing_scope(self):
        for invoice in self:
            if invoice.insurance_policy_id:
                if invoice.insurance_policy_id.partner_id != invoice.patient_id:
                    raise ValidationError(_("Billing Insurance Policy belongs to a different patient."))
                if invoice.insurance_policy_id.company_id != invoice.company_id:
                    raise ValidationError(_("Billing Insurance Policy belongs to a different company."))
            if invoice.insurance_authorization_id:
                if invoice.insurance_authorization_id.policy_id != invoice.insurance_policy_id:
                    raise ValidationError(_("Billing Insurance Authorization must belong to the selected Policy."))

    def action_open_insurance_policy(self):
        self.ensure_one()
        if not self.insurance_policy_id:
            raise UserError(_("No Insurance Policy is linked to this Billing Invoice."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Policy"),
            "res_model": "clinic.insurance.policy",
            "view_mode": "form",
            "res_id": self.insurance_policy_id.id,
        }

    def action_open_insurance_authorization(self):
        self.ensure_one()
        if not self.insurance_authorization_id:
            raise UserError(_("No Insurance Authorization is linked to this Billing Invoice."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Insurance Pre-Authorization"),
            "res_model": "clinic.insurance.authorization",
            "view_mode": "form",
            "res_id": self.insurance_authorization_id.id,
        }

