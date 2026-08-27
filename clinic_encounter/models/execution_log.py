# -*- coding: utf-8 -*-
# ClinicOne — clinic_encounter
# File: models/execution_log.py
#
# Tujuan:
# - Merekam event eksekusi sesi prosedur (start/pause/resume/done/cancel/note).
# - Memberi snapshot status saat event, delta durasi sejak event sebelumnya, dan konteks aktor/ruangan.
# - Menyediakan helper untuk mencatat event kustom dan lampiran.
# - Override ringan model clinic.procedure.session: create/start/pause/resume/done/cancel ⇒ auto-log.
#
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# =============================================================================
# MODEL: Execution Log
# =============================================================================
class ClinicExecutionLog(models.Model):
    _name = "clinic.execution.log"
    _description = "Procedure Session Execution Log"
    _order = "date_event asc, id asc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identitas & Perusahaan
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Log #",
        required=True,
        copy=False,
        index=True,
        default=lambda self: _("New"),
        help="Sequence number of this log entry.",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Relasi Utama
    # -------------------------------------------------------------------------
    session_id = fields.Many2one(
        "clinic.procedure.session",
        string="Session",
        required=True,
        ondelete="cascade",
        index=True,
    )
    encounter_id = fields.Many2one(
        "clinic.encounter",
        string="Encounter",
        related="session_id.encounter_id",
        store=True,
        readonly=True,
        index=True,
    )
    patient_id = fields.Many2one(
        "clinic.patient",
        string="Patient",
        related="encounter_id.patient_id",
        store=True,
        readonly=True,
        index=True,
    )
    doctor_id = fields.Many2one(
        "clinic.doctor",
        string="Doctor (Encounter)",
        related="encounter_id.doctor_id",
        store=True,
        readonly=True,
        index=True,
    )
    procedure_id = fields.Many2one(
        "clinic.procedure.catalog",
        string="Procedure",
        related="session_id.procedure_id",
        store=True,
        readonly=True,
        index=True,
    )
    room_id = fields.Many2one(
        "clinic.room",
        string="Room",
        related="session_id.room_id",
        store=True,
        readonly=True,
        index=True,
    )

    # -------------------------------------------------------------------------
    # Event & Snapshot
    # -------------------------------------------------------------------------
    event_type = fields.Selection(
        [
            ("create", "Created"),
            ("start", "Start"),
            ("pause", "Pause"),
            ("resume", "Resume"),
            ("done", "Done"),
            ("cancel", "Cancel"),
            ("note", "Note"),
        ],
        string="Event",
        required=True,
        index=True,
    )
    date_event = fields.Datetime(
        string="Event Time",
        required=True,
        default=lambda self: fields.Datetime.now(),
        index=True,
        help="When this event occurred.",
    )
    state_after = fields.Selection(
        selection=lambda self: self.env["clinic.procedure.session"]._fields["state"].selection,
        string="State After",
        help="Session state immediately after this event.",
    )
    performer_user_id = fields.Many2one(
        "res.users",
        string="Performed By",
        default=lambda self: self.env.user,
        help="User who triggered this event.",
        index=True,
    )
    performer_role = fields.Selection(
        [
            ("system", "System"),
            ("user", "User"),
            ("performer", "Performer"),
            ("supervisor", "Supervisor"),
        ],
        string="Performer Role",
        default="user",
        help="Optional performer role for analytics.",
        index=True,
    )

    # -------------------------------------------------------------------------
    # Konten & Lampiran
    # -------------------------------------------------------------------------
    message = fields.Text(string="Message / Note")
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "clinic_exec_log_attachment_rel",
        "log_id",
        "attachment_id",
        string="Attachments",
    )
    # Payload bebas untuk device/alat: simpan JSON (sebagai teks) bila diperlukan
    payload = fields.Text(
        string="Payload (JSON)",
        help="Optional JSON payload from devices/bridges.",
    )

    # -------------------------------------------------------------------------
    # Durasi & Analitik
    # -------------------------------------------------------------------------
    is_timer_event = fields.Boolean(
        string="Timer Event",
        compute="_compute_flags",
        store=True,
        help="True for start/pause/resume/done events.",
    )
    delta_minutes_from_prev = fields.Float(
        string="Δ minutes from previous",
        compute="_compute_deltas",
        store=True,
        help="Time elapsed since previous log for this session (minutes).",
    )
    cumulative_runtime_minutes = fields.Float(
        string="Cumulative Runtime (min)",
        compute="_compute_deltas",
        store=True,
        help="Accrued running time within this session up to this event (minutes).",
    )

    color = fields.Integer(string="Color Index")

    treatment_id = fields.Many2one(
        "clinic.treatment",
        string="Treatment (Legacy)",
        index=True,
        ondelete="set null",
        help="Optional compat if any legacy One2many points logs via 'treatment_id'."
    )

    # -------------------------------------------------------------------------
    # Compute
    # -------------------------------------------------------------------------
    @api.depends("event_type")
    def _compute_flags(self):
        timer_events = {"start", "pause", "resume", "done"}
        for rec in self:
            rec.is_timer_event = rec.event_type in timer_events

    @api.depends("date_event", "event_type", "session_id")
    def _compute_deltas(self):
        """
        Hitung:
          - delta_minutes_from_prev: selisih waktu dari log sebelumnya pada session yang sama
          - cumulative_runtime_minutes: akumulasi menit hanya saat status 'in_progress' (dari pasangan start/resume → pause/done)
        """
        for rec in self:
            rec.delta_minutes_from_prev = 0.0
            rec.cumulative_runtime_minutes = 0.0
            if not rec.session_id or not rec.date_event:
                continue

            # Temukan log sebelumnya di session yang sama
            prev_log = self.search(
                [("session_id", "=", rec.session_id.id), ("date_event", "<", rec.date_event)],
                order="date_event desc, id desc",
                limit=1,
            )
            # Delta dari prev
            if prev_log:
                delta = rec.date_event - prev_log.date_event
                rec.delta_minutes_from_prev = max(delta.total_seconds() / 60.0, 0.0)

            # Hitung akumulasi runtime: cari semua log <= current, akumulasi interval in_progress
            logs = self.search(
                [("session_id", "=", rec.session_id.id), ("date_event", "<=", rec.date_event)],
                order="date_event asc, id asc",
            )
            runtime = 0.0
            running_since = None
            # Kita asumsikan 'in_progress' dimulai pada event 'start' atau 'resume', berhenti pada 'pause' atau 'done'
            for lg in logs:
                if lg.event_type in ("start", "resume"):
                    running_since = lg.date_event
                elif lg.event_type in ("pause", "done"):
                    if running_since:
                        interval = lg.date_event - running_since
                        runtime += max(interval.total_seconds() / 60.0, 0.0)
                        running_since = None
            rec.cumulative_runtime_minutes = runtime

    # -------------------------------------------------------------------------
    # Constraint & Validasi
    # -------------------------------------------------------------------------
    _constraint_uniq_log_name_company = models.Constraint(
        'unique(name, company_id)',
        'Log number must be unique per company.',
    )

    @api.constrains("company_id", "encounter_id")
    def _check_company_consistency(self):
        for rec in self:
            if rec.encounter_id and rec.company_id and rec.company_id != rec.encounter_id.company_id:
                raise ValidationError(_("Log company must match Encounter company."))

    @api.constrains("date_event", "session_id")
    def _check_date_sequence(self):
        # Longgar: izinkan back-date, tapi cegah event yang terlalu jauh di masa depan?
        # Di sini hanya pastikan date_event ada (wajib) dan tidak null, validasi lain melalui UI/workflow.
        for rec in self:
            if not rec.date_event:
                raise ValidationError(_("Event time is required."))

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id
            if vals.get("name", _("New")) in (False, _("New")):
                vals["name"] = seq.next_by_code("clinic.execution.log") or _("New")
        recs = super().create(vals_list)
        return recs

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    @api.model
    def log_for_session(self, session, event_type, message=None, role="user", **extra_vals):
        """
        Helper sederhana untuk mencatat satu event pada sebuah session.
        - session: record clinic.procedure.session
        - event_type: start/pause/resume/done/cancel/note/create
        - message: catatan singkat
        - role: system/user/performer/supervisor
        - extra_vals: payload, attachment_ids [(6,0,ids)], date_event override, dll.
        """
        if not session or session._name != "clinic.procedure.session":
            raise UserError(_("A valid Procedure Session is required to log events."))

        vals = {
            "session_id": session.id,
            "company_id": session.company_id.id,
            "event_type": event_type,
            "state_after": session.state,  # snapshot seketika
            "performer_user_id": self.env.user.id,
            "performer_role": role or "user",
            "date_event": extra_vals.pop("date_event", fields.Datetime.now()),
            "message": message or False,
        }
        # merge ekstra (payload, attachments, dsb.)
        vals.update(extra_vals or {})
        return self.create([vals])[0]

    def action_open_session(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_procedure_session").read()[0]
        action["res_id"] = self.session_id.id
        action["domain"] = [("id", "=", self.session_id.id)]
        action["view_mode"] = "form"
        return action

    def action_open_encounter(self):
        self.ensure_one()
        action = self.env.ref("clinic_encounter.action_clinic_encounter").read()[0]
        action["res_id"] = self.encounter_id.id
        action["domain"] = [("id", "=", self.encounter_id.id)]
        action["view_mode"] = "form"
        return action

    # -------------------------------------------------------------------------
    # Name & Search
    # -------------------------------------------------------------------------
    @api.depends("name", "event_type", "session_id")
    def _compute_display_name(self):
        event_labels = dict(self._fields["event_type"].selection)
        for rec in self:
            label = f"{rec.name or ''} • {event_labels.get(rec.event_type) or rec.event_type or ''}".strip(" •")
            if rec.session_id:
                label = f"{label} • {rec.session_id.name}"
            rec.display_name = label

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=80):
        extra_domain = list(domain or [])
        name_domain = ["|", "|",
                  ("name", operator, name),
                  ("session_id.name", operator, name),
                  ("message", operator, name)]
        recs = self.search(name_domain + extra_domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs.sudo()]


# # =============================================================================
# # EXTENSION: Auto-logging pada clinic.procedure.session
# # =============================================================================
# class ClinicProcedureSession_ExecutionLog(models.Model):
#     _inherit = "clinic.procedure.session"

#     def _log_event(self, event_type, message=None, role="user", **kwargs):
#         """Panggil helper log untuk session ini (single)."""
#         self.ensure_one()
#         Log = self.env["clinic.execution.log"].sudo()
#         try:
#             Log.log_for_session(self, event_type=event_type, message=message, role=role, **kwargs)
#         except Exception:
#             # Jangan gagalkan workflow hanya karena gagal log
#             pass

#     @api.model_create_multi
#     def create(self, vals_list):
#         recs = super().create(vals_list)
#         # Auto-log "create"
#         for rec in recs:
#             rec._log_event("create", message=_("Session created"), role="system")
#         return recs

#     # Override workflow untuk injeksi log
#     def action_start(self):
#         res = super().action_start()
#         for rec in self:
#             rec._log_event("start", message=_("Session started"), role="performer")
#         return res

#     def action_pause(self, reason=None):
#         res = super().action_pause(reason=reason)
#         for rec in self:
#             msg = _("Session paused") + (": %s" % reason if reason else "")
#             rec._log_event("pause", message=msg, role="performer")
#         return res

#     def action_resume(self):
#         res = super().action_resume()
#         for rec in self:
#             rec._log_event("resume", message=_("Session resumed"), role="performer")
#         return res

#     def action_done(self):
#         res = super().action_done()
#         for rec in self:
#             rec._log_event("done", message=_("Session completed"), role="performer")
#         return res

#     def action_cancel(self, reason=None):
#         res = super().action_cancel(reason=reason)
#         for rec in self:
#             msg = _("Session cancelled") + (": %s" % reason if reason else "")
#             rec._log_event("cancel", message=msg, role="performer")
#         return res

#     # Utilitas publik agar UI/otomasi dapat mencatat catatan bebas
#     def log_note(self, message, role="user", **extra_vals):
#         """
#         Catat event 'note' ke log sesi.
#         Use case: operator menambahkan catatan manual, sistem perangkat mengirim telemetry, dsb.
#         """
#         self.ensure_one()
#         if not message:
#             raise UserError(_("Message is required to create a note log."))
#         self._log_event("note", message=message, role=role, **extra_vals)
#         return True
