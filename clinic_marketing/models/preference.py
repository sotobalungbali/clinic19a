from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


CONSENT_SELECTION = [
    ("unknown", "Unknown / Not Recorded"),
    ("opt_in", "Opted In"),
    ("opt_out", "Opted Out"),
]

SOURCE_SELECTION = [
    ("frontdesk", "Front Desk"),
    ("patient", "Patient Request"),
    ("portal", "Patient Portal"),
    ("consent", "Consent / Legal Record"),
    ("import", "Imported"),
    ("campaign", "Campaign Response"),
    ("admin", "Administrator"),
    ("other", "Other"),
]


class ClinicMarketingPreference(models.Model):
    """Company-scoped patient marketing channel preference.

    Marketing consent is intentionally separated from treatment/medical consent.
    This model does not replace Odoo's global email blacklist; both controls are
    respected by the campaign/email pipeline.
    """

    _name = "clinic.marketing.preference"
    _description = "Clinic Marketing Preference"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "partner_id, company_id, id"
    _check_company_auto = True

    _partner_company_unique = models.Constraint(
        "UNIQUE(company_id, partner_id)",
        "Only one Marketing Preference is allowed per patient contact and company.",
    )
    _company_consent_idx = models.Index(
        "(company_id, do_not_contact, email_consent, whatsapp_consent)"
    )

    name = fields.Char(compute="_compute_name", store=True, index=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Patient Contact",
        required=True,
        ondelete="cascade",
        domain="[('is_patient', '=', True)]",
        index=True,
        tracking=True,
    )
    patient_id = fields.Many2one(
        related="partner_id.patient_id",
        string="Patient Card",
        store=True,
        readonly=True,
        index=True,
    )
    branch_id = fields.Many2one(
        related="partner_id.branch_id",
        string="Primary Branch",
        store=True,
        readonly=True,
        index=True,
    )

    email_consent = fields.Selection(
        CONSENT_SELECTION,
        default="unknown",
        required=True,
        tracking=True,
        index=True,
    )
    whatsapp_consent = fields.Selection(
        CONSENT_SELECTION,
        default="unknown",
        required=True,
        tracking=True,
        index=True,
    )
    do_not_contact = fields.Boolean(
        string="Do Not Contact",
        default=False,
        tracking=True,
        index=True,
        help="Global ClinicOne marketing suppression for this company.",
    )
    consent_source = fields.Selection(
        SOURCE_SELECTION,
        default="frontdesk",
        required=True,
        tracking=True,
    )
    consent_note = fields.Text()
    consent_updated_at = fields.Datetime(readonly=True, index=True)
    consent_updated_by_id = fields.Many2one(
        "res.users",
        readonly=True,
    )
    active = fields.Boolean(default=True)

    campaign_recipient_ids = fields.One2many(
        "clinic.marketing.recipient",
        "preference_id",
        string="Campaign Recipient History",
        readonly=True,
    )
    campaign_count = fields.Integer(compute="_compute_campaign_count")

    @api.depends("partner_id", "company_id")
    def _compute_name(self):
        for record in self:
            if record.partner_id:
                record.name = _("%(patient)s - Marketing Preferences") % {
                    "patient": record.partner_id.display_name,
                }
            else:
                record.name = _("New Marketing Preference")

    def _compute_campaign_count(self):
        for record in self:
            record.campaign_count = len(
                record.campaign_recipient_ids.mapped("campaign_id")
            )

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            if vals.get("email_consent", "unknown") != "unknown" or (
                vals.get("whatsapp_consent", "unknown") != "unknown"
            ) or vals.get("do_not_contact"):
                vals.setdefault("consent_updated_at", fields.Datetime.now())
                vals.setdefault("consent_updated_by_id", self.env.user.id)
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        vals = dict(vals)
        consent_fields = {
            "email_consent",
            "whatsapp_consent",
            "do_not_contact",
            "consent_source",
            "consent_note",
        }
        if consent_fields.intersection(vals):
            if not (
                self.env.su
                or self.env.user.has_group(
                    "clinic_marketing.group_marketing_coordinator"
                )
            ):
                raise AccessError(
                    _("Marketing consent changes require Marketing Coordinator access.")
                )
            vals["consent_updated_at"] = fields.Datetime.now()
            vals["consent_updated_by_id"] = self.env.user.id
        return super().write(vals)

    @api.constrains("company_id", "partner_id", "patient_id", "branch_id")
    def _check_patient_scope(self):
        for record in self:
            if not record.partner_id.is_patient or not record.patient_id:
                raise ValidationError(
                    _("Marketing Preference requires a linked Clinic Patient.")
                )
            if record.patient_id.partner_id != record.partner_id:
                raise ValidationError(
                    _("Patient Card and Patient Contact linkage is inconsistent.")
                )
            if (
                record.patient_id.company_id
                and record.patient_id.company_id != record.company_id
            ):
                raise ValidationError(
                    _("Marketing Preference company must match the Patient Card company.")
                )
            if (
                record.branch_id
                and record.branch_id.company_id != record.company_id
            ):
                raise ValidationError(
                    _("Patient Primary Branch must belong to the Marketing Preference company.")
                )

    def _set_channel_consent(self, channel, status):
        if channel not in ("email", "whatsapp"):
            raise ValidationError(_("Unsupported marketing channel."))
        if status not in dict(CONSENT_SELECTION):
            raise ValidationError(_("Unsupported consent status."))
        self.write({
            f"{channel}_consent": status,
            "consent_source": "admin",
        })
        return True

    def action_opt_in_email(self):
        return self._set_channel_consent("email", "opt_in")

    def action_opt_out_email(self):
        return self._set_channel_consent("email", "opt_out")

    def action_opt_in_whatsapp(self):
        return self._set_channel_consent("whatsapp", "opt_in")

    def action_opt_out_whatsapp(self):
        return self._set_channel_consent("whatsapp", "opt_out")

    def action_do_not_contact(self):
        self.write({
            "do_not_contact": True,
            "consent_source": "admin",
        })
        return True

    def action_allow_contact(self):
        self.write({
            "do_not_contact": False,
            "consent_source": "admin",
        })
        return True

    def action_open_patient(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Card"),
            "res_model": "clinic.patient",
            "view_mode": "form",
            "res_id": self.patient_id.id,
        }

    def action_open_campaigns(self):
        self.ensure_one()
        campaign_ids = self.campaign_recipient_ids.mapped("campaign_id").ids
        return {
            "type": "ir.actions.act_window",
            "name": _("Marketing Campaigns"),
            "res_model": "clinic.marketing.campaign",
            "view_mode": "list,form",
            "domain": [("id", "in", campaign_ids)],
        }

    # A campaign must satisfy both ClinicOne suppression and per-channel consent; native Email blacklists apply later too.
    def _channel_allowed(self, channel, require_explicit=True):
        self.ensure_one()
        if self.do_not_contact:
            return False
        value = self[f"{channel}_consent"]
        if value == "opt_out":
            return False
        if require_explicit:
            return value == "opt_in"
        return value != "opt_out"

    @api.model
    def _find_for_partner(self, partner, company):
        return self.sudo().with_context(active_test=False).search([
            ("company_id", "=", company.id),
            ("partner_id", "=", partner.id),
        ], limit=1)

