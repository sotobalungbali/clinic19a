# SECURITY MODEL — HARD GATE 10

## Roles

### Referral User

- reads Program and Source masters in allowed scope;
- creates/updates Referral transactions;
- cannot delete Referral transactions;
- company + allowed-branch record rules apply.

### Referral Manager

- inherits Referral User;
- manages Program and Source masters;
- company-wide Referral visibility within allowed companies;
- controls reward completion/rejection and lifecycle reset;
- can delete only Draft or Cancelled Referrals (Python enforcement).

## Backend enforcement

Security does not rely on invisible UI controls:

- ACL controls CRUD surface;
- record rules enforce company/branch scope;
- Python constraints reject cross-company relations;
- Python workflow guards protect manager-only actions;
- converted/expired evidence cannot simply be deleted;
- downstream drill-down executes with the viewer's normal ACL/record rules.
