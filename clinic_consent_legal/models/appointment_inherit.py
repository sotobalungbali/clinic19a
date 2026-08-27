
# -*- coding: utf-8 -*-
# File: clinic_consent_legal/models/doctor_schedule_inherit.py
#
# Extends clinic.appointment with Consent & Legal capabilities (Odoo 18 CE).
# This replaces the earlier assumption of "clinic.doctor.schedule".
#
# Design notes:
# - Patient resolution is resilient:
#     1) Use appointment.patient_id if present
#     2) Else map from appointment.partner_id -> clinic.patient (unique match) if module installed
#     3) Else try booking/room_session (if such fields exist on appointment via other addons)
# - Treatment resolution tries direct fields or related booking/session if present
# - All strings in English per product requirement
#
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class ClinicAppointmentConsent(models.Model):
    _inherit = "clinic.appointment"

    # -------------------------------------------------------------------------
    # CONSENT POLICY (Per Appointment)
    # -------------------------------------------------------------------------
    consent_policy = fields.Selection(
        selection=[
            ("inherit_treatment", "Inherit from Treatment"),
            ("override_required", "Override: Required"),
            ("override_optional", "Override: Optional"),
        ],
        string="Consent Policy",
        default="inherit_treatment",
        help=(
            "How consent is enforced for this appointment:\n"
            "- Inherit from Treatment: follow the treatment's consent requirements.\n"
            "- Override: Required: force a consent for this session.\n"
            "- Override: Optional: do not require consent for this session."
        ),
        tracking=True,
    )

    consent_template_id = fields.Many2one(
        "clinic.consent.template",
        string="Preferred Consent Template",
        domain="[('legal_governed', '=', True), ('state', '=', 'published')]",
        help=(
            "Preferred template when creating a consent from this appointment. "
            "If empty, the system will suggest from the treatment's default/specific/generic templates."
        ),
        tracking=True,
    )

    consent_validity_days_override = fields.Integer(
        string="Consent Validity Override (days)",
        help=(
            "If set, consents created from this appointment will use this validity instead "
            "of the template/treatment default."
        ),
    )

    # -------------------------------------------------------------------------
    # EFFECTIVE REQUIREMENT & STATUS (Computed vs patient/treatment context)
    # -------------------------------------------------------------------------
    consent_required_effective = fields.Boolean(
        string="Consent Required (Effective)",
        compute="_compute_consent_effective",
        store=False,
        help="Effective consent requirement for this appointment, derived from policy and treatment.",
    )

    consent_status = fields.Selection(
        selection=[
            ("unknown", "Unknown Context"),
            ("not_required", "Not Required"),
            ("missing", "Missing"),
            ("waiting", "Waiting for Signature"),
            ("signed_valid", "Signed (Valid)"),
            ("signed_expired", "Signed (Expired)"),
        ],
        string="Consent Status",
        compute="_compute_consent_status",
        store=False,
        help="Consent status resolved against the current patient/treatment context.",
    )

    consent_id = fields.Many2one(
        "clinic.consent.form",
        string="Resolved Consent",
        compute="_compute_consent_status",
        store=False,
        help="The most relevant consent for this appointment (signed/waiting).",
    )

    consent_status_hint = fields.Text(
        string="Consent Status Hint",
        compute="_compute_consent_status",
        store=False,
        help="A short human-readable explanation of the consent status.",
    )

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------
    def _company_domain(self):
        # Multi-company safety: restrict to current company unless explicitly cross-company
        company = self.env.company
        return [("company_id", "=", company.id)] if "company_id" in self.env["clinic.consent.form"]._fields else []

    def _resolve_patient_id(self):
        """Resolve the consent patient as a ``res.partner`` id.

        ``clinic.consent.form.patient_id`` intentionally stores the patient contact
        (res.partner).  clinic.appointment also carries an optional
        ``clinic.patient`` link, therefore using its raw integer id here would be a
        cross-model id bug.  Prefer partner_id and only use clinic.patient after
        translating it back to its partner.
        """
        self.ensure_one()

        if "partner_id" in self._fields and self.partner_id:
            return self.partner_id.id

        if "patient_id" in self._fields and self.patient_id:
            patient = self.patient_id
            if getattr(patient, "_name", "") == "res.partner":
                return patient.id
            if "partner_id" in patient._fields and patient.partner_id:
                return patient.partner_id.id

        for field_name in ("booking_id", "room_session_id"):
            if field_name not in self._fields:
                continue
            parent = self[field_name]
            if not parent:
                continue
            if "patient_id" in parent._fields and parent.patient_id:
                patient = parent.patient_id
                if getattr(patient, "_name", "") == "res.partner":
                    return patient.id
                if "partner_id" in patient._fields and patient.partner_id:
                    return patient.partner_id.id
            if "partner_id" in parent._fields and parent.partner_id:
                return parent.partner_id.id

        return False

    def _resolve_treatment_id(self):
        """Resolve treatment_id across multiple possible fields safely."""
        self.ensure_one()
        # direct on appointment
        if "treatment_id" in self._fields and self.treatment_id:
            return self.treatment_id.id
        # via booking
        if "booking_id" in self._fields and self.booking_id and hasattr(self.booking_id, "treatment_id"):
            return self.booking_id.treatment_id.id or False
        # via room session
        if "room_session_id" in self._fields and self.room_session_id and hasattr(self.room_session_id, "treatment_id"):
            return self.room_session_id.treatment_id.id or False
        return False

    def _get_treatment_record(self):
        """Return a clinic.treatment record if a treatment can be resolved."""
        Treatment = self.env["clinic.treatment"].sudo()
        tid = self._resolve_treatment_id()
        return tid and Treatment.browse(tid).exists() or Treatment.browse()

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_consent_effective(self):
        for rec in self:
            required = False
            if rec.consent_policy == "override_required":
                required = True
            elif rec.consent_policy == "override_optional":
                required = False
            else:
                # inherit from treatment if present; otherwise leave False
                treatment = rec._get_treatment_record()
                if treatment:
                    required = bool(getattr(treatment, "consent_required", False))
            rec.consent_required_effective = required

    def _compute_consent_status(self):
        Consent = self.env["clinic.consent.form"].sudo()
        for rec in self:
            pid = rec._resolve_patient_id()
            treatment = rec._get_treatment_record()
            rec.consent_id = False
            rec.consent_status_hint = False

            # If no patient context, status unknown
            if not pid:
                rec.consent_status = "unknown"
                rec.consent_status_hint = _("No patient context available on this appointment.")
                continue

            # Determine effective requirement
            required = rec.consent_required_effective
            if not required:
                rec.consent_status = "not_required"
                rec.consent_status_hint = _("Consent not required for this appointment.")
                continue

            # Find latest signed consent, preferring the same treatment while
            # allowing legally governed generic-template consents as fallback.
            domain_signed = [
                ("patient_id", "=", pid),
                ("state", "=", "signed"),
            ] + rec._company_domain()
            if treatment:
                domain_signed += [
                    "|",
                    ("treatment_id", "=", treatment.id),
                    "&",
                    ("treatment_id", "=", False),
                    ("template_id.applicability", "=", "generic"),
                ]

            latest = Consent.search(
                domain_signed,
                order="signature_datetime desc, id desc",
                limit=1,
            )
            if latest:
                rec.consent_id = latest.id
                if getattr(latest, "is_expired", False):
                    rec.consent_status = "signed_expired"
                    rec.consent_status_hint = _("Latest consent has expired.")
                else:
                    rec.consent_status = "signed_valid"
                    rec.consent_status_hint = _("Latest consent is valid.")
                continue

            # No signed consent; check for pending
            pending = Consent.search([("patient_id", "=", pid), ("state", "=", "waiting")] + rec._company_domain(),
                                     order="create_date desc, id desc", limit=1)
            if pending:
                rec.consent_id = pending.id
                rec.consent_status = "waiting"
                rec.consent_status_hint = _("A consent request is waiting for signature.")
            else:
                rec.consent_status = "missing"
                rec.consent_status_hint = _("No signed consent found for this appointment.")

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_create_consent(self):
        """Create a legal consent for this appointment from a governed template."""
        self.ensure_one()
        partner_id = self._resolve_patient_id()
        if not partner_id:
            raise UserError(_("Cannot create consent without a patient context."))

        Template = self.env["clinic.consent.template"].sudo()
        template = self.consent_template_id
        treatment = self._get_treatment_record()

        if (
            not template
            and treatment
            and hasattr(treatment, "consent_default_template_id")
            and treatment.consent_default_template_id
        ):
            template = treatment.consent_default_template_id

        if not template and treatment and hasattr(treatment, "_get_suggested_template"):
            template = treatment._get_suggested_template()

        if not template:
            template = Template.search(
                [
                    ("legal_governed", "=", True),
                    ("state", "=", "published"),
                    ("applicability", "=", "generic"),
                ] + self._company_domain(),
                order="effective_date desc, id desc",
                limit=1,
            )

        if not template:
            raise UserError(_(
                "No published legally governed consent template is available "
                "for this appointment."
            ))

        vals = template._prepare_consent_vals_from_template(
            patient_id=partner_id,
            treatment_id=treatment.id if treatment else False,
            doctor_id=(
                self.doctor_id.id
                if "doctor_id" in self._fields and self.doctor_id
                else False
            ),
            booking_id=(
                self.booking_id.id
                if "booking_id" in self._fields and self.booking_id
                else False
            ),
            room_session_id=(
                self.room_session_id.id
                if "room_session_id" in self._fields and self.room_session_id
                else False
            ),
            source="in_clinic",
            title=template.title or template.name,
        )
        vals["appointment_id"] = self.id
        if "company_id" in self._fields and self.company_id:
            vals["company_id"] = self.company_id.id
        if self.consent_validity_days_override:
            vals["validity_days"] = self.consent_validity_days_override

        consent = self.env["clinic.consent.form"].sudo().create(vals)
        return {
            "type": "ir.actions.act_window",
            "name": _("Consent"),
            "res_model": "clinic.consent.form",
            "view_mode": "form",
            "res_id": consent.id,
            "target": "current",
        }

    def action_view_consent(self):
        """Open the resolved consent if any."""
        self.ensure_one()
        if self.consent_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Consent"),
                "res_model": "clinic.consent.form",
                "view_mode": "form",
                "res_id": self.consent_id.id,
                "target": "current",
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Not Available"),
                       "message": _("No consent is linked to this appointment."),
                       "sticky": False},
        }
