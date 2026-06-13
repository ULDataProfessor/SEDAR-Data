"""HTML and CSV parsing helpers for SEDAR+ UI exports."""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from lxml import html

DOCUMENT_ID_RE = re.compile(r"id=([a-f0-9]+)", re.I)
PROFILE_ID_RE = re.compile(r"records/profile\.html\?id=([a-f0-9]+)", re.I)


def extract_document_id(url: str) -> str | None:
    if not url:
        return None
    match = DOCUMENT_ID_RE.search(url)
    return match.group(1) if match else None


def extract_profile_id(url: str) -> str | None:
    if not url:
        return None
    match = PROFILE_ID_RE.search(url)
    if match:
        return match.group(1)
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    values = query.get("id")
    return values[0] if values else None


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
                headers = headers[: len(values)]
            elif len(values) > len(headers):
                values = values[: len(headers)]
            record = dict(zip(headers, values))
            links = row.xpath(".//a[@href]")
            if links:
                hrefs = [link.get("href", "") for link in links]
                record["links"] = hrefs
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
        or ""
    )
    document_name = (
        row.get("document_name")
        or row.get("document")
        or row.get("filing_type")
        or row.get("type")
        or ""
    )
    submitted = (
        row.get("submitted_date")
        or row.get("date")
        or row.get("submission_date")
        or ""
    )
    document_id = row.get("document_id") or extract_document_id(row.get("download_url", ""))
    if not document_id:
        document_id = extract_document_id(" ".join(row.get("links", [])))
    return {
        "document_id": document_id or f"unknown-{hash(json.dumps(row, sort_keys=True))}",
        "profile_id": row.get("profile_id") or "",
        "document_name": document_name,
        "submitted_date": submitted,
        "jurisdiction": row.get("jurisdiction", ""),
        "file_size": row.get("file_size") or row.get("size") or "",
        "download_url": row.get("download_url") or "",
        "company_name": profile,
        "raw_json": row.get("raw_json") or json.dumps(row),
    }


def map_company_record(row: dict[str, Any]) -> dict[str, Any]:
    profile_id = row.get("profile_id") or extract_profile_id(row.get("profile_url", ""))
    return {
        "profile_id": profile_id or row.get("profile_number") or row.get("name", "unknown"),
        "profile_number": row.get("profile_number") or row.get("profile_no") or "",
        "legal_name": row.get("legal_name") or row.get("name") or row.get("issuer") or "",
        "jurisdiction": row.get("jurisdiction") or "",
        "status": row.get("status") or "",
        "raw_json": row.get("raw_json") or json.dumps(row),
    }
