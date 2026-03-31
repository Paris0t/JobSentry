"""Indeed.com job scraper."""

import re
from datetime import datetime, timedelta
from urllib.parse import quote_plus

from playwright.async_api import BrowserContext

from jobsentry.automation.browser import BrowserManager
from jobsentry.models.job import JobListing
from jobsentry.scrapers.base import BaseScraper
from jobsentry.scrapers.registry import register


@register("indeed")
class IndeedScraper(BaseScraper):
    name = "indeed"
    base_url = "https://www.indeed.com"

    def _build_search_url(
        self,
        keywords: list[str],
        location: str | None = None,
        clearance: str | None = None,
        page: int = 0,
    ) -> str:
        query = quote_plus(" ".join(keywords))
        # Add clearance to search if specified
        if clearance:
            query = quote_plus(" ".join(keywords) + f" {clearance}")
        url = f"{self.base_url}/jobs?q={query}&fromage=14"  # last 14 days
        if location:
            url += f"&l={quote_plus(location)}"
        if page > 0:
            url += f"&start={page * 10}"  # Indeed uses 10 per page
        return url

    async def search(
        self,
        keywords: list[str],
        location: str | None = None,
        clearance: str | None = None,
        pages: int = 3,
    ) -> list[JobListing]:
        jobs: list[JobListing] = []
        page = await self.context.new_page()

        try:
            for page_num in range(pages):
                url = self._build_search_url(keywords, location, clearance, page_num)
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await BrowserManager.human_delay(page, 2000, 4000)

                # Wait for job cards to load
                try:
                    await page.wait_for_selector(
                        ".job_seen_beacon, .jobsearch-ResultsList > li, [data-jk]",
                        timeout=10000,
                    )
                except Exception:
                    pass

                page_jobs = await self._extract_jobs_from_page(page)
                if not page_jobs:
                    break
                jobs.extend(page_jobs)

                # Check for next page
                has_next = await page.locator(
                    'a[aria-label="Next Page"], [data-testid="pagination-page-next"]'
                ).count()
                if not has_next:
                    break

                await BrowserManager.human_delay(page, 2000, 5000)
        finally:
            await page.close()

        return jobs

    async def _extract_jobs_from_page(self, page) -> list[JobListing]:
        """Extract job listings from Indeed search results."""
        jobs: list[JobListing] = []

        # Indeed job cards — multiple possible selectors
        card_selectors = [
            ".job_seen_beacon",
            "[data-jk]",
            ".jobsearch-ResultsList > li",
            ".result",
        ]

        cards = None
        for selector in card_selectors:
            cards = page.locator(selector)
            count = await cards.count()
            if count > 0:
                break

        if not cards or await cards.count() == 0:
            return jobs

        count = await cards.count()
        for i in range(count):
            card = cards.nth(i)
            try:
                job = await self._parse_job_card(card)
                if job:
                    jobs.append(job)
            except Exception:
                continue

        return jobs

    async def _parse_job_card(self, card) -> JobListing | None:
        """Parse a single Indeed job card."""
        try:
            # Job ID from data attribute
            job_id = await card.get_attribute("data-jk")

            # Try link-based extraction if no data-jk
            link = card.locator("a[href*='/viewjob'], a[data-jk], h2 a, .jobTitle a").first
            href = ""
            if await link.count() > 0:
                href = await link.get_attribute("href") or ""
                if not job_id:
                    match = re.search(r"jk=([a-f0-9]+)", href)
                    if match:
                        job_id = match.group(1)

            if not job_id:
                # Try to get any unique identifier
                job_id = await card.get_attribute("id") or ""
                if not job_id:
                    return None

            url = f"{self.base_url}/viewjob?jk={job_id}"

            # Title
            title_el = card.locator(
                ".jobTitle, h2.jobTitle, [class*='jobTitle'] span, "
                "h2 a span, .jcs-JobTitle span"
            ).first
            title = "Unknown"
            if await title_el.count() > 0:
                title = (await title_el.text_content() or "Unknown").strip()

            # Company
            company_el = card.locator(
                "[data-testid='company-name'], .companyName, "
                ".company_location [data-testid='company-name'], "
                "span[class*='company']"
            ).first
            company = "Unknown"
            if await company_el.count() > 0:
                company = (await company_el.text_content() or "Unknown").strip()

            # Location
            location_el = card.locator(
                "[data-testid='text-location'], .companyLocation, "
                "div[class*='location']"
            ).first
            location = ""
            if await location_el.count() > 0:
                location = (await location_el.text_content() or "").strip()

            # Salary (Indeed often shows this)
            salary_el = card.locator(
                "[class*='salary'], [data-testid='attribute_snippet_testid'], "
                ".salary-snippet-container"
            ).first
            salary_min = None
            salary_max = None
            if await salary_el.count() > 0:
                salary_text = (await salary_el.text_content() or "").strip()
                salary_min, salary_max = self._parse_salary(salary_text)

            # Description snippet
            desc_el = card.locator(
                ".job-snippet, [class*='snippet'], "
                "[class*='description'], .underShelfFooter"
            ).first
            description = ""
            if await desc_el.count() > 0:
                description = (await desc_el.text_content() or "").strip()

            # Posted date
            date_el = card.locator(
                ".date, [class*='date'], span[class*='new']"
            ).first
            posted_date = None
            if await date_el.count() > 0:
                date_text = (await date_el.text_content() or "").strip().lower()
                posted_date = self._parse_relative_date(date_text)

            # Remote detection
            remote_type = None
            full_text = (await card.text_content() or "").lower()
            if "remote" in full_text:
                if "hybrid" in full_text:
                    remote_type = "hybrid"
                else:
                    remote_type = "remote"

            return JobListing(
                id=f"indeed:{job_id}",
                external_id=str(job_id),
                source="indeed",
                url=url,
                title=title,
                company=company,
                description=description,
                location=location,
                remote_type=remote_type,
                salary_min=salary_min,
                salary_max=salary_max,
                posted_date=posted_date,
            )
        except Exception:
            return None

    async def get_job_detail(self, job_id: str) -> JobListing | None:
        """Fetch full job details from Indeed."""
        ext_id = job_id.replace("indeed:", "")
        page = await self.context.new_page()

        try:
            await page.goto(
                f"{self.base_url}/viewjob?jk={ext_id}",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            await BrowserManager.human_delay(page, 2000, 4000)

            title_el = page.locator(
                "h1, .jobsearch-JobInfoHeader-title, [class*='JobTitle']"
            ).first
            title = (await title_el.text_content() or "Unknown").strip()

            company_el = page.locator(
                "[data-testid='inlineHeader-companyName'], "
                "[class*='companyName'], .jobsearch-InlineCompanyRating a"
            ).first
            company = "Unknown"
            if await company_el.count() > 0:
                company = (await company_el.text_content() or "Unknown").strip()

            location_el = page.locator(
                "[data-testid='inlineHeader-companyLocation'], "
                "[class*='companyLocation'], .jobsearch-InlineCompanyRating + div"
            ).first
            location = ""
            if await location_el.count() > 0:
                location = (await location_el.text_content() or "").strip()

            desc_el = page.locator(
                "#jobDescriptionText, .jobsearch-jobDescriptionText, "
                "[class*='jobDescription']"
            ).first
            description = ""
            if await desc_el.count() > 0:
                description = (await desc_el.text_content() or "").strip()

            return JobListing(
                id=f"indeed:{ext_id}",
                external_id=ext_id,
                source="indeed",
                url=f"{self.base_url}/viewjob?jk={ext_id}",
                title=title,
                company=company,
                description=description,
                location=location,
            )
        except Exception:
            return None
        finally:
            await page.close()

    async def login(self, username: str, password: str) -> bool:
        """Indeed doesn't require login for searching."""
        return True

    @staticmethod
    def _parse_salary(text: str) -> tuple[int | None, int | None]:
        """Parse salary from text like '$80,000 - $120,000 a year'."""
        amounts = re.findall(r"\$[\d,]+", text)
        if not amounts:
            return None, None

        def to_int(s: str) -> int:
            return int(s.replace("$", "").replace(",", ""))

        # Normalize to annual
        is_hourly = "hour" in text.lower()
        multiplier = 2080 if is_hourly else 1  # ~40hr/week * 52 weeks

        if len(amounts) >= 2:
            return to_int(amounts[0]) * multiplier, to_int(amounts[1]) * multiplier
        elif len(amounts) == 1:
            return to_int(amounts[0]) * multiplier, None
        return None, None

    @staticmethod
    def _parse_relative_date(text: str) -> datetime | None:
        """Parse Indeed relative dates like 'Posted 3 days ago', 'Just posted'."""
        now = datetime.utcnow()
        if "just" in text or "today" in text:
            return now
        match = re.search(r"(\d+)\s*(day|hour|minute)", text)
        if not match:
            return None
        num = int(match.group(1))
        unit = match.group(2)
        deltas = {
            "minute": timedelta(minutes=num),
            "hour": timedelta(hours=num),
            "day": timedelta(days=num),
        }
        return now - deltas.get(unit, timedelta())
