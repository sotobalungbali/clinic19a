
# -*- coding: utf-8 -*-
# File: clinic_consent_legal/models/billing_invoice_inherit.py
#
# Extends account.move (Invoice) with Consent & Legal integrations for ClinicOne (Odoo 18 CE).
# Naming convention unified to `clinic.*`.
#
# What this provides:
# - Consent policy at invoice level (inherit from treatments / override)
# - Auto-resolve required treatments from invoice lines (if present)
# - Effective consent requirement & status for the invoice's patient
# - Actions to view/request consent and link it to the invoice
# - Optional guard at posting time to ensure consent availability (bypassable via context)
#
# Soft-coupled references (optional):
#   - clinic.treatment via invoice line fields (treatment_id / clinic_treatment_id / procedure_id)
#   - booking.booking / clinic.encounter / clinic.room.session on invoice header (if used)
#   - clinic.doctor as responsible doctor on invoice header (if used)
#
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError


class AccountMove(models.Model):
    _inherit = "account.move"

    # -------------------------------------------------------------------------
    # CONTEXT LINKS (soft-coupled)
    # -------------------------------------------------------------------------
    # Patient is the invoice partner (person). We expose alias for clarity in clinic context.
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="partner_id",
        store=True,
        readonly=True,
        help="Patient to whom this invoice belongs."
    )

    # patient_id = fields.Many2one(
    #     "res.partner",
    #     string="Patient",
    #     ondelete="set null",
    #     help="Patient receiving the service. May differ from the invoice customer."
    # )

    # patient_id = fields.Many2one(
    #     "res.partner",
    #     string="Patient",
    #     related="partner_id",
    #     store=False,          # ⬅️ penting: jangan disimpan => tidak ada kolom & FK
    #     readonly=True,
    #     help="Patient to whom this invoice belongs."
    # )

    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        ondelete="set null",
        help="Optional doctor responsible for the care associated with this invoice."
    )

    # TIDAK PERLU LAGI
    # booking_id = fields.Many2one(
    #     "booking.booking",
    #     string="Booking / Appointment",
    #     ondelete="set null",
    #     help="Optional appointment related to this invoice."
    # )

    # encounter_id = fields.Many2one(
    #     "clinic.encounter",
    #     string="Clinical Encounter",
    #     ondelete="set null",
    #     help="Optional clinical encounter related to this invoice."
    # )

    room_session_id = fields.Many2one(
        "clinic.room.session",
        string="Room Session",
        ondelete="set null",
        help="Optional room session related to this invoice."
    )

    # Treatments resolved from invoice lines (computed)
    treatment_ids = fields.Many2many(
        "clinic.treatment",
        string="Treatments (Resolved)",
        compute="_compute_treatment_ids",
        help="Treatments inferred from invoice lines (if any)."
    )

    # -------------------------------------------------------------------------
    # CONSENT POLICY & STATUS
    # -------------------------------------------------------------------------
    consent_policy = fields.Selection(
        selection=[
            ("inherit_treatment", "Inherit from Treatments"),
            ("override_required", "Override: Required"),
            ("override_optional", "Override: Optional"),
        ],
        string="Consent Policy",
        default="inherit_treatment",
        help=(
            "How consent is enforced for this invoice:\n"
            "- Inherit from Treatments: require consent if any listed treatment requires it.\n"
            "- Override: Required: force a consent for this invoice.\n"
            "- Override: Optional: consent not required for this invoice."
        ),
        tracking=True,
    )

    consent_validity_days_override = fields.Integer(
        string="Consent Validity Override (days)",
        help="If set, consents created from this invoice will use this validity "
             "instead of the template/treatment default."
    )

    consent_required_effective = fields.Boolean(
        string="Consent Required (Effective)",
        compute="_compute_consent_effective",
        help="Effective consent requirement derived from policy and treatments."
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
        help="Consent status against the invoice's patient/treatment context."
    )

    consent_id = fields.Many2one(
        "clinic.consent.form",
        string="Resolved Consent",
        compute="_compute_consent_status",
        store=False,
        help="The most relevant consent (signed/waiting) matched for this invoice."
    )

    consent_status_hint = fields.Text(
        string="Consent Status Hint",
        compute="_compute_consent_status",
        help="Short explanation of the consent status."
    )

    # If True, prevent posting when consent is effectively required but missing/expired.
    enforce_consent_on_post = fields.Boolean(
        string="Enforce Consent on Posting",
        default=False,
        help=(
            "If enabled, posting this invoice will require a valid consent when "
            "consent_required_effective is True. You can bypass via context "
            "'bypass_consent_check': True."
        )
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _company_domain(self):
        companies = self.env.companies.ids
        return [("company_id", "in", companies)]

    @api.depends("invoice_line_ids.product_id", "invoice_line_ids.display_type")
    def _compute_treatment_ids(self):
        """
        Resolve treatments from invoice lines without hard dependency.
        We look for common field names on account.move.line:
          - treatment_id (Many2one to clinic.treatment)
          - clinic_treatment_id
          - procedure_id (if that model is clinic.treatment)
        If none present, leave empty.
        """
        Treatment = self.env["clinic.treatment"].sudo()
        Line = self.env["account.move.line"]

        # Cache once: which fields exist on move line?
        line_has_treatment = "treatment_id" in Line._fields
        line_has_clinic_treatment = "clinic_treatment_id" in Line._fields
        line_has_procedure = "procedure_id" in Line._fields

        for move in self:
            t_ids = set()
            for line in move.invoice_line_ids:
                if line.display_type:  # section/note lines are ignored
                    continue
                if line_has_treatment and getattr(line, "treatment_id"):
                    t_ids.add(line.treatment_id.id)
                elif line_has_clinic_treatment and getattr(line, "clinic_treatment_id"):
                    t_ids.add(line.clinic_treatment_id.id)
                elif line_has_procedure and getattr(line, "procedure_id"):
                    # Only accept if the comodel looks like clinic.treatment
                    # We check by model name on field relation when available
                    field = Line._fields.get("procedure_id")
                    if field and getattr(field, "comodel_name", "") == "clinic.treatment":
                        t_ids.add(line.procedure_id.id)

            move.treatment_ids = Treatment.browse(list(t_ids)) if t_ids else Treatment.browse()

    def _compute_consent_effective(self):
        for move in self:
            required = False
            if move.consent_policy == "override_required":
                required = True
            elif move.consent_policy == "override_optional":
                required = False
            else:
                # inherit from treatments: if any associated treatment requires consent
                required = False
                for t in move.treatment_ids:
                    if getattr(t, "consent_required", False):
                        # Timing 'before_booking' or 'before_procedure' both imply required at care time.
                        required = True
                        break
            move.consent_required_effective = required

    def _compute_consent_status(self):
        Consent = self.env["clinic.consent.form"].sudo()
        for move in self:
            move.consent_id = False
            move.consent_status_hint = False

            pid = move.patient_id.id if move.patient_id else False
            if not pid:
                move.consent_status = "unknown"
                move.consent_status_hint = _("No patient (partner) is set on the invoice.")
                continue

            if not move.consent_required_effective:
                move.consent_status = "not_required"
                move.consent_status_hint = _("Consent is not required for this invoice.")
                continue

            # Prefer a signed consent for any of the treatments involved, fallback to generic.
            domain_signed = [("patient_id", "=", pid), ("state", "=", "signed")] + move._company_domain()
            if move.treatment_ids:
                domain_signed = ["|",
                                 ("treatment_id", "in", move.treatment_ids.ids),
                                 "&", ("treatment_id", "=", False), ("template_id.applicability", "=", "generic")] + domain_signed
            latest_signed = Consent.search(domain_signed, order="signature_datetime desc, id desc", limit=1)

            if latest_signed:
                move.consent_id = latest_signed.id
                if latest_signed.expiry_date and latest_signed.expiry_date < fields.Date.context_today(move):
                    move.consent_status = "signed_expired"
                    move.consent_status_hint = _("Signed consent exists but is expired (expired on %s).") % (latest_signed.expiry_date)
                else:
                    move.consent_status = "signed_valid"
                    move.consent_status_hint = _("A valid signed consent is available.")
                continue

            # Check 'waiting for signature'
            domain_wait = [("patient_id", "=", pid), ("state", "=", "to_sign")] + move._company_domain()
            if move.treatment_ids:
                domain_wait = ["|",
                               ("treatment_id", "in", move.treatment_ids.ids),
                               "&", ("treatment_id", "=", False), ("template_id.applicability", "=", "generic")] + domain_wait
            waiting = Consent.search(domain_wait, order="create_date desc, id desc", limit=1)
            if waiting:
                move.consent_id = waiting.id
                move.consent_status = "waiting"
                move.consent_status_hint = _("A consent is pending signature.")
                continue

            move.consent_status = "missing"
            move.consent_status_hint = _("No consent record found for this invoice context.")

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains("consent_validity_days_override")
    def _check_validity_override(self):
        for rec in self:
            if rec.consent_validity_days_override is not None and rec.consent_validity_days_override < 0:
                raise ValidationError(_("Consent Validity Override cannot be negative."))

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------
    def _get_suggested_template_for_invoice(self):
        """
        Pick a published template for this invoice context:
          1) From first treatment's own suggestion
          2) Any published generic template
        """
        Template = self.env["clinic.consent.template"].sudo()
        self.ensure_one()

        # 1) use treatment helper when available
        if self.treatment_ids:
            # Prefer the first treatment by ID order
            t = self.treatment_ids.sorted("id")[0]
            if hasattr(t, "_get_suggested_template"):
                tpl = t._get_suggested_template()
                if tpl:
                    return tpl

        # 2) fallback: any published generic (latest by effective_date)
        generic = Template.search(
            [
                ("legal_governed", "=", True),
                ("state", "=", "published"),
                ("applicability", "=", "generic"),
            ] + self._company_domain(),
            order="effective_date desc, id desc",
            limit=1,
        )
        return generic or False

    def _prepare_consent_vals_from_invoice(self, template):
        """
        Build values for creating a consent from this invoice, using given template
        or minimal content if template is False (only allowed when policy is Optional).
        """
        self.ensure_one()
        pid = self.patient_id.id if self.patient_id else False
        if not pid:
            raise UserError(_("Please set a Patient (Partner) on the invoice first."))

        doctor_id = self.doctor_id.id if self.doctor_id else False
        booking_id = self.booking_id.id if self.booking_id else False
        # encounter_id = self.encounter_id.id if self.encounter_id else False
        room_session_id = self.room_session_id.id if self.room_session_id else False

        # Prefer a single treatment to bind (first one); consent is per treatment typically
        treatment_id = self.treatment_ids and self.treatment_ids.sorted("id")[0].id or False

        if template:
            vals = template._prepare_consent_vals_from_template(
                patient_id=pid,
                treatment_id=treatment_id or False,
                doctor_id=doctor_id or False,
                booking_id=booking_id or False,
                # encounter_id=encounter_id or False,
                room_session_id=room_session_id or False,
                source="in_clinic",
                title=template.title,
            )
        else:
            vals = {
                "patient_id": pid,
                "doctor_id": doctor_id or False,
                "treatment_id": treatment_id or False,
                "booking_id": booking_id or False,
                # "encounter_id": encounter_id or False,
                "room_session_id": room_session_id or False,
                "title": _("Consent"),
                "state": "draft",
                "source": "in_clinic",
            }

        # Apply invoice-level validity override if provided
        if self.consent_validity_days_override:
            vals["validity_days"] = self.consent_validity_days_override

        # Link back to invoice
        vals["invoice_id"] = self.id
        return vals

    def _check_consent_before_post(self):
        """
        Guard invoked by action_post if enforce_consent_on_post is True.
        Bypass with context key: 'bypass_consent_check' = True.
        """
        for move in self:
            if self.env.context.get("bypass_consent_check"):
                continue
            if not move.enforce_consent_on_post:
                continue
            if not move.consent_required_effective:
                continue
            # Need at least one treatment context to justify the check
            if not move.treatment_ids:
                # If you enforce consent but no treatment context, we warn but do not block
                # (to avoid blocking pure financial invoices).
                continue

            # Evaluate current status
            move._compute_consent_status()
            if move.consent_status in ("missing", "waiting"):
                raise UserError(_(
                    "Cannot post the invoice because consent is not available yet (status: %s)."
                ) % dict(move._fields["consent_status"].selection).get(move.consent_status))
            if move.consent_status == "signed_expired":
                raise UserError(_("Cannot post the invoice because the consent is expired."))

    # -------------------------------------------------------------------------
    # ACTIONS (UI)
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
        Create a consent for this invoice's context.
        Preference order for template:
          1) Treatment-suggested template (via first treatment)
          2) Any published generic template
        """
        Consent = self.env["clinic.consent.form"].sudo()
        self.ensure_one()

        # Determine template (may be False for optional policy)
        tpl = self._get_suggested_template_for_invoice()
        if not tpl and self.consent_policy in ("inherit_treatment", "override_required"):
            raise UserError(_("No published consent template is available to create a consent."))

        vals = self._prepare_consent_vals_from_invoice(template=tpl)
        consent = Consent.create(vals)

        # Back-link (in case form inverse not yet set)
        if hasattr(consent, "invoice_id") and not consent.invoice_id:
            consent.write({"invoice_id": self.id})

        if send_to_sign:
            consent.action_set_to_sign()

        # Recompute status on the invoice
        self._compute_consent_status()

        return {
            "type": "ir.actions.act_window",
            "name": _("Consent"),
            "res_model": "clinic.consent.form",
            "view_mode": "form",
            "res_id": consent.id,
            "target": "current",
        }

    def action_view_all_related_consents(self):
        """Open all consents for this invoice's patient filtered by current treatments (if any)."""
        self.ensure_one()
        if not self.patient_id:
            raise UserError(_("Please set a Patient on the invoice first."))
        domain = [("patient_id", "=", self.patient_id.id)] + self._company_domain()
        if self.treatment_ids:
            domain = ["|",
                      ("treatment_id", "in", self.treatment_ids.ids),
                      "&", ("treatment_id", "=", False), ("template_id.applicability", "=", "generic")] + domain
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Consents"),
            "res_model": "clinic.consent.form",
            "view_mode": "list,form,kanban,calendar,pivot,graph",
            "domain": domain,
            "context": {"search_default_group_by_state": 1},
        }

    # -------------------------------------------------------------------------
    # OVERRIDES
    # -------------------------------------------------------------------------
    def action_post(self):
        """
        Override to optionally enforce consent availability before posting.
        Use context 'bypass_consent_check': True to skip the check for special cases.
        """
        self._check_consent_before_post()
        return super().action_post()

    def write(self, vals):
        """
        If consent_id were a stored M2O here we’d guard edits, but it's computed.
        We only keep a tiny hook: if someone links doctor/booking/encounter/session,
        recompute status lazily.
        """
        res = super().write(vals)
        # touch_keys = {"partner_id", "doctor_id", "booking_id", "encounter_id", "room_session_id"}
        touch_keys = {"partner_id", "doctor_id", "booking_id", "room_session_id"}
        if set(vals.keys()) & touch_keys:
            self._compute_treatment_ids()
            self._compute_consent_effective()
            self._compute_consent_status()
        return res

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("consent_policy")
    def _onchange_consent_policy(self):
        if self.consent_policy == "override_optional" and self.enforce_consent_on_post:
            return {
                "warning": {
                    "title": _("Policy vs Enforcement"),
                    "message": _(
                        "Consent Policy is 'Override: Optional' while 'Enforce Consent on Posting' is enabled. "
                        "Posting will not be blocked unless Policy requires consent."
                    ),
                }
            }
        return {}

    @api.onchange("consent_validity_days_override")
    def _onchange_consent_validity_days_override(self):
        if self.consent_validity_days_override and self.consent_validity_days_override < 0:
            return {
                "warning": {
                    "title": _("Invalid Override"),
                    "message": _("Consent Validity Override cannot be negative."),
                }
            }
        return {}
