"""
SEDAR+ scraper — minimal and working.

Key findings from page_dump.html diagnosis:
- POST endpoint is /viewInstance/update.html (NOT view.html)
- _CBHTMLFRAG_ + _CBHTMLFRAGNODEID_=W167 required; server returns fragment HTML only
- _CBVALUE_ is 1-based (page 2 = "2", page 3 = "3", etc.)
- Page 1 is loaded via GET; subsequent pages via POST to update.html
"""

import re
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────

BASE_URL = "https://www.sedarplus.ca"
VIEW_ID  = "0c11f8b7998bcd966133b671f299339ae40216b61518a131"
OUT_DIR  = Path("downloads")
MAX_PAGES = 5
SLEEP_S   = 1.2

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Refresh from browser DevTools → Network → any request → Cookie header
COOKIES = {
    "JSESSIONID":                "YKFKQKv9mkPGQ8hsNceYy4X6cha-JgEnSQDuIlItPcg9faNCm30T!-1524954598",
    "TS01bfbdd0":                "016abe8a181dbd8aabcf0fcea07d9145ed512f75432f653609a0d867daccf2ac861d75a7b23331d6bb7e863454d7cd13be72110a218b31da73456633b8b6c2af8dc946140ad6b6ed58697e607501016ed48de2666fdf1ad0558e93ed47d7470e817d074721340541063ae2300b2fc085a6f9a52a336c4d2b246b5b70ec0da9daa3c0178c4a",
    "x-catalyst-session-global": "dc27043bec1f81f49bcae196919f71d38b825a75341a805bdaaafc826ec3ee083d838acc5d8ef846",
    "x-catalyst-locale":         "en",
    "x-catalyst-timezone":       "EST5EDT",
    "__uzma":                    "e270f475-72ce-40f8-922d-549e26e25158",
    "__uzmb":                    "1779132652",
    "__uzmc":                    "9564510682120",
    "__uzmd":                    "1779364633",
    "__uzme":                    "3949",
    "__uzmf":                    "7f9000e270f475-72ce-40f8-922d-549e26e251582-1779132652876231980134-003f3539e0fb639483b106",
    "uzmx":                      "7f9000ed22e935-f6c1-424a-b594-5f06c75ea7b02-1779132652876231980134-a72114179260eb6d106",
    "__ssds":                    "0",
    "__ssuzjsr0":                "a9be0cd8e",
}

# ── Session ───────────────────────────────────────────────────────────────────

def make_client() -> httpx.Client:
    return httpx.Client(headers=HEADERS, cookies=COOKIES,
                        follow_redirects=True, timeout=30.0)


def load_page1(client: httpx.Client) -> tuple[BeautifulSoup, str]:
    """GET page 1 and extract vikey."""
    url = f"{BASE_URL}/csa-party/viewInstance/view.html?id={VIEW_ID}"
    r = client.get(url)
    r.raise_for_status()
    if "sedarplus.ca" not in str(r.url):
        raise RuntimeError("Cookies expired — grab fresh ones from DevTools.")
    soup = BeautifulSoup(r.text, "html.parser")

    tag = soup.find("input", {"name": "_VIKEY_"})
    if tag:
        vikey = tag["value"]
    else:
        m = re.search(r"viewInstanceKey\s*[=:'\"]+\s*([a-f0-9x]+)", r.text)
        vikey = m.group(1) if m else ""

    print(f"[init] vikey={vikey[:16]}...")
    return soup, vikey

# ── Pagination ────────────────────────────────────────────────────────────────

def fetch_page(client: httpx.Client, vikey: str, page_num: int) -> BeautifulSoup:
    """
    POST to update.html (the correct Catalyst async endpoint).
    Returns the fragment HTML injected into #AsyncWrapperW167.
    """
    # update.html, not view.html
    url = f"{BASE_URL}/csa-party/viewInstance/update.html?id={VIEW_ID}"
    ref = f"{BASE_URL}/csa-party/viewInstance/view.html?id={VIEW_ID}"

    payload = {
        "_VIKEY_":            vikey,
        "_CBNODE_":           "W231",
        "_CBNAME_":           "selectPage",
        "_CBVALUE_":          str(page_num),   # 1-based: page 2 → "2"
        "_CBASYNCUPDATE_":    "true",
        "_CBHTMLFRAG_":       "true",
        "_CBHTMLFRAGNODEID_": "W167",
        "_CBHTMLFRAGID_":     str(int(time.time() * 1000)),
    }
    r = client.post(url, data=payload, headers={"Referer": ref})
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

def download(client: httpx.Client, filing: dict, out_dir: Path):
    url = filing["doc_url"]
    if not url:
        return
    r = client.get(url)
    r.raise_for_status()
    safe = re.sub(r'[^\w\-.]', '_', filing["doc_name"]) or "doc"
    path = out_dir / safe
    if path.exists():
        path = out_dir / f"{path.stem}_{abs(hash(url)) % 9999}{path.suffix}"
    path.write_bytes(r.content)
    print(f"    ✓ {path.name}  ({len(r.content) // 1024} KB)")

# ── Main ──────────────────────────────────────────────────────────────────────

def run(max_pages: int = MAX_PAGES, do_download: bool = True):
    OUT_DIR.mkdir(exist_ok=True)
    client = make_client()

    print("[*] Loading page 1...")
    soup, vikey = load_page1(client)

    seen: set[str] = set()

    for page_num in range(1, max_pages + 1):
        print(f"\n[*] Page {page_num}")

        filings = parse_filings(soup)
        new = [f for f in filings if f["doc_url"] not in seen]
        seen.update(f["doc_url"] for f in new)
        print(f"    {len(new)} new filings")

        if not new and page_num > 1:
            print("    All dupes — pagination stalled. Stopping.")
            break

        for f in new:
            print(f"  {f['company'][:45]}  {f['doc_name']}")
            if do_download:
                download(client, f, OUT_DIR)

        if page_num >= max_pages:
            break

        # Fetch next page
        print(f"    → fetching page {page_num + 1}...")
        soup = fetch_page(client, vikey, page_num + 1)
        time.sleep(SLEEP_S)

    print(f"\n[done] {len(seen)} unique filings collected.")


if __name__ == "__main__":
    run(max_pages=MAX_PAGES, do_download=True)