# Source / Static Validation and Runtime Acceptance

## Required source/static gates

- parse all Python;
- parse all XML/QWeb;
- verify every manifest data/asset file;
- ignore numeric-prefix backup files;
- verify `clinic_ecommerce 19.0.1.0.0` latest baseline;
- verify `clinic_portal` absent from baseline;
- verify embedded official specification responsibility;
- inspect live-import Patient/Booking/Billing/Encounter contracts;
- validate native Odoo 19 `portal.wizard` integration;
- validate every browser ID is intersected with exact patient/company domain;
- validate no commercial-partner clinical family domain;
- validate no public/portal backend ACL to `clinic.portal.profile`;
- validate Search/List/Form matrix;
- validate Odoo 19 Search architecture;
- validate no `<tree>`, legacy `attrs=`, legacy `states=`;
- validate `models.Constraint` / `models.Index`;
- run HARD GATE 11 database identifier/ORM naming safety;
- validate no future addon dependency;
- validate treatment page does not expose SOAP/diagnosis/vitals fields.

## Runtime acceptance

1. Activate `clinic_portal`.
2. Confirm an existing patient Portal User gets exactly one Draft Portal Profile.
3. Confirm a non-patient Portal User gets no Clinic Portal access.
4. Confirm a patient in another company is denied in the current company.
5. Open `/my` and verify My Clinic cards.
6. Open `/my/clinic`.
7. Verify Booking count against exact patient's Booking records.
8. Verify another patient's Booking ID returns 404.
9. Test Booking Upcoming / History / Cancelled filters.
10. Open one Booking detail.
11. Verify no Booking state changes.
12. Verify Clinic Invoice count.
13. Verify another patient's Clinic Billing ID returns 404.
14. Open a Clinic Invoice summary.
15. Follow the linked native invoice URL.
16. Verify invoice PDF/payment remains native Odoo.
17. Verify Treatment History contains `done` Encounters only.
18. Verify another patient's Encounter ID returns 404.
19. Verify completed Procedure Sessions display.
20. Verify SOAP notes/diagnosis/vitals/internal notes are absent.
21. Suspend the Portal Profile and verify `/my/clinic` is unavailable.
22. Reactivate the profile.
23. Disable Booking view and verify Booking routes return 403.
24. Disable Invoice view and verify Invoice routes return 403.
25. Disable Treatment History and verify Treatment routes return 403.
26. Open `/my/clinic-wallet`.
27. Open `/my/consents`.
28. Open `/my/orders`.
29. Open `/clinic/shop`.
30. Verify page-size setting.
31. Verify Portal Operator cannot change profile state.
32. Verify Portal Manager can use native Portal Access Management.
33. Revoke native Portal access and verify Clinic pages are unavailable.
34. Verify company record isolation in backend.
35. Verify external Portal User has no backend ACL to `clinic.portal.profile`.
36. Verify access telemetry updates only `last_access_at/page`.

Until these runtime checks pass:

**ODOO RUNTIME = PENDING**.
