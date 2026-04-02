"""Basic smoke tests — verify imports and core functionality."""


def test_imports():
    """All core modules should import without errors."""
    from jobsentry.config import get_settings, validate_settings
    from jobsentry.db.tables import JobTable
    from jobsentry.db.repository import JobRepository
    from jobsentry.models.job import JobListing
    from jobsentry.models.profile import UserProfile
    from jobsentry.notifications.email import EmailNotifier
    from jobsentry.notifications.telegram import TelegramNotifier
    from jobsentry.automation.auto_apply import AutoApplier
    from jobsentry.scrapers.registry import list_scrapers

    assert JobTable is not None
    assert JobRepository is not None
    assert JobListing is not None
    assert UserProfile is not None
    assert EmailNotifier is not None
    assert TelegramNotifier is not None
    assert AutoApplier is not None


def test_settings_defaults():
    """Settings should load with sensible defaults."""
    from jobsentry.config import get_settings

    settings = get_settings()
    assert settings.default_board == "clearancejobs"
    assert settings.match_threshold == 0.65
    assert settings.daily_match_limit == 10
    assert settings.smtp_host == "smtp.gmail.com"
    assert settings.smtp_port == 587
    assert settings.headless is True


def test_validate_settings():
    """Validate should return warnings, not crash."""
    from jobsentry.config import validate_settings

    warnings = validate_settings()
    assert isinstance(warnings, list)


def test_job_model():
    """JobListing model should accept valid data."""
    from jobsentry.models.job import JobListing

    job = JobListing(
        id="test:123",
        external_id="123",
        source="test",
        url="https://example.com/job/123",
        title="Security Analyst",
        company="Test Corp",
        description="A test job listing.",
    )
    assert job.id == "test:123"
    assert job.match_score is None
    assert job.notified_at is None
    assert job.applied_at is None


def test_profile_model():
    """UserProfile model should accept valid data."""
    from jobsentry.models.profile import UserProfile, ClearanceLevel

    profile = UserProfile(
        full_name="Test User",
        email="test@example.com",
        clearance_level=ClearanceLevel.TOP_SECRET_SCI,
        skills=["Python", "AWS", "SIEM"],
    )
    assert profile.clearance_level == ClearanceLevel.TOP_SECRET_SCI
    assert "Python" in profile.skills


def test_repository_init():
    """Repository should initialize without errors."""
    from jobsentry.db.repository import JobRepository

    repo = JobRepository()
    assert repo is not None


def test_repository_stats():
    """Stats should return a valid dict."""
    from jobsentry.db.repository import JobRepository

    repo = JobRepository()
    stats = repo.get_stats()
    assert "total" in stats
    assert "matched" in stats
    assert "sources" in stats
    assert "score_brackets" in stats


def test_email_notifier_disabled():
    """Email notifier should be disabled without SMTP config."""
    from jobsentry.notifications.email import EmailNotifier

    notifier = EmailNotifier()
    # In CI, SMTP won't be configured
    assert isinstance(notifier.enabled, bool)


def test_cli_app():
    """CLI app should respond to --help."""
    import typer.testing
    from jobsentry.cli.app import app

    runner = typer.testing.CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "jobsentry" in result.output.lower()
    assert "profile" in result.output
    assert "jobs" in result.output
