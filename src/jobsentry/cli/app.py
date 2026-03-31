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
app.add_typer(jobs_app, name="jobs", help="Search, list, and match jobs")
app.add_typer(notify_app, name="notify", help="Telegram notifications")
app.add_typer(schedule_app, name="schedule", help="Automate daily job searches")


@app.command()
def version():
    """Show the current version."""
    from jobsentry import __version__

    typer.echo(f"jobsentry v{__version__}")


if __name__ == "__main__":
    app()
