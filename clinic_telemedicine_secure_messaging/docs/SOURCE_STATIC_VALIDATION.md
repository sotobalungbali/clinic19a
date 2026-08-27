# Source / Static Validation and Runtime Acceptance

## Mandatory source/static checks

- parse every Python file;
- resolve class-load imports for decorators/base expressions;
- parse every XML/QWeb file;
- validate every manifest data/asset path;
- reject numeric-prefix backup files;
- verify latest baseline has frozen `clinic_marketing 19.0.1.0.1`;
- verify latest bundle contains failed addon-33 baseline 19.0.1.0.0;
- verify repair target is 19.0.1.0.1;
- reject runtime-failed `clinic_patient.view_clinic_patient_form` integration;
- require stable native `base.view_partner_form` for Patient Contact smart navigation;
- verify live Staff/Doctor/Patient/Appointment/Booking/Queue/Encounter/Consent/Portal contracts;
- verify exact historical `clinic.telemedicine.thread` + `handler_id`;
- verify every owned model has Search/List/Form;
- verify Search roots/direct groups follow ClinicOne Odoo 19 contract;
- reject non-searchable computed fields in Search domains;
- reject `<tree>`, `attrs=`, and `states=`;
- validate object-button methods;
- validate nested One2many model switching;
- verify Odoo 19 `models.Constraint`/`models.Index`;
- execute HARD GATE 11 database identifier/ORM naming checks;
- verify no Portal/Public backend ACL;
- verify every patient detail route intersects browser ID with exact patient/company domain;
- reject `commercial_partner_id` from clinical portal scope;
- verify explicit portal feature grants default False;
- verify secure messages are not copied to generic chatter/email;
- verify file allowlist/size/checksum/download controls;
- verify HTTPS meeting URL validation;
- verify no future-addon dependency.

## Runtime acceptance

1. Activate `clinic_telemedicine_secure_messaging`.
2. Open Telemedicine Settings.
3. Verify Provider Mode defaults to Manual HTTPS URL.
4. Verify Patient Portal Telemedicine and Messaging grants default False.
5. Grant both features to one Active Patient Portal Profile.
6. Confirm another patient still has no access.
7. Create a Telemedicine-enabled Appointment.
8. Create a Session from Appointment.
9. Verify the same source cannot create a duplicate Session.
10. Create/reuse the same Session from linked Booking.
11. Verify Booking/Appointment states are unchanged.
12. Test Doctor with `telemedicine_enabled=False` is blocked.
13. Test branch policy disablement blocks branch-scoped readiness.
14. Test optional signed Consent requirement.
15. Schedule Session.
16. Confirm historical Staff Thread integration count becomes live.
17. Provide valid HTTPS meeting URL.
18. Verify HTTP/non-host Meeting URL is rejected.
19. Mark Session Ready.
20. Login as exact patient and open `/my`.
21. Verify Teleconsultation and Secure Message portal cards.
22. Verify patient Session list.
23. Verify another patient's Session ID returns 404/403.
24. Verify Join before early window is blocked.
25. Verify Join in authorized window redirects only to validated HTTPS URL.
26. Verify patient join timestamp is recorded.
27. Start/Complete Session as Clinician.
28. Verify patient cannot join after state completion.
29. Open patient Secure Messages.
30. Verify another patient's Thread ID returns 404/403.
31. Start a patient-created Thread with an enabled Doctor.
32. Verify maximum open patient Thread ceiling.
33. Send patient text.
34. Verify immutable Message evidence.
35. Send clinician response.
36. Verify first-response SLA timestamp/minutes.
37. Reopen Thread and confirm patient read evidence.
38. Upload PDF.
39. Upload JPEG.
40. Upload PNG.
41. Reject unsupported executable/document types.
42. Reject a file above the configured size ceiling.
43. Verify SHA-256 is stored.
44. Verify another patient cannot download the Attachment ID.
45. Verify authorized patient can download it.
46. Verify response is no-store/no-cache/nosniff.
47. Verify Message/Attachment normal business edit/delete is blocked.
48. Close Thread and verify patient reply is blocked.
49. Reopen as Clinician.
50. Archive as Manager and verify patient access is removed.
51. Verify Telemedicine User is read-only.
52. Verify Clinician can operate Sessions/Threads but cannot delete evidence.
53. Verify Manager workflow authority.
54. Verify company isolation across all four owned models.
55. Verify no patient/Public backend ACL exists.
56. Verify no Secure Message body appears in generic chatter/email.
57. Verify provider-hook mode without an installed provider does not claim success.
58. Verify Queue link opens the correct Session.
59. Verify Encounter link remains navigation only.
60. Run representative multi-company patient isolation tests.

Until all runtime checks succeed:

**ODOO RUNTIME = PENDING**.

