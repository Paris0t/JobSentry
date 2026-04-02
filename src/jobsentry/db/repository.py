"""Database CRUD operations."""

from datetime import datetime, timedelta

from sqlalchemy import func, select
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
            for field in [
                "title",
                "company",
                "description",
                "location",
                "remote_type",
                "salary_min",
                "salary_max",
                "clearance_required",
                "polygraph_required",
                "posted_date",
                "application_count",
            ]:
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
        unnotified_only: bool = False,
        applied_only: bool = False,
        since: datetime | None = None,
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
        if unnotified_only:
            stmt = stmt.where(JobTable.notified_at.is_(None))
        if applied_only:
            stmt = stmt.where(JobTable.applied_at.isnot(None))
        if since:
            stmt = stmt.where(JobTable.scraped_at >= since)
        stmt = stmt.limit(limit)

        rows = self.session.execute(stmt).scalars().all()
        return [self._row_to_job(r) for r in rows]

    def mark_notified(self, job_ids: list[str]) -> None:
        """Mark jobs as notified so they aren't sent again."""
        if not job_ids:
            return
        now = datetime.utcnow()
        for job_id in job_ids:
            row = self.session.get(JobTable, job_id)
            if row:
                row.notified_at = now
        self.session.commit()

    def mark_applied(self, job_id: str) -> bool:
        """Mark a job as applied. Returns True if found."""
        row = self.session.get(JobTable, job_id)
        if not row:
            return False
        row.applied_at = datetime.utcnow()
        self.session.commit()
        return True

    def update_match(self, job_id: str, score: float, reasoning: str) -> None:
        row = self.session.get(JobTable, job_id)
        if row:
            row.match_score = score
            row.match_reasoning = reasoning
            self.session.commit()

    def get_stats(self) -> dict:
        """Get database statistics."""
        total = self.session.execute(select(func.count()).select_from(JobTable)).scalar() or 0

        matched = (
            self.session.execute(
                select(func.count()).select_from(JobTable).where(JobTable.match_score.isnot(None))
            ).scalar()
            or 0
        )

        high_matches = (
            self.session.execute(
                select(func.count()).select_from(JobTable).where(JobTable.match_score >= 0.75)
            ).scalar()
            or 0
        )

        notified = (
            self.session.execute(
                select(func.count()).select_from(JobTable).where(JobTable.notified_at.isnot(None))
            ).scalar()
            or 0
        )

        applied = (
            self.session.execute(
                select(func.count()).select_from(JobTable).where(JobTable.applied_at.isnot(None))
            ).scalar()
            or 0
        )

        # Per-source counts
        sources = {}
        source_rows = self.session.execute(
            select(JobTable.source, func.count()).group_by(JobTable.source)
        ).all()
        for src, count in source_rows:
            sources[src] = count

        # Score distribution
        score_brackets = {}
        for label, low, high in [
            ("90-100%", 0.9, 1.01),
            ("75-89%", 0.75, 0.9),
            ("65-74%", 0.65, 0.75),
            ("50-64%", 0.5, 0.65),
            ("<50%", 0.0, 0.5),
        ]:
            count = (
                self.session.execute(
                    select(func.count())
                    .select_from(JobTable)
                    .where(
                        JobTable.match_score >= low,
                        JobTable.match_score < high,
                    )
                ).scalar()
                or 0
            )
            if count > 0:
                score_brackets[label] = count

        # Recent activity (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent = (
            self.session.execute(
                select(func.count()).select_from(JobTable).where(JobTable.scraped_at >= week_ago)
            ).scalar()
            or 0
        )

        return {
            "total": total,
            "matched": matched,
            "unmatched": total - matched,
            "high_matches": high_matches,
            "notified": notified,
            "applied": applied,
            "sources": sources,
            "score_brackets": score_brackets,
            "recent_7d": recent,
        }

    def prune_old(self, days: int = 90) -> int:
        """Delete jobs older than N days. Returns count deleted."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        rows = (
            self.session.execute(select(JobTable).where(JobTable.scraped_at < cutoff))
            .scalars()
            .all()
        )
        count = len(rows)
        for row in rows:
            self.session.delete(row)
        if count:
            self.session.commit()
        return count

    def find_duplicates(self) -> list[tuple[str, str]]:
        """Find likely duplicate jobs across boards (same company + similar title).
        Returns list of (keep_id, duplicate_id) pairs."""
        dupes = []
        # Get all jobs grouped by normalized company
        stmt = (
            select(JobTable)
            .where(JobTable.match_score.isnot(None))
            .order_by(JobTable.match_score.desc())
        )
        rows = self.session.execute(stmt).scalars().all()

        seen: dict[str, JobTable] = {}  # "company:title_normalized" -> best row
        for row in rows:
            key = f"{row.company.lower().strip()}:{row.title.lower().strip()}"
            if key in seen:
                dupes.append((seen[key].id, row.id))
            else:
                seen[key] = row
        return dupes

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
            notified_at=row.notified_at,
            applied_at=row.applied_at,
        )
