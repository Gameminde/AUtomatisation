-- Studio creator template defaults
-- Stores reusable visual template parameters per user without saving local image files.

ALTER TABLE public.user_settings
    ADD COLUMN IF NOT EXISTS studio_template_defaults TEXT;
