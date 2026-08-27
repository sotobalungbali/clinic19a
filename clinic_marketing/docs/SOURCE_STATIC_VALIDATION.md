# Source / Static Validation and Runtime Acceptance

## Source/static gates

- parse every Python file;
- parse every XML file;
- validate manifest data files;
- ignore numeric-prefix backup files;
- verify latest baseline contains `clinic_portal 19.0.1.0.0`;
- verify latest user baseline contains failed `clinic_marketing 19.0.1.0.0`;
- verify repair target is `clinic_marketing 19.0.1.0.1`;
- verify every Python class decorator/base resolves its required imported Odoo symbol;
- verify live-import Patient/Branch/Booking/Membership/Feedback contracts;
- verify Promotion owner-source models/fields;
- verify Odoo Email Marketing extension contracts;
- verify all six owner models Search/List/Form;
- verify Campaign Kanban and Recipient Pivot/Graph;
- verify attribute-free Odoo 19 Search architecture;
- verify no `<tree>`, legacy `attrs=`, legacy `states=`;
- verify no executable `_sql_constraints`;
- verify company rules / Odoo 19 privileges;
- verify Workflow methods cannot be bypassed by UI/RPC;
- execute HARD GATE 11 identifier/ORM naming checks;
- verify no future addon dependency.

## Runtime acceptance

1. Activate `clinic_marketing`.
2. Open Marketing Settings.
3. Verify explicit opt-in defaults to enabled.
4. Create a Patient Marketing Preference.
5. Test Email Opt-In/Opt-Out.
6. Test WhatsApp Opt-In/Opt-Out.
7. Test Do Not Contact and clear it.
8. Verify ordinary Marketing User cannot change consent.
9. Create and activate a Segment.
10. Preview a demographic Segment.
11. Preview a Branch Segment.
12. Disable `policy_branch_scope_marketing` and verify branch Campaign is blocked.
13. Test active-Membership segmentation.
14. Test completed-visit recency segmentation.
15. Test inactivity segmentation.
16. Test latest NPS Promoter/Detractor segmentation.
17. Create an informational Promotion.
18. Create each supported owner-linked Promotion type.
19. Verify source Company mismatches are blocked.
20. Create an Email-only Campaign.
21. Prepare Audience.
22. Verify Recipient snapshot inclusion/exclusion reasons.
23. Verify maximum-audience safety ceiling.
24. Mark Campaign Ready.
25. Verify scope/content is locked.
26. Launch Campaign as Marketing Manager.
27. Verify native `mailing.mailing` is created.
28. Verify mailing target domain matches included Email recipients only.
29. Verify native exclusion list remains enabled.
30. Verify native mailing queues successfully.
31. Send in a test database.
32. Verify `mailing.trace` synchronizes Sent/Open/Reply/Bounce/Error.
33. Create a WhatsApp-only Campaign.
34. Verify only consented numbers receive Messages.
35. Open a manual `wa.me` handoff.
36. Mark sent and verify Campaign evidence.
37. Set transport to Provider Extension Hook without provider and verify no false success.
38. Test a custom provider hook in integration test if available.
39. Verify one WhatsApp provider failure does not abort unrelated queue records.
40. Test mixed Email+WhatsApp Campaign.
41. Verify Campaign completion waits for selected channels.
42. Test Campaign cancellation.
43. Verify native queued Email is cancelled only through native action.
44. Test Promotion auto-expiry.
45. Verify company isolation across all six models.
46. Verify Marketing User cannot launch Campaign.
47. Verify Coordinator cannot bypass Manager Launch.
48. Verify Recipient direct create/write/unlink is rejected.
49. Verify Message direct create/write/unlink is rejected.
50. Verify no Booking/Billing/Membership/eCommerce source records mutate.

Until all runtime checks pass:

**ODOO RUNTIME = PENDING**.

