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
    created_at TIMESTAMPTZ DEFAULT NOW(),
    user_id UUID REFERENCES users(id)
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
    article_id UUID,
    -- Original pipeline fields
    content TEXT,
    image_url TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    generated_at TIMESTAMPTZ,
    -- AI-generated content fields
    post_type TEXT,
    generated_text TEXT,
    hook TEXT,
    call_to_action TEXT,
    hashtags TEXT,
    script_for_reel TEXT,
    arabic_text TEXT,
    target_audience TEXT,
    -- Image fields
    image_path TEXT,
    local_image_path TEXT,
    template_id TEXT,
    -- Publishing fields
    fb_post_id TEXT,
    rejected_reason TEXT,
    -- A/B testing + analytics
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
    timezone TEXT DEFAULT 'UTC',
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
    -- Engagement metrics (synced from Facebook Graph API)
    likes INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    reach INTEGER DEFAULT 0,
    user_id UUID REFERENCES users(id)
);

-- System-wide status/health key-value store (not tenant-scoped)
CREATE TABLE IF NOT EXISTS system_status (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Migration: add posting_times to existing managed_pages
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'managed_pages' AND column_name = 'posting_times'
    ) THEN
        ALTER TABLE managed_pages ADD COLUMN posting_times TEXT DEFAULT '08:00,13:00,19:00';
    END IF;
END $$;

-- Migration: add user_id to existing managed_pages
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'managed_pages' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE managed_pages ADD COLUMN user_id UUID REFERENCES users(id);
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

-- !! user_id on all content tables (existing DBs that predate multi-tenant) !!
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'processed_content' AND column_name = 'user_id') THEN ALTER TABLE processed_content ADD COLUMN user_id UUID REFERENCES users(id); END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scheduled_posts'   AND column_name = 'user_id') THEN ALTER TABLE scheduled_posts   ADD COLUMN user_id UUID REFERENCES users(id); END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'published_posts'   AND column_name = 'user_id') THEN ALTER TABLE published_posts   ADD COLUMN user_id UUID REFERENCES users(id); END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'raw_articles'      AND column_name = 'user_id') THEN ALTER TABLE raw_articles      ADD COLUMN user_id UUID REFERENCES users(id); END IF; END $$;

-- Indexes for user_id lookups (safe to re-run)
CREATE INDEX IF NOT EXISTS idx_processed_content_user ON processed_content(user_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_posts_user   ON scheduled_posts(user_id);
CREATE INDEX IF NOT EXISTS idx_published_posts_user   ON published_posts(user_id);
CREATE INDEX IF NOT EXISTS idx_managed_pages_user     ON managed_pages(user_id);
CREATE INDEX IF NOT EXISTS idx_raw_articles_user      ON raw_articles(user_id);

-- processed_content: AI-generated content fields (existing DBs)
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'processed_content' AND column_name = 'article_id') THEN ALTER TABLE processed_content ADD COLUMN article_id UUID; END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'processed_content' AND column_name = 'generated_at') THEN ALTER TABLE processed_content ADD COLUMN generated_at TIMESTAMPTZ; END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'processed_content' AND column_name = 'post_type') THEN ALTER TABLE processed_content ADD COLUMN post_type TEXT; END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'processed_content' AND column_name = 'generated_text') THEN ALTER TABLE processed_content ADD COLUMN generated_text TEXT; END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'processed_content' AND column_name = 'hook') THEN ALTER TABLE processed_content ADD COLUMN hook TEXT; END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'processed_content' AND column_name = 'call_to_action') THEN ALTER TABLE processed_content ADD COLUMN call_to_action TEXT; END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'processed_content' AND column_name = 'hashtags') THEN ALTER TABLE processed_content ADD COLUMN hashtags TEXT; END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'processed_content' AND column_name = 'script_for_reel') THEN ALTER TABLE processed_content ADD COLUMN script_for_reel TEXT; END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'processed_content' AND column_name = 'arabic_text') THEN ALTER TABLE processed_content ADD COLUMN arabic_text TEXT; END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'processed_content' AND column_name = 'target_audience') THEN ALTER TABLE processed_content ADD COLUMN target_audience TEXT; END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'processed_content' AND column_name = 'image_path') THEN ALTER TABLE processed_content ADD COLUMN image_path TEXT; END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'processed_content' AND column_name = 'local_image_path') THEN ALTER TABLE processed_content ADD COLUMN local_image_path TEXT; END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'processed_content' AND column_name = 'template_id') THEN ALTER TABLE processed_content ADD COLUMN template_id TEXT; END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'processed_content' AND column_name = 'fb_post_id') THEN ALTER TABLE processed_content ADD COLUMN fb_post_id TEXT; END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'processed_content' AND column_name = 'rejected_reason') THEN ALTER TABLE processed_content ADD COLUMN rejected_reason TEXT; END IF; END $$;

-- scheduled_posts: timezone field (existing DBs)
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scheduled_posts' AND column_name = 'timezone') THEN ALTER TABLE scheduled_posts ADD COLUMN timezone TEXT DEFAULT 'UTC'; END IF; END $$;

-- published_posts: engagement metrics (existing DBs)
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'published_posts' AND column_name = 'likes') THEN ALTER TABLE published_posts ADD COLUMN likes INTEGER DEFAULT 0; END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'published_posts' AND column_name = 'shares') THEN ALTER TABLE published_posts ADD COLUMN shares INTEGER DEFAULT 0; END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'published_posts' AND column_name = 'comments') THEN ALTER TABLE published_posts ADD COLUMN comments INTEGER DEFAULT 0; END IF; END $$;
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'published_posts' AND column_name = 'reach') THEN ALTER TABLE published_posts ADD COLUMN reach INTEGER DEFAULT 0; END IF; END $$;

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
-- SECTION 6: user_settings (Phase 2 — per-user config)
-- ============================================

CREATE TABLE IF NOT EXISTS user_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    gemini_api_key TEXT,
    ai_provider TEXT DEFAULT 'gemini',
    provider_fallback TEXT,
    ai_model TEXT,
    ai_api_key TEXT,
    onboarding_step INTEGER DEFAULT 1,
    onboarding_complete BOOLEAN DEFAULT FALSE,
    telegram_chat_id TEXT,
    pexels_api_key TEXT,
    newsdata_api_key TEXT,
    language_ratio NUMERIC(3,2) DEFAULT 0.70,
    ui_language TEXT DEFAULT 'en',
    content_language TEXT DEFAULT 'en',
    content_languages TEXT DEFAULT 'en',
    content_tone TEXT DEFAULT 'professional',
    content_dialect TEXT DEFAULT '',
    content_mode TEXT DEFAULT 'single_language',
    country_code TEXT DEFAULT 'OTHER',
    timezone TEXT DEFAULT 'UTC',
    source_preset TEXT DEFAULT 'OTHER',
    niche_preset TEXT,
    rss_feed_urls TEXT,
    niche_keywords TEXT,
    approval_mode BOOLEAN DEFAULT FALSE,
    daily_summary_time TEXT DEFAULT '08:00',
    posts_per_day INTEGER DEFAULT 3,
    posting_times TEXT DEFAULT '12:00,18:00,20:00',
    brand_color TEXT DEFAULT '#F9C74F',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_settings_user ON user_settings(user_id);

ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS user_settings_owner ON user_settings;
CREATE POLICY user_settings_owner ON user_settings
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

ALTER TABLE user_settings
    ADD COLUMN IF NOT EXISTS ai_provider TEXT DEFAULT 'gemini',
    ADD COLUMN IF NOT EXISTS provider_fallback TEXT,
    ADD COLUMN IF NOT EXISTS ai_model TEXT,
    ADD COLUMN IF NOT EXISTS ai_api_key TEXT,
    ADD COLUMN IF NOT EXISTS newsdata_api_key TEXT,
    ADD COLUMN IF NOT EXISTS language_ratio NUMERIC(3,2) DEFAULT 0.70,
    ADD COLUMN IF NOT EXISTS ui_language TEXT DEFAULT 'en',
    ADD COLUMN IF NOT EXISTS content_language TEXT DEFAULT 'en',
    ADD COLUMN IF NOT EXISTS content_languages TEXT DEFAULT 'en',
    ADD COLUMN IF NOT EXISTS content_tone TEXT DEFAULT 'professional',
    ADD COLUMN IF NOT EXISTS content_dialect TEXT DEFAULT '',
    ADD COLUMN IF NOT EXISTS content_mode TEXT DEFAULT 'single_language',
    ADD COLUMN IF NOT EXISTS country_code TEXT DEFAULT 'OTHER',
    ADD COLUMN IF NOT EXISTS timezone TEXT DEFAULT 'UTC',
    ADD COLUMN IF NOT EXISTS source_preset TEXT DEFAULT 'OTHER',
    ADD COLUMN IF NOT EXISTS niche_preset TEXT,
    ADD COLUMN IF NOT EXISTS rss_feed_urls TEXT,
    ADD COLUMN IF NOT EXISTS niche_keywords TEXT,
    ADD COLUMN IF NOT EXISTS approval_mode BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS daily_summary_time TEXT DEFAULT '08:00',
    ADD COLUMN IF NOT EXISTS posts_per_day INTEGER DEFAULT 3,
    ADD COLUMN IF NOT EXISTS posting_times TEXT DEFAULT '12:00,18:00,20:00',
    ADD COLUMN IF NOT EXISTS brand_color TEXT DEFAULT '#F9C74F';

-- Migration: add instagram_account_id to managed_pages if missing
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'managed_pages' AND column_name = 'instagram_account_id'
    ) THEN
        ALTER TABLE managed_pages ADD COLUMN instagram_account_id TEXT;
    END IF;
END $$;

-- ============================================
-- SECTION 7: Engine multi-tenancy additions (Phase 3)
-- ============================================

-- Migration: add last_error to processed_content for publish failure tracking
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'processed_content' AND column_name = 'last_error'
    ) THEN
        ALTER TABLE processed_content ADD COLUMN last_error TEXT;
    END IF;
END $$;

-- Migration: add retry_count to processed_content for retry logic
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'processed_content' AND column_name = 'retry_count'
    ) THEN
        ALTER TABLE processed_content ADD COLUMN retry_count INTEGER DEFAULT 0;
    END IF;
END $$;

-- Migration: add posts_per_day and posting_times to user_settings if missing
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_settings' AND column_name = 'posts_per_day'
    ) THEN
        ALTER TABLE user_settings ADD COLUMN posts_per_day INTEGER DEFAULT 3;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_settings' AND column_name = 'posting_times'
    ) THEN
        ALTER TABLE user_settings ADD COLUMN posting_times TEXT DEFAULT '08:00,13:00,19:00';
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_settings' AND column_name = 'newsdata_api_key'
    ) THEN
        ALTER TABLE user_settings ADD COLUMN newsdata_api_key TEXT;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_settings' AND column_name = 'language_ratio'
    ) THEN
        ALTER TABLE user_settings ADD COLUMN language_ratio NUMERIC(3,2) DEFAULT 0.70;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_settings' AND column_name = 'niche_keywords'
    ) THEN
        ALTER TABLE user_settings ADD COLUMN niche_keywords TEXT;
    END IF;
END $$;

-- ============================================
-- SECTION 8: Telegram Bot (Phase 4)
-- ============================================

-- telegram_connections: one row per user, stores chat_id + unique activation code
CREATE TABLE IF NOT EXISTS telegram_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    chat_id TEXT,
    unique_code TEXT UNIQUE,
    connected_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_telegram_connections_user   ON telegram_connections(user_id);
CREATE INDEX IF NOT EXISTS idx_telegram_connections_code   ON telegram_connections(unique_code);
CREATE INDEX IF NOT EXISTS idx_telegram_connections_chatid ON telegram_connections(chat_id);

ALTER TABLE telegram_connections ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS telegram_owner ON telegram_connections;
CREATE POLICY telegram_owner ON telegram_connections
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- Migration: add approval_mode to user_settings
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_settings' AND column_name = 'approval_mode'
    ) THEN
        ALTER TABLE user_settings ADD COLUMN approval_mode BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

-- Migration: add token_expires_at to managed_pages (Facebook token expiry tracking)
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'managed_pages' AND column_name = 'token_expires_at'
    ) THEN
        ALTER TABLE managed_pages ADD COLUMN token_expires_at TIMESTAMPTZ;
    END IF;
END $$;

-- Migration: add daily_summary_time to user_settings (default 08:00 UTC)
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_settings' AND column_name = 'daily_summary_time'
    ) THEN
        ALTER TABLE user_settings ADD COLUMN daily_summary_time TEXT DEFAULT '08:00';
    END IF;
END $$;

-- Migration: add approval_requested_at to processed_content
-- Tracks when a post was moved to pending_approval so 4-hour timeout
-- is measured from approval-request time, not content-creation time.
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'processed_content' AND column_name = 'approval_requested_at'
    ) THEN
        ALTER TABLE processed_content ADD COLUMN approval_requested_at TIMESTAMPTZ;
    END IF;
END $$;

-- ============================================
-- Done! All tables ready.
-- ============================================
