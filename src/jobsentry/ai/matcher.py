"""AI-powered job matching — scores jobs against user profile."""

from dataclasses import dataclass

from jobsentry.ai.client import AIClient
from jobsentry.config import get_settings
from jobsentry.models.job import JobListing
from jobsentry.models.profile import UserProfile

MATCH_SYSTEM_PROMPT = """\
You are an expert job matching assistant for cleared defense/intelligence professionals.

Given a candidate profile and a list of job postings, score each job from 0.0 to 1.0:
- Title/role alignment (0-0.25)
- Skills/requirements overlap (0-0.25)
- Clearance level fit (0-0.20)
- Location/remote preference match (0-0.15)
- Seniority/experience alignment (0-0.15)

Be strict: 0.8+ is a strong match, 0.5-0.7 is partial, below 0.5 is weak.

Respond ONLY with a JSON array. Each element:
{"job_id": "...", "score": 0.XX, "reasoning": "one-sentence explanation"}

No other text outside the JSON array."""


@dataclass
class MatchResult:
    job_id: str
    score: float
    reasoning: str


def _build_profile_summary(profile: UserProfile) -> str:
    """Build a concise profile summary for the AI prompt."""
    parts = [
        f"Name: {profile.full_name}",
        f"Title: {profile.title}",
        f"Clearance: {profile.clearance_level.value.replace('_', ' ').title()}",
        f"Polygraph: {profile.polygraph.value.replace('_', ' ').title()}",
        f"Experience: {profile.years_experience} years",
        f"Skills: {', '.join(profile.skills)}",
        f"Certifications: {', '.join(profile.certifications)}",
        f"Desired titles: {', '.join(profile.desired_titles)}",
        f"Desired locations: {', '.join(profile.desired_locations)}",
        f"Work type: {', '.join(w.value for w in profile.work_preferences)}",
    ]
    if profile.min_salary:
        parts.append(f"Min salary: ${profile.min_salary:,}")
    if profile.excluded_companies:
        parts.append(f"Excluded companies: {', '.join(profile.excluded_companies)}")
    if profile.resume_text:
        # Include first ~2000 chars of resume for context
        resume_excerpt = profile.resume_text[:2000]
        parts.append(f"\nResume excerpt:\n{resume_excerpt}")
    return "\n".join(parts)


def _build_jobs_prompt(jobs: list[JobListing]) -> str:
    """Build the jobs list for the AI prompt."""
    entries = []
    for job in jobs:
        desc = job.description[:500] if job.description else "No description"
        entry = (
            f"---\n"
            f"Job ID: {job.id}\n"
            f"Title: {job.title}\n"
            f"Company: {job.company}\n"
            f"Location: {job.location}\n"
            f"Clearance: {job.clearance_required or 'Not specified'}\n"
            f"Description: {desc}\n"
        )
        if job.salary_min or job.salary_max:
            sal = ""
            if job.salary_min:
                sal += f"${job.salary_min:,}"
            if job.salary_max:
                sal += f" - ${job.salary_max:,}"
            entry += f"Salary: {sal}\n"
        entries.append(entry)
    return "\n".join(entries)


def match_jobs(
    profile: UserProfile,
    jobs: list[JobListing],
    batch_size: int = 10,
) -> list[MatchResult]:
    """Score a list of jobs against the user profile using Claude.

    Jobs are batched to keep costs down and stay within context limits.
    """
    settings = get_settings()
    client = AIClient()
    all_results: list[MatchResult] = []
    profile_summary = _build_profile_summary(profile)

    for i in range(0, len(jobs), batch_size):
        batch = jobs[i : i + batch_size]
        jobs_prompt = _build_jobs_prompt(batch)

        user_message = (
            f"## Candidate Profile\n{profile_summary}\n\n"
            f"## Job Postings to Score\n{jobs_prompt}"
        )

        try:
            results = client.call_json(
                system=MATCH_SYSTEM_PROMPT,
                user_message=user_message,
                model=settings.match_model,
            )
            for r in results:
                all_results.append(
                    MatchResult(
                        job_id=r["job_id"],
                        score=float(r["score"]),
                        reasoning=r.get("reasoning", ""),
                    )
                )
        except Exception as e:
            # Log but continue with remaining batches
            for job in batch:
                all_results.append(
                    MatchResult(job_id=job.id, score=0.0, reasoning=f"Error: {e}")
                )

    return all_results
