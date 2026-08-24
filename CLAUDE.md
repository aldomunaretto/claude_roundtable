# CLAUDE.md - Technical Notes for Claude Roundtable

This file contains technical details, architectural decisions, and important implementation notes for future development sessions.

## Project Overview

Claude Roundtable (a fork of [Andrej Karpathy's `llm-council`](https://github.com/karpathy/llm-council)) is a 3-stage deliberation system where multiple LLMs collaboratively answer user questions. The key innovation is anonymized peer review in Stage 2, preventing models from playing favorites.

## Architecture

### Backend Structure (`backend/`)

**`config.py`**
- Contains `COUNCIL_MODEL` (the single Claude model backing every council seat, `claude-opus-5`)
- Contains `COUNCIL_ROLES` (list of 5 dicts, each with `name` and `system_prompt`, defining the 5 advisor personas/thinking styles - see "Council Roles" below)
- Contains `CHAIRMAN_MODEL` (model that synthesizes final answer, also `claude-opus-5`)
- Contains `MODEL_EFFORT` ("high") - passed as `output_config.effort` on every request
- Contains `TITLE_MODEL`/`TITLE_MODEL_EFFORT` (`claude-haiku-4-5`/`None`) for cheap conversation title generation
- Uses environment variable `ANTHROPIC_API_KEY` from `.env`
- Backend runs on **port 8001** (NOT 8000 - user had another app on 8000)

**`claude_client.py`**
- Uses the official `anthropic` Python SDK (`AsyncAnthropic`)
- `query_model()`: Single async model query via `messages.create()`, passes `output_config={"effort": ...}` (omitted when `effort` is falsy, since some models like Haiku 4.5 reject the param) and an optional `system` prompt (used to give a seat its persona)
- `query_models_parallel()`: Parallel queries using `asyncio.gather()`, with an optional `systems` list (per-seat system prompts, aligned with `models`). Returns a **list** of `(model, response)` tuples (NOT a dict) so duplicate model identifiers (all 5 council seats use `claude-opus-5`) don't collide/overwrite each other
- Returns dict with 'content' (concatenated text blocks from the response)
- Graceful degradation: returns None on failure, continues with successful responses

**`council.py`** - The Core Logic
- `stage1_collect_responses()`: Parallel queries to all 5 `COUNCIL_ROLES`, each with its own `system_prompt`; results are keyed by **role name** (e.g. "The Contrarian"), not the underlying model id
- `stage2_collect_rankings()`:
  - Anonymizes responses as "Response A, B, C, etc."
  - Creates `label_to_model` mapping (label -> advisor role name) for de-anonymization
  - Re-queries the same 5 roles (same personas) to evaluate and rank the anonymized responses (with strict format requirements)
  - Returns tuple: (rankings_list, label_to_model_dict)
  - Each ranking includes both raw text and `parsed_ranking` list
- `stage3_synthesize_final()`: Chairman (`CHAIRMAN_MODEL`, no persona) synthesizes from all responses + rankings
- `parse_ranking_from_text()`: Extracts "FINAL RANKING:" section, handles both numbered lists and plain format
- `calculate_aggregate_rankings()`: Computes average rank position across all peer evaluations, grouped by advisor role name

**`storage.py`**
- JSON-based conversation storage in `data/conversations/`
- Each conversation: `{id, created_at, messages[]}`
- Assistant messages contain: `{role, stage1, stage2, stage3}`
- `delete_conversation()` removes the conversation's JSON file, returns `False` if it didn't exist
- Note: metadata (label_to_model, aggregate_rankings) is NOT persisted to storage, only returned via API

**`main.py`**
- FastAPI app with CORS enabled for localhost:5173 and localhost:3000
- POST `/api/conversations/{id}/message` returns metadata in addition to stages
- DELETE `/api/conversations/{id}` deletes a conversation, 404 if not found
- Metadata includes: label_to_model mapping and aggregate_rankings

### Frontend Structure (`frontend/src/`)

**`App.jsx`**
- Main orchestration: manages conversations list and current conversation
- Handles message sending and metadata storage
- `handleDeleteConversation()` calls the API, removes the conversation from local state, and clears the current conversation if it was the one deleted
- Important: metadata is stored in the UI state for display but not persisted to backend JSON

**`components/Sidebar.jsx`**
- Lists conversations; each item has a delete ("×") button, revealed on hover via CSS, with `stopPropagation` so it doesn't also select the conversation
- Delete is confirmed with `window.confirm()` before calling `onDeleteConversation`

**`components/ChatInterface.jsx`**
- Multiline textarea (3 rows, resizable)
- Enter to send, Shift+Enter for new line
- User messages wrapped in markdown-content class for padding

**`components/Stage1.jsx`**
- Tab view of individual model responses
- ReactMarkdown rendering with markdown-content wrapper

**`components/Stage2.jsx`**
- **Critical Feature**: Tab view showing RAW evaluation text from each model
- De-anonymization happens CLIENT-SIDE for display (models receive anonymous labels)
- Shows "Extracted Ranking" below each evaluation so users can validate parsing
- Aggregate rankings shown with average position and vote count
- Explanatory text clarifies that boldface model names are for readability only

**`components/Stage3.jsx`**
- Final synthesized answer from chairman
- Green-tinted background (#f0fff0) to highlight conclusion

**Styling (`*.css`)**
- Light mode theme (not dark mode)
- Primary color: #4a90e2 (blue)
- Global markdown styling in `index.css` with `.markdown-content` class
- 12px padding on all markdown content to prevent cluttered appearance

## Key Design Decisions

### Stage 2 Prompt Format
The Stage 2 prompt is very specific to ensure parseable output:
```
1. Evaluate each response individually first
2. Provide "FINAL RANKING:" header
3. Numbered list format: "1. Response C", "2. Response A", etc.
4. No additional text after ranking section
```

This strict format allows reliable parsing while still getting thoughtful evaluations.

### De-anonymization Strategy
- Models receive: "Response A", "Response B", etc.
- Backend creates mapping: `{"Response A": "The Contrarian", ...}` (advisor role name, not the literal model id, since all seats share `claude-opus-5`)
- Frontend displays advisor names in **bold** for readability
- Users see explanation that original evaluation used anonymous labels
- This prevents bias while maintaining transparency

### Error Handling Philosophy
- Continue with successful responses if some models fail (graceful degradation)
- Never fail the entire request due to single model failure
- Log errors but don't expose to user unless all models fail

### UI/UX Transparency
- All raw outputs are inspectable via tabs
- Parsed rankings shown below raw text for validation
- Users can verify system's interpretation of model outputs
- This builds trust and allows debugging of edge cases

## Important Implementation Details

### Relative Imports
All backend modules use relative imports (e.g., `from .config import ...`) not absolute imports. This is critical for Python's module system to work correctly when running as `python -m backend.main`.

### Port Configuration
- Backend: 8001 (changed from 8000 to avoid conflict)
- Frontend: 5173 (Vite default)
- Update both `backend/main.py` and `frontend/src/api.js` if changing

### Markdown Rendering
All ReactMarkdown components must be wrapped in `<div className="markdown-content">` for proper spacing. This class is defined globally in `index.css`.

### Model Configuration
All council seats and the chairman are hardcoded in `backend/config.py` to `claude-opus-5` at `MODEL_EFFORT = "high"`. Since all seats share the same model identifier, `query_models_parallel()` must return a list (not a dict) to avoid collapsing duplicate keys - see `claude_client.py` notes above.

### Council Roles
`COUNCIL_ROLES` in `backend/config.py` defines 5 advisor personas via per-seat `system` prompts (not different models - all use `COUNCIL_MODEL`). They are thinking styles, not job titles, chosen to create natural tension:
- **The Contrarian** - looks for what's wrong, missing, or likely to fail (downside)
- **The First Principles Thinker** - strips away assumptions, asks what's actually being solved
- **The Expansionist** - looks for missed upside and adjacent opportunities (upside, opposite of Contrarian)
- **The Outsider** - zero context, reacts only to what's in front of it, catches blind spots
- **The Executor** - only cares if/how it can be done fastest (opposite of First Principles)

Both `stage1_collect_responses()` and `stage2_collect_rankings()` query the same 5 roles (same system prompts) so each advisor evaluates rankings from its own persona's perspective, not a neutral one.

### Docker Setup
- `docker-compose.yml` (project root) defines `backend` and `frontend` services
- `backend/Dockerfile`: Python 3.12-slim + `uv`, runs `uv run python -m backend.main` on port 8001
- `frontend/Dockerfile`: Node 20-alpine, runs `npm run dev -- --host 0.0.0.0` on port 5173
- `backend` reads `ANTHROPIC_API_KEY` from the root `.env` via `env_file` (marked `required: false` so compose doesn't fail if `.env` is missing)
- Source directories are volume-mounted (not baked into the image) so local edits are picked up live; `./data` is mounted for conversation persistence
- `frontend/vite.config.js` sets `server.host: true` and `watch.usePolling: true` so the dev server is reachable and detects file changes from bind mounts inside the container

## Common Gotchas

1. **Module Import Errors**: Always run backend as `python -m backend.main` from project root, not from backend directory
2. **CORS Issues**: Frontend must match allowed origins in `main.py` CORS middleware
3. **Ranking Parse Failures**: If models don't follow format, fallback regex extracts any "Response X" patterns in order
4. **Missing Metadata**: Metadata is ephemeral (not persisted), only available in API responses

## Future Enhancement Ideas

- Configurable council/chairman via UI instead of config file
- Streaming responses instead of batch loading
- Export conversations to markdown/PDF
- Model performance analytics over time
- Custom ranking criteria (not just accuracy/insight)
- Support for reasoning models (o1, etc.) with special handling

## Testing Notes

Use a small script with the `anthropic` SDK to verify API connectivity and test different Claude model identifiers before adding them to the council.

## Data Flow Summary

```
User Query
    ↓
Stage 1: Parallel queries → [individual responses]
    ↓
Stage 2: Anonymize → Parallel ranking queries → [evaluations + parsed rankings]
    ↓
Aggregate Rankings Calculation → [sorted by avg position]
    ↓
Stage 3: Chairman synthesis with full context
    ↓
Return: {stage1, stage2, stage3, metadata}
    ↓
Frontend: Display with tabs + validation UI
```

The entire flow is async/parallel where possible to minimize latency.
