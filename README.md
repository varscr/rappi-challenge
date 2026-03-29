# Rappi AI Engineer — Technical Challenge


Two independent technical cases solving real Rappi problems: competitive market intelligence and operational AI analysis.

**Author**: Fabio Vargas
**Position**: AI Engineer

## Videos explaining the challenges

Operations AI System: [text](https://kommodo.ai/recordings/KezRcqOUuXMiE3wAew8P?onlyRecording=1)

Competitive Intelligence: [text](https://kommodo.ai/recordings/X1b6PpeYXIYS3ualRHQf)

---

## Case 1: Competitive Intelligence System

> **Goal**: Automated scraping of Rappi, Uber Eats, and DiDi Food across 20 Mexican addresses to generate actionable pricing and operational insights.

**Highlights**:
- 3 platforms scraped with real data (no mocks) using Playwright + scrapling
- 36 records across 8 cities, 7 competitive metrics per record
- Interactive Streamlit dashboard with 7+ charts and Top 5 insights (Finding / Impact / Recommendation)
- Cookie teleportation, SSR parsing (__NEXT_DATA__), JSON-LD extraction, API interception

```bash
cd competitive_intelligence
source .venv/bin/activate
python -m src.main          # Run scraper
streamlit run src/app.py    # Launch dashboard
```

Full documentation: [competitive_intelligence/README.md](competitive_intelligence/README.md)

---

## Case 2: Operations AI System

> **Goal**: Intelligent analysis system with a conversational bot (Spanish) and automatic insights engine over Rappi operational data.

**Highlights**:
- Structured Intent Parsing pipeline — LLM (GPT-4o) outputs JSON intents, never executes code
- 6 query types: filter, group, rank, trend, compare, summarize
- Automatic executive HTML report with anomalies, trends, correlations, and growth opportunities
- Built-in email delivery via Resend API

**Live Demo**: [varscr-rappi-challenge-operations-ai-systemapp-bxpmzi.streamlit.app](https://varscr-rappi-challenge-operations-ai-systemapp-bxpmzi.streamlit.app/)

```bash
cd operations_ai_system
source .venv/bin/activate
streamlit run app.py              # Conversational bot
python generate_report.py         # Executive report
```

Full documentation: [operations_ai_system/README.md](operations_ai_system/README.md)

---

## Repository Structure

```
rappi-challenge/
├── competitive_intelligence/    # Case 1: Competitive scraping + dashboard
│   ├── src/
│   │   ├── scrapers/            # Rappi, Uber Eats, DiDi Food
│   │   ├── main.py              # Scraping pipeline
│   │   └── app.py               # Streamlit dashboard
│   ├── data/
│   │   ├── geography/           # 20 geocoded addresses
│   │   └── raw/                 # Scrape results (JSON)
│   └── docs/architecture/
│
├── operations_ai_system/        # Case 2: Conversational bot + insights
│   ├── src/
│   │   ├── query_engine.py      # Intent parsing + pandas executors
│   │   ├── llm_client.py        # OpenAI wrapper
│   │   └── data_loader.py       # Excel loader
│   ├── app.py                   # Streamlit chatbot
│   ├── generate_report.py       # HTML report generator
│   └── data/
│       └── rappi_data.xlsx      # Operational dataset
│
└── README.md                    # This file
```

## Tech Stack

| Area | Tools |
|------|-------|
| **Scraping** | scrapling, Playwright, curl_cffi, browserforge |
| **LLM** | OpenAI GPT-4o (structured intent parsing) |
| **Data** | Pydantic v2, pandas |
| **Visualization** | Streamlit, Plotly, Folium |
| **Testing** | pytest |

## AI Tools Used

This project was developed with the assistance of AI-powered engineering tools:

- **Claude Code**: Architectural design, complex refactoring, and core logic implementation.
- **Gemini CLI**: Rapid UI iterations and collaborative programming sessions.
- **OpenCode**: Codebase navigation and structural analysis.

## Prerequisites

- Python 3.12+
- OpenAI API Key (Case 2)
- Chromium browser via Playwright (Case 1)

Each case has its own virtual environment and requirements. See the individual READMEs for setup instructions.
