from odoo import fields, models, _


class ResPartner(models.Model):
    """Additive backend navigation; Patient identity remains owned by clinic_patient."""

    _inherit = "res.partner"

    clinic_portal_profile_ids = fields.One2many(
        "clinic.portal.profile",
        "partner_id",
        string="Clinic Portal Profiles",
    )
    clinic_portal_profile_count = fields.Integer(
        compute="_compute_clinic_portal_profile_count",
    )

    def _compute_clinic_portal_profile_count(self):
        Profile = self.env["clinic.portal.profile"].sudo()
        for partner in self:
            partner.clinic_portal_profile_count = Profile.search_count([
                ("partner_id", "=", partner.id),
            ])

    def action_open_clinic_portal_profiles(self):
        self.ensure_one()
        if not self.env.user.has_group(
            "clinic_portal.group_patient_portal_operator"
        ):
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic Portal Profiles"),
            "res_model": "clinic.portal.profile",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {
                "default_partner_id": self.id,
                "default_company_id": self.env.company.id,
                "active_test": False,
            },
        }


class ClinicPatient(models.Model):
    """Patient-to-Portal navigation without changing Patient clinical ownership."""

    _inherit = "clinic.patient"

    clinic_portal_profile_ids = fields.One2many(
        "clinic.portal.profile",
        "patient_id",
        string="Clinic Portal Profiles",
    )
    clinic_portal_profile_count = fields.Integer(
        compute="_compute_clinic_portal_profile_count",
    )

    def _compute_clinic_portal_profile_count(self):
        Profile = self.env["clinic.portal.profile"].sudo()
        for patient in self:
            patient.clinic_portal_profile_count = Profile.search_count([
                ("patient_id", "=", patient.id),
            ])

    def action_open_clinic_portal_profiles(self):
        self.ensure_one()
        if not self.env.user.has_group(
            "clinic_portal.group_patient_portal_operator"
        ):
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Clinic Portal Profiles"),
            "res_model": "clinic.portal.profile",
            "view_mode": "list,form",
            "domain": [("patient_id", "=", self.id)],
            "context": {
                "default_partner_id": self.partner_id.id,
                "default_company_id": self.company_id.id,
                "active_test": False,
            },
        }
