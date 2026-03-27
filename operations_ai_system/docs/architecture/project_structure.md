# Project Structure — Operations AI System

## Module Responsibilities

### `src/data_loader.py`
Loads and normalizes the Excel data. Single responsibility: read `data/rappi_data.xlsx`, return clean DataFrames with consistent column naming.

- Loads RAW_INPUT_METRICS, RAW_ORDERS, RAW_SUMMARY
- Normalizes week columns (both `_ROLL` and non-`_ROLL` variants mapped to a common `L{n}W` format internally)
- Caches loaded data (loaded once at app startup via `@st.cache_data`)
- Exposes: list of valid metric names, countries, cities, zones, zone types

### `src/prompts.py`
All LLM prompts in one place. No business logic, no API calls — just prompt templates.

- `INTENT_PARSER_SYSTEM_PROMPT`: schema context + metrics dict + few-shot examples → structured JSON
- `RESPONSE_NARRATOR_PROMPT`: DataFrame result + question → business language answer
- `SUGGESTION_PROMPT`: generates follow-up questions

### `src/llm_client.py`
OpenAI API wrapper. Handles:

- API calls with retry logic
- Conversation memory (last 6 turns)
- Last intent storage for follow-up resolution
- JSON parsing with fallback

### `src/query_engine.py`
The core. Two phases:

1. **Intent Parsing**: calls LLM client → gets JSON → validates metric names (fuzzy match) → returns structured intent
2. **Query Execution**: deterministic pandas functions for each of the 6 query types. No LLM involvement in execution — pure pandas.

### `app.py`
Streamlit chat UI. Orchestrates the flow:

User input → query_engine.parse_intent() → query_engine.execute() → llm_client.narrate() → display result + optional chart

### `generate_report.py`
Automatic insights system. Runs all 4 detectors (anomalies, trends, benchmarks, correlations) and renders an HTML executive report via Jinja2 template.

## Data Flow

```
rappi_data.xlsx
     │
     ▼
[data_loader] ──→ df_metrics (12,573 rows), df_orders (1,242 rows)
     │                              │
     │                              │
     ▼                              ▼
[query_engine]                [generate_report]
  ├─ parse_intent() ← LLM       ├─ detect_anomalies()
  ├─ execute_filter_rank()       ├─ detect_trends()
  ├─ execute_compare()           ├─ benchmark_zones()
  ├─ execute_trend()             ├─ compute_correlations()
  ├─ execute_aggregate()         └─ render_html_report()
  ├─ execute_multivariable()
  └─ execute_order_growth()
     │
     ▼
[llm_client.narrate()] → business language response
     │
     ▼
[app.py / Streamlit] → chat UI + charts
```

## Design Decisions

1. **Structured intent parsing over text-to-pandas**: safer (no eval), more predictable, easier to debug and test
2. **Long format preserved**: we don't reshape the entire DataFrame at load time — only pivot when needed (multivariable queries)
3. **Prompts separated from logic**: `prompts.py` is pure templates, making it easy to iterate on prompts without touching business logic
4. **Conversation memory in LLM client**: keeps the query engine stateless — memory is injected as context
