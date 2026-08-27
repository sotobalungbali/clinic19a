# Forecast Methods

## Naive

Next period equals the most recent actual value. Useful as a baseline.

## Moving Average

Forecast is the mean of the latest configured window. Future predictions are
fed into the rolling window deterministically.

## Linear Trend

Ordinary least-squares trend over sequential periods. The release reports:
- slope;
- MAE;
- MAPE where actual is non-zero;
- residual standard deviation;
- an indicative ±1.96 residual-standard-deviation range.

These are baseline statistical indicators. The software must not present them
as guaranteed outcomes.
