# Content Factory - Facebook Automation Dashboard

## Overview
A Python-based web dashboard for automating social media content creation and publishing to Facebook. Features AI-powered content generation, news scraping, image handling, and scheduling.

## Architecture
- **Framework:** Flask (Python 3.10)
- **Database:** SQLite (default, local) or Supabase (optional cloud)
- **Frontend:** Vanilla JS + Bootstrap-style CSS served by Flask templates
- **AI:** Google Gemini (primary) or OpenRouter/Claude (fallback)

## Key Files
- `dashboard_app.py` - Main Flask application entry point
- `config.py` - Centralized configuration and environment variable handling
- `database.py` - Database abstraction layer (SQLite/Supabase)
- `ai_generator.py` - AI content generation
- `scraper.py` - News/RSS scraping
- `publisher.py` - Facebook Graph API publishing
- `scheduler.py` - Post scheduling
- `templates/` - HTML templates for the dashboard
- `static/` - CSS, JS, and other frontend assets

## Running the App
The app runs via `python dashboard_app.py` on port 5000. It serves on `0.0.0.0` for Replit proxy compatibility.

## Environment Variables
See `.env.example` / `env.example` for required variables:
- `GEMINI_API_KEY` - Google Gemini API key (recommended, free)
- `FACEBOOK_ACCESS_TOKEN` - Facebook Graph API token
- `FACEBOOK_PAGE_ID` - Facebook page ID to publish to
- `PEXELS_API_KEY` - Pexels image API (optional)
- `SUPABASE_URL` / `SUPABASE_KEY` - Only if using Supabase instead of SQLite
- `DASHBOARD_API_KEY` - Optional API key for dashboard auth
- `FLASK_SECRET_KEY` - Flask session key (auto-generated if not set)

## Deployment
- Production server: gunicorn via `gunicorn --bind=0.0.0.0:5000 --reuse-port dashboard_app:app`
- Deployment target: autoscale

## Dependencies
All dependencies are in `requirements.txt`. Key packages:
- flask, flask-cors
- python-dotenv
- Pillow (image processing)
- feedparser, pytrends (content sources)
- supabase (optional cloud DB)
- cryptography
- gunicorn (production server)
