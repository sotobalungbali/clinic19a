# HARD GATE 4 - Full Structural Inventory

## Owned persistent models

### 1. `clinic.telemedicine.session`

Teleconsultation lifecycle:
Draft -> Scheduled -> Ready -> In Progress -> Completed

Terminal:
Cancelled / No Show

Includes:
- exact Patient/Doctor/company/branch;
- Booking/Appointment/Encounter/Consent provenance;
- provider-neutral HTTPS Meeting URL;
- patient/host join evidence;
- configured patient join window;
- Secure Thread;
- Telemedicine Queue reverse relation.

### 2. `clinic.telemedicine.thread`

Historical Staff-compatible secure conversation scope:
- exact `handler_id -> clinic.staff`;
- Patient/Doctor/company/branch;
- optional Session;
- Open / Closed / Archived;
- Routine / Priority / Urgent;
- patient reply/upload grants;
- attention flag;
- internal note hidden from patient portal;
- stored message/file/unread metrics;
- first-response SLA evidence.

### 3. `clinic.telemedicine.message`

Immutable plain-text communication evidence:
- exact Thread/Patient/Doctor;
- server-owned author identity;
- Patient / Doctor / Staff / System author kind;
- direction;
- sent timestamp;
- controlled patient/clinic read evidence;
- Attachment relation.

### 4. `clinic.telemedicine.attachment`

Immutable secure file evidence:
- exact Thread + Message;
- PDF/JPEG/PNG allowlist;
- MIME + extension validation;
- company size ceiling;
- SHA-256 checksum;
- uploader identity;
- custom controlled download route.

## Additive inherited models

- `res.company`
- `res.config.settings`
- `clinic.portal.profile`
- `clinic.staff`
- `clinic.doctor`
- `clinic.patient`
- `clinic.appointment`
- `booking.booking`
- `clinic.queue`
- `clinic.encounter`

## Controllers

Authenticated Patient Portal routes for:
- Teleconsultation list/detail/join;
- Secure Thread list/new/detail/send;
- secure attachment download.

## UI

Every owned model:
- Search
- List
- Form

Additional:
- Session Kanban
- Thread Kanban
- alternate Portal Access Search/List/Form
- Settings
- Booking/Patient source-owner smart/action buttons
- statusbars
- smart buttons
- body buttons
- One2many row actions.

