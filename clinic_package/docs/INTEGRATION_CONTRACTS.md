# Integration Contracts — clinic_package

`clinic_package` owns commercial/entitlement package logic. It does not own clinical medication records.

## Direct upstream contracts

- `clinic_patient`: allocation patient and patient portfolio.
- `clinic_doctor`: responsible/allowed doctors.
- `clinic_treatment_catalog`: treatment/package component matching.
- `clinic_inventory`: product ownership and stock product contract.
- `clinic_booking`: booking-backed redemption.
- `clinic_queue_room` / `clinic_room_device`: visit/room/device restrictions.
- `clinic_care_plan`: multi-session package treatment plan.
- `clinic_emar`: traceable medication order/schedule/administration linkage.
- `sale`, `account`, `stock`: commercial references and package service product.

## eMAR ownership boundary

Package redemption is the entitlement ledger. eMAR remains the clinical owner.

`clinic.package.usage` may store:
- `emar_order_id`
- `emar_schedule_id`
- `emar_administration_id`

The package module validates patient consistency and hierarchy consistency. eMAR models receive non-invasive reverse navigation/count fields only. No medication workflow state is owned or changed by `clinic_package`.

## Downstream soft contract

`clinic.package.integration.event` emits durable events such as package activation, allocation activation/pause/resume/transfer/expiry, usage confirmation/cancellation, and voucher lifecycle. Future billing/finance/portal/API/analytics owners consume these events without creating reverse hard dependencies.
