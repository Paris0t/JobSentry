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

<p align="center">
  <a href="https://github.com/Paris0t/JobSentry/actions"><img src="https://github.com/Paris0t/JobSentry/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/AI-Claude%20Sonnet-blueviolet.svg" alt="Claude AI">
</p>

---

JobSentry scrapes job boards, scores listings against your profile using Claude AI, and sends you a branded digest of top matches with direct apply links and your resume attached. It only notifies you about new jobs — no duplicates, no spam. It can even auto-apply to Easy Apply jobs for you.

## Features

- **Multi-board scraping** — ClearanceJobs, LinkedIn, Indeed (Playwright headless browser)
- **AI-powered matching** — Claude scores every job 0-100% against your resume, clearance, skills, and preferences
- **Smart notifications** — only sends jobs you haven't seen before; no duplicate alerts
- **Auto-apply** — automatically applies to Indeed and LinkedIn Easy Apply jobs (experimental)
- **Branded email digests** — premium HTML emails with score badges, match reasoning, apply buttons, and motivational quotes
- **Telegram alerts** — real-time notifications for search completions, matches, and summaries
- **Application tracking** — mark jobs as applied, view stats, track your pipeline
- **Auto-login** — stored credentials with cookie persistence across sessions
- **Scheduled runs** — cron or systemd timer for fully automated discovery (configurable frequency)
- **Health checks** — built-in scraper diagnostics and config validation
- **Privacy-first** — all credentials in `.env`, all data stored locally in SQLite, nothing leaves your machine except API calls

## Quick Start

### 1. Install

```bash
git clone https://github.com/Paris0t/JobSentry.git
cd JobSentry
python3 -m venv .venv
source .venv/bin/activate    # or: source .venv/bin/activate.fish
pip install -e .
playwright install chromium
```

### 2. Configure

```bash
cp .env.example .env         # Edit with your API keys and credentials
jobsentry profile init       # Interactive profile setup (name, clearance, skills, resume)
jobsentry check              # Verify your configuration
```

### 3. Authenticate with job boards

```bash
jobsentry jobs login clearancejobs   # Opens browser for login, saves cookies
jobsentry jobs login linkedin        # Same for LinkedIn
# Indeed doesn't require login
```

### 4. Run the pipeline

```bash
jobsentry jobs search          # Scrape job boards for new listings
jobsentry jobs fetch           # Fetch full descriptions for new jobs
jobsentry jobs match           # AI-score jobs against your profile
jobsentry notify digest        # Email top matches with resume attached
```

### 5. Track and apply

```bash
jobsentry jobs list --matched  # View your top matches
jobsentry jobs auto-apply      # Auto-apply to Easy Apply jobs
jobsentry jobs applied 3       # Manually mark job #3 as applied
jobsentry jobs stats           # View your pipeline statistics
```

### 6. Automate it

```bash
jobsentry schedule setup       # Set up a recurring cron job (every 5 days by default)
```

## Configuration

Copy `.env.example` to `.env` and fill in what you need:

```bash
# Required — Claude API key for AI matching
JOBSENTRY_ANTHROPIC_API_KEY=sk-ant-...

# Job board credentials (for auto-login when cookies expire)
JOBSENTRY_CLEARANCEJOBS_PASSWORD=...
JOBSENTRY_LINKEDIN_PASSWORD=...

# Email notifications (Gmail app password recommended)
JOBSENTRY_SMTP_USERNAME=you@gmail.com
JOBSENTRY_SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx    # App password, not your Gmail password
JOBSENTRY_NOTIFY_EMAILS=you@gmail.com

# Telegram notifications (optional)
JOBSENTRY_TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
JOBSENTRY_TELEGRAM_CHAT_ID=123456789
```

Run `jobsentry check` after editing to verify everything is configured correctly.

<details>
<summary><strong>All environment variables</strong></summary>

| Variable | Default | Description |
|----------|---------|-------------|
| `JOBSENTRY_ANTHROPIC_API_KEY` | *required* | Claude API key ([get one](https://console.anthropic.com/)) |
| `JOBSENTRY_CLEARANCEJOBS_PASSWORD` | — | Auto-login password for ClearanceJobs |
| `JOBSENTRY_LINKEDIN_PASSWORD` | — | Auto-login password for LinkedIn |
| `JOBSENTRY_DATA_DIR` | `~/.local/share/jobsentry` | Where database, cookies, and logs are stored |
| `JOBSENTRY_MATCH_MODEL` | `claude-sonnet-4-20250514` | Claude model for job matching |
| `JOBSENTRY_MATCH_THRESHOLD` | `0.65` | Minimum match score to include in digests |
| `JOBSENTRY_DAILY_MATCH_LIMIT` | `10` | Max jobs to AI-score per run (controls API costs) |
| `JOBSENTRY_HEADLESS` | `true` | Run browser in headless mode |
| `JOBSENTRY_DEFAULT_BOARD` | `clearancejobs` | Default board for `jobs search` |
| `JOBSENTRY_SEARCH_PAGES` | `3` | Pages to scrape per search |
| `JOBSENTRY_SMTP_USERNAME` | — | SMTP username (your email) |
| `JOBSENTRY_SMTP_PASSWORD` | — | SMTP password ([Gmail app password](https://myaccount.google.com/apppasswords)) |
| `JOBSENTRY_SMTP_HOST` | `smtp.gmail.com` | SMTP server |
| `JOBSENTRY_SMTP_PORT` | `587` | SMTP port (TLS) |
| `JOBSENTRY_NOTIFY_EMAILS` | — | Comma-separated recipient list |
| `JOBSENTRY_TELEGRAM_BOT_TOKEN` | — | Telegram bot token from [@BotFather](https://t.me/BotFather) |
| `JOBSENTRY_TELEGRAM_CHAT_ID` | — | Your Telegram chat ID |

</details>

## Commands

### Profile

```
jobsentry profile init          # Interactive setup — name, clearance, skills, resume
jobsentry profile show          # View current profile
jobsentry profile edit          # Open profile JSON in $EDITOR
```

### Jobs

```
jobsentry jobs search           # Scrape all configured boards
jobsentry jobs search -b indeed # Scrape a specific board
jobsentry jobs search -p 5      # Scrape 5 pages deep
jobsentry jobs fetch            # Fetch full descriptions for jobs with short summaries
jobsentry jobs list             # Show all scraped jobs
jobsentry jobs list --matched   # Show AI-scored jobs only
jobsentry jobs list --applied   # Show jobs you've applied to
jobsentry jobs show 3           # Full details of job #3
jobsentry jobs open 3           # Open job #3 in browser
jobsentry jobs match            # Run AI matching on unscored jobs
jobsentry jobs login <board>    # Interactive login (clearancejobs, linkedin, indeed)
jobsentry jobs applied 3        # Mark job #3 as applied
jobsentry jobs auto-apply       # Auto-apply to Easy Apply jobs (Indeed, LinkedIn)
jobsentry jobs stats            # Database statistics and score distribution
jobsentry jobs doctor           # Scraper health check + config validation
jobsentry jobs prune            # Remove jobs older than 90 days
```

### Notifications

```
jobsentry notify digest             # Email top matches (only new/unsent jobs)
jobsentry notify digest -n 20       # Send top 20 instead of 10
jobsentry notify digest --since 7d  # Re-send matches from last 7 days
jobsentry notify summary            # Telegram daily summary
jobsentry notify test               # Test Telegram connection
jobsentry notify chatid             # Helper to find your Telegram chat ID
```

### Scheduling

```
jobsentry schedule setup                      # Default: every 5 days at 8 AM
jobsentry schedule setup -f daily             # Run daily
jobsentry schedule setup -f weekdays          # Weekdays only
jobsentry schedule setup -f twice-daily       # 8 AM and 8 PM
jobsentry schedule setup -f every-5-days      # Every 5 days (default)
jobsentry schedule setup --hour 6 --minute 30 # Custom time
jobsentry schedule setup --dry-run            # Preview without installing
jobsentry schedule status                     # View schedule and recent logs
jobsentry schedule remove                     # Remove the cron job
```

### System

```
jobsentry check                 # Validate configuration
jobsentry version               # Show version
```

## How Matching Works

JobSentry uses Claude to score each job against your profile on a 0-100% scale. The AI evaluates:

| Criteria | Weight | What it checks |
|----------|--------|----------------|
| Title alignment | 25% | How well the job title matches your desired roles |
| Skills overlap | 25% | Which of your technical skills match the requirements |
| Clearance fit | 20% | Whether your clearance level meets the requirement |
| Location match | 15% | Remote preference, geographic proximity |
| Experience level | 15% | Years of experience vs. job expectations |

Each job gets a score with written reasoning. Only jobs above 65% (configurable) appear in your digest.

Jobs are batched (10 at a time) to control API token usage. You can limit daily scoring with `JOBSENTRY_DAILY_MATCH_LIMIT` to manage costs.

## Auto-Apply (Experimental)

JobSentry can automatically apply to jobs that support Easy Apply on Indeed and LinkedIn:

```bash
# Preview what would be applied to
jobsentry jobs auto-apply --dry-run

# Apply to top 5 matches above 75%
jobsentry jobs auto-apply

# Apply to more jobs with a lower threshold
jobsentry jobs auto-apply --top 10 --threshold 0.65

# Only apply to Indeed jobs
jobsentry jobs auto-apply --board indeed
```

Auto-apply fills in your name, email, and phone from your profile. Jobs that require external applications (company websites) are skipped automatically. Applied jobs are tracked in the database so they won't be applied to again.

## Email Digest

The email digest is a branded HTML report featuring:

- **Shield/radar logo** and "AI Job Intelligence Report" header in navy/blue
- **Stats bar** showing match count, score range, and date
- **Job cards** with color-coded score badges, apply buttons, and AI reasoning
- **Motivational quote** to keep you going (rotated each digest)
- **Resume attachment** for easy applications

## Automated Pipeline

When scheduled, JobSentry runs this pipeline automatically:

```
Scrape boards  ->  Fetch descriptions  ->  AI match  ->  Email digest  ->  Telegram summary
```

The digest only includes jobs you haven't been notified about before — no repeated emails for the same job.

Set it up with:

```bash
jobsentry schedule setup --frequency every-5-days
```

Or for systemd-based servers, see `deploy/proxmox-setup.sh`.

## Data Storage

All data stays local on your machine:

```
~/.local/share/jobsentry/
  profile.json          # Your profile and resume text
  jobsentry.db          # SQLite database (all jobs + scores + applied status)
  cookies/              # Browser session cookies (per site)
  logs/                 # Scheduled run logs (last 30 kept)
```

Clean up old data with `jobsentry jobs prune --older-than 90`.

## Architecture

```
src/jobsentry/
  cli/              # Typer CLI — profile, jobs, notify, schedule
  scrapers/         # Playwright headless scrapers — ClearanceJobs, LinkedIn, Indeed
  ai/               # Anthropic Claude integration — job matching + scoring
  db/               # SQLAlchemy + SQLite — job storage, match results, notification + apply tracking
  notifications/    # Email (SMTP + branded HTML) and Telegram (Bot API)
  automation/       # Browser management, cookie persistence, auto-apply engine
  models/           # Pydantic models — UserProfile, JobListing
  config.py         # pydantic-settings — all env vars with validation
```

## Deployment

### Quick deploy (any Linux server)

```bash
git clone https://github.com/Paris0t/JobSentry.git
cd JobSentry
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/playwright install chromium --with-deps
cp .env.example .env && vim .env
jobsentry profile init
jobsentry check
jobsentry schedule setup
```

### Proxmox LXC

A full automated setup script is provided for Debian 12 containers:

```bash
# Create LXC (1 core, 1GB RAM, 4GB disk)
pct create 200 local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst \
  --hostname jobsentry --memory 1024 --cores 1 \
  --rootfs local-lvm:4 --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --unprivileged 1 --features nesting=1 --start 1

# Inside the container
bash /tmp/proxmox-setup.sh
```

Then copy your `.env` and `profile.json` to the container and start the timer.

See [`deploy/proxmox-setup.sh`](deploy/proxmox-setup.sh) for full details.

### Updating a deployed instance

```bash
./deploy/sync-to-lxc.sh <LXC_IP>
```

## Requirements

- Python 3.11+
- Chromium (auto-installed via Playwright)
- Anthropic API key ([get one here](https://console.anthropic.com/))
- Gmail app password for email digests ([create one here](https://myaccount.google.com/apppasswords))

## Support

If you find JobSentry useful, consider supporting development:

<a href="https://buymeacoffee.com/paris0t" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="40">
</a>

## License

MIT
