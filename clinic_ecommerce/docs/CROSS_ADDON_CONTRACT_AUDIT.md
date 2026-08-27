# Cross-Addon Contract Audit

Authoritative source: latest ClinicOne bundle supplied by the user on
2026-08-20/21.

## Baseline

- `clinic_reports`: 19.0.1.0.0
- `clinic_dashboard`: 19.0.1.0.0
- `clinic_ecommerce`: absent in baseline → addon 30 is a new owner.

## Odoo 19 Website Sale contract

Native Odoo remains the commercial owner:
- `website._create_cart()` creates/returns the native `sale.order` cart;
- `sale.order._cart_add()` remains the cart mutation entry point;
- `_cart_find_product_line()` is extended only to prevent semantically distinct
  Clinic offerings/schedules/Branches from merging;
- `_prepare_order_line_values()` adds Clinic provenance to native Sales Lines;
- `_verify_updated_quantity()` enforces Catalog min/max/single-quantity policy;
- `payment.transaction._post_process()` calls `super()` first, then Clinic
  fulfillment only for completed payment transactions.

No replacement checkout or payment transaction model is created.

## Treatment contracts

Owner addon: `clinic_treatment_catalog`.

Consumed source:
- `clinic.treatment`
- `clinic.treatment.bundle`

Treatment online readiness uses owner fields/methods:
- `active`
- `allow_online_booking`
- delegated catalog validity
- `duration_minutes`
- `get_service_product()`

Treatment Bundle uses:
- `active`
- `allow_online_sale`
- `is_currently_valid`
- `get_service_product()`

Fulfillment:
- Treatment → Draft `booking.booking` handoff.
- Treatment Bundle → native Odoo Sale lifecycle; no invented bundle entitlement.

## Booking contract

Owner addon: `clinic_booking` 19.0.1.0.1.

Dashboard/eCommerce does not override Booking workflow. For Treatment sales,
fulfillment creates a Draft `booking.booking` only after staff provides an
exact `booking_start_datetime`.

Owner-required fields are respected:
- company;
- patient Contact;
- Treatment;
- exact start/end;
- optional Doctor/Room.

`action_confirm()` is **not** automatically called by eCommerce. Booking
availability/overlap/confirmation remains the owner-module responsibility.

## Package contract

Owner addon: `clinic_package` 19.0.3.0.0.

Source sale product:
- `clinic.package.product_template_id` → Product Variant.

Fulfillment creates owner model `clinic.package.allocation` with:
- Package;
- Clinic Patient;
- Partner;
- Branch;
- Sales Order;
- quantity;
- eCommerce provenance.

Optional auto-activation calls the existing owner `action_activate()` only.

## Membership contract

Owner addon: `clinic_membership` 19.0.3.0.5.

Source:
- Active `membership.plan`
- plan `product_id`

Fulfillment creates a Draft `membership.contract`.

Critical anti-duplication rule:
`membership.contract.action_confirm()` is **not called automatically**, because
that owner workflow can create a Membership invoice. Odoo Website Sale already
owns the commercial invoice. When a paid Odoo Sales invoice exists, eCommerce
may link that existing invoice to `membership.contract.invoice_id` before the
owner `action_activate()` is optionally invoked.

Default:
- `clinic_ecommerce_auto_activate_membership = False`.

## Patient contract

Owner addon: `clinic_patient` 19.0.1.0.0.

Patient resolution uses active `clinic.patient` linked to the signed-in Contact
or commercial Contact in the selected company. The storefront never creates a
Patient card automatically.

## Branch contract

Owner addon: `clinic_branch` 19.0.1.0.0.

Backend enforces:
- Branch belongs to company;
- `res.company.policy_branch_scope_ecommerce`;
- optional one-Branch-per-cart policy;
- no silent Branch fallback if policy disables scoping.

## Reports and Dashboard preservation

`clinic_reports` remains the normalized reporting owner.
`clinic_dashboard` remains its presentation/consumer layer.
`clinic_ecommerce` does not redefine KPI formulas or Dashboard models.

## Cancellation/refund governance

Completed Clinic fulfillment artifacts are never automatically reversed by a
Sales Order cancellation. They transition to `reversal_required` and require
an operator/manager to resolve in the owner module.

Pre-completion fulfillment evidence may be cancelled. Historical fulfillment
records cannot be deleted.

## Result

- duplicated Odoo checkout/payment lifecycle: 0
- duplicated Treatment/Booking/Package/Membership owner models: 0
- duplicate Membership invoice creation by eCommerce: 0
- source workflow replacement: 0
- silent Branch policy bypass: 0
- future addon dependency: 0
