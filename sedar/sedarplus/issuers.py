"""Reporting issuers list sync."""

from __future__ import annotations

import logging
from typing import Any

from sedar.compliance import require_live_access
from sedar.config import Settings, get_settings
from sedar.sedarplus.browser import SedarPlusBrowser
from sedar.sedarplus.parsers import map_company_record, parse_csv_export, parse_results_table
from sedar.storage.engine import Storage

logger = logging.getLogger(__name__)


def _click_search(browser: SedarPlusBrowser) -> None:
    for label in ("Search", "Apply", "Run search"):
        if browser.page and browser.page.get_by_role("button", name=label, exact=False).count():
            browser.click_text(label)
            return


def sync_reporting_issuers(
    *,
    max_pages: int = 50,
    confirm_authorized: bool = False,
    settings: Settings | None = None,
    storage: Storage | None = None,
    browser: SedarPlusBrowser | None = None,
) -> list[dict[str, Any]]:
    cfg = settings or get_settings()
    store = storage or Storage(cfg)
    require_live_access(confirm_authorized=confirm_authorized, settings=cfg)

    run_id = store.start_sync_run("sync_issuers")
    synced: list[dict[str, Any]] = []
    errors = ""

    own_browser = browser is None
    active_browser = browser or SedarPlusBrowser(cfg)
    if own_browser:
        active_browser.start()

    try:
        active_browser.goto_service("searchReportingIssuers")
        _click_search(active_browser)

        for page_num in range(1, max_pages + 1):
            try:
                active_browser.wait_for_results()
            except Exception:
                logger.debug("Issuer results table not found on page %s", page_num)

            csv_content = active_browser.export_csv_content()
            rows = parse_csv_export(csv_content) if csv_content else parse_results_table(
                active_browser.page_html()
            )
            if not rows:
                break

            for row in rows:
                mapped = map_company_record(row)
                store.upsert_company(mapped)
                synced.append(mapped)

            if page_num >= max_pages:
                break
            if active_browser.page is None:
                break
            next_button = active_browser.page.get_by_role("button", name="Next", exact=False)
            if next_button.count() == 0:
                break
            active_browser.rate_limiter.wait()
            next_button.first.click()
            active_browser._check_page(active_browser.page.url)
    except Exception as exc:
        errors = str(exc)
        raise
    finally:
        store.finish_sync_run(run_id, len(synced), errors)
        if own_browser:
            active_browser.stop()

    return synced
