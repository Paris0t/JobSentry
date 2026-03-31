# JobSentry

AI-powered job discovery and matching for cleared defense/intelligence professionals.

## Quick Start

```bash
source .venv/bin/activate.fish
jobsentry profile init          # one-time setup
jobsentry jobs login clearancejobs  # one-time auth
jobsentry jobs search           # scrape jobs
jobsentry jobs match            # AI rank them
jobsentry notify digest         # email top matches
```

## Architecture

- **CLI**: Typer (`src/jobsentry/cli/`) — all commands
- **Scrapers**: Playwright-based (`src/jobsentry/scrapers/`) — ClearanceJobs, LinkedIn, Indeed
- **AI**: Anthropic SDK (`src/jobsentry/ai/`) — job matching (Sonnet)
- **DB**: SQLAlchemy + SQLite (`src/jobsentry/db/`) — job tracking
- **Notifications**: Telegram + Email (`src/jobsentry/notifications/`) — daily summaries, match digests
- **Config**: pydantic-settings (`src/jobsentry/config.py`) — env vars from `.env`

## Key Files

- `.env` — API keys, passwords, Telegram token (chmod 600, gitignored)
- `~/.local/share/jobsentry/profile.json` — user profile and resume
- `~/.local/share/jobsentry/jobsentry.db` — SQLite database
- `~/.local/share/jobsentry/cookies/` — browser session cookies
- `deploy/proxmox-setup.sh` — LXC deployment script

## Deployment

Designed for Proxmox LXC (Debian 12).
Systemd timer runs at 8:00 AM and 6:00 PM UTC daily.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
playwright install chromium
```

## Conventions

- Auto-login via stored credentials when cookies expire
- All passwords in .env only, never in code or profile.json
