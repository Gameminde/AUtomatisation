-- ============================================
-- Content Factory - Supabase Tables
-- ============================================
-- Run this SQL in Supabase SQL Editor
-- Note: Run each section separately if you get errors
-- ============================================

-- ============================================
-- SECTION 1: Create managed_pages table (NEW)
-- ============================================
CREATE TABLE IF NOT EXISTS managed_pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id TEXT UNIQUE NOT NULL,
    page_name TEXT DEFAULT 'My Page',
    access_token TEXT NOT NULL,
    posts_per_day INTEGER DEFAULT 3 CHECK (posts_per_day BETWEEN 1 AND 5),
    language TEXT DEFAULT 'ar',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- SECTION 2: Add missing columns to existing tables
-- Run these if tables already exist
-- ============================================

-- Add created_at to processed_content if missing
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'processed_content' AND column_name = 'created_at'
    ) THEN
        ALTER TABLE processed_content ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW();
    END IF;
END $$;

-- Add ab_test_id and ab_variant_style if missing
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'processed_content' AND column_name = 'ab_test_id'
    ) THEN
        ALTER TABLE processed_content ADD COLUMN ab_test_id TEXT;
        ALTER TABLE processed_content ADD COLUMN ab_variant_style TEXT;
    END IF;
END $$;

-- Add virality_score if missing
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'processed_content' AND column_name = 'virality_score'
    ) THEN
        ALTER TABLE processed_content ADD COLUMN virality_score FLOAT;
    END IF;
END $$;

-- Add created_at to scheduled_posts if missing
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'scheduled_posts' AND column_name = 'created_at'
    ) THEN
        ALTER TABLE scheduled_posts ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW();
    END IF;
END $$;

-- ============================================
-- SECTION 3: Create indexes (safe - IF NOT EXISTS)
-- ============================================
CREATE INDEX IF NOT EXISTS idx_scheduled_time ON scheduled_posts(scheduled_time);
CREATE INDEX IF NOT EXISTS idx_published_at ON published_posts(published_at);

-- Only create this index if created_at column exists
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'processed_content' AND column_name = 'created_at'
    ) THEN
        CREATE INDEX IF NOT EXISTS idx_content_created ON processed_content(created_at);
    END IF;
END $$;

-- ============================================
-- Done! All tables ready.
-- ============================================
