# -*- coding: utf-8 -*-

import math
import statistics

from odoo import api, models, _
from odoo.exceptions import ValidationError


class ClinicAnalyticsForecasting(models.AbstractModel):
    """Transparent baseline forecasting methods with deterministic output."""

    _name = "clinic.analytics.forecasting"
    _description = "Clinic Analytics Forecasting Service"

    @api.model
    def _clamp(self, value, unit):
        value = float(value or 0.0)
        if unit in ("count", "amount", "currency"):
            return max(0.0, value)
        if unit == "percentage":
            return min(100.0, max(0.0, value))
        return value

    @api.model
    def run(
        self,
        values,
        method,
        horizon,
        window,
        unit,
    ):
        values = [float(value or 0.0) for value in values]
        if len(values) < 2:
            raise ValidationError(
                _("At least two historical points are required.")
            )

        fitted = [None] * len(values)
        slope = 0.0

        if method == "naive":
            for index in range(1, len(values)):
                fitted[index] = values[index - 1]
            future = [values[-1]] * horizon

        elif method == "moving_average":
            if window < 2:
                raise ValidationError(
                    _("Moving Average window must be at least 2.")
                )
            for index in range(1, len(values)):
                start = max(0, index - window)
                fitted[index] = statistics.fmean(values[start:index])

            rolling = list(values)
            future = []
            for _step in range(horizon):
                sample = rolling[-window:]
                predicted = statistics.fmean(sample)
                future.append(predicted)
                rolling.append(predicted)

        elif method == "linear_trend":
            n = len(values)
            xs = list(range(n))
            x_mean = statistics.fmean(xs)
            y_mean = statistics.fmean(values)
            denominator = sum((x - x_mean) ** 2 for x in xs)
            slope = (
                sum(
                    (x - x_mean) * (y - y_mean)
                    for x, y in zip(xs, values)
                ) / denominator
                if denominator
                else 0.0
            )
            intercept = y_mean - slope * x_mean
            fitted = [intercept + slope * x for x in xs]
            future = [
                intercept + slope * x
                for x in range(n, n + horizon)
            ]
        else:
            raise ValidationError(
                _("Unsupported forecast method.")
            )

        residuals = [
            actual - predicted
            for actual, predicted in zip(values, fitted)
            if predicted is not None
        ]
        mae = (
            statistics.fmean(abs(value) for value in residuals)
            if residuals
            else 0.0
        )
        mape_terms = [
            abs((actual - predicted) / actual) * 100.0
            for actual, predicted in zip(values, fitted)
            if predicted is not None and abs(actual) > 1e-9
        ]
        mape = statistics.fmean(mape_terms) if mape_terms else 0.0
        residual_std = (
            statistics.pstdev(residuals)
            if len(residuals) > 1
            else abs(residuals[0]) if residuals else 0.0
        )

        future_rows = []
        for predicted in future:
            predicted = self._clamp(predicted, unit)
            margin = 1.96 * residual_std
            future_rows.append({
                "predicted": predicted,
                "lower": self._clamp(predicted - margin, unit),
                "upper": self._clamp(predicted + margin, unit),
            })

        return {
            "fitted": [
                self._clamp(value, unit)
                if value is not None else None
                for value in fitted
            ],
            "future": future_rows,
            "mae": mae,
            "mape": mape,
            "slope": slope,
            "residual_std": residual_std,
        }
