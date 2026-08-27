
# -*- coding: utf-8 -*-
# ClinicOne - Clinical Staff (Nurse & Therapist) Management
# File: staff_kpi.py
#
# Catatan (ID):
# - Menyediakan master definisi KPI serta snapshot KPI per staff & periode.
# - Integrasi holistik dengan Roster/Assignment/Availability/Post-Care/Telemed/Incident/Feedback/Procedure.
# - Menggunakan soft lookup (env.get) & pengecekan field dinamis agar aman jika modul belum aktif.
# - Semua label/help Bahasa Inggris; komentar penjelas Bahasa Indonesia.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import timedelta

# ============================================================
# KPI Definition (Master)
# ============================================================
class ClinicKPIDefinition(models.Model):
    _name = "clinic.kpi.definition"
    _description = "KPI Definition"
    _rec_name = "name"
    _order = "sequence, category, name"

    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Ordering of KPI definitions in pickers and reports.",
    )

    name = fields.Char(
        string="KPI Name",
        required=True,
        translate=True,
        help="Human-readable name for the KPI.",
    )

    code = fields.Char(
        string="Code",
        required=True,
        copy=False,
        default="/",
        index=True,
        help="Unique KPI code generated from a sequence.",
    )

    category = fields.Selection(
        selection=[
            ("utilization", "Utilization"),
            ("quality", "Quality of Care"),
            ("safety", "Safety"),
            ("timeliness", "Timeliness"),
            ("experience", "Patient Experience"),
            ("productivity", "Productivity"),
            ("financial", "Financial"),
            ("telemedicine", "Telemedicine"),
            ("other", "Other"),
        ],
        string="Category",
        default="other",
        index=True,
        help="KPI Category for dashboards and grouping.",
    )

    metric_type = fields.Selection(
        selection=[
            ("count", "Count"),
            ("percent", "Percentage"),
            ("duration_min", "Duration (Minutes)"),
            ("duration_hr", "Duration (Hours)"),
            ("ratio", "Ratio"),
            ("score", "Score"),
            ("money", "Money"),
        ],
        string="Metric Type",
        required=True,
        default="count",
        help="Metric value type that influences formatting and aggregation.",
    )

    unit = fields.Char(
        string="Unit",
        help="Unit label to display with metric values, e.g., '%', 'min', 'hrs'.",
    )

    aggregation = fields.Selection(
        selection=[
            ("sum", "Sum"),
            ("avg", "Average"),
            ("max", "Max"),
            ("min", "Min"),
        ],
        string="Aggregation Method",
        default="avg",
        help="Default aggregation to apply when combining multiple samples.",
    )

    description = fields.Text(
        string="Description",
        translate=True,
        help="Description or computation notes for this KPI.",
    )

    active = fields.Boolean(
        string="Active",
        default=True,
        help="If unchecked, this KPI will be hidden from selections.",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        help="Company for which this KPI applies.",
    )

    _kpi_def_code_unique = models.Constraint(
        'unique(code)',
        'KPI Code must be unique.',
    )

    _kpi_def_name_company_unique = models.Constraint(
        'unique(name, company_id)',
        'KPI Name must be unique per company.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("code") or vals.get("code") in ("/",):
                vals["code"] = self.env["ir.sequence"].next_by_code("clinic.kpi.definition") or "/"
        return super().create(vals_list)


# ============================================================
# Staff KPI Snapshot (Summary)
# ============================================================
class ClinicStaffKPI(models.Model):
    _name = "clinic.staff.kpi"
    _description = "Staff KPI Snapshot"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "display_name"
    _order = "date_from desc, staff_id, id desc"

    # -------------------------
    # Identitas & Periode
    # -------------------------
    staff_id = fields.Many2one(
        "clinic.staff",
        string="Staff",
        required=True,
        index=True,
        ondelete="cascade",
        help="Staff for whom the KPI snapshot is computed.",
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
    #     help="Operational branch context for this KPI snapshot.",
    # )

    period_type = fields.Selection(
        selection=[
            ("week", "Week"),
            ("month", "Month"),
            ("custom", "Custom"),
        ],
        string="Period Type",
        required=True,
        default="week",
        index=True,
        help="Defines the time bucket for KPI aggregation.",
        tracking=True,
    )

    date_from = fields.Date(
        string="From",
        required=True,
        index=True,
        help="Start date of the snapshot period (inclusive).",
        tracking=True,
    )

    date_to = fields.Date(
        string="To",
        required=True,
        index=True,
        help="End date of the snapshot period (inclusive).",
        tracking=True,
    )

    # -------------------------
    # KPI Utama (aggregat ringkas)
    # -------------------------
    utilization_planned_pct = fields.Float(
        string="Planned Utilization (%)",
        help="Planned hours / capacity * 100 based on workload summary.",
        tracking=True,
    )
    utilization_actual_pct = fields.Float(
        string="Actual Utilization (%)",
        help="Actual hours / capacity * 100 based on workload summary.",
        tracking=True,
    )

    roster_fulfillment_pct = fields.Float(
        string="Roster Fulfillment (%)",
        help="Completed roster entries / Published roster entries * 100 within the period.",
    )
    shift_swaps = fields.Integer(
        string="Shift Swaps",
        help="Number of shift swap events in the period (if tracked).",
    )
    shift_cancellations = fields.Integer(
        string="Shift Cancellations",
        help="Number of cancelled roster entries in the period.",
    )

    assignments_count = fields.Integer(
        string="Assignments",
        help="Number of assignments handled within the period.",
    )
    on_time_assignments_pct = fields.Float(
        string="On-Time Assignments (%)",
        help="Assignments meeting their SLA target / Total assignments with SLA * 100.",
    )

    postcare_on_time_pct = fields.Float(
        string="Post-Care On-Time (%)",
        help="Completed post-care tasks within due date / Total completed * 100.",
    )

    telemed_threads = fields.Integer(
        string="Telemedicine Threads",
        help="Number of telemedicine threads handled within the period.",
    )
    telemed_first_response_avg_min = fields.Float(
        string="Telemed First Response (Avg min)",
        help="Average minutes from thread creation to first staff response.",
    )

    incidents_count = fields.Integer(
        string="Incidents",
        help="Number of incidents involving the staff within the period.",
    )
    incidents_rate_per_100_assign = fields.Float(
        string="Incidents per 100 Assignments",
        help="Incidents count / Assignments count * 100.",
    )

    feedback_avg_score = fields.Float(
        string="Feedback Avg. Score",
        help="Average patient feedback score associated with this staff.",
    )

    procedures_count = fields.Integer(
        string="Procedures",
        help="Number of procedures/treatment sessions performed/assisted.",
    )
    procedure_avg_duration_min = fields.Float(
        string="Procedure Avg. Duration (min)",
        help="Average duration in minutes for procedures/sessions when durations are available.",
    )

    # -------------------------
    # Detail lines (optional)
    # -------------------------
    line_ids = fields.One2many(
        "clinic.staff.kpi.line",
        "kpi_id",
        string="KPI Lines",
        help="Detailed KPI lines and intermediate computations.",
    )

    # -------------------------
    # Tampilan & Status
    # -------------------------
    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
        help="Composite label for this KPI snapshot.",
    )

    notes = fields.Text(
        string="Notes",
        help="Additional remarks or investigation notes for the KPI snapshot.",
    )

    _date_order_valid = models.Constraint(
        'CHECK (date_from <= date_to)',
        'Date From must be earlier or equal to Date To.',
    )

    _unique_staff_period = models.Constraint(
        'unique(staff_id, date_from, date_to, period_type)',
        'KPI snapshot for the same staff and period must be unique.',
    )

    # =========================
    # Compute & Helpers
    # =========================
    @api.depends("staff_id.display_name", "period_type", "date_from", "date_to")
    def _compute_display_name(self):
        for rec in self:
            period = dict(self._fields["period_type"].selection).get(rec.period_type, "")
            who = rec.staff_id.display_name or _("(No Staff)")
            rec.display_name = f"{who} - {period} [{rec.date_from} → {rec.date_to}]"

    def _dt_range(self):
        """Konversi Date ke Datetime rentang harian penuh (UTC)."""
        start_dt = fields.Datetime.to_datetime(f"{self.date_from} 00:00:00")
        end_dt = fields.Datetime.to_datetime(f"{self.date_to} 23:59:59")
        return start_dt, end_dt

    def _add_line(self, code, value_float=0.0, value_int=0, unit=None, note=None, source_ref=None):
        """Utility membuat baris detail untuk sebuah KPI code bila definisi tersedia."""
        KDef = self.env["clinic.kpi.definition"].sudo()
        Line = self.env["clinic.staff.kpi.line"].sudo()
        for snap in self:
            kdef = KDef.search([("code", "=", code), ("active", "=", True)], limit=1)
            if not kdef:
                # Jika definisi belum ada, skip quietly (data/kpi_definitions.xml akan menambahkan)
                continue
            Line.create({
                "kpi_id": snap.id,
                "definition_id": kdef.id,
                "value_float": value_float,
                "value_int": value_int,
                "unit": unit or kdef.unit,
                "note": note,
                "source_ref": source_ref,
            })

    # =========================
    # Aggregators (Soft Lookups)
    # =========================
    def _aggregate_from_workload(self):
        """Tarik utilization dari Workload summary jika tersedia."""
        Workload = self.env.get("clinic.staff.workload")
        for rec in self:
            if not Workload:
                continue
            wl = Workload.search([
                ("staff_id", "=", rec.staff_id.id),
                ("date_from", "=", rec.date_from),
                ("date_to", "=", rec.date_to),
                ("period_type", "=", rec.period_type),
            ], limit=1)
            if wl:
                rec.utilization_planned_pct = wl.utilization_planned
                rec.utilization_actual_pct = wl.utilization_actual
                rec._add_line(
                    code="UTIL_PLANNED",
                    value_float=wl.utilization_planned,
                    unit="%",
                    note="Pulled from workload summary",
                    source_ref=f"{wl._name},{wl.id}",
                )
                rec._add_line(
                    code="UTIL_ACTUAL",
                    value_float=wl.utilization_actual,
                    unit="%",
                    note="Pulled from workload summary",
                    source_ref=f"{wl._name},{wl.id}",
                )

    def _aggregate_from_roster(self):
        Roster = self.env.get("clinic.staff.roster")
        if not Roster:
            return
        for rec in self:
            start_dt, end_dt = rec._dt_range()
            rosters = Roster.sudo().search([
                ("staff_id", "=", rec.staff_id.id),
                ("start", "<=", end_dt),
                ("stop", ">=", start_dt),
            ])
            total_published = sum(1 for r in rosters if r.state in ("published", "in_progress", "completed"))
            total_completed = sum(1 for r in rosters if r.state in ("completed",))
            total_cancelled = sum(1 for r in rosters if r.state in ("cancelled",))
            # shift swap (indikatif): cari notes mengandung "swap" atau gunakan field eksplisit jika ada
            swaps = 0
            if "notes" in Roster._fields:
                swaps = sum(1 for r in rosters if r.notes and "swap" in r.notes.lower())
            rec.roster_fulfillment_pct = (total_completed / total_published * 100.0) if total_published else 0.0
            rec.shift_cancellations = total_cancelled
            rec.shift_swaps = swaps

            rec._add_line("ROSTER_PUBLISHED", value_int=total_published, note="Published/in progress/completed")
            rec._add_line("ROSTER_COMPLETED", value_int=total_completed)
            rec._add_line("ROSTER_CANCELLED", value_int=total_cancelled)
            rec._add_line("ROSTER_FULFILLMENT", value_float=rec.roster_fulfillment_pct, unit="%")
            if swaps:
                rec._add_line("ROSTER_SWAPS", value_int=swaps)

    def _aggregate_from_assignments(self):
        Assign = self.env.get("clinic.staff.assignment")
        if not Assign:
            return
        for rec in self:
            start_dt, end_dt = rec._dt_range()
            asg = Assign.sudo().search([
                ("staff_id", "=", rec.staff_id.id),
                ("state", "not in", ("cancelled", "closed")),
                ("start", "<=", end_dt),
                ("stop", ">=", start_dt),
            ])
            rec.assignments_count = len(asg)
            # On-time SLA
            with_sla = 0
            met_sla = 0
            for a in asg:
                if a.sla_deadline:
                    with_sla += 1
                    if a.sla_target == "start" and a.actual_start:
                        if a.actual_start <= a.sla_deadline:
                            met_sla += 1
                    elif a.sla_target == "finish" and a.actual_stop:
                        if a.actual_stop <= a.sla_deadline:
                            met_sla += 1
            rec.on_time_assignments_pct = (met_sla / with_sla * 100.0) if with_sla else 0.0

            rec._add_line("ASSIGN_COUNT", value_int=rec.assignments_count)
            rec._add_line("ASSIGN_SLA_ON_TIME", value_float=rec.on_time_assignments_pct, unit="%", note=f"{met_sla}/{with_sla} on-time")

    # def _aggregate_from_postcare(self):
    #     PTask = self.env.get("clinic.postcare.task")
    #     if not PTask:
    #         return
    #     # Gunakan field lazim: state, due_date, done_on/closed_on, assignee_id (clinic.staff)
    #     for rec in self:
    #         start_dt, end_dt = rec._dt_range()
    #         dom = [
    #             ("assignee_id", "=", rec.staff_id.id),
    #             ("create_date", "<=", end_dt),
    #             ("create_date", ">=", start_dt),
    #         ]
    #         tasks = PTask.sudo().search(dom)
    #         done = [t for t in tasks if getattr(t, "state", "") in ("done", "closed")]
    #         # due_date / closed_on heuristik
    #         ontime = 0
    #         total_done = 0
    #         for t in done:
    #             total_done += 1
    #             due = getattr(t, "due_date", False) or getattr(t, "deadline", False)
    #             finished = getattr(t, "closed_on", False) or getattr(t, "done_on", False) or getattr(t, "write_date", False)
    #             if due and finished and finished <= fields.Datetime.to_datetime(due):
    #                 ontime += 1
    #         pct = (ontime / total_done * 100.0) if total_done else 0.0
    #         rec.postcare_on_time_pct = pct

    #         rec._add_line("POSTCARE_COMPLETED", value_int=total_done)
    #         rec._add_line("POSTCARE_ON_TIME", value_float=pct, unit="%", note=f"{ontime}/{total_done} on-time")

    # def _aggregate_from_telemedicine(self):
    #     TThread = self.env.get("clinic.telemedicine.thread")
    #     if not TThread:
    #         return
    #     # Asumsi field: handler_id (clinic.staff), create_date, first_response_on (jika ada)
    #     # Jika field first_response_on tidak ada, coba infer dari activity/message (diabaikan bila tidak tersedia).
    #     for rec in self:
    #         start_dt, end_dt = rec._dt_range()
    #         threads = TThread.sudo().search([
    #             ("handler_id", "=", rec.staff_id.id),
    #             ("create_date", "<=", end_dt),
    #             ("create_date", ">=", start_dt),
    #         ])
    #         rec.telemed_threads = len(threads)
    #         # hitung avg first response jika field ada
    #         avg_min = 0.0
    #         sample = 0
    #         if "first_response_on" in TThread._fields:
    #             for th in threads:
    #                 fr = getattr(th, "first_response_on", False)
    #                 if fr:
    #                     diff = (fr - th.create_date).total_seconds() / 60.0
    #                     if diff >= 0:
    #                         avg_min += diff
    #                         sample += 1
    #         # fallback: lewati jika tidak ada field pendukung
    #         rec.telemed_first_response_avg_min = round((avg_min / sample), 2) if sample else 0.0

    #         rec._add_line("TELEMED_THREADS", value_int=rec.telemed_threads)
    #         if sample:
    #             rec._add_line("TELEMED_FIRST_RESPONSE", value_float=rec.telemed_first_response_avg_min, unit="min", note=f"samples={sample}")

    # def _aggregate_from_incidents(self):
    #     Incident = self.env.get("clinic.incident")
    #     if not Incident:
    #         return
    #     # Asumsi field: occurred_at (Datetime), involved_staff_ids (m2m to clinic.staff)
    #     for rec in self:
    #         start_dt, end_dt = rec._dt_range()
    #         inc = Incident.sudo().search([
    #             ("occurred_at", "<=", end_dt),
    #             ("occurred_at", ">=", start_dt),
    #             ("involved_staff_ids", "in", rec.staff_id.id),
    #         ])
    #         rec.incidents_count = len(inc)
    #         rate = (rec.incidents_count / rec.assignments_count * 100.0) if rec.assignments_count else 0.0
    #         rec.incidents_rate_per_100_assign = rate

    #         rec._add_line("INCIDENTS", value_int=rec.incidents_count)
    #         rec._add_line("INCIDENTS_PER_100_ASSIGN", value_float=rate, unit="%")

    # def _aggregate_from_feedback(self):
    #     Feedback = self.env.get("clinic.feedback")
    #     if not Feedback:
    #         return
    #     # Asumsi field: staff_id / handler_id, rating (float/int), create_date
    #     for rec in self:
    #         start_dt, end_dt = rec._dt_range()
    #         # coba beberapa nama kolom relasi staff
    #         staff_fields = [f for f in ("staff_id", "handler_id", "therapist_id", "nurse_id") if f in Feedback._fields]
    #         if not staff_fields:
    #             continue
    #         domain = [("create_date", "<=", end_dt), ("create_date", ">=", start_dt)]
    #         domain += ["|"] * (len(staff_fields) - 1)
    #         for f in staff_fields:
    #             domain.append((f, "=", rec.staff_id.id))
    #         fb = Feedback.sudo().search(domain)
    #         ratings = []
    #         for f in fb:
    #             val = getattr(f, "rating", False) or getattr(f, "score", False)
    #             if isinstance(val, (int, float)):
    #                 ratings.append(float(val))
    #         rec.feedback_avg_score = round(sum(ratings) / len(ratings), 2) if ratings else 0.0

    #         rec._add_line("FEEDBACK_AVG_SCORE", value_float=rec.feedback_avg_score, unit="score", note=f"samples={len(ratings)}")

    # def _aggregate_from_procedures(self):
    #     # Coba model procedure & treatment session
    #     Proc = self.env.get("clinic.procedure")
    #     Sess = self.env.get("clinic.procedure.session")
    #     for rec in self:
    #         start_dt, end_dt = rec._dt_range()
    #         total = 0
    #         dur_sum_min = 0
    #         dur_samples = 0

    #         def _collect(model, staff_field_candidates):
    #             nonlocal total, dur_sum_min, dur_samples
    #             if not model:
    #                 return
    #             rel_fields = [f for f in staff_field_candidates if f in model._fields]
    #             if not rel_fields:
    #                 return
    #             dom = [("create_date", "<=", end_dt), ("create_date", ">=", start_dt)]
    #             # OR staff relation
    #             dom += ["|"] * (len(rel_fields) - 1)
    #             for f in rel_fields:
    #                 dom.append((f, "=", rec.staff_id.id))
    #             recs = model.sudo().search(dom)
    #             total += len(recs)
    #             # durasi: gunakan (end - start) bila ada; fallback ke planned duration (minutes)
    #             for r in recs:
    #                 start = getattr(r, "start", False) or getattr(r, "start_time", False)
    #                 stop = getattr(r, "stop", False) or getattr(r, "end_time", False)
    #                 minutes = 0
    #                 if start and stop and stop > start:
    #                     minutes = int((stop - start).total_seconds() // 60)
    #                 else:
    #                     minutes = int(getattr(r, "duration_minutes", 0) or getattr(r, "duration", 0) or 0)
    #                 if minutes > 0:
    #                     dur_sum_min += minutes
    #                     dur_samples += 1

    #         _collect(Proc, ("performer_id", "assistant_id", "staff_id", "handler_id"))
    #         _collect(Sess, ("therapist_id", "nurse_id", "staff_id", "handler_id"))

    #         rec.procedures_count = total
    #         rec.procedure_avg_duration_min = round(dur_sum_min / dur_samples, 2) if dur_samples else 0.0

    #         rec._add_line("PROCEDURES", value_int=total)
    #         if dur_samples:
    #             rec._add_line("PROC_AVG_DURATION", value_float=rec.procedure_avg_duration_min, unit="min", note=f"samples={dur_samples}")

    # =========================
    # Public API
    # =========================
    def recompute_snapshot(self, generate_lines=True, replace_lines=True):
        """Hitung ulang seluruh KPI untuk snapshot ini."""
        Line = self.env["clinic.staff.kpi.line"].sudo()
        for rec in self:
            if generate_lines and replace_lines and rec.line_ids:
                rec.line_ids.unlink()

            # Tarik Utilization dari Workload bila ada
            rec._aggregate_from_workload()
            # Roster metrics
            rec._aggregate_from_roster()
            # Assignment metrics (jumlah & SLA)
            rec._aggregate_from_assignments()
            # Post-care tasks SLA
            # rec._aggregate_from_postcare()
            # Telemedicine responsiveness
            # rec._aggregate_from_telemedicine()
            # Incidents & rates
            # rec._aggregate_from_incidents()
            # Feedback score
            # rec._aggregate_from_feedback()
            # Procedures throughput & duration
            # rec._aggregate_from_procedures()

            rec.message_post(body=_("KPI snapshot recomputed."))

        return True

    # =========================
    # Actions
    # =========================
    def action_recompute(self):
        self.recompute_snapshot(generate_lines=True, replace_lines=True)
        return True

    def action_open_lines(self):
        self.ensure_one()
        return {
            "name": _("KPI Lines"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.staff.kpi.line",
            "view_mode": "list,form,graph,pivot",
            "domain": [("kpi_id", "=", self.id)],
            "context": {"default_kpi_id": self.id},
        }

    def action_open_rosters(self):
        self.ensure_one()
        Roster = self.env.get("clinic.staff.roster")
        if not Roster:
            return False
        start_dt, end_dt = self._dt_range()
        return {
            "name": _("Rosters"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.staff.roster",
            "view_mode": "calendar,list,form,gantt",
            "domain": [
                ("staff_id", "=", self.staff_id.id),
                ("start", "<=", end_dt),
                ("stop", ">=", start_dt),
            ],
        }

    def action_open_assignments(self):
        self.ensure_one()
        Assign = self.env.get("clinic.staff.assignment")
        if not Assign:
            return False
        start_dt, end_dt = self._dt_range()
        return {
            "name": _("Assignments"),
            "type": "ir.actions.act_window",
            "res_model": "clinic.staff.assignment",
            "view_mode": "list,form,kanban",
            "domain": [
                ("staff_id", "=", self.staff_id.id),
                ("start", "<=", end_dt),
                ("stop", ">=", start_dt),
            ],
        }

    # def action_open_incidents(self):
    #     self.ensure_one()
    #     Incident = self.env.get("clinic.incident")
    #     if not Incident:
    #         return False
    #     start_dt, end_dt = self._dt_range()
    #     return {
    #         "name": _("Incidents"),
    #         "type": "ir.actions.act_window",
    #         "res_model": "clinic.incident",
    #         "view_mode": "list,form,kanban",
    #         "domain": [
    #             ("occurred_at", "<=", end_dt),
    #             ("occurred_at", ">=", start_dt),
    #             ("involved_staff_ids", "in", self.staff_id.id),
    #         ],
    #     }

    # def action_open_postcare(self):
    #     self.ensure_one()
    #     PTask = self.env.get("clinic.postcare.task")
    #     if not PTask:
    #         return False
    #     start_dt, end_dt = self._dt_range()
    #     return {
    #         "name": _("Post-Care Tasks"),
    #         "type": "ir.actions.act_window",
    #         "res_model": "clinic.postcare.task",
    #         "view_mode": "list,form,kanban",
    #         "domain": [
    #             ("assignee_id", "=", self.staff_id.id),
    #             ("create_date", "<=", end_dt),
    #             ("create_date", ">=", start_dt),
    #         ],
    #     }

    # def action_open_telemedicine(self):
    #     self.ensure_one()
    #     TThread = self.env.get("clinic.telemedicine.thread")
    #     if not TThread:
    #         return False
    #     start_dt, end_dt = self._dt_range()
    #     return {
    #         "name": _("Telemedicine Threads"),
    #         "type": "ir.actions.act_window",
    #         "res_model": "clinic.telemedicine.thread",
    #         "view_mode": "list,form,kanban",
    #         "domain": [
    #             ("handler_id", "=", self.staff_id.id),
    #             ("create_date", "<=", end_dt),
    #             ("create_date", ">=", start_dt),
    #         ],
    #     }

    # def action_open_feedback(self):
    #     self.ensure_one()
    #     Feedback = self.env.get("clinic.feedback")
    #     if not Feedback:
    #         return False
    #     start_dt, end_dt = self._dt_range()
    #     domain = [("create_date", "<=", end_dt), ("create_date", ">=", start_dt)]
    #     # OR beberapa field relasi staff
    #     domain += ["|", "|", "|"]
    #     for f in ("staff_id", "handler_id", "therapist_id", "nurse_id"):
    #         if f in Feedback._fields:
    #             domain.append((f, "=", self.staff_id.id))
    #     return {
    #         "name": _("Feedback"),
    #         "type": "ir.actions.act_window",
    #         "res_model": "clinic.feedback",
    #         "view_mode": "list,form,graph,pivot",
    #         "domain": domain,
    #     }

    # def action_open_procedures(self):
    #     self.ensure_one()
    #     Proc = self.env.get("clinic.procedure")
    #     if not Proc:
    #         return False
    #     start_dt, end_dt = self._dt_range()
    #     # OR performer/assistant/staff/handler
    #     domain = [("create_date", "<=", end_dt), ("create_date", ">=", start_dt)]
    #     domain += ["|", "|", "|"]
    #     for f in ("performer_id", "assistant_id", "staff_id", "handler_id"):
    #         if f in Proc._fields:
    #             domain.append((f, "=", self.staff_id.id))
    #     return {
    #         "name": _("Procedures"),
    #         "type": "ir.actions.act_window",
    #         "res_model": "clinic.procedure",
    #         "view_mode": "list,form,graph,pivot",
    #         "domain": domain,
    #     }


# ============================================================
# Staff KPI Line (Details)
# ============================================================
class ClinicStaffKPILine(models.Model):
    _name = "clinic.staff.kpi.line"
    _description = "Staff KPI Line"
    _order = "definition_id, id"

    kpi_id = fields.Many2one(
        "clinic.staff.kpi",
        string="KPI Snapshot",
        required=True,
        index=True,
        ondelete="cascade",
        help="The parent KPI snapshot.",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="kpi_id.company_id",
        store=True,
        readonly=True,
    )

    definition_id = fields.Many2one(
        "clinic.kpi.definition",
        string="Definition",
        required=True,
        ondelete="restrict",
        help="The KPI definition for this line.",
    )

    # Nilai numerik bisa disimpan dalam dua kolom (int/float) agar fleksibel
    value_int = fields.Integer(
        string="Value (Int)",
        help="Integer value for count-like metrics.",
    )

    value_float = fields.Float(
        string="Value (Float)",
        help="Float value for percentages, durations, or scores.",
    )

    unit = fields.Char(
        string="Unit",
        help="Optional unit string overriding the definition unit.",
    )

    note = fields.Char(
        string="Note",
        help="Optional short note describing this line computation.",
    )

    # Referensi teknis (model,id) untuk sumber agregasi
    source_ref = fields.Char(
        string="Source",
        help="Technical reference to a source record in the format '<model>,<id>'.",
    )

    # Quick navigation to source
    def action_open_source(self):
        """Open the referenced source record if accessible."""
        self.ensure_one()
        if not self.source_ref or "," not in self.source_ref:
            return False
        model, rec_id = self.source_ref.split(",", 1)
        try:
            rec_id_int = int(rec_id)
        except Exception:
            return False
        Model = self.env.get(model)
        if not Model:
            return False
        if not Model.browse(rec_id_int).exists():
            return False
        return {
            "name": _("Source Record"),
            "type": "ir.actions.act_window",
            "res_model": model,
            "view_mode": "form",
            "res_id": rec_id_int,
            "target": "current",
        }
