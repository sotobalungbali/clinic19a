
# -*- coding: utf-8 -*-
# ClinicOne - Clinical Staff (Nurse & Therapist) Management
# File: staff_availability.py
#
# Catatan (ID):
# - Menyediakan 2 model:
#   1) clinic.staff.availability  -> pola ketersediaan (single/recurring)
#   2) clinic.staff.availability.occurrence -> kejadian konkret hasil ekspansi pola
# - Dibuat agar:
#   * Bisa dipakai pada Calendar view untuk perencanaan.
#   * Terintegrasi dengan roster/assignment (deteksi konflik waktu).
#   * Mendukung recurring sederhana (daily/weekly/monthly) dan minggu terpilih.
# - Semua label/help dalam Bahasa Inggris; komentar penjelas menggunakan Bahasa Indonesia.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


# ============================================================
# Helpers / Utilities
# ============================================================

def _overlap_domain(start_dt, end_dt):
    """Domain overlap standar: (start < end) & (stop > start)."""
    return [("start", "<", end_dt), ("stop", ">", start_dt)]


def _ensure_tz(env):
    """Ambil TZ efektif dari context user; fallback UTC."""
    tz = env.user.tz or env.context.get("tz") or "UTC"
    return tz


# ============================================================
# Availability Pattern (Master)
# ============================================================
class ClinicStaffAvailability(models.Model):
    _name = "clinic.staff.availability"
    _description = "Staff Availability"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "display_name"
    _order = "staff_id, start, stop, id desc"

    # -------------------------
    # Identitas & relasi utama
    # -------------------------
    name = fields.Char(
        string="Title",
        help="Short title for this availability entry, e.g., 'Morning Availability', 'Training'.",
        tracking=True,
        translate=True,
    )

    staff_id = fields.Many2one(
        "clinic.staff",
        string="Staff",
        required=True,
        index=True,
        ondelete="cascade",
        tracking=True,
        help="Staff member for whom this availability is defined.",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="staff_id.company_id",
        store=True,
        readonly=True,
        help="Company of the staff member.",
    )

    # branch_id = fields.Many2one(
    #     "clinic.branch",
    #     string="Branch",
    #     help="Operational branch context for this availability.",
    # )

    # ----------------------------------
    # Waktu dasar (single occurrence)
    # ----------------------------------
    start = fields.Datetime(
        string="Start",
        required=True,
        index=True,
        tracking=True,
        help="Start datetime of the availability window (stored in UTC).",
    )

    stop = fields.Datetime(
        string="Stop",
        required=True,
        index=True,
        tracking=True,
        help="End datetime of the availability window (stored in UTC).",
    )

    duration_hours = fields.Float(
        string="Duration (Hours)",
        compute="_compute_duration_hours",
        help="Duration in hours for this availability window.",
        store=False,
    )

    # ----------------------------------
    # Klasifikasi ketersediaan
    # ----------------------------------
    availability_type = fields.Selection(
        selection=[
            ("available", "Available"),
            ("standby", "Standby"),
            ("unavailable", "Unavailable"),
            ("leave", "Leave"),
            ("training", "Training"),
        ],
        string="Type",
        required=True,
        default="available",
        index=True,
        help="Availability classification that may impact scheduling and conflicts.",
        tracking=True,
    )

    is_blocking = fields.Boolean(
        string="Blocking",
        compute="_compute_is_blocking",
        store=True,
        help="If enabled, this window blocks scheduling (e.g., Unavailable, Leave).",
    )

    color = fields.Integer(
        string="Color",
        help="Optional color index for calendar views.",
    )

    # ----------------------------------
    # Recurrence (opsional)
    # ----------------------------------
    recurrency = fields.Boolean(
        string="Recurring",
        default=False,
        help="Enable to repeat this availability using a recurrence rule.",
        tracking=True,
    )

    rrule_type = fields.Selection(
        selection=[
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
        ],
        string="Repeat Every",
        default="weekly",
        help="Recurrence frequency.",
        tracking=True,
    )

    interval = fields.Integer(
        string="Interval",
        default=1,
        help="Repeat every N (days/weeks/months) depending on frequency.",
    )

    # Weekly flags (dipakai bila rrule_type == weekly)
    w_mon = fields.Boolean("Mon", default=False)
    w_tue = fields.Boolean("Tue", default=False)
    w_wed = fields.Boolean("Wed", default=False)
    w_thu = fields.Boolean("Thu", default=False)
    w_fri = fields.Boolean("Fri", default=False)
    w_sat = fields.Boolean("Sat", default=False)
    w_sun = fields.Boolean("Sun", default=False)

    # Akhiran recurrence
    recur_end_type = fields.Selection(
        selection=[("forever", "No End"), ("until", "Until Date"), ("count", "Occurrences Count")],
        string="End",
        default="until",
        help="Controls when the recurrence stops.",
    )

    recur_until = fields.Date(
        string="Until",
        help="Date (inclusive) when recurrence should stop.",
    )

    recur_count = fields.Integer(
        string="Occurrences",
        help="Number of occurrences to generate (including the first pattern window).",
    )

    # ----------------------------------
    # Smart info & tampilan
    # ----------------------------------
    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
        help="Composite label: Staff - Type [Start → Stop].",
    )

    next_occurrence_start = fields.Datetime(
        string="Next Occurrence Start",
        compute="_compute_next_occurrence",
        store=False,
        help="Next start datetime for this availability pattern.",
    )

    # ----------------------------------
    # Konflik dengan Roster / Assignment
    # ----------------------------------
    # conflict_roster_count = fields.Integer(
    #     string="Roster Conflicts",
    #     compute="_compute_conflicts",
    #     store=False,
    #     help="Number of roster entries that overlap with blocking windows.",
    # )

    # conflict_assignment_count = fields.Integer(
    #     string="Assignment Conflicts",
    #     compute="_compute_conflicts",
    #     store=False,
    #     help="Number of assignments that overlap with blocking windows.",
    # )

    # ----------------------------------
    # Status record
    # ----------------------------------
    active = fields.Boolean(
        string="Active",
        default=True,
        help="If unchecked, this availability entry will be hidden from most views.",
    )

    notes = fields.Text(
        string="Notes",
        help="Additional description or constraints for this availability.",
    )

    _check_start_before_stop = models.Constraint(
        'CHECK (start < stop)',
        'The Start must be earlier than the Stop.',
    )

    # -------------------------
    # Compute Methods
    # -------------------------
    @api.depends("availability_type")
    def _compute_is_blocking(self):
        """Default: Unavailable/Leave bersifat blocking; lainnya tidak."""
        for rec in self:
            rec.is_blocking = rec.availability_type in ("unavailable", "leave")

    def _compute_duration_hours(self):
        for rec in self:
            rec.duration_hours = 0.0
            if rec.start and rec.stop:
                delta = rec.stop - rec.start
                rec.duration_hours = (delta.total_seconds() / 3600.0)

    @api.depends("name", "staff_id.display_name", "availability_type", "start", "stop")
    def _compute_display_name(self):
        """Bangun label tampilan: Staff - Type [Start → Stop]."""
        # NB: Gunakan ternary 'A if cond else B' (bukan 'cond and A else B')
        for rec in self:
            parts = []
            if rec.staff_id:
                parts.append(rec.staff_id.display_name or _("(No Staff)"))
            if rec.availability_type:
                type_label = dict(self._fields['availability_type'].selection).get(
                    rec.availability_type, rec.availability_type
                )
                parts.append(f"- {type_label}")
            if rec.start and rec.stop:
                parts.append(f"[{fields.Datetime.to_string(rec.start)} → {fields.Datetime.to_string(rec.stop)}]")
            base = " ".join(parts) if parts else _("Staff Availability")
            rec.display_name = f"{rec.name} • {base}" if rec.name else base

    def _compute_next_occurrence(self):
        """Hitung occurrence berikutnya berdasarkan pola (non-stored)."""
        for rec in self:
            rec.next_occurrence_start = False
            # Jika tidak recurring, next occurrence = start jika start >= now
            now = fields.Datetime.now()
            if not rec.recurrency:
                rec.next_occurrence_start = rec.start if rec.start and rec.start >= now else False
                continue
            # Untuk recurring, cari kemunculan >= now (bounded until).
            occ = rec._iter_occurrences(now, limit=1)
            rec.next_occurrence_start = occ[0][0] if occ else False

    # -------------------------
    # Constraints (Python)
    # -------------------------
    @api.constrains("start", "stop")
    def _check_datetime_order(self):
        """Validasi start < stop; cek overlap basic antar pattern blocking di waktu yang sama."""
        for rec in self:
            if rec.start and rec.stop and rec.stop <= rec.start:
                raise ValidationError(_("End datetime must be later than start datetime."))

        # Cegah overlap pattern blocking lain pada staff yang sama (hanya pola non-recurring).
        # Pattern recurring akan dievaluasi saat ekspansi occurrence.
        for rec in self.filtered(lambda r: r.is_blocking and not r.recurrency):
            domain = [
                ("id", "!=", rec.id),
                ("staff_id", "=", rec.staff_id.id),
                ("active", "=", True),
                ("is_blocking", "=", True),
            ] + _overlap_domain(rec.start, rec.stop)
            clash = self.search_count(domain)
            if clash:
                raise ValidationError(_("This blocking availability overlaps with another blocking window."))

    # -------------------------
    # Konflik dengan roster/assignment
    # -------------------------
    # Jika tidak blocking, treat konflik = 0
    # def _compute_conflicts(self):
    #     """Hitung konflik dengan roster/assignment (hanya hitung kasar)."""
    #     Roster = self.env.get("clinic.staff.roster")
    #     Assign = self.env.get("clinic.staff.assignment")
    #     for rec in self:
            
    #         if not rec.is_blocking:
    #             rec.conflict_roster_count = 0
    #             rec.conflict_assignment_count = 0
    #             continue
    #         rec.conflict_roster_count = 0
    #         rec.conflict_assignment_count = 0

    #         if Roster:
    #             domain = [
    #                 ("staff_id", "=", rec.staff_id.id),
    #             ] + _overlap_domain(rec.start, rec.stop)
    #             try:
    #                 rec.conflict_roster_count = Roster.sudo().search_count(domain)
    #             except Exception:
    #                 _logger.debug("Roster conflict check failed for availability %s", rec.id)

    #         if Assign:
    #             domain = [
    #                 ("staff_id", "=", rec.staff_id.id),
    #                 ("state", "!=", "closed"),
    #             ] + _overlap_domain(rec.start, rec.stop)
    #             try:
    #                 rec.conflict_assignment_count = Assign.sudo().search_count(domain)
    #             except Exception:
    #                 _logger.debug("Assignment conflict check failed for availability %s", rec.id)

    # -------------------------
    # Occurrence Generation
    # -------------------------
    def _weekly_days_selected(self):
        """Kembalikan set indeks hari (0=Mon..6=Sun) dari flag mingguan."""
        self.ensure_one()
        days = []
        if self.w_mon: days.append(0)
        if self.w_tue: days.append(1)
        if self.w_wed: days.append(2)
        if self.w_thu: days.append(3)
        if self.w_fri: days.append(4)
        if self.w_sat: days.append(5)
        if self.w_sun: days.append(6)
        return set(days)

    def _iter_occurrences(self, start_from, limit=0, date_to=None):
        """Hasilkan list tuple (start, stop) untuk kemunculan >= start_from.
        - limit: jika >0 batasi jumlah kemunculan.
        - date_to: batasi tanggal akhir (UTC).
        """
        self.ensure_one()
        if not self.start or not self.stop:
            return []
        if not self.recurrency:
            # Satu kemunculan saja bila masih di masa depan
            if self.stop >= start_from:
                return [(self.start, self.stop)]
            return []

        occurrences = []
        base_start = self.start
        base_stop = self.stop
        delta = base_stop - base_start
        freq = self.rrule_type or "weekly"
        step = max(1, int(self.interval or 1))

        # Batas akhir berdasarkan pengaturan end
        until = None
        if self.recur_end_type == "until" and self.recur_until:
            # Gunakan pukul 23:59:59 di zona UTC untuk inclusive
            until = datetime.combine(self.recur_until, datetime.max.time())
        elif self.recur_end_type == "count" and self.recur_count:
            # total occurrences (termasuk base)
            pass  # akan dikontrol via limit jika belum diset

        # Jika weekly tanpa hari terpilih, default ke weekday base_start
        weekly_days = self._weekly_days_selected() if freq == "weekly" else set()
        if freq == "weekly" and not weekly_days:
            weekly_days = {base_start.weekday()}

        # Mulai iterasi dari base_start sampai memenuhi syarat
        # Geser pointer ke occurrence >= start_from
        current_start = base_start
        current_stop = base_stop

        # Fungsi bantu geser step
        def step_forward(dt, how_many=1):
            if freq == "daily":
                return dt + timedelta(days=step * how_many)
            if freq == "weekly":
                return dt + timedelta(weeks=step * how_many)
            if freq == "monthly":
                # gunakan relativedelta bila tersedia
                try:
                    from dateutil.relativedelta import relativedelta
                    return dt + relativedelta(months=step * how_many)
                except Exception:
                    # fallback kasar: 30 hari x step
                    return dt + timedelta(days=30 * step * how_many)
            # default weekly
            return dt + timedelta(weeks=step * how_many)

        # Geser ke depan sampai window tidak seluruhnya di masa lalu
        # Untuk weekly, kita iterasi per minggu lalu isi hari terpilih
        # Untuk daily/monthly, sederhana per step.
        produced = 0
        # Optimisasi: lompati batch besar untuk mencapai start_from (khusus daily/weekly/monthly)
        if start_from > current_stop:
            # Perkirakan lompatan kasar
            if freq == "daily":
                days_diff = (start_from - current_start).days
                jumps = max(0, (days_diff // step) - 1)
                if jumps:
                    current_start = step_forward(current_start, jumps)
                    current_stop = current_start + delta
            elif freq == "weekly":
                weeks_diff = (start_from - current_start).days // 7
                jumps = max(0, (weeks_diff // step) - 1)
                if jumps:
                    current_start = step_forward(current_start, jumps)
                    current_stop = current_start + delta
            elif freq == "monthly":
                # tidak mudah diperkirakan tanpa relativedelta; biarkan iterasi bertahap
                pass

        while True:
            if freq == "weekly":
                # generate hari-hari terpilih dalam minggu saat ini
                # anchor minggu = current_start (hari apapun), geser ke Senin minggu itu
                anchor = current_start - timedelta(days=current_start.weekday())
                for day_idx in sorted(list(weekly_days)):
                    occ_start = anchor + timedelta(days=day_idx, hours=current_start.hour, minutes=current_start.minute, seconds=current_start.second)
                    # "occ_stop" mengikuti delta durasi asli, bukan hanya jam
                    # Agar presisi, ambil waktu start detil dari base_start
                    occ_start = occ_start.replace(hour=base_start.hour, minute=base_start.minute, second=base_start.second, microsecond=base_start.microsecond)
                    occ_stop = occ_start + delta

                    # Lewati occurrence yang berakhir sebelum start_from
                    if occ_stop <= start_from:
                        continue
                    # Batas until
                    if until and occ_start > until:
                        return occurrences
                    # Batas date_to
                    if date_to and occ_start > date_to:
                        return occurrences

                    occurrences.append((occ_start, occ_stop))
                    produced += 1
                    if limit and produced >= limit:
                        return occurrences

                # geser ke minggu berikutnya sesuai step
                current_start = step_forward(current_start, 1)
                current_stop = current_start + delta
            else:
                # daily / monthly
                if current_stop > start_from:
                    if until and current_start > until:
                        return occurrences
                    if date_to and current_start > date_to:
                        return occurrences
                    occurrences.append((current_start, current_stop))
                    produced += 1
                    if limit and produced >= limit:
                        return occurrences
                # maju ke occurrence berikutnya
                current_start = step_forward(current_start, 1)
                current_stop = current_start + delta

            # Batas count (termasuk base)
            if self.recur_end_type == "count" and self.recur_count:
                if produced >= max(0, self.recur_count):
                    return occurrences

    # -------------------------
    # Kejadian (occurrence) API
    # -------------------------
    def expand_occurrences(self, date_from=None, date_to=None, limit=0, replace=False):
        """Ekspansi pola menjadi occurrences pada rentang waktu.
        - date_from/date_to dalam UTC; jika kosong, gunakan [now, now + 8 weeks].
        - limit: batasi jumlah occurrence yang dibuat (0=tak terbatas).
        - replace: jika True, hapus occurrence existing di rentang sebelum membuat ulang.
        """
        Occ = self.env["clinic.staff.availability.occurrence"].sudo()
        now = fields.Datetime.now()
        date_from = date_from or now
        date_to = date_to or (now + timedelta(weeks=8))

        created_total = 0
        for rec in self:
            # Optional replace: hapus occurrence existing di rentang
            if replace:
                dom = [
                    ("availability_id", "=", rec.id),
                    ("start", ">=", date_from),
                    ("start", "<=", date_to),
                ]
                old = Occ.search(dom)
                old.unlink()

            # Ambil daftar occurrence dari pola
            occ_list = []
            if rec.recurrency:
                occ_list = rec._iter_occurrences(start_from=date_from, limit=limit, date_to=date_to)
            else:
                # Non recurring: hanya jika overlap rentang [date_from, date_to]
                if rec.stop > date_from and rec.start < date_to:
                    occ_list = [(rec.start, rec.stop)]

            # Buat record occurrence
            vals_batch = []
            for start_dt, stop_dt in occ_list:
                occurrence_vals = {
                    "availability_id": rec.id,
                    "staff_id": rec.staff_id.id,
                    "company_id": rec.company_id.id,
                    "availability_type": rec.availability_type,
                    "is_blocking": rec.is_blocking,
                    "start": start_dt,
                    "stop": stop_dt,
                    "state": "planned",
                    "name": rec.name or False,
                    "color": rec.color or 0,
                }
                if "branch_id" in rec._fields and rec.branch_id:
                    occurrence_vals["branch_id"] = rec.branch_id.id
                vals_batch.append(occurrence_vals)
                if limit and len(vals_batch) >= limit:
                    break
            if vals_batch:
                Occ.create(vals_batch)
                created_total += len(vals_batch)

        return created_total

    # -------------------------
    # Actions (UI)
    # -------------------------
    def action_expand_next_8_weeks(self):
        """Ekspansi cepat pola ke 8 minggu ke depan."""
        created = self.expand_occurrences(limit=0, replace=False)
        msg = _("Generated %s occurrences for the next planning window.") % created
        for rec in self:
            rec.message_post(body=msg)
        return True

    def action_open_occurrences(self):
        """Buka daftar occurrence untuk pola ini."""
        self.ensure_one()
        return {
            "name": _("Availability Occurrences"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.staff.availability.occurrence",
            "view_mode": "calendar,list,form",
            "domain": [("availability_id", "=", self.id)],
            "context": {"default_availability_id": self.id, "search_default_my_staff": 0},
        }

    def action_open_roster_conflicts(self):
        """Buka roster yang berkonflik untuk pola ini."""
        self.ensure_one()
        Roster = self.env.get("clinic.staff.roster")
        if not Roster:
            return False
        return {
            "name": _("Roster Conflicts"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.staff.roster",
            "view_mode": "calendar,list,form,gantt",
            "domain": [
                ("staff_id", "=", self.staff_id.id),
            ] + _overlap_domain(self.start, self.stop),
            "context": {},
        }

    def action_open_assignment_conflicts(self):
        """Buka assignment yang berkonflik untuk pola ini."""
        self.ensure_one()
        Assign = self.env.get("clinic.staff.assignment")
        if not Assign:
            return False
        return {
            "name": _("Assignment Conflicts"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.staff.assignment",
            "view_mode": "list,form,kanban",
            "domain": [
                ("staff_id", "=", self.staff_id.id),
                ("state", "!=", "closed"),
            ] + _overlap_domain(self.start, self.stop),
            "context": {},
        }

    # -------------------------
    # CRUD overrides
    # -------------------------
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        # Jadwalkan activity jika entry blocking dan beririsan dengan roster
        Roster = self.env.get("clinic.staff.roster")
        for rec in recs.filtered("is_blocking"):
            try:
                if Roster:
                    dom = [("staff_id", "=", rec.staff_id.id)] + _overlap_domain(rec.start, rec.stop)
                    if Roster.sudo().search_count(dom):
                        rec.activity_schedule(
                            "mail.mail_activity_data_todo",
                            summary=_("Blocking availability overlaps with roster"),
                            note=_("Please resolve conflicts between roster and blocking availability window."),
                        )
            except Exception:
                _logger.debug("Skipped scheduling conflict activity for availability %s", rec.id)
        return recs

    def write(self, vals):
        res = super().write(vals)
        # Re-check conflicts after time/type changes
        if {"start", "stop", "availability_type"}.intersection(vals.keys()):
            for rec in self:
                if not rec.is_blocking:
                    continue
                Roster = self.env.get("clinic.staff.roster")
                if Roster:
                    dom = [("staff_id", "=", rec.staff_id.id)] + _overlap_domain(rec.start, rec.stop)
                    if Roster.sudo().search_count(dom):
                        rec.activity_schedule(
                            "mail.mail_activity_data_todo",
                            summary=_("Blocking availability overlaps with roster"),
                            note=_("Please resolve conflicts between roster and blocking availability window."),
                        )
        return res

    # -------------------------
    # Name get
    # -------------------------
    def name_get(self):
        res = []
        for rec in self:
            name = rec.display_name or rec.name or _("Staff Availability")
            res.append((rec.id, name))
        return res


# ============================================================
# Availability Occurrence (Expanded)
# ============================================================
class ClinicStaffAvailabilityOccurrence(models.Model):
    _name = "clinic.staff.availability.occurrence"
    _description = "Staff Availability Occurrence"
    _inherit = ["mail.thread"]
    _rec_name = "display_name"
    _order = "start, id desc"

    availability_id = fields.Many2one(
        "clinic.staff.availability",
        string="Availability Pattern",
        required=True,
        index=True,
        ondelete="cascade",
        help="Parent availability pattern from which this occurrence was generated.",
    )

    staff_id = fields.Many2one(
        "clinic.staff",
        string="Staff",
        required=True,
        index=True,
        ondelete="cascade",
        help="Staff for this occurrence.",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        help="Company of the staff.",
    )

    branch_id = fields.Many2one(
        "clinic.branch",
        string="Branch",
        help="Operational branch for this occurrence.",
    )

    name = fields.Char(
        string="Title",
        help="Optional custom title for this occurrence.",
        translate=True,
    )

    start = fields.Datetime(
        string="Start",
        required=True,
        index=True,
        help="Start datetime (UTC).",
    )

    stop = fields.Datetime(
        string="Stop",
        required=True,
        index=True,
        help="End datetime (UTC).",
    )

    duration_hours = fields.Float(
        string="Duration (Hours)",
        compute="_compute_duration_hours",
        store=False,
        help="Duration in hours.",
    )

    availability_type = fields.Selection(
        selection=[
            ("available", "Available"),
            ("standby", "Standby"),
            ("unavailable", "Unavailable"),
            ("leave", "Leave"),
            ("training", "Training"),
        ],
        string="Type",
        required=True,
        default="available",
        index=True,
        help="Occurrence availability type.",
    )

    is_blocking = fields.Boolean(
        string="Blocking",
        default=False,
        help="If enabled, this occurrence blocks scheduling.",
    )

    state = fields.Selection(
        selection=[("planned", "Planned"), ("applied", "Applied"), ("cancelled", "Cancelled")],
        string="State",
        default="planned",
        index=True,
        help="Planned: for planning; Applied: used by roster; Cancelled: not used.",
    )

    color = fields.Integer(
        string="Color",
        help="Optional color index for calendar views.",
    )

    # Konflik cepat dengan roster/assignment
    # conflict_roster = fields.Boolean(
    #     string="Roster Conflict",
    #     compute="_compute_conflicts",
    #     store=False,
    #     help="True if overlaps with existing roster entries.",
    # )
    # conflict_assignment = fields.Boolean(
    #     string="Assignment Conflict",
    #     compute="_compute_conflicts",
    #     store=False,
    #     help="True if overlaps with existing assignments.",
    # )

    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
        help="Composite label for this occurrence.",
    )

    _check_start_before_stop = models.Constraint(
        'CHECK (start < stop)',
        'The Start must be earlier than the Stop.',
    )

    # -------------------------
    # Compute
    # -------------------------
    def _compute_duration_hours(self):
        for rec in self:
            rec.duration_hours = 0.0
            if rec.start and rec.stop:
                delta = rec.stop - rec.start
                rec.duration_hours = (delta.total_seconds() / 3600.0)

    @api.depends("staff_id.display_name", "availability_type", "start", "stop", "state")
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.staff_id:
                parts.append(rec.staff_id.display_name or _("(No Staff)"))
            parts.append(f"- {dict(self._fields['availability_type'].selection).get(rec.availability_type)}")
            if rec.state:
                parts.append(f"[{dict(self._fields['state'].selection).get(rec.state)}]")
            if rec.start and rec.stop:
                parts.append(f"({fields.Datetime.to_string(rec.start)} → {fields.Datetime.to_string(rec.stop)})")
            rec.display_name = " ".join(parts)

    # def _compute_conflicts(self):
    #     Roster = self.env.get("clinic.staff.roster")
    #     Assign = self.env.get("clinic.staff.assignment")
    #     for rec in self:
    #         rec.conflict_roster = False
    #         rec.conflict_assignment = False
    #         if not rec.is_blocking:
    #             continue
    #         if Roster:
    #             domain = [("staff_id", "=", rec.staff_id.id)] + _overlap_domain(rec.start, rec.stop)
    #             try:
    #                 rec.conflict_roster = bool(Roster.sudo().search_count(domain))
    #             except Exception:
    #                 _logger.debug("Roster conflict check failed (occurrence %s)", rec.id)
    #         if Assign:
    #             domain = [("staff_id", "=", rec.staff_id.id), ("state", "!=", "closed")] + _overlap_domain(rec.start, rec.stop)
    #             try:
    #                 rec.conflict_assignment = bool(Assign.sudo().search_count(domain))
    #             except Exception:
    #                 _logger.debug("Assignment conflict check failed (occurrence %s)", rec.id)

    # -------------------------
    # Constraints
    # -------------------------
    @api.constrains("start", "stop", "is_blocking", "staff_id", "state")
    def _check_overlap_blocking(self):
        """Jika occurrence blocking dan masih planned/applied, cegah overlap occurrence blocking lain."""
        for rec in self.filtered(lambda r: r.is_blocking and r.state in ("planned", "applied")):
            dom = [
                ("id", "!=", rec.id),
                ("staff_id", "=", rec.staff_id.id),
                ("is_blocking", "=", True),
                ("state", "in", ("planned", "applied")),
            ] + _overlap_domain(rec.start, rec.stop)
            clash = self.search_count(dom)
            if clash:
                raise ValidationError(_("Blocking availability overlaps with another blocking occurrence."))

    # -------------------------
    # Actions
    # -------------------------
    def action_mark_applied(self):
        """Tandai occurrence dipakai pada roster."""
        for rec in self:
            rec.state = "applied"
        return True

    def action_cancel(self):
        """Batalkan occurrence (misal ada perubahan jadwal)."""
        for rec in self:
            rec.state = "cancelled"
        return True

    def action_open_roster_conflicts(self):
        self.ensure_one()
        Roster = self.env.get("clinic.staff.roster")
        if not Roster:
            return False
        return {
            "name": _("Roster Conflicts"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.staff.roster",
            "view_mode": "calendar,list,form,gantt",
            "domain": [("staff_id", "=", self.staff_id.id)] + _overlap_domain(self.start, self.stop),
            "context": {},
        }

    def action_open_assignment_conflicts(self):
        self.ensure_one()
        Assign = self.env.get("clinic.staff.assignment")
        if not Assign:
            return False
        return {
            "name": _("Assignment Conflicts"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.staff.assignment",
            "view_mode": "list,form,kanban",
            "domain": [("staff_id", "=", self.staff_id.id), ("state", "!=", "closed")] + _overlap_domain(self.start, self.stop),
            "context": {},
        }

    # -------------------------
    # Name get
    # -------------------------
    def name_get(self):
        res = []
        for rec in self:
            name = rec.display_name or _("Staff Availability")
            res.append((rec.id, name))
        return res
