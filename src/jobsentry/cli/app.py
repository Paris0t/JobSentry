"""Root CLI application."""

import typer

from jobsentry.cli.jobs import app as jobs_app
from jobsentry.cli.profile import app as profile_app
from jobsentry.cli.notify import app as notify_app
from jobsentry.cli.schedule import app as schedule_app

app = typer.Typer(
    name="jobsentry",
    help="AI-powered job discovery and matching for cleared professionals.",
    no_args_is_help=True,
)

app.add_typer(profile_app, name="profile", help="Manage your professional profile")
app.add_typer(jobs_app, name="jobs", help="Search, list, match, and manage jobs")
app.add_typer(notify_app, name="notify", help="Email and Telegram notifications")
app.add_typer(schedule_app, name="schedule", help="Automate job searches on a schedule")


@app.command()
def version():
    """Show the current version."""
    from jobsentry import __version__

    typer.echo(f"jobsentry v{__version__}")


@app.command()
def check():
    """Validate your configuration and show any issues."""
    from rich.console import Console
    from rich.panel import Panel

    from jobsentry.config import validate_settings

    console = Console()
    warnings = validate_settings()

    if not warnings:
        console.print(Panel("[bold green]All configured![/bold green]", style="green"))
        console.print(
            "[green]Your setup looks good. Run 'jobsentry jobs doctor' for a deeper check.[/green]"
        )
    else:
        console.print(Panel("[bold yellow]Configuration Issues[/bold yellow]", style="yellow"))
        for w in warnings:
            console.print(f"  [yellow]![/yellow] {w}")
        console.print()
        console.print("[dim]Fix these in your .env file, then run 'jobsentry check' again.[/dim]")


if __name__ == "__main__":
    app()
