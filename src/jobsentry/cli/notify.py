"""Telegram notification CLI commands."""

from datetime import datetime, timedelta
from typing import Optional

import typer
from rich.console import Console

from jobsentry.config import get_settings
from jobsentry.notifications.telegram import TelegramNotifier

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command()
def test():
    """Send a test notification to verify Telegram is configured."""
    notifier = TelegramNotifier()

    if not notifier.enabled:
        console.print("[red]Telegram not configured. Set these in .env:[/red]")
        console.print("  JOBSENTRY_TELEGRAM_BOT_TOKEN=...")
        console.print("  JOBSENTRY_TELEGRAM_CHAT_ID=...")
        console.print()
        console.print("[dim]To get these:[/dim]")
        console.print("  1. Message @BotFather on Telegram, send /newbot")
        console.print("  2. Copy the bot token")
        console.print("  3. Message your bot, then visit:")
        console.print("     https://api.telegram.org/bot<TOKEN>/getUpdates")
        console.print("  4. Find your chat_id in the response")
        raise typer.Exit(1)

    ok = notifier.send("🤖 <b>JobSentry</b> — Telegram notifications are working!")
    if ok:
        console.print("[green]Test notification sent! Check your Telegram.[/green]")
    else:
        console.print("[red]Failed to send. Check your bot token and chat ID.[/red]")


@app.command()
def summary():
    """Send a daily summary to Telegram."""
    from jobsentry.db.repository import JobRepository

    notifier = TelegramNotifier()
    if not notifier.enabled:
        console.print("[red]Telegram not configured.[/red]")
        raise typer.Exit(1)

    job_repo = JobRepository()

    all_jobs = job_repo.list_jobs(limit=10000)

    scores = [j.match_score for j in all_jobs if j.match_score is not None]
    high = len([s for s in scores if s >= 0.75])

    stats = {
        "total_jobs": len(all_jobs),
        "new_jobs": len(all_jobs),  # Could track by date for "today" count
        "matched": len(scores),
        "high_matches": high,
    }

    ok = notifier.notify_daily_summary(stats)
    if ok:
        console.print("[green]Summary sent to Telegram.[/green]")
    else:
        console.print("[red]Failed to send summary.[/red]")


@app.command()
def digest(
    top: int = typer.Option(10, "--top", "-n", help="Number of top matches to include"),
    threshold: float = typer.Option(0.65, "--threshold", "-t", help="Minimum match score"),
    since: Optional[str] = typer.Option(
        None,
        "--since",
        "-s",
        help="Include jobs from last N days (e.g. '7d', '30d') — overrides notified filter",
    ),
):
    """Send a digest of top job matches via email (with resume attached)."""
    from jobsentry.db.repository import JobRepository
    from jobsentry.models.profile import UserProfile
    from jobsentry.notifications.email import EmailNotifier

    settings = get_settings()
    notifier = EmailNotifier()

    if not notifier.enabled:
        console.print("[red]Email not configured. Set these in .env:[/red]")
        console.print("  JOBSENTRY_SMTP_USERNAME=you@gmail.com")
        console.print("  JOBSENTRY_SMTP_PASSWORD=your-app-password")
        console.print("  JOBSENTRY_NOTIFY_EMAILS=you@gmail.com,other@work.com")
        raise typer.Exit(1)

    # Load profile for resume path
    profile_path = settings.get_profile_path()
    resume_path = None
    if profile_path.exists():
        profile = UserProfile.model_validate_json(profile_path.read_text())
        resume_path = profile.resume_pdf_path

    # Parse --since flag
    since_dt = None
    unnotified = True
    if since:
        import re

        m = re.match(r"(\d+)d", since)
        if m:
            since_dt = datetime.utcnow() - timedelta(days=int(m.group(1)))
            unnotified = False  # --since overrides the unnotified filter
        else:
            console.print("[red]Invalid --since format. Use e.g. '7d' or '30d'.[/red]")
            raise typer.Exit(1)

    # Get top matched jobs
    job_repo = JobRepository()
    all_jobs = job_repo.list_jobs(
        matched_only=True,
        unnotified_only=unnotified,
        since=since_dt,
        limit=100,
    )

    candidates = [j for j in all_jobs if j.match_score and j.match_score >= threshold][:top]

    if not candidates:
        console.print(
            f"[yellow]No {'new ' if unnotified else ''}jobs above {threshold:.0%} threshold.[/yellow]"
        )
        return

    jobs_data = []
    for j in candidates:
        salary = ""
        if j.salary_min or j.salary_max:
            parts = []
            if j.salary_min:
                parts.append(f"${j.salary_min:,}")
            if j.salary_max:
                parts.append(f"${j.salary_max:,}")
            salary = " - ".join(parts)

        jobs_data.append(
            {
                "title": j.title,
                "company": j.company,
                "score": j.match_score,
                "url": j.url,
                "location": j.location or "",
                "clearance": j.clearance_required or "",
                "salary": salary,
                "reasoning": j.match_reasoning or "",
            }
        )

    console.print(
        f"Sending digest with {len(jobs_data)} jobs to {', '.join(notifier.recipients)}..."
    )

    ok = notifier.send_job_digest(jobs_data, resume_path=resume_path)
    if ok:
        # Mark these jobs as notified so they won't be sent again
        job_repo.mark_notified([j.id for j in candidates])
        console.print(
            f"[green]Digest sent with {len(jobs_data)} matches{'+ resume' if resume_path else ''}![/green]"
        )
    else:
        console.print("[red]Failed to send digest. Check SMTP credentials.[/red]")


@app.command()
def chatid():
    """Helper to find your Telegram chat ID."""
    notifier = TelegramNotifier()

    if not notifier.bot_token:
        console.print("[red]Set JOBSENTRY_TELEGRAM_BOT_TOKEN in .env first.[/red]")
        raise typer.Exit(1)

    console.print("Send any message to your bot on Telegram, then press Enter here...")
    input()

    import httpx

    resp = httpx.get(
        f"https://api.telegram.org/bot{notifier.bot_token}/getUpdates",
        timeout=10,
    )

    if resp.status_code != 200:
        console.print("[red]Failed to fetch updates. Check your bot token.[/red]")
        raise typer.Exit(1)

    data = resp.json()
    results = data.get("result", [])
    if not results:
        console.print(
            "[yellow]No messages found. Send a message to your bot and try again.[/yellow]"
        )
        return

    chat_id = results[-1]["message"]["chat"]["id"]
    console.print(f"\n[green]Your chat ID: {chat_id}[/green]")
    console.print("\nAdd this to your .env:")
    console.print(f"  JOBSENTRY_TELEGRAM_CHAT_ID={chat_id}")
