from pathlib import Path

import pytest

from sedar.compliance import (
    BotChallengeError,
    ComplianceError,
    SEDARUnavailableError,
    detect_bot_challenge,
    detect_unavailable,
    enforce_download_limit,
    enforce_profile_limit,
    require_live_access,
    verify_authorization_file,
)
from sedar.config import Settings, reset_settings
from sedar.sedarplus.parsers import (
    extract_document_id,
    extract_profile_id,
    map_company_record,
    map_document_record,
    parse_csv_export,
    parse_results_table,
)
from sedar.storage.engine import Storage

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _reset_settings():
    reset_settings()
    yield
    reset_settings()


@pytest.fixture
def settings(tmp_path, monkeypatch):
    auth_file = tmp_path / "authorization.txt"
    auth_file.write_text("Authorized for testing.\n")
    db_path = tmp_path / "test.db"
    cfg = Settings(
        DATABASE_URL=f"sqlite:///{db_path}",
        SEDAR_AUTHORIZATION_FILE=str(auth_file),
        SEDAR_CONFIRM_AUTHORIZED="1",
        SEDAR_DOWNLOAD_DIR=str(tmp_path / "filings"),
    )
    monkeypatch.setenv("DATABASE_URL", cfg.database_url)
    monkeypatch.setenv("SEDAR_AUTHORIZATION_FILE", str(auth_file))
    monkeypatch.setenv("SEDAR_CONFIRM_AUTHORIZED", "1")
    reset_settings()
    return cfg


def test_verify_authorization_file(settings):
    path = verify_authorization_file(settings.authorization_file)
    assert path.is_file()


def test_require_live_access_without_confirm(tmp_path):
    auth_file = tmp_path / "authorization.txt"
    auth_file.write_text("ok")
    cfg = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'test.db'}",
        SEDAR_AUTHORIZATION_FILE=str(auth_file),
        SEDAR_CONFIRM_AUTHORIZED="0",
    )
    with pytest.raises(ComplianceError):
        require_live_access(confirm_authorized=False, settings=cfg)


def test_require_live_access_with_confirm(settings):
    path = require_live_access(confirm_authorized=True, settings=settings)
    assert path.exists()


def test_enforce_download_limit():
    assert enforce_download_limit(30) == 30
    with pytest.raises(ComplianceError):
        enforce_download_limit(31)


def test_enforce_profile_limit():
    enforce_profile_limit(50)
    with pytest.raises(ComplianceError):
        enforce_profile_limit(51)


def test_detect_bot_challenge():
    with pytest.raises(BotChallengeError):
        detect_bot_challenge("Radware Captcha Page", "https://example.com")


def test_detect_unavailable():
    with pytest.raises(SEDARUnavailableError):
        detect_unavailable(
            "SEDAR+ is temporarily unavailable due to planned system maintenance.",
            "https://www.sedarplus.ca",
        )


def test_service_link_uses_current_sedar_apps():
    cfg = Settings()

    assert (
        cfg.service_link("searchIndustryParticipant")
        == "https://www.sedarplus.ca/csa-party/service/create.html"
        "?_locale=en&service=searchIndustryParticipant&targetAppCode=csa-party"
    )
    assert (
        cfg.service_link("searchCeaseTradeOrders")
        == "https://www.sedarplus.ca/csa-order/service/create.html"
        "?_locale=en&service=searchCeaseTradeOrders&targetAppCode=csa-order"
    )


def test_parse_results_table():
    html = (FIXTURES / "search_results.html").read_text()
    rows = parse_results_table(html)
    assert len(rows) == 2
    assert rows[0]["document_id"] == "abc123def456"
    assert "profile_id" not in rows[0]


def test_extract_ids_require_matching_path():
    document_url = "https://www.sedarplus.ca/csa-party/records/document.html?id=abc123"
    profile_url = "https://www.sedarplus.ca/csa-party/records/profile.html?id=prof456"

    assert extract_document_id(document_url) == "abc123"
    assert extract_profile_id(document_url) is None
    assert extract_profile_id(profile_url) == "prof456"
    assert extract_document_id(profile_url) is None


def test_parse_csv_export_documents():
    content = (FIXTURES / "documents.csv").read_text()
    rows = parse_csv_export(content)
    assert len(rows) == 2
    mapped = map_document_record(rows[0])
    assert mapped["document_id"] == "abc123def456"
    assert mapped["document_name"] == "Annual MD&A"


def test_parse_csv_export_issuers():
    content = (FIXTURES / "issuers.csv").read_text()
    rows = parse_csv_export(content)
    mapped = map_company_record(rows[0])
    assert mapped["legal_name"] == "Example Corp."
    assert mapped["profile_number"] == "00001234"


def test_map_reporting_issuer_fields():
    mapped = map_company_record(
        {
            "name": "Example Fund",
            "number": "000037625",
            "reporting_jurisdictions_determined_by_regulator": "AB, ON",
            "principal_jurisdiction": "ON",
            "type": "Investment fund",
            "in_default": "No",
            "active_cease_trade_order_ban_trading_by_ban_trading_of": "No",
        }
    )

    assert mapped["profile_number"] == "000037625"
    assert mapped["jurisdiction"] == "ON"
    assert mapped["reporting_jurisdictions"] == "AB, ON"
    assert mapped["profile_type"] == "Investment fund"
    assert mapped["in_default"] == "No"
    assert mapped["active_cease_trade_order"] == "No"


def test_storage_upsert(settings):
    storage = Storage(settings)
    storage.upsert_filing(
        {
            "document_id": "doc1",
            "profile_id": "prof1",
            "document_name": "Test",
            "submitted_date": "2024-01-01",
        }
    )
    row = storage.find_filing("doc1")
    assert row is not None
    assert row["document_name"] == "Test"
    storage.ping()


def test_import_csv_cli(settings, tmp_path):
    from click.testing import CliRunner

    from sedar.cli import main

    csv_path = FIXTURES / "documents.csv"
    cli = CliRunner()
    result = cli.invoke(main, ["import-csv", str(csv_path), "--kind", "documents"])
    assert result.exit_code == 0
    assert "Imported 2" in result.output
