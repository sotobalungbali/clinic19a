# HARD GATE 11 - Database Identifier & ORM Naming Safety

Owned Odoo models / default SQL tables:

- `clinic.telemedicine.session` -> `clinic_telemedicine_session`
- `clinic.telemedicine.thread` -> `clinic_telemedicine_thread`
- `clinic.telemedicine.message` -> `clinic_telemedicine_message`
- `clinic.telemedicine.attachment` -> `clinic_telemedicine_attachment`

Executable checks cover:
1. lowercase dotted `_name`;
2. default SQL table identifier <= PostgreSQL 63-byte ceiling;
3. field technical names are safe snake_case and <= 63 bytes;
4. Constraint/Index identifiers stay within safe length;
5. explicit Many2many relation identifiers stay within safe length;
6. no field/method technical-name collision;
7. no list-valued `_inherit` without explicit `_name`;
8. no upstream owner-model shadowing;
9. no unsafe SQL reserved field names;
10. no Odoo recordset proxy used as an `isinstance()` Python type;
11. Python class-load decorator/base symbols resolve their imports;
12. XML field/object-button contracts resolve against the combined live model graph.

The class-load import check is mandatory because ordinary syntax compilation
does not catch a missing symbol such as `@api.model` without importing `api`.

