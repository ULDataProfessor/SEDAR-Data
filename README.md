# SEDAR+ Filing Collection

Python tooling for **authorized** collection of Canadian securities filings from
[SEDAR+](https://www.sedarplus.ca), with legacy pre-2023 `sedar.com` code preserved
for reference.

SEDAR+ has no official public API. This project uses Playwright browser automation
against the public UI, with compliance gates, rate limiting, and audit logging. Do
not run live commands without written authorization — see
[docs/sedar-plus-and-data-access.md](docs/sedar-plus-and-data-access.md).

## Quick Start

```bash
# Install package and Playwright browser
make setup

# Copy and edit configuration
cp .env.example .env
# Set SEDAR_AUTHORIZATION_FILE to your authorization document

# Verify configuration
sedar check-auth

# Live commands require explicit authorization
sedar sync-issuers --confirm-authorized
sedar search-docs --profile "Example Corp." --confirm-authorized
sedar download --limit 30 --confirm-authorized

# Import a manual CSV export (no live browser)
sedar import-csv exports/documents.csv --kind documents
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL or SQLite connection | `sqlite:///sedar.db` |
| `SEDAR_AUTHORIZATION_FILE` | Path to authorization document | `./docs/authorization.example.txt` |
| `SEDAR_CONFIRM_AUTHORIZED` | Opt-in for live automation (`1`/`0`) | `0` |
| `SEDAR_RATE_LIMIT_SECONDS` | Delay between browser actions | `4` |
| `SEDAR_DOWNLOAD_DIR` | Local filing storage | `./filings` |
| `SEDAR_HEADLESS` | Headless browser (`false` for manual CAPTCHA) | `true` |
| `SEDAR_MAX_DOWNLOAD_BATCH` | Max documents per batch | `30` |

## CLI Commands

| Command | Description |
|---------|-------------|
| `sedar check-auth` | Verify authorization file and database |
| `sedar sync-issuers` | Sync reporting issuers list |
| `sedar search-docs` | Search documents and store metadata |
| `sedar download` | Download pending filings (max 30) |
| `sedar import-csv` | Import manual SEDAR+ CSV export |
| `sedar legacy-scrape` | Historical legacy scraper (deprecated) |

## Project Layout

```
sedar/
  cli.py                 # CLI entry point
  config.py              # Settings
  compliance.py          # Authorization and rate limits
  storage/               # PostgreSQL / SQLite via dataset
  sedarplus/             # Playwright client (search, download, issuers)
  legacy/                # Pre-SEDAR+ scraper and CAPTCHA helper
docs/                    # Data access guidance and authorization checklist
tests/                   # Fixture-based unit tests
```

## Storage

Metadata is stored in `company`, `filing`, and `sync_run` tables. Filings are saved
under `SEDAR_DOWNLOAD_DIR/{profile_id}/{document_id}/`.

Use PostgreSQL for production:

```
DATABASE_URL=postgresql://localhost/sedar
```

Use SQLite for local development:

```
DATABASE_URL=sqlite:///sedar.db
```

## Legacy Code

The original legacy `sedar.com` scraper lives in `sedar/legacy/`. Root `scrape.py`
and `breaker.py` are deprecation shims. Legacy endpoints were replaced by SEDAR+ in
July 2023 and are not maintained for current use.

## Known Limits

- **30 documents** per public download batch
- **50 profiles** max per document search
- **Radware bot protection** may require headed browser and manual CAPTCHA
- **No official SEDAR+ API** — UI automation may break when the site changes

## Development

```bash
make test    # pytest
make lint    # ruff check
make format  # ruff format
```

CI runs lint and tests without live SEDAR+ access.

## Disclaimer

This tool is for authorized research and operational use only. Review the current
[SEDAR+ Terms of Use](https://systems.securities-administrators.ca/terms-of-use/)
before collecting, storing, or redistributing filing data. This repository is not
legal advice.
