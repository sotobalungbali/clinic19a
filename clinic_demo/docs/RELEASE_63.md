# clinic_demo 19.0.1.0.63 — Complete window action contracts

Corrects the v62 follow-up window action causing browser _preprocessAction to
attempt map on an undefined views array. The nested notification action must carry
its explicit views, rather than depending on top-level server normalization.

All 14 inline window actions in clinic_demo models now include views consistent
with view_mode: [(False, 'form')] or [(False, 'list'), (False, 'form')]. This covers
Validate follow-up, Acceptance Results, Journey Progress, detail navigation,
reference drill-down, reset wizard and child-list actions. Record IDs, domains,
permissions and targets remain the existing contracts.

No data reset, workflow replay, ACL relaxation, population threshold change or
manual commit is included. Explicit v62 source lineage supports same-run adoption.

Install: replace full clinic_demo folder; restart Odoo; Update Apps List; upgrade
clinic_demo to 19.0.1.0.63. Open the same run, Refresh Compatibility, Validate.
The notification then reopens the same Demo Run with refreshed evidence. Inspect
Acceptance Results or Reporting Sufficiency. An Insufficient result still means
population expansion is needed, not that this navigation repair failed.

Validation: 242 source/record-double tests and clinic_demo guardrail pass.
Added regression coverage checks every inline window action and executes both
success/failure notification branches, including exact run navigation.
Native Odoo/browser runtime unavailable here; runtime acceptance remains pending.













