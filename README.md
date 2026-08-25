# Claude Roundtable

![Claude Roundtable](img/header.jpeg)

> This project is a fork of [Andrej Karpathy's `llm-council`](https://github.com/karpathy/llm-council), adapted to use Anthropic's Claude API exclusively (instead of OpenRouter) and rebranded as Claude Roundtable.

Instead of asking a single question to one Claude model, Claude Roundtable consults a "Roundtable" of advisors, each reasoning from a different, deliberately tension-creating thinking style. It's a simple, local web app that looks like ChatGPT, except your query goes out to every advisor, they review and rank each other's work, and a Chairman model produces the final synthesized answer.

## How It Works

1. **Stage 1: First opinions** - the query goes to every advisor individually, in parallel. Each response is shown in its own tab so you can inspect them one by one.
2. **Stage 2: Peer review** - each advisor is shown the others' responses (identities anonymized, so nobody can play favorites) and ranks them for accuracy and insight, from their own thinking style's perspective.
3. **Stage 3: Final synthesis** - the Chairman takes every response and ranking and compiles a single final answer, presented to the user.

## Council Roles

Out of the box, the council has 5 default advisor roles:

1. **The Contrarian** - looks for what's wrong, missing, or likely to fail.
2. **The First Principles Thinker** - strips away assumptions and asks what problem is actually being solved.
3. **The Expansionist** - looks for the upside and adjacent opportunities everyone else is missing.
4. **The Outsider** - has zero context and reacts purely to what's in front of them, catching blind spots experts miss.
5. **The Executor** - only cares whether it can actually be done, and what the fastest first step is.

These 5 are just the starting defaults, not fixed. Click the ⚙ button next to the "Claude Roundtable" title in the sidebar to open **Council Settings**, where you can edit any role's system prompt, Claude model, and effort level, add brand-new members, or delete any role (including the original 5). When you start a new conversation, a picker lets you choose which members of the current roster sit on the council for that conversation - the selection is fixed for the whole conversation, including any follow-up messages.

## Conversations

Conversations support follow-up questions: each one re-runs the entire 3-stage process above, with the context of your earlier questions and the Chairman's previous final answers (advisors' individual opinions and peer rankings from earlier turns aren't replayed, only the final answers, to keep prompts small). Since a follow-up means convening the whole council again rather than a quick incremental reply, the app asks you to confirm before sending one.

Conversations are listed in the sidebar and can be deleted at any time by hovering over one and clicking the "×" button that appears (with a confirmation prompt).

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

### 3. Configure the Council (Optional)

The council roles (system prompt, model, effort) are editable from the app itself via the ⚙ **Council Settings** button in the sidebar - no code changes or restart needed. `backend/config.py` only supplies the *starting* roster the first time the app runs (or after you delete `data/council_roles.json` to start over):

```python
DEFAULT_COUNCIL_ROLES = [
    {"name": "The Contrarian", "system_prompt": "...", "model": "claude-sonnet-5", "effort": "medium"},
    {"name": "The First Principles Thinker", "system_prompt": "...", "model": "claude-sonnet-5", "effort": "medium"},
    {"name": "The Expansionist", "system_prompt": "...", "model": "claude-sonnet-5", "effort": "medium"},
    {"name": "The Outsider", "system_prompt": "...", "model": "claude-sonnet-5", "effort": "medium"},
    {"name": "The Executor", "system_prompt": "...", "model": "claude-sonnet-5", "effort": "medium"},
]

CHAIRMAN_MODEL = "claude-opus-5"
CHAIRMAN_EFFORT = "high"
```

The Chairman (the model that synthesizes the final answer) is not part of the editable roster - it stays a plain constant in `config.py`, independent of whatever model/effort the council roles use.

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

- **Backend:** FastAPI (Python 3.12), Anthropic Claude API
- **Frontend:** React + Vite, react-markdown for rendering
- **Storage:** JSON files in `data/conversations/` and `data/council_roles.json`
- **Package Management:** uv for Python, npm for JavaScript
- **Containers:** Docker Compose (`backend/Dockerfile`, `frontend/Dockerfile`)
