# Rappi Operations AI System

## Overview
This repository contains a production-ready solution for the Rappi Technical Case: Intelligent Analysis System for Operations. The system provides a multi-layered analytical suite designed to democratize data access and automate operational monitoring for Rappi's global teams.

1. **Conversational Data Bot**: A secure, Streamlit-based interface that translates natural language Spanish into deterministic data insights and interactive visualizations.
2. **Automatic Insights Engine**: A robust backend system (`generate_report.py`) integrated into the UI that executes statistical anomaly detection, benchmarking, and trend analysis across thousands of zone-metric pairs.

---

## Key Features & Scalability

- **100% Spanish Localization**: The entire user experience (UI, LLM narrations, follow-up suggestions, and executive reports) is localized in professional Spanish.
- **Hyper-Dynamic Architecture**: 
    - **Dynamic Week Detection**: Automatically parses time-series data regardless of the number of weeks provided (L8W..L0W, L12W, etc.).
    - **Dynamic Dimension Mapping**: The engine identifies geographic hierarchies (Country, City, Zone) at runtime. Adding new dimensions requires zero code changes.
    - **Case-Insensitive Metric Resolution**: Dynamically finds and validates the "Metric" column and KPI names using fuzzy matching.
- **Enterprise-Grade Security**:
    - **Structured Intent Parsing**: Prevents prompt injection risks by ensuring the LLM never executes raw code (No eval()).
    - **Persona Anchoring**: System prompts utilize strict guardrails to prevent behavioral manipulation or leakage of internal instructions.
- **Advanced Analytical Logic**:
    - **True Conversational Memory**: Supports follow-up questions and meta-conversation about the chat history.
    - **Explanatory Growth Analysis**: The order growth query doesn't just show "what" changed, but joins data with KPIs like Lead Penetration to explain "why" growth is happening.

---

## Quickstart & Setup

### Prerequisites
- Python 3.12+
- OpenAI API Key (configured in .env or Streamlit Secrets)
- `data/rappi_data.xlsx` placed in the project root.

### Installation
1. Clone the repository.
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Setup environment:
   ```bash
   cp .env.example .env
   # Add your OPENAI_API_KEY to .env
   ```

### Running the System
**Chat Bot UI (Streamlit):**
```bash
streamlit run app.py
```

**Executive Insights Report:**
You can generate the report directly from the **Streamlit Sidebar** using the "🚀 Generar Nuevo Análisis" button. Alternatively, run it via CLI:
```bash
python generate_report.py
```
*(Reports are saved as professional HTML files in reports/)*

---

## 🚀 Bonus Features

### 📧 Automatic Email Reporting
The system includes a built-in email delivery system via the **Resend API**. 
- **Demo Mode**: If no `RESEND_API_KEY` is provided, the system simulates the email sending process (perfect for live presentations).
- **Production Mode**: Get a free API key at [Resend.com](https://resend.com) and add `RESEND_API_KEY` to your environment to send real HTML reports to stakeholders directly from the UI.

### 📊 Cloud-Ready Deployment
The app is fully optimized for **Streamlit Community Cloud**. It automatically detects the environment and uses `st.secrets` for API keys.

---

## ☁️ Deployment Guide (Streamlit Cloud)

1. **Push to GitHub**: Ensure your repository is public and contains `requirements.txt`.
2. **Connect to Streamlit**: Log in to [Streamlit Share](https://share.streamlit.io/) and select this repository.
3. **Set Main File**: Point to `operations_ai_system/app.py`.
4. **Configure Secrets**: In the App Settings -> Secrets, paste your keys:
   ```toml
   OPENAI_API_KEY = "sk-proj-..."
   RESEND_API_KEY = "re_..." # Optional for real emails
   ```

---

## API Costs & Usage Estimation

The system is optimized for token efficiency. Below is an estimated cost based on current OpenAI gpt-4o pricing (~$2.50/1M input, ~$10.00/1M output):

- **Per Query**: ~$0.015 USD
- **Per 10-Question Session**: ~$0.15 USD
- **Automatic Insights Report**: $0.00 (Processed locally via Pandas)

---

## Technical Design

### The Safe Logic Pipeline
The architecture follows a strict Intent -> Execute -> Narrate flow:
1. **Parser**: LLM interprets the Spanish question into a structured JSON "Intent".
2. **Executor**: Deterministic Python (Pandas) code executes the query. No LLM-generated code is ever run.
3. **Narrator**: LLM translates the raw data result back into professional Spanish business insights.

### Conversational Memory & Data Scope
- **Dialogue Follow-up**: The bot retains history to resolve pronouns (e.g., "now show it for MX") and answer meta-questions about the chat.
- **Data Horizon**: The current implementation has access to 9 weeks of rolling operational data (L8W to L0W). Queries regarding "last year" will explicitly explain this limitation based on dynamic schema detection.

### Detection Statistical Models
- **Anomalies**: Identifies drastic week-over-week changes (>20% threshold with significance filtering).
- **Trends**: Surfaces metrics in consistent deterioration (3+ weeks in a row).
- **Benchmarking**: Compares zones performing >1.5 standard deviations below their peer group mean.
- **Growth Opportunities**: Automatically identifies top-growing zones in terms of raw order volume.
