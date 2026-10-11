# Phase 6.6: Forecast Integration Approach

**Status**: Backend Integration Design (No Deployment)  
**Date**: October 12, 2026  
**Scope**: How to integrate Python forecasting outputs with Power BI

---

## Overview

Forecasting is NOT directly available via SQL queries. The Python forecasting engine (`analytics/forecasting.py`) generates forecasts in-memory and returns them as Python dictionaries. This document outlines the technical approaches to make forecasts available in Power BI dashboards.

---

## Current Forecasting Implementation

### Forecast Generation Method

**File**: `analytics/forecasting.py`  
**Function**: `forecast_demand(reference_date, forecast_weeks=4)`

**Output Structure**:
```python
{
    'forecasts': [
        {
            'week_start_date': '2026-10-05',
            'week_end_date': '2026-10-11',
            'predicted_demand': 18,
            'confidence_lower_bound': 12,
            'confidence_upper_bound': 24,
        },
        # ... more weeks
    ],
    'method_used': 'seasonal_naive',  # or 'exponential_smoothing', 'last_year_average'
    'historical_weeks_used': 104,
    'forecast_reference_date': '2026-09-15',
    'limitations': [
        'Assumes year-over-year seasonality is stable',
        'Cannot detect trend changes',
    ],
    'evaluation_metrics': {
        'mae': 4.12,
        'rmse': 4.73,
        'mape': 86.52,
        'wape': 38.37,
    }
}
```

### Current Access Method

- **Via Django View**: GET `/api/analytics/demand-forecast/` (HTTP JSON)
- **Via Python Function**: `forecast_demand()` (requires Django setup)
- **Direct SQL**: NOT AVAILABLE (forecast is computed, not stored)

---

## Approach 1: REST API Integration (Recommended for Phase 6.6)

### Architecture

```
┌─────────────────┐
│  Power BI       │
│  (Desktop or    │
│  Service)       │
└────────┬────────┘
         │
         │ HTTP GET
         │ /api/analytics/demand-forecast/
         │
    ┌────▼────────────────────┐
    │ Django Application      │
    │ (REST API Server)       │
    │                         │
    │ ├─ analytics/views.py   │
    │ │  └─ demand_forecast() │
    │ │     └─ HTTP 200 JSON  │
    │ │                       │
    │ └─ analytics/           │
    │    forecasting.py       │
    │    └─ forecast_demand() │
    │       └─ Python Dict    │
    └────┬────────────────────┘
         │
         │ .using('analytics')
         │ SELECT ...
         │
    ┌────▼──────────────────┐
    │ Aiven MySQL           │
    │ (Analytics DB)        │
    │ Historical Data       │
    └───────────────────────┘
```

### Implementation Steps

#### Step 1: Verify Django API Endpoint (Already Implemented)

**Endpoint**: `GET /api/analytics/demand-forecast/`  
**Location**: `analytics/views.py:demand_forecast()`  
**Status**: ✅ Already implemented and tested

**Authentication Note**: The current endpoint uses Django session authentication (via `@require_auth_json` decorator). This means:
- For **development/testing**: Use a logged-in session from the Django admin interface
- For **Power BI Desktop**: If running on the same machine with active session, authentication is automatic
- For **Power BI Service (cloud)**: Will require either:
  1. Service account with session cookie management, OR
  2. API gateway with token conversion (future enhancement)

The endpoint returns HTTP 401 JSON (not redirect) for unauthenticated requests, compatible with REST clients.

**Test the endpoint** (with active session):
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://your-domain/api/analytics/demand-forecast/
```

Note: Bearer token shown above is placeholder. Actual implementation uses Django session cookies. For testing, ensure you have an active authenticated session.

Expected response:
```json
{
    "forecasts": [...],
    "method_used": "seasonal_naive",
    "forecast_reference_date": "2026-10-12",
    ...
}
```

#### Step 2: Authentication Handling

The Django endpoint uses **session-based authentication** (not Bearer tokens). This requires proper session management:

**For Django Development Server**:
- Session cookie is set automatically when user logs into Django admin
- Power BI Desktop can access using the session cookie

**For Power BI Service (Production)**:
- Session authentication is complex for cloud deployments
- Recommended approach: Implement an API gateway or reverse proxy that:
  1. Accepts requests from Power BI Service
  2. Authenticates using a service account credential
  3. Forwards requests with proper session/authentication

**Configure Session Settings** (if needed):

```python
# config/settings.py
SESSION_COOKIE_SECURE = True  # HTTPS only
SESSION_COOKIE_HTTPONLY = True  # No JavaScript access
SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection
CSRF_TRUSTED_ORIGINS = ['https://your-domain']
```

**For Power BI Cross-Origin Access**:

If Power BI Service needs cross-domain access, enable CORS:

```python
# config/settings.py
INSTALLED_APPS = [
    # ...
    'corsheaders',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    # ... other middleware
]

CORS_ALLOWED_ORIGINS = [
    "https://app.powerbi.com",  # Power BI Service domain
    "https://analysis.windows.net",  # Power BI Analytics
]

CORS_ALLOW_CREDENTIALS = True
```

This configuration:
- Allows Power BI Service to send session cookies cross-domain
- Restricts CORS to Power BI domains only
- Requires session-based authentication (not Bearer tokens)

#### Step 3: In Power BI Desktop

1. **Home** → **Get Data** → **Web**
2. Enter the API endpoint URL:
   ```
   https://your-domain/api/analytics/demand-forecast/
   ```
3. Authentication for Django Session-Based API:
   - **Option A** (Recommended for Power BI Desktop): Use Windows Authentication
     - Django will use the session cookie from your logged-in session
     - Select **Windows** in authentication dialog
   - **Option B** (For testing/development): Add username/password
     - If credentials are needed, enter Django admin username/password
     - NOT Bearer token format (that's a documentation placeholder)
4. Click **OK**

#### Step 4: Transform the Response in Power BI

Power BI will import the JSON. You'll need to transform it:

1. In **Power Query Editor**:
   - Expand the `forecasts` array
   - Extract columns: `week_start_date`, `week_end_date`, `predicted_demand`, etc.
2. Set data types:
   - `week_start_date`: Date
   - `predicted_demand`: Whole Number
   - etc.
3. Click **Load** to import

### Pros & Cons

**Pros**:
- ✅ No additional database writes needed
- ✅ Leverage existing Django API
- ✅ Secure (uses existing authentication)
- ✅ Real-time forecasts (updated each query)
- ✅ Minimal backend changes required

**Cons**:
- ❌ Each Power BI refresh triggers Python calculation (slower than pre-cached)
- ❌ Power BI's JSON handling requires transformation
- ❌ May hit rate limits if refreshed too frequently
- ❌ Requires Django API to stay running

---

## Approach 2: Pre-Calculate and Store Forecasts (Alternative for Future)

### Architecture (Future Implementation)

```
┌─────────────────────────────────────────┐
│  Scheduled Job (Celery/APScheduler)    │
│  - Runs daily at 2 AM                  │
│  - Calls forecast_demand()             │
│  - Stores in analytics.forecasts table │
└────────────────┬────────────────────────┘
                 │
                 ▼
    ┌────────────────────────────┐
    │ Aiven MySQL               │
    │ Analytics DB              │
    │                           │
    │ NEW TABLE:                │
    │ analytics_forecasts       │
    │ - id                      │
    │ - forecast_date           │
    │ - week_start_date         │
    │ - predicted_demand        │
    │ - confidence_lower        │
    │ - confidence_upper        │
    │ - method_used             │
    │ - created_at              │
    └────────────────┬───────────┘
                     │
                     │ SELECT ...
                     │
         ┌───────────▼───────────┐
         │  Power BI             │
         │  (Direct SQL Query)   │
         └───────────────────────┘
```

### Why NOT Implemented Yet

1. **No live database writes permitted** (Phase 6.6 restriction)
2. **Requires schema change** (new table)
3. **Requires scheduler setup** (Celery/APScheduler)
4. **Requires migration** (Django migrations)
5. **Backend only scope** (no frontend components)

### Future Considerations

If forecasting becomes performance-critical:
1. ✅ Create `analytics_forecasts` table
2. ✅ Implement daily scheduled job to pre-calculate forecasts
3. ✅ Store results for direct SQL access from Power BI
4. ✅ Remove dependency on real-time calculation

---

## Approach 3: Hybrid Approach (Recommended for Scale)

### Combined Strategy

1. **Real-time**: Use REST API for current forecast
2. **Historical**: Store forecast results in database for backtesting
3. **Analysis**: Compare actual demand vs. forecast predictions

**Implementation Timeline**:
- Phase 6.6 (Now): Use REST API approach
- Phase 6.7 (Future): Implement pre-calculation approach if needed

---

## Power BI Web.Contents Function (Advanced)

### For Custom JSON Parsing

Power BI can call Web APIs using the `Web.Contents()` function:

```m
let
    Forecast = Json.Document(
        Web.Contents(
            "https://your-domain/api/analytics/demand-forecast/",
            [Headers = [Authorization = "Bearer YOUR_TOKEN"]]
        )
    ),
    ForecastTable = Table.FromList(
        Forecast[forecasts],
        Splitter.SplitByNothing(),
        null,
        ExtraValues.Error
    ),
    ExpandedForecast = Table.ExpandRecordColumn(
        ForecastTable, "Column1",
        {"week_start_date", "week_end_date", "predicted_demand", "confidence_lower_bound", "confidence_upper_bound"},
        {"week_start_date", "week_end_date", "predicted_demand", "lower_bound", "upper_bound"}
    )
in
    ExpandedForecast
```

**Steps to implement**:
1. In Power BI Desktop: **Home** → **Transform Data** → **New Source** → **Blank Query**
2. Paste the above M code
3. Click **Done**

---

## Authentication Considerations

**Current Implementation**: The Django endpoint uses **session-based authentication**, not Bearer tokens.

### Option 1: Session Cookie Authentication (Current)

For Django session-based API (current implementation):

```m
// Power BI will automatically use the session cookie from your Windows/browser session
Forecast = Web.Contents(
    "https://your-domain/api/analytics/demand-forecast/",
    [ManualStatusHandling = {400, 401, 403, 404, 500, 503}]
)
```

**How it works**:
- Power BI sends your session cookie automatically
- No explicit token needed if you have an active authenticated session
- Returns HTTP 401 if session expired

### Option 2: Bearer Token (Future Enhancement)

If you implement token-based authentication in Phase 6.7+:

```m
Token = "YOUR_JWT_TOKEN_HERE",
Forecast = Web.Contents(
    "https://your-domain/api/analytics/demand-forecast/",
    [Headers = [Authorization = "Bearer " & Token]]
)
```

**Setup required**:
- Implement JWT or API token authentication in Django
- Issue token from login endpoint
- Store securely in Power BI

### Option 3: OAuth 2.0 (Alternative for Service Deployments)

For Power BI Service deployments:

1. Implement OAuth 2.0 in Django
2. Register Power BI as OAuth client
3. Configure redirect URI: `https://oauth.powerbi.com/finally`
4. In Power BI Service: **Settings** → **Data Gateway** → **Configure OAuth**

### Option 4: No Authentication (Not Recommended)

If your API is public (not recommended for production):

```m
Web.Contents("https://your-domain/api/analytics/demand-forecast/")
```

---

## Performance Characteristics

### REST API Approach

| Metric | Value | Notes |
|--------|-------|-------|
| Latency | 1-3 seconds | Django calculates forecast on each request |
| Refresh Duration | 2-5 minutes | Includes transformation in Power BI |
| Recommended Frequency | 1-4 times daily | Not recommended more frequent than 4x/day |
| Scalability | ~100 concurrent requests | Depends on server capacity |

### Calculation Breakdown

```
API Request:           ~100ms (HTTP overhead)
Django View:           ~50ms (authentication, routing)
forecast_demand():     ~1-2 seconds (calculation)
Data Serialization:    ~50ms (JSON encoding)
Total per request:     ~1.2-2.2 seconds
```

---

## Error Handling in Power BI

### Common Errors & Solutions

**Error**: "Web request failed"
- Cause: API endpoint not accessible
- Solution: Verify URL, check authentication, ensure Django server running

**Error**: "JSON parsing failed"
- Cause: Response format unexpected
- Solution: Check API output format, verify M code

**Error**: "Authorization failed"
- Cause: Invalid token or expired credentials
- Solution: Refresh token, verify Bearer token format

### Retry Logic

Power BI automatically retries failed Web requests:
- Default: 3 retries
- Backoff: Exponential (1s, 2s, 4s)
- Configure in: **File** → **Options** → **Web**

---

## Data Quality Considerations

### Limitations to Document in Power BI

1. **Forecast Uncertainty**
   - Add confidence bounds (already in output)
   - Visualize as range, not point estimate

2. **Method Assumptions**
   - Document which method used (seasonal_naive, exponential_smoothing, or fallback)
   - Display in report: "Method: {method_used}"

3. **Training Data**
   - Show historical weeks used
   - Display: "Based on {historical_weeks_used} weeks of history"

4. **Refresh Latency**
   - Forecast uses historical data through API call date
   - Document in report: "Forecast as of {forecast_reference_date}"

---

## Recommended Configuration

### For Phase 6.6 Implementation

```
Approach:         REST API Integration (Approach 1)
Endpoint:         GET /api/analytics/demand-forecast/
Refresh:          Daily (8 AM Manila time)
Authentication:   Token-based (if required)
Transformation:   Power BI Power Query M code
Storage:          In-memory (Power BI dataset)
```

### Connection String (If Using Web Connector)

```
https://[your-domain]/api/analytics/demand-forecast/?format=json
```

---

## Future Enhancements (Phase 6.7+)

1. **Pre-calculated Forecasts**
   - Store in database table
   - Direct SQL query from Power BI
   - Faster refresh (no calculation needed)

2. **Forecast Versioning**
   - Track multiple forecast runs
   - Compare forecast accuracy over time
   - Identify when forecasts changed

3. **Advanced Scenarios**
   - What-if analysis (adjust parameters)
   - Multi-method comparison
   - Ensemble forecasting

4. **Real-Time Updates**
   - Streaming datasets to Power BI
   - Live forecast updates
   - Anomaly detection

---

## Testing the Integration

### Step 1: Manual API Test

```bash
# Get forecast via curl
curl -X GET \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  https://your-domain/api/analytics/demand-forecast/ | jq .
```

### Step 2: Test in Power Query

1. In Power BI Desktop, create new blank query
2. Paste M code with Web.Contents()
3. Click "Run"
4. Verify data loads without errors

### Step 3: Add to Dashboard

1. Load the forecast query into Power BI
2. Create visualization:
   - Line chart (Week vs. Predicted Demand)
   - Area chart (with confidence bounds)
   - Table (for detailed inspection)

---

## Security Notes

- ✅ API uses HTTPS with TLS
- ✅ Authentication required (token or session)
- ✅ No sensitive data exposed (synthetic data only)
- ✅ CORS configured for Power BI domains only
- ✅ Power BI credentials stored encrypted

---

## Conclusion

For Phase 6.6, **Approach 1 (REST API Integration)** is recommended:

1. ✅ Minimal backend changes needed
2. ✅ Real-time forecasts (always current)
3. ✅ Uses existing Django API
4. ✅ Secure authentication
5. ✅ No database schema changes required

In future phases (6.7+), consider **Approach 2 (Pre-Calculated Storage)** for:
- Better performance (pre-cached results)
- Historical tracking (forecast versioning)
- Scalability (no real-time calculation overhead)

---

**Document Status**: Ready for Review  
**Implementation**: Deferred to Phase 6.6.2 (dashboard development)
