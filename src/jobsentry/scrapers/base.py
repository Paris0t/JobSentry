"""Abstract base class for job board scrapers."""

from abc import ABC, abstractmethod

from playwright.async_api import BrowserContext

from jobsentry.models.job import JobListing


class BaseScraper(ABC):
    """Base class for all job board scrapers."""

    name: str
    base_url: str

    def __init__(self, browser_context: BrowserContext):
        self.context = browser_context

    @abstractmethod
    async def search(
        self,
        keywords: list[str],
        location: str | None = None,
        clearance: str | None = None,
        pages: int = 3,
    ) -> list[JobListing]:
        """Search for jobs and return structured listings."""
        ...

    @abstractmethod
    async def get_job_detail(self, job_id: str) -> JobListing | None:
        """Fetch full details for a single job listing."""
        ...

    @abstractmethod
    async def login(self, username: str, password: str) -> bool:
        """Authenticate with the job board. Returns True on success."""
        ...
