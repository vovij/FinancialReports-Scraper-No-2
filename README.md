# SEDAR+ Scraper

A raw-HTTP scraper for [SEDAR+](https://www.sedarplus.ca), the Canadian regulatory filing database. Built with `httpx` and `BeautifulSoup`. No browser automation.

---

## How it works

SEDAR+ is a Catalyst/OpenText portal — a server-side widget framework that manages state through a session key (`_VIKEY_`) and sends partial HTML back via AJAX POSTs rather than clean JSON API responses. Every page navigation is a POST to `update.html` that re-renders one widget subtree. This shapes the entire approach.

### Session bootstrap (`load_page1`)

1. **Warm Imperva** — a GET to `/home/` establishes the Imperva bot-protection cookie (`TS01bfbdd0`) before touching any functional endpoint.
2. **Create session** — GET to `/csa-party/service/create.html` with `service=searchDocuments` triggers a 302 redirect to `view.html?id=<hex>`. The hex `view_id` is extracted from the redirect URL via regex and is the anchor for all subsequent requests.
3. **Load page 1** — GET `view.html?id={view_id}` returns the full initial HTML. Three values are extracted from it dynamically:
   - `_VIKEY_` — the Catalyst session token, pulled first from a hidden `<input name="_VIKEY_">` and falling back to a regex on the raw source.
   - `_CBNODE_` — the widget node ID that owns the `selectPage` callback (e.g. `W1030`). Found via `'(W\d+)','selectPage'` in the source. Falls back to `W1030` if not found.
   - `_CBHTMLFRAGNODEID_` — the async wrapper node ID (e.g. `W167`). Found via `AsyncWrapper(W\d+)`. Falls back to `W167`.

All three are dynamic per session — nothing is hardcoded.

### Pagination (`fetch_page`)

Page turns POST to `update.html?id={view_id}` with a Catalyst AJAX payload:

```
_VIKEY_            = <session token>
_CBNODE_           = <results widget node>
_CBNAME_           = selectPage
_CBVALUE_          = <target page number>
_CBASYNCUPDATE_    = true
_CBHTMLFRAG_       = true
_CBHTMLFRAGNODEID_ = <async wrapper node>
_CBHTMLFRAGID_     = <timestamp millis>
```

The server returns a partial HTML fragment — only the re-rendered widget subtree — which is parsed directly with BeautifulSoup.

### Parsing (`parse_filings`)

Selects `tr.appTblRow` rows, skipping header rows. Extracts:
- Company name from `a.appMenuItem span.appReceiveFocus`
- Document name and URL from `a.appDocumentLink`

### Download (`download`)

Streams each document URL with the same session client (cookies intact). Filenames are sanitised and de-duplicated with a counter suffix.

---

## Usage

```bash
# Install dependencies (requires uv)
uv sync

# Scrape 5 pages and download documents (default)
python scraper.py

# Scrape more pages
python scraper.py --pages 10

# List filings only, skip downloads
python scraper.py --no-download
```

Downloaded files land in `downloads/`.

---

## Filters / historical backfills (Level 3)

Not implemented within the time budget, but here's how I'd approach it.

SEDAR+ filter state is submitted via the same Catalyst POST mechanism. When you apply a filter in the browser (e.g. "Issuer Name" = "Shopify"), the form widget fires a `selectFilter` or `applyFilter` callback — a POST to `update.html` with `_CBNAME_=applyFilter` and the filter criteria in `_CBVALUE_` or a set of auxiliary form fields. The first step is to capture one such request in browser devtools to identify the exact field names (Catalyst often uses generated names like `W1031_filterField`).

With those in hand, the approach would be:
1. After `load_page1()`, send an additional POST with the filter payload before starting the page loop.
2. The server responds with an updated widget fragment confirming the filter is active and showing a new result count.
3. The existing pagination loop then works unchanged — it walks whatever result set the filter left active.

For a full backfill runner you'd wrap this in a list of (company, date-range) tuples and iterate, re-bootstrapping the session between runs to avoid state bleed.

---

## Notes & known limitations

- **`_VIKEY_` rotation** — Catalyst can issue a new `_VIKEY_` on certain state transitions. The scraper uses the initial token throughout; if a session mid-run returns a new token in its response, it would need to be picked up and threaded forward. Not observed in testing, but worth watching.
- **Selector fragility** — `a.appDocumentLink` and `a.appMenuItem` are stable Catalyst class names, but a portal upgrade could rename them. A retry with a broader row-level selector would be a good addition.
- **Rate limiting** — A 1.2 s sleep between pages is conservative. Imperva fingerprints more on TLS/header consistency than raw timing, but backing off further is easy via `--sleep`.
- **No retries** — Downloads fail hard. Production use would want `tenacity` or a manual retry loop.