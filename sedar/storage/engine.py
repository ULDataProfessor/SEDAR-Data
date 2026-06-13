"""Database engine wrapper using dataset."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import dataset

from sedar.config import Settings, get_settings
from sedar.storage.schema import (
    COMPANY_KEYS,
    COMPANY_TABLE,
    FILING_KEYS,
    FILING_TABLE,
    SYNC_RUN_TABLE,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Storage:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.engine = dataset.connect(self.settings.database_url)
        self.company = self.engine[COMPANY_TABLE]
        self.filing = self.engine[FILING_TABLE]
        self.sync_run = self.engine[SYNC_RUN_TABLE]

    def ping(self) -> bool:
        self.engine.tables
        return True

    def upsert_company(self, data: dict[str, Any]) -> None:
        payload = dict(data)
        if "raw_json" in payload and not isinstance(payload["raw_json"], str):
            payload["raw_json"] = json.dumps(payload["raw_json"])
        self.company.upsert(payload, COMPANY_KEYS)

    def upsert_filing(self, data: dict[str, Any]) -> None:
        payload = dict(data)
        if "raw_json" in payload and not isinstance(payload["raw_json"], str):
            payload["raw_json"] = json.dumps(payload["raw_json"])
        self.filing.upsert(payload, FILING_KEYS)

    def find_filing(self, document_id: str) -> dict[str, Any] | None:
        return self.filing.find_one(document_id=document_id)

    def filings_pending_download(self, limit: int = 30) -> list[dict[str, Any]]:
        rows = list(
            self.filing.find(local_path=None, _limit=limit, order_by="-submitted_date")
        )
        if rows:
            return rows
        return list(
            self.filing.find(local_path="", _limit=limit, order_by="-submitted_date")
        )

    def start_sync_run(self, mode: str) -> int:
        row = {
            "started_at": _utcnow().isoformat(),
            "mode": mode,
            "records_fetched": 0,
            "errors": "",
        }
        self.sync_run.insert(row)
        return int(row["id"])

    def finish_sync_run(
        self,
        run_id: int,
        records_fetched: int,
        errors: str = "",
    ) -> None:
        self.sync_run.update(
            {
                "id": run_id,
                "finished_at": _utcnow().isoformat(),
                "records_fetched": records_fetched,
                "errors": errors,
            },
            ["id"],
        )
