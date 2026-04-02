"""ClearanceJobs.com scraper."""

import re
from datetime import datetime
from urllib.parse import quote_plus

from jobsentry.automation.browser import BrowserManager
from jobsentry.models.job import JobListing
from jobsentry.scrapers.base import BaseScraper
from jobsentry.scrapers.registry import register


@register("clearancejobs")
class ClearanceJobsScraper(BaseScraper):
    name = "clearancejobs"
    base_url = "https://www.clearancejobs.com"

    def _build_search_url(
        self,
        keywords: list[str],
        location: str | None = None,
        clearance: str | None = None,
        page: int = 1,
    ) -> str:
        query = quote_plus(" ".join(keywords))
        url = f"{self.base_url}/jobs?keywords={query}"
        if location:
            url += f"&location={quote_plus(location)}"
        if clearance:
            url += f"&clearance={quote_plus(clearance)}"
        if page > 1:
            url += f"&page={page}"
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
            for page_num in range(1, pages + 1):
                url = self._build_search_url(keywords, location, clearance, page_num)
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await BrowserManager.human_delay(page)

                # Auto-login if redirected to login page
                from jobsentry.config import get_settings as _gs

                bm = BrowserManager(data_dir=_gs().data_dir, headless=True)
                if bm.is_login_page("clearancejobs", page.url):
                    await bm.auto_login(page, "clearancejobs")
                    # Retry the search URL after login
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                    await BrowserManager.human_delay(page)

                page_jobs = await self._extract_jobs_from_page(page)
                if not page_jobs:
                    break
                jobs.extend(page_jobs)

                # Check for next page
                has_next = await page.locator(
                    'button[aria-label="Next page"], '
                    'a[aria-label="Next page"], '
                    ".el-pagination .btn-next:not([disabled])"
                ).count()
                if not has_next:
                    break

                await BrowserManager.human_delay(page, 1000, 3000)
        finally:
            await page.close()

        return jobs

    async def _extract_jobs_from_page(self, page) -> list[JobListing]:
        """Extract job listings from search results page."""
        jobs: list[JobListing] = []

        # ClearanceJobs uses .job-search-list-item-desktop for each card
        cards = page.locator(".job-search-list-item-desktop")
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
        """Parse a job listing from a ClearanceJobs card."""
        try:
            # Job link — contains /jobs/{id}/{slug}
            link = card.locator("a[href*='/jobs/']").first
            if await link.count() == 0:
                return None
            href = await link.get_attribute("href")
            if not href:
                return None

            # Extract numeric ID from URL like /jobs/8265505/information-security-analyst
            match = re.search(r"/jobs/(\d+)", href)
            if not match:
                return None
            ext_id = match.group(1)
            url = href if href.startswith("http") else f"{self.base_url}{href}"

            # Title: .job-search-list-item-desktop__job-name
            title_el = card.locator(".job-search-list-item-desktop__job-name").first
            title = "Unknown"
            if await title_el.count() > 0:
                title = (await title_el.text_content() or "Unknown").strip()

            # Company: .job-search-list-item-desktop__company-name
            company_el = card.locator(".job-search-list-item-desktop__company-name").first
            company = "Unknown"
            if await company_el.count() > 0:
                company = (await company_el.text_content() or "Unknown").strip()

            # Description snippet: .job-search-list-item-desktop__description
            desc_el = card.locator(".job-search-list-item-desktop__description").first
            description = ""
            if await desc_el.count() > 0:
                description = (await desc_el.text_content() or "").strip()

            # Location: .job-search-list-item-desktop__location
            location_el = card.locator(".job-search-list-item-desktop__location").first
            location = ""
            if await location_el.count() > 0:
                location = (await location_el.text_content() or "").strip()

            # Clearance level — look in footer/group area
            clearance = None
            clearance_el = card.locator("[class*='clearance'], [class*='Clearance']").first
            if await clearance_el.count() > 0:
                clearance = (await clearance_el.text_content() or "").strip()

            # Check for any tags/badges in the footer
            footer_el = card.locator(".job-search-list-item-desktop__footer").first
            footer_text = ""
            if await footer_el.count() > 0:
                footer_text = (await footer_el.text_content() or "").strip()

            # Try to extract clearance from footer text if not found
            if not clearance and footer_text:
                for level in ["TS/SCI", "Top Secret/SCI", "Top Secret", "Secret", "Public Trust"]:
                    if level.lower() in footer_text.lower():
                        clearance = level
                        break

            return JobListing(
                id=f"clearancejobs:{ext_id}",
                external_id=ext_id,
                source="clearancejobs",
                url=url,
                title=title,
                company=company,
                description=description,
                location=location,
                clearance_required=clearance,
            )
        except Exception:
            return None

    async def get_job_detail(self, job_id: str) -> JobListing | None:
        """Fetch full details for a single job."""
        ext_id = job_id.replace("clearancejobs:", "")
        page = await self.context.new_page()
        try:
            await page.goto(
                f"{self.base_url}/jobs/{ext_id}", wait_until="networkidle", timeout=30000
            )
            await BrowserManager.human_delay(page)

            title_el = page.locator("h1").first
            title = (
                (await title_el.text_content() or "Unknown").strip()
                if await title_el.count()
                else "Unknown"
            )

            company_el = page.locator(
                ".job-search-list-item-desktop__company-name, "
                "[class*='company-name'], [class*='employer']"
            ).first
            company = "Unknown"
            if await company_el.count() > 0:
                company = (await company_el.text_content() or "Unknown").strip()

            desc_el = page.locator(
                ".job-search-list-item-desktop__description, "
                "[class*='description'], [class*='job-detail']"
            ).first
            description = ""
            if await desc_el.count() > 0:
                description = (await desc_el.text_content() or "").strip()

            location_el = page.locator(
                ".job-search-list-item-desktop__location, [class*='location']"
            ).first
            location = ""
            if await location_el.count() > 0:
                location = (await location_el.text_content() or "").strip()

            return JobListing(
                id=f"clearancejobs:{ext_id}",
                external_id=ext_id,
                source="clearancejobs",
                url=f"{self.base_url}/jobs/{ext_id}",
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
        """Log in to ClearanceJobs."""
        page = await self.context.new_page()
        try:
            await page.goto(f"{self.base_url}/login", wait_until="networkidle")
            await BrowserManager.human_delay(page)

            await page.fill('input[name="email"], input[type="email"]', username)
            await BrowserManager.human_delay(page, 300, 800)
            await page.fill('input[name="password"], input[type="password"]', password)
            await BrowserManager.human_delay(page, 300, 800)
            await page.click('button[type="submit"]')

            await page.wait_for_load_state("networkidle", timeout=15000)
            is_logged_in = await page.locator('[class*="avatar"], [class*="profile"]').count() > 0
            return is_logged_in
        except Exception:
            return False
        finally:
            await page.close()

    @staticmethod
    def _parse_date(val) -> datetime | None:
        if not val:
            return None
        if isinstance(val, datetime):
            return val
        try:
            return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
