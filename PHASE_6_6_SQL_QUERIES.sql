-- ============================================================================
-- PHASE 6.6: POWER BI BACKEND - READ-ONLY SQL QUERIES
-- ============================================================================
-- 
-- Database: Aiven Cloud MySQL (Analytics DB)
-- Purpose: Provide read-only SQL queries for Power BI dashboards
-- 
-- These queries are designed to be:
-- - READ-ONLY (SELECT only, no modifications)
-- - Efficient (optimized for analytics workloads)
-- - Compatible with Power BI data import
-- - Filtered to SYNTHETIC data only (analytics dataset)
--
-- ============================================================================

-- ============================================================================
-- QUERY 1: Base Reservations Data (for Power BI import)
-- ============================================================================
-- 
-- Purpose: Base fact table of all reservations
-- Usage: Import directly into Power BI as main data source
-- Row Count: ~5,000 (synthetic reservations)
--
-- Columns:
--   - id: Unique reservation ID
--   - facility_id: Which facility (FK to facilities_facility)
--   - requested_by_id: User who requested (FK to accounts_user)
--   - reservation_date: Booking date
--   - start_time: Booking window start
--   - end_time: Booking window end
--   - status: PENDING/APPROVED/REJECTED/CANCELLED
--   - reviewed_by_id: Staff who approved/rejected (FK to accounts_user)
--   - reviewed_at: When action taken
--   - is_synthetic: Always TRUE for this dataset
--   - created_at: Request submission timestamp
--   - updated_at: Last modification timestamp

SELECT 
    `id`,
    `requested_by_id`,
    `facility_id`,
    `purpose`,
    `reservation_date`,
    `start_time`,
    `end_time`,
    `status`,
    `reviewed_by_id`,
    `reviewed_at`,
    `rejection_reason`,
    `is_synthetic`,
    `created_at`,
    `updated_at`
FROM `reservations_reservation`
WHERE `is_synthetic` = TRUE
ORDER BY `created_at` DESC;

-- ============================================================================
-- QUERY 2: Facility Master Data
-- ============================================================================
--
-- Purpose: Facility dimension for lookups and analysis
-- Usage: Join with reservations for facility-level analysis
-- Row Count: ~20-50 (facilities)

SELECT 
    `id`,
    `facility_type_id`,
    `name`,
    `location`,
    `capacity`,
    `description`,
    `status`,
    `is_synthetic`,
    `created_at`,
    `updated_at`
FROM `facilities_facility`
WHERE `is_synthetic` = TRUE
ORDER BY `name`;

-- ============================================================================
-- QUERY 3: Facility Types Dimension
-- ============================================================================
--
-- Purpose: Facility category reference
-- Usage: Lookup table for facility type names

SELECT 
    `id`,
    `name`,
    `description`,
    `is_synthetic`,
    `created_at`,
    `updated_at`
FROM `facilities_facilitytype`
WHERE `is_synthetic` = TRUE
ORDER BY `name`;

-- ============================================================================
-- QUERY 4: User Dimension (Requesters & Reviewers)
-- ============================================================================
--
-- Purpose: User reference for filtering and analysis
-- Usage: Join for request analysis and reviewer tracking

SELECT 
    `id`,
    `username`,
    `email`,
    `role`,
    `is_synthetic`,
    `created_at`
FROM `accounts_user`
WHERE `is_synthetic` = TRUE
ORDER BY `username`;

-- ============================================================================
-- QUERY 5: Reservation Status Distribution (Monthly Summary)
-- ============================================================================
--
-- Purpose: Summary of reservation statuses by month
-- Output: One row per month with status counts
-- 
-- Columns:
--   - year_month: YYYY-MM format
--   - total_reservations: Total reservations that month
--   - approved_count: Approved reservations
--   - rejected_count: Rejected reservations
--   - cancelled_count: Cancelled reservations
--   - pending_count: Pending reservations

SELECT 
    DATE_FORMAT(`created_at`, '%Y-%m') AS `year_month`,
    COUNT(*) AS `total_reservations`,
    COUNT(CASE WHEN `status` = 'APPROVED' THEN 1 END) AS `approved_count`,
    COUNT(CASE WHEN `status` = 'REJECTED' THEN 1 END) AS `rejected_count`,
    COUNT(CASE WHEN `status` = 'CANCELLED' THEN 1 END) AS `cancelled_count`,
    COUNT(CASE WHEN `status` = 'PENDING' THEN 1 END) AS `pending_count`
FROM `reservations_reservation`
WHERE `is_synthetic` = TRUE
GROUP BY DATE_FORMAT(`created_at`, '%Y-%m')
ORDER BY `year_month` DESC;

-- ============================================================================
-- QUERY 6: Monthly Reservation Trends (Detailed)
-- ============================================================================
--
-- Purpose: Monthly trends with additional metrics
-- Output: One row per month
--
-- Columns:
--   - year_month: YYYY-MM format
--   - total: Total reservations
--   - approved: Approved count
--   - rejected: Rejected count
--   - cancelled: Cancelled count
--   - avg_days_to_approval: Average days from request to approval (approved only)

SELECT 
    DATE_FORMAT(`created_at`, '%Y-%m') AS `year_month`,
    COUNT(*) AS `total`,
    COUNT(CASE WHEN `status` = 'APPROVED' THEN 1 END) AS `approved`,
    COUNT(CASE WHEN `status` = 'REJECTED' THEN 1 END) AS `rejected`,
    COUNT(CASE WHEN `status` = 'CANCELLED' THEN 1 END) AS `cancelled`,
    ROUND(
        AVG(
            CASE 
                WHEN `status` = 'APPROVED' AND `reviewed_at` IS NOT NULL
                THEN DATEDIFF(`reviewed_at`, `created_at`)
                ELSE NULL
            END
        ), 
        2
    ) AS `avg_days_to_approval`
FROM `reservations_reservation`
WHERE `is_synthetic` = TRUE
GROUP BY DATE_FORMAT(`created_at`, '%Y-%m')
ORDER BY `year_month` DESC;

-- ============================================================================
-- QUERY 7: Facility Demand (Ranked by Reservation Count)
-- ============================================================================
--
-- Purpose: Demand analysis by facility
-- Output: One row per facility with reservation statistics
--
-- Columns:
--   - facility_id: Facility ID
--   - facility_name: Facility name
--   - facility_type: Facility type name
--   - capacity: Facility capacity
--   - reservation_count: Total reservations at this facility
--   - approved_count: Approved reservations
--   - rejected_count: Rejected reservations
--   - cancelled_count: Cancelled reservations

SELECT 
    `f`.`id` AS `facility_id`,
    `f`.`name` AS `facility_name`,
    `ft`.`name` AS `facility_type`,
    `f`.`capacity`,
    COUNT(`r`.`id`) AS `reservation_count`,
    COUNT(CASE WHEN `r`.`status` = 'APPROVED' THEN 1 END) AS `approved_count`,
    COUNT(CASE WHEN `r`.`status` = 'REJECTED' THEN 1 END) AS `rejected_count`,
    COUNT(CASE WHEN `r`.`status` = 'CANCELLED' THEN 1 END) AS `cancelled_count`
FROM `facilities_facility` `f`
LEFT JOIN `facilities_facilitytype` `ft` ON `f`.`facility_type_id` = `ft`.`id`
LEFT JOIN `reservations_reservation` `r` ON `f`.`id` = `r`.`facility_id` AND `r`.`is_synthetic` = TRUE
WHERE `f`.`is_synthetic` = TRUE
GROUP BY `f`.`id`, `f`.`name`, `ft`.`name`, `f`.`capacity`
ORDER BY `reservation_count` DESC;

-- ============================================================================
-- QUERY 8: Peak Booking Periods (Hourly Distribution)
-- ============================================================================
--
-- Purpose: Identify peak booking times by hour of day
-- Output: Hour breakdown of booking volume
--
-- Note: TIME columns are extracted as HOUR values
-- Columns:
--   - hour: 0-23 (hour of day)
--   - booking_count: Number of reservations starting in that hour

SELECT 
    HOUR(`start_time`) AS `hour`,
    COUNT(*) AS `booking_count`
FROM `reservations_reservation`
WHERE `is_synthetic` = TRUE
GROUP BY HOUR(`start_time`)
ORDER BY `hour` ASC;

-- ============================================================================
-- QUERY 9: Peak Booking Periods (Day of Week Distribution)
-- ============================================================================
--
-- Purpose: Identify peak booking days of week
-- Output: Day breakdown of booking volume
--
-- Columns:
--   - day_of_week: 1=Monday, 2=Tuesday, ..., 7=Sunday (ISO week)
--   - day_name: Text name (Monday, Tuesday, etc.)
--   - booking_count: Number of reservations on that day

SELECT 
    DAYOFWEEK(`reservation_date`) - 1 AS `day_of_week_iso`,
    DAYNAME(`reservation_date`) AS `day_name`,
    COUNT(*) AS `booking_count`
FROM `reservations_reservation`
WHERE `is_synthetic` = TRUE
GROUP BY DAYNAME(`reservation_date`), DAYOFWEEK(`reservation_date`)
ORDER BY `day_of_week_iso` ASC;

-- ============================================================================
-- QUERY 10: Peak Booking Periods (Facility-Level)
-- ============================================================================
--
-- Purpose: Identify which facilities have most bookings
-- Output: Facility ranking by booking volume

SELECT 
    `f`.`id` AS `facility_id`,
    `f`.`name` AS `facility_name`,
    `ft`.`name` AS `facility_type`,
    COUNT(`r`.`id`) AS `booking_count`
FROM `facilities_facility` `f`
LEFT JOIN `facilities_facilitytype` `ft` ON `f`.`facility_type_id` = `ft`.`id`
LEFT JOIN `reservations_reservation` `r` ON `f`.`id` = `r`.`facility_id` AND `r`.`is_synthetic` = TRUE
WHERE `f`.`is_synthetic` = TRUE
GROUP BY `f`.`id`, `f`.`name`, `ft`.`name`
ORDER BY `booking_count` DESC;

-- ============================================================================
-- QUERY 11: Facility Booking Intensity (KPI Metric)
-- ============================================================================
--
-- Purpose: Calculate booking intensity (approved reservations / capacity)
-- Output: Intensity metric ranked by score (highest first)
--
-- Interpretation:
--   - <0.5: Low intensity (plenty of available capacity)
--   - 0.5-1.0: Moderate intensity (reasonable utilization)
--   - >1.0: High intensity (more bookings than capacity can cover in one slot)
--
-- Note: Intensity = approved_count / capacity
--       Higher intensity indicates high facility demand
--
-- Columns:
--   - facility_id: Facility ID
--   - facility_name: Facility name
--   - facility_type: Category
--   - capacity: Facility capacity
--   - approved_reservations: Count of approved bookings
--   - booking_intensity: Intensity score

SELECT 
    `f`.`id` AS `facility_id`,
    `f`.`name` AS `facility_name`,
    `ft`.`name` AS `facility_type`,
    `f`.`capacity`,
    COUNT(CASE WHEN `r`.`status` = 'APPROVED' THEN 1 END) AS `approved_reservations`,
    ROUND(
        COUNT(CASE WHEN `r`.`status` = 'APPROVED' THEN 1 END) / `f`.`capacity`,
        4
    ) AS `booking_intensity`
FROM `facilities_facility` `f`
LEFT JOIN `facilities_facilitytype` `ft` ON `f`.`facility_type_id` = `ft`.`id`
LEFT JOIN `reservations_reservation` `r` ON `f`.`id` = `r`.`facility_id` AND `r`.`is_synthetic` = TRUE
WHERE `f`.`is_synthetic` = TRUE
GROUP BY `f`.`id`, `f`.`name`, `ft`.`name`, `f`.`capacity`
ORDER BY `booking_intensity` DESC;

-- ============================================================================
-- QUERY 12: Reservation KPIs (Aggregate Summary)
-- ============================================================================
--
-- Purpose: Overall reservation metrics (single row)
-- Output: One row with aggregate statistics
--
-- Columns:
--   - total_reservations: Total count (all statuses)
--   - approved_count: Approved reservations
--   - rejected_count: Rejected reservations
--   - cancelled_count: Cancelled reservations
--   - pending_count: Pending reservations
--   - approval_rate: approved / (approved + rejected + cancelled)
--   - rejection_rate: rejected / (approved + rejected + cancelled)
--   - cancellation_rate: cancelled / total
--   - avg_days_to_approval: Average days from request to approval

SELECT 
    COUNT(*) AS `total_reservations`,
    COUNT(CASE WHEN `status` = 'APPROVED' THEN 1 END) AS `approved_count`,
    COUNT(CASE WHEN `status` = 'REJECTED' THEN 1 END) AS `rejected_count`,
    COUNT(CASE WHEN `status` = 'CANCELLED' THEN 1 END) AS `cancelled_count`,
    COUNT(CASE WHEN `status` = 'PENDING' THEN 1 END) AS `pending_count`,
    ROUND(
        COUNT(CASE WHEN `status` = 'APPROVED' THEN 1 END) / 
        (COUNT(CASE WHEN `status` = 'APPROVED' THEN 1 END) +
         COUNT(CASE WHEN `status` = 'REJECTED' THEN 1 END) +
         COUNT(CASE WHEN `status` = 'CANCELLED' THEN 1 END)),
        4
    ) AS `approval_rate`,
    ROUND(
        COUNT(CASE WHEN `status` = 'REJECTED' THEN 1 END) / 
        (COUNT(CASE WHEN `status` = 'APPROVED' THEN 1 END) +
         COUNT(CASE WHEN `status` = 'REJECTED' THEN 1 END) +
         COUNT(CASE WHEN `status` = 'CANCELLED' THEN 1 END)),
        4
    ) AS `rejection_rate`,
    ROUND(
        COUNT(CASE WHEN `status` = 'CANCELLED' THEN 1 END) / COUNT(*),
        4
    ) AS `cancellation_rate`,
    ROUND(
        AVG(
            CASE 
                WHEN `status` = 'APPROVED' AND `reviewed_at` IS NOT NULL
                THEN DATEDIFF(`reviewed_at`, `created_at`)
                ELSE NULL
            END
        ), 
        2
    ) AS `avg_days_to_approval`
FROM `reservations_reservation`
WHERE `is_synthetic` = TRUE;

-- ============================================================================
-- QUERY 13: Historical Demand Data (for Forecast Comparison)
-- ============================================================================
--
-- Purpose: Weekly aggregated demand for comparison with forecasts
-- Output: One row per week with reservation count
--
-- Columns:
--   - week_start_date: Start of ISO week (Monday)
--   - week_end_date: End of ISO week (Sunday)
--   - reservation_count: Number of requests submitted that week

SELECT 
    DATE_SUB(`created_at`, INTERVAL DAYOFWEEK(`created_at`) - 2 DAY) AS `week_start_date`,
    DATE_ADD(
        DATE_SUB(`created_at`, INTERVAL DAYOFWEEK(`created_at`) - 2 DAY),
        INTERVAL 6 DAY
    ) AS `week_end_date`,
    COUNT(*) AS `reservation_count`
FROM `reservations_reservation`
WHERE `is_synthetic` = TRUE
GROUP BY DATE_SUB(`created_at`, INTERVAL DAYOFWEEK(`created_at`) - 2 DAY)
ORDER BY `week_start_date` DESC;

-- ============================================================================
-- QUERY 14: Reviewer Performance (Staff Metrics)
-- ============================================================================
--
-- Purpose: Track review actions by staff/admin
-- Output: Per-reviewer statistics
--
-- Columns:
--   - reviewer_id: User ID who reviewed
--   - reviewer_name: Username
--   - approved_count: Reservations approved
--   - rejected_count: Reservations rejected
--   - total_reviewed: Total actions taken

SELECT 
    `u`.`id` AS `reviewer_id`,
    `u`.`username` AS `reviewer_name`,
    COUNT(CASE WHEN `r`.`status` = 'APPROVED' THEN 1 END) AS `approved_count`,
    COUNT(CASE WHEN `r`.`status` = 'REJECTED' THEN 1 END) AS `rejected_count`,
    COUNT(*) AS `total_reviewed`
FROM `accounts_user` `u`
LEFT JOIN `reservations_reservation` `r` ON `u`.`id` = `r`.`reviewed_by_id` AND `r`.`is_synthetic` = TRUE
WHERE `u`.`is_synthetic` = TRUE AND `u`.`role` IN ('ADMIN', 'STAFF')
GROUP BY `u`.`id`, `u`.`username`
ORDER BY `total_reviewed` DESC;

-- ============================================================================
-- NOTES FOR POWER BI DEPLOYMENT
-- ============================================================================
--
-- 1. These queries are READ-ONLY (SELECT only)
-- 2. All queries filter WHERE is_synthetic = TRUE (analytics dataset)
-- 3. All queries can be imported directly into Power BI
-- 4. Use Query 1 (Base Reservations) as main fact table
-- 5. Use Queries 2, 3, 4 as dimension tables
-- 6. Use Queries 5-14 as pre-calculated summary tables (optional)
--
-- Performance Notes:
--   - Base Reservations: ~5,000 rows (no aggregation, fast)
--   - Summary queries: Aggregated (1-50 rows, very fast)
--   - Join queries: On-demand, may be slower for large datasets
--
-- Refresh Recommendation:
--   - Base tables: Every 15-30 minutes (real-time)
--   - Dimension tables: Daily
--   - Summary queries: Can be calculated in Power BI DAX
--
-- ============================================================================
