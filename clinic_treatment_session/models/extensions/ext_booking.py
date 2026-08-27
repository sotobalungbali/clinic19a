# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime


class BookingBooking(models.Model):
    """
    Extension of booking.booking to integrate with Clinic Treatment Session.

    Tujuan utama:
      - Menambahkan relasi One2many ke clinic.treatment.session
      - Menyediakan helper untuk membuat session dari booking
      - Menyediakan smart button / action untuk melihat session

    Integrasi dengan ekosistem ClinicOne:
      - clinic_patient:
          patient_id (res.partner dengan is_patient=True) di booking akan
          diteruskan ke session.patient_id.
      - clinic_doctor:
          clinic_doctor_id / doctor_id / employee_id di booking akan diteruskan
          ke session.clinic_doctor_id (jika ada).
      - clinic_booking:
          booking.booking & booking.room sebagai sumber jadwal & room session.
      - clinic_treatment_catalog:
          treatment_id di booking (jika ada) diteruskan ke session.treatment_id.
      - clinic_treatment_session:
          membuat record clinic.treatment.session & menjaga relasi.
      - Addon lain (wallet, membership, package, dll) dapat meng-override:
          * _prepare_session_vals_extra()
          * _post_generate_treatment_sessions()
          untuk menambahkan logika khusus saat session dibuat dari booking.
    """

    _inherit = "booking.booking"

    # -------------------------------------------------------------------------
    # RELATIONS TO TREATMENT SESSION
    # -------------------------------------------------------------------------
    treatment_session_ids = fields.One2many(
        "clinic.treatment.session",
        "booking_id",
        string="Treatment Sessions",
        copy=False,
        help="Treatment sessions that have been or will be executed for this booking.",
    )

    treatment_session_count = fields.Integer(
        string="Treatment Session Count",
        compute="_compute_treatment_session_count",
        help="Number of treatment sessions linked to this booking.",
    )

    has_treatment_sessions = fields.Boolean(
        string="Has Treatment Sessions",
        compute="_compute_treatment_session_count",
        help="Technical flag indicating whether this booking has any sessions.",
    )

    # Kebijakan pembuatan sesi dari booking; bisa dibaca addon lain
    auto_session_policy = fields.Selection(
        [
            ("manual", "Manual - Created On Demand"),
            ("auto_on_confirm", "Automatically When Booking Is Confirmed"),
            ("auto_on_checkin", "Automatically When Patient Checks In"),
        ],
        string="Treatment Session Policy",
        default="manual",
        help=(
            "Define how treatment sessions should be created for this booking:\n"
            "- Manual: staff explicitly triggers creation.\n"
            "- Auto on Confirm: sessions can be created automatically when booking "
            "is confirmed (if implemented by the booking workflow).\n"
            "- Auto on Check-in: sessions can be created automatically when patient "
            "checks in (if booking module has a check-in flow)."
        ),
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends("treatment_session_ids.state")
    def _compute_treatment_session_count(self):
        """
        Hitung jumlah sesi per booking & set flag has_treatment_sessions.
        """
        for booking in self:
            count = len(booking.treatment_session_ids)
            booking.treatment_session_count = count
            booking.has_treatment_sessions = bool(count)

    # -------------------------------------------------------------------------
    # HELPER: GUESS FIELDS FROM BOOKING MODEL
    # -------------------------------------------------------------------------
    def _get_booking_patient(self):
        """
        Cari field pasien dari booking.
        Prioritas:
          - patient_id (ClinicOne booking biasa)
          - partner_id (fallback jika booking generik)
        """
        self.ensure_one()
        patient = False
        if "patient_id" in self._fields and self.patient_id:
            patient = self.patient_id
        elif "partner_id" in self._fields and self.partner_id:
            patient = self.partner_id
        return patient

    def _get_booking_doctor(self):
        """
        Cari dokter / therapist dari booking.
        Prioritas:
          - clinic_doctor_id (ClinicOne)
          - doctor_id (alternatif)
          - employee_id (fallback HR)
        """
        self.ensure_one()
        doctor = False
        if "clinic_doctor_id" in self._fields and self.clinic_doctor_id:
            doctor = self.clinic_doctor_id
        elif "doctor_id" in self._fields and getattr(self, "doctor_id", False):
            doctor = self.doctor_id
        elif "employee_id" in self._fields and getattr(self, "employee_id", False):
            doctor = self.employee_id
        return doctor

    def _get_booking_room(self):
        """
        Cari room/device dari booking.
        Prioritas:
          - room_id (ClinicOne booking)
          - resource_id (mis. resource.calendar)
        """
        self.ensure_one()
        room = False
        if "room_id" in self._fields and self.room_id:
            room = self.room_id
        elif "resource_id" in self._fields and getattr(self, "resource_id", False):
            room = self.resource_id
        return room

    def _get_booking_datetime_range(self):
        """
        Cari start & end datetime booking.

        Prioritas field:
          - start_datetime / end_datetime
          - start / stop (model generic calendar/event)
          - date_start / date_end + default jam
          - date_booking + duration (fallback)
        """
        self.ensure_one()
        start_dt = None
        end_dt = None

        # 1) start_datetime / end_datetime
        if "start_datetime" in self._fields and getattr(
            self, "start_datetime", False
        ):
            start_dt = self.start_datetime
        if "end_datetime" in self._fields and getattr(self, "end_datetime", False):
            end_dt = self.end_datetime

        # 2) start / stop (event-like)
        if not start_dt and "start" in self._fields and getattr(self, "start", False):
            start_dt = self.start
        if not end_dt and "stop" in self._fields and getattr(self, "stop", False):
            end_dt = self.stop

        # 3) date_start / date_end
        if (
            not start_dt
            and "date_start" in self._fields
            and getattr(self, "date_start", False)
        ):
            # date_start type-nya bisa Date atau Datetime; biarkan Odoo handle
            start_dt = self.date_start
        if (
            not end_dt
            and "date_end" in self._fields
            and getattr(self, "date_end", False)
        ):
            end_dt = self.date_end

        # 4) date_booking + duration (fallback)
        if not start_dt and "date_booking" in self._fields and getattr(
            self, "date_booking", False
        ):
            # treat date_booking as date, jam default misalnya 09:00
            date_obj = fields.Date.to_date(self.date_booking)
            start_dt = datetime.combine(date_obj, datetime.min.time())
        if not end_dt and start_dt and "duration" in self._fields:
            try:
                duration_hours = float(self.duration or 0.0)
            except Exception:
                duration_hours = 0.0
            if duration_hours > 0:
                end_dt = fields.Datetime.to_datetime(start_dt) + fields.Date.delta(
                    hours=duration_hours
                )

        return start_dt, end_dt

    def _get_booking_treatments(self):
        """
        Cari treatment yang terkait dengan booking.

        Skema yang didukung:
          - treatment_id (Many2one ke clinic.treatment)
          - treatment_ids (Many2many ke clinic.treatment)
          - booking_line_ids dengan field treatment_id

        Return: recordset clinic.treatment (boleh kosong).
        """
        self.ensure_one()
        Treatment = self.env["clinic.treatment"]
        treatments = Treatment.browse()

        # Single treatment_id
        if "treatment_id" in self._fields and getattr(self, "treatment_id", False):
            treatments |= self.treatment_id

        # Many2many treatment_ids
        if "treatment_ids" in self._fields and getattr(self, "treatment_ids", False):
            treatments |= self.treatment_ids

        # Line-based treatment
        if "booking_line_ids" in self._fields and getattr(
            self, "booking_line_ids", False
        ):
            for line in self.booking_line_ids:
                if hasattr(line, "treatment_id") and line.treatment_id:
                    treatments |= line.treatment_id

        return treatments

    # -------------------------------------------------------------------------
    # PREPARE SESSION VALS
    # -------------------------------------------------------------------------
    def _prepare_session_vals(self, treatment=False, start_dt=False, end_dt=False, room=False):
        """
        Siapkan dict nilai untuk create clinic.treatment.session dari booking.

        Parameter:
          - treatment : clinic.treatment (opsional)
          - start_dt  : datetime planned start (opsional, fallback ke booking)
          - end_dt    : datetime planned end (opsional, fallback ke booking)
          - room      : booking.room / resource (opsional, fallback ke booking)

        Addon lain boleh override method ini untuk menambahkan field tambahan,
        atau override _prepare_session_vals_extra di bawah.
        """
        self.ensure_one()

        # Ambil entity utama dari helper di atas
        patient = self._get_booking_patient()
        doctor = self._get_booking_doctor()
        room = room or self._get_booking_room()
        start, end = self._get_booking_datetime_range()
        if start_dt:
            start = start_dt
        if end_dt:
            end = end_dt

        # Hitung planned duration (menit)
        duration_planned = 0.0
        if start and end:
            start_dt_real = fields.Datetime.to_datetime(start)
            end_dt_real = fields.Datetime.to_datetime(end)
            delta = end_dt_real - start_dt_real
            duration_planned = max(delta.total_seconds() / 60.0, 0.0)

        # Cari note internal di booking (nama field bisa beda)
        note_internal = False
        for field_name in ("note", "internal_note", "remarks", "comment"):
            if field_name in self._fields and getattr(self, field_name, False):
                note_internal = getattr(self, field_name)
                break

        vals = {
            "company_id": self.company_id.id if "company_id" in self._fields else self.env.company.id,
            "patient_id": patient.id if patient else False,
            "clinic_doctor_id": doctor.id if doctor else False,
            "treatment_id": treatment.id if treatment else False,
            "booking_id": self.id,
            "room_id": room.id if room else False,
            "start_datetime": start,
            "end_datetime": end,
            "duration_planned": duration_planned,
            "note_internal": note_internal,
        }

        # Extra vals from specialized addons (wallet/membership/package/etc.)
        extra_vals = self._prepare_session_vals_extra(treatment=treatment)
        if extra_vals:
            vals.update(extra_vals)

        return vals

    def _prepare_session_vals_extra(self, treatment=False):
        """
        Hook untuk addon lain.

        Contoh di addon lain (mis. clinic_package):
            def _prepare_session_vals_extra(self, treatment=False):
                res = super()._prepare_session_vals_extra(treatment=treatment)
                res.update({
                    'some_field': self.some_value,
                })
                return res

        Default: tidak menambah field apa pun.
        """
        return {}

    # -------------------------------------------------------------------------
    # MAIN ACTION: GENERATE TREATMENT SESSIONS
    # -------------------------------------------------------------------------
    def action_generate_treatment_sessions(self):
        """
        Aksi utama untuk membuat session dari booking.

        Behavior default:
          - Untuk setiap booking:
              * Jika sudah punya treatment_session_ids dan context TIDAK
                mengizinkan duplikasi, raise UserError.
              * Cari treatment dari _get_booking_treatments().
              * Kalau treatment ada:
                    - Buat 1 session per treatment (satu booking bisa jadi
                      multi-session kalau booking multi-treatment).
                Kalau tidak ada:
                    - Tetap buat satu session 'kosong' tanpa treatment_id.
          - Kembalikan action untuk membuka sessions yang baru dibuat.

        Context flags:
          - allow_duplicate_sessions=True:
              izinkan membuat session baru meskipun booking sudah punya session.
        """
        Session = self.env["clinic.treatment.session"]
        allow_dup = bool(self.env.context.get("allow_duplicate_sessions"))
        created_sessions = Session.browse()

        for booking in self:
            if booking.treatment_session_ids and not allow_dup:
                raise UserError(
                    _(
                        "Booking '%s' already has treatment sessions. "
                        "To generate additional sessions, please enable "
                        "'allow_duplicate_sessions' in the context or "
                        "use a dedicated action."
                    )
                    % (booking.display_name or booking.name or booking.id,)
                )

            treatments = booking._get_booking_treatments()

            # Case 1: ada beberapa treatment → buat session per treatment
            if treatments:
                for treat in treatments:
                    vals = booking._prepare_session_vals(treatment=treat)
                    new_session = Session.create(vals)
                    created_sessions |= new_session
            else:
                # Case 2: tidak ada treatment → tetap buat minimal 1 session
                vals = booking._prepare_session_vals(treatment=False)
                new_session = Session.create(vals)
                created_sessions |= new_session

        # Hook setelah sesi dibuat (untuk sinkronisasi booking / notifikasi / dsb.)
        self._post_generate_treatment_sessions(created_sessions)

        # Return action untuk membuka session yang baru dibuat / terkait booking
        if len(created_sessions) == 1:
            # langsung buka form view
            action = self.env.ref(
                "clinic_treatment_session.action_clinic_treatment_session"
            ).read()[0]
            action.update(
                {
                    "view_mode": "form",
                    "res_id": created_sessions.id,
                    "views": [(False, "form")],
                }
            )
            return action
        else:
            # buka tree view terfilter ke session yang terkait booking(s) ini
            action = self.env.ref(
                "clinic_treatment_session.action_clinic_treatment_session"
            ).read()[0]
            action_domain = [("id", "in", created_sessions.ids)]
            action.update({"domain": action_domain})
            return action

    def _post_generate_treatment_sessions(self, sessions):
        """
        Hook setelah sesi treatment dibuat dari booking.

        Default:
          - Tidak melakukan apa-apa (placeholder untuk addon lain).
        Contoh di addon lain:
          - Update state booking (mis. 'in_progress' / 'scheduled')
          - Buat aktivitas di chatter dokter/pasien
          - Sinkronisasi dengan modul billing, membership, wallet, dll.
        """
        # Designed for override by other modules.
        return True

    # -------------------------------------------------------------------------
    # ACTIONS / SMART BUTTONS
    # -------------------------------------------------------------------------
    def action_view_treatment_sessions(self):
        """
        Smart button untuk melihat semua treatment session yang terkait booking ini.
        """
        self.ensure_one()
        action = self.env.ref(
            "clinic_treatment_session.action_clinic_treatment_session"
        ).read()[0]

        action.update(
            {
                "domain": [("booking_id", "=", self.id)],
                "context": {
                    "default_booking_id": self.id,
                    "default_patient_id": self._get_booking_patient().id
                    if self._get_booking_patient()
                    else False,
                    "default_clinic_doctor_id": self._get_booking_doctor().id
                    if self._get_booking_doctor()
                    else False,
                    "default_room_id": self._get_booking_room().id
                    if self._get_booking_room()
                    else False,
                },
            }
        )
        return action

    def action_generate_and_view_treatment_sessions(self):
        """
        Convenience action: generate sessions lalu langsung buka hasilnya.

        Bisa di-mapping ke button terpisah:
          'Generate Sessions' pada form booking.
        """
        # simply call main generator; dia sudah return action
        return self.with_context(allow_duplicate_sessions=self.env.context.get("allow_duplicate_sessions")).action_generate_treatment_sessions()
