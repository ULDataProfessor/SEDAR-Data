"""HTML and CSV parsing helpers for SEDAR+ UI exports."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from lxml import html

DOCUMENT_ID_RE = re.compile(r"document(?:\.html)?(?:\?id=|/)([a-z0-9_-]+)", re.I)
PROFILE_ID_RE = re.compile(r"profile(?:\.html)?(?:\?id=|/)([a-z0-9_-]+)", re.I)


def _stable_unknown_id(prefix: str, row: dict[str, Any]) -> str:
    payload = json.dumps(row, sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def extract_document_id(url: str) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    if "document" in parsed.path.lower():
        values = parse_qs(parsed.query).get("id")
        if values:
            return values[0]
    match = DOCUMENT_ID_RE.search(url)
    return match.group(1) if match else None


def extract_profile_id(url: str) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    if "profile" in parsed.path.lower():
        values = parse_qs(parsed.query).get("id")
        if values:
            return values[0]
    match = PROFILE_ID_RE.search(url)
    return match.group(1) if match else None


def normalize_header(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def parse_results_table(page_html: str) -> list[dict[str, Any]]:
    doc = html.fromstring(page_html)
    tables = doc.xpath("//table")
    rows_out: list[dict[str, Any]] = []

    for table in tables:
        header_cells = table.xpath(".//thead//th | .//tr[1]/th")
        if not header_cells:
            first_row = table.xpath(".//tr[1]")
            if not first_row:
                continue
            header_cells = first_row[0].xpath("./td")
        headers = [normalize_header(cell.text_content()) for cell in header_cells]
        if not headers or sum(1 for h in headers if h) < 2:
            continue

        body_rows = table.xpath(".//tbody/tr") or table.xpath(".//tr[position()>1]")
        for row in body_rows:
            cells = row.xpath("./td")
            if len(cells) < 2:
                continue
            values = [cell.text_content().strip() for cell in cells]
            if len(values) < len(headers):
                row_headers = headers[: len(values)]
            elif len(values) > len(headers):
                values = values[: len(headers)]
                row_headers = headers
            else:
                row_headers = headers
            record = dict(zip(row_headers, values))
            links = row.xpath(".//a[@href]")
            if links:
                hrefs = [link.get("href", "") for link in links]
                texts = [link.text_content().strip() for link in links]
                record["links"] = hrefs
                record["link_texts"] = texts
                for href in hrefs:
                    doc_id = extract_document_id(href)
                    if doc_id:
                        record["document_id"] = doc_id
                        record["download_url"] = href
                    profile_id = extract_profile_id(href)
                    if profile_id:
                        record["profile_id"] = profile_id
            if any(record.values()):
                record["raw_json"] = json.dumps(record)
                rows_out.append(record)
        if rows_out:
            break
    return rows_out


def parse_csv_export(content: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(content))
    rows: list[dict[str, Any]] = []
    for row in reader:
        cleaned = {normalize_header(k): (v or "").strip() for k, v in row.items() if k}
        if not cleaned:
            continue
        for key, value in list(cleaned.items()):
            if "url" in key or "link" in key:
                doc_id = extract_document_id(value)
                if doc_id:
                    cleaned["document_id"] = doc_id
                    cleaned["download_url"] = value
                profile_id = extract_profile_id(value)
                if profile_id:
                    cleaned["profile_id"] = profile_id
        cleaned["raw_json"] = json.dumps(cleaned)
        rows.append(cleaned)
    return rows


def map_document_record(row: dict[str, Any]) -> dict[str, Any]:
    profile = (
        row.get("profile")
        or row.get("issuer")
        or row.get("company")
        or row.get("profile_name")
        or row.get("profile_name_or_number")
        or ""
    )
    document_name = (
        row.get("document_type")
        or row.get("document_name")
        or row.get("document")
        or row.get("filing_type")
        or row.get("type")
        or ""
    )
    submitted = (
        row.get("submitted_date")
        or row.get("date_submitted")
        or row.get("filed_date")
        or row.get("date_filed")
        or row.get("date")
        or row.get("submission_date")
        or ""
    )
    download_url = (
        row.get("download_url")
        or row.get("generated_url")
        or row.get("document_url")
        or row.get("url")
        or row.get("link")
        or ""
    )
    document_id = row.get("document_id") or extract_document_id(download_url)
    if not document_id:
        document_id = extract_document_id(" ".join(row.get("links", [])))
    return {
        "document_id": document_id or _stable_unknown_id("unknown-document", row),
        "profile_id": row.get("profile_id") or "",
        "document_name": document_name,
        "submitted_date": submitted,
        "jurisdiction": row.get("jurisdiction", ""),
        "file_size": row.get("file_size") or row.get("size") or "",
        "download_url": download_url,
        "company_name": profile,
        "raw_json": row.get("raw_json") or json.dumps(row),
    }


def map_company_record(row: dict[str, Any]) -> dict[str, Any]:
    profile_url = (
        row.get("profile_url")
        or row.get("url")
        or row.get("link")
        or " ".join(row.get("links", []))
    )
    profile_number = row.get("profile_number") or row.get("profile_no") or row.get("number") or ""
    profile_id = row.get("profile_id") or extract_profile_id(profile_url)
    jurisdiction = (
        row.get("principal_jurisdiction")
        or row.get("jurisdiction")
        or row.get("reporting_jurisdiction")
        or ""
    )
    return {
        "profile_id": profile_id or profile_number or _stable_unknown_id("unknown-profile", row),
        "profile_number": profile_number,
        "legal_name": (
            row.get("legal_name")
            or row.get("profile_name")
            or row.get("name")
            or row.get("issuer")
            or ""
        ),
        "jurisdiction": jurisdiction,
        "principal_jurisdiction": row.get("principal_jurisdiction") or "",
        "reporting_jurisdictions": (
            row.get("reporting_jurisdictions_determined_by_regulator")
            or row.get("reporting_jurisdictions")
            or ""
        ),
        "profile_type": row.get("profile_type") or row.get("type") or "",
        "status": row.get("status") or "",
        "in_default": row.get("in_default") or "",
        "active_cease_trade_order": (
            row.get("active_cease_trade_order_ban_trading_by_ban_trading_of")
            or row.get("active_cease_trade_order")
            or ""
        ),
        "raw_json": row.get("raw_json") or json.dumps(row),
    }
