"""Application configuration via environment variables."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SEDAR_PLUS_SERVICES = {
    "searchIndustryParticipant": ("csa-party", "searchIndustryParticipant", "csa-party"),
    "searchDocuments": ("csa-party", "searchDocuments", "csa-party"),
    "searchReportingIssuers": ("csa-party", "searchReportingIssuers", "csa-party"),
    "searchDisciplinedList": ("csa-order", "searchDisciplinedList", "csa-order"),
    "searchCeaseTradeOrders": ("csa-order", "searchCeaseTradeOrders", "csa-order"),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = Field(default="sqlite:///sedar.db", alias="DATABASE_URL")
    authorization_file: Path = Field(
        default=Path("./docs/authorization.example.txt"),
        alias="SEDAR_AUTHORIZATION_FILE",
    )
    confirm_authorized: bool = Field(default=False, alias="SEDAR_CONFIRM_AUTHORIZED")
    rate_limit_seconds: float = Field(default=4.0, alias="SEDAR_RATE_LIMIT_SECONDS")
    download_dir: Path = Field(default=Path("./filings"), alias="SEDAR_DOWNLOAD_DIR")
    headless: bool = Field(default=True, alias="SEDAR_HEADLESS")
    base_url: str = Field(default="https://www.sedarplus.ca", alias="SEDAR_BASE_URL")
    max_download_batch: int = Field(default=30, alias="SEDAR_MAX_DOWNLOAD_BATCH")
    max_profiles_per_search: int = Field(default=50, alias="SEDAR_MAX_PROFILES_PER_SEARCH")
    locale: str = Field(default="en", alias="SEDAR_LOCALE")
    browser_state_dir: Path = Field(
        default=Path(".sedar/browser_state"),
        alias="SEDAR_BROWSER_STATE_DIR",
    )

    @field_validator("confirm_authorized", mode="before")
    @classmethod
    def parse_confirm_authorized(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @property
    def service_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/csa-party/service/create.html"

    def service_link(self, service: str, *, target_app_code: str | None = None) -> str:
        app_path, service_name, app_code = SEDAR_PLUS_SERVICES.get(
            service,
            ("csa-party", service, target_app_code or "csa-party"),
        )
        return (
            f"{self.base_url.rstrip('/')}/{app_path}/service/create.html"
            f"?_locale={self.locale}&service={service_name}&targetAppCode={app_code}"
        )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    global _settings
    _settings = None
