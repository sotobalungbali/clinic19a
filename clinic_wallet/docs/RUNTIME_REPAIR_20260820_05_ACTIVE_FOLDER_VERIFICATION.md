# Runtime Repair — Active Folder Verification

Build marker: `CLINIC_WALLET_BUILD_20260820_0500_V19.0.3.0.5`

The user's newest runtime bundle still showed version `19.0.3.0.3` and still
contained:

```xml
ref="clinic_patient.view_partner_form_clinic_patient"
```

therefore the prior replacement had not become the active source read by Odoo.

This build enforces:

```xml
ref="base.view_partner_form"
```

and includes `BUILD_ID.txt` so the active Windows folder can be verified before
Odoo starts.

Before starting Odoo, verify all three:
1. `__manifest__.py` says `19.0.3.0.5`;
2. `views/res_partner_views.xml` says `ref="base.view_partner_form"`;
3. `BUILD_ID.txt` contains `CLINIC_WALLET_BUILD_20260820_0500_V19.0.3.0.5`.

