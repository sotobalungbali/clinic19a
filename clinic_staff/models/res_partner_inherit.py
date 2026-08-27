
from odoo import _, api, fields, models

# TIDAK DIPANGGIL di __init__.py
class ResPartnerInherit(models.Model):
    _inherit = 'res.partner'

    # SUDAH CREATE SAAT Addon clinic_audit 
    # -------------------------------------------------------------------------
    # DOCTOR FLAG & LINKS
    # -------------------------------------------------------------------------
    is_doctor = fields.Boolean(
        string="Is a Doctor",
        help="Enable this to indicate that this contact is a doctor."
    )
