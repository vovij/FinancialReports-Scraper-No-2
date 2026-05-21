import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.sedarplus.ca"
SEARCH_ENTRY = "https://www.sedarplus.ca/csa-party/parties/search/enhanced-search.html"

def build_client(manual_cookies: dict) -> httpx.Client:
    return httpx.Client(
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.sedarplus.ca/home/",
        },
        cookies=manual_cookies,
        follow_redirects=True,
        timeout=30.0
    )

def init_session(client: httpx.Client) -> dict:
    """
    Hit the search entry point — it redirects to a fresh view.html?id=<session_id>
    Extract that ID + _VIKEY_ from the landed page.
    """
    r = client.get(SEARCH_ENTRY)
    r.raise_for_status()

    print(f"Final URL: {r.url}")          # add this
    print(f"Page title: {BeautifulSoup(r.text, 'html.parser').title.text}")  # and this

    # The final URL after redirect contains the fresh session view_id
    view_id = str(r.url).split("id=")[-1].split("&")[0]
    print(f"Got fresh view_id: {view_id[:16]}...")

    soup = BeautifulSoup(r.text, "html.parser")
    vikey_input = soup.find("input", {"name": "_VIKEY_"})
    vikey = vikey_input["value"] if vikey_input else None

    return {
        "view_id": view_id,
        "vikey": vikey,
        "base_url": BASE_URL,
    }