"""Application settings loaded from environment variables and .env file."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JOBSENTRY_", env_file=".env")

    # API Keys
    anthropic_api_key: str = ""

    # Paths
    data_dir: Path = Path.home() / ".local" / "share" / "jobsentry"
    profile_path: Path | None = None
    db_path: Path | None = None

    # Scraping
    default_board: str = "clearancejobs"
    search_pages: int = 3
    headless: bool = True

    # AI models
    match_model: str = "claude-sonnet-4-20250514"
    match_threshold: float = 0.65
    daily_match_limit: int = 10  # max jobs to AI-score per run (controls token usage)

    # Credentials (env vars only)
    clearancejobs_password: str | None = None
    linkedin_password: str | None = None

    # Telegram notifications
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    # Email notifications
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    notify_emails: str | None = None  # comma-separated

    def get_profile_path(self) -> Path:
        return self.profile_path or self.data_dir / "profile.json"

    def get_db_path(self) -> Path:
        return self.db_path or self.data_dir / "jobsentry.db"

    def get_cookies_dir(self) -> Path:
        return self.data_dir / "cookies"

    def ensure_dirs(self) -> None:
        """Create data directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.get_cookies_dir().mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    """Load settings from environment."""
    return Settings()
