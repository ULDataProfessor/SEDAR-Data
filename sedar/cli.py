"""Command-line interface for SEDAR+ tools."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from sedar.compliance import ComplianceError, verify_authorization_file
from sedar.config import get_settings
from sedar.legacy.scrape import load_filings as legacy_load_filings
from sedar.sedarplus.download import download_batch
from sedar.sedarplus.issuers import sync_reporting_issuers
from sedar.sedarplus.parsers import map_company_record, map_document_record, parse_csv_export
from sedar.sedarplus.search import search_documents
from sedar.storage.engine import Storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def _common_options(func):
    func = click.option(
        "--confirm-authorized",
        is_flag=True,
        help="Confirm written authorization for live SEDAR+ access.",
    )(func)
    return func


@click.group()
@click.version_option(package_name="sedar")
def main() -> None:
    """Authorized SEDAR+ filing collection."""


@main.command("check-auth")
def check_auth() -> None:
    """Verify authorization file and database connectivity."""
    settings = get_settings()
    try:
        auth_path = verify_authorization_file(settings.authorization_file)
        click.echo(f"Authorization file OK: {auth_path}")
    except ComplianceError as exc:
        click.echo(f"Authorization check failed: {exc}", err=True)
        sys.exit(1)

    storage = Storage(settings)
    try:
        storage.ping()
        click.echo(f"Database OK: {settings.database_url}")
    except Exception as exc:
        click.echo(f"Database check failed: {exc}", err=True)
        sys.exit(1)


@main.command("sync-issuers")
@_common_options
@click.option("--max-pages", default=50, show_default=True, type=int)
def sync_issuers_cmd(confirm_authorized: bool, max_pages: int) -> None:
    """Sync reporting issuers from SEDAR+."""
    try:
        rows = sync_reporting_issuers(
            max_pages=max_pages,
            confirm_authorized=confirm_authorized,
        )
        click.echo(f"Synced {len(rows)} issuers")
    except ComplianceError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)


@main.command("search-docs")
@_common_options
@click.option("--profile", default=None, help="Profile name or number.")
@click.option("--query", default=None, help="Document keyword query.")
@click.option("--from-date", default=None, type=click.DateTime(formats=["%Y-%m-%d"]))
@click.option("--to-date", default=None, type=click.DateTime(formats=["%Y-%m-%d"]))
@click.option("--max-pages", default=1, show_default=True, type=int)
def search_docs_cmd(
    confirm_authorized: bool,
    profile: str | None,
    query: str | None,
    from_date,
    to_date,
    max_pages: int,
) -> None:
    """Search SEDAR+ documents and store metadata."""
    try:
        rows = search_documents(
            profile=profile,
            query=query,
            from_date=from_date.date() if from_date else None,
            to_date=to_date.date() if to_date else None,
            max_pages=max_pages,
            confirm_authorized=confirm_authorized,
        )
        click.echo(f"Stored {len(rows)} document records")
    except ComplianceError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)


@main.command("download")
@_common_options
@click.option("--limit", default=None, type=int, help="Documents to download (max 30).")
def download_cmd(confirm_authorized: bool, limit: int | None) -> None:
    """Download pending filings from SEDAR+."""
    try:
        rows = download_batch(
            limit=limit,
            confirm_authorized=confirm_authorized,
        )
        click.echo(f"Downloaded {len(rows)} documents")
    except ComplianceError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)


@main.command("import-csv")
@click.argument("csv_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--kind",
    type=click.Choice(["documents", "issuers"], case_sensitive=False),
    default="documents",
    show_default=True,
)
def import_csv_cmd(csv_path: Path, kind: str) -> None:
    """Import a manual SEDAR+ CSV export into the database."""
    content = csv_path.read_text(encoding="utf-8", errors="replace")
    rows = parse_csv_export(content)
    storage = Storage()
    count = 0
    for row in rows:
        if kind == "issuers":
            storage.upsert_company(map_company_record(row))
        else:
            storage.upsert_filing(map_document_record(row))
        count += 1
    click.echo(f"Imported {count} {kind} rows from {csv_path}")


@main.command("legacy-scrape")
@click.option(
    "--i-know-this-is-legacy",
    is_flag=True,
    help="Acknowledge this targets deprecated legacy sedar.com endpoints.",
)
def legacy_scrape_cmd(i_know_this_is_legacy: bool) -> None:
    """Run the historical legacy SEDAR scraper (deprecated)."""
    if not i_know_this_is_legacy:
        click.echo(
            "Refusing to run legacy scraper without --i-know-this-is-legacy.",
            err=True,
        )
        sys.exit(1)
    click.echo("WARNING: legacy scraper targets pre-SEDAR+ endpoints and may not work.")
    legacy_load_filings()


if __name__ == "__main__":
    main()
