# -*- coding: utf-8 -*-
"""Clinical context reconciliation for the eMAR domain.

Important compatibility decision:
- clinic.emar.prescription keeps patient_id=clinic.patient and doctor_id=clinic.doctor.
- clinic.emar.order keeps downstream-compatible patient_id=res.partner and
  doctor_id=hr.employee because clinic_imaging extends those exact fields.
- clinic_patient_id / clinic_doctor_id preserve the canonical ClinicOne clinical
  registry references on an execution order.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


ROUTE_SELECTION = [
    ("oral", "Oral"),
    ("iv", "Intravenous"),
    ("im", "Intramuscular"),
    ("sc", "Subcutaneous"),
    ("topical", "Topical"),
    ("inhaled", "Inhaled"),
    ("ophthalmic", "Ophthalmic"),
    ("otic", "Otic"),
    ("nasal", "Nasal"),
    ("rectal", "Rectal"),
    ("vaginal", "Vaginal"),
    ("other", "Other"),
]

FREQUENCY_SELECTION = [
    ("once", "Once"),
    ("qd", "Once Daily"),
    ("bid", "Twice Daily (BID)"),
    ("tid", "Three Times Daily (TID)"),
    ("qid", "Four Times Daily (QID)"),
    ("q4h", "Every 4 Hours"),
    ("q6h", "Every 6 Hours"),
    ("q8h", "Every 8 Hours"),
    ("q12h", "Every 12 Hours"),
    ("weekly", "Weekly"),
    ("prn", "As Needed (PRN)"),
]


class ClinicEmarOrderClinicalContext(models.Model):
    _inherit = "clinic.emar.order"

    # Keep these comodels aligned with the already-installed clinic_imaging
    # extension.  Canonical ClinicOne references are kept in separate fields.
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient Contact",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
        check_company=True,
    )
    doctor_id = fields.Many2one(
        "hr.employee",
        string="Prescribing Doctor / Employee",
        index=True,
        ondelete="set null",
        tracking=True,
        check_company=True,
    )
    clinic_patient_id = fields.Many2one(
        "clinic.patient",
        string="Clinic Patient",
        index=True,
        ondelete="restrict",
        tracking=True,
        check_company=True,
    )
    clinic_doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Clinic Doctor",
        index=True,
        ondelete="set null",
        tracking=True,
        check_company=True,
    )

    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Appointment",
        index=True,
        ondelete="set null",
        tracking=True,
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        index=True,
        ondelete="set null",
        tracking=True,
    )
    vitals_intake_id = fields.Many2one(
        "clinic.vitals.intake",
        string="Vitals / Triage Intake",
        index=True,
        ondelete="set null",
        tracking=True,
    )

    order_type = fields.Selection(
        [
            ("medication", "Medication"),
            ("premedication", "Premedication"),
            ("infusion", "Infusion"),
            ("supportive", "Supportive / Adjunct"),
            ("other", "Other"),
        ],
        default="medication",
        required=True,
        tracking=True,
        index=True,
    )
    priority = fields.Selection(
        [
            ("0", "Routine"),
            ("1", "High"),
            ("2", "Urgent"),
            ("3", "STAT / Emergency"),
        ],
        default="0",
        required=True,
        tracking=True,
        index=True,
    )
    is_emergency = fields.Boolean(tracking=True)
    allow_substitution = fields.Boolean(default=True, tracking=True)
    instructions = fields.Text(tracking=True)
    contraindications = fields.Text(tracking=True)
    counseling_notes = fields.Text(tracking=True)
    date_approved = fields.Datetime(readonly=True, copy=False, tracking=True)
    date_dispensed = fields.Datetime(readonly=True, copy=False, tracking=True)
    date_completed = fields.Datetime(readonly=True, copy=False, tracking=True)

    requested_by_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        readonly=True,
        copy=False,
        index=True,
    )
    pharmacist_id = fields.Many2one("res.users", tracking=True, index=True)
    nurse_id = fields.Many2one("res.users", tracking=True, index=True)
    color = fields.Integer()

    administration_ids = fields.One2many(
        "clinic.emar.administration",
        "order_id",
        string="Administrations",
        readonly=True,
    )
    administration_count = fields.Integer(
        compute="_compute_clinical_counts",
        store=False,
    )
    line_count = fields.Integer(
        compute="_compute_clinical_counts",
        store=False,
    )

    # Compatibility alias used by clinic_imaging.  It intentionally points to
    # the same inverse as line_ids.
    order_line_ids = fields.One2many(
        "clinic.emar.medication.line",
        "order_id",
        string="Order Lines",
        readonly=False,
    )

    @api.depends("line_ids", "administration_ids")
    def _compute_clinical_counts(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.administration_count = len(rec.administration_ids)

    def _resolve_employee_from_clinic_doctor(self, doctor):
        if not doctor:
            return self.env["hr.employee"]
        user = doctor.user_id if "user_id" in doctor._fields else False
        if user:
            employee = self.env["hr.employee"].search(
                [("user_id", "=", user.id), ("company_id", "=", self.env.company.id)],
                limit=1,
            )
            if employee:
                return employee
        return self.env["hr.employee"]

    @api.onchange("clinic_patient_id", "patient_id")
    def _onchange_patient(self):
        for rec in self:
            if rec.clinic_patient_id and rec.clinic_patient_id.partner_id:
                rec.patient_id = rec.clinic_patient_id.partner_id
            elif rec.patient_id and not rec.clinic_patient_id:
                rec.clinic_patient_id = self.env["clinic.patient"].search(
                    [
                        ("partner_id", "=", rec.patient_id.id),
                        ("company_id", "=", rec.company_id.id),
                    ],
                    limit=1,
                )
            rec.partner_id = rec.patient_id
            if not rec.payer_partner_id:
                rec.payer_partner_id = rec.patient_id

    @api.onchange("clinic_doctor_id")
    def _onchange_clinic_doctor_id(self):
        for rec in self:
            employee = rec._resolve_employee_from_clinic_doctor(rec.clinic_doctor_id)
            if employee:
                rec.doctor_id = employee

    @api.constrains(
        "company_id",
        "patient_id",
        "doctor_id",
        "clinic_patient_id",
        "clinic_doctor_id",
    )
    def _check_company_consistency(self):
        for rec in self:
            for ref in (
                rec.patient_id,
                rec.doctor_id,
                rec.clinic_patient_id,
                rec.clinic_doctor_id,
            ):
                if (
                    ref
                    and "company_id" in ref._fields
                    and ref.company_id
                    and ref.company_id != rec.company_id
                ):
                    raise ValidationError(
                        _("Company mismatch between the eMAR Order and a related clinical record.")
                    )

    @api.model_create_multi
    def create(self, vals_list):
        Patient = self.env["clinic.patient"]
        Doctor = self.env["clinic.doctor"]
        for vals in vals_list:
            company_id = vals.get("company_id") or self.env.company.id
            clinic_patient_id = vals.get("clinic_patient_id")
            patient_partner_id = vals.get("patient_id")
            if clinic_patient_id and not patient_partner_id:
                patient = Patient.browse(clinic_patient_id)
                if patient.partner_id:
                    vals["patient_id"] = patient.partner_id.id
            elif patient_partner_id and not clinic_patient_id:
                patient = Patient.search(
                    [
                        ("partner_id", "=", patient_partner_id),
                        ("company_id", "=", company_id),
                    ],
                    limit=1,
                )
                if patient:
                    vals["clinic_patient_id"] = patient.id

            clinic_doctor_id = vals.get("clinic_doctor_id")
            if clinic_doctor_id and not vals.get("doctor_id"):
                doctor = Doctor.browse(clinic_doctor_id)
                employee = self._resolve_employee_from_clinic_doctor(doctor)
                if employee:
                    vals["doctor_id"] = employee.id

            vals.setdefault("partner_id", vals.get("patient_id"))
            vals.setdefault("payer_partner_id", vals.get("patient_id"))
        return super().create(vals_list)

    def write(self, vals):
        """Keep partner and canonical ClinicOne patient references synchronized.

        A multi-record write may span companies, therefore patient resolution must
        be performed record-by-record instead of returning after the first record.
        """
        vals = dict(vals)
        if vals.get("clinic_patient_id") and "patient_id" not in vals:
            patient = self.env["clinic.patient"].browse(vals["clinic_patient_id"])
            if patient.partner_id:
                vals["patient_id"] = patient.partner_id.id

        if vals.get("patient_id") and "clinic_patient_id" not in vals:
            for rec in self:
                local_vals = dict(vals)
                patient = self.env["clinic.patient"].search(
                    [
                        ("partner_id", "=", vals["patient_id"]),
                        ("company_id", "=", rec.company_id.id),
                    ],
                    limit=1,
                )
                local_vals["clinic_patient_id"] = patient.id if patient else False
                super(ClinicEmarOrderClinicalContext, rec).write(local_vals)
            return True

        return super().write(vals)

    def action_view_administrations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Administrations"),
            "res_model": "clinic.emar.administration",
            "view_mode": "list,form",
            "domain": [("order_id", "=", self.id)],
            "context": {"default_order_id": self.id},
        }


class ClinicEmarPrescriptionClinicalContext(models.Model):
    _inherit = "clinic.emar.prescription"

    appointment_id = fields.Many2one(
        "clinic.appointment",
        string="Appointment",
        index=True,
        ondelete="set null",
        tracking=True,
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        index=True,
        ondelete="set null",
        tracking=True,
    )
    vitals_intake_id = fields.Many2one(
        "clinic.vitals.intake",
        string="Vitals / Triage Intake",
        index=True,
        ondelete="set null",
        tracking=True,
    )
    prescription_type = fields.Selection(
        [
            ("outpatient", "Outpatient"),
            ("in_clinic", "In-Clinic"),
            ("discharge", "Discharge"),
            ("procedure", "Procedure / Premedication"),
        ],
        default="outpatient",
        required=True,
        tracking=True,
        index=True,
    )
    is_emergency = fields.Boolean(tracking=True)
    allow_substitution = fields.Boolean(default=True, tracking=True)
    prn = fields.Boolean(string="PRN Prescription", tracking=True)
    instructions = fields.Text(tracking=True)
    contraindications = fields.Text(tracking=True)
    counseling_notes = fields.Text(tracking=True)
    diagnosis_notes = fields.Char(tracking=True)
    date_approved = fields.Datetime(readonly=True, copy=False, tracking=True)
    color = fields.Integer()

    def _prepare_order_vals_from_prescription(self):
        self.ensure_one()
        vals = super()._prepare_order_vals_from_prescription()
        patient_partner = self.patient_id.partner_id if self.patient_id else False
        doctor_employee = self.env["hr.employee"]
        if self.doctor_id and "user_id" in self.doctor_id._fields and self.doctor_id.user_id:
            doctor_employee = self.env["hr.employee"].search(
                [
                    ("user_id", "=", self.doctor_id.user_id.id),
                    ("company_id", "=", self.company_id.id),
                ],
                limit=1,
            )
        vals.update(
            {
                "clinic_patient_id": self.patient_id.id if self.patient_id else False,
                "patient_id": patient_partner.id if patient_partner else False,
                "clinic_doctor_id": self.doctor_id.id if self.doctor_id else False,
                "doctor_id": doctor_employee.id if doctor_employee else False,
                "appointment_id": self.appointment_id.id if self.appointment_id else False,
                "treatment_id": self.treatment_id.id if self.treatment_id else False,
                "vitals_intake_id": self.vitals_intake_id.id if self.vitals_intake_id else False,
                "instructions": self.instructions,
                "contraindications": self.contraindications,
                "counseling_notes": self.counseling_notes,
                "allow_substitution": self.allow_substitution,
                "is_emergency": self.is_emergency,
                "priority": {"normal": "0", "urgent": "2", "stat": "3"}.get(self.priority, "0"),
            }
        )
        return vals


class ClinicEmarMedicationLineClinicalContext(models.Model):
    _inherit = "clinic.emar.medication.line"

    profile_id = fields.Many2one(
        "clinic.emar.medication.profile",
        string="Medication Profile",
        index=True,
        ondelete="set null",
        check_company=True,
        tracking=True,
    )
    dosage = fields.Char(
        string="Dosage Display",
        help="Human-readable dosage, e.g. 500 mg.",
        tracking=True,
    )
    route = fields.Selection(ROUTE_SELECTION, tracking=True)
    frequency = fields.Selection(FREQUENCY_SELECTION, default="qd", tracking=True, index=True)
    duration_count = fields.Integer(default=1, tracking=True)
    duration_unit = fields.Selection(
        [
            ("dose", "Dose(s)"),
            ("day", "Day(s)"),
            ("week", "Week(s)"),
            ("month", "Month(s)"),
        ],
        default="day",
        tracking=True,
    )
    notes = fields.Text()
    initial_quantity = fields.Float(readonly=True, copy=False)
    requested_lot_ids = fields.Many2many(
        "stock.lot",
        "clinic_emar_line_requested_lot_rel",
        "line_id",
        "lot_id",
        string="Preferred Lots / Serials",
        copy=False,
        domain="[('product_id', '=', product_id)]",
    )
    is_billable = fields.Boolean(default=True)
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    price_unit = fields.Monetary(currency_field="currency_id")
    discount_percent = fields.Float()
    price_subtotal = fields.Monetary(
        compute="_compute_line_amount",
        store=True,
        currency_field="currency_id",
    )

    _positive_quantity = models.Constraint(
        "CHECK(quantity > 0)",
        "Medication quantity must be greater than zero.",
    )
    _nonnegative_dose = models.Constraint(
        "CHECK(dose >= 0)",
        "Medication dose cannot be negative.",
    )
    _nonnegative_duration = models.Constraint(
        "CHECK(duration_count >= 0)",
        "Medication duration cannot be negative.",
    )

    @api.depends("quantity", "price_unit", "discount_percent", "is_billable")
    def _compute_line_amount(self):
        for rec in self:
            gross = rec.quantity * rec.price_unit if rec.is_billable else 0.0
            rec.price_subtotal = gross * (1.0 - ((rec.discount_percent or 0.0) / 100.0))

    @api.onchange("product_id")
    def _onchange_product_id_set_defaults(self):
        result = super()._onchange_product_id_set_defaults()
        for rec in self:
            if not rec.product_id:
                continue
            profile = self.env["clinic.emar.medication.profile"].search(
                [
                    ("product_id", "=", rec.product_id.id),
                    ("company_id", "=", rec.company_id.id or self.env.company.id),
                    ("active", "=", True),
                ],
                limit=1,
            )
            if profile:
                rec.profile_id = profile
                rec.route = rec.route or profile.default_route
                rec.frequency = rec.frequency or profile.default_frequency
                rec.dose_uom_id = rec.dose_uom_id or profile.dose_uom_id
                rec.is_substitutable = profile.allow_substitution
            if not rec.price_unit:
                rec.price_unit = rec.product_id.lst_price
        return result

    @api.onchange("order_id", "prescription_id")
    def _onchange_header_context_fill(self):
        for rec in self:
            order = rec.order_id
            rx = rec.prescription_id
            if order:
                rec.company_id = order.company_id
                rec.patient_id = order.clinic_patient_id
                rec.doctor_id = order.clinic_doctor_id
            elif rx:
                rec.company_id = rx.company_id
                rec.patient_id = rx.patient_id
                rec.doctor_id = rx.doctor_id

    @api.model_create_multi
    def create(self, vals_list):
        Order = self.env["clinic.emar.order"]
        Rx = self.env["clinic.emar.prescription"]
        Profile = self.env["clinic.emar.medication.profile"]
        for vals in vals_list:
            if vals.get("order_id"):
                order = Order.browse(vals["order_id"])
                vals.setdefault("company_id", order.company_id.id)
                vals.setdefault("patient_id", order.clinic_patient_id.id if order.clinic_patient_id else False)
                vals.setdefault("doctor_id", order.clinic_doctor_id.id if order.clinic_doctor_id else False)
            elif vals.get("prescription_id"):
                rx = Rx.browse(vals["prescription_id"])
                vals.setdefault("company_id", rx.company_id.id)
                vals.setdefault("patient_id", rx.patient_id.id if rx.patient_id else False)
                vals.setdefault("doctor_id", rx.doctor_id.id if rx.doctor_id else False)
            if vals.get("product_id") and not vals.get("profile_id"):
                profile = Profile.search(
                    [
                        ("product_id", "=", vals["product_id"]),
                        ("company_id", "=", vals.get("company_id") or self.env.company.id),
                        ("active", "=", True),
                    ],
                    limit=1,
                )
                if profile:
                    vals["profile_id"] = profile.id
                    vals.setdefault("route", profile.default_route)
                    vals.setdefault("frequency", profile.default_frequency)
                    vals.setdefault("dose_uom_id", profile.dose_uom_id.id if profile.dose_uom_id else False)
            vals.setdefault("initial_quantity", vals.get("quantity") or 1.0)
        return super().create(vals_list)

    def action_open_medication_profile(self):
        self.ensure_one()
        profile = self.profile_id
        if not profile and self.product_id:
            profile = self.env["clinic.emar.medication.profile"].search(
                [("product_id", "=", self.product_id.id), ("company_id", "=", self.company_id.id)],
                limit=1,
            )
        if profile:
            return {
                "type": "ir.actions.act_window",
                "name": _("Medication Clinical Profile"),
                "res_model": "clinic.emar.medication.profile",
                "view_mode": "form",
                "res_id": profile.id,
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Medication Clinical Profile"),
            "res_model": "clinic.emar.medication.profile",
            "view_mode": "form",
            "context": {
                "default_product_id": self.product_id.id if self.product_id else False,
                "default_company_id": self.company_id.id,
            },
        }

    @api.constrains("order_id", "prescription_id")
    def _check_single_header(self):
        for rec in self:
            if bool(rec.order_id) == bool(rec.prescription_id):
                raise ValidationError(
                    _("A medication line must belong to exactly one Order or one Prescription.")
                )


class ClinicEmarScheduleClinicalContext(models.Model):
    _inherit = "clinic.emar.schedule"

    @api.depends(
        "order_id",
        "line_id",
        "order_id.clinic_patient_id",
        "order_id.clinic_doctor_id",
        "order_id.company_id",
        "line_id.order_id",
        "line_id.prescription_id",
    )
    def _compute_context_refs(self):
        for rec in self:
            order = rec.order_id or rec.line_id.order_id
            rx = rec.line_id.prescription_id if rec.line_id else False
            rec.company_id = order.company_id if order else (rx.company_id if rx else self.env.company)
            rec.patient_id = (
                order.clinic_patient_id
                if order
                else (rx.patient_id if rx else False)
            )
            rec.doctor_id = (
                order.clinic_doctor_id
                if order
                else (rx.doctor_id if rx else False)
            )
            rec.prescription_id = (
                order.prescription_id
                if order and order.prescription_id
                else (rx if rx else False)
            )


class ClinicEmarAdministrationClinicalContext(models.Model):
    _inherit = "clinic.emar.administration"

    @api.depends(
        "schedule_id",
        "order_id",
        "line_id",
        "order_id.clinic_patient_id",
        "order_id.clinic_doctor_id",
        "order_id.company_id",
        "line_id.order_id",
        "line_id.prescription_id",
    )
    def _compute_context_refs(self):
        for rec in self:
            order = rec.order_id or (rec.schedule_id.order_id if rec.schedule_id else False)
            line = rec.line_id or (rec.schedule_id.line_id if rec.schedule_id else False)
            rx = (
                order.prescription_id
                if order and order.prescription_id
                else (line.prescription_id if line else False)
            )
            rec.prescription_id = rx
            rec.patient_id = (
                order.clinic_patient_id
                if order
                else (rx.patient_id if rx else False)
            )
            rec.doctor_id = (
                order.clinic_doctor_id
                if order
                else (rx.doctor_id if rx else False)
            )
