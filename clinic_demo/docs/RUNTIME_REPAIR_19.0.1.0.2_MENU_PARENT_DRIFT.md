




# Runtime Repair 19.0.1.0.2 — Demo Menu Parent XML-ID Drift

## Runtime evidence

Odoo upgrade failed while parsing `views/demo_menus.xml` because:

`clinic_patient.menu_patient_configuration`

exists in the latest ClinicOne source, but the installed database did not contain
that external ID.

## Root cause

The Prompt-07 menu used a hard external parent reference at XML load time. The
source contract was valid, but the database's `ir.model.data` layout lagged that
source. This is a source/database external-ID drift problem, not a missing
ClinicOne business dependency.

## Compatible repair

1. `menu_demo_dataset` is now load-time parentless.
2. `data/demo_menu_bridge.xml` runs after the local menus load.
3. `DemoMenuBridgeService` tries, in order:
   - exact `clinic_patient.menu_patient_configuration`;
   - matching `clinic_patient` `ir.model.data`;
   - a Configuration child below the ClinicOne root;
   - ClinicOne root itself;
   - parentless top-level fallback.
4. No hard external parent can abort `clinic_demo` upgrade.
5. The existing Prompt-07 Control Center, security, Safe Mode, identity,
   reset-policy and Golden Journey behavior is preserved.

Authoritative repair source SHA-256: `d8ddf19e0b17e706791d2a7c31a0aeacd038a52f717832e8ca1eee32b939caa7`
























