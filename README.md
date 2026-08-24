# Claude Roundtable

![Claude Roundtable](header.jpg)

> This project is a fork of [Andrej Karpathy's `llm-council`](https://github.com/karpathy/llm-council), adapted to use Anthropic's Claude API exclusively (instead of OpenRouter) and rebranded as Claude Roundtable.

The idea of this repo is that instead of asking a single question to a Claude model, you consult a "Roundtable" of 5 advisors, each reasoning from a different, deliberately tension-creating thinking style (all backed by Claude Opus 5). This repo is a simple, local web app that essentially looks like ChatGPT except it uses the Anthropic API to send your query to each advisor, it then asks them to review and rank each other's work, and finally a Chairman model produces the final response.

The 5 advisor roles are:

1. **The Contrarian** - looks for what's wrong, missing, or likely to fail.
2. **The First Principles Thinker** - strips away assumptions and asks what problem is actually being solved.
3. **The Expansionist** - looks for the upside and adjacent opportunities everyone else is missing.
4. **The Outsider** - has zero context and reacts purely to what's in front of them, catching blind spots experts miss.
5. **The Executor** - only cares whether it can actually be done, and what the fastest first step is.

In a bit more detail, here is what happens when you submit a query:

1. **Stage 1: First opinions**. The user query is given to all 5 advisors individually, and the responses are collected. The individual responses are shown in a "tab view", so that the user can inspect them all one by one.
2. **Stage 2: Review**. Each advisor is given the responses of the others. Under the hood, the advisor identities are anonymized so that they can't play favorites when judging outputs. Each advisor ranks the responses in accuracy and insight, from their own thinking style's perspective.
3. **Stage 3: Final response**. The designated Chairman of the Claude Roundtable takes all of the advisors' responses and compiles them into a single final answer that is presented to the user.

## Vibe Code Alert

This project was 99% vibe coded as a fun Saturday hack because I wanted to explore and evaluate a number of LLMs side by side in the process of [reading books together with LLMs](https://x.com/karpathy/status/1990577951671509438). It's nice and useful to see multiple responses side by side, and also the cross-opinions of all LLMs on each other's outputs. I'm not going to support it in any way, it's provided here as is for other people's inspiration and I don't intend to improve it. Code is ephemeral now and libraries are over, ask your LLM to change it in whatever way you like.

## Setup

### 1. Install Dependencies

The project uses [uv](https://docs.astral.sh/uv/) for project management.

**Backend:**
```bash
uv sync
```

**Frontend:**
```bash
cd frontend
npm install
cd ..
```

### 2. Configure API Key

Create a `.env` file in the project root:

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

Get your API key at [console.anthropic.com](https://console.anthropic.com/). Make sure you have credits available on your account.

### 3. Configure Models (Optional)

Edit `backend/config.py` to customize the council:

```python
COUNCIL_MODEL = "claude-opus-5"
COUNCIL_ROLES = [
    {"name": "The Contrarian", "system_prompt": "..."},
    {"name": "The First Principles Thinker", "system_prompt": "..."},
    {"name": "The Expansionist", "system_prompt": "..."},
    {"name": "The Outsider", "system_prompt": "..."},
    {"name": "The Executor", "system_prompt": "..."},
]

CHAIRMAN_MODEL = "claude-opus-5"
MODEL_EFFORT = "high"
```

## Running the Application

**Option 1: Use the start script**
```bash
./start.sh
```

**Option 2: Run manually**

Terminal 1 (Backend):
```bash
uv run python -m backend.main
```

Terminal 2 (Frontend):
```bash
cd frontend
npm run dev
```

**Option 3: Docker Compose**
```bash
docker compose up --build
```
This builds and runs the backend and frontend in containers, reading `ANTHROPIC_API_KEY` from the `.env` file in the project root. Source files are volume-mounted so changes are picked up without rebuilding.

Then open http://localhost:5173 in your browser.

## Tech Stack

- **Backend:** FastAPI (Python 3.10+), Anthropic Claude API
- **Frontend:** React + Vite, react-markdown for rendering
- **Storage:** JSON files in `data/conversations/`
- **Package Management:** uv for Python, npm for JavaScript
- **Containers:** Docker Compose (`backend/Dockerfile`, `frontend/Dockerfile`)
