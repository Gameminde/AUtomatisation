-- ============================================
-- Content Factory SaaS - Supabase Schema
-- ============================================
-- Run this SQL in Supabase SQL Editor
-- Run each section separately if you get errors
-- ============================================


-- ============================================
-- SECTION 0: Multi-tenant user system (NEW)
-- ============================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS activation_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT UNIQUE NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    used_by UUID REFERENCES users(id) ON DELETE SET NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- How to generate activation codes:
-- INSERT INTO activation_codes (code) VALUES
--   (gen_random_uuid()::text),
--   (gen_random_uuid()::text);
-- Then share the 'code' values with buyers.

-- Add user_id to content tables
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'processed_content' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE processed_content ADD COLUMN user_id UUID REFERENCES users(id);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scheduled_posts' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE scheduled_posts ADD COLUMN user_id UUID REFERENCES users(id);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'published_posts' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE published_posts ADD COLUMN user_id UUID REFERENCES users(id);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'raw_articles' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE raw_articles ADD COLUMN user_id UUID REFERENCES users(id);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'managed_pages' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE managed_pages ADD COLUMN user_id UUID REFERENCES users(id);
    END IF;
END $$;

-- Indexes for user_id lookups
CREATE INDEX IF NOT EXISTS idx_processed_content_user ON processed_content(user_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_posts_user ON scheduled_posts(user_id);
CREATE INDEX IF NOT EXISTS idx_published_posts_user ON published_posts(user_id);
CREATE INDEX IF NOT EXISTS idx_managed_pages_user ON managed_pages(user_id);


-- ============================================
-- SECTION 1: Create managed_pages table (if new)
-- ============================================
CREATE TABLE IF NOT EXISTS managed_pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id TEXT UNIQUE NOT NULL,
    page_name TEXT DEFAULT 'My Page',
    access_token TEXT NOT NULL,
    posts_per_day INTEGER DEFAULT 3 CHECK (posts_per_day BETWEEN 1 AND 5),
    posting_times TEXT DEFAULT '08:00,13:00,19:00',
    language TEXT DEFAULT 'ar',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Migration: add posting_times to existing managed_pages (run if column missing)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'managed_pages' AND column_name = 'posting_times'
    ) THEN
        ALTER TABLE managed_pages ADD COLUMN posting_times TEXT DEFAULT '08:00,13:00,19:00';
    END IF;
END $$;

-- ============================================
-- SECTION 2: Add missing columns to existing tables
-- ============================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'processed_content' AND column_name = 'created_at'
    ) THEN
        ALTER TABLE processed_content ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW();
    END IF;
END $$;

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

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'processed_content' AND column_name = 'virality_score'
    ) THEN
        ALTER TABLE processed_content ADD COLUMN virality_score FLOAT;
    END IF;
END $$;

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
-- SECTION 3: Indexes
-- ============================================
CREATE INDEX IF NOT EXISTS idx_scheduled_time ON scheduled_posts(scheduled_time);
CREATE INDEX IF NOT EXISTS idx_published_at ON published_posts(published_at);

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
-- SECTION 4: Instagram publishing support
-- ============================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'published_posts' AND column_name = 'instagram_post_id'
    ) THEN
        ALTER TABLE published_posts ADD COLUMN instagram_post_id TEXT;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'published_posts' AND column_name = 'platforms'
    ) THEN
        ALTER TABLE published_posts ADD COLUMN platforms TEXT DEFAULT 'facebook';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'published_posts' AND column_name = 'facebook_status'
    ) THEN
        ALTER TABLE published_posts ADD COLUMN facebook_status TEXT;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'published_posts' AND column_name = 'instagram_status'
    ) THEN
        ALTER TABLE published_posts ADD COLUMN instagram_status TEXT;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scheduled_posts' AND column_name = 'platforms'
    ) THEN
        ALTER TABLE scheduled_posts ADD COLUMN platforms TEXT DEFAULT 'facebook';
    END IF;
END $$;


-- ============================================
-- SECTION 5: Row Level Security (RLS)
-- NOTE: Since the backend uses the service key (bypasses RLS),
-- these policies protect against direct anon-key access only.
-- Application-level user_id filtering in Python is the primary isolation.
-- ============================================

-- Enable RLS (does not affect service key)
ALTER TABLE managed_pages ENABLE ROW LEVEL SECURITY;
ALTER TABLE processed_content ENABLE ROW LEVEL SECURITY;
ALTER TABLE scheduled_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE published_posts ENABLE ROW LEVEL SECURITY;

-- Service role bypasses RLS automatically.
-- No policies needed for backend - add them here only if you expose
-- the Supabase anon key to the frontend in a future phase.


-- ============================================
-- Done! All tables ready.
-- ============================================
