## 🧠 QaAgent Installation Guide

Welcome! Follow these steps to set up and run QaAgent.

---

## 🚀 Prerequisites

- Install [UV](https://github.com/astral-sh/uv) on Windows:
  `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- Create a virtual environment:
  uv venv
- Install dependencies:
  uv sync

---

## ⚙️ MCP Configuration

- Install fastmcp globally (not in the virtual environment):
  `pip install fastmcp`
- Locate scripts:
  - Terminal server: `./mcp/terminal_server/terminal_server.py`
  - Context retrieval: `./mcp/context_retrieval/context_retrieval.py`
- **Note**: Use full paths in mcp_config.json (relative paths do not work).

---

## 🌱 Environment Variables

Add these to your environment (e.g., in a .env file):

```
GOOGLE_API_KEY=
WORKSPACE_FOLDER=USED_TO_STORE_PLAYERIGHT_SCRIPTS
OUTPUT_FOLDER=USED_TO_STORE_PLAYWRIGHT_SESSION
```

---

## 📚 Knowledge Base Setup

1. Place documents in their respective folders:
   - Amazon: ./Backend/Knowledge_base/Amazon
   - Udemy: ./Backend/Knowledge_base/Udemy
2. Navigate to backend:
   `cd backend`
3. Run the ingestion pipeline:
   `uv run RagPipeline/ingest.py`

---

## 🤖 Running Agents

- Web Agent:
  `uv run python -m agents.web_agent`
- Host Agent:
  `uv run python -m agents.host_agent`

---

## 🖥️ Frontend Setup

1. Create a virtual environment:
   `uv venv`
2. Install dependencies:
   `uv sync`
3. Navigate to scripts folder:
   `cd frontend/scripts`
4. Install npm dependencies:
   `npm install`
5. Run the frontend app:
   `uv run app.py`

---