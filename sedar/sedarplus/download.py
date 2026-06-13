"""SEDAR+ document download automation."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from sedar.compliance import enforce_download_limit, require_live_access
from sedar.config import Settings, get_settings
from sedar.sedarplus.browser import SedarPlusBrowser
from sedar.storage.engine import Storage

logger = logging.getLogger(__name__)


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _target_path(settings: Settings, filing: dict[str, Any], filename: str) -> Path:
    profile_id = filing.get("profile_id") or "unknown"
    document_id = filing.get("document_id") or "unknown"
    return settings.download_dir / profile_id / document_id / filename


def download_batch(
    *,
    limit: int | None = None,
    confirm_authorized: bool = False,
    settings: Settings | None = None,
    storage: Storage | None = None,
    browser: SedarPlusBrowser | None = None,
) -> list[dict[str, Any]]:
    cfg = settings or get_settings()
    store = storage or Storage(cfg)
    require_live_access(confirm_authorized=confirm_authorized, settings=cfg)

    batch_size = enforce_download_limit(limit or cfg.max_download_batch, cfg.max_download_batch)
    pending = store.filings_pending_download(batch_size)
    if not pending:
        logger.info("No filings pending download")
        return []

    run_id = store.start_sync_run("download_batch")
    downloaded: list[dict[str, Any]] = []
    errors = ""

    own_browser = browser is None
    active_browser = browser or SedarPlusBrowser(cfg)
    if own_browser:
        active_browser.start()

    try:
        cfg.download_dir.mkdir(parents=True, exist_ok=True)
        for filing in pending[:batch_size]:
            url = filing.get("download_url")
            if not url:
                doc_id = filing.get("document_id")
                logger.warning("Skipping filing without download_url: %s", doc_id)
                continue
            if not url.startswith("http"):
                url = f"{cfg.base_url.rstrip('/')}/{url.lstrip('/')}"

            active_browser.goto(url)
            if active_browser.page is None:
                continue

            filename = filing.get("document_name") or f"{filing.get('document_id')}.pdf"
            filename = filename.replace("/", "-")
            if not filename.lower().endswith(".pdf"):
                filename = f"{filename}.pdf"
            target = _target_path(cfg, filing, filename)

            if target.exists():
                filing["local_path"] = str(target)
                filing["checksum"] = _checksum(target)
                store.upsert_filing(filing)
                downloaded.append(filing)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            saved = False

            download_link = active_browser.page.get_by_role("link", name="Download", exact=False)
            if download_link.count():
                with active_browser.page.expect_download(timeout=120_000) as download_info:
                    active_browser.rate_limiter.wait()
                    download_link.first.click()
                download = download_info.value
                download.save_as(str(target))
                saved = True
            else:
                # Some document pages expose a direct PDF viewer; persist rendered content.
                pdf_link = active_browser.page.locator(
                    "a[href*='.pdf'], embed[type='application/pdf']"
                )
                if pdf_link.count():
                    href = pdf_link.first.get_attribute("href")
                    if href:
                        if not href.startswith("http"):
                            href = f"{cfg.base_url}{href}"
                        active_browser.goto(href)
                        with active_browser.page.expect_download(timeout=120_000) as download_info:
                            active_browser.page.keyboard.press("Control+S")
                        download = download_info.value
                        download.save_as(str(target))
                        saved = True

            if saved and target.exists():
                filing["local_path"] = str(target)
                filing["checksum"] = _checksum(target)
                store.upsert_filing(filing)
                downloaded.append(filing)
                active_browser.audit.log(
                    "document_downloaded",
                    document_id=filing.get("document_id"),
                    path=str(target),
                )
    except Exception as exc:
        errors = str(exc)
        raise
    finally:
        store.finish_sync_run(run_id, len(downloaded), errors)
        if own_browser:
            active_browser.stop()

    return downloaded
