# -*- coding: utf-8 -*-
from odoo import fields, models


class ClinicApiEventType(models.Model):
    _name = "clinic.api.event.type"
    _description = "Clinic Integration Event Type"
    _order = "code, id"

    _code_unique = models.Constraint("UNIQUE(code)", "Integration event type code must be unique.")

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    description = fields.Text()
