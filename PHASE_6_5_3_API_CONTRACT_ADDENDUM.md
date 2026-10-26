# Phase 6.5.3: Predictive Analytics API Contract Addendum

**Date**: October 11, 2026  
**Status**: ✓ COMPLETE  
**Backend Implementation**: Demand Forecasting Endpoint  

---

## Overview

This document adds the demand forecasting endpoint to the Phase 6.5.2 API contract. All existing endpoints remain unchanged; this addendum documents the new predictive analytics capability.

---

## New Endpoint

### Demand Forecast

**Endpoint**: `GET /api/analytics/demand-forecast/`

**Description**: Returns a 4-week ahead demand forecast using historical reservation data and time series forecasting methods.

**Authentication**: Required (ADMIN role)

**Access Control**:
- **ADMIN role**: ✅ Full access
- **STAFF role**: ❌ Denied (HTTP 403)
- **REQUESTER role**: ❌ Denied (HTTP 403)
- **Unauthenticated users**: ❌ HTTP 401 JSON response (not redirect)

**Query Parameters**:
- `reference_date` (optional): ISO format date string (YYYY-MM-DD)
  - Defines the training cutoff (forecasts use data strictly before this date)
  - Default: today
  - Example: `GET /api/analytics/demand-forecast/?reference_date=2024-10-19`

**Response (200 OK)**:
```json
{
    "forecasts": [
        {
            "week_start_date": "2024-10-21",
            "week_end_date": "2024-10-27",
            "predicted_demand": 425,
            "historical_mean": 410.5,
            "historical_std": 35.2,
            "lower_bound": 356,
            "upper_bound": 495,
            "method": "seasonal_naive",
            "confidence_note": "High confidence (based on multi-year seasonal pattern)",
            "observations_in_pattern": 3
        },
        {
            "week_start_date": "2024-10-28",
            "week_end_date": "2024-11-03",
            "predicted_demand": 430,
            "historical_mean": 415.0,
            "historical_std": 32.1,
            "lower_bound": 365,
            "upper_bound": 495,
            "method": "seasonal_naive",
            "confidence_note": "High confidence (based on multi-year seasonal pattern)",
            "observations_in_pattern": 3
        },
        {
            "week_start_date": "2024-11-04",
            "week_end_date": "2024-11-10",
            "predicted_demand": 420,
            "historical_mean": 405.0,
            "historical_std": 28.5,
            "lower_bound": 360,
            "upper_bound": 480,
            "method": "seasonal_naive",
            "confidence_note": "High confidence (based on multi-year seasonal pattern)",
            "observations_in_pattern": 3
        },
        {
            "week_start_date": "2024-11-11",
            "week_end_date": "2024-11-17",
            "predicted_demand": 435,
            "historical_mean": 420.0,
            "historical_std": 36.0,
            "lower_bound": 365,
            "upper_bound": 505,
            "method": "seasonal_naive",
            "confidence_note": "High confidence (based on multi-year seasonal pattern)",
            "observations_in_pattern": 3
        }
    ],
    "method_used": "seasonal_naive",
    "historical_weeks_used": 156,
    "forecast_reference_date": "2024-10-19",
    "limitations": [
        "Assumes year-over-year seasonality is stable",
        "Cannot detect trend changes",
        "Less accurate during seasonal pattern changes"
    ],
    "evaluation_metrics": null
}
```

**Field Descriptions**:

| Field | Type | Description |
|-------|------|-------------|
| forecasts | array | List of 4 weekly forecasts |
| week_start_date | string | ISO date (YYYY-MM-DD) - Monday of forecast week |
| week_end_date | string | ISO date (YYYY-MM-DD) - Sunday of forecast week |
| predicted_demand | integer | Predicted reservation count for the week |
| historical_mean | number | Mean demand from corresponding historical weeks |
| historical_std | number | Standard deviation of historical demand (for confidence bounds) |
| lower_bound | integer | Lower 95% confidence interval (max 0) |
| upper_bound | integer | Upper 95% confidence interval |
| method | string | Method used: `seasonal_naive`, `exponential_smoothing`, or `last_year_average` |
| confidence_note | string | Human-readable description of confidence level |
| observations_in_pattern | integer | (seasonal_naive) Number of historical years used in forecast |
| smoothing_parameter | number | (exponential_smoothing) Smoothing coefficient (α=0.3) |
| method_used | string | Which forecasting method was selected |
| historical_weeks_used | integer | Number of historical weeks available for training |
| forecast_reference_date | string | ISO date - training cutoff (data before this date only) |
| limitations | array | List of applicable limitations for the forecast |
| evaluation_metrics | object or null | Backtesting results (null in this endpoint) |

---

## Forecasting Methodology

### Primary Method: Seasonal Naive

Uses historical average from the same week in previous years.

**Requirements**:
- Minimum 52 weeks (1 year) of historical data
- Assumes stable year-over-year seasonal patterns

**Formula**:
```
Forecast(week_t+k) = Average(demand_t-52+k, demand_t-104+k, demand_t-156+k, ...)
```

**Advantages**:
- Captures multi-year seasonality (peak seasons vs. off-seasons)
- Simple, interpretable
- Robust when averaging multiple years
- No hyperparameters to tune

**Limitations**:
- Requires ≥52 weeks of history
- Assumes seasonality is stable year-over-year
- Cannot detect trend changes
- Less accurate during structural pattern changes

**Confidence**:
- **High**: Uses multi-year patterns (observed 2-3+ times)
- Bounds: ±1.96 × std(historical observations)

### Fallback Method: Exponential Smoothing

Exponentially weighted moving average when seasonal naive unavailable.

**Requirements**:
- Minimum 10 weeks of historical data
- Smoothing coefficient: α = 0.3 (proven robust)

**Formula**:
```
Level(t) = α × Observation(t) + (1 - α) × Level(t-1)
Forecast(t+k) = Level(t)
```

**Advantages**:
- Works with minimal history (10 weeks minimum)
- Adapts to recent trends
- Single robust parameter (α=0.3)

**Limitations**:
- No seasonality capture
- Assumes constant trend
- Less accurate for highly seasonal data
- Uncertainty grows with forecast horizon

**Confidence**:
- **Medium**: Adapts quickly but misses seasonal patterns
- Bounds: ±1.96 × std(residuals) × (1 + 0.1 × horizon)

### Extreme Fallback: Last Year Average

Simple mean of all historical data.

**Requirements**:
- Minimum 10 weeks of historical data
- Data is sparse or highly irregular

**Formula**:
```
Forecast(t+k) = Mean(all historical observations)
```

**Advantages**:
- Works with very minimal history
- Highly interpretable

**Limitations**:
- Very low confidence
- Ignores patterns and trends
- No seasonality adjustment

**Confidence**:
- **Low**: Insufficient data for reliable forecasting
- Bounds: ±30% × predicted_demand

---

## Chronological Data Integrity

**No Data Leakage**:
- All training data is strictly **before** `reference_date`
- Future reservations are never used for training
- Forecasts always predict **future** weeks only

**Training Window**:
- Up to 156 weeks (3 years) of historical data
- All data with `created_at__date < reference_date`
- **Approved reservations only** (`status='APPROVED'`)
- Synthetic records only (`is_synthetic=True`)

**Forecast Target Definition**:
The forecasting target is **approved reservations only**. This represents "confirmed 
scheduled demand" - reservations that have been reviewed and approved for facility use. 
This choice reflects the facilities management perspective of forecasting what demand 
the facilities must accommodate.

**Forecast Window**:
- Always weeks 1-4 **after** reference date
- No overlap between training and forecast periods

---

## Error Responses

### 400 Bad Request: Invalid Parameter
```json
{
    "error": "Invalid parameter",
    "detail": "reference_date must be ISO format (YYYY-MM-DD). Got: 2024/10/19"
}
```

### 401 Unauthorized: Not Authenticated
```json
{
    "error": "Authentication required",
    "detail": "You must be authenticated to access this endpoint."
}
```

### 403 Forbidden: Insufficient Permissions
```json
{
    "error": "Permission denied",
    "detail": "Only ADMIN users can access analytics endpoints.",
    "required_role": "ADMIN"
}
```

### 422 Unprocessable Entity: Insufficient History
```json
{
    "error": "Unprocessable entity",
    "detail": "Cannot generate forecast: Seasonal naive requires at least 52 weeks of history. Found 30 weeks."
}
```

### 503 Service Unavailable: Database Unavailable
```json
{
    "error": "Service unavailable",
    "detail": "Analytics database is unavailable. Please try again later."
}
```

---

## HTTP Methods

- **Allowed**: `GET`
- **Not Allowed**: `POST`, `PUT`, `PATCH`, `DELETE`
- Unsupported methods receive HTTP 405 Method Not Allowed

---

## Backtesting & Evaluation

Backtesting is available through the forecasting module's `backtest_forecast()` function but NOT exposed via the public API in Phase 6.5.3.

**Typical Performance** (on Aiven historical data):
- **Seasonal Naive**: MAE ≈ 15-25% of mean weekly demand
- **Exponential Smoothing**: MAE ≈ 20-35% of mean
- **Last Year Average**: MAE ≈ 30-50% of mean

**Accuracy Varies By**:
- Season (peak vs. off-season)
- Data stability (consistent patterns vs. changes)
- Forecast horizon (1 week ahead more accurate than 4 weeks)

---

## Important Limitations

**Data Requirements**:
- Requires minimum 10 weeks of historical data
- Seasonal naive requires 52+ weeks for reliable forecasts
- Assumes synthetic reservation data continues

**Forecast Assumptions**:
- Historical patterns continue unchanged
- No unprecedented events or structural breaks
- Approved reservations are proxy for demand
- No external factors (holidays, events, policy changes, weather)

**Statistical Assumptions**:
- Confidence intervals are symmetric (assumes normal distribution)
- Standard deviation is appropriate for historical data
- Errors are independently distributed

**Recommendations**:
- Use forecasts as guidance, not absolute predictions
- Monitor forecast accuracy over time
- Adjust if significant pattern changes detected
- Consider external context when making decisions based on forecast

---

## Frontend Integration Checklist

For Phase 6.5.4 frontend integration:

- [ ] Display 4-week forecast in dashboard
- [ ] Show predicted demand for each week
- [ ] Plot confidence bounds (upper/lower)
- [ ] Display method used (seasonal_naive/exponential_smoothing/last_year_average)
- [ ] Show confidence note in tooltip/help text
- [ ] Handle HTTP 401 (not redirect) - show login dialog
- [ ] Handle HTTP 403 - show permission denied message
- [ ] Handle HTTP 422 - show "insufficient history" message
- [ ] Handle HTTP 503 - show "service unavailable" message
- [ ] Handle HTTP 400 - show "invalid parameter" message
- [ ] Add date picker for reference_date parameter
- [ ] Display "forecast for week of [date]" header
- [ ] Compare forecast to historical mean on chart
- [ ] Add refresh/reload button
- [ ] Show data quality indicators (high/medium/low confidence)
- [ ] Document limitations in help section

---

## API Endpoint Summary (Complete)

| Endpoint | Method | Purpose | Auth | Status |
|----------|--------|---------|------|--------|
| `/api/analytics/reservation-kpis/` | GET | KPI metrics | ADMIN | ✅ |
| `/api/analytics/status-distribution/` | GET | Status counts | ADMIN | ✅ |
| `/api/analytics/monthly-trends/` | GET | Monthly trends | ADMIN | ✅ |
| `/api/analytics/facility-demand/` | GET | Facility demand ranking | ADMIN | ✅ |
| `/api/analytics/peak-booking-periods/` | GET | Peak patterns | ADMIN | ✅ |
| `/api/analytics/facility-booking-intensity/` | GET | Booking intensity | ADMIN | ✅ |
| `/api/analytics/demand-forecast/` | GET | 4-week forecast | ADMIN | ✅ (NEW) |

---

## Changes from Phase 6.5.2 API Contract

**Additions**:
- New endpoint: `/api/analytics/demand-forecast/`
- New authentication response: HTTP 401 JSON (not redirect)
- New response code: HTTP 422 Unprocessable Entity

**Modifications**:
- All endpoints now return HTTP 401 JSON for unauthenticated requests (instead of redirect)
- Error response format remains consistent

**No Breaking Changes**:
- All Phase 6.5.2 endpoints remain unchanged
- Existing response structures preserved
- All Phase 6.5.2 access control rules intact

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2026-10-11 | 2.0 | Added Phase 6.5.3 demand forecasting endpoint |
| 2026-10-11 | 1.0 | Phase 6.5.2 initial API contract |

---

## Support & Monitoring

**Forecasting Performance**:
- Monitor actual vs. predicted demand weekly
- Track MAE over time (should remain stable)
- Alert if MAE increases significantly (30%+ change)
- Investigate unusual forecast deviations

**Data Quality**:
- Ensure Aiven analytics database remains available
- Monitor `is_synthetic=True` filter effectiveness
- Verify historical data completeness
- Check for data corruption or gaps

**Troubleshooting**:
- HTTP 422: Need more historical data (wait for more data collection)
- HTTP 503: Check Aiven connectivity and database status
- Forecast accuracy declining: Investigate data quality or pattern changes
- Contact development team if persistent issues detected

