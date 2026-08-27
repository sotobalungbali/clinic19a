
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
        domain="[('state', '=', 'published')]",
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
        """
        Resolve a patient id robustly:
        1) Direct appointment.patient_id (if field exists & set)
        2) Map from appointment.partner_id -> clinic.patient (unique match)
        3) Try via booking_id / room_session_id if those relations exist and expose patient_id
        """
        self.ensure_one()

        # 1) Direct field
        if "patient_id" in self._fields and self.patient_id:
            return self.patient_id.id

        # 2) Map from partner -> patient (if patient module installed)
        if "partner_id" in self._fields and self.partner_id and "clinic.patient" in self.env:
            candidates = self.env["clinic.patient"].sudo().search([("partner_id", "=", self.partner_id.id)], limit=2)
            if len(candidates) == 1:
                return candidates.id

        # 3) Indirects (if other addons add these fields on appointment)
        if "booking_id" in self._fields and self.booking_id and hasattr(self.booking_id, "patient_id"):
            return self.booking_id.patient_id.id or False
        if "room_session_id" in self._fields and self.room_session_id and hasattr(self.room_session_id, "patient_id"):
            return self.room_session_id.patient_id.id or False

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

            # Find latest signed consent (preferring same treatment; falling back to generic)
            domain_signed = [("patient_id", "=", pid), ("state", "=", "signed")] + rec._company_domain()
            if treatment:
                domain_signed = ["|",
                                 "&", ("treatment_id", "=", treatment.id)] + domain_signed + \
                                ["&", ("is_generic", "=", True)] + domain_signed

            latest = Consent.search(domain_signed, order="signed_on desc, id desc", limit=1)
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
        """
        Create a consent form for this appointment using selected template (or suggest one).
        Opens the newly created consent or returns a notification when context is insufficient.
        """
        self.ensure_one()
        pid = self._resolve_patient_id()
        if not pid:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Missing Patient"),
                    "message": _("Cannot create consent without a patient context."),
                    "sticky": False,
                },
            }

        # Choose template: explicit on appointment -> treatment default -> generic published
        Template = self.env["clinic.consent.template"].sudo()
        tmpl = self.consent_template_id
        if not tmpl:
            treatment = self._get_treatment_record()
            if treatment and hasattr(treatment, "default_consent_template_id") and treatment.default_consent_template_id:
                tmpl = treatment.default_consent_template_id
            if not tmpl:
                tmpl = Template.search([("state", "=", "published"), ("is_generic", "=", True)], limit=1)

        # Prepare vals
        vals = {
            "patient_id": pid,
            "doctor_id": self.doctor_id.id if "doctor_id" in self._fields and self.doctor_id else False,
            "appointment_id": self.id,
            "company_id": self.company_id.id if "company_id" in self._fields else False,
        }
        if tmpl:
            vals["template_id"] = tmpl.id
            if self.consent_validity_days_override:
                vals["valid_days"] = self.consent_validity_days_override

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

    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        ondelete="set null",
        help="Optional doctor responsible for the care associated with this invoice."
    )

    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking / Appointment",
        ondelete="set null",
        help="Optional appointment related to this invoice."
    )

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
            [("state", "=", "published"), ("applicability", "=", "generic")] + self._company_domain(),
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
            "view_mode": "tree,form,kanban,calendar,pivot,graph",
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

# -*- coding: utf-8 -*-
# File: clinic_consent_legal/models/consent_attachment.py
#
# Attachment registry for ClinicOne Consent & Legal Forms (Odoo 18 CE).
# Naming convention unified to `clinic.*`.
#
# Purpose:
#   - Centralize attachments related to a consent form (support docs, photos, lab results, IDs, etc.)
#   - Track file metadata (size/mime/checksum) via ir.attachment
#   - Control portal visibility per attachment with confidentiality levels
#   - Enforce edit/delete guards after consent is signed/archived
#   - Offer soft-coupled links to booking/encounter/room session for audit
#
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError


class ConsentAttachment(models.Model):
    _name = "clinic.consent.attachment"
    _description = "Consent Attachment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, create_date desc, id desc"

    # -------------------------------------------------------------------------
    # CORE / LINKS
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Title",
        required=True,
        tracking=True,
        help="Short title of the attachment (e.g., 'Pre-op Photo (Front)')."
    )

    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order for display in lists/kanban."
    )

    form_id = fields.Many2one(
        "clinic.consent.form",
        string="Consent Form",
        required=True,
        ondelete="cascade",
        index=True,
        help="The consent form this attachment belongs to."
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="form_id.company_id",
        store=True,
        index=True,
        readonly=True
    )

    # Convenience relateds (for easy filtering/reporting)
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="form_id.patient_id",
        store=True,
        index=True,
        readonly=True
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        related="form_id.doctor_id",
        store=True,
        index=True,
        readonly=True
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        related="form_id.treatment_id",
        store=True,
        index=True,
        readonly=True
    )

    # Optional deep links (soft-coupled)
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking / Appointment",
        ondelete="set null",
        help="Optional link to appointment for contextual audit."
    )
    # encounter_id = fields.Many2one(
    #     "clinic.encounter",
    #     string="Clinical Encounter",
    #     ondelete="set null",
    #     help="Optional link to clinical encounter for contextual audit."
    # )
    room_session_id = fields.Many2one(
        "clinic.room.session",
        string="Room Session",
        ondelete="set null",
        help="Optional link to room session for contextual audit."
    )

    # -------------------------------------------------------------------------
    # CLASSIFICATION & VISIBILITY
    # -------------------------------------------------------------------------
    category = fields.Selection(
        selection=[
            ("id_doc", "Identity Document"),
            ("medical_record", "Medical Record"),
            ("lab_result", "Lab Result"),
            ("imaging", "Imaging"),
            ("pre_photo", "Pre-op Photo"),
            ("post_photo", "Post-op Photo"),
            ("consent_support", "Consent Supporting Doc"),
            ("external_legal", "External Legal Document"),
            ("other", "Other"),
        ],
        string="Category",
        default="other",
        index=True,
        help="Attachment classification to support search and policies."
    )

    confidentiality = fields.Selection(
        selection=[
            ("internal", "Internal Only"),
            ("patient", "Visible to Patient"),
            ("third_party", "Shareable to Third-Party"),
        ],
        string="Confidentiality",
        default="internal",
        help="Visibility and sharing policy for this attachment."
    )

    show_on_portal = fields.Boolean(
        string="Show on Portal",
        default=False,
        help="If enabled, the attachment appears on the patient portal under the related consent."
    )

    requires_redaction = fields.Boolean(
        string="Requires Redaction",
        help="Indicates that sensitive information must be redacted before sharing."
    )

    # -------------------------------------------------------------------------
    # STORAGE (IR.ATTACHMENT OR EXTERNAL URL)
    # -------------------------------------------------------------------------
    attachment_id = fields.Many2one(
        "ir.attachment",
        string="Attachment",
        ondelete="set null",
        help="Linked file stored in Odoo filestore."
    )

    external_url = fields.Char(
        string="External URL",
        help="External link to the document if not stored as an Odoo attachment."
    )

    file_name = fields.Char(
        string="Filename",
        compute="_compute_file_meta",
        store=True,
        help="Filename derived from the linked attachment."
    )

    mimetype = fields.Char(
        string="MIME Type",
        compute="_compute_file_meta",
        store=True,
        help="MIME type derived from the linked attachment."
    )

    file_size = fields.Integer(
        string="File Size (bytes)",
        compute="_compute_file_meta",
        store=True,
        help="Size in bytes derived from the linked attachment."
    )

    checksum = fields.Char(
        string="Checksum",
        compute="_compute_file_meta",
        store=True,
        help="Checksum derived from the linked attachment."
    )

    # Redacted version (if any)
    redacted_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Redacted Attachment",
        ondelete="set null",
        help="Optional redacted copy of the attachment for sharing."
    )

    # -------------------------------------------------------------------------
    # ORIGINS & AUDIT
    # -------------------------------------------------------------------------
    origin = fields.Selection(
        selection=[
            ("backend_user", "Backend User Upload"),
            ("portal_patient", "Portal (Patient)"),
            ("api", "External API"),
            ("scanner", "Scanner/Import"),
            ("camera", "Camera Capture"),
            ("import", "Data Import"),
        ],
        string="Origin",
        default="backend_user",
        help="How this attachment was acquired."
    )

    uploaded_by = fields.Many2one(
        "res.users",
        string="Uploaded By",
        default=lambda self: self.env.user,
        help="User who uploaded/linked the attachment."
    )

    uploaded_on = fields.Datetime(
        string="Uploaded On",
        default=lambda self: fields.Datetime.now(),
        help="Timestamp when the attachment was uploaded/linked."
    )

    note = fields.Text(
        string="Internal Notes",
        help="Internal notes regarding this attachment."
    )

    # Portal deep-link (anchor), consistent with consent/signature anchors
    access_url = fields.Char(
        string="Portal URL (Anchor)",
        compute="_compute_access_url",
        help="Public portal URL (anchor to this attachment) for the parent consent."
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("attachment_id")
    def _compute_file_meta(self):
        for rec in self:
            att = rec.attachment_id.sudo() if rec.attachment_id else False
            rec.file_name = att.name if att else False
            rec.mimetype = att.mimetype if att else False
            rec.file_size = att.file_size if att and hasattr(att, "file_size") else False
            rec.checksum = att.checksum if att and hasattr(att, "checksum") else False

    def _compute_access_url(self):
        for rec in self:
            base = rec.form_id.access_url or f"/my/consents/{rec.form_id.id}"
            rec.access_url = f"{base}#att-{rec.id}"

    # -------------------------------------------------------------------------
    # CONSTRAINTS & SANITY CHECKS
    # -------------------------------------------------------------------------
    _unique_attachment_per_form = models.Constraint(
        "unique(form_id, attachment_id)",
        "The same file is already linked to this consent.",
    )

    @api.constrains("attachment_id", "external_url")
    def _check_attachment_or_url(self):
        for rec in self:
            if not rec.attachment_id and not rec.external_url:
                raise ValidationError(_("Please provide either an Attachment or an External URL."))

    @api.constrains("show_on_portal", "confidentiality")
    def _check_portal_visibility_policy(self):
        for rec in self:
            if rec.show_on_portal and rec.confidentiality not in ("patient", "third_party"):
                raise ValidationError(_(
                    "Attachments shown on the portal must have confidentiality 'Visible to Patient' "
                    "or 'Shareable to Third-Party'."
                ))

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------
    def _ensure_editable(self):
        """Prevent edits on attachments when form is signed/archived, except benign fields."""
        for rec in self:
            if rec.form_id.state in ("signed", "archived"):
                raise AccessError(_("You cannot modify attachments of a signed or archived consent."))

    def _ensure_deletable(self):
        for rec in self:
            if rec.form_id.state not in ("draft", "cancelled"):
                raise AccessError(_("You can only delete attachments when the consent is Draft or Cancelled."))

    def _link_attachment_to_form(self):
        """
        Ensure ir.attachment is linked to the consent record (res_model/res_id).
        This keeps all files discoverable from the consent's 'Attachments' smart button.
        """
        for rec in self:
            if not rec.attachment_id:
                continue
            att = rec.attachment_id.sudo()
            # Link only if not already referencing the form
            if getattr(att, "res_model", False) != rec.form_id._name or getattr(att, "res_id", 0) != rec.form_id.id:
                att.write({
                    "res_model": rec.form_id._name,
                    "res_id": rec.form_id.id,
                })

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # After create: propagate filename/meta and link ir.attachment to the consent
        for rec in records:
            rec._link_attachment_to_form()
            rec._compute_file_meta()
            # Auto-policy: if confidentiality is 'patient', auto-enable show_on_portal
            if rec.confidentiality == "patient" and not rec.show_on_portal:
                rec.write({"show_on_portal": True})
        return records

    def write(self, vals):
        # Guard writes when parent is signed/archived (allow benign fields)
        benign_fields = {
            "activity_exception_decoration", "message_follower_ids", "message_ids",
            "message_main_attachment_id", "activity_ids", "activity_state",
            "activity_user_id", "activity_type_id", "activity_date_deadline",
            "note", "sequence", "show_on_portal", "confidentiality",
        }
        if any(rec.form_id.state in ("signed", "archived") for rec in self):
            forbidden = set(vals.keys()) - benign_fields
            if forbidden:
                raise AccessError(_("You cannot modify attachments of a signed or archived consent."))
        res = super().write(vals)
        # Refresh metadata & ensure ir.attachment link if attachment_id updated
        if "attachment_id" in vals:
            for rec in self:
                rec._link_attachment_to_form()
        if {"attachment_id"} & set(vals.keys()):
            self._compute_file_meta()
        return res

    def unlink(self):
        self._ensure_deletable()
        return super().unlink()

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_open_attachment_record(self):
        """Open the underlying ir.attachment in a form view."""
        self.ensure_one()
        if not self.attachment_id:
            raise UserError(_("No Odoo attachment is linked to this record."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Attachment"),
            "res_model": "ir.attachment",
            "view_mode": "form",
            "res_id": self.attachment_id.id,
            "target": "current",
        }

    def action_open_in_portal(self):
        """Open the consent portal page anchored to this attachment."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.access_url,
            "target": "new",
        }

    def action_mark_portal_visible(self):
        self.write({"show_on_portal": True, "confidentiality": "patient"})

    def action_mark_portal_hidden(self):
        self.write({"show_on_portal": False})

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("attachment_id")
    def _onchange_attachment_id(self):
        """Update computed meta early in the UI and auto-fill name if empty."""
        if self.attachment_id:
            att = self.attachment_id.sudo()
            self.file_name = att.name
            self.mimetype = att.mimetype
            self.file_size = att.file_size if hasattr(att, "file_size") else False
            self.checksum = att.checksum if hasattr(att, "checksum") else False
            if not self.name and att.name:
                self.name = att.name

    # -------------------------------------------------------------------------
    # DISPLAY
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            label = rec.name or _("Attachment")
            if rec.category:
                label = f"[{dict(self._fields['category'].selection).get(rec.category)}] {label}"
            res.append((rec.id, label))
        return res

# -*- coding: utf-8 -*-
# File: clinic_consent_legal/models/consent_form_template.py
#
# Consent Template model for ClinicOne (Odoo 18 CE).
# Naming convention unified to `clinic.*`.
#
# Key capabilities:
# - Rich HTML/Text content with risks & alternatives
# - Template lifecycle: draft -> published -> retired
# - Optional auto version bump on content change
# - Company-scoped (global or per company)
# - Soft-coupled integrations to other ClinicOne modules
# - Safe duplication into a new version
# - Quick action to create Consent Form from a template
#
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError
from odoo.tools import format_datetime
import hashlib


class ConsentFormTemplate(models.Model):
    _name = "clinic.consent.template"
    _description = "Consent & Legal Form Template"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "state, title, id"

    # -------------------------------------------------------------------------
    # CORE / IDENTITY
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Template Number",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self._default_name(),
        help="Unique template identifier generated from an internal sequence."
    )

    title = fields.Char(
        string="Title",
        required=True,
        tracking=True,
        help="Short title of the consent template (e.g., 'Laser Treatment Consent')."
    )

    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
        help="Human-readable display name: Template Number + Title."
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True
    )

    active = fields.Boolean(
        string="Active",
        default=True,
        help="If unchecked, the template will be hidden without being deleted."
    )

    # -------------------------------------------------------------------------
    # VERSIONING & LIFECYCLE
    # -------------------------------------------------------------------------
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("published", "Published"),
            ("retired", "Retired"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
        help="Lifecycle state of the template."
    )

    consent_version = fields.Char(
        string="Version",
        default="v1.0",
        tracking=True,
        help="Human-readable version label (e.g., 'v1.0', 'v1.1')."
    )

    version_auto_bump = fields.Boolean(
        string="Auto-bump on Content Change",
        default=True,
        help="If enabled, the template version is automatically bumped when "
             "key content fields change."
    )

    version_major = fields.Integer(
        string="Major",
        default=1,
        help="Major version number."
    )
    version_minor = fields.Integer(
        string="Minor",
        default=0,
        help="Minor version number."
    )

    effective_date = fields.Date(
        string="Effective Date",
        help="Date from which this template is intended to be used."
    )

    supersedes_id = fields.Many2one(
        "clinic.consent.template",
        string="Supersedes",
        ondelete="set null",
        help="Previous template superseded by this one."
    )
    superseded_by_id = fields.Many2one(
        "clinic.consent.template",
        string="Superseded By",
        ondelete="set null",
        help="Next template that supersedes this one."
    )

    # -------------------------------------------------------------------------
    # APPLICABILITY (Soft-coupled to treatment)
    # -------------------------------------------------------------------------
    applicability = fields.Selection(
        selection=[
            ("generic", "Generic / All Procedures"),
            ("treatment", "Specific Treatment"),
        ],
        string="Applicability",
        default="generic",
        help="Whether this template is generic or linked to a specific treatment."
    )

    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        ondelete="set null",
        help="If Applicability = 'Specific Treatment', you can set its treatment here."
    )

    # -------------------------------------------------------------------------
    # CONTENT
    # -------------------------------------------------------------------------
    content_html = fields.Html(
        string="Consent Content (HTML)",
        sanitize=True,
        help="Full consent content in rich HTML."
    )

    content_text = fields.Text(
        string="Consent Content (Text)",
        help="Plain text fallback for the consent content."
    )

    risks_and_complications = fields.Html(
        string="Risks & Complications",
        help="Documented risks and complications associated with the procedure."
    )

    alternatives = fields.Html(
        string="Alternatives",
        help="Possible alternatives to the proposed procedure."
    )

    required_before_procedure = fields.Boolean(
        string="Required Before Procedure",
        default=True,
        help="If checked, the procedure cannot start unless the consent is signed."
    )

    validity_days = fields.Integer(
        string="Default Validity (days)",
        default=365,
        help="Default validity in days for consents derived from this template."
    )

    content_checksum = fields.Char(
        string="Content Checksum",
        readonly=True,
        help="SHA256 checksum of key content fields to support auditing/versioning."
    )

    # -------------------------------------------------------------------------
    # USAGE & REFERENCES
    # -------------------------------------------------------------------------
    usage_count = fields.Integer(
        string="Usage Count",
        compute="_compute_usage_count",
        help="Number of consents created based on this template."
    )

    last_used_on = fields.Datetime(
        string="Last Used On",
        readonly=True,
        help="Timestamp when this template was last used to create a consent."
    )

    default_mail_template_id = fields.Many2one(
        "mail.template",
        string="Reminder Mail Template",
        ondelete="set null",
        help="Default mail template used when sending consent reminders."
    )

    notes = fields.Text(
        string="Internal Notes",
        help="Internal notes for template authors; not included in the legal document."
    )

    # -------------------------------------------------------------------------
    # DEFAULTS
    # -------------------------------------------------------------------------
    @api.model
    def _default_name(self):
        # Sequence code should exist in data/consent_sequence.xml (or own template sequence)
        return self.env["ir.sequence"].next_by_code("clinic.consent.template") or _("New Template")

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("name", "title")
    def _compute_display_name(self):
        for rec in self:
            if rec.title:
                rec.display_name = f"{rec.name} - {rec.title}"
            else:
                rec.display_name = rec.name or _("Consent Template")

    @api.depends()
    def _compute_usage_count(self):
        Consent = self.env["clinic.consent.form"]
        grouped = Consent.read_group(
            domain=[("template_id", "in", self.ids)],
            fields=["template_id"],
            groupby=["template_id"],
        )
        mapped = {g["template_id"][0]: g["template_id_count"] for g in grouped}
        for rec in self:
            rec.usage_count = mapped.get(rec.id, 0)

    # -------------------------------------------------------------------------
    # CONSTRAINTS & SANITY CHECKS
    # -------------------------------------------------------------------------
    _name_company_uniq = models.Constraint(
        "unique(name, company_id)",
        "Template Number must be unique per company.",
    )

    @api.constrains("title", "content_html", "content_text")
    def _check_minimum_content(self):
        for rec in self:
            if not rec.title:
                raise ValidationError(_("Title is required."))
            if not (rec.content_html or rec.content_text):
                raise ValidationError(_("Template content is required (HTML or Text)."))

    @api.constrains("applicability", "treatment_id")
    def _check_applicability(self):
        for rec in self:
            if rec.applicability == "treatment" and not rec.treatment_id:
                raise ValidationError(_("Please select a Treatment when Applicability is 'Specific Treatment'."))

    @api.constrains("validity_days")
    def _check_validity_days(self):
        for rec in self:
            if rec.validity_days is not None and rec.validity_days < 0:
                raise ValidationError(_("Validity days cannot be negative."))

    # -------------------------------------------------------------------------
    # OVERRIDES
    # -------------------------------------------------------------------------
    def write(self, vals):
        """
        Enforce versioning constraints and optionally auto-bump version on content changes.
        Protect published templates already used by signed consents from being modified.
        """
        # Identify key content fields
        content_fields = {
            "content_html",
            "content_text",
            "risks_and_complications",
            "alternatives",
            "required_before_procedure",
            "validity_days",
            "title",
        }

        # Decide if content will change for any record in self
        content_will_change = any(f in vals for f in content_fields)

        # For published templates used at least once, disallow in-place content edits
        if content_will_change:
            # Allow explicit override via context flag
            force_edit = self.env.context.get("force_edit_published")
            for rec in self:
                if rec.state == "published" and rec.usage_count > 0 and not force_edit:
                    raise AccessError(_(
                        "Cannot modify content of a published template already in use.\n"
                        "Please duplicate it as a new version instead (Action: 'Duplicate as New Version')."
                    ))

        # Perform normal write first
        result = super().write(vals)

        # Recompute checksum and handle auto version bump if needed
        for rec in self:
            if content_will_change or "version_major" in vals or "version_minor" in vals:
                rec._update_content_checksum()

            if rec.version_auto_bump and content_will_change:
                # Bump minor version by default on content change
                rec._bump_minor_version(persist=True)

                # If template is 'published', keep it published but reflect new version label
                # (or optionally move back to draft; we keep published for continuity)
                # No action needed on 'state' here unless desired.

        return result

    def copy(self, default=None):
        """Make a safe copy with auto-incremented version and '(Copy)' suffix."""
        default = dict(default or {})
        default.setdefault("title", f"{self.title} (Copy)")
        # Start new copy with minor reset and +1 major by default
        default.setdefault("version_major", (self.version_major or 1) + 1)
        default.setdefault("version_minor", 0)
        default.setdefault("consent_version", f"v{default['version_major']}.{default['version_minor']}")
        default.setdefault("state", "draft")
        default.setdefault("supersedes_id", self.id)
        default.setdefault("superseded_by_id", False)
        rec = super().copy(default)
        # Link back the chain
        self.sudo().write({"superseded_by_id": rec.id})
        # Recompute checksum on the new record
        rec._update_content_checksum()
        return rec

    # -------------------------------------------------------------------------
    # INTERNALS: VERSIONING & CHECKSUM
    # -------------------------------------------------------------------------
    def _bump_minor_version(self, persist=False):
        for rec in self:
            mj = rec.version_major or 1
            mn = (rec.version_minor or 0) + 1
            if persist:
                rec.write({
                    "version_minor": mn,
                    "consent_version": f"v{mj}.{mn}",
                })
            else:
                rec.version_minor = mn
                rec.consent_version = f"v{mj}.{mn}"

    def _update_content_checksum(self):
        for rec in self:
            items = [
                ("company_id", rec.company_id.id if rec.company_id else 0),
                ("title", rec.title or ""),
                ("content_html", rec.content_html or ""),
                ("content_text", rec.content_text or ""),
                ("risks", rec.risks_and_complications or ""),
                ("alternatives", rec.alternatives or ""),
                ("required_before_procedure", str(bool(rec.required_before_procedure))),
                ("validity_days", int(rec.validity_days or 0)),
                ("version", rec.consent_version or ""),
                ("applicability", rec.applicability or ""),
                ("treatment_id", rec.treatment_id.id if rec.treatment_id else 0),
            ]
            payload = "|".join([f"{k}={v}" for k, v in items])
            checksum = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if rec.content_checksum != checksum:
                rec.write({"content_checksum": checksum})

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_publish(self):
        for rec in self:
            if rec.state == "retired":
                raise UserError(_("Cannot publish a retired template. Duplicate it instead."))
            # Ensure minimum content before publish
            if not rec.title or not (rec.content_html or rec.content_text):
                raise UserError(_("Please complete the Title and Content before publishing the template."))
            rec._update_content_checksum()
            rec.write({"state": "published"})

    def action_retire(self):
        for rec in self:
            # Retiring is always allowed; the template remains available historically
            rec.write({"state": "retired"})

    def action_duplicate_new_version(self):
        """User-facing action to duplicate into the next major version in Draft."""
        new = self.copy()
        return {
            "type": "ir.actions.act_window",
            "name": _("New Template Version"),
            "res_model": self._name,
            "view_mode": "form",
            "res_id": new.id,
            "target": "current",
        }

    def action_open_related_consents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Consents Based on this Template"),
            "res_model": "clinic.consent.form",
            "view_mode": "list,form,kanban,calendar,pivot,graph",
            "domain": [("template_id", "=", self.id)],
            "context": {"search_default_group_by_state": 1},
        }

    def action_create_consent_from_template(
        self,
        patient_id=False,
        treatment_id=False,
        doctor_id=False,
        booking_id=False,
        # encounter_id=False,
        room_session_id=False,
        source="in_clinic",
        title=False,
    ):
        """
        Create a new Consent Form record from this template and return the form view action.

        Parameters are optional; pass IDs of existing records when available.
        """
        Consent = self.env["clinic.consent.form"]
        self.ensure_one()

        if self.state != "published":
            raise UserError(_("Only Published templates can be used to create consents."))

        if not patient_id:
            raise UserError(_("Please provide a Patient to create a consent."))

        vals = self._prepare_consent_vals_from_template(
            patient_id=patient_id,
            treatment_id=treatment_id or (self.treatment_id.id if self.applicability == "treatment" else False),
            doctor_id=doctor_id,
            booking_id=booking_id,
            # encounter_id=encounter_id,
            room_session_id=room_session_id,
            source=source,
            title=title or self.title,
        )
        rec = Consent.create(vals)
        self.write({"last_used_on": fields.Datetime.now()})
        return {
            "type": "ir.actions.act_window",
            "name": _("Consent"),
            "res_model": "clinic.consent.form",
            "view_mode": "form",
            "res_id": rec.id,
            "target": "current",
        }

    def _prepare_consent_vals_from_template(
        self,
        patient_id,
        treatment_id=False,
        doctor_id=False,
        booking_id=False,
        # encounter_id=False,
        room_session_id=False,
        source="in_clinic",
        title=False,
    ):
        """Build default values to create `clinic.consent.form` from this template."""
        self.ensure_one()
        vals = {
            "company_id": self.company_id.id if self.company_id else self.env.company.id,
            "patient_id": patient_id,
            "doctor_id": doctor_id or False,
            "treatment_id": treatment_id or False,
            "booking_id": booking_id or False,
            # "encounter_id": encounter_id or False,
            "room_session_id": room_session_id or False,

            "template_id": self.id,
            "title": title or self.title or _("Consent"),

            "content_html": self.content_html,
            "content_text": self.content_text,
            "risks_and_complications": self.risks_and_complications,
            "alternatives": self.alternatives,

            "required_before_procedure": self.required_before_procedure,
            "validity_days": self.validity_days,
            "consent_version": self.consent_version,

            "source": source or "in_clinic",
            "state": "draft",
        }
        return vals

    # -------------------------------------------------------------------------
    # UI HELPERS
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            name = f"[{rec.consent_version}] {rec.title}" if rec.consent_version and rec.title else (rec.title or rec.name)
            res.append((rec.id, name))
        return res

    # -------------------------------------------------------------------------
    # HOOKS
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            # Ensure checksum present after create
            rec._update_content_checksum()
        return records

# -*- coding: utf-8 -*-
# File: clinic_consent_legal/models/consent_form.py
#
# Primary domain model for Consent & Legal Forms in ClinicOne (Odoo 18 CE).
# Naming convention unified to `clinic.*`.
#
# Integration notes:
# - Patient: res.partner (is_company = False) from contacts/clinic_patient
# - Doctor: clinic.doctor (assumed to expose partner_id) from clinic_doctor
# - Treatment: clinic.treatment from clinic_treatment
# - Booking/Appointment: booking.booking from clinic_booking
# - Clinical Encounter: clinic.encounter from clinic_encounter
# - Room Session: clinic.room.session from clinic_room_device or clinic_queue_room
# - Billing/Invoice: account.move (out_invoice / out_refund)
#
# Dependencies expected in __manifest__.py:
#   base, mail, contacts, hr, account, product, portal, clinic_base,
#   clinic_patient, clinic_doctor, clinic_booking, clinic_treatment, clinic_billing, ...
#
from datetime import timedelta
import hashlib

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError
from odoo.tools import format_datetime


class ConsentForm(models.Model):
    _name = "clinic.consent.form"
    _description = "Consent & Legal Form"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _order = "create_date desc, id desc"
    _rec_name = "name"

    # -------------------------------------------------------------------------
    # CORE / IDENTITY
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Consent Number",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self._default_name(),
        help="Unique consent identifier generated from an internal sequence."
    )

    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
        help="Human-readable display name: Consent Number + Patient."
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True
    )

    active = fields.Boolean(
        string="Active",
        default=True,
        help="If unchecked, the record will be hidden without being deleted."
    )

    # -------------------------------------------------------------------------
    # LINKS TO OTHER MODULES (Soft-coupled)
    # -------------------------------------------------------------------------
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        required=True,
        ondelete="restrict",
        domain="[('is_company', '=', False)]",
        tracking=True,
        index=True,
        help="The patient who is giving consent."
    )

    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        ondelete="set null",
        tracking=True,
        index=True,
        help="The doctor responsible for the procedure (from Clinic Doctor module)."
    )

    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment / Procedure",
        ondelete="set null",
        tracking=True,
        index=True,
        help="The treatment/procedure for which this consent is required."
    )

    # Optional direct links (keep optional to avoid hard coupling at install)
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking / Appointment",
        ondelete="set null",
        help="Related booking/appointment record when available."
    )

    # encounter_id = fields.Many2one(
    #     "clinic.encounter",
    #     string="Clinical Encounter",
    #     ondelete="set null",
    #     help="Related clinical encounter record when available."
    # )

    room_session_id = fields.Many2one(
        "clinic.room.session",
        string="Room Session",
        ondelete="set null",
        help="Related room session record when available."
    )

    invoice_id = fields.Many2one(
        "account.move",
        string="Related Invoice",
        domain="[('move_type', 'in', ['out_invoice', 'out_refund'])]",
        ondelete="set null",
        help="Optional link to the invoice related to this consent."
    )

    # Generic reference to other records (Appointment, Encounter, etc.)
    target_ref = fields.Reference(
        selection=lambda self: self._referenceable_models(),
        string="Related Record",
        help="Generic link to a related record (e.g., appointment, encounter, "
             "treatment session) within ClinicOne."
    )

    # -------------------------------------------------------------------------
    # TEMPLATE / CONTENT
    # -------------------------------------------------------------------------
    template_id = fields.Many2one(
        "clinic.consent.template",
        string="Template",
        ondelete="set null",
        help="Template used to pre-fill the legal content and defaults."
    )

    title = fields.Char(
        string="Title",
        required=True,
        tracking=True,
        help="Short title of the consent (e.g., 'Laser Treatment Consent')."
    )

    content_html = fields.Html(
        string="Consent Content (HTML)",
        sanitize=True,
        help="Full consent content in rich HTML."
    )

    content_text = fields.Text(
        string="Consent Content (Text)",
        help="Plain text fallback for the consent content."
    )

    risks_and_complications = fields.Html(
        string="Risks & Complications",
        help="Documented risks and complications associated with the procedure."
    )

    alternatives = fields.Html(
        string="Alternatives",
        help="Possible alternatives to the proposed procedure."
    )

    required_before_procedure = fields.Boolean(
        string="Required Before Procedure",
        default=True,
        help="If checked, the procedure cannot start unless this consent is signed."
    )

    validity_days = fields.Integer(
        string="Validity (days)",
        default=365,
        help="Number of days after signature during which this consent remains valid."
    )

    consent_version = fields.Char(
        string="Consent Version",
        help="Version marker of the consent content (e.g., derived from template)."
    )

    # -------------------------------------------------------------------------
    # SIGNING & E-SIGNATURE
    # -------------------------------------------------------------------------
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("to_sign", "Waiting for Signature"),
            ("signed", "Signed"),
            ("cancelled", "Cancelled"),
            ("archived", "Archived"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
        help="Lifecycle state of the consent."
    )

    signer_name = fields.Char(
        string="Signer Full Name",
        help="Full name of the signer as it should appear on the legal document."
    )

    signer_relationship = fields.Selection(
        selection=[
            ("self", "Self (Patient)"),
            ("guardian_parent", "Guardian/Parent"),
            ("guardian_legal", "Legal Guardian/Representative"),
            ("other", "Other Authorized Person"),
        ],
        string="Signer Relationship",
        default="self",
        help="Relationship of the signer to the patient."
    )

    guardian_partner_id = fields.Many2one(
        "res.partner",
        string="Signer (Partner)",
        ondelete="set null",
        help="If the signer is not the patient (e.g., parent/guardian), "
             "link to the partner here."
    )

    signature_binary = fields.Binary(
        string="Signature",
        attachment=True,
        help="Captured e-signature image (PNG)."
    )

    signature_datetime = fields.Datetime(
        string="Signed On",
        help="Timestamp when the consent was signed."
    )

    signature_ip = fields.Char(
        string="Signature IP Address",
        help="Public IP address captured at the moment of signature (if available)."
    )

    signature_user_agent = fields.Char(
        string="Signature User-Agent",
        help="Client user-agent string captured at the moment of signature (if available)."
    )

    integrity_hash = fields.Char(
        string="Content Integrity Hash",
        readonly=True,
        help="SHA256 hash to record the integrity of key fields at signature time."
    )

    expiry_date = fields.Date(
        string="Expiry Date",
        compute="_compute_expiry_date",
        store=True,
        help="Date when this consent expires based on validity settings."
    )

    is_expired = fields.Boolean(
        string="Expired",
        compute="_compute_is_expired",
        store=False,
        help="Indicates whether the consent has already expired."
    )

    # -------------------------------------------------------------------------
    # PORTAL / ACCESS
    # -------------------------------------------------------------------------
    access_url = fields.Char(
        string="Portal URL",
        compute="_compute_access_url",
        help="Public portal URL for the patient to review/sign this consent."
    )

    # access_token is provided by portal.mixin (Char)
    # message_follower_ids provided by mail.thread

    # -------------------------------------------------------------------------
    # OPERATIONS / REMINDERS / UTILITIES
    # -------------------------------------------------------------------------
    source = fields.Selection(
        selection=[
            ("in_clinic", "In-Clinic"),
            ("portal", "Portal"),
            ("ecommerce", "eCommerce Pre-Booking"),
            ("import", "Imported")
        ],
        string="Origin Source",
        default="in_clinic",
        help="Where this consent was initiated."
    )

    next_reminder_date = fields.Date(
        string="Next Reminder On",
        help="Next planned reminder date to request signature."
    )

    attachments_count = fields.Integer(
        string="Attachments",
        compute="_compute_attachments_count",
        help="Number of attachments linked to this consent."
    )

    note = fields.Text(
        string="Internal Notes",
        help="Internal notes for staff; not included in the legal document."
    )

    # -------------------------------------------------------------------------
    # DEFAULTS
    # -------------------------------------------------------------------------
    @api.model
    def _default_name(self):
        # Sequence code should exist in data/consent_sequence.xml
        return self.env["ir.sequence"].next_by_code("clinic.consent.form") or _("New")

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("name", "patient_id")
    def _compute_display_name(self):
        for rec in self:
            if rec.patient_id:
                rec.display_name = f"{rec.name} - {rec.patient_id.display_name}"
            else:
                rec.display_name = rec.name or _("Consent")

    @api.depends("signature_datetime", "validity_days")
    def _compute_expiry_date(self):
        for rec in self:
            if rec.signature_datetime and rec.validity_days and rec.validity_days > 0:
                rec.expiry_date = (rec.signature_datetime + timedelta(days=rec.validity_days)).date()
            else:
                rec.expiry_date = False

    def _compute_is_expired(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_expired = bool(rec.expiry_date and rec.expiry_date < today)

    def _compute_access_url(self):
        for rec in self:
            # Keep stable, portable portal URL
            rec.access_url = f"/my/consents/{rec.id}"

    @api.depends()
    def _compute_attachments_count(self):
        Attachment = self.env["ir.attachment"]
        for rec in self:
            rec.attachments_count = Attachment.search_count([
                ("res_model", "=", rec._name),
                ("res_id", "=", rec.id),
            ])

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange("template_id")
    def _onchange_template_id(self):
        """When selecting a template, pull in content, risks, alternatives, version, validity, and title if empty."""
        if self.template_id:
            tpl = self.template_id.sudo()
            if not self.title:
                self.title = tpl.title or _("Consent")
            self.content_html = tpl.content_html
            self.content_text = tpl.content_text
            self.risks_and_complications = tpl.risks_and_complications
            self.alternatives = tpl.alternatives
            if tpl.validity_days:
                self.validity_days = tpl.validity_days
            if tpl.consent_version:
                self.consent_version = tpl.consent_version
            if tpl.required_before_procedure is not None:
                self.required_before_procedure = tpl.required_before_procedure

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    _name_company_uniq = models.Constraint(
        "unique(name, company_id)",
        "Consent Number must be unique per company.",
    )

    @api.constrains("patient_id", "title", "content_html", "content_text")
    def _check_minimum_content(self):
        for rec in self:
            if not rec.title:
                raise ValidationError(_("Title is required."))
            if not rec.patient_id:
                raise ValidationError(_("Patient is required."))
            if not (rec.content_html or rec.content_text):
                raise ValidationError(_("Consent content is required (HTML or Text)."))

    # If required_before_procedure = True, ensure treatment/booking known before signing
    @api.constrains("required_before_procedure", "state")
    def _check_required_context(self):
        for rec in self:
            if rec.required_before_procedure and rec.state in ("to_sign", "signed"):
                # Prefer at least treatment or booking context for audit clarity
                if not (rec.treatment_id or rec.booking_id):
                    raise ValidationError(
                        _("When consent is required before a procedure, "
                          "either Treatment or Booking should be specified.")
                    )

    # -------------------------------------------------------------------------
    # ACCESS GUARDS
    # -------------------------------------------------------------------------
    def _ensure_editable(self):
        for rec in self:
            if rec.state in ("signed", "archived"):
                raise AccessError(_("You cannot modify a signed or archived consent."))

    def write(self, vals):
        # Disallow editing after signed/archived, except certain benign fields
        protected_states = ("signed", "archived")
        benign_fields = {
            "activity_exception_decoration", "message_follower_ids", "message_ids",
            "message_main_attachment_id", "activity_ids", "activity_state",
            "activity_user_id", "activity_type_id", "activity_date_deadline",
            "next_reminder_date", "note", "active",
        }
        if any(rec.state in protected_states for rec in self):
            forbidden = set(vals.keys()) - benign_fields
            if forbidden:
                raise AccessError(_("You cannot modify a signed or archived consent."))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.state not in ("draft", "cancelled"):
                raise AccessError(_("You can only delete consents in Draft or Cancelled state."))
        return super().unlink()

    # -------------------------------------------------------------------------
    # REFERENCEABLE MODELS (for fields.Reference)
    # -------------------------------------------------------------------------
    @api.model
    def _referenceable_models(self):
        """
        Return a selection of (model, label) that are safe to reference across ClinicOne.
        These models may or may not be installed; that's acceptable for a reference field.
        """
        return [
            ("clinic.treatment", "Treatment"),
            ("clinic.treatment.session", "Treatment Session"),
            ("clinic.encounter", "Clinical Encounter"),
            ("booking.booking", "Booking/Appointment"),
            ("clinic.room.session", "Room Session"),
            ("account.move", "Invoice"),
            ("res.partner", "Partner"),
        ]

    # -------------------------------------------------------------------------
    # STATE TRANSITIONS & BUSINESS METHODS
    # -------------------------------------------------------------------------
    def action_set_to_sign(self):
        for rec in self:
            if rec.state not in ("draft", "cancelled"):
                raise UserError(_("Only Draft/Cancelled consents can be sent for signature."))
            if not rec.patient_id:
                raise UserError(_("Please set the Patient before requesting a signature."))
            if not (rec.content_html or rec.content_text):
                raise UserError(_("Please fill the consent content before requesting a signature."))
            rec.state = "to_sign"
            rec._subscribe_parties()
            # Schedule an activity for the responsible user (optional)
            rec.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=self.env.user.id,
                note=_("Request the patient to review and sign the consent."),
            )

    def action_sign(
        self,
        signer_name=False,
        signature_binary=False,
        signer_relationship=False,
        ip_address=False,
        user_agent=False,
        signed_dt=False,
    ):
        """
        Perform signature. Typically called from a controller or wizard.

        :param signer_name: Full name of signer (string)
        :param signature_binary: Binary PNG of signature
        :param signer_relationship: 'self', 'guardian_parent', 'guardian_legal', 'other'
        :param ip_address: IP address string
        :param user_agent: HTTP user-agent string
        :param signed_dt: datetime; if False, use fields.Datetime.now()
        """
        for rec in self:
            if rec.state != "to_sign":
                raise UserError(_("Only consents in 'Waiting for Signature' can be signed."))
            if rec.required_before_procedure and not rec.patient_id:
                raise UserError(_("Patient is required before signing."))

            _signer_name = signer_name or rec.signer_name
            if not _signer_name:
                raise UserError(_("Signer Full Name is required."))

            signed_when = signed_dt or fields.Datetime.now()

            # Persist signature
            rec.write({
                "signer_name": _signer_name,
                "signature_binary": signature_binary or rec.signature_binary,
                "signer_relationship": signer_relationship or rec.signer_relationship,
                "signature_ip": ip_address or rec.signature_ip,
                "signature_user_agent": user_agent or rec.signature_user_agent,
                "signature_datetime": signed_when,
                "state": "signed",
                "integrity_hash": rec._compute_integrity_hash(
                    signer_name=_signer_name,
                    signed_dt=signed_when,
                ),
            })

            # Optional: close related activities
            rec.activity_feedback(["mail.mail_activity_data_todo"])

    def action_cancel(self):
        self._ensure_editable()
        self.write({"state": "cancelled"})

    def action_reset_to_draft(self):
        # Allow resetting cancelled only
        for rec in self:
            if rec.state != "cancelled":
                raise UserError(_("Only Cancelled consents can be reset to Draft."))
        self.write({"state": "draft"})

    def action_archive(self):
        for rec in self:
            if rec.state != "signed":
                raise UserError(_("Only Signed consents can be archived."))
        self.write({"state": "archived"})

    def action_send_reminder(self, days=3):
        """Set next reminder date and schedule an activity."""
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state != "to_sign":
                raise UserError(_("Only consents waiting for signature can be reminded."))
            rec.next_reminder_date = today + timedelta(days=days or 3)
            rec.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=self.env.user.id,
                note=_("Follow up with the patient to sign the consent."),
                date_deadline=rec.next_reminder_date,
            )

    # -------------------------------------------------------------------------
    # UTILITIES
    # -------------------------------------------------------------------------
    def _subscribe_parties(self):
        """Subscribe patient and doctor partners to chatter notifications."""
        for rec in self:
            partner_ids = []
            if rec.patient_id:
                partner_ids.append(rec.patient_id.id)
            # If doctor model has a partner_id field, subscribe it when available.
            if rec.doctor_id and hasattr(rec.doctor_id, "partner_id") and rec.doctor_id.partner_id:
                partner_ids.append(rec.doctor_id.partner_id.id)
            if partner_ids:
                rec.message_subscribe(partner_ids=partner_ids)

    def _compute_integrity_hash(self, signer_name, signed_dt):
        """Compute a SHA256 hash over key legal fields at signature time."""
        items = [
            ("company_id", self.company_id.id if self.company_id else 0),
            ("patient_id", self.patient_id.id if self.patient_id else 0),
            ("doctor_id", self.doctor_id.id if self.doctor_id else 0),
            ("treatment_id", self.treatment_id.id if self.treatment_id else 0),
            ("booking_id", self.booking_id.id if self.booking_id else 0),
            # ("encounter_id", self.encounter_id.id if self.encounter_id else 0),
            ("room_session_id", self.room_session_id.id if self.room_session_id else 0),
            ("title", self.title or ""),
            ("content_html", self.content_html or ""),
            ("content_text", self.content_text or ""),
            ("risks", self.risks_and_complications or ""),
            ("alternatives", self.alternatives or ""),
            ("required_before_procedure", str(bool(self.required_before_procedure))),
            ("validity_days", int(self.validity_days or 0)),
            ("consent_version", self.consent_version or ""),
            ("signer_name", signer_name or ""),
            ("signer_relationship", self.signer_relationship or ""),
            ("signed_dt", format_datetime(self.env, signed_dt) if signed_dt else ""),
        ]
        payload = "|".join([f"{k}={v}" for k, v in items])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # -------------------------------------------------------------------------
    # PORTAL MIXIN
    # -------------------------------------------------------------------------
    def _get_report_base_filename(self):
        self.ensure_one()
        base = self.name or "Consent"
        suffix = f" - {self.patient_id.display_name}" if self.patient_id else ""
        return f"{base}{suffix}"

    def _get_access_action(self, access_uid=None):
        """Override to route portal action to our custom URL."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "target": "self",
            "url": self.access_url,
        }

    # -------------------------------------------------------------------------
    # HELPERS FOR VIEWS & UI
    # -------------------------------------------------------------------------
    def action_view_attachments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Attachments"),
            "res_model": "ir.attachment",
            "view_mode": "kanban,tree,form",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "context": {"default_res_model": self._name, "default_res_id": self.id},
        }

    def action_preview_portal(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.access_url,
            "target": "new",
        }

# -*- coding: utf-8 -*-
# File: clinic_consent_legal/models/consent_signature.py
#
# Signature ledger for ClinicOne Consent & Legal Forms (Odoo 18 CE).
# Naming convention unified to `clinic.*`.
#
# Purpose:
#   - Persistent, append-only style log of signatures tied to a consent form
#   - Supports multiple roles (patient, guardian, doctor, witness, staff)
#   - Stores signature image, device info, IP, timestamp, content snapshot & checksum
#   - Allows revocation (with reason) and superseding when new versions are signed
#
# Integration notes:
#   - Primary link to `clinic.consent.form` (see consent_form.py)
#   - Soft-coupled to other modules via optional links (booking/encounter/room session)
#   - Portal anchoring points to parent consent URL with signature anchor
#
# Typical flow:
#   - Controllers/wizards call `clinic.consent.form.action_sign(...)`
#   - Additionally create a `clinic.consent.signature` entry via `create_from_consent(...)`
#
import hashlib
import json
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError
from odoo.tools import format_datetime


class ConsentSignature(models.Model):
    _name = "clinic.consent.signature"
    _description = "Consent Signature (Ledger)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "signed_on desc, id desc"

    # -------------------------------------------------------------------------
    # CORE / LINKS
    # -------------------------------------------------------------------------
    form_id = fields.Many2one(
        "clinic.consent.form",
        string="Consent Form",
        required=True,
        ondelete="cascade",
        index=True,
        help="The consent form this signature is associated with."
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="form_id.company_id",
        store=True,
        index=True,
        readonly=True
    )

    # Convenience relateds for filtering/reporting
    patient_id = fields.Many2one(
        "res.partner",
        string="Patient",
        related="form_id.patient_id",
        store=True,
        index=True,
        readonly=True
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor",
        related="form_id.doctor_id",
        store=True,
        index=True,
        readonly=True
    )
    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment",
        related="form_id.treatment_id",
        store=True,
        index=True,
        readonly=True
    )

    # Optional deep links (soft-coupled)
    booking_id = fields.Many2one(
        "booking.booking",
        string="Booking / Appointment",
        ondelete="set null",
        help="Optional: link to appointment present at signing time."
    )
    # encounter_id = fields.Many2one(
    #     "clinic.encounter",
    #     string="Clinical Encounter",
    #     ondelete="set null",
    #     help="Optional: link to clinical encounter present at signing time."
    # )
    room_session_id = fields.Many2one(
        "clinic.room.session",
        string="Room Session",
        ondelete="set null",
        help="Optional: link to room session present at signing time."
    )

    # -------------------------------------------------------------------------
    # SIGNER INFO
    # -------------------------------------------------------------------------
    role = fields.Selection(
        selection=[
            ("patient", "Patient"),
            ("guardian", "Guardian/Representative"),
            ("doctor", "Doctor"),
            ("witness", "Witness"),
            ("staff", "Staff"),
        ],
        string="Signature Role",
        required=True,
        default="patient",
        help="Role of the person who signed."
    )

    signer_name = fields.Char(
        string="Signer Full Name",
        required=True,
        help="Full name as it should appear on the legal document."
    )

    relationship = fields.Selection(
        selection=[
            ("self", "Self (Patient)"),
            ("guardian_parent", "Guardian/Parent"),
            ("guardian_legal", "Legal Guardian/Representative"),
            ("other", "Other Authorized Person"),
        ],
        string="Signer Relationship",
        default="self",
        help="Relationship of the signer to the patient (for non-patient signatures)."
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Signer (Partner)",
        ondelete="set null",
        help="If the signer exists in contacts, link here."
    )

    user_id = fields.Many2one(
        "res.users",
        string="Signed By (User)",
        ondelete="set null",
        help="If signed by a logged-in internal user (e.g., staff/doctor countersign)."
    )

    signature_image = fields.Binary(
        string="Signature Image",
        attachment=True,
        help="Captured e-signature image (PNG)."
    )

    signed_on = fields.Datetime(
        string="Signed On",
        required=True,
        default=lambda self: fields.Datetime.now(),
        index=True,
        help="Timestamp when the signature was recorded."
    )

    ip_address = fields.Char(
        string="IP Address",
        help="Public IP captured at the moment of signature (if available)."
    )
    user_agent = fields.Char(
        string="User-Agent",
        help="Client user-agent string captured at the moment of signature (if available)."
    )
    device_hint = fields.Char(
        string="Device Hint",
        help="Optional hint (e.g., 'iPad kiosk', 'Nurse station terminal', etc.)."
    )

    # -------------------------------------------------------------------------
    # STATE & AUDIT
    # -------------------------------------------------------------------------
    state = fields.Selection(
        selection=[
            ("signed", "Signed"),
            ("revoked", "Revoked"),
            ("superseded", "Superseded"),
        ],
        string="Status",
        default="signed",
        tracking=True,
        help="Signature status in the ledger."
    )

    revoke_reason = fields.Text(
        string="Revoke Reason",
        help="Reason for revocation, if any."
    )
    revoked_on = fields.Datetime(
        string="Revoked On",
        help="Timestamp when the signature was revoked."
    )

    content_version = fields.Char(
        string="Consent Version",
        help="Consent content version at the time of signing (copied from form)."
    )

    content_checksum = fields.Char(
        string="Content Integrity Hash",
        help="SHA256 hash of key legal fields at signing time."
    )

    content_snapshot = fields.Text(
        string="Content Snapshot (JSON)",
        help="JSON snapshot of key fields from consent form to support full audit."
    )

    access_url = fields.Char(
        string="Portal URL (Anchor)",
        compute="_compute_access_url",
        help="Public portal URL (anchor to this signature) for the parent consent."
    )

    is_latest_for_role = fields.Boolean(
        string="Is Latest For Role",
        compute="_compute_is_latest_for_role",
        help="True if this is the latest non-revoked signature for the given role on this form."
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    _signed_on_required = models.Constraint(
        "CHECK(signed_on IS NOT NULL)",
        "Signed On must be set.",
    )

    @api.constrains("signature_image", "state")
    def _check_signature_image_required(self):
        for rec in self:
            if rec.state == "signed" and not rec.signature_image:
                raise ValidationError(_("Signature Image is required for a signed record."))

    @api.constrains("form_id", "state")
    def _check_form_state(self):
        for rec in self:
            if rec.form_id and rec.state == "signed" and rec.form_id.state not in ("to_sign", "signed"):
                # Allow historical imports via context 'allow_historical_signature'
                if not rec.env.context.get("allow_historical_signature"):
                    raise ValidationError(_(
                        "The parent consent must be in 'Waiting for Signature' or 'Signed' "
                        "to accept a signature."
                    ))

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _compute_access_url(self):
        for rec in self:
            # Anchor to parent consent portal URL using signature anchor
            # Parent consent computes: /my/consents/<id>
            base = rec.form_id.access_url or f"/my/consents/{rec.form_id.id}"
            rec.access_url = f"{base}#sig-{rec.id}"

    def _compute_is_latest_for_role(self):
        for rec in self:
            # Latest = most recent (by signed_on, id tiebreak) that is not revoked
            latest = self.search([
                ("form_id", "=", rec.form_id.id),
                ("role", "=", rec.role),
                ("state", "!=", "revoked"),
            ], order="signed_on desc, id desc", limit=1)
            rec.is_latest_for_role = (latest.id == rec.id) if latest else False

    # -------------------------------------------------------------------------
    # HELPERS: SNAPSHOT & CHECKSUM
    # -------------------------------------------------------------------------
    def _build_snapshot_dict(self):
        """Return a minimal JSON-serializable snapshot of the form & context at signing time."""
        self.ensure_one()
        f = self.form_id.sudo()
        snapshot = {
            "company_id": f.company_id.id if f.company_id else False,
            "patient_id": f.patient_id.id if f.patient_id else False,
            "doctor_id": f.doctor_id.id if f.doctor_id else False,
            "treatment_id": f.treatment_id.id if f.treatment_id else False,
            "booking_id": f.booking_id.id if f.booking_id else False,
            # "encounter_id": f.encounter_id.id if f.encounter_id else False,
            "room_session_id": f.room_session_id.id if f.room_session_id else False,

            "title": f.title or "",
            "content_html": f.content_html or "",
            "content_text": f.content_text or "",
            "risks_and_complications": f.risks_and_complications or "",
            "alternatives": f.alternatives or "",

            "required_before_procedure": bool(f.required_before_procedure),
            "validity_days": int(f.validity_days or 0),
            "consent_version": f.consent_version or "",

            # light denorms for search/report
            "form_state": f.state or "",
            "form_name": f.name or "",
        }
        return snapshot

    @api.model
    def _compute_checksum_from_payload(self, payload_dict, signer_name, role, signed_dt):
        """Compute a SHA256 checksum of key content composed with signer identity."""
        items = [
            # content payload
            ("payload", json.dumps(payload_dict, sort_keys=True, ensure_ascii=False)),
            # signer info
            ("signer_name", signer_name or ""),
            ("role", role or ""),
            ("signed_dt", format_datetime(self.env, signed_dt) if signed_dt else ""),
        ]
        raw = "|".join([f"{k}={v}" for k, v in items])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    # -------------------------------------------------------------------------
    # FACTORY: CREATE FROM CONSENT
    # -------------------------------------------------------------------------
    @api.model
    def create_from_consent(
        self,
        form_id,
        role="patient",
        signer_name=None,
        signature_image=None,
        relationship="self",
        partner_id=False,
        user_id=False,
        ip_address=False,
        user_agent=False,
        device_hint=False,
        booking_id=False,
        # encounter_id=False,
        room_session_id=False,
        signed_on=False,
    ):
        """
        Create a signature ledger entry for a given consent form.
        Raises if basic requirements are not met.

        Typical usage:
            env['clinic.consent.signature'].create_from_consent(
                form_id=form.id,
                role='patient',
                signer_name='John Doe',
                signature_image=b64png,
                ip_address=request.httprequest.remote_addr,
                user_agent=request.httprequest.user_agent.string,
            )
        """
        Consent = self.env["clinic.consent.form"]
        form = Consent.browse(form_id).exists()
        if not form:
            raise UserError(_("Consent Form not found."))

        if form.state not in ("to_sign", "signed"):
            # Allow backfill with context flag
            if not self.env.context.get("allow_historical_signature"):
                raise UserError(_("The consent is not in a signable state."))

        if not signer_name:
            raise UserError(_("Signer Full Name is required."))

        when = signed_on or fields.Datetime.now()

        # Build content snapshot & checksum
        # We use a new transient record (not stored yet) to access helper cleanly
        dummy = self.new({"form_id": form.id})
        payload = dummy._build_snapshot_dict()
        checksum = self._compute_checksum_from_payload(
            payload_dict=payload,
            signer_name=signer_name,
            role=role,
            signed_dt=when,
        )

        vals = {
            "form_id": form.id,
            "role": role,
            "signer_name": signer_name,
            "relationship": relationship or "self",
            "partner_id": partner_id or False,
            "user_id": user_id or False,

            "signature_image": signature_image,
            "signed_on": when,

            "ip_address": ip_address or False,
            "user_agent": user_agent or False,
            "device_hint": device_hint or False,

            "booking_id": booking_id or form.booking_id.id or False,
            # "encounter_id": encounter_id or form.encounter_id.id or False,
            "room_session_id": room_session_id or form.room_session_id.id or False,

            "state": "signed",
            "content_version": form.consent_version or False,
            "content_checksum": checksum,
            "content_snapshot": json.dumps(payload, ensure_ascii=False),
        }
        rec = self.create(vals)

        # Post a chatter message on parent form for traceability
        form.message_post(
            body=_("Signature recorded (%s) by <b>%s</b>.") % (rec.role, rec.signer_name),
            subtype_xmlid="mail.mt_note",
        )
        return rec

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_revoke(self, reason=None):
        """Revoke signature with an optional reason."""
        for rec in self:
            if rec.state != "signed":
                raise UserError(_("Only 'Signed' signatures can be revoked."))
            rec.write({
                "state": "revoked",
                "revoke_reason": reason or _("Revoked"),
                "revoked_on": fields.Datetime.now(),
            })
            rec.form_id.message_post(
                body=_("Signature revoked (%s) by <b>%s</b>. Reason: %s") %
                     (rec.role, rec.signer_name, rec.revoke_reason or "-"),
                subtype_xmlid="mail.mt_note",
            )

    def action_mark_superseded(self):
        """Mark signature as superseded (e.g., when a newer version is signed)."""
        for rec in self:
            if rec.state != "signed":
                # Allow idempotent supersede on non-signed states (no-op)
                continue
            rec.write({"state": "superseded"})
            rec.form_id.message_post(
                body=_("Signature marked as superseded (%s) for <b>%s</b>.") %
                     (rec.role, rec.signer_name),
                subtype_xmlid="mail.mt_note",
            )

    def action_open_parent_consent(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Consent"),
            "res_model": "clinic.consent.form",
            "view_mode": "form",
            "res_id": self.form_id.id,
            "target": "current",
        }

    def action_open_in_portal(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.access_url,
            "target": "new",
        }

    # -------------------------------------------------------------------------
    # UI / DISPLAY
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            ts = format_datetime(self.env, rec.signed_on) if rec.signed_on else ""
            ver = f"[{rec.content_version}] " if rec.content_version else ""
            name = f"{ver}{rec.role.capitalize()} - {rec.signer_name} ({ts})"
            res.append((rec.id, name))
        return res

    # -------------------------------------------------------------------------
    # CREATE/WRITE OVERRIDES (light guards)
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Ensure each record has checksum & snapshot (if a direct create bypasses factory)
        for rec in records:
            if not rec.content_snapshot or not rec.content_checksum:
                payload = rec._build_snapshot_dict()
                checksum = rec._compute_checksum_from_payload(
                    payload_dict=payload,
                    signer_name=rec.signer_name,
                    role=rec.role,
                    signed_dt=rec.signed_on or fields.Datetime.now(),
                )
                rec.write({
                    "content_snapshot": json.dumps(payload, ensure_ascii=False),
                    "content_checksum": checksum,
                    "content_version": rec.form_id.consent_version or rec.content_version,
                })
        return records

    def write(self, vals):
        # Disallow mutating critical signer identity once signed, except for administrative corrections
        protected_when_signed = {"signer_name", "role", "signature_image", "signed_on"}
        if any(rec.state == "signed" for rec in self) and protected_when_signed & set(vals.keys()):
            # Allow via context flag when truly necessary
            if not self.env.context.get("allow_signature_identity_edit"):
                raise AccessError(_("Editing signer identity or signature content is not allowed."))
        return super().write(vals)

# -*- coding: utf-8 -*-
# File: clinic_consent_legal/models/res_partner_inherit.py
#
# Extends res.partner with Consent & Legal capabilities for ClinicOne (Odoo 18 CE).
# Naming convention unified to `clinic.*`.
#
# Key capabilities:
# - One2many relations to patient consents and guardian-consents
# - Portal deep link to patient's consents
# - Metrics: total/pending/signed counts, last consent references
# - Smart actions: open all/pending/signed consents, open portal, request a new consent,
#   bulk send reminders for pending consents
#
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    # -------------------------------------------------------------------------
    # RELATIONS
    # -------------------------------------------------------------------------
    consent_form_ids = fields.One2many(
        "clinic.consent.form",
        "patient_id",
        string="Consents (as Patient)",
        help="All consent records where this contact is the Patient."
    )

    consent_guardian_form_ids = fields.One2many(
        "clinic.consent.form",
        "guardian_partner_id",
        string="Consents (as Guardian/Representative)",
        help="All consent records where this contact signed as Guardian or Representative."
    )

    # -------------------------------------------------------------------------
    # METRICS
    # -------------------------------------------------------------------------
    consent_count = fields.Integer(
        string="Total Consents",
        compute="_compute_consent_metrics",
        help="Total number of consents related to this partner (as Patient)."
    )

    consent_pending_count = fields.Integer(
        string="Pending Consents",
        compute="_compute_consent_metrics",
        help="Number of consents waiting for signature (as Patient)."
    )

    consent_signed_count = fields.Integer(
        string="Signed Consents",
        compute="_compute_consent_metrics",
        help="Number of signed consents (as Patient)."
    )

    consent_guardian_count = fields.Integer(
        string="Guardian Consents",
        compute="_compute_consent_metrics",
        help="Number of consents where this partner is a Guardian/Representative."
    )

    last_consent_id = fields.Many2one(
        "clinic.consent.form",
        string="Last Consent",
        compute="_compute_consent_last",
        help="Most recently created consent for this partner (as Patient)."
    )

    last_consent_signed_on = fields.Datetime(
        string="Last Signed On",
        compute="_compute_consent_last",
        help="Signature time of the most recently signed consent (as Patient)."
    )

    # -------------------------------------------------------------------------
    # PORTAL / PREFERENCES
    # -------------------------------------------------------------------------
    consent_portal_url = fields.Char(
        string="Consents Portal URL",
        compute="_compute_consent_portal_url",
        help="Direct portal URL for this patient to review/sign their consents."
    )

    consent_portal_opt_out = fields.Boolean(
        string="Opt-out of Portal Consent",
        help="If enabled, this contact prefers not to use the portal for consent signing."
    )

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    def _company_domain(self):
        """Helper: domain restricting to the partner's company (if applicable)."""
        # In multi-company setups, limit by allowed companies of current env.
        companies = self.env.companies.ids
        return [("company_id", "in", companies)]

    def _compute_consent_metrics(self):
        Consent = self.env["clinic.consent.form"].sudo()
        for partner in self:
            if partner.is_company:
                # Typically consents are tied to individuals; still compute if used otherwise
                patient_domain = [("patient_id", "=", partner.id)]
            else:
                patient_domain = [("patient_id", "=", partner.id)]

            guardian_domain = [("guardian_partner_id", "=", partner.id)]

            # Apply multi-company filter
            patient_domain += self._company_domain()
            guardian_domain += self._company_domain()

            total = Consent.search_count(patient_domain)
            pending = Consent.search_count(patient_domain + [("state", "=", "to_sign")])
            signed = Consent.search_count(patient_domain + [("state", "=", "signed")])
            guardian_total = Consent.search_count(guardian_domain)

            partner.consent_count = total
            partner.consent_pending_count = pending
            partner.consent_signed_count = signed
            partner.consent_guardian_count = guardian_total

    def _compute_consent_last(self):
        Consent = self.env["clinic.consent.form"].sudo()
        for partner in self:
            domain = [("patient_id", "=", partner.id)] + self._company_domain()
            last = Consent.search(domain, order="create_date desc, id desc", limit=1)
            partner.last_consent_id = last.id or False

            last_signed = Consent.search(
                domain + [("state", "=", "signed")],
                order="signature_datetime desc, write_date desc, id desc",
                limit=1,
            )
            partner.last_consent_signed_on = last_signed.signature_datetime if last_signed else False

    def _compute_consent_portal_url(self):
        for partner in self:
            # Deep-link to a filtered consent list on the patient portal.
            # A portal controller can read partner_id querystring to filter.
            partner.consent_portal_url = f"/my/consents?partner_id={partner.id}"

    # -------------------------------------------------------------------------
    # ACTIONS (SMART BUTTONS)
    # These actions return ir.actions for UI; views are expected in this addon.
    # -------------------------------------------------------------------------
    def action_view_consents_as_patient(self):
        """Open consents where this partner is the Patient."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Consents (Patient)"),
            "res_model": "clinic.consent.form",
            "view_mode": "list,form,kanban,calendar,pivot,graph",
            "domain": [("patient_id", "=", self.id)] + self._company_domain(),
            "context": {"search_default_group_by_state": 1, "default_patient_id": self.id},
        }

    def action_view_consents_as_guardian(self):
        """Open consents where this partner is the Guardian/Representative."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Consents (Guardian/Representative)"),
            "res_model": "clinic.consent.form",
            "view_mode": "list,form,kanban,calendar,pivot,graph",
            "domain": [("guardian_partner_id", "=", self.id)] + self._company_domain(),
            "context": {"search_default_group_by_state": 1, "default_guardian_partner_id": self.id},
        }

    def action_view_all_related_consents(self):
        """Open both patient and guardian consents for this partner."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("All Related Consents"),
            "res_model": "clinic.consent.form",
            "view_mode": "list,form,kanban,calendar,pivot,graph",
            "domain": ["|",
                       ("patient_id", "=", self.id),
                       ("guardian_partner_id", "=", self.id)] + self._company_domain(),
            "context": {"search_default_group_by_state": 1, "default_patient_id": self.id},
        }

    def action_view_pending_consents(self):
        """Open pending consents (Waiting for Signature) for this partner."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Pending Consents"),
            "res_model": "clinic.consent.form",
            "view_mode": "list,form,kanban,calendar,pivot,graph",
            "domain": [("patient_id", "=", self.id), ("state", "=", "to_sign")] + self._company_domain(),
            "context": {"default_patient_id": self.id},
        }

    def action_view_signed_consents(self):
        """Open signed consents for this partner."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Signed Consents"),
            "res_model": "clinic.consent.form",
            "view_mode": "list,form,kanban,calendar,pivot,graph",
            "domain": [("patient_id", "=", self.id), ("state", "=", "signed")] + self._company_domain(),
            "context": {"default_patient_id": self.id},
        }

    def action_open_portal_consents(self):
        """Open patient consents in the portal (new tab)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.consent_portal_url,
            "target": "new",
        }

    def action_request_new_consent(self):
        """
        Open the Consent Template list (Published) to create a new Consent for this partner.
        The template form will use context to prefill patient and allow 'Create Consent' flow.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Consent Templates"),
            "res_model": "clinic.consent.template",
            "view_mode": "list,form",
            "domain": [("state", "=", "published")] + self._company_domain(),
            "context": {
                "default_applicability": "generic",
                "clinic_consent_create_context": {
                    "patient_id": self.id,
                    # Optionally prefill treatment/doctor if you open from those records
                },
            },
            "target": "current",
        }

    def action_send_consent_reminders(self, days=3):
        """
        Bulk-send reminders for pending consents for selected partners.
        Schedules activities on each pending consent.
        """
        Consent = self.env["clinic.consent.form"].sudo()
        total = 0
        for partner in self:
            domain = [
                ("patient_id", "=", partner.id),
                ("state", "=", "to_sign"),
            ] + partner._company_domain()
            pending = Consent.search(domain)
            for c in pending:
                c.action_send_reminder(days=days)
                total += 1
        if not total:
            return False
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Reminders Scheduled"),
                "message": _("%s reminder(s) have been scheduled for pending consents.") % total,
                "sticky": False,
            },
        }

    # -------------------------------------------------------------------------
    # QUICK HELPERS FOR OTHER MODULES
    # -------------------------------------------------------------------------
    def has_pending_consent(self):
        """Return True if the partner has at least one 'to_sign' consent."""
        self.ensure_one()
        Consent = self.env["clinic.consent.form"].sudo()
        return bool(Consent.search_count(
            [("patient_id", "=", self.id), ("state", "=", "to_sign")] + self._company_domain()
        ))

    def get_latest_signed_consent(self):
        """Return the latest signed consent record for this partner (or False)."""
        self.ensure_one()
        Consent = self.env["clinic.consent.form"].sudo()
        return Consent.search(
            [("patient_id", "=", self.id), ("state", "=", "signed")] + self._company_domain(),
            order="signature_datetime desc, write_date desc, id desc",
            limit=1,
        )

    # -------------------------------------------------------------------------
    # ONCHANGE (optional quality-of-life)
    # -------------------------------------------------------------------------
    @api.onchange("consent_portal_opt_out")
    def _onchange_consent_portal_opt_out(self):
        """
        Optional UX behavior: show a friendly message if user opts out of portal.
        Controllers and business logic should honor this preference where applicable.
        """
        if self.consent_portal_opt_out:
            return {
                "warning": {
                    "title": _("Portal Opt-out Enabled"),
                    "message": _(
                        "This contact opts out of portal-based consent signing. "
                        "Consider in-clinic signing flows instead."
                    ),
                }
            }
        return {}

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
        domain="[('state', '=', 'published'), '|', "
               "('applicability', '=', 'generic'), "
               "&('applicability', '=', 'treatment'), ('treatment_id', '=', id)]",
        help="Default template suggested when creating a consent for this treatment."
    )

    consent_template_ids = fields.One2many(
        "clinic.consent.template",
        "treatment_id",
        string="Associated Consent Templates",
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
            ("state", "=", "published"),
            ("applicability", "=", "treatment"),
            ("treatment_id", "=", self.id),
        ] + self._company_domain(), order="effective_date desc, id desc", limit=1)
        if specific:
            return specific

        # 3) any published generic
        generic = Template.search([
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
            "view_mode": "tree,form,kanban,calendar,pivot,graph",
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
            "view_mode": "tree,form",
            "domain": ["|",
                       "&", ("state", "=", "published"), ("applicability", "=", "treatment"),
                            ("treatment_id", "=", self.id),
                       "&", ("state", "=", "published"), ("applicability", "=", "generic")] + self._company_domain(),
            "context": {"default_applicability": "treatment", "default_treatment_id": self.id},
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
