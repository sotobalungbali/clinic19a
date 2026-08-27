# HARD GATE 4 - Full Structural Inventory

## Owned persistent models

1. `clinic.insurance.plan`
   - payer plan master;
   - default authorization/coverage/copay/deductible/annual limit;
   - settlement-journal preference;
   - service benefit rules.

2. `clinic.insurance.plan.rule`
   - treatment/procedure/product coverage rule;
   - authorization requirement;
   - coverage/copay/deductible;
   - payer amount / quantity limits.

3. `clinic.insurance.policy`
   - patient Policy;
   - member/group/policy identifiers;
   - coverage window;
   - verification and lifecycle;
   - annual benefit snapshot;
   - Eligibility/Authorization/Claim links.

4. `clinic.insurance.eligibility.check`
   - persistent eligibility evidence;
   - internal/payer verification method;
   - eligible/ineligible/error/expiry evidence.

5. `clinic.insurance.authorization`
   - payer pre-authorization request;
   - Booking/Appointment/Encounter/Treatment/Billing sources;
   - submitted/pending/approved/partial/rejected workflow;
   - claim creation orchestration.

6. `clinic.insurance.authorization.line`
   - requested services;
   - benefit rule;
   - requested/approved amount;
   - insurer/patient responsibility.

## Abstract support

- `clinic.insurance.company.mixin`

## Frozen Billing-owned models extended, not owned

- `clinic.insurance.claim`
- `clinic.insurance.claim.line`

Extensions include:
- Policy;
- Authorization;
- Eligibility evidence;
- payer adjudication metadata;
- Authorization service-line linkage;
- Claim-vs-Authorization variance;
- governed permission checks.

## Other inherited models

- `res.partner`
- `clinic.patient`
- `booking.booking`
- `clinic.appointment`
- `clinic.treatment`
- `clinic.encounter`
- `clinic.billing.invoice`
- `res.company`
- `res.config.settings`

## Services

- 3 sequences;
- 3 daily expiry crons;
- Authorization PDF;
- Claim Evidence PDF;
- 4-level Insurance privilege hierarchy;
- 6 company record rules;
- 78 runtime regression/contract tests;
- Enterprise Development Guardrail.

