"""
SEDAR+ document scraper.

Pulls filings from the general list, downloads attached documents,
and walks through multiple pages.

Usage:
    python scraper.py
    python scraper.py --pages 10
    python scraper.py --no-download
"""

import re
import time
import argparse
from pathlib import Path

from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup

BASE_URL   = "https://www.sedarplus.ca"
CREATE_URL = f"{BASE_URL}/csa-party/service/create.html"
OUT_DIR    = Path("downloads")
MAX_PAGES  = 5
SLEEP_S    = 1.2

HEADERS = {
    "User-Agent":         "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Accept":             "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language":    "en-US,en;q=0.9",
    "sec-ch-ua":          '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
    "sec-ch-ua-mobile":   "?0",
    "sec-ch-ua-platform": '"macOS"',
    "upgrade-insecure-requests": "1",
}

# ── Session ───────────────────────────────────────────────────────────────────

def load_page1() -> tuple[curl_requests.Session, BeautifulSoup, str, str, str, str]:
    """
    Bootstrap a fresh session and load page 1.
    Returns (client, soup, view_id, vikey, cbnode, fragnode).
    All Catalyst widget IDs extracted dynamically — nothing hardcoded.
    """
    client = curl_requests.Session(impersonate="chrome", headers=HEADERS)

    # Warm up Imperva
    client.get(f"{BASE_URL}/home/",
               headers={**HEADERS, "sec-fetch-site": "none",
                        "sec-fetch-mode": "navigate", "sec-fetch-dest": "document"})

    # create.html → 302 → view.html?id=<hex>, issues JSESSIONID + TS01* cookie
    r = client.get(CREATE_URL,
                   params={"targetAppCode": "csa-party",
                           "service": "searchDocuments", "_locale": "en"},
                   headers={**HEADERS, "Referer": f"{BASE_URL}/home/",
                            "sec-fetch-site": "same-origin", "sec-fetch-mode": "navigate",
                            "sec-fetch-dest": "document", "sec-fetch-user": "?1"})
    m = re.search(r"[?&]id=([a-f0-9]+)", str(r.url))
    if not m:
        raise RuntimeError("Session bootstrap failed — create.html did not redirect to view.html.")
    view_id = m.group(1)

    # Load page 1
    r = client.get(f"{BASE_URL}/csa-party/viewInstance/view.html?id={view_id}",
                   headers={**HEADERS, "Referer": f"{BASE_URL}/home/",
                            "sec-fetch-site": "same-origin", "sec-fetch-mode": "navigate",
                            "sec-fetch-dest": "document"})
    soup = BeautifulSoup(r.text, "html.parser")

    # _VIKEY_: Catalyst session key
    tag = soup.find("input", {"name": "_VIKEY_"})
    vikey = tag["value"] if tag else ""
    if not vikey:
        m2 = re.search(r"viewInstanceKey\s*[=:'\"]+\s*([a-f0-9x]+)", r.text)
        vikey = m2.group(1) if m2 else ""
    if not vikey:
        raise RuntimeError("Could not extract _VIKEY_ from view.html.")

    # _CBNODE_: results widget that handles selectPage (dynamic per session)
    nodes = re.findall(r"'(W\d+)','selectPage'", r.text)
    cbnode = nodes[0] if nodes else "W1030"

    # _CBHTMLFRAGNODEID_: AsyncWrapper container node (dynamic per session)
    frag_m = re.search(r"AsyncWrapper(W\d+)", r.text)
    fragnode = frag_m.group(1) if frag_m else "W167"

    print(f"[init] view_id={view_id}  vikey={vikey[:8]}...  cbnode={cbnode}  fragnode={fragnode}")
    return client, soup, view_id, vikey, cbnode, fragnode

# ── Pagination ────────────────────────────────────────────────────────────────

def fetch_page(client: curl_requests.Session, view_id: str, vikey: str,
               cbnode: str, fragnode: str, page_num: int) -> BeautifulSoup:
    """POST to Catalyst update endpoint to get the next page of results."""
    r = client.post(
        f"{BASE_URL}/csa-party/viewInstance/update.html?id={view_id}",  # scopes request to our session
        data={
            "_VIKEY_":            vikey,       # Catalyst session token
            "_CBNODE_":           cbnode,      # widget that owns the results table
            "_CBNAME_":           "selectPage", # action to perform
            "_CBVALUE_":          str(page_num), # target page number
            "_CBASYNCUPDATE_":    "true",      # AJAX update, not full page load
            "_CBHTMLFRAG_":       "true",      # return HTML fragment only
            "_CBHTMLFRAGNODEID_": fragnode,    # which async wrapper to return
            "_CBHTMLFRAGID_":     str(int(time.time() * 1000)),  # cache-busting timestamp nonce
        },
        headers={
            "Referer": f"{BASE_URL}/csa-party/viewInstance/view.html?id={view_id}",  # proves request came from our session page
        },
    )
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

# ── Parsing ───────────────────────────────────────────────────────────────────

def parse_filings(soup: BeautifulSoup) -> list[dict]:
    filings = []
    for row in soup.select("tr.appTblRow"):
        if row.find("th"):
            continue
        doc_tag = row.select_one("a.appDocumentLink")
        if not doc_tag:
            continue
        company_tag = row.select_one("a.appMenuItem span.appReceiveFocus")
        filings.append({
            "company":  company_tag.get_text(strip=True) if company_tag else "",
            "doc_name": doc_tag.get_text(strip=True),
            "doc_url":  doc_tag.get("href", ""),
        })
    return filings

# ── Download ──────────────────────────────────────────────────────────────────

def download(client: curl_requests.Session, filing: dict, out_dir: Path, view_id: str):
    """
    Download a filing document.

    NOTE: SEDAR+ document URLs are protected by Radware/Imperva WAF.
    The GET to resource.html requires the TS01* session cookie issued during
    the initial page load. If downloads return captcha pages, the WAF has
    flagged the session — see README for workaround notes.
    """
    url = filing["doc_url"]
    if not url:
        return

    r = client.get(url, headers={
        **HEADERS,
        "Referer":        f"{BASE_URL}/csa-party/viewInstance/view.html?id={view_id}",
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "navigate",
        "sec-fetch-dest": "document",
        "sec-fetch-user": "?1",
    })
    r.raise_for_status()

    if r.content[:4] != b"%PDF":
        print(f"    ✗ blocked (captcha) — {filing['doc_name']}")
        return

    safe = re.sub(r'[^\w\-.]', '_', filing["doc_name"]) or "doc"
    path = out_dir / safe
    counter = 1
    while path.exists():
        path = out_dir / f"{Path(safe).stem}_{counter}{Path(safe).suffix}"
        counter += 1

    path.write_bytes(r.content)
    print(f"    ✓ {path.name}  ({len(r.content) // 1024} KB)")

# ── Main ──────────────────────────────────────────────────────────────────────

def run(max_pages: int, do_download: bool):
    OUT_DIR.mkdir(exist_ok=True)
    client, soup, view_id, vikey, cbnode, fragnode = load_page1()

    for page_num in range(1, max_pages + 1):
        print(f"\n[page {page_num}]")
        filings = parse_filings(soup)
        print(f"  {len(filings)} filings")

        for f in filings:
            print(f"  {f['company'][:45]}  {f['doc_name']}")
            if do_download:
                download(client, f, OUT_DIR, view_id)

        if page_num >= max_pages:
            break

        print(f"  → fetching page {page_num + 1}...")
        soup = fetch_page(client, view_id, vikey, cbnode, fragnode, page_num + 1)
        time.sleep(SLEEP_S)

    total = sum(1 for _ in OUT_DIR.iterdir()) if do_download else 0
    print(f"\n[done] {max_pages} pages scraped. Files in downloads/: {total}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=MAX_PAGES, help="Pages to scrape (default: 5)")
    parser.add_argument("--no-download", action="store_true", help="List filings only, skip downloads")
    args = parser.parse_args()
    run(args.pages, not args.no_download)