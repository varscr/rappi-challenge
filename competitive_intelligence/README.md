# Competitive Intelligence System

Automated system that collects competitive pricing data from **Rappi**, **Uber Eats**, and **DiDi Food** across 20 representative Mexican addresses and generates actionable insights via an interactive Streamlit dashboard.

Built for Rappi's Pricing, Operations, and Strategy teams.

## Quick Start

### Prerequisites

- Python 3.12+
- Chromium browser (installed via Playwright)

### Setup

```bash
cd competitive_intelligence
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|----------|----------|-------------|
| `DIDI_TICKET` | Yes (for DiDi) | Session ticket from DiDi Food browser login. See `.env.example` for instructions. |
| `WAIT_TIME_MIN` | No (default: 5) | Minimum seconds between scrape requests |
| `WAIT_TIME_MAX` | No (default: 15) | Maximum seconds between scrape requests |

### Run the Scraper

```bash
python -m src.main
```

Scrapes all 20 addresses across 3 platforms. Output saved to `data/raw/scrape_results_<timestamp>.json`.

### Launch the Dashboard

```bash
streamlit run src/app.py
```

Opens an interactive dashboard with filters, charts, geographic map, and Top 5 actionable insights.

### Run Tests

```bash
pytest tests/
```

## Architecture

```
Address CSV ──> Orchestrator (main.py)
                    │
        ┌───────────┼───────────┐
        v           v           v
   RappiScraper  UberScraper  DiDiScraper
   (SSR/Next.js) (JSON-LD)   (API intercept)
        │           │           │
        └───────────┼───────────┘
                    v
           Pydantic Validation
           (ScrapedStore model)
                    v
              JSON Output
           (data/raw/*.json)
                    v
          Streamlit Dashboard
           (src/app.py)
```

- **`src/base_scraper.py`** — Abstract base class with DynamicFetcher (Playwright) + StealthyFetcher
- **`src/scrapers/`** — Platform-specific scrapers implementing `scrape_address()`
- **`src/models.py`** — Pydantic v2 data contracts (`ScrapedStore`, `ScrapedProduct`)
- **`src/main.py`** — Pipeline orchestrator with rate limiting
- **`src/app.py`** — Streamlit dashboard with 7+ charts and dynamic insights

See [docs/architecture/system_design.md](docs/architecture/system_design.md) for detailed design documentation.

## Data Collected

| Metric | Coverage |
|--------|----------|
| Product prices (Big Mac, McNuggets, McTrio) | All 3 platforms |
| Delivery fee | All 3 platforms |
| Service fee | All 3 platforms |
| Estimated delivery time (ETA) | All 3 platforms |
| Active discounts/promotions | All 3 platforms |
| Store availability | All 3 platforms |
| Total final price (computed) | All 3 platforms |

**Geographic coverage**: 20 addresses across 8 cities (CDMX, Monterrey, Guadalajara, Puebla, Queretaro, Merida, Tijuana, Leon) — spanning premium, residential, corporate, and peripheral zone types.

## Scraping Strategies

| Platform | Technique | Auth Required |
|----------|-----------|---------------|
| **Rappi** | Cookie teleportation + `__NEXT_DATA__` SSR parsing | No |
| **Uber Eats** | `getSearchFeedV1` API + JSON-LD schema from store page | No |
| **DiDi Food** | Ticket cookie injection + `/feed/indexV2` and `/shop/index` API interception | Yes (session ticket) |

## Known Limitations

- **DiDi Food** requires a valid session ticket that expires periodically; must be refreshed manually
- Anti-bot measures (DataDome, Cloudflare) may block scraping during high-traffic periods
- Data is point-in-time snapshots, not real-time streams
- Service fee is not separately exposed in search-level data for Rappi and Uber Eats
- Geographic coverage is limited to 8 Mexican cities (20 addresses)

## Ethics and Legality

- **Rate limiting**: Random 5-15 second delays between requests to avoid server overload
- **User-Agent**: Appropriate browser fingerprints via browserforge/Playwright
- **Public data**: All data is publicly visible to any user of each platform
- **DiDi authentication**: Uses the user's own session credentials (no credential harvesting)
- **Purpose**: Built for recruitment evaluation purposes only. In a production scenario, consult Legal before deploying systematic scraping.

## Tech Stack

| Category | Tools |
|----------|-------|
| Scraping | scrapling, Playwright, curl_cffi, browserforge |
| Data validation | Pydantic v2 |
| Processing | pandas |
| Visualization | Streamlit, Plotly, Folium |
| Matching | rapidfuzz |
| Logging | loguru |
| Testing | pytest |
