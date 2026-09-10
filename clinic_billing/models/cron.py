# -*- coding: utf-8 -*-
from odoo import api, models


class ClinicBillingCron(models.Model):
    _inherit = "clinic.billing.invoice"

    @api.model
    def _cron_sync_accounting_states(self):
        invoices = self.search([("move_id", "!=", False), ("state", "not in", ("cancelled", "paid"))], limit=1000)
        invoices._sync_state_from_move()
        return True



