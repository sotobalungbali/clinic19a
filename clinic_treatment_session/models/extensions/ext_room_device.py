# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BookingRoom(models.Model):
    """
    Extension of booking.room to integrate with Clinic Treatment Session.

    Peran & integrasi utama:

    - Relasi:
        * One2many ke clinic.treatment.session (treatment_session_ids)
          sehingga setiap room/device mengetahui sesi apa saja yang
          sudah/sedang/akan berlangsung di ruang tersebut.

    - Monitoring Occupancy:
        * occupancy_state      → available / scheduled / in_use
        * next_session_id      → sesi treatment berikutnya di room itu
        * sessions_today_count → jumlah sesi treatment hari ini
        * sessions_in_use_count→ sesi yang sedang berlangsung

    - Helper:
        * is_available(start, end) → cek ketersediaan room di interval waktu
        * get_occupancy_summary()  → info ringkas untuk dashboard/addon lain

    Integrasi dengan 39 addon ClinicOne:

    - clinic_booking:
        * booking.booking & booking.room bisa memanggil helper is_available()
          ketika menjadwalkan booking atau menggeser jadwal.
        * action_view_treatment_sessions bisa dipakai dari form room.

    - clinic_treatment_session:
        * field room_id di clinic.treatment.session menunjuk ke booking.room.

    - Addon lain:
        * modul scheduler, dashboard, analytics dapat override /
          memperluas get_occupancy_summary() untuk menambahkan informasi
          tambahan seperti revenue per room, kategori alat, dsb.
    """

    _inherit = "booking.room"

    # -------------------------------------------------------------------------
    # RELATIONS TO TREATMENT SESSIONS
    # -------------------------------------------------------------------------
    treatment_session_ids = fields.One2many(
        "clinic.treatment.session",
        "room_id",
        string="Treatment Sessions",
        help="Treatment sessions scheduled or performed in this room/device.",
    )

    treatment_session_count = fields.Integer(
        string="Treatment Session Count",
        compute="_compute_session_statistics",
        help="Total number of treatment sessions linked to this room.",
    )

    sessions_today_count = fields.Integer(
        string="Today's Sessions",
        compute="_compute_session_statistics",
        help="Number of treatment sessions scheduled for today in this room.",
    )

    sessions_in_use_count = fields.Integer(
        string="Sessions In Progress",
        compute="_compute_session_statistics",
        help="Number of treatment sessions currently in progress in this room.",
    )

    next_session_id = fields.Many2one(
        "clinic.treatment.session",
        string="Next Session",
        compute="_compute_next_session",
        help="The next upcoming treatment session booked in this room.",
    )

    occupancy_state = fields.Selection(
        [
            ("available", "Available"),
            ("scheduled", "Scheduled"),
            ("in_use", "In Use"),
        ],
        string="Occupancy State",
        compute="_compute_occupancy_state",
        store=False,
        help=(
            "Real-time occupancy status based on treatment sessions:\n"
            "- 'In Use': session currently in progress.\n"
            "- 'Scheduled': upcoming sessions but none in progress.\n"
            "- 'Available': no sessions in progress or scheduled."
        ),
    )

    occupancy_state_label = fields.Char(
        string="Occupancy Label",
        compute="_compute_occupancy_state",
        help="Human readable label for the occupancy state (for kanban/badges).",
    )

    # -------------------------------------------------------------------------
    # SESSION STATISTICS
    # -------------------------------------------------------------------------
    @api.depends("treatment_session_ids.state", "treatment_session_ids.start_datetime")
    def _compute_session_statistics(self):
        """
        Hitung:
          - total treatment_session_count
          - sessions_today_count (sesi dengan start_datetime hari ini & state bukan cancelled)
          - sessions_in_use_count (state = in_progress)
        """
        today = fields.Date.context_today(self)
        for room in self:
            sessions = room.treatment_session_ids
            room.treatment_session_count = len(sessions)

            # Hari ini: berdasarkan tanggal start_datetime
            today_count = 0
            in_use_count = 0
            for sess in sessions:
                if sess.state == "in_progress":
                    in_use_count += 1
                if not sess.start_datetime:
                    continue
                if fields.Date.to_date(sess.start_datetime) == today and sess.state not in (
                    "cancelled",
                ):
                    today_count += 1

            room.sessions_today_count = today_count
            room.sessions_in_use_count = in_use_count

    # -------------------------------------------------------------------------
    # NEXT SESSION (UPCOMING)
    # -------------------------------------------------------------------------
    @api.depends("treatment_session_ids.state", "treatment_session_ids.start_datetime")
    def _compute_next_session(self):
        """
        Cari sesi berikutnya (start_datetime >= sekarang) dengan state
        draft/confirmed/in_progress, urut berdasarkan start_datetime.
        """
        Session = self.env["clinic.treatment.session"]
        now = fields.Datetime.now()
        for room in self:
            # cari via search supaya efisien bila data besar
            next_session = Session.search(
                [
                    ("room_id", "=", room.id),
                    ("state", "in", ("draft", "confirmed", "in_progress")),
                    ("start_datetime", ">=", now),
                ],
                order="start_datetime asc, id asc",
                limit=1,
            )
            room.next_session_id = next_session.id if next_session else False

    # -------------------------------------------------------------------------
    # OCCUPANCY STATE
    # -------------------------------------------------------------------------
    @api.depends(
        "treatment_session_ids.state",
        "treatment_session_ids.start_datetime",
        "treatment_session_ids.end_datetime",
    )
    def _compute_occupancy_state(self):
        """
        Tentukan occupancy_state berdasarkan sesi treatment:

        - in_use:
            ada session dengan:
              state = 'in_progress'
              dan (start <= now < end OR end kosong).

        - scheduled:
            tidak ada in_use, tapi ada session dengan:
              state in ('draft', 'confirmed')
              dan start_datetime >= now.

        - available:
            selain kondisi di atas.
        """
        now = fields.Datetime.now()
        for room in self:
            occupancy = "available"
            sessions = room.treatment_session_ids

            # 1) Cek sesi yang sedang berjalan (in_progress)
            in_use = False
            for sess in sessions:
                if sess.state != "in_progress":
                    continue
                if not sess.start_datetime:
                    continue
                start = fields.Datetime.to_datetime(sess.start_datetime)
                end = (
                    fields.Datetime.to_datetime(sess.end_datetime)
                    if sess.end_datetime
                    else None
                )
                if start <= now and (not end or now < end):
                    in_use = True
                    break

            if in_use:
                occupancy = "in_use"
            else:
                # 2) Cek sesi mendatang (draft / confirmed)
                upcoming = any(
                    sess.state in ("draft", "confirmed")
                    and sess.start_datetime
                    and fields.Datetime.to_datetime(sess.start_datetime) >= now
                    for sess in sessions
                )
                if upcoming:
                    occupancy = "scheduled"
                else:
                    occupancy = "available"

            room.occupancy_state = occupancy

            if occupancy == "in_use":
                room.occupancy_state_label = _("In Use")
            elif occupancy == "scheduled":
                room.occupancy_state_label = _("Scheduled")
            else:
                room.occupancy_state_label = _("Available")

    # -------------------------------------------------------------------------
    # AVAILABILITY CHECK
    # -------------------------------------------------------------------------
    def is_available(self, start_datetime, end_datetime, ignore_session_ids=None):
        """
        Cek apakah room tersedia pada interval waktu tertentu.

        Parameter:
          - start_datetime : datetime planned start
          - end_datetime   : datetime planned end
          - ignore_session_ids : list/recordset clinic.treatment.session
            yang boleh diabaikan (mis. saat reschedule session itu sendiri)

        Return:
          - True  → tidak ada sesi lain yang overlap di room ini
          - False → ada konflik (overlap dengan sesi lain)

        Kriteria overlap:
          [start1, end1) overlaps [start2, end2) jika:
             start1 < end2 AND start2 < end1

        State yang dipertimbangkan:
          - 'draft'
          - 'confirmed'
          - 'in_progress'
        (state done/no_show/cancelled tidak menghalangi booking baru).
        """
        self.ensure_one()
        if not start_datetime or not end_datetime:
            # Tidak cukup info untuk cek; anggap tidak aman.
            return False

        Session = self.env["clinic.treatment.session"]
        ignore_ids = []
        if ignore_session_ids:
            if hasattr(ignore_session_ids, "ids"):
                ignore_ids = ignore_session_ids.ids
            elif isinstance(ignore_session_ids, (list, tuple, set)):
                ignore_ids = list(ignore_session_ids)

        domain = [
            ("room_id", "=", self.id),
            ("state", "in", ("draft", "confirmed", "in_progress")),
            ("id", "not in", ignore_ids),
            ("start_datetime", "<", end_datetime),
            ("end_datetime", ">", start_datetime),
        ]

        # Catatan: jika end_datetime dari sesi atau param None, logic overlap
        # bisa dibuat lebih canggih, tapi di sini kita asumsikan end_datetime
        # selalu terisi saat cek.
        conflict = Session.search_count(domain)
        return conflict == 0

    def get_occupancy_summary(self):
        """
        Berikan ringkasan occupancy untuk room ini sebagai dict.

        Return dict contoh:
        {
            'room_id': <id>,
            'name': <room_name>,
            'occupancy_state': 'in_use',
            'occupancy_label': 'In Use',
            'sessions_today': 5,
            'sessions_in_use': 1,
            'next_session_id': 42,
            'next_session_start': '2025-11-28 10:00:00',
            'next_session_patient': 'John Doe',
        }

        Modul lain (dashboard, reporting, analytics) bisa pakai method ini
        sebagai API stabil, dan boleh override di modul khusus.
        """
        self.ensure_one()
        summary = {
            "room_id": self.id,
            "name": self.display_name or self.name,
            "occupancy_state": self.occupancy_state,
            "occupancy_label": self.occupancy_state_label,
            "sessions_today": self.sessions_today_count,
            "sessions_in_use": self.sessions_in_use_count,
            "next_session_id": self.next_session_id.id if self.next_session_id else False,
            "next_session_start": self.next_session_id.start_datetime
            if self.next_session_id
            else False,
            "next_session_patient": self.next_session_id.patient_id.display_name
            if self.next_session_id and self.next_session_id.patient_id
            else False,
        }
        return summary

    # -------------------------------------------------------------------------
    # ACTIONS / SMART BUTTONS
    # -------------------------------------------------------------------------
    def action_view_treatment_sessions(self):
        """
        Smart button dari form room untuk melihat semua sesi treatment
        yang menggunakan room/device ini.
        """
        self.ensure_one()
        action = self.env.ref(
            "clinic_treatment_session.action_clinic_treatment_session"
        ).read()[0]
        action.update(
            {
                "domain": [("room_id", "=", self.id)],
                "context": {
                    "default_room_id": self.id,
                },
            }
        )
        return action

    def action_view_today_treatment_sessions(self):
        """
        Optional action: buka daftar sesi treatment di room ini khusus hari ini.
        Bisa dipakai sebagai smart button kedua atau menu khusus.
        """
        self.ensure_one()
        today = fields.Date.context_today(self)
        start_of_day = fields.Datetime.to_datetime(today)
        end_of_day = start_of_day + fields.Date.delta(days=1)

        action = self.env.ref(
            "clinic_treatment_session.action_clinic_treatment_session"
        ).read()[0]
        action.update(
            {
                "domain": [
                    ("room_id", "=", self.id),
                    ("start_datetime", ">=", start_of_day),
                    ("start_datetime", "<", end_of_day),
                    ("state", "!=", "cancelled"),
                ],
                "context": {
                    "default_room_id": self.id,
                },
            }
        )
        return action
