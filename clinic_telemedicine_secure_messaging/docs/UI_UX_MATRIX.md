# HARD GATE 7 - UI/UX Matrix

| Model | Search | List | Form | Statusbar | Additional Enterprise UX |
|---|---|---|---|---|---|
| `clinic.telemedicine.session` | Yes | Yes | Yes | Yes | Kanban, Schedule/Ready/Join/Start/Complete/No Show/Cancel, Patient/Doctor/Thread/Queue/Booking/Appointment/Encounter/Portal smart actions |
| `clinic.telemedicine.thread` | Yes | Yes | Yes | Yes | Kanban, Assign to Me, read evidence, close/reopen/archive, Patient/Doctor/Session/Message/File/Portal smart actions |
| `clinic.telemedicine.message` | Yes | Yes | Yes | N/A | immutable evidence, read action, Thread/File smart navigation |
| `clinic.telemedicine.attachment` | Yes | Yes | Yes | N/A | immutable file evidence, controlled Download, Thread/Message/Patient navigation |

Additional governance:
- `clinic.portal.profile` alternate Telemedicine Access Search/List/Form
- Odoo Settings section
- Booking Create Telemedicine Session action
- Patient Telemedicine/Secure Thread smart navigation

UI buttons never substitute for backend workflow/authorization checks.

