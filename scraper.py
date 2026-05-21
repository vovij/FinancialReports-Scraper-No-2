import time
import json
from pathlib import Path
from bs4 import BeautifulSoup
from session import build_client, init_session, BASE_URL

# Paste your cookies from DevTools here
COOKIES = {
    "JSESSIONID":                "YKFKQKv9mkPGQ8hsNceYy4X6cha-JgEnSQDuIlItPcg9faNCm30T!-1524954598",  # keep old one if not in new list
    "TS01bfbdd0":                "016abe8a180a7ca13f5302535237b58bd21fc2e2a54717689d36b4085c8369f1ada439681617b008cd3f59435a90f12672bbcd878fffd02230d1d554d989654d0e71a245d7fc734e5f0a611c1e7ca3dad3b6b7eab6070ed77222e0d3c1bcea336c381ddfc27dfdd44fe9428defa3633a5f7440191c",
    "x-catalyst-session-global": "59909a21660cac3ab91f1e49adeae2dc344ade3f56ed88e3d3e12d4defb079e429e3d66e1071c27d",
    "x-catalyst-locale":         "en",
    "x-catalyst-timezone":       "EST5EDT",
    "__uzma":                    "3aeb8b9e-4367-48e4-843f-3c5e80777437",
    "__uzmb":                    "1779363273",
    "__uzmc":                    "609111955942",
    "__uzmd":                    "1779363282",
    "__uzme":                    "6287",
    "__uzmf":                    "7f90003aeb8b9e-4367-48e4-843f-3c5e807774371-17793632739348890-0038c92d83f4bf02ce819",
    "uzmx":                      "7f9000b2a49f90-eb47-4938-87aa-0cd17f1459821-17793632739348890-ed7a6f9c70c3e09919",
    "__ssds":                    "0",
    "__ssuzjsr0":                "a9be0cd8e",
}

def fetch_page(client, meta, frag_id, filters={}):
    payload = {
        "nodeW551-filterSQL":     "contains",
        "nodeW552ac":             "",
        "DocumentContent":        "",
        "nodeW559-searchOp":      "EqualsIgnoreCase",
        "nodeW560-AnyAllFilter":  "any",
        "FilingIdentifier":       filters.get("filing_id", ""),
        "FilingCategory":         filters.get("category", "securitiesofferings"),
        "SubmissionDate":         filters.get("date_from", ""),
        "SubmissionDate2":        filters.get("date_to", ""),
        "_CBASYNCUPDATE_":        "true",
        "_CBHTMLFRAGNODEID_":     "W534",
        "_CBHTMLFRAGID_":         str(frag_id),
        "_CBHTMLFRAG_":           "true",
        "_CBNODE_":               "W563",
        "_VIKEY_":                meta["vikey"],
        "_CBNAME_":               "fireOnChange",
    }
    url = f"{BASE_URL}/csa-party/viewInstance/view.html?id={meta['view_id']}"
    r = client.post(url, data=payload)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def parse_filings(soup):
    # Inspect the HTML response in DevTools → Response tab to get real selectors
    rows = soup.select("tr.filing-row")  # placeholder — check actual class names
    filings = []
    for row in rows:
        filings.append({
            "id":       row.get("data-id"),
            "company":  row.select_one(".company-name").text.strip(),
            "doc_url":  row.select_one("a")["href"],
        })
    return filings

def download_doc(client, filing, out_dir: Path):
    out_dir.mkdir(exist_ok=True)
    r = client.get(filing["doc_url"])
    fname = out_dir / f"{filing['id']}.pdf"
    fname.write_bytes(r.content)
    print(f"  saved → {fname}")

def run(pages=3, filters={}):
    client = build_client(COOKIES)
    meta = init_session(client)
    print(f"Session OK — VIKEY: {meta['vikey'][:12]}...")

    out_dir = Path("downloads")
    frag_id = 1779362227212  # starting value from your recon — increment each page

    for page in range(pages):
        print(f"Fetching page {page + 1}...")
        soup = fetch_page(client, meta, frag_id + page, filters)
        filings = parse_filings(soup)
        
        for filing in filings:
            download_doc(client, filing, out_dir)
        
        time.sleep(1)  # be polite

    print("Done.")

if __name__ == "__main__":
    run(pages=3)