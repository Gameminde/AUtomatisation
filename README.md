# Content Factory (Facebook Automation)

A minimal Python scaffold to collect tech news, generate viral posts with Gemini, schedule posts, and publish to Facebook via the Graph API.

## Quickstart

1) Create a virtual environment and install dependencies:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

2) Create a `.env` file from the template and fill your keys:

```bash
copy .env.example .env
```

3) Run modules manually:

```bash
python main.py scrape
python main.py generate --limit 5
python main.py schedule
python main.py publish --limit 5
python main.py analytics --limit 10
```

## Project Layout

- `main.py` orchestrator CLI
- `config.py` shared config, logging, and env helpers
- `scraper.py` news collection and filtering
- `ai_generator.py` Gemini content generation
- `publisher.py` Facebook publishing
- `scheduler.py` scheduling logic
- `analytics.py` metrics sync
- `requirements.txt` dependencies
- `.env.example` env var template

## Notes

- Reel publishing needs a video URL. The current `publisher.py` only supports text posts.
- Make sure your Facebook app and page permissions are set before publishing.
- Supabase tables must exist before running the pipeline.

## Database Schema

See the SQL from your planning doc for:
`raw_articles`, `processed_content`, `scheduled_posts`, `published_posts`, `performance_metrics`.

## Logs

Logs are written to `logs/` with one file per module.
