-- Fix: Add missing facility columns to production Aiven MySQL database
-- These columns are defined in migration 0004_add_facility_details.py
-- but were not applied to the cloud database.

-- BACKUP FIRST: This script modifies production data!
-- Run: mysqldump -h <host> -u <user> -p <database> > backup.sql

USE dssc_analytics;

-- Add equipment_list column
ALTER TABLE facilities_facility 
ADD COLUMN IF NOT EXISTS equipment_list LONGTEXT NOT NULL DEFAULT '';

-- Add hours_of_operation column  
ALTER TABLE facilities_facility 
ADD COLUMN IF NOT EXISTS hours_of_operation VARCHAR(200) NOT NULL DEFAULT '8am-6pm';

-- Add noise_level column with enum choices
ALTER TABLE facilities_facility 
ADD COLUMN IF NOT EXISTS noise_level VARCHAR(20) NOT NULL DEFAULT 'low';

-- Add floor_number column (nullable)
ALTER TABLE facilities_facility 
ADD COLUMN IF NOT EXISTS floor_number INT NULL;

-- Add building_code column
ALTER TABLE facilities_facility 
ADD COLUMN IF NOT EXISTS building_code VARCHAR(10) NOT NULL DEFAULT '';

-- Add has_wheelchair_access column
ALTER TABLE facilities_facility 
ADD COLUMN IF NOT EXISTS has_wheelchair_access BOOLEAN NOT NULL DEFAULT TRUE;

-- Create indexes for performance (if they don't exist)
CREATE INDEX IF NOT EXISTS fac_noise_capacity_idx 
ON facilities_facility (noise_level, capacity);

CREATE INDEX IF NOT EXISTS fac_building_floor_idx 
ON facilities_facility (building_code, floor_number);

-- Verify columns were added
SELECT 
    COLUMN_NAME, 
    COLUMN_TYPE, 
    IS_NULLABLE, 
    COLUMN_DEFAULT
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = 'facilities_facility' 
AND TABLE_SCHEMA = 'dssc_analytics'
AND COLUMN_NAME IN (
    'equipment_list', 
    'hours_of_operation', 
    'noise_level', 
    'floor_number', 
    'building_code', 
    'has_wheelchair_access'
)
ORDER BY ORDINAL_POSITION;

-- Check indexes
SELECT * FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_NAME = 'facilities_facility' 
AND TABLE_SCHEMA = 'dssc_analytics'
AND INDEX_NAME IN (
    'fac_noise_capacity_idx',
    'fac_building_floor_idx'
);
