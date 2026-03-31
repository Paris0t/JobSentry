"""Job search, listing, and matching CLI commands."""

import asyncio
import webbrowser
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from jobsentry.config import get_settings
from jobsentry.db.repository import JobRepository
from jobsentry.models.profile import UserProfile

app = typer.Typer(no_args_is_help=True)
console = Console()


def _load_profile() -> UserProfile:
    settings = get_settings()
    path = settings.get_profile_path()
    if not path.exists():
        console.print("[red]No profile found. Run 'jobsentry profile init' first.[/red]")
        raise typer.Exit(1)
    return UserProfile.model_validate_json(path.read_text())


def _run_async(coro):
    """Run an async function from sync CLI context."""
    return asyncio.run(coro)


async def _search_jobs(board: str, keywords: list[str], location: str | None, pages: int):
    """Run the scraper and return job listings."""
    from jobsentry.automation.browser import BrowserManager
    from jobsentry.scrapers.clearancejobs import ClearanceJobsScraper  # noqa: ensure registered
    from jobsentry.scrapers.indeed import IndeedScraper  # noqa: ensure registered
    from jobsentry.scrapers.linkedin import LinkedInScraper  # noqa: ensure registered
    from jobsentry.scrapers.registry import get_scraper

    settings = get_settings()

    async with BrowserManager(settings.data_dir, headless=settings.headless) as bm:
        context = await bm.get_context(site=board)
        scraper = get_scraper(board, context)
        jobs = await scraper.search(
            keywords=keywords,
            location=location,
            pages=pages,
        )
        await bm.save_cookies(board)
        return jobs


@app.command()
def search(
    keywords: Optional[str] = typer.Option(None, "--keywords", "-k", help="Search keywords (comma-separated)"),
    board: str = typer.Option("clearancejobs", "--board", "-b", help="Job board to search"),
    location: Optional[str] = typer.Option(None, "--location", "-l", help="Location filter"),
    pages: int = typer.Option(3, "--pages", "-p", help="Number of pages to scrape"),
):
    """Search for jobs on a job board."""
    profile = _load_profile()

    # Default keywords from profile if not specified
    if keywords:
        kw_list = [k.strip() for k in keywords.split(",")]
    elif profile.desired_titles:
        kw_list = profile.desired_titles[:3]
        console.print(f"Using profile titles as keywords: {', '.join(kw_list)}")
    else:
        console.print("[red]Provide --keywords or set desired_titles in your profile.[/red]")
        raise typer.Exit(1)

    loc = location or (profile.desired_locations[0] if profile.desired_locations else None)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(f"Searching {board}...", total=None)
        jobs = _run_async(_search_jobs(board, kw_list, loc, pages))

    if not jobs:
        console.print("[yellow]No jobs found. Try different keywords or check your connection.[/yellow]")
        return

    # Save to database
    repo = JobRepository()
    new_count = repo.upsert_jobs(jobs)
    console.print(
        f"[green]Found {len(jobs)} jobs ({new_count} new, {len(jobs) - new_count} updated)[/green]"
    )


@app.command("list")
def list_jobs(
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Filter by source"),
    matched: bool = typer.Option(False, "--matched", "-m", help="Show only matched jobs"),
    unmatched: bool = typer.Option(False, "--unmatched", "-u", help="Show only unmatched jobs"),
    limit: int = typer.Option(25, "--limit", "-n", help="Number of jobs to show"),
):
    """List jobs from the database."""
    repo = JobRepository()
    jobs = repo.list_jobs(
        source=source,
        matched_only=matched,
        unmatched_only=unmatched,
        limit=limit,
    )

    if not jobs:
        console.print("[yellow]No jobs found. Run 'jobsentry jobs search' first.[/yellow]")
        return

    table = Table(title=f"Jobs ({len(jobs)} shown)")
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", style="bold", max_width=35)
    table.add_column("Company", max_width=20)
    table.add_column("Location", max_width=20)
    table.add_column("Clearance", max_width=12)
    table.add_column("Score", justify="right", width=6)
    table.add_column("Source", style="dim", width=14)

    for i, job in enumerate(jobs, 1):
        score = f"{job.match_score:.0%}" if job.match_score is not None else "—"
        score_style = ""
        if job.match_score is not None:
            if job.match_score >= 0.75:
                score_style = "bold green"
            elif job.match_score >= 0.5:
                score_style = "yellow"
            else:
                score_style = "dim"

        table.add_row(
            str(i),
            job.title,
            job.company,
            job.location,
            job.clearance_required or "—",
            f"[{score_style}]{score}[/{score_style}]" if score_style else score,
            job.source,
        )

    console.print(table)


@app.command()
def show(
    job_num: int = typer.Argument(..., help="Job number from 'jobs list' output"),
    source: Optional[str] = typer.Option(None, "--source", "-s"),
    matched: bool = typer.Option(False, "--matched", "-m"),
):
    """Show full details of a job."""
    repo = JobRepository()
    jobs = repo.list_jobs(source=source, matched_only=matched, limit=100)

    if job_num < 1 or job_num > len(jobs):
        console.print(f"[red]Invalid job number. Valid range: 1-{len(jobs)}[/red]")
        raise typer.Exit(1)

    job = jobs[job_num - 1]

    console.print(Panel(f"[bold]{job.title}[/bold]\n{job.company}", style="blue"))

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="bold cyan", width=16)
    table.add_column("Value")

    table.add_row("ID", job.id)
    table.add_row("Source", job.source)
    table.add_row("URL", job.url)
    table.add_row("Location", job.location)
    table.add_row("Remote", job.remote_type or "—")
    table.add_row("Clearance", job.clearance_required or "—")
    table.add_row("Polygraph", job.polygraph_required or "—")

    if job.salary_min or job.salary_max:
        sal = ""
        if job.salary_min:
            sal += f"${job.salary_min:,}"
        if job.salary_max:
            sal += f" - ${job.salary_max:,}"
        table.add_row("Salary", sal)

    if job.match_score is not None:
        table.add_row("Match Score", f"{job.match_score:.0%}")
        table.add_row("Match Reason", job.match_reasoning or "—")

    table.add_row("Posted", str(job.posted_date) if job.posted_date else "—")
    table.add_row("Scraped", str(job.scraped_at))

    console.print(table)
    console.print()
    console.print(Panel(job.description[:2000] if job.description else "No description", title="Description"))


@app.command("open")
def open_job(
    job_num: int = typer.Argument(..., help="Job number from 'jobs list' output"),
    source: Optional[str] = typer.Option(None, "--source", "-s"),
    matched: bool = typer.Option(False, "--matched", "-m"),
):
    """Open a job listing in your browser."""
    repo = JobRepository()
    jobs = repo.list_jobs(source=source, matched_only=matched, limit=100)

    if job_num < 1 or job_num > len(jobs):
        console.print(f"[red]Invalid job number. Valid range: 1-{len(jobs)}[/red]")
        raise typer.Exit(1)

    job = jobs[job_num - 1]
    webbrowser.open(job.url)
    console.print(f"Opened: {job.url}")


@app.command()
def fetch(
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Only fetch from this source"),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of jobs to fetch details for"),
):
    """Fetch full descriptions for jobs that only have summaries."""
    settings = get_settings()
    repo = JobRepository()

    # Find jobs with empty or very short descriptions
    jobs = repo.list_jobs(source=source, limit=500)
    needs_fetch = [j for j in jobs if len(j.description) < 100][:limit]

    if not needs_fetch:
        console.print("[green]All jobs already have full descriptions.[/green]")
        return

    console.print(f"Fetching details for {len(needs_fetch)} jobs...")

    async def _do_fetch():
        from jobsentry.automation.browser import BrowserManager
        from jobsentry.scrapers.clearancejobs import ClearanceJobsScraper  # noqa
        from jobsentry.scrapers.linkedin import LinkedInScraper  # noqa
        from jobsentry.scrapers.registry import get_scraper

        fetched = 0
        async with BrowserManager(settings.data_dir, headless=settings.headless) as bm:
            # Group by source so we reuse contexts
            by_source: dict[str, list] = {}
            for j in needs_fetch:
                by_source.setdefault(j.source, []).append(j)

            for src, src_jobs in by_source.items():
                context = await bm.get_context(site=src)
                try:
                    scraper = get_scraper(src, context)
                except ValueError:
                    continue

                for j in src_jobs:
                    detail = await scraper.get_job_detail(j.id)
                    if detail and detail.description:
                        j.description = detail.description
                        if detail.remote_type:
                            j.remote_type = detail.remote_type
                        repo.upsert_job(j)
                        fetched += 1
                    await BrowserManager.human_delay(
                        await context.new_page(), 1000, 3000
                    )

                await bm.save_cookies(src)

        return fetched

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Fetching job details...", total=None)
        fetched = _run_async(_do_fetch())

    console.print(f"[green]Enriched {fetched}/{len(needs_fetch)} jobs with full descriptions.[/green]")


@app.command()
def match(
    limit: int = typer.Option(0, "--limit", "-n", help="Max jobs to score (0 = use daily_match_limit from config)"),
    threshold: float = typer.Option(0.0, "--threshold", "-t", help="Only show results above this score"),
    rerun: bool = typer.Option(False, "--rerun", help="Re-score already matched jobs"),
):
    """AI-match unscored jobs against your profile."""
    settings = get_settings()

    # Default to daily_match_limit from config (saves tokens)
    if limit <= 0:
        limit = settings.daily_match_limit

    if not settings.anthropic_api_key:
        console.print(
            "[red]JOBSENTRY_ANTHROPIC_API_KEY not set. "
            "Add it to .env or export it.[/red]"
        )
        raise typer.Exit(1)

    profile = _load_profile()
    repo = JobRepository()

    jobs = repo.list_jobs(unmatched_only=not rerun, limit=limit)
    if not jobs:
        console.print("[yellow]No unmatched jobs. Run 'jobsentry jobs search' first.[/yellow]")
        return

    console.print(f"Matching {len(jobs)} jobs against your profile...")

    from jobsentry.ai.matcher import match_jobs

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Running AI matching...", total=None)
        results = match_jobs(profile, jobs)

    # Update database
    for result in results:
        repo.update_match(result.job_id, result.score, result.reasoning)

    # Display results
    results.sort(key=lambda r: r.score, reverse=True)
    filtered = [r for r in results if r.score >= threshold]

    table = Table(title=f"Match Results ({len(filtered)} jobs)")
    table.add_column("Score", justify="right", width=6)
    table.add_column("Job", max_width=50)
    table.add_column("Reasoning", max_width=50)

    job_map = {j.id: j for j in jobs}
    for r in filtered:
        job = job_map.get(r.job_id)
        if not job:
            continue

        score_style = "bold green" if r.score >= 0.75 else "yellow" if r.score >= 0.5 else "dim"
        table.add_row(
            f"[{score_style}]{r.score:.0%}[/{score_style}]",
            f"{job.title}\n[dim]{job.company}[/dim]",
            r.reasoning,
        )

    console.print(table)

    above_threshold = len([r for r in results if r.score >= settings.match_threshold])
    console.print(
        f"\n[green]{above_threshold} jobs scored above your threshold "
        f"({settings.match_threshold:.0%})[/green]"
    )


@app.command()
def login(
    board: str = typer.Argument("clearancejobs", help="Job board to log in to"),
):
    """Interactively log in to a job board (saves cookies for future use)."""
    settings = get_settings()

    urls = {
        "clearancejobs": "https://www.clearancejobs.com/login",
        "linkedin": "https://www.linkedin.com/login",
        "indeed": "https://secure.indeed.com/auth",
    }

    if board not in urls:
        console.print(f"[red]Unknown board '{board}'. Available: {', '.join(urls.keys())}[/red]")
        raise typer.Exit(1)

    console.print(f"Opening {board} login page in a browser window...")
    console.print("[dim]Log in, then come back here and press Enter.[/dim]")

    async def _do_login():
        from jobsentry.automation.browser import BrowserManager
        bm = BrowserManager(settings.data_dir, headless=False)
        await bm.interactive_login(urls[board], board)

    _run_async(_do_login())
    console.print(f"[green]Cookies saved for {board}.[/green]")
