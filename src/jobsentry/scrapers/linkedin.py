"""LinkedIn job scraper — requires cookie-based auth via 'jobs login linkedin'."""

import re
from datetime import datetime, timedelta
from urllib.parse import quote_plus

from playwright.async_api import BrowserContext

from jobsentry.automation.browser import BrowserManager
from jobsentry.models.job import JobListing
from jobsentry.scrapers.base import BaseScraper
from jobsentry.scrapers.registry import register


@register("linkedin")
class LinkedInScraper(BaseScraper):
    name = "linkedin"
    base_url = "https://www.linkedin.com"

    def _build_search_url(
        self,
        keywords: list[str],
        location: str | None = None,
        page: int = 0,
    ) -> str:
        query = quote_plus(" ".join(keywords))
        url = f"{self.base_url}/jobs/search/?keywords={query}&f_TPR=r604800"  # past week
        if location:
            url += f"&location={quote_plus(location)}"
        if page > 0:
            url += f"&start={page * 25}"
        return url

    async def search(
        self,
        keywords: list[str],
        location: str | None = None,
        clearance: str | None = None,
        pages: int = 3,
    ) -> list[JobListing]:
        # If clearance filter was specified, add it to keywords for LinkedIn
        if clearance:
            keywords = keywords + [clearance]

        jobs: list[JobListing] = []
        page = await self.context.new_page()

        try:
            for page_num in range(pages):
                url = self._build_search_url(keywords, location, page_num)
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await BrowserManager.human_delay(page, 2000, 4000)

                # Check if we're on a login page
                if "/login" in page.url or "/authwall" in page.url:
                    return jobs  # not logged in, return what we have

                await page.wait_for_load_state("networkidle", timeout=15000)

                page_jobs = await self._extract_jobs_from_page(page)
                if not page_jobs:
                    break
                jobs.extend(page_jobs)

                await BrowserManager.human_delay(page, 2000, 5000)
        finally:
            await page.close()

        return jobs

    async def _extract_jobs_from_page(self, page) -> list[JobListing]:
        """Extract job listings from LinkedIn search results."""
        jobs: list[JobListing] = []

        # LinkedIn job cards in search results
        card_selectors = [
            ".job-search-card",
            ".jobs-search-results__list-item",
            "[data-occludable-job-id]",
            ".scaffold-layout__list-item",
        ]

        cards = None
        for selector in card_selectors:
            cards = page.locator(selector)
            if await cards.count() > 0:
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
        """Parse a single LinkedIn job card."""
        try:
            # Get job ID from data attribute or link
            job_id = await card.get_attribute("data-occludable-job-id")
            if not job_id:
                job_id = await card.get_attribute("data-job-id")

            # Try to extract from link if no data attribute
            link = card.locator("a[href*='/jobs/view/']").first
            href = ""
            if await link.count() > 0:
                href = await link.get_attribute("href") or ""
                if not job_id:
                    match = re.search(r"/jobs/view/(\d+)", href)
                    if match:
                        job_id = match.group(1)

            if not job_id:
                return None

            url = f"{self.base_url}/jobs/view/{job_id}/"

            # Title
            title_el = card.locator(
                ".base-search-card__title, "
                ".job-search-card__title, "
                "[class*='job-title'], "
                "a[class*='title']"
            ).first
            title = "Unknown"
            if await title_el.count() > 0:
                title = (await title_el.text_content() or "Unknown").strip()

            # Company
            company_el = card.locator(
                ".base-search-card__subtitle, "
                "[class*='company'], "
                "[class*='subtitle'] a"
            ).first
            company = "Unknown"
            if await company_el.count() > 0:
                company = (await company_el.text_content() or "Unknown").strip()

            # Location
            location_el = card.locator(
                ".job-search-card__location, "
                "[class*='location']"
            ).first
            location = ""
            if await location_el.count() > 0:
                location = (await location_el.text_content() or "").strip()

            # Posted date
            time_el = card.locator("time, [class*='listed-date'], [class*='posted']").first
            posted_date = None
            if await time_el.count() > 0:
                datetime_attr = await time_el.get_attribute("datetime")
                if datetime_attr:
                    try:
                        posted_date = datetime.fromisoformat(datetime_attr.replace("Z", "+00:00"))
                    except ValueError:
                        pass
                if not posted_date:
                    time_text = (await time_el.text_content() or "").strip().lower()
                    posted_date = self._parse_relative_date(time_text)

            return JobListing(
                id=f"linkedin:{job_id}",
                external_id=str(job_id),
                source="linkedin",
                url=url,
                title=title,
                company=company,
                description="",  # fetched in detail view
                location=location,
                posted_date=posted_date,
            )
        except Exception:
            return None

    async def get_job_detail(self, job_id: str) -> JobListing | None:
        """Fetch full job details from LinkedIn."""
        ext_id = job_id.replace("linkedin:", "")
        page = await self.context.new_page()

        try:
            await page.goto(
                f"{self.base_url}/jobs/view/{ext_id}/",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            await BrowserManager.human_delay(page, 2000, 4000)
            await page.wait_for_load_state("networkidle", timeout=15000)

            # Title
            title_el = page.locator(
                "h1, .top-card-layout__title, [class*='job-title']"
            ).first
            title = (await title_el.text_content() or "Unknown").strip()

            # Company
            company_el = page.locator(
                ".topcard__org-name-link, "
                "[class*='company-name'], "
                "a[class*='topcard__org']"
            ).first
            company = "Unknown"
            if await company_el.count() > 0:
                company = (await company_el.text_content() or "Unknown").strip()

            # Location
            location_el = page.locator(
                ".topcard__flavor--bullet, "
                "[class*='location'], "
                "span[class*='topcard__flavor']"
            ).first
            location = ""
            if await location_el.count() > 0:
                location = (await location_el.text_content() or "").strip()

            # Description
            desc_el = page.locator(
                ".description__text, "
                "[class*='description'], "
                ".show-more-less-html__markup"
            ).first
            description = ""
            if await desc_el.count() > 0:
                description = (await desc_el.text_content() or "").strip()

            # Check for remote/hybrid/onsite
            remote_type = None
            workplace_el = page.locator("[class*='workplace-type']").first
            if await workplace_el.count() > 0:
                workplace_text = (await workplace_el.text_content() or "").strip().lower()
                if "remote" in workplace_text:
                    remote_type = "remote"
                elif "hybrid" in workplace_text:
                    remote_type = "hybrid"
                elif "on-site" in workplace_text or "onsite" in workplace_text:
                    remote_type = "onsite"

            return JobListing(
                id=f"linkedin:{ext_id}",
                external_id=ext_id,
                source="linkedin",
                url=f"{self.base_url}/jobs/view/{ext_id}/",
                title=title,
                company=company,
                description=description,
                location=location,
                remote_type=remote_type,
            )
        except Exception:
            return None
        finally:
            await page.close()

    async def login(self, username: str, password: str) -> bool:
        """Log in to LinkedIn programmatically."""
        page = await self.context.new_page()
        try:
            await page.goto(f"{self.base_url}/login", wait_until="networkidle")
            await BrowserManager.human_delay(page)

            await page.fill("#username", username)
            await BrowserManager.human_delay(page, 300, 800)
            await page.fill("#password", password)
            await BrowserManager.human_delay(page, 300, 800)
            await page.click('button[type="submit"]')

            await page.wait_for_load_state("networkidle", timeout=15000)
            # Check if we made it past login
            return "/feed" in page.url or "/mynetwork" in page.url
        except Exception:
            return False
        finally:
            await page.close()

    @staticmethod
    def _parse_relative_date(text: str) -> datetime | None:
        """Parse LinkedIn relative dates like '3 days ago', '1 week ago'."""
        now = datetime.utcnow()
        match = re.search(r"(\d+)\s+(minute|hour|day|week|month)", text)
        if not match:
            return None
        num = int(match.group(1))
        unit = match.group(2)
        deltas = {
            "minute": timedelta(minutes=num),
            "hour": timedelta(hours=num),
            "day": timedelta(days=num),
            "week": timedelta(weeks=num),
            "month": timedelta(days=num * 30),
        }
        return now - deltas.get(unit, timedelta())
