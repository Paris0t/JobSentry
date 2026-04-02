"""Auto-apply to jobs via Easy Apply where available.

Currently supports:
- Indeed "Easy Apply" (one-click applications with stored resume)

This is experimental. Use at your own risk — review the jobs before enabling auto-apply.
"""

import asyncio

from playwright.async_api import BrowserContext, Page

from jobsentry.automation.browser import BrowserManager
from jobsentry.config import get_settings
from jobsentry.models.job import JobListing
from jobsentry.models.profile import UserProfile


class AutoApplier:
    """Handles automated job applications via Easy Apply buttons."""

    def __init__(self, context: BrowserContext, profile: UserProfile):
        self.context = context
        self.profile = profile

    async def apply_indeed(self, job: JobListing) -> dict:
        """Attempt to apply via Indeed Easy Apply.

        Returns dict with keys: success (bool), method (str), error (str|None)
        """
        page = await self.context.new_page()
        result = {"success": False, "method": "indeed_easy_apply", "error": None}

        try:
            ext_id = job.external_id
            await page.goto(
                f"https://www.indeed.com/viewjob?jk={ext_id}",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            await BrowserManager.human_delay(page, 2000, 4000)

            # Look for "Apply now" or "Easy Apply" button
            apply_btn = page.locator(
                "button:has-text('Apply now'), "
                "button:has-text('Easy Apply'), "
                "[class*='apply'] button, "
                "#indeedApplyButton"
            ).first

            if await apply_btn.count() == 0:
                result["error"] = "No Easy Apply button found — may require external application"
                return result

            # Check if it's an external apply (opens new tab)
            btn_text = (await apply_btn.text_content() or "").lower()
            if "external" in btn_text or "company site" in btn_text:
                result["error"] = "External application — requires manual apply on company site"
                return result

            await apply_btn.click()
            await BrowserManager.human_delay(page, 2000, 3000)

            # Handle the Indeed apply flow — fill fields if prompted
            applied = await self._handle_indeed_apply_flow(page)

            if applied:
                result["success"] = True
            else:
                result["error"] = "Apply flow incomplete — may need manual review"

        except Exception as e:
            result["error"] = str(e)[:200]
        finally:
            await page.close()

        return result

    async def _handle_indeed_apply_flow(self, page: Page) -> bool:
        """Walk through Indeed's multi-step apply form.

        Returns True if application was submitted successfully.
        """
        max_steps = 5
        for _ in range(max_steps):
            await BrowserManager.human_delay(page, 1000, 2000)

            # Check for success/confirmation
            confirmation = page.locator(
                "[class*='ia-PostApply'], "
                ":has-text('Application submitted'), "
                ":has-text('application has been sent'), "
                "[class*='applied-confirmation']"
            ).first
            if await confirmation.count() > 0:
                return True

            # Fill name fields if empty
            for selector, value in [
                (
                    'input[name*="name"][name*="first"], input[id*="firstName"]',
                    self.profile.full_name.split()[0] if self.profile.full_name else "",
                ),
                (
                    'input[name*="name"][name*="last"], input[id*="lastName"]',
                    self.profile.full_name.split()[-1] if self.profile.full_name else "",
                ),
                ('input[name*="email"], input[type="email"]', self.profile.email),
                ('input[name*="phone"], input[type="tel"]', self.profile.phone),
            ]:
                if not value:
                    continue
                field = page.locator(selector).first
                if await field.count() > 0:
                    current = await field.input_value()
                    if not current:
                        await field.fill(value)
                        await BrowserManager.human_delay(page, 200, 500)

            # Look for continue/submit/next button
            next_btn = page.locator(
                "button:has-text('Continue'), "
                "button:has-text('Submit'), "
                "button:has-text('Apply'), "
                "button:has-text('Next'), "
                "[class*='ia-continueButton']"
            ).first

            if await next_btn.count() > 0:
                await next_btn.click()
                await BrowserManager.human_delay(page, 2000, 3000)
            else:
                break

        # Final check for success
        await BrowserManager.human_delay(page, 2000, 3000)
        success_el = page.locator(
            "[class*='ia-PostApply'], "
            ":has-text('Application submitted'), "
            ":has-text('application has been sent')"
        ).first
        return await success_el.count() > 0

    async def apply_linkedin_easy(self, job: JobListing) -> dict:
        """Attempt LinkedIn Easy Apply.

        Returns dict with keys: success (bool), method (str), error (str|None)
        """
        page = await self.context.new_page()
        result = {"success": False, "method": "linkedin_easy_apply", "error": None}

        try:
            ext_id = job.external_id
            await page.goto(
                f"https://www.linkedin.com/jobs/view/{ext_id}/",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            await BrowserManager.human_delay(page, 2000, 4000)

            # Check for login wall
            if "/login" in page.url or "/authwall" in page.url:
                result["error"] = "Not logged in to LinkedIn"
                return result

            # Look for Easy Apply button specifically
            easy_apply = page.locator(
                "button:has-text('Easy Apply'), [class*='jobs-apply-button']:has-text('Easy Apply')"
            ).first

            if await easy_apply.count() == 0:
                result["error"] = "No Easy Apply — requires application on company site"
                return result

            await easy_apply.click()
            await BrowserManager.human_delay(page, 2000, 3000)

            # Handle the multi-step Easy Apply modal
            applied = await self._handle_linkedin_apply_flow(page)

            if applied:
                result["success"] = True
            else:
                result["error"] = "Apply flow incomplete — may need manual review"

        except Exception as e:
            result["error"] = str(e)[:200]
        finally:
            await page.close()

        return result

    async def _handle_linkedin_apply_flow(self, page: Page) -> bool:
        """Walk through LinkedIn's Easy Apply modal.

        Returns True if application was submitted.
        """
        max_steps = 6
        for _ in range(max_steps):
            await BrowserManager.human_delay(page, 1500, 2500)

            # Check for success
            success = page.locator(
                "[class*='post-apply'], "
                ":has-text('Application sent'), "
                "[class*='artdeco-inline-feedback--success']"
            ).first
            if await success.count() > 0:
                return True

            # Fill contact fields if empty
            for selector, value in [
                ('input[name*="email"], input[id*="email"]', self.profile.email),
                ('input[name*="phone"], input[id*="phone"]', self.profile.phone),
            ]:
                if not value:
                    continue
                field = page.locator(selector).first
                if await field.count() > 0:
                    current = await field.input_value()
                    if not current:
                        await field.fill(value)
                        await BrowserManager.human_delay(page, 200, 500)

            # Click Next/Review/Submit
            submit = page.locator(
                "button:has-text('Submit application'), "
                "button:has-text('Submit'), "
                "[aria-label='Submit application']"
            ).first
            if await submit.count() > 0:
                await submit.click()
                await BrowserManager.human_delay(page, 3000, 5000)
                continue

            next_btn = page.locator(
                "button:has-text('Next'), "
                "button:has-text('Review'), "
                "button:has-text('Continue'), "
                "[aria-label='Continue to next step']"
            ).first
            if await next_btn.count() > 0:
                await next_btn.click()
                await BrowserManager.human_delay(page, 1500, 2500)
            else:
                break

        # Final check
        await BrowserManager.human_delay(page, 2000, 3000)
        success_el = page.locator("[class*='post-apply'], :has-text('Application sent')").first
        return await success_el.count() > 0


async def auto_apply_jobs(
    jobs: list[JobListing],
    profile: UserProfile,
    headless: bool = True,
) -> list[dict]:
    """Apply to a list of jobs automatically.

    Returns list of result dicts: {job_id, title, company, success, method, error}
    """
    settings = get_settings()
    results = []

    async with BrowserManager(settings.data_dir, headless=headless) as bm:
        for job in jobs:
            context = await bm.get_context(site=job.source)
            applier = AutoApplier(context, profile)

            if job.source == "indeed":
                result = await applier.apply_indeed(job)
            elif job.source == "linkedin":
                result = await applier.apply_linkedin_easy(job)
            else:
                result = {
                    "success": False,
                    "method": "unsupported",
                    "error": f"Auto-apply not supported for {job.source}",
                }

            results.append(
                {
                    "job_id": job.id,
                    "title": job.title,
                    "company": job.company,
                    **result,
                }
            )

            # Don't spam — human-like delay between applications
            if job != jobs[-1]:
                await asyncio.sleep(5)

    return results
