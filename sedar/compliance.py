"""Compliance gates for authorized SEDAR+ access."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from sedar.config import Settings, get_settings

logger = logging.getLogger("sedar.compliance")

MAX_DOWNLOAD_BATCH = 30
MAX_PROFILES_PER_SEARCH = 50

BOT_CHALLENGE_MARKERS = (
    "radware",
    "captcha",
    "we apologize for the inconvenience",
    "made us think that you are a bot",
    "terms of use violation",
    "blocked activity",
)


class ComplianceError(Exception):
    """Raised when compliance requirements are not met."""


class BotChallengeError(ComplianceError):
    """Raised when SEDAR+ bot protection blocks automation."""


class AuditLogger:
    def __init__(self) -> None:
        self._logger = logging.getLogger("sedar.audit")

    def log(self, event: str, **details: object) -> None:
        parts = [f"{key}={value}" for key, value in details.items()]
        message = f"{event} | " + " ".join(parts) if parts else event
        self._logger.info(message)


_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def _truthy(value: bool | str | int | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def verify_authorization_file(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ComplianceError(
            f"Authorization file not found: {resolved}. "
            "Set SEDAR_AUTHORIZATION_FILE to your written authorization document."
        )
    if not resolved.stat().st_size:
        raise ComplianceError(f"Authorization file is empty: {resolved}")
    return resolved


def require_live_access(
    *,
    confirm_authorized: bool | None = None,
    settings: Settings | None = None,
) -> Path:
    cfg = settings or get_settings()
    authorized = confirm_authorized if confirm_authorized is not None else cfg.confirm_authorized
    if not _truthy(authorized):
        raise ComplianceError(
            "Live SEDAR+ access requires explicit authorization. "
            "Pass --confirm-authorized or set SEDAR_CONFIRM_AUTHORIZED=1."
        )
    auth_path = verify_authorization_file(cfg.authorization_file)
    get_audit_logger().log(
        "authorization_verified",
        path=str(auth_path),
    )
    return auth_path


class RateLimiter:
    def __init__(self, delay_seconds: float) -> None:
        self.delay_seconds = delay_seconds
        self._last_action = 0.0

    def wait(self) -> None:
        if self.delay_seconds <= 0:
            return
        elapsed = time.monotonic() - self._last_action
        remaining = self.delay_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_action = time.monotonic()


def enforce_download_limit(requested: int, max_batch: int = MAX_DOWNLOAD_BATCH) -> int:
    if requested <= 0:
        raise ComplianceError("Download limit must be positive.")
    if requested > max_batch:
        raise ComplianceError(
            f"Requested {requested} documents exceeds SEDAR+ batch limit of {max_batch}."
        )
    return requested


def enforce_profile_limit(count: int, max_profiles: int = MAX_PROFILES_PER_SEARCH) -> None:
    if count > max_profiles:
        raise ComplianceError(
            f"Search includes {count} profiles; SEDAR+ limit is {max_profiles}."
        )


def detect_bot_challenge(page_text: str, url: str = "") -> None:
    lowered = page_text.lower()
    if any(marker in lowered for marker in BOT_CHALLENGE_MARKERS):
        get_audit_logger().log("bot_challenge_detected", url=url)
        raise BotChallengeError(
            "SEDAR+ bot protection detected. Re-run with SEDAR_HEADLESS=false, "
            "complete the CAPTCHA manually in the browser, then retry."
        )
