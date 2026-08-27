# -*- coding: utf-8 -*-
from odoo import fields, models


class ClinicApiScope(models.Model):
    """Stable permission vocabulary for API clients.

    Scopes narrow what a configured service user may do. They never grant more
    authority than the Odoo ACLs and record rules of that service user.
    """

    _name = "clinic.api.scope"
    _description = "Clinic API Scope"
    _order = "sequence, code, id"

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "API scope code must be unique.",
    )

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text()
