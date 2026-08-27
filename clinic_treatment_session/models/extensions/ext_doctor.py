# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrEmployee(models.Model):
    """
    Extension of hr.employee for ClinicOne Treatment Sessions (Odoo 19 CE).

    Asumsi arsitektur ClinicOne:
      - Addon `clinic_doctor` meng-extend hr.employee untuk menandai staff
        sebagai dokter/terapis (misalnya dengan field boolean `is_clinic_doctor`
        atau `is_doctor`).
      - Model `clinic.treatment.session` menggunakan field:
            clinic_doctor_id = Many2one('hr.employee')

    Tujuan ext_doctor:
      - Menambahkan relasi 1:N dari dokter ke sesi treatment:
            dokter → clinic.treatment.session
      - Memberikan statistik siap pakai:
          * jumlah semua sesi (total)
          * sesi hari ini
          * sesi in_progress
          * sesi terakhir (last_session)
          * sesi berikutnya (next_session)
      - Menyediakan actions & helper API yang bisa dipakai 39 addon lain:
          * billing, membership, package, wallet, scheduler, dashboard, reports, dsb.

    Desain:
      - Soft-coupled: hanya bergantung pada model `clinic.treatment.session`
        dan field umum di hr.employee (`is_clinic_doctor` / `is_doctor` jika ada).
      - Multi-company aware.
      - Kompatibel dengan Odoo 19 CE (API modern, tanpa attrs/states di XML).
    """

    _inherit = "hr.employee"

    # -------------------------------------------------------------------------
    # RELATIONS & BASIC STATS
    # -------------------------------------------------------------------------
    treatment_session_ids = fields.One2many(
        "clinic.treatment.session",
        "clinic_doctor_id",
        string="Treatment Sessions",
        help="All treatment sessions (past and future) handled by this doctor/therapist.",
    )

    treatment_session_count = fields.Integer(
        string="Treatment Sessions",
        compute="_compute_treatment_session_stats",
        help="Total number of treatment sessions linked to this doctor/therapist.",
    )

    sessions_today_count = fields.Integer(
        string="Today's Sessions",
        compute="_compute_treatment_session_stats",
        help="Number of treatment sessions scheduled for this doctor today (non-cancelled).",
    )

    sessions_in_progress_count = fields.Integer(
        string="Sessions In Progress",
        compute="_compute_treatment_session_stats",
        help="Number of treatment sessions currently in progress for this doctor.",
    )

    has_treatment_sessions = fields.Boolean(
        string="Has Treatment Sessions",
        compute="_compute_treatment_session_stats",
        help="Technical flag indicating whether this doctor ever had a session.",
    )

    # -------------------------------------------------------------------------
    # LAST & NEXT SESSION
    # -------------------------------------------------------------------------
    last_session_id = fields.Many2one(
        "clinic.treatment.session",
        string="Last Session",
        compute="_compute_last_next_session",
        help="Most recent completed or in-progress session for this doctor.",
    )

    last_session_date = fields.Datetime(
        string="Last Session Date",
        compute="_compute_last_next_session",
        help="Date/time of the last session.",
    )

    next_session_id = fields.Many2one(
        "clinic.treatment.session",
        string="Next Scheduled Session",
        compute="_compute_last_next_session",
        help="Next upcoming session for this doctor.",
    )

    next_session_date = fields.Datetime(
        string="Next Session Date",
        compute="_compute_last_next_session",
        help="Planned date/time of the next session.",
    )

    upcoming_session_exists = fields.Boolean(
        string="Has Upcoming Session",
        compute="_compute_last_next_session",
        help="Indicates if there is at least one future scheduled session.",
    )

    # -------------------------------------------------------------------------
    # INTERNAL HELPERS
    # -------------------------------------------------------------------------
    def _is_clinic_doctor(self):
        """
        Helper: tentukan apakah employee ini diperlakukan sebagai dokter/terapis.

        Logika:
          - Jika field `is_clinic_doctor` ada → gunakan nilainya.
          - Kalau tidak ada tapi ada field `is_doctor` → gunakan nilainya.
          - Jika keduanya tidak ada, fallback: treat as doctor=True
            (untuk menjaga kompatibilitas ketika modul clinic_doctor belum
             menambahkan flag eksplisit).
        """
        self.ensure_one()
        if "is_clinic_doctor" in self._fields:
            return bool(self.is_clinic_doctor)
        if "is_doctor" in self._fields:
            return bool(self.is_doctor)
        # fallback
        return True

    def _base_session_domain(self):
        """
        Domain dasar untuk mencari sesi milik dokter ini.

        Multi-company aware:
          - Secara default, hanya ambil sesi pada perusahaan aktif
            atau company employee bila di-set.
        """
        self.ensure_one()
        domain = [("clinic_doctor_id", "=", self.id)]

        company = self.company_id or self.env.company
        if company:
            domain.append(("company_id", "=", company.id))
        return domain

    # -------------------------------------------------------------------------
    # COMPUTE: COUNT, TODAY, IN PROGRESS
    # -------------------------------------------------------------------------
    @api.depends("treatment_session_ids.state", "treatment_session_ids.start_datetime")
    def _compute_treatment_session_stats(self):
        """
        Hitung:
          - total sesi per dokter
          - sesi hari ini
          - sesi in_progress
          - flag has_treatment_sessions
        Kombinasi read_group + perhitungan manual untuk efisiensi.
        """
        Session = self.env["clinic.treatment.session"].sudo()
        today = fields.Date.context_today(self)

        # reset default
        for emp in self:
            emp.treatment_session_count = 0
            emp.sessions_today_count = 0
            emp.sessions_in_progress_count = 0
            emp.has_treatment_sessions = False

        # Hanya doctors
        doctors = self.filtered(lambda e: e._is_clinic_doctor())
        if not doctors:
            return

        # 1) read_group untuk total count per doctor
        domain = [("clinic_doctor_id", "in", doctors.ids)]
        group_data = Session.read_group(
            domain=domain,
            fields=["clinic_doctor_id", "id:count"],
            groupby=["clinic_doctor_id"],
            lazy=False,
        )
        total_map = {
            g["clinic_doctor_id"][0]: g["clinic_doctor_id_count"] for g in group_data
        }

        # 2) hitung sessions_today & sessions_in_progress secara sederhana
        #    (loop per doctor; bisa dioptimasi dengan search sekali jika perlu)
        for emp in doctors:
            total = total_map.get(emp.id, 0)
            emp.treatment_session_count = total
            emp.has_treatment_sessions = bool(total)

            if not total:
                continue

            # filter sesi per dokter ini untuk hitung harian & in_progress
            sessions = emp.treatment_session_ids
            today_count = 0
            in_progress_count = 0
            for sess in sessions:
                if sess.state == "in_progress":
                    in_progress_count += 1
                if (
                    sess.start_datetime
                    and fields.Date.to_date(sess.start_datetime) == today
                    and sess.state not in ("cancelled",)
                ):
                    today_count += 1
            emp.sessions_today_count = today_count
            emp.sessions_in_progress_count = in_progress_count

    # -------------------------------------------------------------------------
    # COMPUTE: LAST & NEXT SESSION
    # -------------------------------------------------------------------------
    @api.depends(
        "treatment_session_ids.state",
        "treatment_session_ids.start_datetime",
        "treatment_session_ids.end_datetime",
    )
    def _compute_last_next_session(self):
        """
        Hitung:
          - last_session_id & last_session_date:
              Sesi dengan start_datetime paling akhir di antara:
                state in ('done', 'in_progress', 'confirmed')
          - next_session_id & next_session_date:
              Sesi dengan start_datetime >= now,
              state in ('draft', 'confirmed', 'in_progress'),
              urut start_datetime asc.
          - upcoming_session_exists.
        """
        Session = self.env["clinic.treatment.session"]
        now = fields.Datetime.now()

        for emp in self:
            emp.last_session_id = False
            emp.last_session_date = False
            emp.next_session_id = False
            emp.next_session_date = False
            emp.upcoming_session_exists = False

            if not emp._is_clinic_doctor():
                continue

            base_domain = emp._base_session_domain()

            # LAST
            last_domain = base_domain + [
                ("state", "in", ("done", "in_progress", "confirmed")),
                ("start_datetime", "!=", False),
            ]
            last_session = Session.search(
                last_domain,
                order="start_datetime desc, id desc",
                limit=1,
            )
            if last_session:
                emp.last_session_id = last_session
                emp.last_session_date = last_session.start_datetime

            # NEXT
            next_domain = base_domain + [
                ("state", "in", ("draft", "confirmed", "in_progress")),
                ("start_datetime", ">=", now),
            ]
            next_session = Session.search(
                next_domain,
                order="start_datetime asc, id asc",
                limit=1,
            )
            if next_session:
                emp.next_session_id = next_session
                emp.next_session_date = next_session.start_datetime
                emp.upcoming_session_exists = True

    # -------------------------------------------------------------------------
    # ACTIONS / SMART BUTTONS
    # -------------------------------------------------------------------------
    def action_view_treatment_sessions(self):
        """
        Smart button: buka semua treatment session milik dokter ini.

        Cocok dipasang sebagai tombol "Treatment Sessions" di form doctor (hr.employee).
        """
        self.ensure_one()
        if not self._is_clinic_doctor():
            raise UserError(
                _(
                    "This employee is not marked as a clinic doctor/therapist "
                    "and therefore has no treatment sessions."
                )
            )

        action = self.env.ref(
            "clinic_treatment_session.action_clinic_treatment_session"
        ).read()[0]
        action.update(
            {
                "domain": [("clinic_doctor_id", "=", self.id)],
                "context": {
                    "default_clinic_doctor_id": self.id,
                    "search_default_group_by_doctor": 1,
                },
            }
        )
        return action

    def action_view_today_treatment_sessions(self):
        """
        Smart button opsional: buka daftar sesi hari ini untuk dokter ini.

        Bisa dipakai di dashboard dokter untuk melihat jadwal harian.
        """
        self.ensure_one()
        if not self._is_clinic_doctor():
            raise UserError(
                _(
                    "This employee is not marked as a clinic doctor/therapist. "
                    "No daily treatment agenda can be displayed."
                )
            )

        today = fields.Date.context_today(self)
        start_of_day = fields.Datetime.to_datetime(today)
        end_of_day = start_of_day + fields.Date.delta(days=1)

        action = self.env.ref(
            "clinic_treatment_session.action_clinic_treatment_session"
        ).read()[0]
        action.update(
            {
                "name": _("Today's Sessions"),
                "domain": [
                    ("clinic_doctor_id", "=", self.id),
                    ("start_datetime", ">=", start_of_day),
                    ("start_datetime", "<", end_of_day),
                    ("state", "!=", "cancelled"),
                ],
                "context": {
                    "default_clinic_doctor_id": self.id,
                },
            }
        )
        return action

    def action_view_next_session(self):
        """
        Smart button opsional: langsung buka sesi terdekat (next scheduled).

        Biasanya dipakai sebagai tombol cepat di kartu dokter.
        """
        self.ensure_one()
        if not self._is_clinic_doctor():
            raise UserError(
                _(
                    "This employee is not marked as a clinic doctor/therapist. "
                    "No upcoming treatment session can be found."
                )
            )
        if not self.next_session_id:
            raise UserError(
                _(
                    "There is no upcoming treatment session scheduled for this doctor yet."
                )
            )

        action = self.env.ref(
            "clinic_treatment_session.action_clinic_treatment_session"
        ).read()[0]
        action.update(
            {
                "view_mode": "form",
                "views": [(False, "form")],
                "res_id": self.next_session_id.id,
                "domain": [("id", "=", self.next_session_id.id)],
                "context": {
                    "default_clinic_doctor_id": self.id,
                },
            }
        )
        return action

    # -------------------------------------------------------------------------
    # PUBLIC API FOR OTHER ADDONS (PRODUCTIVITY / WORKLOAD)
    # -------------------------------------------------------------------------
    def get_treatment_statistics(self, since_date=False):
        """
        API yang dapat dipanggil modul lain (scheduler, billing, membership,
        package, wallet, dashboard, reporting, dsb.) untuk mengambil ringkasan
        statistik sesi per dokter.

        Param:
          - since_date (optional Date/Datetime/string):
                jika diisi, hanya hitung sesi dengan start_datetime >= since_date.

        Return:
          - Untuk single record: dict
          - Untuk multi record: list of dict

        Struktur dict:
          {
            'doctor_id': <id>,
            'doctor_name': <name>,
            'company_id': <company_id>,
            'total_sessions': int,
            'total_done': int,
            'total_no_show': int,
            'total_cancelled': int,
            'total_upcoming': int,
            'patients_served': int,   # distinct patient_id
            'last_session_id': <id or False>,
            'last_session_date': <datetime or False>,
            'next_session_id': <id or False>,
            'next_session_date': <datetime or False>,
          }
        """
        Session = self.env["clinic.treatment.session"]

        def _normalize_since(d):
            if not d:
                return False
            if isinstance(d, str):
                # biarkan Odoo parse string; bisa Date atau Datetime
                try:
                    return fields.Datetime.to_datetime(d)
                except Exception:
                    try:
                        date_obj = fields.Date.to_date(d)
                        return fields.Datetime.to_datetime(date_obj)
                    except Exception:
                        return False
            # datetime-like (punya atribute hour)
            if hasattr(d, "hour"):
                return d
            # kemungkinan Date object
            return fields.Datetime.to_datetime(d)

        since_dt = _normalize_since(since_date)
        results = []

        for emp in self:
            if not emp._is_clinic_doctor():
                # Bukan dokter; tetap kembalikan entry minimal
                results.append(
                    {
                        "doctor_id": emp.id,
                        "doctor_name": emp.display_name,
                        "company_id": emp.company_id.id if emp.company_id else False,
                        "total_sessions": 0,
                        "total_done": 0,
                        "total_no_show": 0,
                        "total_cancelled": 0,
                        "total_upcoming": 0,
                        "patients_served": 0,
                        "last_session_id": False,
                        "last_session_date": False,
                        "next_session_id": False,
                        "next_session_date": False,
                    }
                )
                continue

            base_domain = emp._base_session_domain()
            if since_dt:
                base_domain += [("start_datetime", ">=", since_dt)]

            # read_group by state
            group_data = Session.read_group(
                domain=base_domain,
                fields=["state", "id:count"],
                groupby=["state"],
                lazy=False,
            )

            total_sessions = 0
            total_done = 0
            total_no_show = 0
            total_cancelled = 0
            total_upcoming = 0

            for g in group_data:
                state = g["state"]
                cnt = g["state_count"]
                total_sessions += cnt
                if state == "done":
                    total_done += cnt
                elif state == "no_show":
                    total_no_show += cnt
                elif state == "cancelled":
                    total_cancelled += cnt
                elif state in ("draft", "confirmed", "in_progress"):
                    total_upcoming += cnt

            # Distinct patients served
            patient_group = Session.read_group(
                domain=base_domain,
                fields=["patient_id"],
                groupby=["patient_id"],
                lazy=False,
            )
            patients_served = len(patient_group)

            results.append(
                {
                    "doctor_id": emp.id,
                    "doctor_name": emp.display_name,
                    "company_id": emp.company_id.id if emp.company_id else False,
                    "total_sessions": total_sessions,
                    "total_done": total_done,
                    "total_no_show": total_no_show,
                    "total_cancelled": total_cancelled,
                    "total_upcoming": total_upcoming,
                    "patients_served": patients_served,
                    "last_session_id": emp.last_session_id.id
                    if emp.last_session_id
                    else False,
                    "last_session_date": emp.last_session_date,
                    "next_session_id": emp.next_session_id.id
                    if emp.next_session_id
                    else False,
                    "next_session_date": emp.next_session_date,
                }
            )

        return results if len(self) > 1 else (results[0] if results else {})
