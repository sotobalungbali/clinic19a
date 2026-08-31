# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ClinicBranchReferral(models.Model):
    """Branch-level referral operational navigation."""

    _inherit = "clinic.branch"

    referral_count = fields.Integer(compute="_compute_referral_counts")
    converted_referral_count = fields.Integer(
        compute="_compute_referral_counts"
    )

    def _compute_referral_counts(self):
        Referral = self.env["clinic.referral"]
        for branch in self:
            branch.referral_count = Referral.search_count(
                [("branch_id", "=", branch.id)]
            )
            branch.converted_referral_count = Referral.search_count(
                [
                    ("branch_id", "=", branch.id),
                    ("state", "=", "converted"),
                ]
            )

    def action_open_referrals(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Branch Referrals"),
            "res_model": "clinic.referral",
            "view_mode": "list,kanban,form",
            "domain": [("branch_id", "=", self.id)],
            "context": {
                "default_branch_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }

