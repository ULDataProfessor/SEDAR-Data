import os
import urllib.parse
from datetime import UTC, datetime, timedelta
from itertools import count
from typing import Dict
from urllib.parse import urljoin

import dataset
import requests
from lxml import html
from slugify import slugify
from werkzeug.utils import secure_filename

from sedar.legacy.breaker import make_cracked_session

# Constants
INDUSTRIES = "046,047,005,006,058,025"
TO_DATE = datetime.now(UTC)
FROM_DATE = TO_DATE - timedelta(days=10 * 365)

SEARCH_PAGE = "http://www.sedar.com/search/search_form_pc_en.htm"
RESULT_PAGE = "http://www.sedar.com/FindCompanyDocuments.do"

# Preparing search parameters
PARAMS: Dict[str, str | int] = {
    "lang": "EN",
    "page_no": 2,
    "company_search": "All (or type a name)",
    "document_selection": 0,
    "industry_group": INDUSTRIES,
    "FromDate": FROM_DATE.strftime("%d"),
    "FromMonth": FROM_DATE.strftime("%m"),
    "FromYear": FROM_DATE.strftime("%Y"),
    "ToDate": TO_DATE.strftime("%d"),
    "ToMonth": TO_DATE.strftime("%m"),
    "ToYear": TO_DATE.strftime("%Y"),
    "Variable": "Issuer",
}

# Database connection
engine = dataset.connect("postgresql://localhost/sedar")
filing = engine["filing"]
company = engine["company"]
sess: dict[str, requests.Session | None] = {}


def chomp_name(key: str) -> str:
    """
    Transforms a string to a slug and replaces "-" with "_" and trims "_" from ends.

    :param key: The string to be transformed
    :return: Transformed string
    """
    return slugify(key).replace("-", "_").strip("_")


def get_company(url: str) -> None:
    """
    Scrapes and stores company data from a given url.

    :param url: Url to the company's page
    """
    if company.find_one(url=url):
        return
    res = requests.get(url)
    doc = html.fromstring(res.content)
    content = doc.find('.//div[@id="content"]')
    data = {"url": url, "name": content.findtext(".//td/font/strong")}
    print(f'Company: {data["name"]}')
    key = None
    for row in content.findall(".//td"):
        if row.get("class") == "bt":
            key = chomp_name(row.text)
        elif row.get("class") == "rt" and key is not None:
            data[key] = row.text
            key = None
    company.upsert(data, ["url"])


def download_document(form: str) -> str:
    """
    Downloads a document from a form action url.

    :param form: Form action url
    :return: Local path to the downloaded file
    """
    file_name = form.split("/filings/", 1)[-1]
    filing_id, doc_id, rest = file_name.split("/", 2)
    rest = secure_filename(urllib.parse.unquote(rest))
    file_name = os.path.join("filings", filing_id, doc_id, rest)
    if os.path.exists(file_name):
        return file_name

    print(f"Downloading: {form}")
    if "ca" not in sess or sess["ca"] is None:
        sess["ca"] = make_cracked_session()

    res = sess["ca"].get(form)
    if "x-powered-by" in res.headers or b"Accept Terms of Use" in res.content:
        sess["ca"] = make_cracked_session()
        return download_document(form)

    os.makedirs(os.path.dirname(file_name), exist_ok=True)

    with open(file_name, "wb") as fh:
        fh.write(res.content)

    return file_name


def load_filings() -> None:
    """
    Loads filings from a page until no more filings are found.
    """
    for i in count(1):
        page_hits = 0
        params = PARAMS.copy()
        params["page_no"] = i
        res = requests.get(RESULT_PAGE, params=params)
        doc = html.fromstring(res.content)

        for row in doc.findall(".//tr"):
            cells = row.findall(".//td")
            if len(cells) < 6:
                continue
            submit_children = list(cells[3])
            if not submit_children:
                continue
            submit = submit_children[0].get("action")
            if submit is None:
                continue
            page_hits += 1
            filing_id = submit.split("fileName=", 1)[-1]
            print(f"Filing: {filing_id}")
            form = urljoin(RESULT_PAGE, submit)
            file_name = download_document(form)
            company_link = cells[0].find("./a")
            data = {
                "filing": filing_id,
                "file_name": file_name,
                "company": cells[0].text_content().strip(),
                "company_url": urljoin(RESULT_PAGE, company_link.get("href"))
                if company_link is not None
                else "",
                "date": cells[1].text_content().strip(),
                "time": cells[2].text_content().strip(),
                "type": cells[3].text_content().strip(),
                "tos_form": form,
                "format": cells[4].text_content().strip(),
                "size": cells[5].text_content().strip(),
            }
            filing.upsert(data, ["filing"])
            if data["company_url"]:
                get_company(data["company_url"])

        if page_hits == 0:
            return


if __name__ == "__main__":
    load_filings()
