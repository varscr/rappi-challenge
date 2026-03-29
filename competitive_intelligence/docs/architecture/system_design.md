# System Design — Competitive Intelligence

## 1. System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        PIPELINE FLOW                             │
│                                                                  │
│  mexico_addresses.csv     Rate Limiter (5-15s)                   │
│         │                      │                                 │
│         v                      v                                 │
│  ┌─────────────┐    ┌──────────────────┐    ┌────────────────┐   │
│  │ Orchestrator │───>│   BaseScraper    │───>│ Pydantic v2    │   │
│  │  (main.py)  │    │   (ABC)          │    │ ScrapedStore   │   │
│  └─────────────┘    │                  │    │ ScrapedProduct │   │
│                     │  ┌─────────────┐ │    └───────┬────────┘   │
│                     │  │RappiScraper │ │            │            │
│                     │  │UberScraper  │ │            v            │
│                     │  │DiDiScraper  │ │    ┌────────────────┐   │
│                     │  └─────────────┘ │    │ JSON Output    │   │
│                     └──────────────────┘    │ (data/raw/)    │   │
│                                             └───────┬────────┘   │
│                                                     │            │
│                                                     v            │
│                                             ┌────────────────┐   │
│                                             │   Streamlit    │   │
│                                             │  Dashboard     │   │
│                                             │  (app.py)      │   │
│                                             └────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

## 2. Scraping Strategies

Each platform requires a different extraction approach due to varying anti-bot measures and data exposure patterns.

### 2.1 Rappi — Cookie Teleportation + SSR Parsing

```
Browser Context
    │
    ├── 1. Fetch homepage (establish session)
    ├── 2. Inject Base64 `currentLocation` cookie (lat/lon/address)
    ├── 3. Fetch /search?query=mcdonalds (network_idle)
    ├── 4. Decode response.body (bytes, not .text)
    ├── 5. Extract <script id="__NEXT_DATA__"> JSON
    ├── 6. Navigate props.pageProps.fallback → find stores list
    └── 7. Match McDonald's → extract products, fees, ETA
```

**Key insight**: Rappi uses Next.js SSR. The `__NEXT_DATA__` script tag contains the full page state as JSON, eliminating the need for fragile CSS selectors.

**Anti-bot bypass**: Location is set via cookie injection ("teleportation") rather than UI interaction, avoiding DataDome overlays.

### 2.2 Uber Eats — Two-Phase API + JSON-LD

```
Playwright Browser
    │
    ├── Phase 1: Search Feed
    │   ├── Navigate to /search?q=mcdonalds&pl=<base64>
    │   ├── Intercept getSearchFeedV1 API response
    │   └── Extract: store name, ETA, availability, promotions
    │
    └── Phase 2: Store Page
        ├── Navigate to store URL from actionUrl
        ├── Parse <script type="application/ld+json">
        ├── Find @type=Restaurant schema
        └── Extract: hasMenu → hasMenuSection → hasMenuItem → offers.price
```

**Key insight**: Uber Eats embeds structured data using schema.org JSON-LD (`@type: Restaurant`), providing reliable product prices without scraping DOM elements.

**No auth required**: All data is publicly accessible via SSR.

### 2.3 DiDi Food — Authenticated API Interception

```
Playwright Browser
    │
    ├── 1. Inject `ticket` cookie (session auth)
    ├── 2. Set localStorage: pl (Base64 location), ticket
    ├── 3. Navigate to /es-MX/food/feed/?pl=<base64>
    ├── 4. Intercept /feed/indexV2 → store list (delivery fee, ETA, status)
    ├── 5. Click McDonald's or navigate to /food/store/<shopId>/
    ├── 6. Intercept /shop/index → full menu (cateInfo[].items[])
    └── 7. Extract products (prices in centavos, divide by 100)
```

**Key insight**: DiDi requires a valid session ticket. The scraper mirrors the browser's authenticated state by injecting cookies and localStorage, then intercepts the internal API responses that the SPA consumes.

**Price format**: DiDi returns prices in centavos (e.g., `18900` = $189.00 MXN). `specialPrice = -0.01` means no discount.

## 3. Data Model

```
ScrapedStore
├── platform: str              # "Rappi" | "Uber Eats" | "DiDi Food"
├── store_name: str            # "McDonald's Polanco"
├── address_name: str          # "Polanco, CDMX"
├── lat, lon: float            # Geocoordinates
├── delivery_fee: float        # MXN, before discounts
├── service_fee: float         # MXN, platform commission
├── estimated_time: str        # "20-30 min"
├── time_minutes: int          # Normalized integer for analysis
├── availability: bool         # Store currently accepting orders
├── source_type: str           # "SSR" | "API" | "DOM"
├── active_discounts: list[str]
├── scraped_at: datetime       # UTC timestamp
├── products: list[ScrapedProduct]
│   ├── name: str
│   ├── price: float           # Current price in MXN
│   ├── original_price: float? # Before discount (None if no discount)
│   ├── category: str
│   └── status: str            # "available" | "out_of_stock"
└── total_final_price: float   # Computed: sum(products.price) + fees
```

All fields validated via Pydantic v2 constraints (`ge=0` for prices/fees, timezone-aware datetime).

## 4. Anti-Detection Approach

| Layer | Technique |
|-------|-----------|
| **Browser fingerprint** | browserforge generates realistic browser profiles |
| **TLS fingerprint** | curl_cffi mimics real browser TLS/JA3 handshakes |
| **Adaptive selectors** | scrapling learns DOM changes between runs |
| **Rate limiting** | Random 5-15s delays between requests (configurable via env) |
| **Locale/UA** | Each context sets `locale="es-MX"` and a realistic User-Agent |
| **Geolocation** | Playwright permission grants + coordinate injection |

## 5. Dashboard Architecture

The Streamlit app (`src/app.py`) loads the most recent JSON from `data/raw/` and presents:

1. **KPI row** — zones scraped, avg delivery fees per platform
2. **Delivery fee comparison** — box plot across platforms
3. **ETA comparison** — box plot across platforms
4. **Big Mac price by zone** — grouped bar chart
5. **Total final price** — grouped bar chart
6. **Geographic map** — Folium with per-platform color coding
7. **Avg fee by city** — grouped bar chart
8. **ETA by zone** — grouped bar chart
9. **Availability & promotions** — data tables
10. **Top 5 Insights** — Finding / Impact / Recommendation format

Sidebar filters: platform, city, availability toggle. Data cached with `@st.cache_data`.

## 6. Design Decisions

| Decision | Rationale |
|----------|-----------|
| **scrapling over raw Playwright** | Adaptive selectors survive DOM changes; built-in stealth engines reduce detection |
| **Pydantic over dataclasses** | Validation constraints (`ge=0`), computed fields, JSON serialization out of the box |
| **JSON over CSV** | Nested data (products list, discount arrays) maps naturally to JSON; CSV would require flattening |
| **McDonald's as reference product** | Standardized menu across all platforms and zones; enables like-for-like price comparison |
| **20 addresses across 8 cities** | Covers premium/residential/corporate/peripheral zones without excessive scraping load |
| **Playwright for DiDi/Uber** | These platforms require JS rendering and API interception that scrapling's DynamicSession alone cannot provide |
