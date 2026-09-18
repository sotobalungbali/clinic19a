




# Runtime Repair 19.0.1.0.12 — Membership ACL Database Drift

## Runtime evidence

After the functional-actor repair, `master.catalog` and `master.consent` progressed,
but `master.commercial` failed creating `membership.plan` with Odoo reporting that
no group currently allowed create.

## Root cause

The latest `clinic_membership` source already declares Membership Manager create
ACL for `membership.plan` and `membership.plan.benefit`, and its manifest loads the
ACL CSV. The runtime message therefore identifies installed-database ACL drift rather
than a missing functional group assignment.

## Repair contract

- requires `clinic_membership 19.0.3.0.6`;
- Prompt-11 commercial preflight checks actual create access for every directly
  created restricted commercial master under the Demo Clinic Manager actor;
- no `sudo()`, direct SQL, ACL bypass, or workflow rewrite;
- a failed `master.commercial` checkpoint can adopt the repair build only when its
  savepoint left no `master.commercial` references committed.
























