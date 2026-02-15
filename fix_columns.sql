-- ============================================
-- Quick Fix: Add missing column to processed_content
-- Run this in Supabase SQL Editor
-- ============================================

ALTER TABLE processed_content 
ADD COLUMN IF NOT EXISTS local_image_path TEXT;

ALTER TABLE processed_content 
ADD COLUMN IF NOT EXISTS virality_score FLOAT;

ALTER TABLE processed_content 
ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
