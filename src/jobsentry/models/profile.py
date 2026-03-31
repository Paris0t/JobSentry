"""User profile model — stored as JSON file, not in database."""

from enum import StrEnum

from pydantic import BaseModel


class ClearanceLevel(StrEnum):
    UNCLEARED = "uncleared"
    PUBLIC_TRUST = "public_trust"
    SECRET = "secret"
    TOP_SECRET = "top_secret"
    TOP_SECRET_SCI = "ts_sci"


class PolygraphType(StrEnum):
    NONE = "none"
    CI = "ci_poly"
    FULL_SCOPE = "full_scope_poly"


class WorkPreference(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"


class UserProfile(BaseModel):
    # Identity
    full_name: str
    email: str
    phone: str = ""
    location: str = ""  # General location (e.g., "Northern Virginia")
    linkedin_url: str | None = None

    # Clearance
    clearance_level: ClearanceLevel = ClearanceLevel.TOP_SECRET
    polygraph: PolygraphType = PolygraphType.NONE
    clearance_active: bool = True

    # Professional
    resume_text: str = ""
    resume_pdf_path: str | None = None
    years_experience: int = 0
    title: str = ""
    skills: list[str] = []
    certifications: list[str] = []

    # Preferences
    desired_titles: list[str] = []
    desired_locations: list[str] = []
    work_preferences: list[WorkPreference] = [WorkPreference.REMOTE, WorkPreference.HYBRID]
    min_salary: int | None = None
    max_commute_miles: int | None = None
    excluded_companies: list[str] = []

    # Site credentials (usernames only — passwords are env vars)
    clearancejobs_username: str | None = None
    linkedin_username: str | None = None
