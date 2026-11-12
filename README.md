# Hazardous Waste Management Platform (D2S-MTP)

> **Wet Laboratory Chemical Hazard Classification, Physical Containment Segregation, and Regulatory Compliance Planning System**  
> *M.Tech Project (D2S-MTP) — Automated Environmental Health & Safety (EHS) Operations*

[![Live Web Application](https://img.shields.io/badge/Live%20Demo-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://hazardous-waste-management-yxpo.onrender.com)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![OpenRouter](https://img.shields.io/badge/LLM-OpenRouter%20Nemotron-6366F1?style=flat)](https://openrouter.ai/)
[![Tests](https://img.shields.io/badge/Tests-77%20passing%20(unittest)-brightgreen?style=flat)](tests/)
[![Tailwind CSS](https://img.shields.io/badge/UI-Tailwind%20%2B%20Alpine.js-38B2AC?style=flat&logo=tailwindcss&logoColor=white)](index.html)

---

## 🌐 Live Web Application

The live, fully functional application is hosted and accessible online at:

🔗 **[https://hazardous-waste-management-yxpo.onrender.com](https://hazardous-waste-management-yxpo.onrender.com)**

> [!NOTE]
> When hosted on Render's free tier, the web service may spin down after periods of inactivity. If visiting after an idle period, please allow **30–50 seconds** for the initial cold start.

---

## 📋 Overview

Academic and industrial research wet laboratories generate complex, high-risk chemical and biological waste streams. Improper identification, incompatible mixing, or non-compliant storage can trigger violent exothermic reactions, toxic gas releases, laboratory fires, and severe regulatory penalties.

The **Hazardous Waste Management Platform (D2S-MTP)** is an end-to-end laboratory EHS orchestration tool designed to automate:
1. **Multi-Hazard Characterization**: Rapid evaluation across physical, chemical, and biological hazard classes.
2. **Physical Storage Cabinet Allocation**: Deterministic segregation into dedicated laboratory storage cabinets to prevent adverse co-mingling.
3. **Dual-Regulatory Compliance Synthesis**: Tailored management plans complying with both the **US EPA RCRA (40 CFR 261)** framework and the **Indian Hazardous and Other Wastes (HOWM) Rules, 2016**.
4. **Institutional Reporting**: Multi-sheet, audit-ready Excel workbooks generated directly for compliance inspection.

---

## ✨ Key Features

### 🔍 1. Single Chemical Instant Dossier Lookup
- Instant search bar supporting IUPAC names, common chemical nomenclature, laboratory reagents, and common solvent mixtures.
- Generates a 14-point compliance dossier covering recommended containers, PPE, storage protocols, spill response, incompatible substances, and regulatory classifications.

### 📁 2. Automated Batch Manifest Ingestion
- Upload real-world lab chemical inventories in Excel (`.xlsx` or `.xls`) format.
- Intelligent header detection automatically maps diverse column names (e.g., `Chemical`, `Waste Name`, `Chemical Discarded`, `Item Name`).
- Automatically cleanses, normalizes, and de-duplicates chemical records prior to processing.

### ⚡ 3. Real-Time Streaming Stepper (Server-Sent Events)
- Two-stage live streaming pipeline powered by FastAPI Server-Sent Events (SSE):
  - **Stage 1 (Classification)**: High-speed classification of each chemical across 5 hazard vectors (Flammable, Corrosive, Toxic, Carcinogenic, Infectious).
  - **Optional Classification Review Pause**: Allows EHS officers to inspect and verify preliminary hazard tags before generating disposal dossiers.
  - **Stage 2 (Planning)**: Comprehensive regulatory and handling synthesis (containment, PPE, spill measures, RCRA codes, HOWM schedules, treatment, disposal).
- Live progress bars, step indicators, and streaming event updates in the UI.

### 🗄️ 4. Physical Storage Cabinet Segregation (Swimlanes & Grid Views)
Deterministic rule-based allocation of waste items into dedicated physical containment zones:
- 🔴 **Flammable Solvents**: Dedicated fire-rated yellow safety cabinets.
- 🟡 **Inorganic Acids**: Polyethylene-lined acid storage with dedicated secondary containment.
- 🔵 **Inorganic Bases**: Separate corrosive base storage segregated from mineral acids.
- 🟣 **Carcinogenic & Toxic Organics**: Ventilated, lockable hazardous materials containment.
- 🟢 **Biohazard & Infectious**: Designated autoclave collection and biohazard receptacles.
- ⚪ **Safety Review Queue**: Isolated quarantine for ambiguous nomenclature or items requiring human EHS intervention.

### ✏️ 5. In-Place Chemical Remediation & Re-assessment
- Interactive remediation modal within the UI allows users to rename, correct, or refine ambiguous chemical names directly in the Review Queue.
- Atomically re-runs classification and planning for the single item and automatically reallocates it into the correct physical containment cabinet without needing to re-process the entire batch.

### 📊 6. Institutional Multi-Sheet Excel Exports
Exports professionally styled, multi-sheet Excel spreadsheets directly from any batch run:
- **Comprehensive Waste Management Plan** (`hazardous_waste_management_plan_{run_id}.xlsx`):
  1. *Complete Management Plan*: 14 compliance columns for all processed chemicals.
  2. *Segregation Bins*: Grouped chemical inventory sorted by physical cabinet allocation.
  3. *Review Queue*: Segregated log of unclassified or flagged items requiring manual verification.
- **Hazard Classification Matrix** (`hazardous_waste_classification_{run_id}.xlsx`):
  1. *Hazard Matrix*: Boolean breakdown across Flammable, Carcinogenic, Infectious, Toxic, and Corrosive categories.
  2. *Category Summary*: Aggregate counts and percentage distribution.

### 🎛️ 7. Flexible Deployment Architecture
- Seamless operation as a full-stack unified app (FastAPI serving static frontend) or as a decoupled client-server architecture.
- Frontend includes a **Backend Configuration Modal (⚙️)** allowing the UI (e.g., hosted statically on GitHub Pages) to target any remote API instance.

---

## 🏛️ Regulatory Compliance Standards

| Regulatory Standard | Scope & Implementation |
| :--- | :--- |
| **US EPA RCRA**<br>*(40 CFR Part 261)* | • **Characteristic Waste Identification**: Ignitability (D001), Corrosivity (D002), Reactivity (D003), and Toxicity Characteristic Leaching Procedure (D004–D043).<br>• **Listed Wastes**: F-List (spent solvents), K-List, P-List (acutely hazardous chemicals), and U-List toxic commercial chemical products.<br>• **Accumulation Rules**: Satellite Accumulation Areas (SAA) vs Central Accumulation Areas (CAA) compliance. |
| **Indian HOWM Rules, 2016**<br>*(Hazardous & Other Wastes Management)* | • **Schedules I, II & III**: Identification of process-specific waste categories and concentration thresholds.<br>• **Form 10 Manifest Protocols**: Statutory manifest tracking for transportation to authorized TSDFs.<br>• **Treatment & TSDF Routing**: Mandated pathways including secured landfilling (SLF), common hazardous waste incineration (CHWI), or co-processing in cement kilns. |

---

## 🏗️ System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        User Web Interface                              │
│              (Tailwind CSS + Standalone Alpine.js)                     │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │ HTTP / REST & Server-Sent Events (SSE)
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       FastAPI Application Core                         │
│                           (src/app.py)                                 │
└───────┬─────────────────────────┬───────────────────────────────┬──────┘
        │                         │                               │
        ▼                         ▼                               ▼
┌──────────────┐          ┌──────────────┐                ┌──────────────┐
│ Ingestion &  │          │ Segregation  │                │ Excel Export │
│ Deduplication│          │ Rule Engine  │                │ Generator    │
│(src/services)│          │(src/models)  │                │ (OpenPyXL)   │
└───────┬──────┘          └───────┬──────┘                └──────────────┘
        │                         │
        ▼                         ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     LLM Orchestration Layer                            │
│                      (src/llm_client.py)                               │
│   • OpenRouter API Client (nvidia/nemotron-3-ultra-550b-a55b:free)     │
│   • Pydantic Function Tool Calling & Strict Schema Enforcement         │
│   • Resilient Markdown JSON Fallback Parser                            │
│   • Exponential Backoff & Jitter for 429/503 Transient Handling       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

- **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) with [Uvicorn](https://www.uvicorn.org/) (ASGI web server)
- **Programming Language**: Python 3.12
- **Data Validation & Modeling**: [Pydantic v2](https://docs.pydantic.dev/latest/)
- **LLM Provider & Orchestration**: [OpenRouter API](https://openrouter.ai/) (`nvidia/nemotron-3-ultra-550b-a55b:free` default model) via the OpenAI Python SDK
- **Data Manipulation & Ingestion**: [Pandas](https://pandas.pydata.org/)
- **Spreadsheet Generation**: [OpenPyXL](https://openpyxl.readthedocs.io/)
- **Frontend**: Single-file reactive frontend (`index.html`) using [Alpine.js](https://alpinejs.dev/) and [Tailwind CSS](https://tailwindcss.com/) (zero build tools required)
- **Testing**: Python Standard Library `unittest` (77 comprehensive test cases, 100% offline)

---

## 🚀 Getting Started (Local Development)

### 1. Prerequisites
- **Python 3.12+** (or Conda / Miniconda)
- An **OpenRouter API Key** (register for free at [openrouter.ai](https://openrouter.ai/))

### 2. Clone the Repository
```bash
git clone https://github.com/notdhanraj/MTP---1.git
cd MTP---1
```

### 3. Set Up Environment & Install Dependencies
Using Conda:
```bash
conda create -n d2s-mtp python=3.12 -y
conda activate d2s-mtp
pip install -r requirements.txt
```

Or using standard Python `venv`:
```bash
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the example environment file and configure your API key:
```bash
cp .env.example .env
```
Edit `.env` to include your OpenRouter credentials:
```env
# OpenRouter API Key (Get yours at https://openrouter.ai/keys)
OPENROUTER_API_KEY=sk-or-v1-your-actual-api-key-here

# Optional: Default model (defaults to free Nemotron if unset)
OPENROUTER_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free
```

### 5. Launch the Server
```bash
uvicorn src.app:app --host 127.0.0.1 --port 8000 --reload
```
Open your web browser and navigate to:
```
http://127.0.0.1:8000
```

---

## 🧪 Running the Test Suite

The test suite is built entirely on Python's built-in `unittest` framework. It executes **100% offline** with zero LLM API token consumption, using mocked network responses and deterministic fixtures.

Run all 77 unit, integration, and end-to-end tests:

```bash
python -m unittest discover -s tests -v
```

### Test Coverage Highlights:
- **`tests/test_models.py`**: Validates Pydantic schema serialization, model validators, and physical segregation bin assignment rules.
- **`tests/test_llm_client.py`**: Verifies tool calling payloads, schema conformance, markdown JSON fallback parsers, exponential backoff retries, and `.env` loader guards.
- **`tests/test_services.py`**: Ingestion header detection, deduplication, run initialization, SSE event generators, inline chemical remediation, and multi-sheet Excel generation.
- **`tests/test_app.py`**: FastAPI endpoint validation, CORS behavior, static template delivery, SSE streaming responses, and end-to-end sample workbook ingestion.

---

## 📁 Repository Structure

```
MTP---1/
├── index.html                  # Responsive frontend (Alpine.js + Tailwind CSS)
├── requirements.txt            # Python dependencies
├── .env.example                # Template for environment configuration
├── .gitignore                  # Git ignore rules for virtualenvs, keys, and cache
├── README.md                   # Project documentation and user guide
├── src/
│   ├── __init__.py
│   ├── app.py                  # FastAPI application, CORS, routes & SSE endpoints
│   ├── classify_waste.py       # Pydantic classification schema & prompt definitions
│   ├── generate_management_plan.py # Pydantic plan schema & compliance instructions
│   ├── llm_client.py           # OpenRouter client, tool calling & retry logic
│   ├── models.py               # WasteManagementDossier, API schemas & bin mapping
│   ├── services.py             # Batch processing, SSE streaming & Excel generators
│   └── Hazardous Waste.xlsx    # Sample input inventory for testing & verification
└── tests/
    ├── __init__.py
    ├── test_app.py             # FastAPI endpoint and E2E integration tests
    ├── test_llm_client.py      # LLM client, fallback parsing and retry tests
    ├── test_models.py          # Data model, validator and bin assignment tests
    └── test_services.py        # Ingestion, deduplication, SSE and Excel tests
```

---

## ☁️ Deployment Guide

### Deploying to Render
1. Create a new **Web Service** on [Render](https://dashboard.render.com/).
2. Connect your GitHub repository.
3. Configure the build and start settings:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn src.app:app --host 0.0.0.0 --port $PORT`
4. In the **Environment Variables** tab, add:
   - `OPENROUTER_API_KEY`: Your OpenRouter API key.
   - `OPENROUTER_MODEL`: `nvidia/nemotron-3-ultra-550b-a55b:free` (or any compatible OpenRouter model).
5. Deploy the service. Your application will be live at `https://<your-service-name>.onrender.com`.

---

## 📜 License & Academic Context

Developed as part of the **M.Tech Project (D2S-MTP)** on intelligent environmental health, safety, and chemical compliance automation in academic laboratory environments.

Distributed under the **MIT License**. See `LICENSE` for details (if applicable).
