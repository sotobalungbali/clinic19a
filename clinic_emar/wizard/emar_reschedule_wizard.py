# -*- coding: utf-8 -*-
"""Enterprise reschedule wizard with upgrade-window vacuum resilience."""

import logging

from psycopg2.errors import UndefinedTable

from odoo import api, fields, models, _
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class ClinicEmarRescheduleWizard(models.TransientModel):
    _name = "clinic.emar.reschedule.wizard"
    _description = "Reschedule eMAR Administration"

    schedule_id = fields.Many2one(
        "clinic.emar.schedule",
        required=True,
        readonly=True,
    )
    current_datetime = fields.Datetime(
        related="schedule_id.planned_datetime",
        readonly=True,
    )
    new_datetime = fields.Datetime(required=True)
    reason = fields.Char(required=True)

    @api.autovacuum
    def _transient_vacuum(self):
        """Keep global autovacuum alive during a source/schema transition.

        Odoo calls transient-model vacuum jobs independently from the eMAR UI.
        If source 19.0.3 is copied while the module upgrade has not yet created
        this table, a normal TransientModel vacuum would execute SQL against a
        missing table.  The savepoint contains that *temporary upgrade-window*
        condition.  Once the table exists, the standard Odoo vacuum path runs
        unchanged.
        """
        try:
            with self.env.cr.savepoint():
                return super()._transient_vacuum()
        except UndefinedTable:
            _logger.warning(
                "[clinic_emar] Skipping transient vacuum because table %s does "
                "not exist yet. Upgrade clinic_emar to synchronize the schema.",
                self._table,
            )
            return self._name, False

    def action_reschedule(self):
        self.ensure_one()
        if not self.new_datetime:
            raise UserError(_("Enter the new administration date/time."))
        if self.new_datetime == self.current_datetime:
            raise UserError(
                _(
                    "The new administration date/time must differ from the "
                    "current schedule."
                )
            )
        return self.schedule_id.action_reschedule(
            self.new_datetime,
            self.reason,
        )

