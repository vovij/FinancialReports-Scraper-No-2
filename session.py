import re
import httpx
from bs4 import BeautifulSoup

BASE_URL   = "https://www.sedarplus.ca"
SEARCH_URL = f"{BASE_URL}/csa-party/parties/search/enhanced-search.html"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
}

# Extracted from browser curl — replace when session expires
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

# Already known from the referer in the curl — skip the redirect entirely
KNOWN_VIEW_ID = "0c11f8b7998bcd966133b671f299339ae40216b61518a131"

def get_session() -> tuple[httpx.Client, dict]:
    client = httpx.Client(
        headers=HEADERS,
        cookies=COOKIES,
        follow_redirects=True,
        timeout=30.0,
    )

    # Hit the view directly — we already know the id from browser recon
    view_url = f"{BASE_URL}/csa-party/viewInstance/view.html?id={KNOWN_VIEW_ID}"
    r = client.get(view_url)
    r.raise_for_status()

    final_url = str(r.url)
    print(f"[session] landed: {final_url[:80]}...")

    if "sedarplus.ca" not in final_url:
        raise RuntimeError("Bot challenge — grab fresh cookies+view_id from browser Network tab.")

    # Re-extract view_id from final URL in case of redirect to fresh id
    m = re.search(r"[?&]id=([^&]+)", final_url)
    view_id = m.group(1) if m else KNOWN_VIEW_ID

    soup = BeautifulSoup(r.text, "html.parser")
    # Dump page for inspection
    with open("page_dump.html", "w") as f:
        f.write(r.text)
    print(f"[session] page dumped to page_dump.html ({len(r.text)} bytes)")
    print(f"[session] title: {soup.title.text if soup.title else '(none)'}")

    # Try input tag first, then JS variable
    vikey_tag = soup.find("input", {"name": "_VIKEY_"})
    if vikey_tag:
        vikey = vikey_tag["value"]
    else:
        m = re.search(r"viewInstanceKey:'([^']+)'", r.text)
        if not m:
            raise RuntimeError("No _VIKEY_ found — check page_dump.html")
        vikey = m.group(1)

    print(f"[session] view_id : {view_id}")
    print(f"[session] vikey   : {vikey[:16]}...")
    return client, {"view_id": view_id, "vikey": vikey}

if __name__ == "__main__":
    client, meta = get_session()
    print("[session] OK")