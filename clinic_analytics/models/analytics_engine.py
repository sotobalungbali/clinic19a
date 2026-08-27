# -*- coding: utf-8 -*-

import json
from datetime import datetime, time, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClinicAnalyticsEngine(models.AbstractModel):
    """Fixed-source analytics engine.

    No model, field or domain name is accepted from external/user input.
    Each KPI code maps to a reviewed adapter below.
    """

    _name = "clinic.analytics.engine"
    _description = "Clinic Analytics Fixed Source Engine"

    @api.model
    def _percentage(self, numerator, denominator):
        return (float(numerator) / float(denominator) * 100.0) if denominator else 0.0

    @api.model
    def _date_domain(
        self,
        model_name,
        date_field,
        date_from,
        date_to,
    ):
        Model = self.env[model_name]
        if date_field not in Model._fields:
            raise ValidationError(
                _("Source field %s.%s is not available.") % (model_name, date_field)
            )

        field = Model._fields[date_field]
        domain = []
        if field.type == "datetime":
            if date_from:
                start = datetime.combine(fields.Date.to_date(date_from), time.min)
                domain.append((date_field, ">=", fields.Datetime.to_string(start)))
            if date_to:
                end = datetime.combine(fields.Date.to_date(date_to), time.max)
                domain.append((date_field, "<=", fields.Datetime.to_string(end)))
        else:
            if date_from:
                domain.append((date_field, ">=", fields.Date.to_date(date_from)))
            if date_to:
                domain.append((date_field, "<=", fields.Date.to_date(date_to)))
        return domain

    @api.model
    def _source_domain(
        self,
        model_name,
        company,
        branch,
        date_field,
        date_from,
        date_to,
        branch_path=None,
        extra=None,
    ):
        Model = self.env[model_name]
        domain = list(extra or [])

        if "company_id" in Model._fields:
            domain.append(("company_id", "=", company.id))

        if branch:
            if "branch_id" in Model._fields:
                domain.append(("branch_id", "=", branch.id))
            elif branch_path:
                domain.append((branch_path, "=", branch.id))
            else:
                raise ValidationError(
                    _(
                        "KPI source %s has no authoritative Branch field/path. "
                        "Branch analytics therefore fail closed."
                    )
                    % model_name
                )

        domain += self._date_domain(
            model_name,
            date_field,
            date_from,
            date_to,
        )
        return domain

    @api.model
    def _result(self, value, model_name, domain, source_count, note=""):
        return {
            "value": float(value or 0.0),
            "source_model": model_name,
            "source_count": int(source_count or 0),
            "source_domain_json": json.dumps(
                domain,
                default=str,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "note": note or "",
        }

    @api.model
    def evaluate(
        self,
        source_key,
        company,
        branch,
        date_from,
        date_to,
    ):
        method = getattr(self, f"_metric_{source_key}", None)
        if not method:
            raise ValidationError(
                _("Unsupported governed KPI source: %s") % source_key
            )
        return method(company, branch, date_from, date_to)

    # ------------------------------------------------------------------
    # Financial
    # ------------------------------------------------------------------
    @api.model
    def _metric_revenue_total(self, company, branch, date_from, date_to):
        model_name = "clinic.billing.invoice"
        domain = self._source_domain(
            model_name, company, branch,
            "invoice_date", date_from, date_to,
            branch_path="patient_id.branch_id",
            extra=[("state", "in", ("posted", "paid"))],
        )
        records = self.env[model_name].sudo().search(domain)
        return self._result(
            sum(records.mapped("amount_total")),
            model_name, domain, len(records),
            _("Posted and paid Clinic Billing invoice total."),
        )

    @api.model
    def _metric_revenue_paid(self, company, branch, date_from, date_to):
        model_name = "clinic.billing.invoice"
        domain = self._source_domain(
            model_name, company, branch,
            "invoice_date", date_from, date_to,
            branch_path="patient_id.branch_id",
            extra=[("state", "=", "paid")],
        )
        records = self.env[model_name].sudo().search(domain)
        return self._result(
            sum(records.mapped("amount_total")),
            model_name, domain, len(records),
            _("Fully paid Clinic Billing invoice value."),
        )

    # ------------------------------------------------------------------
    # Booking / patient retention
    # ------------------------------------------------------------------
    @api.model
    def _booking_domain(self, company, branch, date_from, date_to, extra=None):
        return self._source_domain(
            "booking.booking", company, branch,
            "start_datetime", date_from, date_to,
            branch_path="patient_id.branch_id",
            extra=extra,
        )

    @api.model
    def _metric_booking_count(self, company, branch, date_from, date_to):
        domain = self._booking_domain(company, branch, date_from, date_to)
        count = self.env["booking.booking"].sudo().search_count(domain)
        return self._result(count, "booking.booking", domain, count)

    @api.model
    def _metric_booking_completion_rate(self, company, branch, date_from, date_to):
        domain = self._booking_domain(company, branch, date_from, date_to)
        records = self.env["booking.booking"].sudo().search(domain)
        done = len(records.filtered(lambda rec: rec.state == "done"))
        return self._result(
            self._percentage(done, len(records)),
            "booking.booking", domain, len(records),
            _("Completed bookings divided by all bookings in the period."),
        )

    @api.model
    def _metric_booking_no_show_rate(self, company, branch, date_from, date_to):
        domain = self._booking_domain(company, branch, date_from, date_to)
        records = self.env["booking.booking"].sudo().search(domain)
        no_show = len(records.filtered("is_no_show"))
        return self._result(
            self._percentage(no_show, len(records)),
            "booking.booking", domain, len(records),
            _("Bookings marked No Show divided by all bookings in the period."),
        )

    @api.model
    def _metric_unique_patients(self, company, branch, date_from, date_to):
        domain = self._booking_domain(
            company, branch, date_from, date_to,
            extra=[("state", "=", "done")],
        )
        records = self.env["booking.booking"].sudo().search(domain)
        patient_count = len(records.mapped("patient_id"))
        return self._result(
            patient_count,
            "booking.booking", domain, len(records),
            _("Unique patient contacts with a completed booking."),
        )

    @api.model
    def _metric_repeat_patient_rate(self, company, branch, date_from, date_to):
        current_domain = self._booking_domain(
            company, branch, date_from, date_to,
            extra=[("state", "=", "done")],
        )
        current = self.env["booking.booking"].sudo().search(current_domain)
        patients = current.mapped("patient_id")
        if not patients:
            return self._result(0.0, "booking.booking", current_domain, 0)

        previous_domain = [
            ("company_id", "=", company.id),
            ("state", "=", "done"),
            ("patient_id", "in", patients.ids),
        ]
        if branch:
            previous_domain.append(("patient_id.branch_id", "=", branch.id))
        start = datetime.combine(fields.Date.to_date(date_from), time.min)
        previous_domain.append(
            ("start_datetime", "<", fields.Datetime.to_string(start))
        )
        previous = self.env["booking.booking"].sudo().search(previous_domain)
        repeat_patients = previous.mapped("patient_id")
        return self._result(
            self._percentage(len(repeat_patients), len(patients)),
            "booking.booking", current_domain, len(current),
            _(
                "Unique completed-booking patients with at least one earlier "
                "completed booking divided by unique completed patients."
            ),
        )

    # ------------------------------------------------------------------
    # Membership / Wallet
    # ------------------------------------------------------------------
    @api.model
    def _metric_membership_active(self, company, branch, date_from, date_to):
        model_name = "membership.contract"
        domain = [
            ("company_id", "=", company.id),
            ("state", "in", ("active", "on_hold")),
            ("start_date", "<=", fields.Date.to_date(date_to)),
            "|",
            ("end_date", "=", False),
            ("end_date", ">=", fields.Date.to_date(date_to)),
        ]
        if branch:
            domain.append(("partner_id.branch_id", "=", branch.id))
        count = self.env[model_name].sudo().search_count(domain)
        return self._result(
            count, model_name, domain, count,
            _("Active/on-hold membership contracts at period end."),
        )

    @api.model
    def _metric_membership_renewal_rate(self, company, branch, date_from, date_to):
        model_name = "membership.contract"
        domain = self._source_domain(
            model_name, company, branch,
            "start_date", date_from, date_to,
            branch_path="partner_id.branch_id",
        )
        records = self.env[model_name].sudo().search(domain)
        renewals = len(records.filtered(lambda rec: bool(rec.renewed_from_id)))
        return self._result(
            self._percentage(renewals, len(records)),
            model_name, domain, len(records),
            _("New contracts in the period that renew an earlier contract."),
        )

    @api.model
    def _metric_wallet_balance(self, company, branch, date_from, date_to):
        model_name = "clinic.wallet"
        domain = [
            ("company_id", "=", company.id),
            ("state", "=", "active"),
        ]
        if branch:
            domain.append(("partner_id.branch_id", "=", branch.id))
        records = self.env[model_name].sudo().search(domain)
        return self._result(
            sum(records.mapped("balance")),
            model_name, domain, len(records),
            _("Current active wallet balance; this is a point-in-time KPI."),
        )

    # ------------------------------------------------------------------
    # Patient experience
    # ------------------------------------------------------------------
    @api.model
    def _feedback_records(self, company, branch, date_from, date_to):
        model_name = "clinic.feedback"
        domain = self._source_domain(
            model_name, company, branch,
            "submitted_at", date_from, date_to,
            extra=[("state", "!=", "draft")],
        )
        return domain, self.env[model_name].sudo().search(domain)

    @api.model
    def _metric_feedback_nps(self, company, branch, date_from, date_to):
        domain, records = self._feedback_records(
            company, branch, date_from, date_to
        )
        values = [value for value in records.mapped("nps_score") if value >= 0]
        promoters = len([value for value in values if value >= 9])
        detractors = len([value for value in values if value <= 6])
        nps = (
            ((promoters - detractors) / len(values)) * 100.0
            if values else 0.0
        )
        return self._result(
            nps, "clinic.feedback", domain, len(records),
            _("Net Promoter Score from submitted feedback."),
        )

    @api.model
    def _metric_feedback_avg_rating(self, company, branch, date_from, date_to):
        domain, records = self._feedback_records(
            company, branch, date_from, date_to
        )
        ratings = [value for value in records.mapped("overall_rating") if value > 0]
        average = sum(ratings) / len(ratings) if ratings else 0.0
        return self._result(
            average, "clinic.feedback", domain, len(records),
            _("Average overall patient rating from submitted feedback."),
        )

    # ------------------------------------------------------------------
    # Quality / Incident
    # ------------------------------------------------------------------
    @api.model
    def _metric_quality_score(self, company, branch, date_from, date_to):
        model_name = "clinic.quality.check"
        domain = self._source_domain(
            model_name, company, branch,
            "planned_date", date_from, date_to,
            extra=[("state", "=", "closed")],
        )
        records = self.env[model_name].sudo().search(domain)
        scores = records.mapped("compliance_score")
        average = sum(scores) / len(scores) if scores else 0.0
        return self._result(
            average, model_name, domain, len(records),
            _("Average compliance score of closed quality checks."),
        )

    @api.model
    def _metric_incident_count(self, company, branch, date_from, date_to):
        model_name = "clinic.incident"
        domain = self._source_domain(
            model_name, company, branch,
            "occurred_at", date_from, date_to,
            extra=[("state", "!=", "cancelled")],
        )
        count = self.env[model_name].sudo().search_count(domain)
        return self._result(count, model_name, domain, count)

    @api.model
    def _metric_critical_incident_count(self, company, branch, date_from, date_to):
        model_name = "clinic.incident"
        domain = self._source_domain(
            model_name, company, branch,
            "occurred_at", date_from, date_to,
            extra=[
                ("state", "!=", "cancelled"),
                ("severity", "=", "critical"),
            ],
        )
        count = self.env[model_name].sudo().search_count(domain)
        return self._result(count, model_name, domain, count)

    # ------------------------------------------------------------------
    # Marketing
    # ------------------------------------------------------------------
    @api.model
    def _metric_marketing_reach(self, company, branch, date_from, date_to):
        model_name = "clinic.marketing.recipient"
        domain = self._source_domain(
            model_name, company, branch,
            "create_date", date_from, date_to,
            extra=[("inclusion_state", "=", "included")],
        )
        count = self.env[model_name].sudo().search_count(domain)
        return self._result(
            count, model_name, domain, count,
            _("Included campaign recipient snapshots created in the period."),
        )

    @api.model
    def _metric_marketing_delivery_rate(self, company, branch, date_from, date_to):
        model_name = "clinic.marketing.recipient"
        domain = self._source_domain(
            model_name, company, branch,
            "create_date", date_from, date_to,
            extra=[("inclusion_state", "=", "included")],
        )
        records = self.env[model_name].sudo().search(domain)
        delivered = records.filtered(
            lambda rec: (
                rec.email_delivery_state in ("sent", "opened", "replied")
                or rec.whatsapp_state in ("sent", "opened")
            )
        )
        return self._result(
            self._percentage(len(delivered), len(records)),
            model_name, domain, len(records),
            _("Recipients with delivered/opened email or sent/opened WhatsApp."),
        )

    # ------------------------------------------------------------------
    # Time-series helpers
    # ------------------------------------------------------------------
    @api.model
    def historical_periods(self, as_of_date, frequency, count):
        """Return complete historical periods ending before the as-of period."""
        as_of = fields.Date.to_date(as_of_date)
        periods = []

        if frequency == "month":
            current_start = as_of.replace(day=1)
            for offset in range(count, 0, -1):
                start = current_start - relativedelta(months=offset)
                end = start + relativedelta(months=1) - timedelta(days=1)
                periods.append((start, end))
            return periods

        if frequency == "week":
            current_start = as_of - timedelta(days=as_of.weekday())
            for offset in range(count, 0, -1):
                start = current_start - timedelta(weeks=offset)
                end = start + timedelta(days=6)
                periods.append((start, end))
            return periods

        raise ValidationError(_("Unsupported forecast frequency."))

    @api.model
    def future_periods(self, as_of_date, frequency, count):
        as_of = fields.Date.to_date(as_of_date)
        periods = []

        if frequency == "month":
            start = as_of.replace(day=1)
            for offset in range(count):
                period_start = start + relativedelta(months=offset)
                period_end = period_start + relativedelta(months=1) - timedelta(days=1)
                periods.append((period_start, period_end))
            return periods

        if frequency == "week":
            start = as_of - timedelta(days=as_of.weekday())
            for offset in range(count):
                period_start = start + timedelta(weeks=offset)
                period_end = period_start + timedelta(days=6)
                periods.append((period_start, period_end))
            return periods

        raise ValidationError(_("Unsupported forecast frequency."))

    @api.model
    def retention_cohort(self, company, branch, cohort_start):
        """30/60/90-day repeat-booking retention without persisting patient IDs."""
        start = fields.Date.to_date(cohort_start).replace(day=1)
        end = start + relativedelta(months=1) - timedelta(days=1)
        horizon_end = end + timedelta(days=90)

        domain = [
            ("company_id", "=", company.id),
            ("state", "=", "done"),
            (
                "start_datetime",
                "<=",
                fields.Datetime.to_string(
                    datetime.combine(horizon_end, time.max)
                ),
            ),
        ]
        if branch:
            domain.append(("patient_id.branch_id", "=", branch.id))

        bookings = self.env["booking.booking"].sudo().search(
            domain,
            order="start_datetime, id",
        )

        by_patient = {}
        for booking in bookings:
            if not booking.patient_id or not booking.start_datetime:
                continue
            when = fields.Datetime.to_datetime(booking.start_datetime)
            by_patient.setdefault(booking.patient_id.id, []).append(when)

        cohort = []
        for patient_id, dates in by_patient.items():
            dates.sort()
            first = dates[0]
            if start <= first.date() <= end:
                cohort.append((patient_id, dates))

        size = len(cohort)
        retained = {30: 0, 60: 0, 90: 0}
        for _patient_id, dates in cohort:
            first = dates[0]
            later = [date for date in dates[1:] if date > first]
            for days in retained:
                if any(date <= first + timedelta(days=days) for date in later):
                    retained[days] += 1

        return {
            "cohort_start": start,
            "cohort_end": end,
            "cohort_size": size,
            "retained_30": retained[30],
            "retained_60": retained[60],
            "retained_90": retained[90],
            "retention_30": self._percentage(retained[30], size),
            "retention_60": self._percentage(retained[60], size),
            "retention_90": self._percentage(retained[90], size),
            "source_count": len(bookings),
        }
