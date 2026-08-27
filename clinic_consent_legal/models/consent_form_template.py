
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
    # Odoo 19 requires an explicit _name when _inherit is a list. Using the
    # same model name as the first inherited model extends the existing model
    # in place while also adding the mail mixins; it does not create a second
    # business model/table.
    _name = "clinic.consent.template"
    _inherit = ["clinic.consent.template", "mail.thread", "mail.activity.mixin"]

    # -------------------------------------------------------------------------
    # CORE / IDENTITY
    # -------------------------------------------------------------------------
    legal_governed = fields.Boolean(
        string="Legal Governance Enabled",
        default=False,
        index=True,
        help=(
            "Opt this canonical Treatment Catalog template into the advanced "
            "Consent & Legal governance lifecycle. Core catalog templates remain "
            "fully compatible when this option is disabled."
        ),
    )

    legal_reference = fields.Char(
        string="Legal Reference",
        copy=False,
        readonly=True,
        index=True,
        help="Unique legal/governance identifier generated when legal governance is enabled.",
    )

    title = fields.Char(
        string="Legal Title",
        required=False,
        tracking=True,
        help="Short title of the consent template (e.g., 'Laser Treatment Consent')."
    )


    company_id = fields.Many2one(
        "res.company",
        string="Legal Company",
        index=True,
        help=(
            "Company governing this legal template. Non-governed canonical "
            "Treatment Catalog templates may remain global."
        ),
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


    # -------------------------------------------------------------------------
    # DEFAULTS
    # -------------------------------------------------------------------------
    @api.model
    def _default_name(self):
        # Sequence code should exist in data/consent_sequence.xml (or own template sequence)
        return self.env["ir.sequence"].next_by_code("clinic.consent.template") or _("New Template")

    @api.model
    def default_get(self, fields_list):
        """Add legal defaults without changing canonical Treatment Catalog behavior."""
        values = super().default_get(fields_list)
        legal_default = bool(
            self.env.context.get("default_legal_governed")
            or values.get("legal_governed")
        )
        if legal_default:
            values["legal_governed"] = True
            if "scope" in fields_list and not values.get("scope"):
                values["scope"] = "treatment_general"
        return values

    @api.onchange("name")
    def _onchange_name_legal_title(self):
        for rec in self:
            if rec.name and not rec.title:
                rec.title = rec.name

    # -------------------------------------------------------------------------
    # COMPUTES
    # -------------------------------------------------------------------------
    @api.depends("legal_reference", "name", "title")
    def _compute_display_name(self):
        for rec in self:
            title = rec.title or rec.name or _("Consent Template")
            if rec.legal_reference:
                rec.display_name = f"[{rec.legal_reference}] {title}"
            else:
                rec.display_name = title

    @api.depends()
    def _compute_usage_count(self):
        """Count usages with the Odoo 19 backend grouping API."""
        Consent = self.env["clinic.consent.form"]
        grouped = Consent._read_group(
            domain=[("template_id", "in", self.ids)],
            groupby=["template_id"],
            aggregates=["__count"],
        )
        mapped = {
            template.id: count
            for template, count in grouped
            if template
        }
        for rec in self:
            rec.usage_count = mapped.get(rec.id, 0)

    # -------------------------------------------------------------------------
    # CONSTRAINTS & SANITY CHECKS
    # -------------------------------------------------------------------------
    _legal_reference_company_uniq = models.Constraint(
        "unique(legal_reference, company_id)",
        "Legal Reference must be unique per company.",
    )

    @api.constrains("title", "content_html", "content_text")
    def _check_minimum_content(self):
        for rec in self.filtered("legal_governed"):
            if not rec.title:
                raise ValidationError(_("Legal Title is required for legally governed templates."))
            if not (rec.content_html or rec.content_text):
                raise ValidationError(_("Legal consent content is required (HTML or Text)."))

    @api.constrains("applicability", "treatment_id")
    def _check_applicability(self):
        for rec in self.filtered("legal_governed"):
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
        """Apply legal versioning only to templates opted into legal governance."""
        content_fields = {
            "content_html",
            "content_text",
            "risks_and_complications",
            "alternatives",
            "required_before_procedure",
            "validity_days",
            "title",
        }
        content_will_change = any(field_name in vals for field_name in content_fields)

        if content_will_change:
            force_edit = self.env.context.get("force_edit_published")
            protected = self.filtered(
                lambda rec: rec.legal_governed
                and rec.state == "published"
                and rec.usage_count > 0
            )
            if protected and not force_edit:
                raise AccessError(_(
                    "Cannot modify legal content of a published template already in use.\n"
                    "Duplicate it as a new version instead."
                ))

        result = super().write(vals)

        if self.env.context.get("skip_legal_versioning"):
            return result

        governed = self.filtered("legal_governed")
        for rec in governed:
            if not rec.legal_reference:
                rec.with_context(skip_legal_versioning=True).write({
                    "legal_reference": rec._default_name(),
                })
            if not rec.title and rec.name:
                rec.with_context(skip_legal_versioning=True).write({"title": rec.name})

            if content_will_change or "version_major" in vals or "version_minor" in vals:
                rec._update_content_checksum()

            if rec.version_auto_bump and content_will_change:
                rec._bump_minor_version(persist=True)

        return result

    def unlink(self):
        """Protect governed legal history without changing canonical template deletion rules."""
        protected = self.filtered(
            lambda rec: rec.legal_governed
            and (rec.state != "draft" or rec.usage_count)
        )
        if protected:
            raise AccessError(_(
                "Only unused Draft legally governed templates can be deleted. "
                "Retire or version a template that has entered operational use."
            ))
        return super().unlink()

    def copy(self, default=None):
        """Version governed templates; preserve canonical copy semantics otherwise."""
        self.ensure_one()
        if not self.legal_governed:
            return super().copy(default)

        default = dict(default or {})
        default.setdefault("legal_governed", True)
        default.setdefault("legal_reference", False)
        # The canonical Treatment Catalog model owns `code` and enforces it
        # as unique. A legal version must not clone that unique identifier.
        default.setdefault("code", False)
        default.setdefault("title", f"{self.title or self.name} (Copy)")
        default.setdefault("version_major", (self.version_major or 1) + 1)
        default.setdefault("version_minor", 0)
        default.setdefault(
            "consent_version",
            f"v{default['version_major']}.{default['version_minor']}",
        )
        default.setdefault("state", "draft")
        default.setdefault("supersedes_id", self.id)
        default.setdefault("superseded_by_id", False)
        rec = super().copy(default)
        self.sudo().with_context(skip_legal_versioning=True).write({
            "superseded_by_id": rec.id,
        })
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
                rec.with_context(skip_legal_versioning=True).write({
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
                rec.with_context(skip_legal_versioning=True).write({"content_checksum": checksum})

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_publish(self):
        for rec in self:
            if rec.state == "retired":
                raise UserError(_("Cannot publish a retired template. Duplicate it instead."))
            if not rec.legal_governed:
                raise UserError(_("Enable Legal Governance before publishing a legal template."))
            if not rec.title or not (rec.content_html or rec.content_text):
                raise UserError(_("Please complete the Legal Title and Content before publishing."))
            vals = {"state": "published"}
            if not rec.legal_reference:
                vals["legal_reference"] = rec._default_name()
            rec.with_context(skip_legal_versioning=True).write(vals)
            rec._update_content_checksum()

    def action_retire(self):
        for rec in self:
            if not rec.legal_governed:
                raise UserError(_("Enable Legal Governance before retiring a legal template."))
            # The record remains available historically after retirement.
            rec.write({"state": "retired"})

    def action_duplicate_new_version(self):
        """User-facing action to duplicate into the next major version in Draft."""
        self.ensure_one()
        if not self.legal_governed:
            raise UserError(_("Enable Legal Governance before creating a legal version."))
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

        create_context = self.env.context.get("clinic_consent_create_context") or {}
        patient_id = patient_id or create_context.get("patient_id")
        treatment_id = treatment_id or create_context.get("treatment_id")
        doctor_id = doctor_id or create_context.get("doctor_id")
        booking_id = booking_id or create_context.get("booking_id")
        room_session_id = room_session_id or create_context.get("room_session_id")

        if not self.legal_governed or self.state != "published":
            raise UserError(_("Only published legally governed templates can create legal consents."))

        if not patient_id:
            defaults = self._prepare_consent_vals_from_template(
                patient_id=False,
                treatment_id=treatment_id or (
                    self.treatment_id.id
                    if self.applicability == "treatment" and self.treatment_id
                    else False
                ),
                doctor_id=doctor_id,
                booking_id=booking_id,
                room_session_id=room_session_id,
                source=source,
                title=title or self.title,
            )
            defaults.pop("patient_id", None)
            return {
                "type": "ir.actions.act_window",
                "name": _("New Consent"),
                "res_model": "clinic.consent.form",
                "view_mode": "form",
                "target": "current",
                "context": {
                    **self.env.context,
                    **{f"default_{key}": value for key, value in defaults.items()},
                },
            }

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
        return [(rec.id, rec.display_name) for rec in self]

    # -------------------------------------------------------------------------
    # HOOKS
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for incoming in vals_list:
            vals = dict(incoming)
            legal_governed = bool(
                vals.get("legal_governed")
                or self.env.context.get("default_legal_governed")
            )
            if legal_governed:
                vals["legal_governed"] = True
                if not vals.get("legal_reference"):
                    vals["legal_reference"] = self._default_name()
                if not vals.get("company_id"):
                    vals["company_id"] = self.env.company.id
                if vals.get("name") and not vals.get("title"):
                    vals["title"] = vals["name"]
                vals.setdefault("scope", "treatment_general")
            prepared.append(vals)

        records = super().create(prepared)
        for rec in records.filtered("legal_governed"):
            rec._update_content_checksum()
        return records

