-- Content Factory SaaS alignment migration
-- Source of truth: runtime code in app/, engine/, tasks/, database/database.py
-- Safe to re-run on partially migrated projects.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- 1. user_settings (required by onboarding, settings, UserConfig)
-- ============================================================

CREATE TABLE IF NOT EXISTS public.user_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES public.users(id) ON DELETE CASCADE,
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

ALTER TABLE public.user_settings
    ADD COLUMN IF NOT EXISTS gemini_api_key TEXT,
    ADD COLUMN IF NOT EXISTS ai_provider TEXT DEFAULT 'gemini',
    ADD COLUMN IF NOT EXISTS provider_fallback TEXT,
    ADD COLUMN IF NOT EXISTS ai_model TEXT,
    ADD COLUMN IF NOT EXISTS ai_api_key TEXT,
    ADD COLUMN IF NOT EXISTS onboarding_step INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS onboarding_complete BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS telegram_chat_id TEXT,
    ADD COLUMN IF NOT EXISTS pexels_api_key TEXT,
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
    ADD COLUMN IF NOT EXISTS brand_color TEXT DEFAULT '#F9C74F',
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_user_settings_user_id
    ON public.user_settings(user_id);

ALTER TABLE public.user_settings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS user_settings_owner ON public.user_settings;
CREATE POLICY user_settings_owner ON public.user_settings
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());


-- ============================================================
-- 2. telegram_connections (required by tasks/telegram_bot.py)
-- ============================================================

CREATE TABLE IF NOT EXISTS public.telegram_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES public.users(id) ON DELETE CASCADE,
    chat_id TEXT,
    unique_code TEXT UNIQUE,
    connected_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.telegram_connections
    ADD COLUMN IF NOT EXISTS chat_id TEXT,
    ADD COLUMN IF NOT EXISTS unique_code TEXT,
    ADD COLUMN IF NOT EXISTS connected_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_telegram_connections_user_id
    ON public.telegram_connections(user_id);
CREATE INDEX IF NOT EXISTS idx_telegram_connections_unique_code
    ON public.telegram_connections(unique_code);
CREATE INDEX IF NOT EXISTS idx_telegram_connections_chat_id
    ON public.telegram_connections(chat_id);

ALTER TABLE public.telegram_connections ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS telegram_owner ON public.telegram_connections;
CREATE POLICY telegram_owner ON public.telegram_connections
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());


-- ============================================================
-- 3. managed_pages alignment
-- ============================================================

ALTER TABLE public.managed_pages
    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES public.users(id),
    ADD COLUMN IF NOT EXISTS posting_times TEXT DEFAULT '12:00,18:00,20:00',
    ADD COLUMN IF NOT EXISTS posts_per_day INTEGER DEFAULT 3,
    ADD COLUMN IF NOT EXISTS instagram_account_id TEXT,
    ADD COLUMN IF NOT EXISTS token_expires_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_managed_pages_user_id
    ON public.managed_pages(user_id);


-- ============================================================
-- 4. raw_articles alignment (runtime source of truth = engine/scraper.py)
-- ============================================================

CREATE TABLE IF NOT EXISTS public.raw_articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    source_name TEXT NOT NULL DEFAULT 'unknown',
    title TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL,
    content TEXT,
    published_date TEXT,
    keywords JSONB DEFAULT '[]'::jsonb,
    virality_score INTEGER DEFAULT 0,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT DEFAULT 'pending'
);

ALTER TABLE public.raw_articles
    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS source_name TEXT,
    ADD COLUMN IF NOT EXISTS title TEXT,
    ADD COLUMN IF NOT EXISTS url TEXT,
    ADD COLUMN IF NOT EXISTS content TEXT,
    ADD COLUMN IF NOT EXISTS published_date TEXT,
    ADD COLUMN IF NOT EXISTS keywords JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS virality_score INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS scraped_at TIMESTAMPTZ DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending';

-- Backfill from older column names if they exist.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'raw_articles' AND column_name = 'source'
    ) AND EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'raw_articles' AND column_name = 'source_name'
    ) THEN
        EXECUTE '
            UPDATE public.raw_articles
               SET source_name = COALESCE(source_name, source)
             WHERE source_name IS NULL
               AND source IS NOT NULL
        ';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'raw_articles' AND column_name = 'fetched_at'
    ) AND EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'raw_articles' AND column_name = 'scraped_at'
    ) THEN
        EXECUTE '
            UPDATE public.raw_articles
               SET scraped_at = COALESCE(scraped_at, fetched_at)
             WHERE scraped_at IS NULL
               AND fetched_at IS NOT NULL
        ';
    END IF;
END $$;

-- Prefer tenant-scoped dedupe over a global URL uniqueness rule.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'raw_articles_url_key'
           AND conrelid = 'public.raw_articles'::regclass
    ) THEN
        ALTER TABLE public.raw_articles DROP CONSTRAINT raw_articles_url_key;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_articles_user_url_unique
    ON public.raw_articles(user_id, url);
CREATE INDEX IF NOT EXISTS idx_raw_articles_status
    ON public.raw_articles(status);
CREATE INDEX IF NOT EXISTS idx_raw_articles_user_id
    ON public.raw_articles(user_id);


-- ============================================================
-- 5. processed_content alignment (DB blocker for generate -> schedule)
-- ============================================================

ALTER TABLE public.processed_content
    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES public.users(id),
    ADD COLUMN IF NOT EXISTS last_error TEXT,
    ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS approval_requested_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS content_hash TEXT,
    ADD COLUMN IF NOT EXISTS last_error_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS publish_attempt_id TEXT;

ALTER TABLE public.processed_content
    ALTER COLUMN status SET DEFAULT 'drafted';

-- Legacy remote schema used status='pending'; runtime scheduler only reads drafted.
UPDATE public.processed_content
   SET status = 'drafted'
 WHERE status = 'pending'
   AND (generated_text IS NOT NULL OR hook IS NOT NULL);

CREATE INDEX IF NOT EXISTS idx_processed_content_user_id
    ON public.processed_content(user_id);
CREATE INDEX IF NOT EXISTS idx_processed_content_status
    ON public.processed_content(status);
CREATE INDEX IF NOT EXISTS idx_processed_content_generated_at
    ON public.processed_content(generated_at);
CREATE INDEX IF NOT EXISTS idx_processed_content_approval_requested_at
    ON public.processed_content(approval_requested_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_processed_content_content_hash_unique
    ON public.processed_content(content_hash)
    WHERE content_hash IS NOT NULL;


-- ============================================================
-- 6. scheduled_posts alignment (runtime source of truth = engine/scheduler.py)
--    page_id is intentionally NOT required by the runtime pipeline.
-- ============================================================

CREATE TABLE IF NOT EXISTS public.scheduled_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    content_id UUID,
    scheduled_time TIMESTAMPTZ NOT NULL,
    timezone TEXT DEFAULT 'UTC',
    priority INTEGER DEFAULT 5,
    status TEXT DEFAULT 'scheduled',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    platforms TEXT DEFAULT 'facebook'
);

ALTER TABLE public.scheduled_posts
    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS content_id UUID,
    ADD COLUMN IF NOT EXISTS scheduled_time TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS timezone TEXT DEFAULT 'UTC',
    ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT 5,
    ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'scheduled',
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS platforms TEXT DEFAULT 'facebook';

ALTER TABLE public.scheduled_posts
    ALTER COLUMN status SET DEFAULT 'scheduled';

CREATE INDEX IF NOT EXISTS idx_scheduled_posts_user_id
    ON public.scheduled_posts(user_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_posts_status
    ON public.scheduled_posts(status);
CREATE INDEX IF NOT EXISTS idx_scheduled_posts_scheduled_time
    ON public.scheduled_posts(scheduled_time);
CREATE INDEX IF NOT EXISTS idx_scheduled_posts_content_id
    ON public.scheduled_posts(content_id);


-- ============================================================
-- 7. published_posts safety alignment (used by publisher + analytics)
-- ============================================================

ALTER TABLE public.published_posts
    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES public.users(id),
    ADD COLUMN IF NOT EXISTS content_id UUID,
    ADD COLUMN IF NOT EXISTS facebook_post_id TEXT,
    ADD COLUMN IF NOT EXISTS instagram_post_id TEXT,
    ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS platforms TEXT DEFAULT 'facebook',
    ADD COLUMN IF NOT EXISTS facebook_status TEXT,
    ADD COLUMN IF NOT EXISTS instagram_status TEXT,
    ADD COLUMN IF NOT EXISTS likes INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS shares INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS comments INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS reach INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_published_posts_user_id
    ON public.published_posts(user_id);
CREATE INDEX IF NOT EXISTS idx_published_posts_published_at
    ON public.published_posts(published_at);
CREATE INDEX IF NOT EXISTS idx_published_posts_content_id
    ON public.published_posts(content_id);


-- ============================================================
-- 8. Basic RLS hardening for tenant tables
-- ============================================================

ALTER TABLE public.managed_pages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.raw_articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.processed_content ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scheduled_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.published_posts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS managed_pages_owner ON public.managed_pages;
DROP POLICY IF EXISTS raw_articles_owner ON public.raw_articles;
DROP POLICY IF EXISTS processed_content_owner ON public.processed_content;
DROP POLICY IF EXISTS scheduled_posts_owner ON public.scheduled_posts;
DROP POLICY IF EXISTS published_posts_owner ON public.published_posts;

CREATE POLICY managed_pages_owner ON public.managed_pages
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY raw_articles_owner ON public.raw_articles
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY processed_content_owner ON public.processed_content
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY scheduled_posts_owner ON public.scheduled_posts
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY published_posts_owner ON public.published_posts
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());
