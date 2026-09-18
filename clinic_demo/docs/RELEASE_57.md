# clinic_demo 19.0.1.0.57 — advanced clinical resolver actor contract

Latest source: clinic19a(20260916-095922).md, SHA-256 3b3f89fcf29667651849539fbc5f17fe0d46f7cc03f6e460995847ecd2b4e0d0. This composite is byte-identical to the earlier 085403 attachment; installed baseline is .56. Latest supplied log and prompt were retained as inputs.

## Correction

The generic journey inspector already selected functional readers, but AdvancedClinicalBase._resolve still defaulted to the Control Center caller when its validators and prerequisite checks omitted record_user. Thus eMAR order validation failed even though the business data existed and the creation path used the prescriber. The same pattern existed in imaging, care/post-care and telemedicine validation.

The shared advanced resolver now selects the declared functional reader from verified run provenance before resolving a restricted business record. It reuses journey_read_context, preserves explicit record_user, preserves missing_ok/model validation, and applies run company plus allowed_company_ids and disabled bulk prefetch to actor-bound records. This covers all four advanced generators and their prerequisite lookups, not just the reported order.state access. ACLs and record rules remain enforced; no sudo, group expansion, ACL retry, sequence mutation or deletion is introduced.

Read contracts: eMAR Order/Prescription -> demo prescriber; Administration -> demo nurse; medication profile/schedule/post-care -> demo manager; imaging/care/telemedicine -> their existing declared actors. Missing or invalid actor provenance remains blocked with evidence.

## Upgrade / resume

Stop Odoo, replace clinic_demo entirely, restart and upgrade clinic_demo to 19.0.1.0.57. Companion addons stay unchanged. Open the SAME Demo Run, Refresh Compatibility, then Reconcile Existing Dataset. Inspect Journey Progress. If eMAR is PASS, use Execute Next / Resume to continue automatically from the first remaining journey. If eMAR remains incomplete, open its Details and inspect the specific diagnosis. No Reset and no manual role changes are required for this correction. Actual records determine PASS counts; 40/40 is not claimed.

## Validation

219 source/behavior tests PASS. New tests execute the actual eMAR validator/resolver with actor-enforcing record doubles: Order reads as prescriber and Administration as nurse; prerequisite profile selects manager; explicit actors and missing-reference handling remain intact. This is not a native Odoo database test.

clinic_demo and five advanced owner guardrails PASS: eMAR, Imaging, Care Plan, Post-Care, Consent. Telemedicine source guardrail reports two absent baseline assets (static/src/img/chat.svg and video.svg) in the uploaded composite. Those assets are unrelated to this Python ACL correction and no Telemedicine addon is included or modified. Its guardrail is NOT reported as PASS. Raw evidence is in evidence_57. Composite parses 930 Python and 517 XML with no parse error. Native Odoo runtime remains pending; L1–L8 population completion remains separate.

The 40-journey registry, historical data and deterministic identities are retained. Build lineage explicitly accepts .56. The latest modelbymodel prompt remains the governing execution/migration authority in GOVERNING_MODEL_BY_MODEL.md.




