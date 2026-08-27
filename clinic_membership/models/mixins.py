

# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import UserError


class MembershipWorkflowMixin(models.AbstractModel):
    """Reusable workflow guard for governed ClinicOne membership records.

    Business actions transition state through ``_membership_write_state``.
    Direct RPC/import writes to ``state`` are rejected so XML visibility is
    never treated as the security boundary.
    """

    _name = "membership.workflow.mixin"
    _description = "Membership Workflow Guard"

    def _membership_write_state(self, values):
        return self.with_context(clinic_membership_state_change=True).write(values)

    def _membership_guard_direct_state_write(self, values):
        if "state" in values and not self.env.context.get("clinic_membership_state_change"):
            raise UserError(
                _("Status must be changed with the approved membership workflow action.")
            )


class MembershipEventMixin(models.AbstractModel):
    """Small helper used by core models to publish downstream events."""

    _name = "membership.event.mixin"
    _description = "Membership Integration Event Publisher"

    def _membership_publish_event(self, event_code, payload=None, source=None):
        Event = self.env["membership.integration.event"].sudo()
        created = self.env["membership.integration.event"]
        for rec in self:
            src = source or rec
            vals = {
                "event_code": event_code,
                "company_id": getattr(rec, "company_id", self.env.company).id,
                "source_model": src._name,
                "source_res_id": src.id,
                "source_reference": getattr(src, "display_name", False) or "",
                "payload_json": Event._json_dumps(payload or {}),
            }
            if rec._name == "membership.contract":
                vals["contract_id"] = rec.id
            elif "contract_id" in rec._fields and rec.contract_id:
                vals["contract_id"] = rec.contract_id.id
            created |= Event.create(vals)
        return created

