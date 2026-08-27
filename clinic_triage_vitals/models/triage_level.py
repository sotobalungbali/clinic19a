
# -*- coding: utf-8 -*-
# File: models/triage_level.py
#
# ClinicOne - Triage & Vitals Intake
# Model: clinic.triage.level
#
# Design goals:
# - Clean, explicit model for triage categories (e.g., Red, Yellow, Green, Blue).
# - Holds SLA, scoring "weight", vitals thresholds, recommended routing (room/queue), and fee hooks.
# - English UI strings per product requirement.
# - Multi-company safe; integrates with mail tracking for auditability.
#
# Notes on cross-module integration:
# - recommended_room_type_id -> expects model 'clinic.room.type' (Clinic Room & Device module).
# - default_queue_stage_id  -> optional; expects model 'clinic.queue.stage' if the queue module is installed.
# - product_id / default_fee -> integrated to 'product' and 'account' for optional billing of triage level.
#
# Migration note:
# - If there are legacy references to 'clinicone.triage.level', update them to 'clinic.triage.level'
#   in dependent modules (e.g., triage_session.py) during the refactor to the 'clinic_*' prefix.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicTriageLevel(models.Model):
    _name = "clinic.triage.level"
    _description = "Clinic Triage Level"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "sequence, weight desc, id"

    # -------------------------------------------------------------------------
    # Identity & Display
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Name",
        required=True,
        index=True,
        tracking=True,
        help="Display name of the triage level, for example: 'Red', 'Yellow', 'Green', 'Blue'."
    )
    code = fields.Char(
        string="Code",
        required=True,
        index=True,
        tracking=True,
        help="Short unique code for the triage level (e.g., RED, YEL, GRN, BLU)."
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Ordering helper; lower values appear first."
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to hide this triage level without deleting it."
    )
    color = fields.Integer(
        string="Kanban Color",
        default=0,
        help="Optional color index used by Kanban views."
    )
    color_hex = fields.Char(
        string="Hex Color",
        help="Optional hex color code for this triage level (e.g., #FF0000 for Red)."
    )
    description = fields.Text(
        string="Description",
        help="Short description of the triage level."
    )
    guidelines_html = fields.Html(
        string="Guidelines",
        sanitize=False,
        help="Internal guidelines for staff when handling patients in this triage level."
    )

    # -------------------------------------------------------------------------
    # Company & Currency
    # -------------------------------------------------------------------------
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        help="Owning company for this configuration."
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True
    )

    # -------------------------------------------------------------------------
    # SLA & Scoring
    # -------------------------------------------------------------------------
    sla_minutes = fields.Integer(
        string="SLA (minutes)",
        default=0,
        tracking=True,
        help="Target minutes to start triage for this level, measured from patient arrival."
    )
    weight = fields.Integer(
        string="Priority Weight",
        default=10,
        tracking=True,
        help="Relative priority weight. Higher means more urgent. Used to compute session priority."
    )
    auto_escalate = fields.Boolean(
        string="Auto Escalate",
        help="If enabled, the system can propose escalation after a time threshold."
    )
    escalate_after_minutes = fields.Integer(
        string="Escalate After (min)",
        default=0,
        help="If 'Auto Escalate' is enabled, propose escalation when triage hasn't started within this time."
    )
    escalate_to_level_id = fields.Many2one(
        "clinic.triage.level",
        string="Escalate To",
        help="Proposed triage level to escalate to when the escalation threshold is reached."
    )

    # -------------------------------------------------------------------------
    # Vitals Thresholds (optional; used by downstream rules/automations)
    # Any threshold can be left empty (null) to mean 'not used'.
    # These are guidance values; enforcement belongs in business rules.
    # -------------------------------------------------------------------------
    temp_min_c = fields.Float(
        string="Temp Min (°C)",
        digits=(6, 2),
        help="Minimum body temperature in Celsius considered for this level."
    )
    temp_max_c = fields.Float(
        string="Temp Max (°C)",
        digits=(6, 2),
        help="Maximum body temperature in Celsius considered for this level."
    )
    hr_min_bpm = fields.Integer(
        string="HR Min (bpm)",
        help="Minimum heart rate (beats per minute) considered for this level."
    )
    hr_max_bpm = fields.Integer(
        string="HR Max (bpm)",
        help="Maximum heart rate (beats per minute) considered for this level."
    )
    rr_min_bpm = fields.Integer(
        string="RR Min (breaths/min)",
        help="Minimum respiratory rate (breaths per minute) considered for this level."
    )
    rr_max_bpm = fields.Integer(
        string="RR Max (breaths/min)",
        help="Maximum respiratory rate (breaths per minute) considered for this level."
    )
    spo2_min_percent = fields.Float(
        string="SpO₂ Min (%)",
        digits=(6, 2),
        help="Minimum oxygen saturation percentage considered for this level."
    )
    sbp_min_mm_hg = fields.Integer(
        string="SBP Min (mmHg)",
        help="Minimum systolic blood pressure considered for this level."
    )
    sbp_max_mm_hg = fields.Integer(
        string="SBP Max (mmHg)",
        help="Maximum systolic blood pressure considered for this level."
    )
    dbp_min_mm_hg = fields.Integer(
        string="DBP Min (mmHg)",
        help="Minimum diastolic blood pressure considered for this level."
    )
    dbp_max_mm_hg = fields.Integer(
        string="DBP Max (mmHg)",
        help="Maximum diastolic blood pressure considered for this level."
    )
    gcs_min = fields.Integer(
        string="GCS Min",
        help="Minimum Glasgow Coma Scale considered for this level."
    )
    gcs_max = fields.Integer(
        string="GCS Max",
        help="Maximum Glasgow Coma Scale considered for this level."
    )

    # -------------------------------------------------------------------------
    # Routing Recommendations (optional)
    # -------------------------------------------------------------------------
    recommended_room_type_id = fields.Many2one(
        "clinic.room.type",
        string="Recommended Room Type",
        help="Recommended room type for patients with this triage level."
    )
    default_queue_stage_id = fields.Many2one(
        "clinic.queue.stage",
        string="Default Queue Stage",
        help="Default queue stage used when a token is created for this level (if queue module is installed)."
    )

    # -------------------------------------------------------------------------
    # Billing Hooks (optional)
    # -------------------------------------------------------------------------
    billable = fields.Boolean(
        string="Billable",
        help="Enable if patients in this triage level should be billed by default."
    )
    product_id = fields.Many2one(
        "product.product",
        string="Service Product",
        help="Service product to use for billing this triage level by default."
    )
    default_fee = fields.Monetary(
        string="Default Fee",
        help="Default fee suggested when billing a triage session of this level."
    )
    default_activity_type_id = fields.Many2one(
        "mail.activity.type",
        string="Default Activity Type",
        help="Suggested activity type to create when this triage level is assigned."
    )

    # -------------------------------------------------------------------------
    # Technical
    # -------------------------------------------------------------------------
    rule_domain = fields.Char(
        string="Suggested Rule Domain",
        help="Optional domain (in Odoo domain syntax) that describes when this level should be suggested, "
             "for example based on vitals or tags. Used by automation rules."
    )

    # -------------------------------------------------------------------------
    # Constraints (SQL)
    # -------------------------------------------------------------------------
    _code_company_uniq = models.Constraint(
        "UNIQUE(code, company_id)",
        "The triage level code must be unique per company.",
    )
    _name_company_uniq = models.Constraint(
        "UNIQUE(name, company_id)",
        "The triage level name must be unique per company.",
    )

    # -------------------------------------------------------------------------
    # Onchange & ORM overrides
    # -------------------------------------------------------------------------
    @api.onchange("code")
    def _onchange_code_upper(self):
        """Normalize the code to uppercase and strip spaces when edited."""
        if self.code:
            self.code = self.code.strip().upper()

    @api.constrains(
        "sla_minutes",
        "escalate_after_minutes",
        "escalate_to_level_id",
        "temp_min_c", "temp_max_c",
        "hr_min_bpm", "hr_max_bpm",
        "rr_min_bpm", "rr_max_bpm",
        "spo2_min_percent",
        "sbp_min_mm_hg", "sbp_max_mm_hg",
        "dbp_min_mm_hg", "dbp_max_mm_hg",
        "gcs_min", "gcs_max",
        "company_id"
    )
    def _check_constraints(self):
        for rec in self:
            # Non-negative SLA
            if rec.sla_minutes is not None and rec.sla_minutes < 0:
                raise ValidationError(_("SLA (minutes) cannot be negative."))

            # Escalation logic
            if rec.auto_escalate:
                if not rec.escalate_after_minutes or rec.escalate_after_minutes <= 0:
                    raise ValidationError(_("Please provide a positive 'Escalate After (min)' when Auto Escalate is enabled."))
                if not rec.escalate_to_level_id:
                    raise ValidationError(_("Please set 'Escalate To' when Auto Escalate is enabled."))
                if rec.escalate_to_level_id == rec:
                    raise ValidationError(_("Escalation target cannot be the same triage level."))
                if rec.escalate_to_level_id.company_id and rec.company_id and rec.escalate_to_level_id.company_id != rec.company_id:
                    raise ValidationError(_("Escalation target must belong to the same company."))

            # Threshold sanity checks (min <= max if both present)
            _pairs = [
                ("temp_min_c", "temp_max_c", _("Temperature (°C)")),
                ("hr_min_bpm", "hr_max_bpm", _("Heart rate (bpm)")),
                ("rr_min_bpm", "rr_max_bpm", _("Respiratory rate (breaths/min)")),
                ("sbp_min_mm_hg", "sbp_max_mm_hg", _("Systolic blood pressure (mmHg)")),
                ("dbp_min_mm_hg", "dbp_max_mm_hg", _("Diastolic blood pressure (mmHg)")),
                ("gcs_min", "gcs_max", _("Glasgow Coma Scale")),
            ]
            for fmin, fmax, label in _pairs:
                vmin = getattr(rec, fmin)
                vmax = getattr(rec, fmax)
                if vmin is not None and vmax is not None and vmin > vmax:
                    raise ValidationError(_("Invalid %s thresholds: min cannot be greater than max.") % label)

    @api.model_create_multi
    def create(self, vals_list):
        # Normalize codes, default name if missing, and ensure company defaults.
        for vals in vals_list:
            if vals.get("code"):
                vals["code"] = vals["code"].strip().upper()
            if not vals.get("name") and vals.get("code"):
                vals["name"] = vals["code"].title()
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
        records = super().create(vals_list)
        for rec in records:
            rec.message_post(
                body=_("Triage level created: <b>%(name)s</b> [%(code)s].") % {"name": rec.name, "code": rec.code},
                subtype_xmlid="mail.mt_note",
            )
        return records

    def write(self, vals):
        # Normalize code on write as well.
        if "code" in vals and vals["code"]:
            vals["code"] = vals["code"].strip().upper()
        res = super().write(vals)
        # Post lightweight change summary on important fields.
        tracked = {"sla_minutes", "weight", "auto_escalate", "escalate_after_minutes", "escalate_to_level_id", "billable"}
        if tracked.intersection(vals.keys()):
            for rec in self:
                parts = []
                if "sla_minutes" in vals:
                    parts.append(_("SLA (minutes): %s") % rec.sla_minutes)
                if "weight" in vals:
                    parts.append(_("Priority Weight: %s") % rec.weight)
                if "auto_escalate" in vals or "escalate_after_minutes" in vals or "escalate_to_level_id" in vals:
                    parts.append(_("Auto Escalate: %s") % (_("Yes") if rec.auto_escalate else _("No")))
                    if rec.auto_escalate:
                        parts.append(_("Escalate After (min): %s") % rec.escalate_after_minutes)
                        if rec.escalate_to_level_id:
                            parts.append(_("Escalate To: %s") % rec.escalate_to_level_id.display_name)
                if "billable" in vals:
                    parts.append(_("Billable: %s") % (_("Yes") if rec.billable else _("No")))
                if parts:
                    rec.message_post(body="<br/>".join(parts), subtype_xmlid="mail.mt_note")
        return res

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    @api.depends("name", "code", "sla_minutes")
    def _compute_display_name(self):
        """Build the Odoo 19 display name used by relational widgets."""
        for rec in self:
            parts = [rec.name or _("Triage Level")]
            if rec.code:
                parts.append("[%s]" % rec.code)
            if rec.sla_minutes:
                parts.append(_("SLA: %sm") % rec.sla_minutes)
            rec.display_name = " ".join(parts)

    def name_get(self):
        """Compatibility wrapper for older ClinicOne callers."""
        return [(rec.id, rec.display_name) for rec in self]

    @api.model
    def get_sla_minutes(self, level_id):
        """Small helper to safely return SLA minutes for a given level ID (int/record)."""
        level = level_id if isinstance(level_id, models.BaseModel) else self.browse(level_id)
        return int(level.sla_minutes or 0)
