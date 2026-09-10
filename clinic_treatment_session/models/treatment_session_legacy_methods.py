
# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import UserError


class ClinicTreatmentSessionLegacyMethods(models.Model):
    """Historical public workflow and billing helper API."""

    _inherit = "clinic.treatment.session"

    def _workflow_write(self, values):
        return self.with_context(clinic_treatment_session_workflow=True).write(values)

    def _sync_stage_with_state(self):
        Stage = self.env["clinic.treatment.session.stage"]
        for rec in self:
            stage = Stage.get_default_stage(rec.state, rec.company_id.id)
            if stage and rec.stage_id != stage:
                rec.with_context(clinic_treatment_session_workflow=True).write({"stage_id": stage.id})
        return True

    def action_confirm(self):
        for rec in self.filtered(lambda r: r.state == "draft"):
            rec._workflow_write({"state": "confirmed"}); rec._sync_stage_with_state()
        return True

    def action_start(self):
        for rec in self.filtered(lambda r: r.state in ("draft", "confirmed")):
            rec._workflow_write({"state": "in_progress"}); rec._sync_stage_with_state()
        return True

    def action_done(self):
        for rec in self.filtered(lambda r: r.state in ("draft", "confirmed", "in_progress")):
            rec._workflow_write({"state": "done"}); rec._sync_stage_with_state(); rec._post_done_hook()
        return True

    def action_no_show(self):
        for rec in self.filtered(lambda r: r.state in ("draft", "confirmed")):
            rec._workflow_write({"state": "no_show"}); rec._sync_stage_with_state()
        return True

    def action_cancel(self):
        for rec in self.filtered(lambda r: r.state not in ("done", "cancelled")):
            rec._workflow_write({"state": "cancelled"}); rec._sync_stage_with_state()
        return True

    def action_reset_draft(self):
        for rec in self.filtered(lambda r: r.state in ("cancelled", "no_show")):
            rec._workflow_write({"state": "draft"}); rec._sync_stage_with_state()
        return True

    def _post_done_hook(self):
        return True

    def action_prepare_billing(self):
        self.ensure_one()
        lines = []
        for line in self.line_ids.filtered(lambda l: l.display_type == "line" and l.is_billable):
            payload = line.prepare_billing_payload_line()
            if payload:
                lines.append(payload)
        return {
            "session_id": self.id, "patient_id": self.patient_id.id,
            "company_id": self.company_id.id, "lines": lines,
        }

    def action_create_invoice(self):
        self.ensure_one()
        if self.move_id:
            return self.action_view_invoice()
        if self.state != "done":
            raise UserError(_("Complete the Treatment Session before invoicing."))
        commands = []
        for item in self.action_prepare_billing()["lines"]:
            commands.append((0, 0, {
                "product_id": item["product_id"], "name": item["name"],
                "quantity": item["qty"], "price_unit": item["price_unit"],
                "discount": item["discount"], "tax_ids": [(6, 0, item.get("tax_ids", []))],
            }))
        if not commands:
            raise UserError(_("No billable Treatment Session lines were found."))
        move = self.env["account.move"].create({
            "move_type": "out_invoice", "partner_id": self.patient_id.id,
            "company_id": self.company_id.id, "invoice_origin": self.name,
            "invoice_line_ids": commands,
        })
        self.move_id = move
        return self.action_view_invoice()

    def action_link_payment(self):
        self.ensure_one()
        if self.move_id:
            return self.action_view_invoice()
        if self.billing_invoice_id:
            return self.action_view_clinic_billing()
        raise UserError(_("No billing document is linked."))

    def cron_send_session_reminders(self):
        return True
