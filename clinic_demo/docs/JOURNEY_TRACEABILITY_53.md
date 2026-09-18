# Model-by-model / bounded-journey traceability — release 53

All 35 existing generator keys and scenario identities are retained. Five source aggregates previously hidden in management.reports are independently executable. Parent/child records stay within their owner aggregate; this is not one transaction per physical table.

MP01–07 remain architecture, scenario/profile, security and Control Center contracts. MP24 executive script remains docs/CLINIC_DEMO_EXECUTIVE_DEMO_SCRIPT.md.

| Order | Journey | Master scope | Owner | Models | Dependencies | Expected identities |
|---|---|---|---|---|---|---|
| 1 | foundation.native | MP-08 | clinic_demo | Native foundation / validation evidence | None | DEMO-BRANCH-* |
| 2 | foundation.organization | MP-08 | clinic_branch | clinic.branch, clinic.branch.location | foundation.native | DEMO-BRANCH-* |
| 3 | workforce.preflight | MP-09 | clinic_demo | Native foundation / validation evidence | foundation.organization | DEMO-DOC-*; DEMO-NUR-*; DEMO-STAFF-* |
| 4 | workforce.staff | MP-09 | base | res.users, res.partner, hr.employee, hr.department, clinic.staff, clinic.practitioner, clinic.skill, clinic.staff.skill, clinic.license.type, clinic.staff.license, clinic.staff.availability, clinic.specialty, clinic.doctor, clinic.schedule.rule | workforce.preflight | DEMO-DOC-*; DEMO-NUR-*; DEMO-STAFF-* |
| 5 | patient.personas | MP-10 | base | res.partner, clinic.patient, clinic.patient.tag, clinic.patient.identifier.type, clinic.patient.identifier, clinic.patient.condition, clinic.patient.allergy | workforce.staff | DEMO-PAT-NEW-*; DEMO-PAT-RET-* |
| 6 | master.catalog | MP-11 | clinic_treatment_catalog | clinic.treatment.category, clinic.treatment, product.template, product.product, clinic.treatment.pricelist, product.pricelist, clinic.treatment.pricelist.item, clinic.care.protocol, clinic.care.protocol.step, clinical.imaging.type, clinical.imaging.protocol, clinical.imaging.type.prep, clinic.emar.medication.profile | patient.personas | DEMO-ENC-001; DEMO-SESSION-001; DEMO-IMG-*; DEMO-EMAR-*; DEMO-CARE-* |
| 7 | master.consent | MP-11 | clinic_encounter | clinic.consent.template, clinic.consent.template.item, clinic.consent.template.version | master.catalog | DEMO-CONSENT-* |
| 8 | master.commercial | MP-11 | clinic_package | clinic.package.policy, clinic.package.pricing, clinic.package, clinic.package.line, clinic.package.integration.event, membership.plan, membership.plan.benefit, membership.integration.event, clinic.insurance.plan, clinic.insurance.plan.rule, clinic.wallet.rule, res.partner, product.template, product.product | master.consent | DEMO-PKG-*; DEMO-MEM-*; DEMO-WALLET-*; DEMO-INS-* |
| 9 | resources.rooms_devices | MP-12 | clinic_room_device | clinic.room.type, clinic.room, clinic.room.availability, clinic.device.category, clinic.device, clinic.room.device.assignment, booking.room, booking.room.schedule, booking.room.blackout, booking.resource, booking.resource.schedule, booking.resource.blackout, booking.doctor.schedule, booking.slot | master.commercial | DEMO-BOOK-TODAY-* |
| 10 | history.patient_longitudinal | MP-13 | clinic_patient | clinic.patient.vital, clinic.patient.condition.episode, clinic.patient.allergy.reaction | resources.rooms_devices | DEMO-PAT-RET-* |
| 11 | operations.referral | MP-14 | clinic_referral | clinic.referral.program, clinic.referral.source, clinic.referral | history.patient_longitudinal | DEMO-REF-001; DEMO-REF-EXC-* |
| 12 | operations.booking | MP-14 | clinic_booking | booking.channel, booking.booking | operations.referral | DEMO-BOOK-HIST-*; DEMO-BOOK-TODAY-*; DEMO-FUT-*; DEMO-REF-001 |
| 13 | operations.queue_triage | MP-15 | clinic_queue_room | clinic.queue.token, clinic.queue, clinic.room.assignment, clinic.triage.level, clinic.triage.session, clinic.vitals.intake | operations.booking | DEMO-QUEUE-*; DEMO-TRIAGE-*; DEMO-TRIAGE-ABN-001 |
| 14 | operations.encounter | MP-16 | clinic_encounter | clinic.encounter.stage, clinic.procedure.category, clinic.procedure.catalog, clinic.encounter, clinic.soap.note, clinic.diagnosis, clinic.encounter.procedure, clinic.postcare.protocol, clinic.postcare.plan | operations.queue_triage | DEMO-ENC-001; DEMO-ENC-RET-* |
| 15 | operations.treatment_session | MP-16 | clinic_treatment_session | clinic.treatment.session, clinic.treatment.session.line | operations.encounter | DEMO-SESSION-001; DEMO-SESSION-EXC-* |
| 16 | clinical.imaging | MP-17 | clinic_imaging | clinical.imaging.device, clinical.imaging | operations.treatment_session | DEMO-IMG-* |
| 17 | clinical.emar | MP-17 | clinic_demo | clinic.emar.prescription, clinic.emar.medication.line, clinic.emar.order, clinic.emar.administration | clinical.imaging | DEMO-EMAR-* |
| 18 | clinical.care_postcare | MP-17 | clinic_consent_legal | clinic.consent.form, clinic.care.plan, clinic.postcare.protocol, clinic.postcare.plan | clinical.emar | DEMO-CARE-* |
| 19 | clinical.telemedicine | MP-17 | clinic_consent_legal | clinic.consent.form, clinic.telemedicine.session, clinic.telemedicine.thread, clinic.telemedicine.message | clinical.care_postcare | DEMO-TELE-* |
| 20 | commercial.billing | MP-18 | clinic_wallet | clinic.billing.invoice, account.move | clinical.telemedicine | DEMO-BILL-* |
| 21 | commercial.ar | MP-18 | clinic_ar | clinic.ar.invoice | commercial.billing | DEMO-AR-* |
| 22 | commercial.ap | MP-18 | base | res.partner, clinic.ap, account.move | commercial.ar | DEMO-AP-* |
| 23 | exception.feedback | MP-19 | clinic_feedback | clinic.feedback.survey, clinic.feedback, clinic.feedback.escalation | commercial.ap | DEMO-FB-* |
| 24 | exception.incident_quality | MP-19 | clinic_quality | clinic.quality.check.template, clinic.quality.check, clinic.incident | exception.feedback | DEMO-INC-*; DEMO-QUAL-* |
| 25 | digital.ecommerce_marketing_portal | MP-19 | clinic_integration_api | clinic.api.event.type, clinic.api.event | exception.incident_quality | DEMO-API-* |
| 26 | operations.future_pipeline | MP-20 | clinic_post_care_followup | clinic.postcare.task | digital.ecommerce_marketing_portal, operations.booking, clinical.telemedicine | DEMO-FUT-* |
| 27 | source.insurance | MP-11/16/18/21 | clinic_insurance_authorization | clinic.insurance.authorization, clinic.insurance.policy, clinic.insurance.authorization.line | operations.future_pipeline | Run-owned FIN-INS source aggregate and children |
| 28 | source.membership | MP-11/16/18/21 | clinic_membership | membership.contract | operations.future_pipeline | Run-owned OPS-MEM source aggregate and children |
| 29 | source.inventory | MP-11/16/18/21 | clinic_inventory | clinic.treatment.product.usage, clinic.treatment.product.usage.line, stock.move, stock.move.line, stock.location, product.product, product.template, product.category | operations.future_pipeline | Run-owned OPS-INV source aggregate and children |
| 30 | source.wallet | MP-11/16/18/21 | clinic_wallet | clinic.wallet.transaction, clinic.wallet, account.move, account.move.line, account.account, account.journal | operations.future_pipeline | Run-owned OPS-WALLET source aggregate and children |
| 31 | source.procedure | MP-11/16/18/21 | clinic_encounter | clinic.procedure.session, clinic.execution.log | operations.future_pipeline | Run-owned CLN-PROC source aggregate and children |
| 32 | management.reports | MP-21 | clinic_reports | clinic.report.run, clinic.report.metric, clinic.report.detail, clinic.insurance.policy, clinic.insurance.authorization, membership.contract, clinic.treatment.product.usage, clinic.wallet, clinic.wallet.transaction, clinic.procedure.session, stock.move, stock.location, product.category, product.product, account.account, account.journal, account.move | operations.future_pipeline, source.insurance, source.membership, source.inventory, source.wallet, source.procedure | DEMO-REPORT-* |
| 33 | management.dashboard | MP-22 | clinic_dashboard | clinic.dashboard.snapshot, clinic.dashboard.snapshot.line | management.reports | DEMO-DASH-* |
| 34 | management.analytics | MP-22 | clinic_analytics | clinic.analytics.snapshot, clinic.analytics.snapshot.line, clinic.analytics.forecast, clinic.analytics.forecast.point, clinic.analytics.insight | management.dashboard | DEMO-ANL-* |
| 35 | validation.structural | MP-23 | clinic_demo | Native foundation / validation evidence | management.analytics | DEMO-ANL-* |
| 36 | validation.temporal | MP-23 | clinic_demo | Native foundation / validation evidence | validation.structural | DEMO-FUT-* |
| 37 | validation.workflow | MP-23 | clinic_demo | Native foundation / validation evidence | validation.temporal | DEMO-ENC-001 |
| 38 | validation.journey_exception | MP-23 | clinic_demo | Native foundation / validation evidence | validation.workflow | DEMO-INC-* |
| 39 | validation.analytics_evidence | MP-23 | clinic_demo | Native foundation / validation evidence | validation.journey_exception | DEMO-DASH-* |
| 40 | validation.integrity_reset_regeneration | MP-23 | clinic_demo | Native foundation / validation evidence | validation.analytics_evidence | DEMO-PAT-RET-* |

Generation and validation callables, model scope, identity, idempotency and reset policies are also stored on each Journey Progress record. Expected minimum counts measure bound provenance, not the full enterprise target population. Golden-reference patterns are scenario identities, not exhaustive per-profile quotas.








