
# -*- coding: utf-8 -*-
{
    "name": "ClinicOne Doctor Management & Scheduling",
    "summary": "Doctors, specialties, availability, and appointments. Integrates with ClinicOne suite.",
"description": """
ClinicOne — Doctor Management & Scheduling (Odoo 19 CE)

OVERVIEW
This module centralizes doctor profiles and streamlines end-to-end scheduling in medical aesthetics clinics. It covers professional identity, specialties, working hours, templated schedule rules, materialized availability slots, leaves/exceptions, and a complete appointment lifecycle. The module is lightweight by design and integrates with the broader ClinicOne suite without creating circular dependencies.

KEY CAPABILITIES
- Doctor profiles: license number, issuing authority, seniority levels, specialties, and internal notes.
- Specialties: hierarchical catalog with unique codes and full-path names for fast search.
- Working hours: use Odoo resource calendars to define base schedules per doctor.
- Scheduling engine:
  * Weekly/recurring Schedule Rules → concrete Availability Slots
  * Capacity per slot, lead-time controls, and optional buffers (room integration)
  * Exception handling: leaves/holidays/blackout periods
- Appointment lifecycle:
  * draft → confirmed → checked_in → in_treatment → done
  * terminal branches: canceled / no_show
  * reminders, rescheduling, no-show rules (cron-ready)
- Room-aware planning (via clinic_queue_room): filter by allowed specialties and preferred doctors (added by this module).
- Dashboards & KPIs (via standard views/reports): utilization, lead time, wait time, no-show rate, revenue per doctor/service.
- Portal-ready (optional): patients can book or manage appointments from the portal when enabled.

DATA MODEL (MAIN OBJECTS)
- clinic.doctor — primary doctor model linked to res.partner (identity & communication)
- clinic.specialty — hierarchical specialty catalog with codes and complete_name
- clinic.schedule.rule — weekly templates that generate availability
- clinic.availability.slot — materialized, bookable slots
- clinic.doctor.leave — time-off/blackouts for doctors
- clinic.appointment — room-aware appointment with state machine

INTEGRATIONS
- Required: clinic_queue_room (provides clinic.room; queue/kiosk features optional within that module)
- Optional HR Bridge: clinic_doctor_hr (links clinic.doctor to hr.employee)
  * Auto-create and sync Employee from Doctor
  * Strict HR Mode (optional): every Doctor must have a linked Employee for payroll flows
- Designed to work with the ClinicOne suite (installed as needed):
  clinic_patient, clinic_booking, clinic_treatment, clinic_billing, clinic_ar, clinic_ap,
  clinic_finance, clinic_accounting, clinic_inventory, clinic_ecommerce, clinic_membership,
  clinic_feedback, clinic_reports, clinic_dashboard, clinic_wallet, clinic_package,
  clinic_pricing, clinic_room_device, clinic_portal, clinic_marketing, clinic_l10n_id, clinic_audit.

ARCHITECTURE PRINCIPLES
- No circular dependencies: other modules depend on clinic_doctor; optional features use bridge modules.
- Privacy & access control: doctor data is separated from HR-sensitive fields; HR linkage is optional.
- Multi-company aware: unique constraints (license, codes) are per company; record rules align with company isolation.
- Timezone aware scheduling: relies on Odoo resource calendars and server time for slot computations.

CONFIGURATION (QUICK START)
1) Define specialties.
2) Create doctor contacts (res.partner) and doctor records; assign specialties and license info.
3) Set working hours (resource calendar) and add Schedule Rules.
4) Generate Availability Slots (manually or via cron).
5) (Optional) Install clinic_doctor_hr to auto-create hr.employee; enable Strict HR Mode if all doctors are employees.
6) (Optional) Configure clinic_queue_room for room-aware planning and queue/kiosk workflows.

AUTOMATION
- Scheduled tasks (cron) for slot regeneration, reminders, and no-show marking (with grace period).
- Server actions and mail templates are provided as examples and can be adapted to your policies.

SECURITY & ACCESS
- Suggested roles: Receptionist, Doctor, Clinic Manager, Clinic Admin.
- Access and record rules align with multi-company data separation.
- Chatter & Activities (mail.thread / mail.activity.mixin) across all main entities.

LIMITATIONS & NOTES
- This module intentionally avoids hard dependencies on HR/Payroll; use clinic_doctor_hr when needed.
- Room/device management is owned by clinic_queue_room and clinic_room_device. This module only extends clinic.room with doctor/specialty context.
- For public bookings, enable portal and configure booking routes in your frontend or related modules.

LICENSE
LGPL-3. See the LICENSE file for details.

SUPPORT
For issues, enhancements, or contributions, follow the ClinicOne contribution guidelines. Please include reproducible steps and test cases where possible.
""",

    "category": "ClinicOne",
    "author": "IG @odoocamp",
    "website": "https://www.247opensource.example",
    "version": "19.0.1.0.0",

    # Odoo core & foundation
    # (Gunakan 'base' huruf kecil sesuai standar Odoo; 'contacts' memuat res.partner,
    #  'mail' untuk chatter/activity, 'resource' untuk resource.calendar, 'portal' untuk template portal opsional)
    "depends": [
        "base", 
        "mail", 
        "contacts", 
        "resource", 
        "portal",
        "hr",
        "account",  # required by active clinic.appointment.invoice_id -> account.move
        "sale",     # required by active clinic.appointment.sale_order_id -> sale.order
        # ClinicOne base
        "clinic_base", 
        "clinic_audit", ## is_doctor create di sini DONE 19
        "clinic_branch", ## DONE 19
        "clinic_staff", ## DONE 19
        "clinic_room_device", ## DONE 19
        "clinic_treatment_catalog", ## DONE 19
        "clinic_patient", ## DONE 19
        #  "clinic_patient",
        # "clinic_room_device",
        # "clinic_queue_room",
        # "clinic_encounter",
        # Catatan:
        # - Modul ClinicOne lain (booking, billing, treatment, dst.) akan meng-"depend" ke clinic_doctor,
        #   bukan sebaliknya, untuk menghindari circular dependency.
    ],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}

