# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
from collections import defaultdict
import math


# =============================================================================
# Helpers (mixins / utilities)
# =============================================================================
class _KPIHelpersMixin(models.AbstractModel):
    _name = "clinical.imaging.kpi.helpers.mixin"
    _description = "Imaging KPI Helpers Mixin"

    # ---------- generic helpers ----------
    def _has_model(self, model_name):
        return model_name in self.env

    def _has_field(self, model_name, field_name):
        try:
            return field_name in self.env[model_name]._fields
        except Exception:
            return False

    def _dt_in_range(self, dt, start, end):
        if not dt:
            return False
        return (dt >= start) and (dt <= end)

    def _hours_between(self, dt_start, dt_end):
        if not dt_start or not dt_end:
            return 0.0
        delta = fields.Datetime.to_datetime(dt_end) - fields.Datetime.to_datetime(dt_start)
        return max(0.0, round(delta.total_seconds() / 3600.0, 4))

    def _avg(self, values):
        vals = [v for v in values if isinstance(v, (int, float))]
        return (sum(vals) / len(vals)) if vals else 0.0

    def _sum(self, values):
        vals = [v for v in values if isinstance(v, (int, float))]
        return sum(vals) if vals else 0.0

    def _safe_search(self, model, domain, fields_list=None, limit=0, order=None):
        """Search + read raw dict list safely."""
        recs = self.env[model].sudo().search(domain, limit=limit, order=order)
        if fields_list:
            return recs.read(fields_list)
        return recs

    def _overlap_hours(self, start_a, end_a, start_b, end_b):
        """Duration (hours) overlapping between [a] and [b]."""
        if not start_a or not end_a or not start_b or not end_b:
            return 0.0
        a1 = fields.Datetime.to_datetime(start_a)
        a2 = fields.Datetime.to_datetime(end_a)
        b1 = fields.Datetime.to_datetime(start_b)
        b2 = fields.Datetime.to_datetime(end_b)
        if a2 <= b1 or a1 >= b2:
            return 0.0
        s = max(a1, b1)
        e = min(a2, b2)
        if e <= s:
            return 0.0
        return (e - s).total_seconds() / 3600.0


# =============================================================================
# KPI Snapshot (periodic aggregation)
# =============================================================================
class ClinicalImagingKpiSnapshot(models.Model, _KPIHelpersMixin):
    _name = "clinical.imaging.kpi.snapshot"
    _description = "Clinical Imaging KPI Snapshot"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc, id desc"
    _check_company_auto = True

    # -------------------------------------------------------------------------
    # Identity & Period
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Name", required=True, copy=False,
        default=lambda s: _("New"),
        help="Display name for this KPI snapshot (auto-filled on compute).",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company", string="Company", required=True,
        default=lambda s: s.env.company, index=True
    )
    period = fields.Selection(
        [
            ("day", "Day"),
            ("week", "Week"),
            ("month", "Month"),
            ("custom", "Custom"),
        ],
        string="Period", default="day", required=True, tracking=True
    )
    date_start = fields.Datetime(string="Start Datetime", required=True, tracking=True)
    date_end = fields.Datetime(string="End Datetime", required=True, tracking=True)

    active = fields.Boolean(default=True)
    notes = fields.Text(string="Internal Notes")

    # -------------------------------------------------------------------------
    # Volume / Workflow counts
    # -------------------------------------------------------------------------
    request_count = fields.Integer(string="Requests", help="Imaging requests created within the period.")
    request_cancelled = fields.Integer(string="Requests Cancelled")
    imaging_count = fields.Integer(string="Imaging Records", help="Imaging records involved in the period.")
    study_count = fields.Integer(string="Studies Acquired", help="DICOM studies acquired in the period.")
    series_count = fields.Integer(string="Series Acquired", help="Series created in the period.")
    image_count = fields.Integer(string="Images Instances", help="DICOM instances or rendered images in the period.")
    result_created = fields.Integer(string="Results Created")
    result_final = fields.Integer(string="Results Finalized")
    backlog_open_requests = fields.Integer(string="Backlog: Open Requests", help="Requests not completed/cancelled at period end.")
    backlog_pending_reports = fields.Integer(string="Backlog: Pending Reports", help="Results not yet final at period end.")

    # -------------------------------------------------------------------------
    # Turn-Around-Time (hours)
    # -------------------------------------------------------------------------
    tat_order_to_acq_avg_h = fields.Float(string="Avg TAT Order→Acquisition (h)")
    tat_acq_to_sign_avg_h = fields.Float(string="Avg TAT Acquisition→Sign (h)")
    tat_total_order_to_sign_avg_h = fields.Float(string="Avg TAT Order→Sign (h)")

    # -------------------------------------------------------------------------
    # Device & QC
    # -------------------------------------------------------------------------
    device_count = fields.Integer(string="Devices Tracked")
    device_downtime_h = fields.Float(string="Total Downtime (h) in Period")
    device_uptime_ratio = fields.Float(
        string="Uptime Ratio (period)", help="Approx uptime ratio across devices in this period (0..1)."
    )
    device_qc_due = fields.Integer(string="QC Due", help="Devices with QC due within the period.")
    device_qc_overdue = fields.Integer(string="QC Overdue at End")

    # -------------------------------------------------------------------------
    # Dose / Exposure (aggregates from Series)
    # -------------------------------------------------------------------------
    avg_ctdi_vol_mgy = fields.Float(string="Avg CTDIvol (mGy)")
    avg_dlp_mgy_cm = fields.Float(string="Avg DLP (mGy·cm)")
    total_dap_gy_cm2 = fields.Float(string="Total DAP (Gy·cm²)")
    total_fluoro_time_min = fields.Float(string="Total Fluoro Time (min)")

    # -------------------------------------------------------------------------
    # Billing (optional, safe if linked)
    # -------------------------------------------------------------------------
    currency_id = fields.Many2one(
        "res.currency", string="Currency",
        default=lambda s: s.env.company.currency_id.id
    )
    invoice_count = fields.Integer(string="Invoices (Imaging)")
    invoice_amount_total = fields.Monetary(string="Total Invoiced")
    avg_days_to_invoice = fields.Float(string="Avg Days to Invoice")

    # -------------------------------------------------------------------------
    # Lines (modality / device / radiologist)
    # -------------------------------------------------------------------------
    modality_line_ids = fields.One2many(
        "clinical.imaging.kpi.modality.line", "snapshot_id",
        string="Modality Lines", copy=True
    )
    device_line_ids = fields.One2many(
        "clinical.imaging.kpi.device.line", "snapshot_id",
        string="Device Lines", copy=True
    )
    radiologist_line_ids = fields.One2many(
        "clinical.imaging.kpi.radiologist.line", "snapshot_id",
        string="Radiologist Lines", copy=True
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for rec in self:
            if rec.date_end <= rec.date_start:
                raise ValidationError(_("End Datetime must be after Start Datetime."))

    # -------------------------------------------------------------------------
    # Compute / Recompute
    # -------------------------------------------------------------------------
    def action_recompute(self):
        """Recompute all KPI fields and lines for this snapshot."""
        for snap in self:
            snap._compute_all_metrics()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            # auto-fill name then compute
            rec.name = rec._make_display_name()
            rec.action_recompute()
        return recs

    def write(self, vals):
        res = super().write(vals)
        # If period or dates change, recompute
        trigger = any(k in vals for k in ["date_start", "date_end", "period", "company_id"])
        if trigger:
            for rec in self:
                rec.name = rec._make_display_name()
                rec.action_recompute()
        return res

    def _make_display_name(self):
        self.ensure_one()
        start = fields.Datetime.to_string(self.date_start)
        end = fields.Datetime.to_string(self.date_end)
        return f"KPI {self.period.upper()} [{start} → {end}]"

    # ---------- core computation ----------
    def _compute_all_metrics(self):
        self.ensure_one()
        start = self.date_start
        end = self.date_end
        company = self.company_id

        # reset lines
        self.modality_line_ids.unlink()
        self.device_line_ids.unlink()
        self.radiologist_line_ids.unlink()

        # --- Requests ---
        self._compute_requests(company, start, end)

        # --- Studies/Series/Images volume ---
        self._compute_acquisition_volume(company, start, end)

        # --- Results & TAT ---
        self._compute_results_and_tat(company, start, end)

        # --- Devices & QC & Downtime ---
        self._compute_device_metrics(company, start, end)

        # --- Dose / Exposure from Series ---
        self._compute_dose_metrics(company, start, end)

        # --- Billing (if linked) ---
        self._compute_billing_metrics(company, start, end)

        # --- Lines: Modality/Device/Radiologist ---
        self._build_modality_lines(company, start, end)
        self._build_device_lines(company, start, end)
        self._build_radiologist_lines(company, start, end)

    # ------------------- Requests -------------------
    def _compute_requests(self, company, start, end):
        if not self._has_model("clinical.imaging.request"):
            self.request_count = 0
            self.request_cancelled = 0
            self.backlog_open_requests = 0
            return

        Req = self.env["clinical.imaging.request"].sudo().with_context(active_test=False)
        # assume 'request_datetime' if exists, else fallback to create_date
        dt_field = "request_datetime" if self._has_field("clinical.imaging.request", "request_datetime") else "create_date"
        state_field = "state" if self._has_field("clinical.imaging.request", "state") else None

        req_in_period = Req.search([
            ("company_id", "=", company.id),
            (dt_field, ">=", start),
            (dt_field, "<=", end),
        ])
        self.request_count = len(req_in_period)

        # cancellations in the period (state == cancelled with write_date in range OR cancel_datetime)
        if state_field:
            cancelled_domain = [("company_id", "=", company.id), (state_field, "in", ["cancelled", "canceled", "void"])]
            if self._has_field("clinical.imaging.request", "cancel_datetime"):
                cancelled_domain += [("cancel_datetime", ">=", start), ("cancel_datetime", "<=", end)]
            else:
                cancelled_domain += [("write_date", ">=", start), ("write_date", "<=", end)]
            self.request_cancelled = Req.search_count(cancelled_domain)
            # backlog at end: not finished/cancelled
            open_states = ["draft", "submitted", "approved", "scheduled", "in_progress"]
            backlog_domain = [("company_id", "=", company.id), (state_field, "in", open_states)]
            self.backlog_open_requests = Req.search_count(backlog_domain)
        else:
            self.request_cancelled = 0
            self.backlog_open_requests = 0

    # ------------------- Acquisition volume -------------------
    def _compute_acquisition_volume(self, company, start, end):
        # Studies
        if self._has_model("clinical.imaging.study"):
            Study = self.env["clinical.imaging.study"].sudo().with_context(active_test=False)
            study_recs = Study.search([
                ("company_id", "=", company.id),
                ("study_datetime", ">=", start),
                ("study_datetime", "<=", end),
            ])
            self.study_count = len(study_recs)
        else:
            study_recs = self.env["clinical.imaging.study"]  # empty
            self.study_count = 0

        # Series
        if self._has_model("clinical.imaging.series"):
            Series = self.env["clinical.imaging.series"].sudo().with_context(active_test=False)
            series_recs = Series.search([
                ("company_id", "=", company.id),
                ("series_datetime", ">=", start),
                ("series_datetime", "<=", end),
            ])
            self.series_count = len(series_recs)
        else:
            series_recs = self.env["clinical.imaging.series"]
            self.series_count = 0

        # Images
        if self._has_model("clinical.imaging.image"):
            Image = self.env["clinical.imaging.image"].sudo().with_context(active_test=False)
            # use acquisition_datetime if present else create_date
            dt_field = "acquisition_datetime" if self._has_field("clinical.imaging.image", "acquisition_datetime") else "create_date"
            image_recs = Image.search([
                ("company_id", "=", company.id),
                (dt_field, ">=", start),
                (dt_field, "<=", end),
            ])
            self.image_count = len(image_recs)
        else:
            image_recs = self.env["clinical.imaging.image"]
            self.image_count = 0

        # Imaging (parent) approximate involvement count: distinct imaging_id from studies
        imaging_ids = set()
        if study_recs:
            imaging_ids.update(study_recs.mapped("imaging_id").ids)
        elif series_recs:
            imaging_ids.update(series_recs.mapped("imaging_id").ids)
        self.imaging_count = len(imaging_ids)

    # ------------------- Results & TAT -------------------
    def _compute_results_and_tat(self, company, start, end):
        if not self._has_model("clinical.imaging.result"):
            self.result_created = 0
            self.result_final = 0
            self.backlog_pending_reports = 0
            self.tat_order_to_acq_avg_h = 0.0
            self.tat_acq_to_sign_avg_h = 0.0
            self.tat_total_order_to_sign_avg_h = 0.0
            return

        Result = self.env["clinical.imaging.result"].sudo().with_context(active_test=False)

        # create count in period (using create_date)
        created_cnt = Result.search_count([
            ("company_id", "=", company.id),
            ("create_date", ">=", start),
            ("create_date", "<=", end),
        ])
        self.result_created = created_cnt

        # finalized in period: states final/amended and signed_datetime in range
        state_field = "state" if self._has_field("clinical.imaging.result", "state") else None
        signed_field = "signed_datetime" if self._has_field("clinical.imaging.result", "signed_datetime") else None
        if state_field and signed_field:
            final_states = ["final", "amended"]
            final_cnt = Result.search_count([
                ("company_id", "=", company.id),
                (state_field, "in", final_states),
                (signed_field, ">=", start),
                (signed_field, "<=", end),
            ])
            self.result_final = final_cnt
            # backlog: not final at end
            pending_states = ["draft", "in_review", "preliminary", "verified", "approved"]
            self.backlog_pending_reports = Result.search_count([
                ("company_id", "=", company.id),
                (state_field, "in", pending_states),
            ])
        else:
            self.result_final = 0
            self.backlog_pending_reports = 0

        # TATs: Order→Acquisition, Acquisition→Sign, Total
        # Derive events:
        # - order: from clinical.imaging.request.request_datetime (fallback: create_date)
        # - acquisition: earliest study_datetime per imaging within period
        # - sign: result.signed_datetime
        order_times = {}
        if self._has_model("clinical.imaging.request"):
            Req = self.env["clinical.imaging.request"].sudo()
            dt_field = "request_datetime" if self._has_field("clinical.imaging.request", "request_datetime") else "create_date"
            reqs = Req.search([("company_id", "=", company.id), (dt_field, "!=", False)], limit=0)
            for r in reqs:
                key = r.imaging_id.id if self._has_field("clinical.imaging.request", "imaging_id") else (r.id,)
                order_times[key] = getattr(r, dt_field)

        # acquisition: earliest study per imaging within global index (not only in-period, to allow cross-period TAT)
        acq_times = {}
        if self._has_model("clinical.imaging.study"):
            Study = self.env["clinical.imaging.study"].sudo()
            st = Study.search([("company_id", "=", company.id), ("study_datetime", "!=", False)], limit=0, order="study_datetime asc")
            for s in st:
                img_id = s.imaging_id.id
                if img_id and img_id not in acq_times:
                    acq_times[img_id] = s.study_datetime

        # sign times for results within the period (to stabilize sample)
        sign_times = {}
        signed_results = Result.search([
            ("company_id", "=", company.id),
            ("signed_datetime", ">=", start),
            ("signed_datetime", "<=", end),
            ("signed_datetime", "!=", False),
        ], order="signed_datetime asc")
        for rs in signed_results:
            sign_times[rs.imaging_id.id if rs.imaging_id else rs.id] = rs.signed_datetime

        # compute arrays
        arr_order_acq = []
        arr_acq_sign = []
        arr_order_sign = []
        for key, sign_dt in sign_times.items():
            # key is imaging_id
            order_dt = order_times.get(key) if isinstance(key, int) else None
            acq_dt = acq_times.get(key)
            if order_dt and acq_dt:
                arr_order_acq.append(self._hours_between(order_dt, acq_dt))
                arr_order_sign.append(self._hours_between(order_dt, sign_dt))
            if acq_dt:
                arr_acq_sign.append(self._hours_between(acq_dt, sign_dt))

        self.tat_order_to_acq_avg_h = round(self._avg(arr_order_acq), 2) if arr_order_acq else 0.0
        self.tat_acq_to_sign_avg_h = round(self._avg(arr_acq_sign), 2) if arr_acq_sign else 0.0
        self.tat_total_order_to_sign_avg_h = round(self._avg(arr_order_sign), 2) if arr_order_sign else 0.0

    # ------------------- Devices & QC -------------------
    def _compute_device_metrics(self, company, start, end):
        if not self._has_model("clinical.imaging.device"):
            self.device_count = 0
            self.device_downtime_h = 0.0
            self.device_uptime_ratio = 1.0
            self.device_qc_due = 0
            self.device_qc_overdue = 0
            return

        Device = self.env["clinical.imaging.device"].sudo().with_context(active_test=False)
        devices = Device.search([("company_id", "=", company.id)], limit=0)
        self.device_count = len(devices)

        # Downtime in period
        downtime_h = 0.0
        qc_due = 0
        qc_over = 0

        # Device downtime model
        if self._has_model("clinical.imaging.device.downtime"):
            Downtime = self.env["clinical.imaging.device.downtime"].sudo()
            for d in devices:
                dts = Downtime.search([("device_id", "=", d.id), ("state", "=", "closed")])
                for row in dts:
                    dur = self._overlap_hours(row.start_datetime, row.end_datetime or fields.Datetime.now(), start, end)
                    downtime_h += dur

        # QC due / overdue within or at end of period
        if self._has_field("clinical.imaging.device", "next_qc_date"):
            for d in devices:
                if d.next_qc_date:
                    # due if next_qc_date is within [start, end]
                    if d.next_qc_date >= fields.Date.to_date(start) and d.next_qc_date <= fields.Date.to_date(end):
                        qc_due += 1
                    # overdue at the end
                    if d.next_qc_date < fields.Date.to_date(end):
                        qc_over += 1

        self.device_downtime_h = round(downtime_h, 2)
        period_hours = max(1.0, (fields.Datetime.to_datetime(end) - fields.Datetime.to_datetime(start)).total_seconds() / 3600.0)
        # uptime ratio = 1 - (downtime / (period_hours * device_count))
        denom = period_hours * max(1, self.device_count)
        uptime_ratio = 1.0 - (downtime_h / denom)
        self.device_uptime_ratio = round(max(0.0, min(1.0, uptime_ratio)), 3)
        self.device_qc_due = qc_due
        self.device_qc_overdue = qc_over

    # ------------------- Dose / Exposure (Series) -------------------
    def _compute_dose_metrics(self, company, start, end):
        if not self._has_model("clinical.imaging.series"):
            self.avg_ctdi_vol_mgy = 0.0
            self.avg_dlp_mgy_cm = 0.0
            self.total_dap_gy_cm2 = 0.0
            self.total_fluoro_time_min = 0.0
            return

        Series = self.env["clinical.imaging.series"].sudo()
        series = Series.search([
            ("company_id", "=", company.id),
            ("series_datetime", ">=", start),
            ("series_datetime", "<=", end),
        ], limit=0)

        ctdi_vals = []
        dlp_vals = []
        dap_vals = []
        fl_time_vals = []

        for s in series:
            if s.ctdi_vol_mgy is not None and s.ctdi_vol_mgy >= 0:
                ctdi_vals.append(s.ctdi_vol_mgy)
            if s.dlp_mgy_cm is not None and s.dlp_mgy_cm >= 0:
                dlp_vals.append(s.dlp_mgy_cm)
            if s.dap_gy_cm2 is not None and s.dap_gy_cm2 >= 0:
                dap_vals.append(s.dap_gy_cm2)
            if s.fluoro_time_min is not None and s.fluoro_time_min >= 0:
                fl_time_vals.append(s.fluoro_time_min)

        self.avg_ctdi_vol_mgy = round(self._avg(ctdi_vals), 2) if ctdi_vals else 0.0
        self.avg_dlp_mgy_cm = round(self._avg(dlp_vals), 2) if dlp_vals else 0.0
        self.total_dap_gy_cm2 = round(self._sum(dap_vals), 2) if dap_vals else 0.0
        self.total_fluoro_time_min = round(self._sum(fl_time_vals), 2) if fl_time_vals else 0.0

    # ------------------- Billing (optional) -------------------
    def _compute_billing_metrics(self, company, start, end):
        # This block is safe: if account.move or linking fields are absent, return zeros.
        self.invoice_count = 0
        self.invoice_amount_total = 0.0
        self.avg_days_to_invoice = 0.0

        if not self._has_model("account.move"):
            return

        Move = self.env["account.move"].sudo()
        # We try to detect a link field from imaging to invoice
        link_field = None
        for fname in ["clinical_imaging_id", "clinic_imaging_id", "imaging_id"]:
            if self._has_field("account.move", fname):
                link_field = fname
                break

        domain = [("company_id", "=", company.id), ("move_type", "in", ["out_invoice", "out_refund"]),
                  ("state", "=", "posted"), ("invoice_date", ">=", fields.Date.to_date(start)),
                  ("invoice_date", "<=", fields.Date.to_date(end))]
        if link_field:
            # keep only invoices that reference imaging records
            domain.append((link_field, "!=", False))
        moves = Move.search(domain, limit=0)

        self.invoice_count = len(moves)
        self.invoice_amount_total = sum(m.amount_total_signed for m in moves)

        # Avg days from acquisition to invoice (if we can find an imaging & earliest study)
        if link_field and self._has_model("clinical.imaging.study"):
            Study = self.env["clinical.imaging.study"].sudo()
            deltas = []
            for mv in moves:
                img = getattr(mv, link_field, False)
                if not img:
                    continue
                # earliest study
                studies = Study.search([("imaging_id", "=", img.id)], limit=1, order="study_datetime asc")
                if studies and mv.invoice_date:
                    dt_acq = fields.Datetime.to_datetime(studies.study_datetime)
                    dt_inv = datetime.combine(mv.invoice_date, datetime.min.time())
                    delta_days = max(0.0, (dt_inv - dt_acq).total_seconds() / 86400.0)
                    deltas.append(delta_days)
            self.avg_days_to_invoice = round(self._avg(deltas), 2) if deltas else 0.0

    # ------------------- Modality Lines -------------------
    def _build_modality_lines(self, company, start, end):
        if not self._has_model("clinical.imaging.study"):
            return
        Study = self.env["clinical.imaging.study"].sudo()
        Result = self.env["clinical.imaging.result"].sudo() if self._has_model("clinical.imaging.result") else None

        # group studies per modality
        studies = Study.search([
            ("company_id", "=", company.id),
            ("study_datetime", ">=", start),
            ("study_datetime", "<=", end),
        ], limit=0)
        grp = defaultdict(list)
        for st in studies:
            grp[st.modality or "OT"].append(st)

        for modality, items in grp.items():
            count_study = len(items)
            # final results linked to these imaging
            final_cnt = 0
            tat_h = []
            if Result:
                for st in items:
                    res = Result.search([
                        ("imaging_id", "=", st.imaging_id.id),
                        ("state", "in", ["final", "amended"]),
                        ("signed_datetime", ">=", start),
                        ("signed_datetime", "<=", end),
                    ], limit=1, order="signed_datetime desc")
                    if res:
                        final_cnt += 1
                        tat_h.append(self._hours_between(st.study_datetime, res.signed_datetime))
            self.env["clinical.imaging.kpi.modality.line"].create({
                "snapshot_id": self.id,
                "modality": modality,
                "study_count": count_study,
                "result_final_count": final_cnt,
                "tat_acq_to_sign_avg_h": round(self._avg(tat_h), 2) if tat_h else 0.0,
            })

    # ------------------- Device Lines -------------------
    def _build_device_lines(self, company, start, end):
        if not self._has_model("clinical.imaging.device"):
            return
        Device = self.env["clinical.imaging.device"].sudo()
        Study = self.env["clinical.imaging.study"].sudo() if self._has_model("clinical.imaging.study") else None
        Downtime = self.env["clinical.imaging.device.downtime"].sudo() if self._has_model("clinical.imaging.device.downtime") else None

        devices = Device.search([("company_id", "=", company.id)], limit=0)
        for d in devices:
            study_cnt = 0
            if Study:
                study_cnt = Study.search_count([
                    ("device_id", "=", d.id),
                    ("study_datetime", ">=", start),
                    ("study_datetime", "<=", end),
                ])
            # downtime hours overlap in period
            dt_h = 0.0
            if Downtime:
                dts = Downtime.search([("device_id", "=", d.id), ("state", "=", "closed")])
                for row in dts:
                    dt_h += self._overlap_hours(row.start_datetime, row.end_datetime or fields.Datetime.now(), start, end)
            # utilization naive: studies per hour capacity (throughput * hours)
            hours = max(1.0, (fields.Datetime.to_datetime(end) - fields.Datetime.to_datetime(start)).total_seconds() / 3600.0)
            capacity = (d.throughput_per_hour or 0.0) * hours
            utilization = (study_cnt / capacity) if capacity > 0 else 0.0
            self.env["clinical.imaging.kpi.device.line"].create({
                "snapshot_id": self.id,
                "device_id": d.id,
                "modality": d.modality,
                "study_count": study_cnt,
                "downtime_h": round(dt_h, 2),
                "utilization_ratio": round(max(0.0, min(1.0, utilization)), 3),
                "qc_status": getattr(d, "qc_status", False) or "ok",
            })

    # ------------------- Radiologist Lines -------------------
    def _build_radiologist_lines(self, company, start, end):
        if not self._has_model("clinical.imaging.result"):
            return
        Result = self.env["clinical.imaging.result"].sudo()
        Study = self.env["clinical.imaging.study"].sudo() if self._has_model("clinical.imaging.study") else None

        # all results signed in period, grouped by author radiologist
        results = Result.search([
            ("company_id", "=", company.id),
            ("signed_datetime", ">=", start),
            ("signed_datetime", "<=", end),
            ("signed_datetime", "!=", False),
            ("author_doctor_id", "!=", False),
        ], limit=0)

        per_rad_counts = defaultdict(int)
        per_rad_tat = defaultdict(list)

        for res in results:
            per_rad_counts[res.author_doctor_id.id] += 1
            # TAT acquisition->sign: use earliest study for that imaging (if exists)
            tat_h = 0.0
            if Study and res.imaging_id:
                st = Study.search([("imaging_id", "=", res.imaging_id.id)], limit=1, order="study_datetime asc")
                if st:
                    tat_h = self._hours_between(st.study_datetime, res.signed_datetime)
            if tat_h:
                per_rad_tat[res.author_doctor_id.id].append(tat_h)

        for rad_id, cnt in per_rad_counts.items():
            self.env["clinical.imaging.kpi.radiologist.line"].create({
                "snapshot_id": self.id,
                "radiologist_id": rad_id,
                "result_signed": cnt,
                "tat_acq_to_sign_avg_h": round(self._avg(per_rad_tat.get(rad_id, [])), 2),
            })

    # -------------------------------------------------------------------------
    # Drill-down Actions
    # -------------------------------------------------------------------------
    def _action_window(self, name, res_model, domain, view_mode="list,form"):
        self.ensure_one()
        return {
            "name": name,
            "type": "ir.actions.act_window",
            "res_model": res_model,
            "view_mode": view_mode,
            "domain": domain,
            "target": "current",
            "context": {},
        }

    def action_open_results_finalized(self):
        self.ensure_one()
        if not self._has_model("clinical.imaging.result"):
            raise UserError(_("Imaging Result model is not available."))
        domain = [
            ("company_id", "=", self.company_id.id),
            ("state", "in", ["final", "amended"]),
            ("signed_datetime", ">=", self.date_start),
            ("signed_datetime", "<=", self.date_end),
        ]
        return self._action_window(_("Finalized Results"), "clinical.imaging.result", domain)

    def action_open_studies(self):
        self.ensure_one()
        if not self._has_model("clinical.imaging.study"):
            raise UserError(_("Imaging Study model is not available."))
        domain = [
            ("company_id", "=", self.company_id.id),
            ("study_datetime", ">=", self.date_start),
            ("study_datetime", "<=", self.date_end),
        ]
        return self._action_window(_("Studies in Period"), "clinical.imaging.study", domain, view_mode="list,form,kanban")

    def action_open_series(self):
        self.ensure_one()
        if not self._has_model("clinical.imaging.series"):
            raise UserError(_("Imaging Series model is not available."))
        domain = [
            ("company_id", "=", self.company_id.id),
            ("series_datetime", ">=", self.date_start),
            ("series_datetime", "<=", self.date_end),
        ]
        return self._action_window(_("Series in Period"), "clinical.imaging.series", domain)

    def action_open_device_downtime(self):
        self.ensure_one()
        if not self._has_model("clinical.imaging.device.downtime"):
            raise UserError(_("Device Downtime model is not available."))
        domain = [
            ("device_id.company_id", "=", self.company_id.id),
            ("state", "=", "closed"),
            ("end_datetime", ">=", self.date_start),
            ("start_datetime", "<=", self.date_end),
        ]
        return self._action_window(_("Device Downtime (overlap period)"), "clinical.imaging.device.downtime", domain)


# =============================================================================
# Lines - Modality
# =============================================================================
class ClinicalImagingKpiModalityLine(models.Model):
    _name = "clinical.imaging.kpi.modality.line"
    _description = "Imaging KPI Modality Line"
    _order = "snapshot_id, modality"
    _check_company_auto = True

    snapshot_id = fields.Many2one(
        "clinical.imaging.kpi.snapshot", string="Snapshot",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="snapshot_id.company_id", store=True, readonly=True
    )
    modality = fields.Selection(
        [
            ("XR", "X-Ray"),
            ("CT", "CT"),
            ("MR", "MRI"),
            ("US", "Ultrasound"),
            ("DX", "Digital Radiography"),
            ("MG", "Mammography"),
            ("NM", "Nuclear Medicine"),
            ("OT", "Other"),
        ],
        string="Modality", required=True
    )
    study_count = fields.Integer(string="Studies")
    result_final_count = fields.Integer(string="Finalized Results")
    tat_acq_to_sign_avg_h = fields.Float(string="Avg TAT Acq→Sign (h)")


# =============================================================================
# Lines - Device
# =============================================================================
class ClinicalImagingKpiDeviceLine(models.Model):
    _name = "clinical.imaging.kpi.device.line"
    _description = "Imaging KPI Device Line"
    _order = "snapshot_id, device_id"
    _check_company_auto = True

    snapshot_id = fields.Many2one(
        "clinical.imaging.kpi.snapshot", string="Snapshot",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="snapshot_id.company_id", store=True, readonly=True
    )
    device_id = fields.Many2one("clinical.imaging.device", string="Device", required=True)
    modality = fields.Selection(
        [
            ("XR", "X-Ray"),
            ("CT", "CT"),
            ("MR", "MRI"),
            ("US", "Ultrasound"),
            ("DX", "Digital Radiography"),
            ("MG", "Mammography"),
            ("NM", "Nuclear Medicine"),
            ("OT", "Other"),
        ],
        string="Modality"
    )
    study_count = fields.Integer(string="Studies")
    downtime_h = fields.Float(string="Downtime (h)")
    utilization_ratio = fields.Float(string="Utilization Ratio (0..1)")
    qc_status = fields.Selection(
        [("ok", "OK"), ("due", "Due"), ("overdue", "Overdue")],
        string="QC Status"
    )


# =============================================================================
# Lines - Radiologist Productivity
# =============================================================================
class ClinicalImagingKpiRadiologistLine(models.Model):
    _name = "clinical.imaging.kpi.radiologist.line"
    _description = "Imaging KPI Radiologist Line"
    _order = "snapshot_id, result_signed desc"
    _check_company_auto = True

    snapshot_id = fields.Many2one(
        "clinical.imaging.kpi.snapshot", string="Snapshot",
        required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", string="Company",
        related="snapshot_id.company_id", store=True, readonly=True
    )
    radiologist_id = fields.Many2one(
        "hr.employee", string="Radiologist",
        domain=[("is_doctor", "=", True)]
    )
    result_signed = fields.Integer(string="Results Signed")
    tat_acq_to_sign_avg_h = fields.Float(string="Avg TAT Acq→Sign (h)")


# \\\ Pindahan DARI clinical_imaging_report ///
# =============================================================================
# Extensions on Result: defaulting & rendering helpers
# =============================================================================
class ClinicalImagingResult(models.Model):
    _inherit = "clinical.imaging.result"

    report_template_id = fields.Many2one(
        "clinical.imaging.report.template",
        string="Report Template",
        help="Template used to render this result. "
             "Defaults from Imaging Type or company default.",
    )

    @api.onchange("imaging_id")
    def _onchange_imaging_set_default_template(self):
        for rec in self:
            if rec.report_template_id:
                continue
            tmpl = rec._get_default_report_template()
            if tmpl:
                rec.report_template_id = tmpl.id
       
    def action_open_key_images(self):
        self.ensure_one()
        return {
            "name": _("Key Images"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.image",
            "view_mode": "list,form,kanban",
            "domain": [("id", "in", self.key_image_ids.ids)],
            "target": "current",
        }

    def action_open_findings(self):
        self.ensure_one()
        return {
            "name": _("Findings"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.finding",
            "view_mode": "list,form,kanban",
            "domain": [("id", "in", self.finding_ids.ids)],
            "target": "current",
        }

    def action_add_existing_finding(self):
        """Open a chooser to link existing findings for the same imaging."""
        self.ensure_one()
        return {
            "name": _("Add Existing Finding"),
            "type": "ir.actions.act_window",
            "res_model": "clinical.imaging.finding",
            "view_mode": "list,form",
            "domain": [("imaging_id", "=", self.imaging_id.id)],
            "target": "current",
            "context": {"default_imaging_id": self.imaging_id.id},
        }

    def _get_default_report_template(self):
        """Resolve default template by priority:
           1) Imaging Type's default report_template_id (if set in type)
           2) Company default template (is_default_company)
           3) Any template filtered by modality
        """
        self.ensure_one()
        imaging = self.imaging_id
        # from type
        if imaging and imaging.imaging_type_id and imaging.imaging_type_id.report_template_id:
            return imaging.imaging_type_id.report_template_id
        # company default
        tmpl = self.env["clinical.imaging.report.template"].search([
            ("company_id", "=", self.company_id.id),
            ("is_default_company", "=", True),
            ("active", "=", True),
        ], limit=1, order="sequence, id")
        if tmpl:
            return tmpl
        # modality match
        modality = imaging.imaging_type_id.modality if imaging and imaging.imaging_type_id else False
        if modality:
            tmpl = self.env["clinical.imaging.report.template"].search([
                ("company_id", "=", self.company_id.id),
                ("modality", "=", modality),
                ("active", "=", True),
            ], limit=1, order="sequence, id")
            if tmpl:
                return tmpl
        # fallback any active
        return self.env["clinical.imaging.report.template"].search([
            ("company_id", "=", self.company_id.id),
            ("active", "=", True),
        ], limit=1, order="sequence, id")

    def action_preview_current_template(self):
        """Preview currently selected template using standard PDF report."""
        self.ensure_one()
        if not self.report_template_id:
            tmpl = self._get_default_report_template()
            if tmpl:
                self.report_template_id = tmpl.id
        report = self.env.ref("clinic_imaging.report_clinical_imaging_result", raise_if_not_found=False)
        if not report:
            raise UserError(_("Report action 'clinic_imaging.report_clinical_imaging_result' not found."))
        return report.report_action(self)

    # Expose HTML (useful for portal/wizard)
    def get_rendered_html(self):
        """Return the HTML string produced by the selected template."""
        self.ensure_one()
        tmpl = self.report_template_id or self._get_default_report_template()
        if not tmpl:
            raise UserError(_("No report template available for rendering."))
        return tmpl.render_html_from_template(self)

# =============================================================================
# Clinical Imaging Finding (structured lesion/observation)
# =============================================================================
class ClinicalImagingFindingKpi(models.Model):
    """
    Structured imaging finding (e.g., pulmonary nodule, hepatic lesion, fracture).
    Links to Imaging/Study/Series/Image for provenance, and to Result for reporting.

    Key features:
      - Standardized categorization (benign/suspicious), risk scores (BI-RADS, LI-RADS, PI-RADS, Lung-RADS)
      - Location & laterality, organ/segment
      - Size measurements (long/short axis) + optional detailed measure lines
      - Evolution/trend tracking vs prior (stable/increase/decrease/resolved)
      - Portal visibility with privacy levels
      - Many2many linkage to Results (bidirectional with clinical.imaging.result.finding_ids)
    """
    _inherit = "clinical.imaging.finding"

    result_ids = fields.Many2many(
        "clinical.imaging.result",
        "clinical_imaging_result_finding_rel",
        "finding_id",
        "result_id",
        string="Results",
        help="Results that include this finding.",
    )
    
    # Linking helpers
    def action_add_to_result(self, result_id=None):
        """
        Add this finding to a Result. If result_id not provided, use latest final/amended result.
        """
        Result = self.env["clinical.imaging.result"]
        for rec in self:
            target = False
            if result_id:
                target = Result.browse(result_id).exists()
            elif rec.imaging_id:
                target = Result.search(
                    [("imaging_id", "=", rec.imaging_id.id), ("state", "in", ["final", "amended"])],
                    order="signed_datetime desc, write_date desc, id desc",
                    limit=1,
                )
            if not target:
                raise UserError(_("No target Result found to link this finding."))
            rec.result_ids = [(4, target.id)]
            target.message_post(body=_("Finding %s linked to this Result.") % rec.display_name)


# =============================================================================
# Clinical Imaging Image (DICOM Instance / Rendered Image)
# =============================================================================
class ClinicalImagingImageKpi(models.Model):
    """
    Represents a single DICOM SOP Instance (or a rendered image file) inside a Series.
    Stores DICOM identifiers (SOP Instance UID, SOP Class UID), key pixel metadata,
    display parameters, and binary content (thumbnail/preview and/or original file).

    Integrations:
      - Patient, Appointment, Encounter, Treatment: propagated via Series -> Study -> Imaging.
      - Device/Room: indirect via Study/Series -> Device.
      - Result: images can be marked as key and linked from results.
      - Portal: optional publishing with privacy level.
      - PACS/Viewer: endpoint URL and status hooks.
    """
    _inherit = "clinical.imaging.image"
    
    def action_add_to_result(self, result_id=None):
        """
        Add this image to a Result's key images.
        Requires model 'clinical.imaging.result' to exist (same module).
        """
        Result = self.env["clinical.imaging.result"]
        for rec in self:
            # Find the latest final/amended result for the imaging if none provided
            dest = False
            if result_id:
                dest = Result.browse(result_id).exists()
            else:
                dest = Result.search(
                    [("imaging_id", "=", rec.imaging_id.id), ("state", "in", ["final", "amended"])],
                    order="signed_datetime desc, write_date desc, id desc",
                    limit=1,
                )
            if not dest:
                raise UserError(_("No target Result found to add this image."))
            dest.key_image_ids = [(4, rec.id)]
            rec.message_post(body=_("Image added to Result %s as key image.") % dest.display_name)

# =============================================================================
# Image Annotation (ROIs, measurements, comments)
# =============================================================================
class ClinicalImagingImageAnnotation(models.Model):
    """
    Stores structured annotations attached to an Image:
      - ROI geometry (point/line/rect/circle/polygon/polyline)
      - Optional measurement values and units
      - Optional linkage to a structured finding
    Geometry is stored as JSON (screen/pixel or patient space as provided by the viewer).
    """
    _inherit = "clinical.imaging.image.annotation"

    result_id = fields.Many2one(
        "clinical.imaging.result",
        string="Linked Result",
        help="Optional diagnostic result this annotation belongs to.",
    )
