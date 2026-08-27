from odoo import fields, models, _


class ResPartner(models.Model):
    """Partner navigation and Email Marketing recipient relation only."""

    _inherit = "res.partner"

    clinic_marketing_preference_ids = fields.One2many(
        "clinic.marketing.preference",
        "partner_id",
        string="Clinic Marketing Preferences",
    )
    clinic_marketing_recipient_ids = fields.One2many(
        "clinic.marketing.recipient",
        "partner_id",
        string="Clinic Marketing Recipient History",
        readonly=True,
    )
    clinic_marketing_preference_count = fields.Integer(
        compute="_compute_clinic_marketing_counts"
    )
    clinic_marketing_campaign_count = fields.Integer(
        compute="_compute_clinic_marketing_counts"
    )

    def _compute_clinic_marketing_counts(self):
        Preference = self.env["clinic.marketing.preference"].sudo()
        Recipient = self.env["clinic.marketing.recipient"].sudo()
        for partner in self:
            partner.clinic_marketing_preference_count = Preference.search_count([
                ("partner_id", "=", partner.id),
            ])
            partner.clinic_marketing_campaign_count = len(
                Recipient.search([
                    ("partner_id", "=", partner.id),
                ]).mapped("campaign_id")
            )

    def action_open_clinic_marketing_preferences(self):
        self.ensure_one()
        if not self.env.user.has_group("clinic_marketing.group_marketing_user"):
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Marketing Preferences"),
            "res_model": "clinic.marketing.preference",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {
                "default_partner_id": self.id,
                "default_company_id": self.env.company.id,
                "active_test": False,
            },
        }

    def action_open_clinic_marketing_campaigns(self):
        self.ensure_one()
        if not self.env.user.has_group("clinic_marketing.group_marketing_user"):
            return False
        campaign_ids = self.env["clinic.marketing.recipient"].sudo().search([
            ("partner_id", "=", self.id),
        ]).mapped("campaign_id").ids
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Marketing Campaigns"),
            "res_model": "clinic.marketing.campaign",
            "view_mode": "list,form",
            "domain": [("id", "in", campaign_ids)],
        }


class ClinicPatient(models.Model):
    """Patient navigation without taking ownership of clinical identity."""

    _inherit = "clinic.patient"

    clinic_marketing_campaign_count = fields.Integer(
        compute="_compute_clinic_marketing_campaign_count"
    )

    def _compute_clinic_marketing_campaign_count(self):
        Recipient = self.env["clinic.marketing.recipient"].sudo()
        for patient in self:
            patient.clinic_marketing_campaign_count = len(
                Recipient.search([
                    ("patient_id", "=", patient.id),
                ]).mapped("campaign_id")
            )

    def action_open_clinic_marketing_campaigns(self):
        self.ensure_one()
        if not self.env.user.has_group("clinic_marketing.group_marketing_user"):
            return False
        campaign_ids = self.env["clinic.marketing.recipient"].sudo().search([
            ("patient_id", "=", self.id),
        ]).mapped("campaign_id").ids
        return {
            "type": "ir.actions.act_window",
            "name": _("Patient Marketing Campaigns"),
            "res_model": "clinic.marketing.campaign",
            "view_mode": "list,form",
            "domain": [("id", "in", campaign_ids)],
        }


class ClinicBranch(models.Model):
    """Branch-to-Campaign navigation; Branch remains owned by clinic_branch."""

    _inherit = "clinic.branch"

    clinic_marketing_campaign_ids = fields.One2many(
        "clinic.marketing.campaign",
        "branch_id",
        string="Marketing Campaigns",
    )
    clinic_marketing_campaign_count = fields.Integer(
        compute="_compute_clinic_marketing_campaign_count"
    )

    def _compute_clinic_marketing_campaign_count(self):
        for branch in self:
            branch.clinic_marketing_campaign_count = len(
                branch.clinic_marketing_campaign_ids
            )

    def action_open_clinic_marketing_campaigns(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Branch Marketing Campaigns"),
            "res_model": "clinic.marketing.campaign",
            "view_mode": "list,form",
            "domain": [("branch_id", "=", self.id)],
        }


# Native mailing remains the Email engine; this bridge adds provenance only.
class MailingMailing(models.Model):
    """Provenance link from native Odoo Email Marketing back to ClinicOne."""

    _inherit = "mailing.mailing"

    clinic_marketing_campaign_id = fields.Many2one(
        "clinic.marketing.campaign",
        string="Clinic Marketing Campaign",
        ondelete="set null",
        index=True,
    )


# Storefront ownership remains in clinic_ecommerce; Marketing only adds promotion navigation.
class ClinicEcommerceCatalogItem(models.Model):
    """Promotion navigation for Clinic Shop offerings."""

    _inherit = "clinic.ecommerce.catalog.item"

    clinic_marketing_promotion_count = fields.Integer(
        compute="_compute_clinic_marketing_promotion_count"
    )

    def _compute_clinic_marketing_promotion_count(self):
        Promotion = self.env["clinic.marketing.promotion"].sudo()
        for item in self:
            item.clinic_marketing_promotion_count = Promotion.search_count([
                ("ecommerce_item_id", "=", item.id),
            ])

    def action_open_clinic_marketing_promotions(self):
        self.ensure_one()
        if not self.env.user.has_group("clinic_marketing.group_marketing_user"):
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Marketing Promotions"),
            "res_model": "clinic.marketing.promotion",
            "view_mode": "list,form",
            "domain": [("ecommerce_item_id", "=", self.id)],
        }

