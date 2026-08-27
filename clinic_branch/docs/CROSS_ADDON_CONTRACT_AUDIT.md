# CROSS-ADDON CONTRACT AUDIT

The latest ClinicOne snapshot already contains downstream modules that refer to:

- model `clinic.branch`
- `res.users.allowed_branch_ids`
- `res.users.working_branch_id`
- `res.company.default_branch_id`
- branch-aware models in accounting, finance, dashboard, ecommerce, feedback, incident,
  package, post-care, quality, reports, staff, telemedicine and other addons.

Therefore this build preserves those contracts and does not rename the branch master,
working-branch contract, or default-branch contract.
