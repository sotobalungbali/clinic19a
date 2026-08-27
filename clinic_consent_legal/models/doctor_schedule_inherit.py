
# -*- coding: utf-8 -*-
# File: clinic_consent_legal/models/doctor_schedule_inherit.py
#
# Extends clinic.doctor.schedule with Consent & Legal capabilities (Odoo 18 CE).
# Naming convention unified to `clinic.*`.
#
# This inheritance assumes the existence of a base model:
#   - Model: clinic.doctor.schedule   (provided by clinic_doctor)
# Common fields in that model may include:
#   - doctor_id (clinic.doctor), start_datetime, end_datetime
#   - booking_id (booking.booking), encounter_id (clinic.encounter),
#     room_session_id (clinic.room.session)
#   - patient_id (res.partner), treatment_id (clinic.treatment)
#
# We guard all cross-field reads via `if '<field>' in self._fields` to keep it resilient
# even if particular fields are not present on the installed schedule variant.
#
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicDoctorSchedule(models.Model):
    _inherit = "clinic.doctor.schedule"

    # -------------------------------------------------------------------------
    # CONSENT POLICY (Per Schedule)
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
            "How consent is enforced for this schedule:\n"
            "- Inherit from Treatment: follow the treatment's consent requirements.\n"
            "- Override: Required: force a consent for this session.\n"
            "- Override: Optional: do not require consent for this session."
        ),
        tracking=True,
    )

    consent_template_id = fields.Many2one(
        "clinic.consent.template",
        string="Preferred Consent Template",
        domain="[('state', '=', 'published')]",
        help=(
            "Preferred template when creating a consent from this schedule. "
            "If empty, the system will suggest from the treatment's default/specific/generic templates."
        ),
        tracking=True,
    )

    consent_validity_days_override = fields.Integer(
        string="Consent Validity Override (days)",
        help=(
            "If set, consents created from this schedule will use this validity instead "
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
        help="Effective consent requirement for this schedule, derived from policy and treatment.",
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
        help="The most relevant consent for this schedule (signed/waiting).",
    )

    consent_status_hint = fields.Text(
        string="Consent Status Hint",
        compute="_compute_consent_status",
        store=False,
        help="A short human-readable explanation of the consent status.",
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _company_domain(self):
        companies = self.env.companies.ids
        return [("company_id", "in", companies)]

    def _resolve_patient_id(self):
        """Resolve patient_id across multiple possible fields safely."""
        self.ensure_one()
        # direct patient on schedule
        if "patient_id" in self._fields and self.patient_id:
            return self.patient_id.id
        # via booking
        if "booking_id" in self._fields and self.booking_id and hasattr(self.booking_id, "patient_id"):
            return self.booking_id.patient_id.id or False
        # via encounter
        # if "encounter_id" in self._fields and self.encounter_id and hasattr(self.encounter_id, "patient_id"):
        #     return self.encounter_id.patient_id.id or False
        # via room session
        if "room_session_id" in self._fields and self.room_session_id and hasattr(self.room_session_id, "patient_id"):
            return self.room_session_id.patient_id.id or False
        return False

    def _resolve_treatment_id(self):
        """Resolve treatment_id across multiple possible fields safely."""
        self.ensure_one()
        if "treatment_id" in self._fields and self.treatment_id:
            return self.treatment_id.id
        if "booking_id" in self._fields and self.booking_id and hasattr(self.booking_id, "treatment_id"):
            return self.booking_id.treatment_id.id or False
        # if "encounter_id" in self._fields and self.encounter_id and hasattr(self.encounter_id, "treatment_id"):
        #     return self.encounter_id.treatment_id.id or False
        if "room_session_id" in self._fields and self.room_session_id and hasattr(self.room_session_id, "treatment_id"):
            return self.room_session_id.treatment_id.id or False
        return False

    def _get_treatment_record(self):
        """Return a clinic.treatment record if a treatment can be resolved."""
        Treatment = self.env["clinic.treatment"].sudo()
        tid = self._resolve_treatment_id()
        return tid and Treatment.browse(tid).exists() or Treatment.browse()

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
                    # Use treatment's own policy
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
                rec.consent_status_hint = _("No patient context available on this schedule.")
                continue

            # Determine effective requirement
            required = rec.consent_required_effective
            if not required:
                rec.consent_status = "not_required"
                rec.consent_status_hint = _("Consent not required for this session.")
                continue

            # Find latest signed consent (preferring same treatment; falling back to generic)
            domain_signed = [("patient_id", "=", pid), ("state", "=", "signed")] + rec._company_domain()
            if treatment:
                # Accept either a direct treatment match OR a generic template
                domain_signed = ["|",
                                 ("treatment_id", "=", treatment.id),
                                 "&", ("treatment_id", "=", False), ("template_id.applicability", "=", "generic")] + domain_signed
            latest_signed = Consent.search(domain_signed, order="signature_datetime desc, id desc", limit=1)

            # If a signed consent exists, check expiry
            if latest_signed:
                rec.consent_id = latest_signed.id
                if latest_signed.expiry_date and latest_signed.expiry_date < fields.Date.context_today(rec):
                    rec.consent_status = "signed_expired"
                    rec.consent_status_hint = _(
                        "Signed consent is expired (expired on %s)."
                    ) % (latest_signed.expiry_date)
                else:
                    rec.consent_status = "signed_valid"
                    rec.consent_status_hint = _(
                        "Valid signed consent found (signed on %s)."
                    ) % (latest_signed.signature_datetime or latest_signed.write_date)
                continue

            # Otherwise, check if there's a waiting consent
            domain_wait = [("patient_id", "=", pid), ("state", "=", "to_sign")] + rec._company_domain()
            if treatment:
                domain_wait = ["|",
                               ("treatment_id", "=", treatment.id),
                               "&", ("treatment_id", "=", False), ("template_id.applicability", "=", "generic")] + domain_wait
            waiting = Consent.search(domain_wait, order="create_date desc, id desc", limit=1)
            if waiting:
                rec.consent_id = waiting.id
                rec.consent_status = "waiting"
                rec.consent_status_hint = _("A consent is pending signature.")
                continue

            # Missing
            rec.consent_status = "missing"
            rec.consent_status_hint = _("No consent record found for this patient and session context.")

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("consent_validity_days_override")
    def _check_validity_override(self):
        for rec in self:
            if rec.consent_validity_days_override is not None and rec.consent_validity_days_override < 0:
                raise ValidationError(_("Consent Validity Override cannot be negative."))

    # If policy says "override_required", ensure at least some template is available somewhere
    @api.constrains("consent_policy", "consent_template_id")
    def _check_required_template_availability(self):
        Template = self.env["clinic.consent.template"].sudo()
        for rec in self:
            if rec.consent_policy != "override_required":
                continue
            # If a preferred template is set, it's fine
            if rec.consent_template_id and rec.consent_template_id.state == "published":
                continue
            # Else try to find via treatment suggestion
            treatment = rec._get_treatment_record()
            if treatment:
                suggested = treatment._get_suggested_template()
                if suggested:
                    continue
            # As a last resort, any published generic template?
            any_generic = Template.search_count([("state", "=", "published"), ("applicability", "=", "generic")] + rec._company_domain())
            if not any_generic and not self.env.context.get("allow_missing_consent_template"):
                raise ValidationError(_(
                    "Consent policy requires a consent, but no published template is available for this session."
                ))

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_view_consent(self):
        """Open the resolved consent (if any)."""
        self.ensure_one()
        if not self.consent_id:
            raise UserError(_("No resolved consent is available."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Consent"),
            "res_model": "clinic.consent.form",
            "view_mode": "form",
            "res_id": self.consent_id.id,
            "target": "current",
        }

    def action_request_consent(self, send_to_sign=False):
        """
        Create a new consent for this schedule's patient/treatment context.
        Preference order:
          1) consent_template_id on schedule (if published)
          2) treatment._get_suggested_template()
          3) any published generic (fallback)
        Applies schedule-level validity override if set.
        """
        Consent = self.env["clinic.consent.form"].sudo()
        Template = self.env["clinic.consent.template"].sudo()

        self.ensure_one()
        pid = self._resolve_patient_id()
        if not pid:
            raise UserError(_("Please set a Patient on this schedule (or via booking/encounter)."))

        treatment = self._get_treatment_record()
        doctor_id = getattr(self, "doctor_id", False) and self.doctor_id.id or False
        booking_id = ("booking_id" in self._fields and self.booking_id.id) or False
        # encounter_id = ("encounter_id" in self._fields and self.encounter_id.id) or False
        room_session_id = ("room_session_id" in self._fields and self.room_session_id.id) or False

        # 1) schedule-preferred template
        tpl = False
        if self.consent_template_id and self.consent_template_id.state == "published":
            tpl = self.consent_template_id

        # 2) treatment suggestion
        if not tpl and treatment:
            tpl = treatment._get_suggested_template()

        # 3) any published generic
        if not tpl:
            tpl = Template.search([("state", "=", "published"), ("applicability", "=", "generic")] + self._company_domain(),
                                  order="effective_date desc, id desc", limit=1)

        if not tpl and self.consent_policy in ("inherit_treatment", "override_required"):
            raise UserError(_("No published consent template is available to create a consent."))

        # Build values
        if tpl:
            vals = tpl._prepare_consent_vals_from_template(
                patient_id=pid,
                treatment_id=(treatment.id if treatment else False),
                doctor_id=doctor_id or False,
                booking_id=booking_id or False,
                # encounter_id=encounter_id or False,
                room_session_id=room_session_id or False,
                source="in_clinic",
                title=tpl.title,
            )
        else:
            # Create a minimal draft consent (allowed when override_optional)
            vals = {
                "patient_id": pid,
                "doctor_id": doctor_id or False,
                "treatment_id": (treatment.id if treatment else False),
                "booking_id": booking_id or False,
                # "encounter_id": encounter_id or False,
                "room_session_id": room_session_id or False,
                "title": _("Consent"),
                "state": "draft",
                "source": "in_clinic",
            }

        # Apply schedule-level validity override
        if self.consent_validity_days_override:
            vals["validity_days"] = self.consent_validity_days_override

        consent = Consent.create(vals)
        if send_to_sign:
            consent.action_set_to_sign()

        # Refresh computes
        self._compute_consent_status()

        return {
            "type": "ir.actions.act_window",
            "name": _("Consent"),
            "res_model": "clinic.consent.form",
            "view_mode": "form",
            "res_id": consent.id,
            "target": "current",
        }

    def action_require_consent_check_in(self):
        """
        Enforce consent before check-in / start session.
        Raise a clear message if consent is missing or expired.
        """
        self.ensure_one()
        pid = self._resolve_patient_id()
        if not pid:
            raise UserError(_("Cannot validate consent because no patient is set."))

        # Compute latest status
        self._compute_consent_effective()
        self._compute_consent_status()

        if not self.consent_required_effective:
            return True

        if self.consent_status in ("missing", "waiting"):
            raise UserError(_("Consent is not available yet (status: %s).") % dict(self._fields["consent_status"].selection).get(self.consent_status))
        if self.consent_status == "signed_expired":
            raise UserError(_("Consent is expired. Please acquire a new consent."))
        if self.consent_status == "unknown":
            raise UserError(_("Consent unknown due to incomplete session context."))

        # signed_valid
        return True

    # -------------------------------------------------------------------------
    # ONCHANGE / UX
    # -------------------------------------------------------------------------
    @api.onchange("consent_policy")
    def _onchange_consent_policy(self):
        if self.consent_policy == "override_optional" and self.consent_template_id:
            return {
                "warning": {
                    "title": _("Template Not Used"),
                    "message": _(
                        "Consent Policy is 'Override: Optional'; the preferred template will not be enforced."
                    ),
                }
            }
        return {}

    @api.onchange("consent_template_id")
    def _onchange_consent_template_id(self):
        if self.consent_template_id and self.consent_policy == "override_optional":
            return {
                "warning": {
                    "title": _("Optional Policy"),
                    "message": _(
                        "A preferred template is selected but the policy is Optional. "
                        "Change policy to 'Override: Required' to enforce consent."
                    ),
                }
            }
        return {}
