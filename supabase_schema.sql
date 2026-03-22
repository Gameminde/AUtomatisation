-- ============================================
-- Content Factory SaaS - Supabase Schema
-- ============================================
-- Run this SQL in Supabase SQL Editor.
-- Safe to run on both fresh and existing databases.
-- All statements are fully idempotent (CREATE/ALTER IF NOT EXISTS).
-- ============================================


-- ============================================
-- SECTION 0: Auth & multi-tenant tables
-- ============================================

-- Users table (custom bcrypt auth, not Supabase Auth)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Activation codes (Gumroad one-time unlock gates)
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


-- ============================================
-- SECTION 1: Core content tables
-- (CREATE before any ALTER statements below)
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

CREATE TABLE IF NOT EXISTS raw_articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT,
    title TEXT,
    content TEXT,
    source TEXT,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT DEFAULT 'new',
    user_id UUID REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS processed_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_article_id UUID,
    content TEXT,
    image_url TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    ab_test_id TEXT,
    ab_variant_style TEXT,
    virality_score FLOAT,
    user_id UUID REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS scheduled_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID,
    page_id TEXT,
    scheduled_time TIMESTAMPTZ,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    platforms TEXT DEFAULT 'facebook',
    user_id UUID REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS published_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID,
    page_id TEXT,
    facebook_post_id TEXT,
    instagram_post_id TEXT,
    published_at TIMESTAMPTZ DEFAULT NOW(),
    platforms TEXT DEFAULT 'facebook',
    facebook_status TEXT,
    instagram_status TEXT,
    user_id UUID REFERENCES users(id)
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
-- The Flask backend uses the SERVICE KEY which bypasses RLS entirely.
-- These policies protect against direct PostgREST calls using the anon key
-- and enforce tenant isolation if the anon key is ever exposed.
-- ============================================

-- Enable RLS on all tenant tables
ALTER TABLE users              ENABLE ROW LEVEL SECURITY;
ALTER TABLE managed_pages      ENABLE ROW LEVEL SECURITY;
ALTER TABLE processed_content  ENABLE ROW LEVEL SECURITY;
ALTER TABLE scheduled_posts    ENABLE ROW LEVEL SECURITY;
ALTER TABLE published_posts    ENABLE ROW LEVEL SECURITY;
ALTER TABLE raw_articles       ENABLE ROW LEVEL SECURITY;

-- Drop any existing policies before recreating (idempotent)
DROP POLICY IF EXISTS users_self           ON users;
DROP POLICY IF EXISTS managed_pages_owner  ON managed_pages;
DROP POLICY IF EXISTS content_owner        ON processed_content;
DROP POLICY IF EXISTS scheduled_owner      ON scheduled_posts;
DROP POLICY IF EXISTS published_owner      ON published_posts;
DROP POLICY IF EXISTS articles_owner       ON raw_articles;

-- Users: each user can only read/update their own row
CREATE POLICY users_self ON users
    FOR ALL
    USING (id = auth.uid())
    WITH CHECK (id = auth.uid());

-- managed_pages: only the owning user can access their pages
CREATE POLICY managed_pages_owner ON managed_pages
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- processed_content: only the owning user
CREATE POLICY content_owner ON processed_content
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- scheduled_posts: only the owning user
CREATE POLICY scheduled_owner ON scheduled_posts
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- published_posts: only the owning user
CREATE POLICY published_owner ON published_posts
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- raw_articles: only the owning user
CREATE POLICY articles_owner ON raw_articles
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- ============================================
-- IMPORTANT — Auth Model & RLS Strategy
-- ============================================
-- This app uses TWO layers of tenant isolation:
--
-- Layer 1 (Server-side, primary): The Flask backend always uses the Supabase
--   SERVICE ROLE key (SUPABASE_KEY env var must be the service_role secret).
--   The service_role has BYPASS RLS privilege in PostgreSQL, so all server-side
--   queries bypass RLS.  Python code enforces tenant isolation by always adding
--   .eq("user_id", user_id) to every Supabase query.
--
-- Layer 2 (Schema-level, defense-in-depth): The auth.uid() RLS policies below
--   protect against accidental anon-key leakage.  If the anon key were ever
--   used directly (e.g., from the browser), no user could read another user's
--   data.  These policies also prepare the schema for future phases where
--   Supabase Auth JWT will be used for client-side SDK access.
--
-- TL;DR: Set SUPABASE_KEY to your service_role key.  Never expose it to the
--   frontend.  The anon key (safe for browsers) is NOT used by the Flask app.
-- ============================================

-- activation_codes: server (service_role) handles all reads/writes via RLS bypass.
-- Deny ALL for anon/authenticated roles so codes cannot be enumerated from the browser.
ALTER TABLE activation_codes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS activation_codes_deny_anon ON activation_codes;
CREATE POLICY activation_codes_deny_anon ON activation_codes
    FOR ALL
    USING (false)
    WITH CHECK (false);
-- (service_role bypasses this policy and can still INSERT/SELECT/UPDATE freely)


-- ============================================
-- Done! All tables ready.
-- ============================================
