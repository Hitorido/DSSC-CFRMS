# Phase 6.6: Power BI Connection Setup Guide

**Status**: Backend Integration Setup (No Deployment)  
**Date**: October 12, 2026  
**Scope**: Instructions for connecting Power BI to Aiven Cloud MySQL

---

## Overview

This guide provides step-by-step instructions for configuring Power BI to connect to the Aiven Cloud MySQL analytics database with TLS encryption.

**Prerequisites**:
- Power BI Desktop (Windows) or Power BI Service (Cloud)
- Aiven MySQL analytics database configured and accessible
- TLS CA certificate downloaded from Aiven
- Aiven database credentials (read-only user account recommended)

---

## Step 1: Obtain Aiven Connection Details

### From Aiven Console

1. Log in to [Aiven Console](https://console.aiven.io)
2. Navigate to: **Services** → **MySQL** → **Connection Information**
3. Note the following:
   - **Hostname**: e.g., `mysql-xxxxxxx.aivencloud.com`
   - **Port**: Usually `3306`
   - **Database Name**: `dssc_analytics` (configured in .env ANALYTICS_DB_NAME)
   - **Username**: Aiven MySQL user (recommend read-only account)
   - **Password**: User password

### Download TLS CA Certificate

1. In Aiven Console, go to **Services** → **MySQL** → **CA Certificate**
2. Click **Download** to save the certificate file
   - Typically named: `ca.pem` or `ca-certificate.pem`
   - Format: PEM (text file with BEGIN/END CERTIFICATE markers)
3. Save to a secure location on your computer
   - Example: `C:\ProgramData\Power BI\aiven-ca.pem`
   - **Do NOT commit to version control or share credentials**

---

## Step 2: Create Read-Only Database User (Recommended)

### Via Aiven Console (Admin Only)

1. In Aiven Console, go to **Services** → **MySQL** → **Users**
2. Click **Create user**
3. Enter credentials:
   - **Username**: `powerbi_readonly` (or your naming convention)
   - **Password**: Generate strong random password
4. Click **Create**

### Grant Read-Only Permissions (MySQL CLI)

```sql
-- Connect as admin user first
GRANT SELECT ON dssc_analytics.* TO 'powerbi_readonly'@'%';
FLUSH PRIVILEGES;
```

**Permissions**:
- `SELECT` only (read-only queries)
- Scoped to `dssc_analytics.*` (analytics tables only)
- `'%'` allows connection from any IP (Power BI IPs vary)

### Alternative: Use Existing User (Not Recommended)

If a read-only user is not available, use an existing account with sufficient permissions. Ensure:
- User has `SELECT` privilege on `dssc_analytics`
- User does NOT have `CREATE`, `DROP`, `ALTER`, `DELETE`, or `UPDATE` privileges

---

## Step 3: Configure Power BI Desktop Connection

### Method 1: Direct SQL Server Connection

1. Open **Power BI Desktop**
2. Go to **Home** → **Get Data** → **More**
3. Search for and select **MySQL Database**
   - If not available: **File** → **Options** → **Data Extensions** → Enable MySQL
4. Configure connection:
   - **Server**: `mysql-xxxxxxx.aivencloud.com`
   - **Database**: `dssc_analytics` (from .env ANALYTICS_DB_NAME)
   - Click **OK**
5. Authentication dialog:
   - **Authentication kind**: `Database`
   - **Username**: `powerbi_readonly` (or your account)
   - **Password**: Password (encrypted in Power BI)
   - Click **Connect**

### Method 2: Using Connection String (Advanced)

If direct method fails, use connection string:

```
server=mysql-xxxxxxx.aivencloud.com;database=dssc_analytics;uid=powerbi_readonly;pwd=YOUR_PASSWORD;SslMode=Required
```

**Steps**:
1. **Home** → **Get Data** → **More**
2. Select **MySQL Database**
3. In **Connection String** field, paste the above string
4. Check **Use My Own Credentials**
5. Click **OK**

---

## Step 4: Configure TLS/SSL Certificate (Critical for Cloud)

### Configure in Power BI Desktop

**For Windows 10+**:

1. After connection step 3, you may see SSL/TLS errors
2. Go to **File** → **Options and Settings** → **Options**
3. Navigate to **Security** → **Data Privacy**
4. Under **Certificate Pinning**:
   - If available, add the Aiven CA certificate
   - Path: `C:\ProgramData\Power BI\aiven-ca.pem`

### Alternative: Trust Certificate Globally (Windows)

1. Open **Certificate Manager** (certmgr.msc)
2. Navigate to **Trusted Root Certification Authorities** → **Certificates**
3. Right-click → **All Tasks** → **Import**
4. Select the Aiven CA certificate file
5. Click through wizard to complete import

### For Power BI Service (Cloud)

TLS certificates are typically handled by:
1. **Power BI Service** → **Settings** → **Data Source Settings**
2. For Aiven MySQL connection, upload the CA certificate:
   - **Upload Certificate** → Select `aiven-ca.pem`
3. Complete connection configuration

---

## Step 5: Test Connection

### In Power BI Desktop

1. After configuring connection, click **OK** to proceed
2. Power BI will attempt to connect to the database
3. If successful, you'll see the navigator showing tables:
   - `accounts_user`
   - `facilities_facility`
   - `facilities_facilitytype`
   - `reservations_reservation`
4. If connection fails:
   - Check error message (usually includes certificate or authentication details)
   - Verify hostname, port, credentials
   - Ensure Aiven CA certificate is properly configured
   - Test with MySQL CLI client from your machine (if available)

### MySQL CLI Test (Optional)

From your local terminal:

```bash
mysql --host=mysql-xxxxxxx.aivencloud.com \
      --port=3306 \
      --user=powerbi_readonly \
      --password \
      --ssl-ca=/path/to/aiven-ca.pem \
      dssc_analytics -e "SELECT COUNT(*) FROM reservations_reservation WHERE is_synthetic=TRUE;"
```

Expected output: ~5000 (number of synthetic reservations)

---

## Step 6: Import Data into Power BI

### Option A: Import Tables Directly

1. In Power BI Navigator:
   - Select `reservations_reservation` (base fact table)
   - Select `facilities_facility`
   - Select `facilities_facilitytype`
   - Select `accounts_user`
   - Click **Load**

2. Power BI will import the selected tables
3. This creates a local copy in Power BI (snapshot)
4. Configure refresh schedule in Power BI Service if needed

### Option B: Use Custom SQL Queries

For pre-aggregated views:

1. In Power BI Navigator, click **New Source**
2. Select **SQL Query Editor** or **Advanced Options**
3. Paste SQL from `PHASE_6_6_SQL_QUERIES.sql`
   - Use Query 5 for Status Distribution
   - Use Query 7 for Facility Demand
   - Use Query 11 for Booking Intensity
   - Use Query 12 for KPIs
4. Click **OK** to execute and load results

### Option C: Mixed Approach (Recommended)

1. Import base tables directly:
   - `reservations_reservation` (Query 1 - base facts)
   - `facilities_facility` (Query 2 - dimensions)
   - `facilities_facilitytype` (Query 3 - dimensions)
   - `accounts_user` (Query 4 - dimensions)

2. Use Power BI DAX to calculate:
   - Status Distribution
   - Monthly Trends
   - Facility Demand
   - KPIs (built-in measures)

This approach balances freshness (base tables) with performance (calculations done locally).

---

## Step 7: Configure Refresh Schedule

### In Power BI Desktop (Local Development)

1. **Home** → **Refresh** (manual refresh)
   - Or use scheduled refresh when published to Service

### In Power BI Service (Production)

1. Published report in Power BI Service
2. **Settings** → **Datasets**
3. Select your dataset
4. Click **Scheduled Refresh**
5. Configure schedule:
   - **Frequency**: Daily, Multiple times per day, etc.
   - **Time**: Choose off-peak hours
   - **Frequency**: 1-8 times per day (depending on license)
6. Power BI will automatically refresh at scheduled times

**Recommended Schedule**:
- Base tables (reservations, facilities): Every 4 hours
- Dimension tables (users, facility types): Daily (overnight)
- Summary queries: Recalculate in DAX (no separate refresh needed)

---

## Troubleshooting Connection Issues

### Error: "Unable to connect to server"

**Causes & Solutions**:
1. **Hostname incorrect**
   - Verify from Aiven console: `mysql-xxxxxxx.aivencloud.com`
   - Check for typos

2. **Port not accessible**
   - Verify Aiven port: Usually `3306`
   - Check if firewall is blocking outbound port 3306
   - Contact network admin if on corporate network

3. **Database name incorrect**
   - Verify database name: `dssc_analytics_db` (or your name)
   - SQL is case-sensitive

### Error: "SSL/TLS certificate error" or "CERTIFICATE_VERIFY_FAILED"

**Causes & Solutions**:
1. **CA certificate not configured**
   - Ensure Aiven CA certificate (`aiven-ca.pem`) is imported
   - For Power BI Desktop: Import globally in Windows Certificate Manager
   - For Power BI Service: Upload certificate in connection settings

2. **Certificate path incorrect**
   - Verify file exists: `C:\ProgramData\Power BI\aiven-ca.pem`
   - Use full absolute path (no relative paths)

3. **Certificate format incorrect**
   - Verify file contains:
     ```
     -----BEGIN CERTIFICATE-----
     [base64 content]
     -----END CERTIFICATE-----
     ```
   - File should be plain text PEM format

### Error: "Authentication failed" or "Access denied"

**Causes & Solutions**:
1. **Credentials incorrect**
   - Verify username and password are correct
   - Test credentials with MySQL CLI

2. **User permissions insufficient**
   - Ensure user has `SELECT` permission on `dssc_analytics_db`
   - Run: `GRANT SELECT ON dssc_analytics_db.* TO 'user'@'%';`

3. **IP not whitelisted (if applicable)**
   - Some Aiven plans restrict connection IPs
   - Check Aiven console for IP allowlist
   - Add Power BI IP if needed (obtain from network admin)

### Error: "Timeout" or "Connection lost"

**Causes & Solutions**:
1. **Aiven service down or unavailable**
   - Check Aiven Status page
   - Verify in Aiven console that MySQL service is "Running"

2. **Slow network connection**
   - Test with: `ping mysql-xxxxxxx.aivencloud.com`
   - Expected: <200ms latency

3. **Power BI memory exceeded**
   - For large datasets (>100MB), Power BI may timeout
   - Solution: Import pre-aggregated summaries instead of full tables

---

## Security Best Practices

### 1. Credential Management

- ✅ Store credentials in Power BI (encrypted internally)
- ❌ Do NOT store credentials in shared documents or emails
- ❌ Do NOT commit credentials to version control
- ✅ Use environment variables for development

### 2. TLS/SSL Encryption

- ✅ Always use TLS for cloud connections
- ✅ Verify certificate path and validity
- ✅ Renew certificates before expiration (Aiven handles auto-renewal)
- ❌ Never accept self-signed certificates without verification

### 3. Database User Permissions

- ✅ Use dedicated read-only user for Power BI
- ✅ Grant minimum permissions (`SELECT` only)
- ✅ Limit scope to analytics database (`dssc_analytics_db.*`)
- ❌ Never use admin credentials for Power BI
- ❌ Never grant write/delete permissions to analytics users

### 4. Network Security

- ✅ Use Aiven IP allowlist if available
- ✅ Connect from secure network (VPN for remote users)
- ✅ Monitor connection logs in Aiven console
- ❌ Do NOT allow anonymous connections from unknown IPs

---

## Data Type Handling in Power BI

### MySQL → Power BI Type Mapping

| MySQL Type | Power BI Type | Format | Notes |
|------------|---------------|--------|-------|
| INT | Whole Number | Default | No decimal |
| VARCHAR | Text | Default | Variable length string |
| DATETIME | Date/Time | YYYY-MM-DD HH:MM:SS | Set timezone in Power BI |
| DATE | Date | YYYY-MM-DD | Date only, no time |
| TIME | Text | HH:MM:SS | No native TIME type in Power BI |
| BOOLEAN/TINYINT(1) | Whole Number | 0 or 1 | Convert to true/false with DAX |
| DECIMAL | Decimal Number | Depends | Use for monetary values |

### Special Configuration

**For DATETIME fields**:
1. After importing, right-click column
2. Select **Data Type**: **Date/Time**
3. Format: **Long Date-Time** (shows timezone)
4. In Power BI Service, set timezone to **"(UTC+08:00) Manila, Singapore"**

**For TIME fields** (start_time, end_time):
1. Import as Text
2. Create calculated column:
   ```dax
   Time_Formatted = TIMEVALUE([start_time])
   ```
3. Use formatted column in visualizations

---

## Performance Optimization

### 1. Query Optimization

- Use pre-aggregated queries for summary views
- Filter `WHERE is_synthetic=TRUE` in all queries (indexes exist)
- Avoid full table scans; use filters on indexed columns
- Load summarized data rather than raw 5,000 rows if possible

### 2. Power BI Model Optimization

- Import dimension tables (small, static data)
- Use DirectQuery only if real-time is critical
- Create relationships between tables for efficient calculations
- Use aggregation tables for pre-calculated metrics

### 3. Refresh Strategy

- Schedule refreshes off-peak (avoid 9-5 business hours)
- Use incremental refresh if available (Power BI Premium)
- Combine multiple queries into single refresh job
- Monitor refresh duration and adjust schedule if needed

---

## Connection String Reference

### For MySQL Connector

```
server=HOSTNAME;database=DATABASE;uid=USERNAME;pwd=PASSWORD;
```

### With TLS/SSL

```
server=HOSTNAME;database=DATABASE;uid=USERNAME;pwd=PASSWORD;SslMode=Required;CertificatePath=/path/to/ca.pem
```

### Complete Example

```
server=mysql-xxxxxxx.aivencloud.com;database=dssc_analytics;uid=powerbi_readonly;pwd=yourpassword;SslMode=Required
```

---

## FAQ

**Q: Can I connect Power BI Service directly to Aiven without Power BI Desktop?**
A: Yes, in Power BI Service, use **Get Data** → **MySQL Database** and follow the same steps. You'll need to upload the CA certificate in the connection settings.

**Q: What if my Power BI license doesn't allow scheduled refresh?**
A: Refresh manually or upgrade to Power BI Pro/Premium. Alternatively, export data to Excel and upload to Power BI.

**Q: Can I use Power BI Desktop's built-in security options instead of TLS?**
A: No, TLS is required for cloud connections like Aiven. Power BI Desktop security options do not replace proper database-level encryption.

**Q: How often should I refresh the data?**
A: Depends on freshness requirements:
- Real-time analytics: Every 15-30 minutes
- Daily reports: Once per day (overnight)
- Ad-hoc analysis: Manual refresh as needed

**Q: Can I share this Power BI report with non-technical users?**
A: Yes, once published to Power BI Service. End users see only the dashboards/reports, not the data connection details.

---

## Next Steps

1. ✅ Obtain Aiven connection details and CA certificate
2. ✅ Create read-only database user (optional but recommended)
3. ✅ Configure Power BI Desktop connection
4. ✅ Import base tables and configure relationships
5. ⏳ (Phase 6.6.3) Build dashboards in Power BI Desktop
6. ⏳ (Phase 6.6.4) Publish to Power BI Service
7. ⏳ (Phase 6.6.5) Configure refresh schedule

---

**Document Status**: Ready for Review  
**Backend Configuration**: Complete (No deployment yet)
