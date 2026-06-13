# SEDAR+, EDGAR, and Public Data Access

This note explains what this repository contains, what changed when SEDAR+
replaced legacy SEDAR, and why current Canadian filing data is not as accessible
for automated collection as U.S. EDGAR data.

## What This Repository Was Built For

The Python code in this repository targets the legacy SEDAR website at
`sedar.com`. In particular:

- `scrape.py` builds requests for old search and document endpoints such as
  `search_form_pc_en.htm`, `FindCompanyDocuments.do`, and document download
  forms.
- `breaker.py` attempts to create a session for the old document flow by using
  image processing and OCR on CAPTCHA images.
- Downloaded documents were intended to be stored under `filings/`, with filing
  and company metadata written to a local PostgreSQL database through
  `dataset`.

That approach belongs to the legacy SEDAR site. It does not describe how to use
SEDAR+ today, and it should not be adapted to bypass SEDAR+ controls.

## What Changed With SEDAR+

SEDAR+ launched on July 25, 2023. The CSA describes SEDAR+ as the web-based
system used to file, disclose, and search for information in Canada's capital
markets. At launch, it consolidated and replaced legacy SEDAR, the national
Cease Trade Order database, the Disciplined List database, and some other
filing channels.

The current public SEDAR+ website supports browser-oriented workflows:

- Search profiles, documents, cease trade orders, and the disciplined list.
- Generate a URL for individual documents from search results.
- Download selected documents or export search results through the interface.
- Subscribe to certain document or regulatory-action alerts.

SEDAR+ also changed legacy data coverage. The SEDAR+ repository includes legacy
SEDAR filings and associated documents submitted since January 1, 2016, while
some frequently referenced filing categories are available beyond that seven
year window. The CSA documentation says a searchable legacy archive remains
available for pre-launch public SEDAR data, and that users interested in an
archive of public documents filed on SEDAR between 1997 and 2015 should contact
the CSA Service Desk.

## Why SEDAR+ Is Not Like EDGAR

The U.S. SEC EDGAR system is explicitly designed for programmatic public access
as well as browser search. The SEC publishes:

- JSON APIs for submissions and XBRL facts on `data.sec.gov`.
- Index files for public filings from 1994Q3 onward.
- Bulk ZIP files for large API datasets, republished nightly.
- Feed and archive directories for filing dissemination.
- A fair-access policy with a published request-rate limit and declared user
  agent guidance.

SEDAR+ has a different public access model. The official public materials
document browser search, result export, manual download, alert subscriptions,
and contact channels, but they do not document a public bulk API equivalent to
EDGAR's submissions, company facts, index, or bulk-data endpoints.

## Access Limits That Matter

The main constraint is not just that old `sedar.com` URLs changed. The SEDAR+
terms and public help pages materially limit automated and bulk use:

- Public users can download documents through the SEDAR+ interface, but the help
  page describes a limit of 30 documents at a time.
- Search results are exposed through a web application, not through a documented
  public filing API.
- The terms limit reuse to narrow purposes and prohibit constructing databases
  from public information without authorization.
- The terms prohibit scraping and automated means to monitor, access, scrape,
  copy, or interfere with SEDAR+ pages or content.
- The terms prohibit automated searches or repeated transactional-server access
  where the ASC considers the activity to unduly burden the public site.
- The terms allow the ASC to limit, suspend, terminate, or block access.
- Not all legacy filings were migrated into SEDAR+; older public documents may
  require the legacy archive or CSA Service Desk contact path.

Because of those limits, a direct SEDAR+ replacement for this repository would
be a policy and authorization project first, not just a parser rewrite.

## Compliant Paths Forward

Use one of these paths for current work:

- Manual SEDAR+ search, CSV export, generated document URLs, and limited
  document downloads through the public website.
- CSA Service Desk contact for archive questions or permitted access options.
- Licensed data vendors that have permission to redistribute Canadian filing
  data.
- Written authorization from the ASC/CSA before building automated collection,
  database reconstruction, monitoring, or redistribution workflows.

If authorized access is obtained later, document the permission, permitted use,
rate limits, retention rules, and redistribution limits before writing code.

## Authorization Checklist

Before running live SEDAR+ automation with this repository, confirm all of the
following:

1. **Written permission** — You hold current written authorization from the ASC/CSA
   or a licensed data provider that permits your intended use.
2. **Scope** — The authorization covers search, download, storage, and any
   redistribution you plan to perform.
3. **Volume limits** — You documented agreed rate and volume limits. The CLI enforces
   the public 30-document download batch cap; stay within any stricter contractual
   limits.
4. **Retention** — You defined how long filings and metadata may be kept and when
   they must be deleted.
5. **Redistribution** — You confirmed whether derived databases, APIs, or republished
   files are permitted.
6. **Audit trail** — You configured logging and can demonstrate what was collected,
   when, and under which authorization file (`SEDAR_AUTHORIZATION_FILE`).
7. **Bot challenges** — You have a process for manual CAPTCHA completion in headed
   browser mode when Radware protection triggers (`SEDAR_HEADLESS=false`).
8. **Contact** — You recorded the CSA Service Desk or licensor contact for
   escalation if access is suspended.

Store the authorization document at the path referenced by `SEDAR_AUTHORIZATION_FILE`
and pass `--confirm-authorized` only after the checklist is complete.

## Official Sources

- [About SEDAR+](https://systems.securities-administrators.ca/onlinehelp/general-help/about-sedar-plus/)
- [SEDAR+ Terms of Use](https://systems.securities-administrators.ca/terms-of-use/)
- [SEDAR+ search and download help](https://systems.securities-administrators.ca/onlinehelp/general-help/search-sedar/search-and-download-documents/)
- [SEDAR+ migrated filings help](https://systems.securities-administrators.ca/onlinehelp/filings/view-a-filing/viewing-migrated-filings/)
- [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)

This document is operational guidance, not legal advice. Always review the
current source documents before collecting, storing, or redistributing filing
data.
