# 🏥 Clinical Decision Support System

### Multi-Agent Workflow using A2A & MCP Protocols

A multi-agent clinical decision support system where AI agents **dynamically discover, plan, and execute** clinical assessments using **Google's A2A (Agent-to-Agent)** protocol for inter-agent communication and **Anthropic's MCP (Model Context Protocol)** for tool access — with **zero hardcoded workflows**.

Built for **Philips IT PoC — Use Case 3** | April 2026

---

## 📌 Problem Statement

> *"Create an Agent workflow application using A2A and MCP protocols where the agents plan the tasks and execute them in a non-hardcoded manner."*
> — Philips IT Brief to Colleges, April 2026

Traditional clinical workflows suffer from three problems:

1. **Manual Process** — Doctors check multiple disconnected systems for patient history, risk scores, and guidelines
2. **Hardcoded Logic** — Existing AI systems use rigid if/else chains that break on unforeseen conditions
3. **No Interoperability** — Agents built on different frameworks cannot communicate or collaborate

---

## 💡 Our Solution

A system where:

- A **Planner Agent** discovers available specialist agents at runtime via A2A Agent Cards
- An **LLM (Llama 3.3 70B)** creates the execution plan dynamically — no if/else routing
- Specialist agents execute tasks in parallel and access data through MCP tools
- A **Report Agent** synthesizes all outputs into a physician-ready recommendation
- A **Patient Wiki** follows the **Karpathy LLM-Wiki pattern** — knowledge is compiled and accumulated, not re-derived

Adding or removing an agent requires **zero code changes**. The Planner discovers what's available and adapts.

---

## 🏗️ System Architecture

```
┌──────────────────────────┐
│    User / Clinician      │
│    Submits Case (UI)     │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────────────┐
│   Planner / Orchestrator Agent   │
│   (LLM decides dynamic plan)    │
│   Port 8000                      │
└──────┬────────────┬──────────────┘
       │            │
       │ A2A        │ A2A
       ▼            ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ History Agent│  │ Risk Agent   │  │ Report Agent │
│ Port 8001    │  │ Port 8002    │  │ Port 8003    │
└──────┬───────┘  └──────┬───────┘  └──────────────┘
       │                 │
       │ MCP             │ MCP
       ▼                 ▼
┌──────────────────┐  ┌──────────────────┐
│ Patient Wiki MCP │  │ Risk Guideline   │
│ Port 9001        │  │ MCP - Port 9002  │
└──────┬───────────┘  └──────┬───────────┘
       │                     │
       ▼                     ▼
┌──────────────┐      ┌──────────────────┐
│patients.json │      │clinical_rules.json│
└──────────────┘      └──────────────────┘
```

### Communication Flow

1. **User** submits a clinical case through the Streamlit UI
2. **Planner** fetches Agent Cards from all registered agents (A2A discovery)
3. **LLM** reads the Agent Cards and creates a dynamic execution plan
4. **Planner** dispatches A2A tasks to specialist agents (History + Risk run in parallel)
5. **History Agent** calls Patient Wiki MCP tools to fetch/create patient records
6. **Risk Agent** calls Risk Guideline MCP tools to compute clinical risk scores
7. **Report Agent** receives all outputs and synthesizes a final clinical recommendation
8. **UI** displays the report, execution plan, audit trail, and raw data

---

## 🔧 Tech Stack

| Component | Tool | Why This Choice |
|-----------|------|-----------------|
| **LLM** | Llama 3.3 70B via Groq | Open-source model, free API tier, fast inference |
| **Language** | Python 3.11+ | Largest AI ecosystem, async support |
| **Web Framework** | FastAPI | Auto documentation, Pydantic validation, async |
| **HTTP Client** | httpx | Async HTTP for A2A task dispatch |
| **Data Validation** | Pydantic | Type-safe models, auto-validation |
| **A2A Protocol** | Custom on FastAPI | Lightweight, follows spec, fully transparent |
| **MCP Tools** | HTTP REST endpoints | Simple, testable, debuggable |
| **UI** | Streamlit | Fastest path to demo-ready frontend |
| **Data Store** | JSON files | Zero setup, portable (Karpathy LLM-Wiki pattern) |
| **Config** | python-dotenv | Environment-based API key management |

**Total cost: Zero.** All open-source. Free tier APIs. No vendor lock-in.

---

## 📂 Project Structure

```
philips-poc/
├── common/                          # Shared utilities
│   ├── __init__.py
│   ├── a2a_models.py               # A2A protocol Pydantic models
│   │                                 (AgentCard, Task, Message, Artifact, AuditEntry)
│   ├── a2a_client.py               # A2A HTTP client
│   │                                 (fetch_agent_card, send_task, audit logging)
│   └── llm_client.py               # Groq/Llama LLM wrapper
│                                     (chat, chat_json, chat_with_tools)
│
├── mcp_servers/                     # MCP Tool Servers
│   ├── __init__.py
│   ├── patient_wiki_server.py      # Patient data MCP (port 9001)
│   │                                 Tools: query_patient, search_patient,
│   │                                 create_patient, update_patient,
│   │                                 ingest_record, get_storage_info
│   └── risk_guideline_server.py    # Clinical scoring MCP (port 9002)
│                                     Tools: get_risk_rules, evaluate_risk,
│                                     list_available_scores
│
├── agents/                          # A2A-compliant Specialist Agents
│   ├── __init__.py
│   ├── history_agent.py            # Patient history agent (port 8001)
│   │                                 Searches by ID/name, auto-creates patients,
│   │                                 deep merges follow-up data
│   ├── risk_agent.py               # Risk assessment agent (port 8002)
│   │                                 HEART Score, CHA2DS2-VASc, Wells, or
│   │                                 general clinical assessment
│   └── report_agent.py             # Report synthesis agent (port 8003)
│                                     Produces physician-ready recommendations
│                                     with differential diagnoses
│
├── planner/                         # Orchestrator
│   ├── __init__.py
│   └── orchestrator.py             # Dynamic planner (port 8000)
│                                     Agent discovery, LLM planning,
│                                     parallel execution, audit trail
│
├── ui/
│   ├── __init__.py
│   └── app.py                      # Streamlit web UI (port 8501)
│                                     Case submission, results display,
│                                     audit trail, wiki status
│
├── data/                            # Data storage (Karpathy LLM-Wiki pattern)
│   ├── patients.json               # Patient records (compiled knowledge base)
│   └── clinical_rules.json         # Clinical scoring algorithms
│
├── .env                             # API keys and port configuration
├── requirements.txt                 # Python dependencies
├── seed_data.py                     # Synthetic data generator
├── run_all.py                       # Launches all 7 services
└── README.md                        # This file
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- A free Groq API key (no credit card required)

### Step 1: Clone and Setup

```bash
cd philips-poc
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### Step 2: Configure API Key

1. Go to https://console.groq.com and sign up (free)
2. Create an API key
3. Open `.env` and replace `your_groq_api_key_here` with your key

### Step 3: Seed Data and Run

```bash
python seed_data.py
python run_all.py
```

### Step 4: Open the UI

Go to **http://localhost:8501** in your browser.

---

## 🧪 Testing

### Quick Test (PowerShell)

```powershell
# Discover agents
Invoke-RestMethod -Uri http://localhost:8000/discover | ConvertTo-Json -Depth 5

# Submit a case
$body = @{
    case_text = "58-year-old male patient P001 with chest tightness on exertion for 2 weeks. History of diabetes and hypertension. Assess cardiac risk."
    patient_id = "P001"
} | ConvertTo-Json

Invoke-RestMethod -Uri http://localhost:8000/submit-case -Method Post -Body $body -ContentType "application/json" | ConvertTo-Json -Depth 10
```

### Demo Scenarios

| Scenario | Description | What It Proves |
|----------|-------------|----------------|
| Existing Patient (P001) | Chest pain case for Rajesh Kumar | HEART Score, parallel execution, audit trail |
| New Patient (no ID) | Unknown patient from free text | Auto-registration, LLM data extraction, wiki creation |
| Follow-up Visit | Same patient returns with new symptoms | Name-based lookup, deep merge, trend tracking |
| Dynamic Discovery | Stop/start an agent mid-demo | Runtime adaptability, non-hardcoded planning |

---

## 🔑 Key Design Decisions

### Why Custom A2A Instead of Google's SDK?

Google's A2A Python SDK is tightly coupled with Google Cloud's ADK and Vertex AI. Our custom implementation follows the A2A specification exactly — Agent Cards at `/.well-known/agent.json`, tasks via `POST /a2a/tasks/send`, JSON-RPC format — without heavyweight cloud dependencies. Every message is transparent and debuggable.

### Why Custom MCP Instead of the Official SDK?

The official MCP SDK uses stdio-based transport designed for local process communication. Our architecture needs HTTP-based tool calls across different ports. We built MCP-compatible REST endpoints that follow the tool interface pattern: manifest at `GET /mcp/tools`, tool calls via POST endpoints.

### Why Not LangChain/CrewAI?

Agent frameworks hide the protocol layer behind abstractions. Using CrewAI, the A2A communication would be invisible — it happens through CrewAI's internal mechanism. By building on FastAPI, every Agent Card, task message, and tool call is visible. The architecture is framework-agnostic — any agent's internals could be swapped to LangChain while keeping the A2A endpoints intact.

### Karpathy LLM-Wiki Pattern

Our Patient Wiki applies Andrej Karpathy's LLM Wiki pattern:

- **Raw sources** = clinician's free-text case descriptions
- **LLM as compiler** = History Agent extracts structured data from text
- **Wiki** = `patients.json` storing compiled, structured patient records
- **Incremental compilation** = follow-up visits deep-merge new data into existing records
- **Query** = agents read from compiled wiki, not from raw text

Knowledge accumulates over time. Each interaction enriches the patient record.

---

## 📡 API Endpoints

### Planner (Port 8000)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/submit-case` | Submit a clinical case for processing |
| GET | `/discover` | Trigger agent discovery |
| GET | `/health` | Health check |

### Agents (Ports 8001-8003)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/.well-known/agent.json` | A2A Agent Card (discovery) |
| POST | `/a2a/tasks/send` | Process an A2A task |
| GET | `/health` | Health check |

### Patient Wiki MCP (Port 9001)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/mcp/tools` | List available tools |
| POST | `/mcp/tools/query_patient` | Get patient by ID |
| POST | `/mcp/tools/search_patient` | Find patient by name |
| POST | `/mcp/tools/create_patient` | Create new patient |
| POST | `/mcp/tools/update_patient` | Merge new data into patient |
| POST | `/mcp/tools/ingest_record` | Add clinical note |
| POST | `/mcp/tools/get_storage_info` | Show storage location |

### Risk Guideline MCP (Port 9002)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/mcp/tools` | List available tools |
| POST | `/mcp/tools/get_risk_rules` | Get scoring algorithm |
| POST | `/mcp/tools/evaluate_risk` | Compute risk score |
| POST | `/mcp/tools/list_available_scores` | List all scoring systems |

---

## 🏥 Clinical Scoring Systems

| Score | Condition | What It Measures |
|-------|-----------|-----------------|
| HEART Score | Chest pain | Major Adverse Cardiac Event (MACE) risk |
| CHA₂DS₂-VASc | Atrial Fibrillation | Stroke risk to guide anticoagulation |
| Wells Score | DVT symptoms | Deep Vein Thrombosis probability |
| General Assessment | Any condition | LLM-based clinical risk evaluation |

For conditions without a specific scoring system, the Risk Agent performs a general clinical risk assessment using the LLM, evaluating age-related risk, vital signs, comorbidity burden, symptom severity, lab abnormalities, and medication complexity.

---

## 🔮 Future Extensions

| Extension | Description |
|-----------|-------------|
| **FHIR Integration** | Connect to real EHR systems via FHIR MCP server |
| **Drug Interaction Agent** | New agent checking medication interactions — auto-discovered by Planner |
| **Docker Deployment** | Containerize each agent as a microservice on Kubernetes |
| **Human-in-the-Loop** | Physician approval for high-risk recommendations |
| **Multi-LLM Routing** | Specialized models per agent (vision model for imaging agent) |
| **Real-time Monitoring** | Prometheus metrics and Grafana dashboards |
| **OAuth 2.0 Auth** | Per A2A spec, secure agent-to-agent authentication |
| **Service Registry** | Consul/etcd replacing hardcoded URL list |
| **Streaming (SSE)** | Real-time task progress updates via Server-Sent Events |

---

## 🛡️ Anti-Hallucination Measures

LLM hallucination is a critical risk in clinical systems. We implement multiple safeguards:

1. **Strict prompts** — every LLM call explicitly instructs "use ONLY provided data, NEVER fabricate"
2. **Regex fallback validation** — critical fields (age, gender, name) are validated with regex extraction from the original text
3. **Null-safe extraction** — the data extraction template uses null placeholders, not example values that the LLM might copy
4. **Deep merge validation** — the wiki won't overwrite real data with nulls or empty values
5. **Cross-check instructions** — prompts tell the LLM "before writing any fact, verify it exists in the input"

---

## ⚠️ Disclaimer

This is a **Proof of Concept** for demonstration purposes only. **Not for clinical use.** All patient data is synthetic. Clinical recommendations must always be validated by a qualified physician.

---

## 📄 License

This project was built for the Philips IT PoC assessment. All tools used are open-source.

- **Llama 3.3 70B** — Meta AI, Llama Community License
- **Groq API** — Free tier
- **FastAPI** — MIT License
- **Streamlit** — Apache 2.0
- **A2A Protocol** — Apache 2.0 (Linux Foundation)
- **MCP Protocol** — MIT License (Anthropic)
