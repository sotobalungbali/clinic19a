# ClinicOne eCommerce

Version **19.0.1.0.0** — official ClinicOne addon **30 of 39**.

This addon is an enterprise integration/orchestration layer on Odoo 19
`website_sale`; it is **not** a replacement cart, checkout, payment, invoicing,
Booking, Package, or Membership engine.

Built-in governed offering types:

1. Treatment → Booking handoff after schedule input.
2. Treatment Bundle → native Odoo Sale handoff.
3. Package → Clinic Package Allocation handoff.
4. Membership → Membership Contract handoff without duplicate membership invoice creation.
5. Generic Product → native Odoo Sale/stock handoff.

Runtime status remains **PENDING** until installation plus website/cart/payment
smoke tests pass on the target Odoo 19 CE database.
