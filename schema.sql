-- ============================================
-- CONTENT FACTORY - SUPABASE DATABASE SCHEMA
-- ============================================
-- À exécuter dans le SQL Editor de Supabase
-- ============================================

-- Table 1: Articles bruts collectés depuis les sources
CREATE TABLE IF NOT EXISTS raw_articles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_name TEXT NOT NULL,
  title TEXT NOT NULL,
  url TEXT UNIQUE NOT NULL,
  content TEXT,
  published_date TIMESTAMP,
  keywords TEXT[],
  virality_score INTEGER DEFAULT 0,
  scraped_at TIMESTAMP DEFAULT NOW(),
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'processed', 'rejected'))
);

-- Table 2: Contenus générés par l'IA
CREATE TABLE IF NOT EXISTS processed_content (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  article_id UUID REFERENCES raw_articles(id) ON DELETE CASCADE,
  post_type TEXT NOT NULL CHECK (post_type IN ('text', 'reel')),
  generated_text TEXT NOT NULL,
  script_for_reel TEXT,
  hashtags TEXT[],
  hook TEXT,
  call_to_action TEXT,
  target_audience TEXT DEFAULT 'US',
  generated_at TIMESTAMP DEFAULT NOW()
);

-- Table 3: Planning de publication
CREATE TABLE IF NOT EXISTS scheduled_posts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id UUID REFERENCES processed_content(id) ON DELETE CASCADE,
  scheduled_time TIMESTAMP NOT NULL,
  timezone TEXT DEFAULT 'America/New_York',
  priority INTEGER DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),
  status TEXT DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'publishing', 'published', 'failed')),
  created_at TIMESTAMP DEFAULT NOW()
);

-- Table 4: Posts publiés + analytics
CREATE TABLE IF NOT EXISTS published_posts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id UUID REFERENCES processed_content(id) ON DELETE CASCADE,
  facebook_post_id TEXT UNIQUE,
  published_at TIMESTAMP DEFAULT NOW(),
  likes INTEGER DEFAULT 0,
  shares INTEGER DEFAULT 0,
  comments INTEGER DEFAULT 0,
  reach INTEGER DEFAULT 0,
  impressions INTEGER DEFAULT 0,
  video_views INTEGER DEFAULT 0,
  estimated_cpm DECIMAL(10,2),
  last_updated TIMESTAMP DEFAULT NOW()
);

-- Table 5: Métriques globales quotidiennes
CREATE TABLE IF NOT EXISTS performance_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  date DATE NOT NULL UNIQUE,
  total_posts INTEGER DEFAULT 0,
  total_reach INTEGER DEFAULT 0,
  total_engagement INTEGER DEFAULT 0,
  avg_cpm DECIMAL(10,2),
  best_post_id UUID REFERENCES published_posts(id),
  revenue_estimate DECIMAL(10,2),
  created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- INDEX POUR OPTIMISATION PERFORMANCES
-- ============================================

-- Index pour accélérer les recherches fréquentes
CREATE INDEX IF NOT EXISTS idx_raw_articles_status ON raw_articles(status);
CREATE INDEX IF NOT EXISTS idx_raw_articles_scraped_at ON raw_articles(scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_articles_url ON raw_articles(url);

CREATE INDEX IF NOT EXISTS idx_processed_content_article_id ON processed_content(article_id);
CREATE INDEX IF NOT EXISTS idx_processed_content_post_type ON processed_content(post_type);

CREATE INDEX IF NOT EXISTS idx_scheduled_posts_time ON scheduled_posts(scheduled_time);
CREATE INDEX IF NOT EXISTS idx_scheduled_posts_status ON scheduled_posts(status);
CREATE INDEX IF NOT EXISTS idx_scheduled_posts_content_id ON scheduled_posts(content_id);

CREATE INDEX IF NOT EXISTS idx_published_posts_date ON published_posts(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_published_posts_facebook_id ON published_posts(facebook_post_id);
CREATE INDEX IF NOT EXISTS idx_published_posts_content_id ON published_posts(content_id);

CREATE INDEX IF NOT EXISTS idx_performance_metrics_date ON performance_metrics(date DESC);

-- ============================================
-- VUES UTILES POUR ANALYTICS
-- ============================================

-- Vue: Top 10 posts performers
CREATE OR REPLACE VIEW top_performing_posts AS
SELECT 
  pp.id,
  pp.facebook_post_id,
  pp.published_at,
  pp.likes + pp.shares + pp.comments AS total_engagement,
  pp.reach,
  pp.video_views,
  pp.estimated_cpm,
  pc.post_type,
  pc.hook,
  ra.title AS article_title
FROM published_posts pp
LEFT JOIN processed_content pc ON pp.content_id = pc.id
LEFT JOIN raw_articles ra ON pc.article_id = ra.id
ORDER BY total_engagement DESC
LIMIT 10;

-- Vue: Statistiques quotidiennes
CREATE OR REPLACE VIEW daily_stats AS
SELECT 
  DATE(published_at) AS date,
  COUNT(*) AS posts_published,
  SUM(likes) AS total_likes,
  SUM(shares) AS total_shares,
  SUM(comments) AS total_comments,
  SUM(reach) AS total_reach,
  AVG(estimated_cpm) AS avg_cpm
FROM published_posts
GROUP BY DATE(published_at)
ORDER BY date DESC;

-- Vue: Statut du pipeline
CREATE OR REPLACE VIEW pipeline_status AS
SELECT 
  'Articles Pending' AS stage,
  COUNT(*) AS count
FROM raw_articles
WHERE status = 'pending'
UNION ALL
SELECT 
  'Content Generated' AS stage,
  COUNT(*) AS count
FROM processed_content
UNION ALL
SELECT 
  'Posts Scheduled' AS stage,
  COUNT(*) AS count
FROM scheduled_posts
WHERE status = 'scheduled'
UNION ALL
SELECT 
  'Posts Published' AS stage,
  COUNT(*) AS count
FROM published_posts;

-- ============================================
-- FONCTIONS HELPER
-- ============================================

-- Fonction: Nettoyer les anciens articles (> 30 jours)
CREATE OR REPLACE FUNCTION cleanup_old_articles()
RETURNS INTEGER AS $$
DECLARE
  deleted_count INTEGER;
BEGIN
  DELETE FROM raw_articles
  WHERE scraped_at < NOW() - INTERVAL '30 days'
    AND status = 'processed';
  
  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Fonction: Calculer engagement rate
CREATE OR REPLACE FUNCTION calculate_engagement_rate(post_id UUID)
RETURNS DECIMAL AS $$
DECLARE
  engagement INTEGER;
  post_reach INTEGER;
BEGIN
  SELECT 
    (likes + shares + comments),
    reach
  INTO engagement, post_reach
  FROM published_posts
  WHERE id = post_id;
  
  IF post_reach > 0 THEN
    RETURN (engagement::DECIMAL / post_reach::DECIMAL) * 100;
  ELSE
    RETURN 0;
  END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- PERMISSIONS (Row Level Security)
-- ============================================

-- Activer RLS sur toutes les tables
ALTER TABLE raw_articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE processed_content ENABLE ROW LEVEL SECURITY;
ALTER TABLE scheduled_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE published_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE performance_metrics ENABLE ROW LEVEL SECURITY;

-- Policy: Permettre toutes les opérations pour les utilisateurs authentifiés
-- (À adapter selon vos besoins de sécurité)
CREATE POLICY "Allow all for authenticated users" ON raw_articles
  FOR ALL USING (true);

CREATE POLICY "Allow all for authenticated users" ON processed_content
  FOR ALL USING (true);

CREATE POLICY "Allow all for authenticated users" ON scheduled_posts
  FOR ALL USING (true);

CREATE POLICY "Allow all for authenticated users" ON published_posts
  FOR ALL USING (true);

CREATE POLICY "Allow all for authenticated users" ON performance_metrics
  FOR ALL USING (true);

-- ============================================
-- DONNÉES DE TEST (OPTIONNEL)
-- ============================================

-- Insérer un article de test
-- INSERT INTO raw_articles (source_name, title, url, content, virality_score, status)
-- VALUES (
--   'techcrunch',
--   'Test Article: AI Revolutionizes Tech Industry',
--   'https://example.com/test-article',
--   'This is a test article about artificial intelligence and its impact on the tech industry.',
--   8,
--   'pending'
-- );

-- ============================================
-- VÉRIFICATIONS POST-INSTALLATION
-- ============================================

-- Vérifier que toutes les tables sont créées
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- Vérifier les index
SELECT indexname, tablename 
FROM pg_indexes 
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- ============================================
-- FIN DU SCHEMA
-- ============================================
-- 
-- ✅ Après exécution de ce script:
-- 1. Toutes les tables sont créées
-- 2. Index optimisés pour performance
-- 3. Vues utiles pour analytics
-- 4. Fonctions helper disponibles
-- 5. RLS activé pour sécurité
--
-- 🔄 Prochaine étape:
-- - Copier SUPABASE_URL et SUPABASE_KEY dans .env
-- - Tester connexion: python -c "import config; config.get_supabase_client()"
-- ============================================
