# ClinicOne Enterprise Demo Dataset (`clinic_demo`)

Odoo 19 Community Edition.

## MASTER PROMPT 06 status

This package is the first installable framework build. It provides deterministic demo
identity, ownership and idempotency foundations without generating ClinicOne business
transactions yet.

### Implemented now

- `clinic.demo.run`
- `clinic.demo.reference`
- `clinic.demo.checkpoint`
- `clinic.demo.log`
- `clinic.demo.validation.result`
- deterministic seed service
- exact ClinicOne source/version compatibility fingerprint
- stable demo-key reference service
- create-or-reuse and missing-record repair foundation
- source-driven reset-policy registry
- ownership-aware reset foundation
- Demo Safe Mode foundation
- checkpoint/logging/validation foundations
- Odoo regression tests
- static Enterprise Guardrail

### Not implemented until later prompts

- enterprise Control Center UI (Prompt 07)
- foundation through management domain generators (Prompts 08–22)
- final full reset/regeneration/validation suite (Prompt 23)
- executive demo script/release hardening (Prompt 24)

No existing ClinicOne addon is patched or replaced by this package.
