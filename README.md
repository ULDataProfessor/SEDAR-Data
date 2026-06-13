# Legacy SEDAR Scraper

This repository contains historical Python code for working with the legacy
SEDAR website at `sedar.com`. It is not a current SEDAR+ scraper, and it should
not be used as a template for automated access to SEDAR+ without written
authorization.

SEDAR+ replaced legacy SEDAR on July 25, 2023. The current SEDAR+ public site is
designed around browser-based search and download workflows, and its terms place
material restrictions on scraping, automated searching, database reconstruction,
and mass redistribution of public information. For background, see
[SEDAR+, EDGAR, and public data access](docs/sedar-plus-and-data-access.md).

## Current Status

- Historical and educational code only.
- Targets legacy `http://www.sedar.com` endpoints, including
  `FindCompanyDocuments.do` and `GetFile.do`.
- Includes code intended to pass old CAPTCHA and terms-of-use screens.
- Does not implement SEDAR+ search, SEDAR+ downloads, or any authorized SEDAR+
  data feed.
- No SEDAR+ automation should be added unless the project first obtains and
  documents permission or a licensed data-access path.

## Repository Contents

- `scrape.py` - legacy scraper logic for company document search, document
  download, and local PostgreSQL storage.
- `breaker.py` - legacy OCR/CAPTCHA helper used by the old scraper flow.
- `captcha/` - sample CAPTCHA image files used by the legacy helper.

The code is preserved to document how the old approach worked. It may not run
against current systems and may require missing dependencies or repairs if used
in an isolated historical test environment.

## Data Access Guidance

For current Canadian issuer filings, use the public SEDAR+ website manually,
contact the CSA Service Desk for available archive options, use a licensed data
vendor, or obtain written permission for any automated access pattern.

For comparison, the U.S. SEC EDGAR system publishes official public APIs, index
files, bulk downloads, and fair-access rules. SEDAR+ does not currently expose
an equivalent documented public bulk API for unrestricted automated collection.

This repository is not legal advice. Review the current SEDAR+ terms and any
applicable laws before collecting, storing, or redistributing filing data.
