"""Profile management CLI commands."""

import json
import os
import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from jobsentry.config import get_settings
from jobsentry.models.profile import (
    ClearanceLevel,
    PolygraphType,
    UserProfile,
    WorkPreference,
)

app = typer.Typer(no_args_is_help=True)
console = Console()


def _load_profile() -> UserProfile | None:
    settings = get_settings()
    path = settings.get_profile_path()
    if not path.exists():
        return None
    return UserProfile.model_validate_json(path.read_text())


def _save_profile(profile: UserProfile) -> Path:
    settings = get_settings()
    settings.ensure_dirs()
    path = settings.get_profile_path()
    path.write_text(profile.model_dump_json(indent=2))
    return path


def _prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"  {label}{suffix}: ").strip()
    return val or default


def _prompt_list(label: str, hint: str = "comma-separated") -> list[str]:
    val = input(f"  {label} ({hint}): ").strip()
    if not val:
        return []
    return [item.strip() for item in val.split(",") if item.strip()]


def _prompt_choice(label: str, choices: list[str], default: str) -> str:
    choices_str = "/".join(choices)
    val = input(f"  {label} ({choices_str}) [{default}]: ").strip()
    return val if val in choices else default


@app.command()
def init():
    """Interactive profile setup wizard."""
    console.print(Panel("[bold]JobSentry Profile Setup[/bold]", style="blue"))
    console.print()

    existing = _load_profile()
    if existing:
        overwrite = typer.confirm("  Profile already exists. Overwrite?", default=False)
        if not overwrite:
            raise typer.Abort()

    console.print("[bold]Identity[/bold]")
    full_name = _prompt("Full name")
    email = _prompt("Email")
    phone = _prompt("Phone")
    location = _prompt("Location (e.g., Northern Virginia)")
    linkedin_url = _prompt("LinkedIn URL (optional)") or None

    console.print()
    console.print("[bold]Clearance[/bold]")
    clearance = _prompt_choice(
        "Clearance level",
        [e.value for e in ClearanceLevel],
        ClearanceLevel.TOP_SECRET.value,
    )
    polygraph = _prompt_choice(
        "Polygraph", [e.value for e in PolygraphType], PolygraphType.NONE.value
    )
    clearance_active = _prompt_choice("Clearance active?", ["yes", "no"], "yes") == "yes"

    console.print()
    console.print("[bold]Professional[/bold]")
    title = _prompt("Current title (e.g., Information Security Analyst)")
    years_exp = int(_prompt("Years of experience", "5"))
    skills = _prompt_list("Skills", "e.g., NIST 800-53, SIEM, Splunk, Risk Assessment")
    certs = _prompt_list("Certifications", "e.g., CISSP, Security+, CISM")

    console.print()
    console.print("[bold]Resume[/bold]")
    resume_pdf = _prompt("Path to resume PDF (optional)") or None
    console.print("  Paste your resume text below (press Enter twice when done):")
    lines = []
    while True:
        line = input()
        if line == "":
            if lines and lines[-1] == "":
                lines.pop()
                break
            lines.append(line)
        else:
            lines.append(line)
    resume_text = "\n".join(lines)

    console.print()
    console.print("[bold]Job Preferences[/bold]")
    desired_titles = _prompt_list(
        "Desired job titles",
        "e.g., Information Security Analyst, ISSO, Cybersecurity Analyst",
    )
    desired_locations = _prompt_list("Desired locations", "e.g., Remote, Washington DC, NOVA")
    work_pref_input = _prompt_list("Work type", "remote, hybrid, onsite")
    work_prefs = []
    for wp in work_pref_input:
        try:
            work_prefs.append(WorkPreference(wp.lower()))
        except ValueError:
            pass
    if not work_prefs:
        work_prefs = [WorkPreference.REMOTE, WorkPreference.HYBRID]

    min_salary_str = _prompt("Minimum salary (annual USD, optional)")
    min_salary = int(min_salary_str) if min_salary_str else None

    excluded = _prompt_list("Companies to exclude (optional)")

    console.print()
    console.print("[bold]Site Credentials (usernames only — passwords go in .env)[/bold]")
    cj_user = _prompt("ClearanceJobs username (optional)") or None
    li_user = _prompt("LinkedIn username/email (optional)") or None

    profile = UserProfile(
        full_name=full_name,
        email=email,
        phone=phone,
        location=location,
        linkedin_url=linkedin_url,
        clearance_level=ClearanceLevel(clearance),
        polygraph=PolygraphType(polygraph),
        clearance_active=clearance_active,
        resume_text=resume_text,
        resume_pdf_path=resume_pdf,
        years_experience=years_exp,
        title=title,
        skills=skills,
        certifications=certs,
        desired_titles=desired_titles,
        desired_locations=desired_locations,
        work_preferences=work_prefs,
        min_salary=min_salary,
        excluded_companies=excluded,
        clearancejobs_username=cj_user,
        linkedin_username=li_user,
    )

    path = _save_profile(profile)
    console.print()
    console.print(f"[green]Profile saved to {path}[/green]")


@app.command()
def show():
    """Display your current profile."""
    profile = _load_profile()
    if not profile:
        console.print("[red]No profile found. Run 'jobsentry profile init' first.[/red]")
        raise typer.Exit(1)

    console.print(Panel(f"[bold]{profile.full_name}[/bold]", style="blue"))

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="bold cyan", width=20)
    table.add_column("Value")

    table.add_row("Title", profile.title)
    table.add_row("Email", profile.email)
    table.add_row("Phone", profile.phone)
    table.add_row("Location", profile.location)
    table.add_row("LinkedIn", profile.linkedin_url or "—")
    table.add_row("", "")
    table.add_row("Clearance", profile.clearance_level.value.replace("_", " ").title())
    table.add_row("Polygraph", profile.polygraph.value.replace("_", " ").title())
    table.add_row("Active", "Yes" if profile.clearance_active else "No")
    table.add_row("", "")
    table.add_row("Experience", f"{profile.years_experience} years")
    table.add_row("Skills", ", ".join(profile.skills) if profile.skills else "—")
    table.add_row("Certifications", ", ".join(profile.certifications) if profile.certifications else "—")
    table.add_row("", "")
    table.add_row("Desired Titles", ", ".join(profile.desired_titles) if profile.desired_titles else "—")
    table.add_row("Desired Locations", ", ".join(profile.desired_locations) if profile.desired_locations else "—")
    table.add_row("Work Type", ", ".join(w.value for w in profile.work_preferences))
    table.add_row("Min Salary", f"${profile.min_salary:,}" if profile.min_salary else "—")
    table.add_row("Excluded Companies", ", ".join(profile.excluded_companies) if profile.excluded_companies else "—")
    table.add_row("", "")
    table.add_row("Resume PDF", profile.resume_pdf_path or "—")
    table.add_row("Resume Text", f"{len(profile.resume_text)} chars" if profile.resume_text else "—")

    console.print(table)


@app.command()
def edit():
    """Open profile JSON in your default editor."""
    settings = get_settings()
    path = settings.get_profile_path()
    if not path.exists():
        console.print("[red]No profile found. Run 'jobsentry profile init' first.[/red]")
        raise typer.Exit(1)

    editor = os.environ.get("EDITOR", "vim")
    subprocess.run([editor, str(path)])

    # Validate after editing
    try:
        UserProfile.model_validate_json(path.read_text())
        console.print("[green]Profile is valid.[/green]")
    except Exception as e:
        console.print(f"[red]Warning: Profile has validation errors: {e}[/red]")
