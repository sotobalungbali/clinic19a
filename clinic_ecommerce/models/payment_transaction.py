from odoo import models


class PaymentTransaction(models.Model):
    """Run Clinic fulfillment only after Odoo Sale finishes its own payment post-processing."""

    _inherit = "payment.transaction"

    # Always let Odoo finish Sale/payment post-processing first; Clinic fulfillment is strictly downstream.
    def _post_process(self):
        result = super()._post_process()
        for transaction in self.filtered(lambda tx: tx.state == "done"):
            if transaction.operation == "validation":
                continue
            orders = transaction.sale_order_ids.sudo().filtered(
                lambda order: order.state in ("sale", "done")
                and order.clinic_ecommerce_line_count
            )
            if orders:
                orders._clinic_ecommerce_process_fulfillments(
                    trigger="payment_done"
                )
        return result
