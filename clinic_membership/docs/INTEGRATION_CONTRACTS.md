

# Integration Contracts
- Hard upstream ClinicOne contracts: patient, doctor, treatment catalog, booking, encounter, eMAR, care plan, package, referral and treatment session.
- `clinic_billing`, `clinic_ar`, and `clinic_wallet` are deliberately NOT dependencies. This keeps Membership before Billing and prevents cycles.
- Membership owns canonical `res.partner.membership_reference` and `membership_level_key`, which existing Billing can consume as soft hints.
- Downstream side effects are announced through `membership.integration.event`.
- Cross-addon form decorations use runtime-safe `env.ref(..., raise_if_not_found=False)` bridges rather than hard inherited view XML IDs.

