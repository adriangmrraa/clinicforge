-- Migration Patch 022: Add Patient Admission Fields for New Admission Process
-- Adds city field and updates patient admission requirements for ClinicForge

BEGIN;

-- ==================== ADD CITY FIELD TO PATIENTS ====================
DO $$
BEGIN
    -- Add city field for patient location (Ciudad/Barrio)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='city') THEN
        ALTER TABLE patients ADD COLUMN city VARCHAR(100);
        RAISE NOTICE 'Added city column to patients table';
    END IF;
    
    -- Ensure first_touch_source exists (renamed from acquisition_source in patch 020)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='first_touch_source') THEN
        ALTER TABLE patients ADD COLUMN first_touch_source VARCHAR(50) DEFAULT 'ORGANIC';
        RAISE NOTICE 'Added first_touch_source column to patients table';
    END IF;
    
    -- Ensure birth_date exists (should already exist from initial schema)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='birth_date') THEN
        ALTER TABLE patients ADD COLUMN birth_date DATE;
        RAISE NOTICE 'Added birth_date column to patients table';
    END IF;
    
    -- Ensure email exists (should already exist from initial schema)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='email') THEN
        ALTER TABLE patients ADD COLUMN email VARCHAR(255);
        RAISE NOTICE 'Added email column to patients table';
    END IF;
END $$;

-- Create index for city field
CREATE INDEX IF NOT EXISTS idx_patients_city ON patients(city);

-- Add comments for documentation
COMMENT ON COLUMN patients.city IS 'Ciudad/Barrio del paciente para registro de admisión';
COMMENT ON COLUMN patients.first_touch_source IS 'Fuente de adquisición del paciente: ORGANIC, INSTAGRAM, GOOGLE, REFERRED, OTHER';
COMMENT ON COLUMN patients.birth_date IS 'Fecha de nacimiento del paciente (formato DD/MM/AAAA)';
COMMENT ON COLUMN patients.email IS 'Email del paciente para comunicación';

-- ==================== UPDATE BOOK_APPOINTMENT TOOL REQUIREMENTS ====================
-- Note: This migration only handles database schema changes.
-- The book_appointment tool logic will be updated in main.py separately.

RAISE NOTICE 'Migration 022 completed successfully: Added city field and ensured admission fields exist';

COMMIT;