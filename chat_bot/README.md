# NIRF Analytics AI Chatbot 🎓

An enterprise-grade, conversational AI analytics application for querying and visualizing the **National Institutional Ranking Framework (NIRF)** dataset (2017–2025) across all 12 ranking categories.

Powered by **Sarvam AI (`sarvam-105b`)**, **PostgreSQL**, **Streamlit**, and **Plotly**.

---

## 🌟 Key Features

1. **Natural-Language-to-SQL Engine**:
   - Ask questions in plain English (e.g., *"Top 10 institutions in Engineering in 2025"*, *"Show rank trend of IIT Madras over time"*).
   - Fast deterministic routing for common ranking questions & dataset overviews.
   - LLM generation powered by Sarvam AI (`sarvam-105b`).
   - Contextual follow-up memory (e.g., *"Now show only Tamil Nadu"*).

2. **Enterprise SQL Security**:
   - Strictly enforces read-only `SELECT` queries with AST parsing via `sqlglot`.
   - Read-only PostgreSQL transactions with strict 5-second execution timeouts.
   - Schema and table whitelisting (`public."NIRF"` only).
   - Star queries (`SELECT *`) and multi-statement queries are blocked.

3. **Modern AI Chat Interface**:
   - ChatGPT / Perplexity inspired minimal UI with responsive design.
   - Clickable suggested question chips on the welcome screen.
   - Full conversation history with "New Chat" and "Clear Conversation" controls.
   - 4-tab structured assistant responses:
     - 📊 **Interactive Visualization**: Inferred Plotly charts or India state choropleth map.
     - 📋 **Results Table**: Interactive table with CSV export.
     - 🔍 **Generated SQL**: Transparent view of executed SQL.
     - 💻 **Plot Code**: Standalone downloadable Python plotting script.

4. **Rich Interactive Visualizations**:
   - **Supported Chart Types**: Bar Chart, Line Chart, Area Chart, Scatter Plot, and India State-Level Choropleth Maps.
   - **User Controls**: Switch chart types, change X/Y axes, select color/grouping columns, and adjust displayed row count.
   - Automatic reversal for rank axes (so Rank #1 is at the top).

---

## 📁 Project Structure

```
code/
├── app.py                      # Main entrypoint to run the Streamlit app
├── streamlit_ui.py             # Modern UI component & page renderer
├── test_sql.py                 # CLI diagnostic script to test PostgreSQL queries
├── load_dataset.py             # Optional helper to load CSV into PostgreSQL
├── requirements.txt            # Python dependencies
├── .env.example                # Template for environment variables
├── .env                        # Local secrets (API keys & DB connection)
│
├── nirf/                       # Geospatial & mapping module
│   ├── __init__.py
│   └── maps.py                 # India state GeoJSON loader & choropleth generator
│
├── nirf_chatbot/               # Core chatbot backend package
│   ├── __init__.py
│   ├── Settings.py             # Environment configuration (Sarvam key, DB URL)
│   ├── database.py             # SQLAlchemy engine setup with connection pooling
│   ├── llm.py                  # Sarvam AI ChatSarvam model initialization
│   ├── prompts.py              # System prompts & guidelines
│   ├── sql_engine.py           # SQL generation prompt & few-shot examples
│   ├── sql_validator.py        # SQL AST validation, normalization, and safety
│   ├── sql_executor.py         # Read-only execution with timeouts & limits
│   ├── answer_engine.py        # Grounded answer generation & fallback handlers
│   ├── visualization.py        # Chart inference, Plotly figure builder, & code gen
│   └── chat_service.py         # Central orchestrator (process_question entrypoint)
│
└── data/                       # Directory for NIRF dataset files
```

---

## 🚀 Setup & Installation

### 1. Prerequisites
- Python 3.10+ (Python 3.11–3.13 recommended)
- A running PostgreSQL instance with the NIRF dataset
- A Sarvam AI API key

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` and set your credentials:
```env
SARVAM_API_KEY=your_sarvam_api_key_here
DATABASE_URL=postgresql://username:password@localhost:5432/nirf_db
```

### 4. (Optional) Load CSV to PostgreSQL
If your PostgreSQL database does not already have the `public."NIRF"` table loaded, run:
```bash
python load_dataset.py --csv path/to/nirf_2017_2025_unified.csv
```

### 5. Verify Database Connection
Test your database connection and verify query execution:
```bash
python test_sql.py 'SELECT "Year", "Category", "Institution_Name", "Rank_Numeric" FROM public."NIRF" LIMIT 5'
```

### 6. Run the Application
Launch the Streamlit interface:
```bash
streamlit run app.py
```
Or:
```bash
streamlit run streamlit_ui.py
```
Open `http://localhost:8501` in your browser.

---

## 💬 Sample Queries

- **Rankings**: *"Show the top 10 institutions in Engineering in 2025"*
- **Specific Institutions**: *"What is the rank of IIT Madras in 2024?"*
- **Institution Comparisons**: *"Compare IIT Bombay and IIT Delhi over the years"*
- **Ranking Trends**: *"Plot the ranking trend of IIT Madras from 2017 to 2025"*
- **State Analytics**: *"Which states have the most institutions in the top 100?"*
- **Choropleth Maps**: *"Show the average score by state on an India map"*
- **Multi-Year Movement**: *"Which institutions improved their rankings between 2024 and 2025?"*

