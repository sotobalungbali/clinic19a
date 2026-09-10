




# Prompt 12 Runtime Repair — Room/Device Sequences

## Runtime evidence
`resources.rooms_devices` failed its own preflight because these source-required
owner sequence codes were absent from the installed database:

- `clinic.device.code`
- `clinic.room.device.assignment`

## Root cause classification
The latest owner source already contains both `ir.sequence` declarations and
manifest-loads `data/clinic_room_device_sequence.xml`. This is therefore treated
as installed-database drift / missing owner data load, not as a reason to bypass
the generator preflight.

## Repair
1. `clinic_room_device` version bump to `19.0.1.0.1` forces normal Odoo upgrade
   loading of the owner sequence XML.
2. `clinic_demo` version `19.0.1.0.13` requires that owner version.
3. The same failed run may adopt the build only when `resources.rooms_devices`
   has no committed demo reference, preserving savepoint/idempotency safety.
4. No manual SQL, `sudo()`, fake sequence, or direct business numbering is added.

Authoritative snapshot SHA-256: `03d244d5c894e69188731687aaf62cae6e586db9dc862c90235036f6da592cad`
Expected suite fingerprint: `17e98031b058cfbf57e3afa6e872a43e949b900265ce38f1109e2cefa9410689`









