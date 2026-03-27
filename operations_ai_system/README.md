# Intelligent Analysis System for Rappi Operations

## Overview
This repository contains the solution for the Rappi Technical Case: Intelligent Analysis System for Operations. The system consists of two primary deliverables designed to democratize access to operational data and automate insights generation for the Strategy, Planning & Analytics (SP&A) and Operations teams.

1. **Data Conversational Bot (70%)**: A Streamlit-based natural language interface that allows non-technical users to query complex operational metrics, trends, and correlations safely.
2. **Automatic Insights System (30%)**: A Python script (`generate_report.py`) that analyzes weekly data to automatically flag anomalies, concerning trends, benchmarks, and correlations, exporting the findings into an executive HTML report.

---

## 🚀 Quickstart & Setup

### Prerequisites
- Python 3.9+
- The `data/rappi_data.xlsx` file provided for the challenge must be placed in the `data/` directory.

### Installation
1. Clone the repository and navigate to the project root.
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables by copying `.env.example` to `.env` and adding your OpenAI API key:
   ```bash
   cp .env.example .env
   # Edit .env and set OPENAI_API_KEY=sk-...
   ```

### Running the System
**To run the Data Conversational Bot UI:**
```bash
streamlit run app.py
```

**To generate the Automatic Insights Report:**
```bash
python generate_report.py
```
*(The generated HTML report will be saved to the `reports/` directory)*

---

## 🏗 Architecture & Technical Design

### Design Philosophy: Structured Intent Parsing
The system leverages a strict **Structured Intent Parsing** architecture. Instead of allowing the LLM to write and execute arbitrary code (which is prone to hallucinations and security risks like `eval()`), the architecture strictly separates the reasoning layer from the execution layer.

**The Pipeline:**
`User Question → [Intent Parser (GPT-4o, temp=0)] → JSON Intent → [Query Executor (pandas)] → DataFrame → [Response Narrator (GPT-4o, temp=0.3)] → Business Language → [Streamlit UI] → Text + Plotly Chart`

### Decision Justifications
- **LLM Choice (OpenAI GPT-4o)**: Selected for its exceptional instruction-following capability and JSON mode reliability. Since the architecture relies heavily on strict JSON schema outputs for the *Intent Parser*, GPT-4o ensures the highest accuracy in mapping complex natural language to our 6 deterministic query types.
- **Execution Engine (Pandas)**: Data operations are executed deterministically using Pandas. This guarantees 100% accurate mathematical calculations for critical business metrics without the unpredictability of LLM-generated math.
- **Frontend Framework (Streamlit)**: Chosen for its rapid prototyping capabilities in Python, native support for Pandas DataFrames, and seamless integration with Plotly for interactive charts. It allows for an immediate, functional prototype focusing on the data rather than boilerplate web development.
- **Visualization (Plotly)**: Provides highly interactive, out-of-the-box charts that allow operational managers to hover, zoom, and inspect data points intuitively, which is essential for business reporting.

---

## ⚙️ How It Works

### The Data Conversational Bot
The bot supports 6 core query types handled by deterministic pandas functions:
1. `filter_rank`: Top/bottom N zones by metric.
2. `compare`: Metric comparisons grouped by `ZONE_TYPE` or `COUNTRY`.
3. `trend`: Time-series evolution over available weeks.
4. `aggregate`: Averages or medians by specific segments.
5. `multivariable`: Identifies zones meeting conditions across multiple metrics simultaneously.
6. `order_growth`: Analyzes zones with the highest order growth and cross-references them with metric correlations.

### The Automatic Insights System
The script `generate_report.py` executes predefined analytical detectors across the entire dataset:
- **Anomalies**: Flags zones with drastic week-over-week changes (`>10%` deterioration or improvement).
- **Concerning Trends**: Identifies metrics in consistent deterioration for 3 or more consecutive weeks.
- **Benchmarking**: Compares similar zones (by Country + Zone Type) to surface entities performing `>1 standard deviation` below their group mean.
- **Correlations**: Calculates Pearson correlation matrices on pivoted metrics to surface significant relationships (e.g., low Lead Penetration correlating with low Conversion).

---

## 💰 API Costs & Usage

The system is optimized for cost-efficiency by using the LLM strictly for parsing and narrating, rather than reading the entire dataset into the prompt context.

**Estimated Cost per Use (Using `gpt-4o`):**
- **Data Bot Query**: ~$0.01 - $0.02 per query.
  - *Intent Parsing*: Small prompt + JSON output (~500 tokens).
  - *Narration*: Executed data summary + Business language output (~800 tokens).
- **Automatic Insights System**: $0.00 (Current implementation)
  - The insights generation is handled entirely locally using Pandas and Numpy. No LLM calls are made during the detection phase, ensuring the pipeline can run infinitely without API costs.

---

## 🔮 Limitations & Next Steps

If granted more time, the following improvements would be prioritized:
1. **Dynamic Schema Updating**: Currently, the system loads `L#W` columns dynamically, but the prompt's knowledge of the metrics is somewhat static. Implementing a lightweight Vector DB (e.g., Chroma) to map user queries to the data dictionary dynamically would improve zero-shot accuracy on unseen metrics.
2. **Cloud Deployment & CI/CD**: Containerize the application using Docker and set up automated deployments to Google Cloud Run or AWS App Runner for scalable team access.
3. **Advanced Caching**: Implement robust caching (e.g., Redis or Streamlit's `@st.cache_data`) for the query executor to prevent re-calculating the same DataFrames for identical intents, significantly speeding up response times.
4. **Automated Alerting**: Integrate the Insights System with Slack or an Email API (SendGrid) to push the executive report directly to operational managers every Monday morning.
