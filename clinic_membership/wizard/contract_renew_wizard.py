


# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import fields, models, _
from odoo.exceptions import UserError


class MembershipContractRenewWizard(models.TransientModel):
    _name = "membership.contract.renew.wizard"
    _description = "Renew Membership Contract"

    contract_id = fields.Many2one("membership.contract", required=True, readonly=True)
    renewal_plan_id = fields.Many2one("membership.plan", required=True, domain="[('state','=','active'),('company_id','=',company_id)]")
    company_id = fields.Many2one(related="contract_id.company_id", readonly=True)
    start_date = fields.Date(required=True)
    auto_create_invoice = fields.Boolean(default=True)
    notes = fields.Text()

    def default_get(self, field_list):
        vals = super().default_get(field_list)
        contract = self.env["membership.contract"].browse(self.env.context.get("default_contract_id")).exists()
        if contract:
            plan = contract.renewal_plan_id if contract.renewal_policy == "custom_plan" and contract.renewal_plan_id else contract.plan_id
            vals.setdefault("renewal_plan_id", plan.id)
            vals.setdefault("start_date", (contract.end_date + timedelta(days=1)) if contract.end_date else fields.Date.context_today(self))
        return vals

    def action_renew(self):
        self.ensure_one()
        old = self.contract_id
        if old.state not in ("active", "on_hold", "expired"):
            raise UserError(_("Only Active, On Hold, or Expired memberships can be renewed."))
        plan = self.renewal_plan_id
        new = self.env["membership.contract"].create({
            "plan_id": plan.id, "company_id": old.company_id.id, "partner_id": old.partner_id.id,
            "patient_id": old.patient_id.id, "referral_id": old.referral_id.id,
            "start_date": self.start_date, "list_price": plan.list_price, "join_fee": 0.0,
            "renewal_fee": plan.renewal_fee, "renewed_from_id": old.id, "notes": self.notes,
        })
        old.write({"renewed_to_id": new.id})
        old._membership_write_state({"state": "renewed"})
        old._membership_publish_event("contract.renewed", {"old_contract_id": old.id, "new_contract_id": new.id})
        if self.auto_create_invoice and new.contract_value > 0:
            new.action_create_invoice()
        return {"type": "ir.actions.act_window", "name": _("Renewed Membership"), "res_model": "membership.contract", "res_id": new.id, "view_mode": "form", "target": "current"}


