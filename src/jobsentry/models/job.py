"""Job listing model."""

from datetime import datetime

from pydantic import BaseModel, Field


class JobListing(BaseModel):
    id: str  # "{source}:{external_id}"
    external_id: str
    source: str  # "clearancejobs", "linkedin", etc.
    url: str

    title: str
    company: str
    description: str
    location: str = ""
    remote_type: str | None = None  # "remote", "hybrid", "onsite"
    salary_min: int | None = None
    salary_max: int | None = None
    clearance_required: str | None = None
    polygraph_required: str | None = None

    posted_date: datetime | None = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    application_count: int | None = None

    # AI-computed (populated after matching)
    match_score: float | None = None
    match_reasoning: str | None = None
