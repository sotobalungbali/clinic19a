
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ClinicRoomAvailability(models.Model):
    """
    Slot/Shift Ketersediaan Ruangan (Calendar-Ready)

    Fitur utama:
    - Definisi slot ketersediaan ruangan (start/stop).
    - Penanda shift (pagi/siang/malam/custom) beserta color hint.
    - Validasi overlap per ruangan.
    - Template & Recurrence (mingguan/bulanan) → generator massal slot actual.
    - Heuristik pengecekan tabrakan ringan dengan Booking (opsional).
    - Smart actions: activate/archive, generate from template, open bookings.

    Integrasi lintas modul:
    - clinic_room_device:
        • clinic.room (room_id) ← relasi inti
    - clinic_booking (opsional):
        • booking.booking (untuk cek tabrakan ringan + action open)
    - mail.thread: audit perubahan konfigurasi.

    Best Practices:
    - Slot ketersediaan TIDAK otomatis menghapus booking. Booking tetap sumber kebenaran jadwal pasien.
    - Gunakan slot availability sebagai "kapasitas buka" ruangan agar Booking/Queue bisa melakukan suggest.
    """

    _name = "clinic.room.availability"
    _description = "Clinic Room Availability"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "room_id, start, id"

    # --------------------------
    # Identity
    # --------------------------
    name = fields.Char(
        string="Reference",
        help="Judul singkat slot (opsional). Jika kosong, akan terisi otomatis dari shift & tanggal.",
        tracking=True,
    )
    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda s: s.env.company,
        index=True,
        required=True,
    )

    # --------------------------
    # Core
    # --------------------------
    room_id = fields.Many2one(
        "clinic.room",
        string="Room",
        required=True,
        index=True,
        ondelete="cascade",
        tracking=True,
    )

    start = fields.Datetime(
        string="Start",
        required=True,
        tracking=True,
        help="Waktu mulai slot.",
    )
    stop = fields.Datetime(
        string="Stop",
        required=True,
        tracking=True,
        help="Waktu berakhir slot.",
    )

    shift = fields.Selection(
        selection=[
            ("morning", "Morning"),
            ("afternoon", "Afternoon"),
            ("evening", "Evening"),
            ("custom", "Custom"),
        ],
        string="Shift",
        default="custom",
        tracking=True,
        help="Penanda shift untuk mempermudah grouping & visualisasi.",
    )
    color = fields.Integer(
        string="Color",
        help="Warna untuk tampilan calendar/kanban (0..11).",
    )

    capacity_hint = fields.Integer(
        string="Capacity Hint",
        default=0,
        help="Opsional. Hint kapasitas tambahan untuk modul booking (0 = abaikan).",
    )

    # --------------------------
    # Template & Recurrence
    # --------------------------
    is_template = fields.Boolean(
        string="Template",
        help="Centang jika record ini adalah TEMPLATE (untuk generator), bukan slot aktual.",
    )
    recurrence = fields.Selection(
        selection=[
            ("none", "None"),
            ("weekly", "Weekly"),
            ("monthly_date", "Monthly (by Date)"),
            ("monthly_weekday", "Monthly (by Weekday)"),
        ],
        string="Recurrence",
        default="none",
        help="Pola pengulangan untuk generator slot.",
    )
    interval = fields.Integer(
        string="Interval",
        default=1,
        help="Setiap berapa minggu/bulan diulang (untuk recurrence != none).",
    )
    byweekday = fields.Selection(
        selection=[
            ("0", "Monday"),
            ("1", "Tuesday"),
            ("2", "Wednesday"),
            ("3", "Thursday"),
            ("4", "Friday"),
            ("5", "Saturday"),
            ("6", "Sunday"),
        ],
        string="By Weekday",
        help="Untuk weekly atau monthly (by weekday).",
    )
    bysetpos = fields.Selection(
        selection=[
            ("1", "1st"),
            ("2", "2nd"),
            ("3", "3rd"),
            ("4", "4th"),
            ("-1", "Last"),
        ],
        string="By Set Position",
        help="Untuk monthly (by weekday), contoh: 2nd Tuesday, Last Friday.",
    )
    until = fields.Date(
        string="Until",
        help="Tanggal akhir pengulangan (generator berhenti pada tanggal ini).",
    )

    # --------------------------
    # State / Computed
    # --------------------------
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("active", "Active"),
            ("archived", "Archived"),
        ],
        default="active",
        string="Status",
        tracking=True,
    )
    in_effect_now = fields.Boolean(
        string="In Effect (Now)",
        compute="_compute_in_effect_now",
        store=False,
        help="True jika now berada di antara start..stop & slot active.",
    )
    label = fields.Char(
        string="Label",
        compute="_compute_label",
        store=False,
        help="Label otomatis untuk tampilan calendar.",
    )

    # conflict_with_booking = fields.Boolean(
    #     string="Conflict w/ Booking",
    #     compute="_compute_conflict_with_booking",
    #     store=False,
    #     help="True jika terdeteksi ada booking overlap pada slot ini (cek ringan & opsional).",
    # )
    # booking_overlap_count = fields.Integer(
    #     string="Overlapped Bookings",
    #     compute="_compute_conflict_with_booking",
    #     store=False,
    # )

    # --------------------------
    # Constraints
    # --------------------------
        # Odoo 19 table constraints
    _start_lt_stop = models.Constraint(
        'CHECK (start < stop)',
        'Start harus lebih kecil dari Stop.',
    )

    # --------------------------
    # Compute
    # --------------------------
    @api.depends("start", "stop", "state")
    def _compute_in_effect_now(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.in_effect_now = rec.state == "active" and rec.start and rec.stop and rec.start <= now <= rec.stop

    @api.depends("name", "shift", "start", "stop")
    def _compute_label(self):
        for rec in self:
            if rec.name:
                rec.label = rec.name
            else:
                # contoh label: "Morning (09:00–12:00)"
                if rec.shift != "custom" and rec.start and rec.stop:
                    t1 = fields.Datetime.context_timestamp(self, rec.start).strftime("%H:%M")
                    t2 = fields.Datetime.context_timestamp(self, rec.stop).strftime("%H:%M")
                    rec.label = _("%s (%s–%s)") % (rec._get_shift_display(), t1, t2)
                else:
                    rec.label = False

    def _get_shift_display(self):
        mapping = dict(self._fields["shift"].selection)
        return mapping.get(self.shift, "Custom")

    # def _get_booking_model(self):
    #     return "booking.booking" if "booking.booking" in self.env else False

    # @api.depends("room_id", "start", "stop")
    # def _compute_conflict_with_booking(self):
    #     BookingModel = self._get_booking_model()
    #     for rec in self:
    #         rec.conflict_with_booking = False
    #         rec.booking_overlap_count = 0
    #         if not BookingModel or not rec.room_id or not rec.start or not rec.stop:
    #             continue
    #         # Heuristik overlap dengan booking (jika modul ada):
    #         # booking overlap jika: booking.start <= slot.stop AND booking.end >= slot.start
    #         domain = [
    #             ("room_id", "=", rec.room_id.id),
    #             ("state", "not in", ["cancelled", "canceled", "cancel"]),
    #             ("start_datetime", "<=", rec.stop),
    #             ("end_datetime", ">=", rec.start),
    #         ]
    #         cnt = self.env[BookingModel].sudo().search_count(domain)
    #         rec.booking_overlap_count = cnt
    #         rec.conflict_with_booking = cnt > 0

    # --------------------------
    # ORM
    # --------------------------
    @api.model_create_multi
    def create(self, vals_list):
        recs = self.browse()
        for vals in vals_list:
            # Default company dari room jika tidak diisi
            if not vals.get("company_id") and vals.get("room_id"):
                vals["company_id"] = self.env["clinic.room"].browse(vals["room_id"]).company_id.id

            # Auto name jika kosong
            if not vals.get("name"):
                vals["name"] = self._build_default_name(vals)

            # Validasi overlap per room (hanya untuk slot active)
            room = self.env["clinic.room"].browse(vals.get("room_id"))
            start = fields.Datetime.to_datetime(vals.get("start"))
            stop = fields.Datetime.to_datetime(vals.get("stop"))
            state = vals.get("state") or "active"
            if room and start and stop and state == "active":
                self._guard_overlap(room.id, start, stop)

            rec = super().create(vals)
            recs |= rec
        return recs

    def write(self, vals):
        for rec in self:
            # Auto name bila dikosongkan
            if vals.get("name") in (None, False):
                vals["name"] = rec._build_default_name(vals)

            # Validasi overlap jika ada perubahan room/start/stop/state → active
            n_room_id = vals.get("room_id", rec.room_id.id)
            n_start = fields.Datetime.to_datetime(vals.get("start")) if vals.get("start") else rec.start
            n_stop = fields.Datetime.to_datetime(vals.get("stop")) if vals.get("stop") else rec.stop
            n_state = vals.get("state", rec.state)
            if n_state == "active" and n_room_id and n_start and n_stop:
                self._guard_overlap(n_room_id, n_start, n_stop, self_id=rec.id)

        return super().write(vals)

    # --------------------------
    # Helpers
    # --------------------------
    def _build_default_name(self, vals):
        """
        Nama default dari shift & tanggal. Contoh:
        - "Morning @ 2025-10-10"
        - "Custom @ 2025-10-10 09:00"
        """
        shift = vals.get("shift") or self.shift or "custom"
        start = fields.Datetime.to_datetime(vals.get("start") or self.start)
        if not start:
            return False
        d = fields.Datetime.context_timestamp(self, start).strftime("%Y-%m-%d")
        t = fields.Datetime.context_timestamp(self, start).strftime("%H:%M")
        if shift != "custom":
            return "%s @ %s" % (dict(self._fields["shift"].selection).get(shift, "Shift"), d)
        return "Custom @ %s %s" % (d, t)

    def _guard_overlap(self, room_id, start, stop, self_id=None):
        """
        Pastikan tidak ada 2 availability ACTIVE yang overlap pada room yang sama.
        Overlap rule: other.start <= stop AND other.stop >= start
        """
        domain = [
            ("room_id", "=", room_id),
            ("state", "=", "active"),
            ("start", "<=", stop),
            ("stop", ">=", start),
        ]
        overlapped = self.search(domain)
        if self_id:
            overlapped = overlapped.filtered(lambda r: r.id != self_id)
        if overlapped:
            raise ValidationError(_("Terdapat slot availability lain yang overlap di ruangan ini."))

    # --------------------------
    # Actions
    # --------------------------
    def action_set_active(self):
        for rec in self:
            rec.write({"state": "active"})
            rec._guard_overlap(rec.room_id.id, rec.start, rec.stop, self_id=rec.id)

    def action_set_archived(self):
        self.write({"state": "archived"})

    def action_set_draft(self):
        self.write({"state": "draft"})

    def action_open_bookings(self):
        """Buka daftar booking yang overlap dengan slot ini (jika modul booking tersedia)."""
        self.ensure_one()
        BookingModel = self._get_booking_model()
        if not BookingModel:
            raise UserError(_("Modul Booking belum terpasang."))
        domain = [
            ("room_id", "=", self.room_id.id),
            ("state", "not in", ["cancelled", "canceled", "cancel"]),
            ("start_datetime", "<=", self.stop),
            ("end_datetime", ">=", self.start),
        ]
        return {
            "name": _("Overlapped Bookings"),
            "type": "ir.actions.act_window",
            "res_model": BookingModel,
            "view_mode": "calendar,tree,form",
            "domain": domain,
            "context": {"default_room_id": self.room_id.id},
        }

    # --------------------------
    # Recurrence Generator
    # --------------------------
    def _get_generator_bounds(self, date_from, date_to):
        """
        Hitung batas waktu generator memperhatikan 'until' template jika ada.
        """
        self.ensure_one()
        df = fields.Date.to_date(date_from)
        dt = fields.Date.to_date(date_to)
        if self.until and self.until < dt:
            dt = self.until
        if df > dt:
            raise UserError(_("Rentang tanggal generator tidak valid."))
        return df, dt

    def _weekly_iter_dates(self, start_date, end_date, weekday_int, interval_weeks):
        """
        Hasilkan tanggal untuk recurrence mingguan berdasarkan weekday & interval.
        weekday_int: 0=Mon ... 6=Sun
        """
        from datetime import timedelta

        # Geser start_date ke weekday yang dituju
        delta = (weekday_int - start_date.weekday()) % 7
        cur = start_date + timedelta(days=delta)

        while cur <= end_date:
            yield cur
            cur += timedelta(weeks=max(int(interval_weeks or 1), 1))

    def _monthly_by_date_iter(self, start_date, end_date, day, interval_months):
        """
        Bulanan berdasarkan 'tanggal' (day).
        """
        from dateutil.relativedelta import relativedelta

        cur = start_date.replace(day=1)
        # Langsung lompat ke bulan & tanggal yang sesuai >= start_date
        while cur <= end_date:
            try:
                candidate = cur.replace(day=day)
            except ValueError:
                # tanggal tidak valid di bulan tsb (mis. 31 di Feb), lewati
                cur = cur + relativedelta(months=+max(int(interval_months or 1), 1))
                continue
            if candidate >= start_date and candidate <= end_date:
                yield candidate
            cur = cur + relativedelta(months=+max(int(interval_months or 1), 1))

    def _monthly_by_weekday_iter(self, start_date, end_date, weekday_int, setpos, interval_months):
        """
        Bulanan berdasarkan (ke-n) weekday, contoh: 2nd Tuesday, Last Friday.
        setpos: 1..4 atau -1
        """
        from calendar import monthcalendar
        from dateutil.relativedelta import relativedelta

        cur = start_date.replace(day=1)
        while cur <= end_date:
            cal = monthcalendar(cur.year, cur.month)  # list of weeks, setiap minggu = 7 hari, 0 jika tidak termasuk bulan
            days = [week[weekday_int] for week in cal if week[weekday_int] != 0]
            if days:
                if setpos == -1:
                    day = days[-1]
                else:
                    idx = max(min(int(setpos or 1), 4), 1) - 1
                    if idx < len(days):
                        day = days[idx]
                    else:
                        day = None
                if day:
                    candidate = cur.replace(day=day)
                    if candidate >= start_date and candidate <= end_date:
                        yield candidate
            cur = cur + relativedelta(months=+max(int(interval_months or 1), 1))

    def action_generate_from_template(self, date_from, date_to):
        """
        Generate slot ACTUAL dari record TEMPLATE sesuai recurrence.
        - Hanya bisa dipanggil pada record is_template=True.
        - Generator tidak menimpa slot existing; validasi overlap tetap berlaku.
        """
        self.ensure_one()
        if not self.is_template:
            raise UserError(_("Hanya template yang dapat dipakai untuk generator."))

        df, dt = self._get_generator_bounds(date_from, date_to)
        if self.recurrence == "none":
            raise UserError(_("Template ini tidak memiliki pengulangan (recurrence)."))

        # Hitung jam/menit dari template (durasi)
        if not self.start or not self.stop:
            raise UserError(_("Template harus memiliki Start & Stop."))
        duration = self.stop - self.start
        if duration.total_seconds() <= 0:
            raise UserError(_("Durasi template tidak valid."))

        created = self.env[self._name]
        # Konversi ke tanggal (tanpa waktu)
        start_date = df
        end_date = dt

        if self.recurrence == "weekly":
            if self.byweekday is None:
                raise UserError(_("Weekly recurrence membutuhkan By Weekday."))
            weekday_int = int(self.byweekday)
            for d in self._weekly_iter_dates(start_date, end_date, weekday_int, self.interval):
                start_dt = fields.Datetime.combine(d, self.start.time())
                stop_dt = start_dt + duration
                created |= self._create_one_generated_slot(start_dt, stop_dt)

        elif self.recurrence == "monthly_date":
            day = self.start.day  # default ambil tanggal dari template start
            for d in self._monthly_by_date_iter(start_date, end_date, day, self.interval):
                start_dt = fields.Datetime.combine(d, self.start.time())
                stop_dt = start_dt + duration
                created |= self._create_one_generated_slot(start_dt, stop_dt)

        elif self.recurrence == "monthly_weekday":
            if self.byweekday is None or not self.bysetpos:
                raise UserError(_("Monthly (by weekday) membutuhkan By Weekday & By Set Position."))
            weekday_int = int(self.byweekday)
            setpos = int(self.bysetpos)
            for d in self._monthly_by_weekday_iter(start_date, end_date, weekday_int, setpos, self.interval):
                start_dt = fields.Datetime.combine(d, self.start.time())
                stop_dt = start_dt + duration
                created |= self._create_one_generated_slot(start_dt, stop_dt)

        # Kembalikan action untuk melihat hasil
        return {
            "name": _("Generated Availability"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.room.availability",
            "view_mode": "calendar,tree,form",
            "domain": [("id", "in", created.ids)],
        }

    def _create_one_generated_slot(self, start_dt, stop_dt):
        """
        Buat satu slot actual dari template (state=active, is_template=False),
        tetap hormati validasi overlap.
        """
        vals = {
            "company_id": self.company_id.id,
            "room_id": self.room_id.id,
            "start": start_dt,
            "stop": stop_dt,
            "shift": self.shift,
            "color": self.color,
            "capacity_hint": self.capacity_hint,
            "state": "active",
            "is_template": False,
            "name": False,  # auto build
        }
        # validasi overlap dilakukan di create()
        rec = self.create([vals])
        return rec

    # --------------------------
    # Public Helper (API) untuk modul lain
    # --------------------------
    @api.model
    def find_next_available(self, room_id, from_dt=None):
        """
        Kembalikan slot ketersediaan berikutnya (recordset 1) dari room tertentu,
        dengan start >= from_dt (default: now), state=active.
        """
        if not room_id:
            return self.env[self._name]
        start_from = from_dt or fields.Datetime.now()
        rec = self.search([
            ("room_id", "=", room_id),
            ("state", "=", "active"),
            ("start", ">=", start_from),
        ], order="start asc", limit=1)
        return rec
