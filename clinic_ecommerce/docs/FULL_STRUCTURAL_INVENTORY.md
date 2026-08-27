# HARD GATE 4 — Full Structural Inventory

## Owned persistent models

### 1. `clinic.ecommerce.catalog.item`

Governed online representation of exactly one source offering.

Capabilities:
- Treatment / Treatment Bundle / Package / Membership / Product mapping;
- Website and company scope;
- optional default Branch;
- publication workflow Draft → In Review → Published → Archived;
- public content and disclaimer;
- sign-in / Patient / Branch / schedule / terms guardrails;
- quantity policy;
- optional native `/shop` publication;
- Sales Order and Fulfillment provenance.

### 2. `clinic.ecommerce.fulfillment`

Immutable handoff/audit model per Clinic Sales Order Line.

Capabilities:
- pending/waiting/ready/processing/done/error/reversal-required/cancelled states;
- patient/Branch/schedule context;
- Booking, Package Allocation and Membership Contract provenance;
- operator retry and manual reversal governance;
- attempt/error/outcome audit.

## Transient model

`clinic.ecommerce.catalog.discovery.wizard`

Idempotently discovers eligible source Treatment, Bundle, Package and
Membership offerings and creates missing Draft Catalog mappings.

## Additive inherited models

- `sale.order`
- `sale.order.line`
- `payment.transaction`
- `res.company`
- `res.config.settings`
- `booking.booking`
- `clinic.package.allocation`
- `membership.contract`
- `clinic.branch`
- `product.template`

## HTTP storefront

Routes:
- GET `/clinic/shop`
- GET `/clinic/shop/item/<id>`
- POST `/clinic/shop/add/<id>`

The custom Clinic storefront ends at native Odoo cart insertion. Standard
Odoo `/shop/cart`, checkout, payment and Sales lifecycle continue afterward.

## Security

Groups:
1. eCommerce User
2. eCommerce Operator
3. eCommerce Manager

Public website users receive no backend model ACL.

## Data

Sequences:
- Clinic eCommerce Catalog Item
- Clinic eCommerce Fulfillment
