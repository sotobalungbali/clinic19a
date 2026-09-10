
# Security Model

Roles:
1. Treatment Session User — operational create/write, no delete.
2. Treatment Session Clinician — User plus clinical execution/consumption.
3. Treatment Session Manager — Clinician plus configuration/reset/delete where
   workflow permits.

Backend enforcement includes ACLs, branch/company record rules, Python
workflow guards, stock completion verification and immutable completed-stock
reset protection.
