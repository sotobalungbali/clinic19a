# PROJECT IDENTITY PREFLIGHT — HARD GATE 0

- Project: ClinicOne, Odoo 19 CE.
- Addon: `clinic_branch`, development order #36 of the official 39-addon plan.
- Authoritative implementation baseline: `clinic19a(20260821-082452).md`.
- Functional mandate: multi-branch and franchise management with separate data segregation.
- Backup policy: any source basename beginning with `0` is ignored.
- Upgrade posture: preserve existing `clinic.branch`, `clinic.branch.location`, `res.users.allowed_branch_ids`,
  `res.users.working_branch_id`, and `res.company.default_branch_id` contracts because downstream ClinicOne addons
  already consume them.
