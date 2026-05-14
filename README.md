# Job Scraper

Free-tier hybrid scraper for remote jobs. Pulls from 5 APIs + 3 HTML sources, dedupes, and writes to Google Sheets. Runs on GitHub Actions hourly/6h/12h cron + manual trigger.

See [design spec](docs/superpowers/specs/2026-05-13-job-scraper-design.md) and [implementation plan](docs/superpowers/plans/2026-05-13-job-scraper.md).

## Local dev

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in secrets
pytest
python -m src.main --window 24h --sources all
```

## Secrets required

- `GOOGLE_SHEETS_CREDS` — service account JSON
- `GOOGLE_SHEET_ID` — target sheet ID
- `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` — from developer.adzuna.com
- `RAPIDAPI_KEY` — from rapidapi.com (JSearch)
- `NTFY_TOPIC` — push notification topic
