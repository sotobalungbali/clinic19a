from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    ap_approval_threshold = fields.Monetary(
        string="AP Approval Threshold",
        currency_field="currency_id",
        default=0.0,
    )
    ap_enforce_receipt_before_post = fields.Boolean(
        string="Require Receipt Before AP Posting",
        default=True,
    )
    ap_qty_tolerance_percent = fields.Float(string="AP Quantity Tolerance (%)", default=0.0)
    ap_price_tolerance_percent = fields.Float(string="AP Price Tolerance (%)", default=0.0)
    ap_default_purchase_journal_id = fields.Many2one(
        "account.journal",
        string="Default AP Purchase Journal",
        check_company=True,
        domain="[('type', 'in', ('purchase', 'general'))]",
    )
    ap_default_payment_journal_id = fields.Many2one(
        "account.journal",
        string="Default AP Payment Journal",
        check_company=True,
        domain="[('type', 'in', ('bank', 'cash', 'credit'))]",
    )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ap_approval_threshold = fields.Monetary(related="company_id.ap_approval_threshold", readonly=False)
    ap_enforce_receipt_before_post = fields.Boolean(related="company_id.ap_enforce_receipt_before_post", readonly=False)
    ap_qty_tolerance_percent = fields.Float(related="company_id.ap_qty_tolerance_percent", readonly=False)
    ap_price_tolerance_percent = fields.Float(related="company_id.ap_price_tolerance_percent", readonly=False)
    ap_default_purchase_journal_id = fields.Many2one(related="company_id.ap_default_purchase_journal_id", readonly=False)
    ap_default_payment_journal_id = fields.Many2one(related="company_id.ap_default_payment_journal_id", readonly=False)
