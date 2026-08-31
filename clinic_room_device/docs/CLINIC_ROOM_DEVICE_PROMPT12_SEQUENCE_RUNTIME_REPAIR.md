# Prompt 12 Sequence Runtime Repair — clinic_room_device 19.0.1.0.1

Runtime evidence on 30 Aug 2026 showed `resources.rooms_devices` stopped in its
fail-fast preflight because the installed database did not contain the owner
sequences `clinic.device.code` and `clinic.room.device.assignment`.

The authoritative source already declares both sequences in
`data/clinic_room_device_sequence.xml` and the manifest loads that file. This
repair therefore does **not** invent replacement numbering and does not bypass the
preflight. The owner addon version is bumped to `19.0.1.0.1` so a normal Odoo
module upgrade reloads the source-owned sequence data into the database.

Guardrail additions verify:
- the repair version;
- the sequence data file remains manifest-loaded;
- the four source-owned sequence XML IDs remain present;
- the expected sequence codes remain present.

No workflow, room/device model, ACL, record rule, or business method is changed.

Authoritative snapshot SHA-256: `03d244d5c894e69188731687aaf62cae6e586db9dc862c90235036f6da592cad`
