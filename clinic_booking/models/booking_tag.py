

# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class BookingTag(models.Model):
    _name = "booking.tag"
    _description = "Booking Tag"
    _order = "name"
    _rec_name = "name"

    name = fields.Char(string="Name", required=True, translate=False)
    color = fields.Integer(string="Color Index", help="Color used in kanban/list visual hints.")
    active = fields.Boolean(string="Active", default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
        help="Company that owns this tag."
    )

    _uniq_name_company = models.Constraint(
        'unique(name, company_id)',
        'Tag name must be unique per company.',
    )

    @api.constrains("name")
    def _check_name(self):
        for rec in self:
            if rec.name and not rec.name.strip():
                raise ValidationError(_("Tag name cannot be blank."))
