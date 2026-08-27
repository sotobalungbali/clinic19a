# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    """
    Extension of res.partner for ClinicOne Treatment Sessions (Odoo 19 CE).

    Asumsi arsitektur ClinicOne:
      - Addon `clinic_patient` menambahkan flag `is_patient` di res.partner
        (atau mekanisme serupa) untuk menandai partner sebagai pasien.
      - Model `clinic.treatment.session` menggunakan field:
            patient_id = Many2one('res.partner', domain=[('is_patient', '=', True)])

    Tujuan ext_patient:
      - Menambahkan relasi 1:N dari pasien ke sesi treatment:
          partner → clinic.treatment.session
      - Memberikan statistik:
          * jumlah semua sesi
          * sesi terakhir (last_session)
          * sesi berikutnya (next_session)
      - Menyediakan action & helper yang bisa dipakai 39 addon lain:
          * billing, membership, package, wallet, dashboard, reports, dsb.

    Desain:
      - Soft-coupled: hanya bergantung pada model `clinic.treatment.session`
        dan field umum di res.partner (`is_patient` jika ada).
      - Multi-company aware: query difilter berdasarkan company jika relevan.
      - Odoo 19 CE kompatibel karena menggunakan API Odoo modern.
    """

    _inherit = "res.partner"

    # -------------------------------------------------------------------------
    # RELATIONS & BASIC STATS
    # -------------------------------------------------------------------------
    treatment_session_ids = fields.One2many(
        "clinic.treatment.session",
        "patient_id",
        string="Treatment Sessions",
        help="All treatment sessions (past and future) linked to this patient.",
    )

    treatment_session_count = fields.Integer(
        string="Treatment Sessions",
        compute="_compute_treatment_session_stats",
        help="Total number of treatment sessions linked to this patient.",
    )

    has_treatment_sessions = fields.Boolean(
        string="Has Treatment Sessions",
        compute="_compute_treatment_session_stats",
        help="Technical flag indicating whether this patient ever had a session.",
    )

    last_session_id = fields.Many2one(
        "clinic.treatment.session",
        string="Last Session",
        compute="_compute_last_next_session",
        help="Most recent completed or in-progress session for this patient.",
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
        help="Next upcoming (scheduled) session for this patient.",
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
    def _is_patient_partner(self):
        """
        Helper: tentukan apakah partner ini dikategorikan sebagai pasien.

        Logika:
          - Jika field `is_patient` ada di model: gunakan nilainya.
          - Jika tidak ada field `is_patient`, fallback: anggap True
            (untuk menjaga kompatibilitas jika clinic_patient hanya
             meng-extend res.partner tanpa flag tersebut).
        """
        self.ensure_one()
        if "is_patient" in self._fields:
            return bool(self.is_patient)
        # fallback: treat as patient (boleh disesuaikan di proyek)
        return True

    def _base_session_domain(self):
        """
        Domain dasar untuk mencari sesi milik partner ini.

        Multi-company aware:
          - Secara default, hanya ambil sesi pada perusahaan aktif
            atau perusahaan patient jika di-set.
        """
        self.ensure_one()
        domain = [("patient_id", "=", self.id)]

        # Multi-company filter:
        # Jika partner punya company_id → filter ke company tersebut.
        # Kalau tidak, pakai env.company.
        company = self.company_id or self.env.company
        if company:
            domain.append(("company_id", "=", company.id))
        return domain

    # -------------------------------------------------------------------------
    # COMPUTE: COUNT & FLAG
    # -------------------------------------------------------------------------
    @api.depends("treatment_session_ids.state", "treatment_session_ids.start_datetime")
    def _compute_treatment_session_stats(self):
        """
        Hitung:
          - total sesi per patient
          - has_treatment_sessions
        Menggunakan read_group untuk efisiensi pada data besar.
        """
        Session = self.env["clinic.treatment.session"].sudo()
        # Default semua 0
        for partner in self:
            partner.treatment_session_count = 0
            partner.has_treatment_sessions = False

        # Filter hanya partner yang dianggap patient
        if "is_patient" in self._fields:
            patient_partners = self.filtered(lambda p: p.is_patient)
        else:
            patient_partners = self

        if not patient_partners:
            return

        # read_group by patient_id
        domain = [("patient_id", "in", patient_partners.ids)]
        # Kita tidak tambahkan filter company di sini karena sudah
        # ada banyak skenario deployment; kalau mau sangat strict,
        # bisa override di custom module.
        group_data = Session.read_group(
            domain=domain,
            fields=["patient_id", "id:count"],
            groupby=["patient_id"],
            lazy=False,
        )

        counts = {g["patient_id"][0]: g["patient_id_count"] for g in group_data}

        for partner in patient_partners:
            count = counts.get(partner.id, 0)
            partner.treatment_session_count = count
            partner.has_treatment_sessions = bool(count)

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
          - last_session_id & last_session_date
              Sesi dengan start_datetime paling akhir di antara:
                state in ('done', 'in_progress', 'confirmed')
          - next_session_id & next_session_date
              Sesi dengan start_datetime setelah sekarang,
              state in ('draft', 'confirmed', 'in_progress'),
              urut start_datetime asc.
          - upcoming_session_exists
        """
        Session = self.env["clinic.treatment.session"]
        now = fields.Datetime.now()

        for partner in self:
            partner.last_session_id = False
            partner.last_session_date = False
            partner.next_session_id = False
            partner.next_session_date = False
            partner.upcoming_session_exists = False

            if not partner._is_patient_partner():
                continue

            # LAST SESSION
            last_domain = partner._base_session_domain() + [
                ("state", "in", ("done", "in_progress", "confirmed")),
                ("start_datetime", "!=", False),
            ]
            last_session = Session.search(
                last_domain,
                order="start_datetime desc, id desc",
                limit=1,
            )
            if last_session:
                partner.last_session_id = last_session
                partner.last_session_date = last_session.start_datetime

            # NEXT SESSION
            next_domain = partner._base_session_domain() + [
                ("state", "in", ("draft", "confirmed", "in_progress")),
                ("start_datetime", ">=", now),
            ]
            next_session = Session.search(
                next_domain,
                order="start_datetime asc, id asc",
                limit=1,
            )
            if next_session:
                partner.next_session_id = next_session
                partner.next_session_date = next_session.start_datetime
                partner.upcoming_session_exists = True

    # -------------------------------------------------------------------------
    # ACTIONS / SMART BUTTONS
    # -------------------------------------------------------------------------
    def action_view_treatment_sessions(self):
        """
        Smart button: buka semua treatment session milik patient ini.

        Dipakai di form view patient (res.partner) sebagai:
          - "Treatment Sessions" button
        """
        self.ensure_one()
        if not self._is_patient_partner():
            raise UserError(
                _(
                    "This partner is not marked as a patient and therefore "
                    "has no treatment sessions."
                )
            )

        action = self.env.ref(
            "clinic_treatment_session.action_clinic_treatment_session"
        ).read()[0]

        action.update(
            {
                "domain": [("patient_id", "=", self.id)],
                "context": {
                    "default_patient_id": self.id,
                    # Default doctor & room bisa diisi dari konteks modul lain
                },
            }
        )
        return action

    def action_view_treatment_history(self):
        """
        Smart button opsional: buka riwayat sesi yang sudah selesai (Done/No-show).

        Cocok untuk tab "Medical History" / "Treatment History" di kartu pasien.
        """
        self.ensure_one()
        if not self._is_patient_partner():
            raise UserError(
                _(
                    "This partner is not marked as a patient and therefore "
                    "has no treatment history."
                )
            )

        action = self.env.ref(
            "clinic_treatment_session.action_clinic_treatment_session"
        ).read()[0]

        action.update(
            {
                "name": _("Treatment History"),
                "domain": [
                    ("patient_id", "=", self.id),
                    ("state", "in", ("done", "no_show", "cancelled")),
                ],
                "context": {
                    "default_patient_id": self.id,
                },
            }
        )
        return action

    def action_view_next_session(self):
        """
        Smart button opsional: langsung buka sesi terdekat (next scheduled).

        Jika tidak ada sesi berikutnya, berikan UserError yang ramah.
        """
        self.ensure_one()
        if not self._is_patient_partner():
            raise UserError(
                _(
                    "This partner is not marked as a patient. "
                    "No upcoming treatment session can be found."
                )
            )
        if not self.next_session_id:
            raise UserError(
                _(
                    "There is no upcoming treatment session for this patient yet."
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
                    "default_patient_id": self.id,
                },
            }
        )
        return action

    # -------------------------------------------------------------------------
    # PUBLIC API FOR OTHER ADDONS
    # -------------------------------------------------------------------------
    def get_treatment_statistics(self, since_date=False):
        """
        API yang bisa dipanggil modul lain (billing, membership, dashboard, dsb.)
        untuk mengambil ringkasan statistik sesi pasien.

        Param:
          - since_date (optional Date/Datetime):
                jika diisi, hanya hitung sesi dengan start_datetime >= since_date.

        Return dict per patient:
          {
            'patient_id': <id>,
            'patient_name': <name>,
            'company_id': <company_id>,
            'total_sessions': int,
            'total_done': int,
            'total_no_show': int,
            'total_cancelled': int,
            'total_upcoming': int,
            'last_session_id': <id or False>,
            'last_session_date': <datetime or False>,
            'next_session_id': <id or False>,
            'next_session_date': <datetime or False>,
          }

        Jika dipanggil pada multiple recordset, return list of dict.
        """
        Session = self.env["clinic.treatment.session"]
        # Normalisasi since_date jadi datetime kalau tipe-nya Date
        def _normalize_since(d):
            if not d:
                return False
            if isinstance(d, str):
                # biarkan Odoo parse; bisa Date atau Datetime string
                try:
                    return fields.Datetime.to_datetime(d)
                except Exception:
                    try:
                        date_obj = fields.Date.to_date(d)
                        return fields.Datetime.to_datetime(date_obj)
                    except Exception:
                        return False
            if hasattr(d, "hour"):  # sudah datetime
                return d
            # kemungkinan Date object
            return fields.Datetime.to_datetime(d)

        since_dt = _normalize_since(since_date)
        results = []

        for partner in self:
            if not partner._is_patient_partner():
                # Skip non-patients, tapi tetap masukkan entry minimal
                results.append(
                    {
                        "patient_id": partner.id,
                        "patient_name": partner.display_name,
                        "company_id": partner.company_id.id if partner.company_id else False,
                        "total_sessions": 0,
                        "total_done": 0,
                        "total_no_show": 0,
                        "total_cancelled": 0,
                        "total_upcoming": 0,
                        "last_session_id": False,
                        "last_session_date": False,
                        "next_session_id": False,
                        "next_session_date": False,
                    }
                )
                continue

            base_domain = partner._base_session_domain()
            if since_dt:
                base_domain += [("start_datetime", ">=", since_dt)]

            # Hitung per state via read_group
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

            # Last & next ambil dari compute (sudah ada di cache)
            results.append(
                {
                    "patient_id": partner.id,
                    "patient_name": partner.display_name,
                    "company_id": partner.company_id.id if partner.company_id else False,
                    "total_sessions": total_sessions,
                    "total_done": total_done,
                    "total_no_show": total_no_show,
                    "total_cancelled": total_cancelled,
                    "total_upcoming": total_upcoming,
                    "last_session_id": partner.last_session_id.id
                    if partner.last_session_id
                    else False,
                    "last_session_date": partner.last_session_date,
                    "next_session_id": partner.next_session_id.id
                    if partner.next_session_id
                    else False,
                    "next_session_date": partner.next_session_date,
                }
            )

        return results if len(self) > 1 else (results[0] if results else {})
