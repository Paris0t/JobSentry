<p align="center">
  <img src="assets/banner.svg" alt="JobSentry" width="700">
</p>

<p align="center">
  <strong>AI-powered job discovery for cleared defense and intelligence professionals</strong>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="#features">Features</a> &bull;
  <a href="#commands">Commands</a> &bull;
  <a href="#configuration">Configuration</a> &bull;
  <a href="#deployment">Deployment</a>
</p>

---

JobSentry scrapes job boards, scores listings against your profile using Claude AI, and sends you a daily digest of top matches with direct apply links and your resume attached.

## Features

- **Multi-board scraping** — ClearanceJobs, LinkedIn, Indeed (Playwright-based)
- **AI-powered matching** — Claude scores every job 0-100% against your resume, clearance, skills, and preferences
- **Email digests** — HTML email with top matches, match reasoning, and direct apply links (resume attached)
- **Telegram alerts** — real-time notifications for new high-scoring matches
- **Auto-login** — stored credentials with cookie persistence across sessions
- **Scheduled runs** — cron/systemd integration for fully automated daily discovery
- **Privacy-first** — all credentials in `.env`, all data stored locally, nothing leaves your machine except API calls

## Quick Start

```bash
# Install
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install chromium

# Configure
cp .env.example .env        # Edit with your API keys and credentials
jobsentry profile init      # Interactive profile setup

# Authenticate with job boards
jobsentry jobs login clearancejobs

# Run the pipeline
jobsentry jobs search       # Scrape job boards
jobsentry jobs match        # AI-score against your profile
jobsentry notify digest     # Email top matches with resume
```

## Configuration

Copy `.env.example` to `.env` and fill in:

```bash
# Required: Claude API key (for AI matching)
JOBSENTRY_ANTHROPIC_API_KEY=sk-ant-...

# Job board credentials (for auto-login when cookies expire)
JOBSENTRY_CLEARANCEJOBS_PASSWORD=...
JOBSENTRY_LINKEDIN_PASSWORD=...

# Email notifications (Gmail app password)
JOBSENTRY_SMTP_USERNAME=you@gmail.com
JOBSENTRY_SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx
JOBSENTRY_NOTIFY_EMAILS=you@gmail.com,you@work.com

# Telegram notifications (optional)
JOBSENTRY_TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
JOBSENTRY_TELEGRAM_CHAT_ID=123456789
```

## Commands

```
jobsentry profile init          # Set up your profile (name, clearance, resume, skills)
jobsentry profile show          # View your profile
jobsentry profile edit          # Edit profile JSON in your editor

jobsentry jobs search           # Scrape all configured boards
jobsentry jobs search -b indeed # Scrape a specific board
jobsentry jobs list             # Show all scraped jobs
jobsentry jobs list --matched   # Show AI-scored jobs only
jobsentry jobs match            # Run AI matching on unscored jobs
jobsentry jobs login <board>    # Interactive login for a job board

jobsentry notify digest         # Email top matches with resume attached
jobsentry notify summary        # Send Telegram daily summary
jobsentry notify test           # Test Telegram connection

jobsentry schedule setup        # Set up daily cron job
jobsentry schedule status       # View schedule and recent logs
jobsentry schedule remove       # Remove the cron job
```

## How Matching Works

JobSentry uses Claude (Sonnet) to score each job against your profile. The AI considers:

- **Title alignment** — how well the job title matches your desired roles
- **Skills overlap** — which of your technical skills match the requirements
- **Clearance fit** — whether your clearance level meets the job's requirements
- **Location match** — remote preference, geographic proximity
- **Experience level** — years of experience vs. job requirements

Each job gets a 0-100% score with written reasoning explaining the match.

## Automated Daily Pipeline

Set up a cron job to run the full pipeline automatically:

```bash
jobsentry schedule setup --frequency twice-daily
```

This runs at 8 AM and 6 PM daily:
1. Scrapes all job boards for new listings
2. Fetches full descriptions for new jobs
3. AI-scores new jobs against your profile
4. Emails you a digest of top matches (with resume attached)
5. Sends a Telegram summary

## Architecture

```
src/jobsentry/
  cli/          # Typer CLI commands
  scrapers/     # Playwright-based job board scrapers
  ai/           # Anthropic Claude integration (matching)
  db/           # SQLAlchemy + SQLite (job storage)
  notifications/# Email (SMTP) + Telegram (Bot API)
  models/       # Pydantic models (profile, jobs)
  config.py     # pydantic-settings (env vars)
  automation/   # Browser management, cookie persistence
```

## Deployment

Designed to run on a headless server (e.g., Proxmox LXC, VPS, Raspberry Pi):

```bash
# On the server
git clone https://github.com/Paris0t/JobSentry.git
cd JobSentry
python3 -m venv .venv
.venv/bin/pip install -e .
playwright install chromium --with-deps
cp .env.example .env && vim .env
jobsentry profile init
jobsentry schedule setup --frequency twice-daily
```

See `deploy/proxmox-setup.sh` for a full automated LXC setup script.

## Requirements

- Python 3.11+
- Chromium (installed via Playwright)
- Anthropic API key ([get one here](https://console.anthropic.com/))
- Gmail app password for email notifications ([create one here](https://myaccount.google.com/apppasswords))

## Support

If you find JobSentry useful, consider supporting development:

<a href="https://buymeacoffee.com/paris0t" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="40">
</a>

## License

MIT
