# Source / Static Validation and Runtime Acceptance

## Required source/static gates

- parse every Python file;
- parse every XML/QWeb file;
- verify every manifest data and asset path;
- ignore basename files beginning with numeric `0`;
- verify latest baseline contains `clinic_dashboard 19.0.1.0.0`;
- verify `clinic_ecommerce` is absent from baseline;
- validate live-import upstream source fields/methods;
- validate Odoo 19 Website Sale cart override signatures;
- validate payment post-process integration calls `super()` first;
- validate no custom checkout/payment replacement;
- validate Treatment/Booking/Package/Membership ownership boundaries;
- validate no Membership duplicate-invoice workflow call;
- validate Branch policy and one-Branch cart guardrails;
- validate public storefront uses narrow published-item sudo queries and no public backend ACL;
- validate Search/List/Form for all owned persistent models;
- validate no legacy `<tree>`, `attrs=`, `states=`;
- validate Odoo 19 `res.groups.privilege` hierarchy;
- validate no future addon dependency;
- validate source/static status remains distinct from runtime completion.

## Runtime acceptance

1. Activate `clinic_ecommerce` on Odoo 19 CE.
2. Open Settings and select Default Website.
3. Run Discover Offerings.
4. Verify Draft Catalog Items are created without duplicate mappings.
5. Review and publish one Treatment offering.
6. Verify `/clinic/shop` displays only Published records for the current Website/company.
7. Test anonymous access against a sign-in-required Treatment.
8. Test signed-in Contact without Patient card.
9. Test signed-in Contact with valid Patient card.
10. Test Branch-required offering.
11. Disable `policy_branch_scope_ecommerce` and verify Branch cannot be forced.
12. Test required terms checkbox.
13. Test Treatment Preferred Date and Time Window.
14. Add to native Odoo cart.
15. Verify Clinic provenance fields on `sale.order.line`.
16. Verify semantically different Branch/date/time lines do not merge.
17. Test single/min/max quantity enforcement.
18. Complete native Odoo checkout/payment.
19. Verify the configured fulfillment trigger runs.
20. Treatment: verify Fulfillment waits for exact staff Booking start.
21. Assign exact Booking start and process.
22. Verify Draft Booking created and not auto-confirmed.
23. Package: verify Allocation owner model is created and linked to Sale Order.
24. Membership: verify Draft Contract is created without calling owner invoice-creating confirmation.
25. Verify a paid native Sale invoice can be reused as Contract `invoice_id`.
26. Test Membership auto-activation only when explicitly enabled and owner payment gate passes.
27. Test Treatment Bundle/native-sale handling.
28. Cancel an Order before fulfillment completion.
29. Cancel an Order after completed Clinic artifact; verify `reversal_required` rather than silent reverse.
30. Verify Fulfillment records cannot be deleted.
31. Verify eCommerce User cannot modify Catalog publication or process Fulfillment.
32. Verify Operator can process Fulfillment but not publish Catalog.
33. Verify Manager can publish Catalog.
34. Verify company record isolation.
35. Verify native `/shop` publication remains off unless explicitly enabled.
36. Verify no upstream owner transaction is simplified/replaced by eCommerce.

Until runtime acceptance succeeds:

**ODOO RUNTIME = PENDING**.
