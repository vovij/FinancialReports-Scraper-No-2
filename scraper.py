import time
import re
from pathlib import Path
from bs4 import BeautifulSoup
from session import get_session, BASE_URL


def fetch_page(client, meta, page_num: int) -> BeautifulSoup:
    """
    Replicates: catHtmlFragmentCallback('W231', 'selectPage', <page_num>, ...)
    Server returns the full page regardless of _CBHTMLFRAG_ — we parse it whole.
    _CBHTMLFRAGID_ must be a real ms timestamp (Catalyst generates it client-side).
    """
    payload = {
        "_VIKEY_":            meta["vikey"],
        "_CBNODE_":           "W231",
        "_CBNAME_":           "selectPage",
        "_CBVALUE_":          str(page_num),
        "_CBASYNCUPDATE_":    "true",
        "_CBHTMLFRAG_":       "true",
        "_CBHTMLFRAGNODEID_": "W167",
        "_CBHTMLFRAGID_":     str(int(time.time() * 1000)),  # ms timestamp like browser
    }
    url = f"{BASE_URL}/csa-party/viewInstance/view.html?id={meta['view_id']}"
    r = client.post(url, data=payload, headers={"Referer": url})
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def parse_filings(soup: BeautifulSoup) -> list[dict]:
    filings = []
    for row in soup.select("tr.appTblRow[class*='searchDocuments']"):
        if row.find("th"):
            continue

        company_tag  = row.select_one("a.appMenuItem span.appReceiveFocus")
        doc_tag      = row.select_one("a.appDocumentLink")
        date_tag     = row.select_one("div[id*='SubmissionDate'] span[aria-hidden='true']")
        juris_tag    = row.select_one("div[id*='PrincipalJurisdictionCode'] div.appAttrValue")
        size_tag     = row.select_one("div[id*='DocumentSize'] div.appAttrValue")

        filings.append({
            "company":      company_tag.text.strip() if company_tag else "",
            "doc_name":     doc_tag.text.strip()     if doc_tag     else "",
            "doc_url":      doc_tag["href"]           if doc_tag     else "",
            "date":         date_tag.text.strip()     if date_tag    else "",
            "jurisdiction": juris_tag.text.strip()    if juris_tag   else "",
            "size":         size_tag.text.strip()     if size_tag    else "",
        })
    return filings


def download_doc(client, filing: dict, out_dir: Path):
    if not filing["doc_url"]:
        return
    r = client.get(filing["doc_url"])
    r.raise_for_status()
    safe_name = re.sub(r'[^\w\-.]', '_', filing["doc_name"]) or "doc"
    path = out_dir / safe_name
    if path.exists():
        stem, suffix = path.stem, path.suffix
        path = out_dir / f"{stem}_{hash(filing['doc_url']) % 9999}{suffix}"
    path.write_bytes(r.content)
    print(f"    saved → {path.name} ({len(r.content) // 1024} KB)")


def run(pages: int = 3, download: bool = True):
    client, meta = get_session()
    print(f"[scraper] session OK — view_id: {meta['view_id'][:20]}...")

    out_dir = Path("downloads")
    out_dir.mkdir(exist_ok=True)

    for page_num in range(1, pages + 1):
        print(f"\n[scraper] fetching page {page_num}...")
        soup = fetch_page(client, meta, page_num)
        filings = parse_filings(soup)
        print(f"[scraper] found {len(filings)} filings")

        for f in filings:
            print(f"  {f['date']}  {f['company'][:50]}  {f['doc_name']}")
            if download:
                download_doc(client, f, out_dir)

        time.sleep(1)

    print(f"\n[scraper] done.")


if __name__ == "__main__":
    run(pages=3, download=True)