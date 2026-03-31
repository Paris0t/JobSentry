"""Database CRUD operations."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from jobsentry.db.engine import get_session, init_db
from jobsentry.db.tables import JobTable
from jobsentry.models.job import JobListing


class JobRepository:
    def __init__(self, session: Session | None = None):
        init_db()
        self._session = session

    @property
    def session(self) -> Session:
        if self._session is None:
            self._session = get_session()
        return self._session

    def upsert_job(self, job: JobListing) -> None:
        """Insert or update a job listing."""
        existing = self.session.get(JobTable, job.id)
        if existing:
            for field in ["title", "company", "description", "location", "remote_type",
                          "salary_min", "salary_max", "clearance_required", "polygraph_required",
                          "posted_date", "application_count"]:
                setattr(existing, field, getattr(job, field))
            existing.scraped_at = datetime.utcnow()
        else:
            row = JobTable(
                id=job.id,
                external_id=job.external_id,
                source=job.source,
                url=job.url,
                title=job.title,
                company=job.company,
                description=job.description,
                location=job.location,
                remote_type=job.remote_type,
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                clearance_required=job.clearance_required,
                polygraph_required=job.polygraph_required,
                posted_date=job.posted_date,
                scraped_at=job.scraped_at,
                application_count=job.application_count,
            )
            self.session.add(row)
        self.session.commit()

    def upsert_jobs(self, jobs: list[JobListing]) -> int:
        """Bulk upsert jobs. Returns count of new jobs inserted."""
        new_count = 0
        for job in jobs:
            existing = self.session.get(JobTable, job.id)
            if not existing:
                new_count += 1
            self.upsert_job(job)
        return new_count

    def get_job(self, job_id: str) -> JobListing | None:
        row = self.session.get(JobTable, job_id)
        if not row:
            return None
        return self._row_to_job(row)

    def list_jobs(
        self,
        source: str | None = None,
        matched_only: bool = False,
        unmatched_only: bool = False,
        limit: int = 50,
    ) -> list[JobListing]:
        stmt = select(JobTable)
        if source:
            stmt = stmt.where(JobTable.source == source)
        if matched_only:
            stmt = stmt.where(JobTable.match_score.isnot(None)).order_by(
                JobTable.match_score.desc()
            )
        elif unmatched_only:
            stmt = stmt.where(JobTable.match_score.is_(None))
        else:
            stmt = stmt.order_by(JobTable.scraped_at.desc())
        stmt = stmt.limit(limit)

        rows = self.session.execute(stmt).scalars().all()
        return [self._row_to_job(r) for r in rows]

    def update_match(self, job_id: str, score: float, reasoning: str) -> None:
        row = self.session.get(JobTable, job_id)
        if row:
            row.match_score = score
            row.match_reasoning = reasoning
            self.session.commit()

    def _row_to_job(self, row: JobTable) -> JobListing:
        return JobListing(
            id=row.id,
            external_id=row.external_id,
            source=row.source,
            url=row.url,
            title=row.title,
            company=row.company,
            description=row.description,
            location=row.location or "",
            remote_type=row.remote_type,
            salary_min=row.salary_min,
            salary_max=row.salary_max,
            clearance_required=row.clearance_required,
            polygraph_required=row.polygraph_required,
            posted_date=row.posted_date,
            scraped_at=row.scraped_at,
            application_count=row.application_count,
            match_score=row.match_score,
            match_reasoning=row.match_reasoning,
        )
