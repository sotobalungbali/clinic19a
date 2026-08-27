# Odoo 19 Website Sale API Audit

The final addon keeps Odoo Website Sale as the commercial owner.

Verified Odoo 19 contracts used by `clinic_ecommerce`:

- `sale.order._cart_add(product_id, quantity=1.0, *, uom_id=None, **kwargs)`
- `sale.order._cart_find_product_line(product_id, uom_id, ..., **kwargs)`
- `sale.order._prepare_order_line_values(product_id, quantity, uom_id, *, ..., **kwargs)`
- `sale.order._verify_updated_quantity(order_line, product_id, new_qty, uom_id, **kwargs)`
- `website._get_and_cache_current_cart()`
- `website._create_cart()`
- `payment.transaction._post_process()`
- `payment.transaction.sale_order_ids`

ClinicOne metadata is passed through the supported `**kwargs` extension points.
Native Odoo remains authoritative for cart quantity validation, product/UoM
selection, checkout, Sale Order confirmation, payment post-processing, invoice
generation and delivery.

Dashboard/reporting addons are not part of the eCommerce transaction lifecycle.
