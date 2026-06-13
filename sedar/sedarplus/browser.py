"""Playwright browser session for authorized SEDAR+ access."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from sedar.compliance import AuditLogger, BotChallengeError, RateLimiter, detect_bot_challenge, get_audit_logger
from sedar.config import Settings, get_settings

logger = logging.getLogger(__name__)


class SedarPlusBrowser:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        headless: bool | None = None,
        audit: AuditLogger | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.headless = self.settings.headless if headless is None else headless
        self.audit = audit or get_audit_logger()
        self.rate_limiter = RateLimiter(self.settings.rate_limit_seconds)
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self.page: Page | None = None

    def __enter__(self) -> "SedarPlusBrowser":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def start(self) -> Page:
        self.settings.browser_state_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        self._context = self._browser.new_context(
            accept_downloads=True,
            storage_state=self._storage_state_path() if self._storage_state_path().exists() else None,
        )
        self.page = self._context.new_page()
        return self.page

    def stop(self) -> None:
        if self._context is not None:
            try:
                self._context.storage_state(path=str(self._storage_state_path()))
            except Exception:
                logger.debug("Could not persist browser storage state", exc_info=True)
            self._context.close()
            self._context = None
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
        self.page = None

    def _storage_state_path(self):
        return self.settings.browser_state_dir / "state.json"

    def goto_service(self, service: str, *, wait_until: str = "domcontentloaded") -> Page:
        url = self.settings.service_link(service)
        return self.goto(url, wait_until=wait_until)

    def goto(self, url: str, *, wait_until: str = "domcontentloaded") -> Page:
        if self.page is None:
            raise RuntimeError("Browser not started")
        self.rate_limiter.wait()
        self.audit.log("navigate", url=url)
        response = self.page.goto(url, wait_until=wait_until, timeout=120_000)
        self._check_page(url)
        if response is not None and response.status >= 400:
            logger.warning("HTTP %s for %s", response.status, url)
        return self.page

    def _check_page(self, url: str) -> None:
        if self.page is None:
            return
        try:
            content = self.page.content()
        except Exception as exc:
            raise BotChallengeError(f"Could not read page content for {url}: {exc}") from exc
        detect_bot_challenge(content, url)

    def click_text(self, text: str, *, exact: bool = False) -> None:
        if self.page is None:
            raise RuntimeError("Browser not started")
        self.rate_limiter.wait()
        self.audit.log("click", text=text)
        self.page.get_by_role("button", name=text, exact=exact).click(timeout=30_000)
        self._check_page(self.page.url)

    def fill_label(self, label: str, value: str) -> None:
        if self.page is None:
            raise RuntimeError("Browser not started")
        self.rate_limiter.wait()
        self.audit.log("fill", label=label, value=value)
        self.page.get_by_label(label, exact=False).fill(value, timeout=30_000)

    def wait_for_results(self, timeout_ms: int = 60_000) -> None:
        if self.page is None:
            raise RuntimeError("Browser not started")
        self.page.wait_for_selector("table", timeout=timeout_ms)

    def page_html(self) -> str:
        if self.page is None:
            raise RuntimeError("Browser not started")
        return self.page.content()

    def export_csv_content(self) -> str | None:
        if self.page is None:
            raise RuntimeError("Browser not started")
        export_labels = ("Export", "Export to CSV", "Export CSV", "Download CSV")
        for label in export_labels:
            locator = self.page.get_by_role("button", name=label, exact=False)
            if locator.count() == 0:
                locator = self.page.get_by_role("link", name=label, exact=False)
            if locator.count() == 0:
                continue
            self.rate_limiter.wait()
            self.audit.log("export_csv", label=label)
            with self.page.expect_download(timeout=120_000) as download_info:
                locator.first.click()
            download = download_info.value
            path = download.path()
            if path:
                return path.read_text(encoding="utf-8", errors="replace")
        return None


@contextmanager
def open_browser(
    settings: Settings | None = None,
    *,
    headless: bool | None = None,
) -> Generator[SedarPlusBrowser, None, None]:
    browser = SedarPlusBrowser(settings=settings, headless=headless)
    try:
        browser.start()
        yield browser
    finally:
        browser.stop()
