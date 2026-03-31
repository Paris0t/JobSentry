"""Playwright browser manager with cookie persistence and auto-login."""

import json
import random
from pathlib import Path

from playwright.async_api import BrowserContext, Page, Playwright, async_playwright


class BrowserManager:
    """Manages Playwright browser lifecycle, cookies, and auto-login."""

    # Login URLs and selectors per site
    LOGIN_CONFIG = {
        "clearancejobs": {
            "login_url": "https://www.clearancejobs.com/login",
            "login_indicators": ["/login", "/sign-in", "/auth"],
            "username_selector": 'input[name="email"], input[type="email"], #email',
            "password_selector": 'input[name="password"], input[type="password"], #password',
            "submit_selector": 'button[type="submit"]',
            "success_indicators": ["/jobs", "/dashboard", "/profile"],
        },
        "linkedin": {
            "login_url": "https://www.linkedin.com/login",
            "login_indicators": ["/login", "/authwall", "/checkpoint"],
            "username_selector": "#username",
            "password_selector": "#password",
            "submit_selector": 'button[type="submit"]',
            "success_indicators": ["/feed", "/mynetwork", "/jobs"],
        },
        "indeed": {
            "login_url": "https://secure.indeed.com/auth",
            "login_indicators": ["/auth", "/login"],
            "username_selector": 'input[name="email"], input[type="email"]',
            "password_selector": 'input[name="password"], input[type="password"]',
            "submit_selector": 'button[type="submit"]',
            "success_indicators": ["/jobs", "/myind"],
        },
    }

    def __init__(self, data_dir: Path, headless: bool = True):
        self.data_dir = data_dir
        self.headless = headless
        self.cookies_dir = data_dir / "cookies"
        self.cookies_dir.mkdir(parents=True, exist_ok=True)
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        return self

    async def __aexit__(self, *args):
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()

    async def get_context(self, site: str | None = None) -> BrowserContext:
        """Get or create a browser context with stealth settings."""
        if self._context:
            return self._context

        browser = await self._playwright.chromium.launch(headless=self.headless)

        self._context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="America/New_York",
        )

        # Mask webdriver detection
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

        # Load cookies if available
        if site:
            await self._load_cookies(site)

        return self._context

    async def save_cookies(self, site: str) -> None:
        """Save current context cookies for a site."""
        if not self._context:
            return
        cookies = await self._context.cookies()
        cookie_file = self.cookies_dir / f"{site}.json"
        cookie_file.write_text(json.dumps(cookies, indent=2))

    async def _load_cookies(self, site: str) -> None:
        """Load saved cookies for a site."""
        cookie_file = self.cookies_dir / f"{site}.json"
        if cookie_file.exists():
            cookies = json.loads(cookie_file.read_text())
            await self._context.add_cookies(cookies)

    def is_login_page(self, site: str, current_url: str) -> bool:
        """Check if the current URL is a login page."""
        config = self.LOGIN_CONFIG.get(site)
        if not config:
            return False
        return any(indicator in current_url for indicator in config["login_indicators"])

    async def auto_login(self, page: Page, site: str) -> bool:
        """Automatically log in using stored credentials. Returns True on success."""
        from jobsentry.config import get_settings
        from jobsentry.models.profile import UserProfile

        settings = get_settings()
        config = self.LOGIN_CONFIG.get(site)
        if not config:
            return False

        # Get credentials
        profile_path = settings.get_profile_path()
        username = None
        password = None

        if profile_path.exists():
            profile = UserProfile.model_validate_json(profile_path.read_text())
            if site == "clearancejobs":
                username = profile.clearancejobs_username
                password = settings.clearancejobs_password
            elif site == "linkedin":
                username = profile.linkedin_username
                password = settings.linkedin_password

        if not username or not password:
            return False

        try:
            # Navigate to login page if not already there
            if not self.is_login_page(site, page.url):
                await page.goto(config["login_url"], wait_until="networkidle", timeout=15000)
                await self.human_delay(page, 1000, 2000)

            # Fill username
            username_field = page.locator(config["username_selector"]).first
            if await username_field.count() == 0:
                return False
            await username_field.fill(username)
            await self.human_delay(page, 300, 800)

            # Fill password
            password_field = page.locator(config["password_selector"]).first
            if await password_field.count() == 0:
                return False
            await password_field.fill(password)
            await self.human_delay(page, 300, 800)

            # Submit
            submit_btn = page.locator(config["submit_selector"]).first
            if await submit_btn.count() > 0:
                await submit_btn.click()

            await page.wait_for_load_state("networkidle", timeout=15000)
            await self.human_delay(page, 1000, 2000)

            # Check if login was successful
            success = any(
                indicator in page.url
                for indicator in config["success_indicators"]
            )

            if success:
                # Save fresh cookies
                await self.save_cookies(site)

            return success
        except Exception:
            return False

    async def ensure_logged_in(self, page: Page, site: str) -> bool:
        """Check if on a login page and auto-login if needed."""
        if self.is_login_page(site, page.url):
            return await self.auto_login(page, site)
        return True

    async def interactive_login(self, url: str, site: str) -> None:
        """Open a headed browser for manual login, then save cookies."""
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        await page.goto(url)

        input(f"\n  Log in to {site} in the browser window, then press Enter here...")

        cookies = await context.cookies()
        cookie_file = self.cookies_dir / f"{site}.json"
        cookie_file.write_text(json.dumps(cookies, indent=2))

        await context.close()
        await browser.close()
        await pw.stop()

    @staticmethod
    async def human_delay(page, min_ms: int = 500, max_ms: int = 2000) -> None:
        """Wait a random human-like delay."""
        await page.wait_for_timeout(random.randint(min_ms, max_ms))
