
# -*- coding: utf-8 -*-
# ClinicOne - Clinical Staff (Nurse & Therapist) Management
# File: staff_presence.py
#
# Catatan (ID):
# - Memberikan presensi real-time dan histori sesi presensi.
# - Integrasi holistik (soft-lookup aman): Roster, Assignment, Availability Blocking.
# - Menyediakan aksi: clock-in, start/end break, clock-out, dan navigasi ke data terkait.
# - Semua label/help Bahasa Inggris; komentar penjelas Bahasa Indonesia.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, time as dtime
import pytz
import logging

_logger = logging.getLogger(__name__)


# ============================================================
# Utilities
# ============================================================
def _overlap_domain(start_dt, end_dt):
    """Domain overlap standar: (start < end) & (stop > start)."""
    return [("start", "<", end_dt), ("stop", ">", start_dt)]


def _utc_now():
    return fields.Datetime.now()


def _to_minutes(delta: timedelta) -> int:
    return max(0, int(delta.total_seconds() // 60))


def _float_hours(minutes: int) -> float:
    return round(float(minutes) / 60.0, 2)


def _user_today_range_utc(env) -> (datetime, datetime):
    """Range hari-ini (00:00–23:59:59) berdasarkan timezone user, dikonversi ke UTC."""
    now_utc = _utc_now()
    # Konversi ke zona user (untuk definisi "hari ini")
    local_now = fields.Datetime.context_timestamp(env.user, now_utc)
    local_date = local_now.date()
    start_local = datetime.combine(local_date, dtime.min)
    end_local = datetime.combine(local_date, dtime.max)
    tzname = env.user.tz or "UTC"
    tz = pytz.timezone(tzname)
    start_utc = tz.localize(start_local).astimezone(pytz.UTC).replace(tzinfo=None)
    end_utc = tz.localize(end_local).astimezone(pytz.UTC).replace(tzinfo=None)
    return start_utc, end_utc


# ============================================================
# Presence Snapshot (Realtime per Staff)
# ============================================================
class ClinicStaffPresence(models.Model):
    _name = "clinic.staff.presence"
    _description = "Staff Presence"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "display_name"
    _order = "write_date desc, staff_id"
    _presence_staff_unique = models.Constraint(
        'unique(staff_id)',
        'Presence snapshot already exists for this staff.',
    )

    # -------------------------
    # Relasi & Identitas
    # -------------------------
    staff_id = fields.Many2one(
        "clinic.staff",
        string="Staff",
        required=True,
        index=True,
        ondelete="cascade",
        help="Staff member represented by this presence snapshot.",
        tracking=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="staff_id.company_id",
        store=True,
        readonly=True,
    )

    # branch_id = fields.Many2one(
    #     "clinic.branch",
    #     string="Branch",
    #     help="Operational branch context for the current presence state.",
    #     tracking=True,
    # )

    # Status real-time
    state = fields.Selection(
        selection=[
            ("off_duty", "Off Duty"),
            ("on_duty", "On Duty"),
            ("on_break", "On Break"),
            ("away", "Away"),
        ],
        string="State",
        required=True,
        default="off_duty",
        index=True,
        help="Realtime presence state of the staff.",
        tracking=True,
    )

    current_session_id = fields.Many2one(
        "clinic.staff.presence.session",
        string="Current Session",
        ondelete="set null",
        help="Open presence session if the staff is currently on duty.",
    )

    last_check_in = fields.Datetime(
        string="Last Check-In",
        help="Timestamp when the staff last clocked in.",
        tracking=True,
    )

    last_check_out = fields.Datetime(
        string="Last Check-Out",
        help="Timestamp when the staff last clocked out.",
        tracking=True,
    )

    last_action_on = fields.Datetime(
        string="Last Action",
        help="Timestamp of the last presence action (check-in/out/break).",
        tracking=True,
    )

    last_source = fields.Selection(
        selection=[("manual", "Manual"), ("kiosk", "Kiosk"), ("mobile", "Mobile"), ("api", "API")],
        string="Last Source",
        help="Source of the last presence action.",
        tracking=True,
    )

    # Geo/IP/Device (opsional)
    last_latitude = fields.Float(string="Last Latitude", digits=(10, 6))
    last_longitude = fields.Float(string="Last Longitude", digits=(10, 6))
    last_ip = fields.Char(string="Last IP")
    last_device = fields.Char(string="Last Device")

    # Ringkasan hari ini
    today_total_hours = fields.Float(
        string="Today Total (Hours)",
        compute="_compute_today_metrics",
        help="Total worked hours from sessions within today's window (user timezone).",
        store=False,
    )

    today_break_hours = fields.Float(
        string="Today Break (Hours)",
        compute="_compute_today_metrics",
        store=False,
        help="Total break hours from sessions within today's window (user timezone).",
    )

    today_net_hours = fields.Float(
        string="Today Net (Hours)",
        compute="_compute_today_metrics",
        store=False,
        help="Net hours (worked minus breaks) within today's window.",
    )

    today_late_minutes = fields.Integer(
        string="Late (min, Today)",
        compute="_compute_today_metrics",
        store=False,
        help="Accumulated late minutes against roster starts (today).",
    )

    today_early_leave_minutes = fields.Integer(
        string="Early Leave (min, Today)",
        compute="_compute_today_metrics",
        store=False,
        help="Accumulated early-leave minutes against roster stops (today).",
    )

    # Keterkaitan operasional (indikasi saat ini)
    roster_id = fields.Many2one(
        "clinic.staff.roster",
        string="Current Roster",
        help="Roster entry overlapping with the current time, if any.",
    )

    assignment_id = fields.Many2one(
        "clinic.staff.assignment",
        string="Current Assignment",
        help="Assignment overlapping with the current time, if any.",
    )

    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
    )

    notes = fields.Text(
        string="Notes",
        help="Additional remarks regarding presence handling.",
    )

    active = fields.Boolean(string="Active", default=True)

    # -------------------------
    # Compute
    # -------------------------
    @api.depends("staff_id.display_name", "state", "current_session_id.start")
    def _compute_display_name(self):
        """Compute the presence label using only fields present in the active model."""
        state_selection = dict(self._fields["state"].selection)
        for rec in self:
            who = rec.staff_id.display_name or _("(No Staff)")
            state_label = state_selection.get(rec.state, rec.state or "")
            parts = [who]
            if state_label:
                parts.append(f"[{state_label}]")
            if rec.current_session_id and rec.current_session_id.start:
                parts.append(f"since {fields.Datetime.to_string(rec.current_session_id.start)}")
            rec.display_name = " ".join(parts)

    # @api.depends("staff_id.display_name", "state", "branch_id", "current_session_id.start")
    # def _compute_display_name(self):
    #     for rec in self:
    #         who = rec.staff_id.display_name or _("(No Staff)")
    #         st = dict(self._fields["state"].selection).get(rec.state, "")
    #         branch = rec.branch_id.display_name if rec.branch_id else ""
    #         when = fields.Datetime.to_string(rec.current_session_id.start) if rec.current_session_id else ""
    #         parts = [who, f"[{st}]"]
    #         if branch:
    #             parts.append(f"@ {branch}")
    #         if when:
    #             parts.append(f"since {when}")
    #         rec.display_name = " ".join(parts)

    def _compute_today_metrics(self):
        Session = self.env["clinic.staff.presence.session"].sudo()
        for rec in self:
            rec.today_total_hours = 0.0
            rec.today_break_hours = 0.0
            rec.today_net_hours = 0.0
            rec.today_late_minutes = 0
            rec.today_early_leave_minutes = 0

            if not rec.staff_id:
                continue

            start_utc, end_utc = _user_today_range_utc(self.env)
            dom = [
                ("staff_id", "=", rec.staff_id.id),
                ("start", "<=", end_utc),
                "|",
                ("stop", ">=", start_utc),
                ("stop", "=", False),
            ]
            sessions = Session.search(dom)

            total_min = 0
            break_min = 0
            net_min = 0
            late_min = 0
            early_min = 0
            now = _utc_now()
            for s in sessions:
                s_start = max(s.start, start_utc)
                s_stop = min(s.stop or now, end_utc)
                if s_stop > s_start:
                    total_min += _to_minutes(s_stop - s_start)
                    break_min += s._break_minutes_between(s_start, s_stop)
                    net_min += _to_minutes(s_stop - s_start) - s._break_minutes_between(s_start, s_stop)
                # agregasi lateness/early leave
                late_min += max(0, s.late_by_minutes or 0)
                early_min += max(0, s.left_early_by_minutes or 0)

            rec.today_total_hours = _float_hours(total_min)
            rec.today_break_hours = _float_hours(break_min)
            rec.today_net_hours = _float_hours(net_min)
            rec.today_late_minutes = late_min
            rec.today_early_leave_minutes = early_min

    # -------------------------
    # Helpers
    # -------------------------
    def _find_current_roster(self):
        Roster = self.env.get("clinic.staff.roster")
        if not Roster:
            return False
        now = _utc_now()
        return Roster.search([
            ("staff_id", "=", self.staff_id.id),
            ("start", "<=", now),
            ("stop", ">=", now),
            ("state", "in", ("published", "in_progress")),
        ], limit=1)

    def _find_current_assignment(self):
        Assign = self.env.get("clinic.staff.assignment")
        if not Assign:
            return False
        now = _utc_now()
        return Assign.search([
            ("staff_id", "=", self.staff_id.id),
            ("start", "<=", now),
            ("stop", ">=", now),
            ("state", "in", ("confirmed", "in_progress", "paused")),
        ], limit=1)

    def _update_current_links(self):
        for rec in self:
            rec.roster_id = rec._find_current_roster() or False
            rec.assignment_id = rec._find_current_assignment() or False

    # -------------------------
    # Actions (Workflow)
    # -------------------------
    def action_clock_in(self, source="manual", branch_id=False, latitude=False, longitude=False, ip=False, device=False):
        """Clock-in: membuat sesi baru; validasi tidak ada sesi terbuka; update snapshot."""
        PresenceSession = self.env["clinic.staff.presence.session"].sudo()
        Av = self.env.get("clinic.staff.availability")

        for rec in self:
            if rec.current_session_id and rec.current_session_id.state != "closed":
                raise ValidationError(_("You already have an open presence session."))

            # Eligibility dasar dari model staff
            rec.staff_id.ensure_clinical_eligibility()

            # Buat sesi presensi
            branch_value = branch_id or False
            if "branch_id" in rec._fields and rec.branch_id:
                branch_value = branch_value or rec.branch_id.id

            vals = {
                "staff_id": rec.staff_id.id,
                "presence_id": rec.id,
                "start": _utc_now(),
                "source": source or "manual",
                "ip_address": ip or False,
                "device_info": device or False,
                "latitude": latitude or 0.0,
                "longitude": longitude or 0.0,
            }
            if branch_value and "branch_id" in PresenceSession._fields:
                vals["branch_id"] = branch_value
            # Tautkan roster yang aktif saat ini
            roster = rec._find_current_roster()
            if roster:
                vals["roster_id"] = roster.id

            session = PresenceSession.create(vals)

            # Jika ada availability blocking (Leave/Unavailable) pada window ini, beri activity
            if Av:
                conflict = Av.sudo().search_count([
                    ("staff_id", "=", rec.staff_id.id),
                    ("is_blocking", "=", True),
                ] + _overlap_domain(session.start, session.start + timedelta(minutes=1)))
                if conflict:
                    rec.activity_schedule(
                        "mail.mail_activity_data_todo",
                        summary=_("Clock-in during blocking availability"),
                        note=_("Staff clocked in while a blocking availability (Leave/Unavailable) is active."),
                    )

            # Update snapshot
            snapshot_vals = {
                "state": "on_duty",
                "current_session_id": session.id,
                "last_check_in": session.start,
                "last_action_on": session.start,
                "last_source": session.source,
                "last_ip": ip or False,
                "last_device": device or False,
                "last_latitude": latitude or 0.0,
                "last_longitude": longitude or 0.0,
            }
            if branch_value and "branch_id" in rec._fields:
                snapshot_vals["branch_id"] = branch_value
            rec.write(snapshot_vals)
            rec._update_current_links()
            rec.message_post(body=_("Clock-in."))

        return True

    def action_start_break(self, reason="rest"):
        """Mulai break di sesi berjalan (state -> on_break)."""
        for rec in self:
            s = rec.current_session_id
            if not s or s.state != "open":
                raise ValidationError(_("No open presence session to start a break."))
            s.action_start_break(reason=reason)
            rec.write({
                "state": "on_break",
                "last_action_on": _utc_now(),
            })
            rec.message_post(body=_("Break started."))
        return True

    def action_end_break(self):
        """Akhiri break (state -> on_duty)."""
        for rec in self:
            s = rec.current_session_id
            if not s or s.state not in ("open", "break"):
                raise ValidationError(_("No break is currently active."))
            s.action_end_break()
            rec.write({
                "state": "on_duty",
                "last_action_on": _utc_now(),
            })
            rec.message_post(body=_("Break ended."))
        return True

    def action_clock_out(self):
        """Clock-out: tutup sesi berjalan; update snapshot."""
        for rec in self:
            s = rec.current_session_id
            if not s or s.state == "closed":
                raise ValidationError(_("No open presence session to clock out."))
            s.action_clock_out()
            rec.write({
                "state": "off_duty",
                "last_check_out": s.stop,
                "last_action_on": s.stop,
                "current_session_id": False,
            })
            rec._update_current_links()
            rec.message_post(body=_("Clock-out."))
        return True

    # -------------------------
    # Navigasi cepat
    # -------------------------
    def action_open_sessions(self):
        self.ensure_one()
        return {
            "name": _("Presence Sessions"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.staff.presence.session",
            "view_mode": "list,form,calendar",
            "domain": [("staff_id", "=", self.staff_id.id)],
            "context": {"default_staff_id": self.staff_id.id, "default_presence_id": self.id},
        }


# ============================================================
# Presence Session (Clock-in/out)
# ============================================================
class ClinicStaffPresenceSession(models.Model):
    _name = "clinic.staff.presence.session"
    _description = "Staff Presence Session"
    _inherit = ["mail.thread"]
    _rec_name = "display_name"
    _order = "start desc, id desc"

    # Identitas & relasi
    reference = fields.Char(
        string="Reference",
        copy=False,
        default="/",
        index=True,
        help="Unique reference generated by sequence for this presence session.",
        tracking=True,
    )

    presence_id = fields.Many2one(
        "clinic.staff.presence",
        string="Presence Snapshot",
        index=True,
        ondelete="cascade",
        help="Parent presence snapshot for this staff.",
    )

    staff_id = fields.Many2one(
        "clinic.staff",
        string="Staff",
        required=True,
        index=True,
        ondelete="cascade",
        help="Staff for this presence session.",
        tracking=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="staff_id.company_id",
        store=True,
        readonly=True,
    )

    # branch_id = fields.Many2one(
    #     "clinic.branch",
    #     string="Branch",
    #     help="Operational branch where the session took place.",
    #     tracking=True,
    # )

    roster_id = fields.Many2one(
        "clinic.staff.roster",
        string="Roster",
        help="Roster entry overlapping with the session time window, if any.",
    )

    assignment_id = fields.Many2one(
        "clinic.staff.assignment",
        string="Assignment",
        help="Active assignment during this session (heuristic, optional).",
    )

    # Waktu & status
    start = fields.Datetime(
        string="Check-In",
        required=True,
        index=True,
        help="Clock-in timestamp (UTC).",
        tracking=True,
    )

    stop = fields.Datetime(
        string="Check-Out",
        index=True,
        help="Clock-out timestamp (UTC).",
        tracking=True,
    )

    state = fields.Selection(
        selection=[("open", "Open"), ("break", "On Break"), ("closed", "Closed")],
        string="State",
        required=True,
        default="open",
        index=True,
        help="Open: on duty; Break: break active; Closed: clocked out.",
        tracking=True,
    )

    # Durasi & metrik
    duration_minutes = fields.Integer(
        string="Duration (min)",
        compute="_compute_durations",
        store=False,
        help="Total session duration (including breaks) based on start/stop.",
    )

    break_minutes = fields.Integer(
        string="Break (min)",
        compute="_compute_durations",
        store=False,
        help="Total break minutes within the session.",
    )

    net_minutes = fields.Integer(
        string="Net (min)",
        compute="_compute_durations",
        store=False,
        help="Net minutes (duration minus breaks).",
    )

    late_by_minutes = fields.Integer(
        string="Late (min)",
        compute="_compute_roster_metrics",
        store=False,
        help="Minutes late against roster start, if linked.",
    )

    left_early_by_minutes = fields.Integer(
        string="Early Leave (min)",
        compute="_compute_roster_metrics",
        store=False,
        help="Minutes left early against roster stop, if linked.",
    )

    inside_roster_window = fields.Boolean(
        string="Inside Roster Window",
        compute="_compute_roster_metrics",
        store=False,
        help="True if the session is within the roster window (heuristic when stop is missing).",
    )

    # Geo/IP/Device
    source = fields.Selection(
        selection=[("manual", "Manual"), ("kiosk", "Kiosk"), ("mobile", "Mobile"), ("api", "API")],
        string="Source",
        default="manual",
        help="Source of presence event creation.",
    )
    ip_address = fields.Char(string="IP Address")
    device_info = fields.Char(string="Device Info")

    latitude = fields.Float(string="Latitude", digits=(10, 6))
    longitude = fields.Float(string="Longitude", digits=(10, 6))

    # Break lines
    break_line_ids = fields.One2many(
        "clinic.staff.presence.break",
        "session_id",
        string="Breaks",
        help="Break intervals within this session.",
    )

    # Tampilan
    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
    )

    notes = fields.Text(string="Notes")

    _check_start_before_stop = models.Constraint(
        'CHECK (stop IS NULL OR start < stop)',
        'Check-Out must be later than Check-In.',
    )

    # -------------------------
    # Create override: sequence
    # -------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("reference") or vals.get("reference") in ("/",):
                vals["reference"] = self.env["ir.sequence"].next_by_code("clinic.staff.presence.session") or "/"
        recs = super().create(vals_list)
        # Heuristik assignment aktif saat create
        Assign = self.env.get("clinic.staff.assignment")
        now = _utc_now()
        for rec in recs:
            if Assign and not rec.assignment_id:
                a = Assign.sudo().search([
                    ("staff_id", "=", rec.staff_id.id),
                    ("start", "<=", now),
                    ("stop", ">=", now),
                    ("state", "in", ("confirmed", "in_progress", "paused")),
                ], limit=1)
                if a:
                    rec.assignment_id = a.id
        return recs

    # -------------------------
    # Compute
    # -------------------------
    @api.depends("reference", "staff_id.display_name", "start", "stop", "state")
    def _compute_display_name(self):
        for rec in self:
            who = rec.staff_id.display_name or _("(No Staff)")
            st = dict(self._fields["state"].selection).get(rec.state)
            rng = f"({fields.Datetime.to_string(rec.start)} → {fields.Datetime.to_string(rec.stop) if rec.stop else '...'} )"
            rec.display_name = f"[{rec.reference}] {who} [{st}] {rng}"

    def _break_minutes_between(self, from_dt: datetime, to_dt: datetime) -> int:
        """Hitung menit break pada rentang tertentu."""
        minutes = 0
        for br in self.break_line_ids:
            s = max(br.start, from_dt) if br.start else None
            e = min(br.stop or _utc_now(), to_dt) if (br.stop or br.start) else None
            if s and e and e > s:
                minutes += _to_minutes(e - s)
        return minutes

    def _compute_durations(self):
        now = _utc_now()
        for rec in self:
            end = rec.stop or now
            # total duration
            rec.duration_minutes = 0
            rec.break_minutes = 0
            rec.net_minutes = 0
            if rec.start and end and end > rec.start:
                rec.duration_minutes = _to_minutes(end - rec.start)
                rec.break_minutes = rec._break_minutes_between(rec.start, end)
                rec.net_minutes = max(0, rec.duration_minutes - rec.break_minutes)

    def _compute_roster_metrics(self):
        for rec in self:
            rec.late_by_minutes = 0
            rec.left_early_by_minutes = 0
            rec.inside_roster_window = False
            roster = rec.roster_id
            if not roster:
                # Coba tautkan roster ketika belum ada (optional)
                roster = rec._find_overlapping_roster()
                if roster:
                    rec.roster_id = roster.id
            roster = rec.roster_id
            if roster:
                # Late: check-in > roster.start
                if rec.start and roster.start and rec.start > roster.start:
                    rec.late_by_minutes = _to_minutes(rec.start - roster.start)
                # Early leave: stop < roster.stop
                if rec.stop and roster.stop and rec.stop < roster.stop:
                    rec.left_early_by_minutes = _to_minutes(roster.stop - rec.stop)
                # Inside?
                now = rec.stop or _utc_now()
                rec.inside_roster_window = (rec.start >= roster.start and now <= roster.stop)

    def _find_overlapping_roster(self):
        Roster = self.env.get("clinic.staff.roster")
        if not Roster or not self.staff_id or not self.start:
            return False
        end = self.stop or (self.start + timedelta(hours=12))  # batas heuristik 12 jam
        return Roster.sudo().search([
            ("staff_id", "=", self.staff_id.id),
            ("state", "in", ("published", "in_progress", "completed")),
        ] + _overlap_domain(self.start, end), limit=1)

    # -------------------------
    # Constraints
    # -------------------------
    @api.constrains("staff_id", "start", "stop", "state")
    def _check_overlap_sessions(self):
        """Larangan dua sesi terbuka/overlap untuk staff yang sama."""
        for rec in self:
            # Jika sudah closed, tetap cek overlap dengan sesi lain
            dom = [
                ("id", "!=", rec.id),
                ("staff_id", "=", rec.staff_id.id),
                "|",
                ("stop", "=", False),
                ("stop", ">", rec.start),
                ("start", "<", rec.stop or (rec.start + timedelta(days=1))),
            ]
            if self.search_count(dom):
                raise ValidationError(_("Presence session overlaps with another session for the same staff."))

    # -------------------------
    # Actions
    # -------------------------
    def action_start_break(self, reason="rest"):
        """Mulai break pada sesi ini."""
        self.ensure_one()
        if self.state == "closed":
            raise ValidationError(_("Cannot start a break on a closed session."))
        # Pastikan tidak ada break terbuka
        open_break = self.break_line_ids.filtered(lambda b: not b.stop)
        if open_break:
            raise ValidationError(_("There is already an active break."))
        self.env["clinic.staff.presence.break"].create({
            "session_id": self.id,
            "reason": reason or "rest",
            "start": _utc_now(),
        })
        self.state = "break"
        return True

    def action_end_break(self):
        """Akhiri break aktif (jika ada)."""
        self.ensure_one()
        if self.state not in ("open", "break"):
            raise ValidationError(_("No active break to end."))
        br = self.break_line_ids.filtered(lambda b: not b.stop)
        if not br:
            # Tidak ada break terbuka; set state kembali open
            self.state = "open"
            return True
        br.write({"stop": _utc_now()})
        self.state = "open"
        return True

    def action_clock_out(self):
        """Clock-out sesi ini."""
        self.ensure_one()
        if self.state == "closed":
            return True
        # Tutup break jika masih aktif
        if self.state == "break":
            self.action_end_break()
        self.stop = _utc_now()
        self.state = "closed"
        # Evaluasi dan beri activity jika keluar sebelum roster selesai
        if self.roster_id and self.stop and self.roster_id.stop and self.stop < self.roster_id.stop:
            try:
                self.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Early check-out against roster"),
                    note=_("This session was closed before the roster end time. Please review."),
                )
            except Exception:
                _logger.debug("Failed to schedule activity for early check-out in session %s", self.id)
        return True

    # -------------------------
    # Name get
    # -------------------------
    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, rec.display_name or rec.reference or _("Presence Session")))
        return res


# ============================================================
# Presence Break (Intervals)
# ============================================================
class ClinicStaffPresenceBreak(models.Model):
    _name = "clinic.staff.presence.break"
    _description = "Staff Presence Break"
    _order = "start desc, id desc"

    session_id = fields.Many2one(
        "clinic.staff.presence.session",
        string="Session",
        required=True,
        index=True,
        ondelete="cascade",
        help="Presence session to which this break belongs.",
    )

    staff_id = fields.Many2one(
        "clinic.staff",
        string="Staff",
        related="session_id.staff_id",
        store=True,
        readonly=True,
    )

    reason = fields.Selection(
        selection=[
            ("meal", "Meal"),
            ("prayer", "Prayer"),
            ("rest", "Rest"),
            ("personal", "Personal"),
            ("other", "Other"),
        ],
        string="Reason",
        default="rest",
        help="Reason for taking the break.",
    )

    start = fields.Datetime(
        string="Start",
        required=True,
        index=True,
        help="Break start time (UTC).",
    )

    stop = fields.Datetime(
        string="Stop",
        index=True,
        help="Break end time (UTC).",
    )

    duration_minutes = fields.Integer(
        string="Duration (min)",
        compute="_compute_duration",
        store=False,
        help="Total minutes of this break.",
    )

    notes = fields.Char(string="Notes")

    _check_start_before_stop = models.Constraint(
        'CHECK (stop IS NULL OR start < stop)',
        'Break end must be later than start.',
    )

    def _compute_duration(self):
        now = _utc_now()
        for rec in self:
            end = rec.stop or now
            rec.duration_minutes = _to_minutes(end - rec.start) if rec.start and end and end > rec.start else 0

    @api.constrains("start", "stop", "session_id")
    def _check_break_inside_session(self):
        """Pastikan break berada di dalam rentang sesi dan tidak overlap break lain pada sesi yang sama."""
        for rec in self:
            s = rec.session_id
            if not s or not s.start:
                continue
            end = rec.stop or (s.stop or (_utc_now() + timedelta(minutes=1)))
            # break harus berada dalam jendela sesi (stop sesi boleh kosong)
            if rec.start < s.start:
                raise ValidationError(_("Break cannot start before the session check-in."))
            if s.stop and end > s.stop:
                raise ValidationError(_("Break cannot end after the session check-out."))
            # Cegah overlap antar break
            dom = [
                ("id", "!=", rec.id),
                ("session_id", "=", s.id),
                ("start", "<", end),
                ("stop", ">", rec.start),
            ]
            if self.search_count(dom):
                raise ValidationError(_("Break overlaps with another break in the same session."))

    # Navigasi cepat
    def action_open_session(self):
        self.ensure_one()
        return {
            "name": _("Presence Session"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.staff.presence.session",
            "view_mode": "form",
            "res_id": self.session_id.id,
            "target": "current",
        }
