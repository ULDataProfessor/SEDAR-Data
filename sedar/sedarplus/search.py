"""SEDAR+ document search automation."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sedar.compliance import enforce_profile_limit, require_live_access
from sedar.config import Settings, get_settings
from sedar.sedarplus.browser import SedarPlusBrowser
from sedar.sedarplus.parsers import map_document_record, parse_csv_export, parse_results_table
from sedar.storage.engine import Storage

logger = logging.getLogger(__name__)


def _click_search(browser: SedarPlusBrowser) -> None:
    for label in ("Search", "Apply", "Run search"):
        if browser.page and browser.page.get_by_role("button", name=label, exact=False).count():
            browser.click_text(label)
            return
    raise RuntimeError("Could not find search button on SEDAR+ page")


def _fill_optional_filters(
    browser: SedarPlusBrowser,
    *,
    profile: str | None,
    query: str | None,
    from_date: date | None,
    to_date: date | None,
) -> None:
    if profile:
        for label in ("Profile name or number", "Profile", "Issuer"):
            if browser.page and browser.page.get_by_label(label, exact=False).count():
                browser.fill_label(label, profile)
                break
    if query:
        for label in ("Document name", "Keywords", "Search"):
            if browser.page and browser.page.get_by_label(label, exact=False).count():
                browser.fill_label(label, query)
                break
    if from_date:
        for label in ("From date", "Start date"):
            if browser.page and browser.page.get_by_label(label, exact=False).count():
                browser.fill_label(label, from_date.isoformat())
                break
    if to_date:
        for label in ("To date", "End date"):
            if browser.page and browser.page.get_by_label(label, exact=False).count():
                browser.fill_label(label, to_date.isoformat())
                break


def _collect_page_results(browser: SedarPlusBrowser) -> list[dict[str, Any]]:
    csv_content = browser.export_csv_content()
    if csv_content:
        return parse_csv_export(csv_content)
    return parse_results_table(browser.page_html())


def search_documents(
    *,
    profile: str | None = None,
    query: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    profiles: list[str] | None = None,
    max_pages: int = 1,
    confirm_authorized: bool = False,
    settings: Settings | None = None,
    storage: Storage | None = None,
    browser: SedarPlusBrowser | None = None,
) -> list[dict[str, Any]]:
    cfg = settings or get_settings()
    store = storage or Storage(cfg)
    require_live_access(confirm_authorized=confirm_authorized, settings=cfg)

    profile_list = profiles or ([profile] if profile else [])
    enforce_profile_limit(len(profile_list), cfg.max_profiles_per_search)

    run_id = store.start_sync_run("search_documents")
    collected: list[dict[str, Any]] = []
    errors = ""

    own_browser = browser is None
    active_browser = browser or SedarPlusBrowser(cfg)
    if own_browser:
        active_browser.start()

    try:
        active_browser.goto_service("searchDocuments")
        if profile_list:
            _fill_optional_filters(
                active_browser,
                profile=", ".join(profile_list[: cfg.max_profiles_per_search]),
                query=query,
                from_date=from_date,
                to_date=to_date,
            )
        else:
            _fill_optional_filters(
                active_browser,
                profile=None,
                query=query,
                from_date=from_date,
                to_date=to_date,
            )
        _click_search(active_browser)

        for page_num in range(1, max_pages + 1):
            try:
                active_browser.wait_for_results()
            except Exception:
                logger.debug("Results table not found on page %s", page_num)
            rows = _collect_page_results(active_browser)
            if not rows:
                break
            for row in rows:
                mapped = map_document_record(row)
                store.upsert_filing(mapped)
                collected.append(mapped)
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
        store.finish_sync_run(run_id, len(collected), errors)
        if own_browser:
            active_browser.stop()

    return collected
