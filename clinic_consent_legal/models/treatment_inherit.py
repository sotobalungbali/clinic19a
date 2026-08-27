
# -*- coding: utf-8 -*-
# File: clinic_consent_legal/models/treatment_inherit.py
#
# Extends clinic.treatment with Consent & Legal capabilities (Odoo 18 CE).
# Naming convention unified to `clinic.*`.
#
# Key capabilities added:
# - Consent policy per treatment (required/optional + timing)
# - Default consent template per treatment + list of associated templates
# - Override validity days at treatment level
# - Autogeneration hint for booking flows (used by clinic_booking)
# - Metrics: consent counts by state for this treatment
# - Actions: view consents/templates, request new consent for a patient
# - Helpers for other modules: ensure_preprocedure_consent(), suggest template, etc.
#
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ClinicTreatment(models.Model):
    _inherit = "clinic.treatment"

    # -------------------------------------------------------------------------
    # CONSENT POLICY & DEFAULTS
    # -------------------------------------------------------------------------
    consent_required = fields.Boolean(
        string="Consent Required",
        default=True,
        help="If checked, a consent is required for this treatment."
    )

    consent_required_timing = fields.Selection(
        selection=[
            ("before_procedure", "Before Procedure"),
            ("before_booking", "Before Booking"),
            ("optional", "Optional"),
        ],
        string="Consent Timing",
        default="before_procedure",
        help="When the consent must be signed relative to the patient journey."
    )

    consent_default_template_id = fields.Many2one(
        "clinic.consent.template",
        string="Default Consent Template",
        domain=(
            "[('legal_governed', '=', True), ('state', '=', 'published'), '|', "
            "('applicability', '=', 'generic'), "
            "'&', ('applicability', '=', 'treatment'), ('treatment_id', '=', id)]"
        ),
        help="Default template suggested when creating a consent for this treatment."
    )

    consent_template_ids = fields.One2many(
        "clinic.consent.template",
        "treatment_id",
        string="Associated Consent Templates",
        domain=[("legal_governed", "=", True), ("applicability", "=", "treatment")],
        help="All templates whose applicability is 'Specific Treatment' for this treatment."
    )

    consent_validity_days_override = fields.Integer(
        string="Consent Validity Override (days)",
        help="If set, consents created for this treatment will use this validity instead of "
             "the template's default validity."
    )

    consent_autogenerate_on_booking = fields.Boolean(
        string="Autogenerate on Booking",
        default=False,
        help="If enabled, downstream booking flows may automatically create a consent "
             "for the patient when this treatment is booked."
    )

    # Optionally show an advisory message in UI
    consent_advisory = fields.Text(
        string="Consent Advisory",
        help="Optional advisory message for staff about consent specifics for this treatment."
    )

    # -------------------------------------------------------------------------
    # METRICS
    # -------------------------------------------------------------------------
    consent_count_total = fields.Integer(
        string="Consents (Total)",
        compute="_compute_consent_metrics",
        help="Total number of consents created for this treatment."
    )
    consent_count_pending = fields.Integer(
        string="Consents (Waiting)",
        compute="_compute_consent_metrics",
        help="Number of consents in 'Waiting for Signature' state for this treatment."
    )
    consent_count_signed = fields.Integer(
        string="Consents (Signed)",
        compute="_compute_consent_metrics",
        help="Number of signed consents for this treatment."
    )
    consent_count_archived = fields.Integer(
        string="Consents (Archived)",
        compute="_compute_consent_metrics",
        help="Number of archived consents for this treatment."
    )

    has_published_specific_template = fields.Boolean(
        string="Has Published Specific Template",
        compute="_compute_template_flags",
        help="True if there is at least one published template specifically bound to this treatment."
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _company_domain(self):
        """Limit by allowed companies of current environment (multi-company safety)."""
        companies = self.env.companies.ids
        return [("company_id", "in", companies)]

    def _compute_consent_metrics(self):
        Consent = self.env["clinic.consent.form"].sudo()
        for rec in self:
            base = [("treatment_id", "=", rec.id)] + rec._company_domain()
            total = Consent.search_count(base)
            waiting = Consent.search_count(base + [("state", "=", "to_sign")])
            signed = Consent.search_count(base + [("state", "=", "signed")])
            archived = Consent.search_count(base + [("state", "=", "archived")])
            rec.consent_count_total = total
            rec.consent_count_pending = waiting
            rec.consent_count_signed = signed
            rec.consent_count_archived = archived

    def _compute_template_flags(self):
        Template = self.env["clinic.consent.template"].sudo()
        for rec in self:
            has_specific = bool(Template.search_count([
                ("legal_governed", "=", True),
                ("state", "=", "published"),
                ("applicability", "=", "treatment"),
                ("treatment_id", "=", rec.id),
            ] + rec._company_domain()))
            rec.has_published_specific_template = has_specific

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("consent_required", "consent_default_template_id")
    def _check_required_template(self):
        """
        If consent is required and timing is strict (before booking/procedure),
        ensure at least a usable template exists (either default or any published specific).
        """
        Template = self.env["clinic.consent.template"].sudo()
        for rec in self:
            if not rec.consent_required:
                continue
            if rec.consent_required_timing in ("before_booking", "before_procedure"):
                if rec.consent_default_template_id:
                    continue
                exists = bool(Template.search_count([
                    ("legal_governed", "=", True),
                    ("state", "=", "published"),
                    ("applicability", "=", "treatment"),
                    ("treatment_id", "=", rec.id),
                ] + rec._company_domain()))
                if not exists and not self.env.context.get("allow_missing_consent_template"):
                    raise ValidationError(_(
                        "Consent is required for '%s', but no default or published specific template is available."
                    ) % (rec.display_name or rec.name))

    @api.constrains("consent_validity_days_override")
    def _check_validity_override(self):
        for rec in self:
            if rec.consent_validity_days_override is not None and rec.consent_validity_days_override < 0:
                raise ValidationError(_("Consent Validity Override cannot be negative."))

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("consent_required")
    def _onchange_consent_required(self):
        if not self.consent_required:
            # Keep data but show a gentle warning for awareness
            return {
                "warning": {
                    "title": _("Consent Not Required"),
                    "message": _(
                        "This treatment no longer requires consent. "
                        "Downstream modules (booking/encounter) may not enforce consent checks."
                    ),
                }
            }
        return {}

    # -------------------------------------------------------------------------
    # SUGGESTION / SELECTION
    # -------------------------------------------------------------------------
    def _get_suggested_template(self):
        """
        Return a published template for this treatment, preferring:
        1) Default template set on treatment
        2) Latest published 'Specific Treatment' template
        3) Any published 'Generic' template (fallback)
        """
        self.ensure_one()
        Template = self.env["clinic.consent.template"].sudo()
        # 1) explicit default
        if self.consent_default_template_id and self.consent_default_template_id.state == "published":
            return self.consent_default_template_id

        # 2) latest published specific for this treatment (sort by effective_date desc, id desc)
        specific = Template.search([
            ("legal_governed", "=", True),
            ("state", "=", "published"),
            ("applicability", "=", "treatment"),
            ("treatment_id", "=", self.id),
        ] + self._company_domain(), order="effective_date desc, id desc", limit=1)
        if specific:
            return specific

        # 3) any published generic
        generic = Template.search([
            ("legal_governed", "=", True),
            ("state", "=", "published"),
            ("applicability", "=", "generic"),
        ] + self._company_domain(), order="effective_date desc, id desc", limit=1)
        return generic or False

    # -------------------------------------------------------------------------
    # HELPERS FOR OTHER MODULES
    # -------------------------------------------------------------------------
    def ensure_preprocedure_consent(self, patient_id):
        """
        Raise UserError if a valid signed consent is required but not found for the given patient.
        To be called by booking/encounter modules before allowing the procedure/session.
        """
        self.ensure_one()
        if not self.consent_required:
            return True

        Consent = self.env["clinic.consent.form"].sudo()
        domain = [
            ("patient_id", "=", patient_id),
            ("treatment_id", "=", self.id),
            ("state", "=", "signed"),
        ] + self._company_domain()
        signed = Consent.search(domain, order="signature_datetime desc, id desc", limit=1)
        if not signed:
            raise UserError(_(
                "A signed consent is required for '%s' but none was found for this patient."
            ) % (self.display_name or self.name))
        if signed.is_expired:
            raise UserError(_(
                "The signed consent for '%s' is expired. Please acquire a new consent."
            ) % (self.display_name or self.name))
        return True

    
    # def prepare_consent_vals_from_treatment(
    #     self, patient_id, doctor_id=False, booking_id=False, encounter_id=False, room_session_id=False, source="in_clinic"
    # ):
    def prepare_consent_vals_from_treatment(
        self, patient_id, doctor_id=False, booking_id=False, room_session_id=False, source="in_clinic"
    ):
        """
        Provide default values for creating a consent form from this treatment.
        Used by booking flows or other modules that want to auto-create consents.
        """
        self.ensure_one()
        template = self._get_suggested_template()
        if not template and self.consent_required and self.consent_required_timing in ("before_booking", "before_procedure"):
            # Strict flows should stop here; controllers can catch & show a clear message
            raise UserError(_(
                "No published consent template is available for '%s'. Please configure a template first."
            ) % (self.display_name or self.name))

        vals = {
            "patient_id": patient_id,
            "doctor_id": doctor_id or False,
            "treatment_id": self.id,
            "booking_id": booking_id or False,
            # "encounter_id": encounter_id or False,
            "room_session_id": room_session_id or False,
            "source": source or "in_clinic",
            "state": "draft",
        }
        if template:
            # Use template helper to prepare values
            vals.update(
                template._prepare_consent_vals_from_template(
                    patient_id=patient_id,
                    treatment_id=self.id,
                    doctor_id=doctor_id or False,
                    booking_id=booking_id or False,
                    # encounter_id=encounter_id or False,
                    room_session_id=room_session_id or False,
                    source=source or "in_clinic",
                    title=template.title,
                )
            )
            # Apply validity override if present
            if self.consent_validity_days_override:
                vals["validity_days"] = self.consent_validity_days_override
        return vals

    # -------------------------------------------------------------------------
    # ACTIONS (UI)
    # -------------------------------------------------------------------------
    def action_view_consents(self):
        """Open consents related to this treatment (all patients)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Consents for Treatment"),
            "res_model": "clinic.consent.form",
            "view_mode": "list,form,kanban,calendar,pivot,graph",
            "domain": [("treatment_id", "=", self.id)] + self._company_domain(),
            "context": {"search_default_group_by_state": 1},
        }

    def action_view_templates(self):
        """Open consent templates related to this treatment (specific + allow generic)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Consent Templates"),
            "res_model": "clinic.consent.template",
            "view_mode": "list,form",
            "domain": [
                ("legal_governed", "=", True),
                ("state", "=", "published"),
                "|",
                "&",
                ("applicability", "=", "treatment"),
                ("treatment_id", "=", self.id),
                ("applicability", "=", "generic"),
            ] + self._company_domain(),
            "context": {
                "default_legal_governed": True,
                "default_scope": "treatment_general",
                "default_applicability": "treatment",
                "default_treatment_id": self.id,
            },
        }

    
    # def action_request_consent_for_patient(
    #     self, patient_id, doctor_id=False, booking_id=False, encounter_id=False, room_session_id=False, send_to_sign=False
    # ):
    def action_request_consent_for_patient(
        self, patient_id, doctor_id=False, booking_id=False, room_session_id=False, send_to_sign=False
    ):
        """
        Create a consent for the given patient based on the suggested/default template, and
        optionally advance to 'Waiting for Signature'.
        Returns an act_window to open the created consent in form view.
        """
        Consent = self.env["clinic.consent.form"].sudo()
        self.ensure_one()
        if not patient_id:
            raise UserError(_("Please provide a Patient."))

        vals = self.prepare_consent_vals_from_treatment(
            patient_id=patient_id,
            doctor_id=doctor_id or False,
            booking_id=booking_id or False,
            # encounter_id=encounter_id or False,
            room_session_id=room_session_id or False,
            source="in_clinic",
        )
        consent = Consent.create(vals)

        if send_to_sign:
            consent.action_set_to_sign()

        return {
            "type": "ir.actions.act_window",
            "name": _("Consent"),
            "res_model": "clinic.consent.form",
            "view_mode": "form",
            "res_id": consent.id,
            "target": "current",
        }

    # -------------------------------------------------------------------------
    # NAME/UX HELPERS
    # -------------------------------------------------------------------------
    def get_consent_summary_badge(self):
        """
        Return a small dict for kanban badges (to be used in QWeb/kanban view):
        {'total': X, 'waiting': Y, 'signed': Z, 'archived': A}
        """
        self.ensure_one()
        return {
            "total": self.consent_count_total,
            "waiting": self.consent_count_pending,
            "signed": self.consent_count_signed,
            "archived": self.consent_count_archived,
        }
