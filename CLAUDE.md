# CLAUDE.md - Technical Notes for Claude Roundtable

This file contains technical details, architectural decisions, and important implementation notes for future development sessions.

## Project Overview

Claude Roundtable (a fork of [Andrej Karpathy's `llm-council`](https://github.com/karpathy/llm-council)) is a 3-stage deliberation system where multiple LLMs collaboratively answer user questions. The key innovation is anonymized peer review in Stage 2, preventing models from playing favorites.

## Architecture

### Backend Structure (`backend/`)

**`config.py`**
- Contains `COUNCIL_MODEL`/`MODEL_EFFORT` (seed defaults, `claude-opus-5`/`"high"`)
- Contains `DEFAULT_COUNCIL_ROLES` (list of 5 dicts, each with `name`/`system_prompt`/`model`/`effort`) - **only used to seed `data/council_roles.json` the first time it's read**, and as the fallback for conversations created before the roles-editor feature existed. The editable roster in that JSON file is the real source of truth at runtime - see `roles_storage.py` and "Council Roles Configuration" below
- Contains `CHAIRMAN_MODEL` (model that synthesizes final answer, also `claude-opus-5`) - NOT configurable via the roles editor, out of scope on purpose
- Contains `TITLE_MODEL`/`TITLE_MODEL_EFFORT` (`claude-haiku-4-5`/`None`) for cheap conversation title generation
- Contains `DATA_ROOT` ("data", parent of `DATA_DIR`) and `FALLBACK_MODELS` (hardcoded model list used when `GET /api/models` can't reach the Anthropic API)
- Uses environment variable `ANTHROPIC_API_KEY` from `.env`
- Backend runs on **port 8001** (NOT 8000 - user had another app on 8000)

**`claude_client.py`**
- Uses the official `anthropic` Python SDK (`AsyncAnthropic`)
- `query_model()`: Single async model query via `messages.create()`, passes `output_config={"effort": ...}` (omitted when `effort` is falsy, since some models like Haiku 4.5 reject the param) and an optional `system` prompt (used to give a seat its persona)
- `query_models_parallel(models, messages, systems=None, efforts=None)`: Parallel queries using `asyncio.gather()`, with optional `systems`/`efforts` lists (per-seat system prompt and effort level, aligned with `models`; each seat can now use a different model/effort, not just a different persona). Returns a **list** of `(model, response)` tuples (NOT a dict) so duplicate model identifiers don't collide/overwrite each other
- Returns dict with 'content' (concatenated text blocks from the response)
- Graceful degradation: returns None on failure, continues with successful responses
- `list_available_models()`: calls `_client.models.list(limit=100)` (the Anthropic Models API) and returns `[{id, display_name}, ...]`; any exception (invalid API key, network error) falls back to `config.FALLBACK_MODELS` instead of raising, so `GET /api/models` never 500s

**`council.py`** - The Core Logic
- `resolve_conversation_roles(conversation)`: Returns `conversation["council_roles"]` if present and non-empty (conversations created after the roles-editor feature snapshot their selected roles at creation time), else falls back to `DEFAULT_COUNCIL_ROLES` (for conversations created before this feature existed)
- `build_history_messages()`: Turns a conversation's prior stored messages into a simplified alternating history (each prior user query paired with only the Chairman's `stage3.response` from that turn) - the internal Stage 1/2 deliberation is NOT replayed. Used to give follow-up messages context - see "Multi-turn Conversations" below
- `stage1_collect_responses(user_query, roles, history=None)`: Parallel queries to all `roles` for this conversation (a list of dicts with `name`/`system_prompt`/`model`/`effort`, NOT the global `DEFAULT_COUNCIL_ROLES` - see "Council Roles Configuration" below), each with its own persona/model/effort; `history` (if given) is prepended to the current query so advisors see prior turns; results are keyed by **role name** (e.g. "The Contrarian"), not the underlying model id
- `stage2_collect_rankings(user_query, stage1_results, roles)`:
  - Anonymizes responses as "Response A, B, C, etc."
  - Creates `label_to_model` mapping (label -> advisor role name) for de-anonymization
  - Re-queries the **same** `roles` that produced `stage1_results` (same personas/models/efforts) to evaluate and rank the anonymized responses (with strict format requirements)
  - Returns tuple: (rankings_list, label_to_model_dict)
  - Each ranking includes both raw text and `parsed_ranking` list
  - Does NOT take `history` - it only ever evaluates the current turn's Stage 1 responses
- `stage3_synthesize_final(..., history=None)`: Chairman (`CHAIRMAN_MODEL`, no persona, NOT configurable) synthesizes from all responses + rankings; `history` (if given) is prepended so the Chairman keeps continuity with its own earlier answers
- `parse_ranking_from_text()`: Extracts "FINAL RANKING:" section, handles both numbered lists and plain format
- `calculate_aggregate_rankings()`: Computes average rank position across all peer evaluations, grouped by advisor role name (role names must be unique roster-wide - see "Council Roles Configuration")
- `run_full_council(user_query, roles, history=None)`: Orchestrates all 3 stages, threading `roles` into Stage 1 and Stage 2, and `history` into Stage 1 and Stage 3

**`storage.py`**
- JSON-based conversation storage in `data/conversations/`
- Each conversation: `{id, created_at, messages[], council_roles[]}` - `council_roles` is a **full snapshot** (not ids) of the roles selected when the conversation was created, set once by `create_conversation(conversation_id, council_roles)` and never mutated afterward
- Assistant messages contain: `{role, stage1, stage2, stage3}`
- `delete_conversation()` removes the conversation's JSON file, returns `False` if it didn't exist
- Note: metadata (label_to_model, aggregate_rankings) is NOT persisted to storage, only returned via API

**`roles_storage.py`**
- JSON-based storage for the **editable** council roles roster, at `data/council_roles.json` (sibling of `data/conversations/`, same gitignored `data/` tree)
- `load_roles()`: seeds the file from `config.DEFAULT_COUNCIL_ROLES` on first access (each role gets a fresh `uuid4` id and `is_default: True`); from then on this file is the live roster, independent of `config.py`
- `create_role()`/`update_role()`/`delete_role()`: standard CRUD. `update_role(role_id, **fields)` only touches keys present in `fields` (an explicit `effort=None` is respected as "no effort"; an omitted `effort` key leaves the stored value untouched - callers must filter with something like Pydantic's `exclude_unset`, see `main.py` below)
- `is_default` is purely informational (shown as a badge in the UI) - it does NOT protect a role from being edited or deleted, by design (the user explicitly wants to be able to remove even the 5 originals)

**`main.py`**
- FastAPI app with CORS enabled for localhost:5173 and localhost:3000
- POST `/api/conversations/{id}/message`: non-streaming variant; runs the full pipeline and returns `{stage1, stage2, stage3, metadata}` in one JSON payload once everything completes. Kept as a simpler integration point, but the current frontend does NOT call it
- POST `/api/conversations/{id}/message/stream`: the endpoint the frontend actually uses. Streams Server-Sent Events (`stage1_start`/`stage1_complete`, `stage2_start`/`stage2_complete`, `stage3_start`/`stage3_complete`, `title_complete`, `complete`, `error`) as each stage finishes, so the UI can show per-stage progress instead of waiting for the whole pipeline
- Both endpoints call `council.build_history_messages(conversation["messages"])` **before** appending the new user message, and pass the result as `history` into `run_full_council()` / `stage1_collect_responses()` / `stage3_synthesize_final()` - see "Multi-turn Conversations" below
- Both endpoints also call `council.resolve_conversation_roles(conversation)` right after loading it, and lazily persist the result back onto `conversation["council_roles"]` if that key was missing (conversations created before the roles-editor feature) - see "Council Roles Configuration" below
- DELETE `/api/conversations/{id}` deletes a conversation, 404 if not found
- POST `/api/conversations` now requires `{role_ids: [...]}` in the body; resolves ids against the live roster (unknown ids are silently ignored), 400 if the resolved set is empty, snapshots the matching role dicts into the new conversation
- `GET/POST/PUT/DELETE /api/roles`: CRUD for the roster (backed by `roles_storage.py`). `POST`/`PUT` validate that `name`/`system_prompt`/`model` are non-empty and that `name` is unique roster-wide (case-insensitive) - duplicate names would silently collide in `label_to_model`/`calculate_aggregate_rankings`, which key by role name. `PUT` builds its update dict via Pydantic's `request.model_dump(exclude_unset=True)`, NOT a plain `.dict()`, so a partial update (e.g. only `name`) doesn't wipe out the existing `effort`
- `GET /api/models`: thin wrapper over `claude_client.list_available_models()`, powers the role editor's model dropdown
- Metadata includes: label_to_model mapping and aggregate_rankings

### Frontend Structure (`frontend/src/`)

**`App.jsx`**
- Main orchestration: manages conversations list and current conversation
- Handles message sending and metadata storage
- `handleDeleteConversation()` calls the API, removes the conversation from local state, and clears the current conversation if it was the one deleted
- Important: metadata is stored in the UI state for display but not persisted to backend JSON
- `handleNewConversation()` no longer creates a conversation directly - it opens `NewConversationModal`; the modal's `onConfirm(roleIds)` callback (`handleConfirmNewConversation`) does the actual `api.createConversation(roleIds)` call and closes the modal
- Owns `isNewConversationModalOpen`/`isRolesSettingsOpen` state and renders both modals as siblings of `Sidebar`/`ChatInterface`

**`components/Sidebar.jsx`**
- Lists conversations; each item has a delete ("×") button, revealed on hover via CSS, with `stopPropagation` so it doesn't also select the conversation
- Delete is confirmed with `window.confirm()` before calling `onDeleteConversation`
- New `onOpenSettings` prop, wired to a `⚙` button in `.sidebar-header` (always visible, unlike the per-conversation delete button) that opens `RolesSettings`

**`components/Modal.jsx`**
- Generic overlay modal (`{isOpen, onClose, title, children}`), reused by `RolesSettings` and `NewConversationModal` - no router or UI library in this repo, so this is the only modal primitive
- Click on the overlay (not the panel) or `Escape` closes it; no focus trap (kept deliberately simple)

**`components/RolesSettings.jsx`**
- Modal (opened from the Sidebar's `⚙` button) for full CRUD on the council roles roster: fetches `api.listRoles()` + `api.listModels()` on open
- List view: a card per role (name, `Default` badge if `is_default`, model badge, effort badge, truncated system prompt, Edit/Delete). Delete uses `window.confirm()`, same pattern as conversation deletion
- Form view (add or edit): name, system prompt textarea, model `<select>` populated from `GET /api/models` (falls back to a free-text `<input>` if that fetch itself fails client-side, on top of the backend's own `FALLBACK_MODELS` safety net), effort `<select>` with fixed options (`low`/`medium`/`high`/`xhigh`/`max`/none)
- Editing or deleting a role here never retroactively affects conversations already created - see "Council Roles Configuration" below

**`components/NewConversationModal.jsx`**
- Modal opened by `App.jsx`'s `handleNewConversation()` instead of creating a conversation immediately
- Fetches `api.listRoles()` on open, shows one checkbox per role (all checked by default) plus "Select All"/"Select None"; "Start Conversation" is disabled if nothing is selected or the roster is empty
- `onConfirm(roleIds)` is the only way a conversation actually gets created

**`components/ChatInterface.jsx`**
- Multiline textarea (3 rows, resizable), always rendered (not hidden after the first message - conversations support multiple turns)
- Enter to send, Shift+Enter for new line
- User messages wrapped in markdown-content class for padding
- `handleSubmit()` treats any send after the first message as a follow-up (`conversation.messages.length > 0`) and shows a `window.confirm()` warning before calling `onSendMessage`, since every message re-runs the full 3-stage council from scratch - see "Multi-turn Conversations" below
- Shows a small `.active-council` subtitle above the message list with `conversation.council_roles.map(r => r.name).join(', ')`, so it's visible which members are seated for that conversation

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
- Backend creates mapping: `{"Response A": "The Contrarian", ...}` (advisor role name, not the literal model id - roles can each use a different model now, and even when they don't, role name is what stays unique)
- Frontend displays advisor names in **bold** for readability
- Users see explanation that original evaluation used anonymous labels
- This prevents bias while maintaining transparency

### Multi-turn Conversations
- Conversations are not limited to one question: the message input stays visible after the first exchange, and `storage.py`'s message list already supported multiple turns - only the frontend previously blocked sending a second message
- Each message, including follow-ups, re-runs the **entire** 3-stage pipeline from scratch (5 advisors → peer rankings → Chairman). There is no lighter incremental/continuation mode - a follow-up is a brand-new council deliberation that happens to have context, not a cheap chat reply
- `build_history_messages()` (in `council.py`) turns prior turns into a simplified alternating history: each prior user query, paired with only the **Chairman's final answer** (`stage3.response`) from that turn. The internal Stage 1/Stage 2 deliberation is intentionally NOT replayed into later prompts, to keep prompt size (and cost) bounded as a conversation grows
- History is threaded into Stage 1 (so advisors' opinions are informed by prior turns) and Stage 3 (so the Chairman keeps continuity with its own earlier answers). Stage 2 (peer ranking) is intentionally left history-free, since it only ever evaluates the current turn's Stage 1 responses
- Because every follow-up means 11 fresh model calls (5 Stage 1 + 5 Stage 2 + 1 Stage 3, all at `MODEL_EFFORT = "high"`), `ChatInterface.jsx` shows a `window.confirm()` warning before sending a follow-up so users can cancel instead of accidentally re-triggering a slow/expensive round

### Council Roles Configuration
- The 5 original roles from `DEFAULT_COUNCIL_ROLES` are only a **seed**, not a fixed roster: `roles_storage.py` persists an editable roster to `data/council_roles.json`, and `RolesSettings.jsx` (opened from the sidebar's `⚙` button) gives full CRUD over it - `system_prompt`, `model`, and `effort` are editable per role, roles can be added, and any role (including the 5 originals) can be deleted. `is_default` is purely a UI badge, it protects nothing
- Which roles participate in a given consultation is chosen **once, when the conversation is created** (`NewConversationModal.jsx`), not per-message - a deliberate simplification the user confirmed explicitly, since Stage 2's peer ranking assumes a stable set of participants for the turn, and letting the set change mid-conversation had no clear benefit
- **Snapshot, not reference**: `POST /api/conversations` resolves the selected `role_ids` against the live roster and copies the full role dicts into `conversation["council_roles"]`. Editing or deleting a role in Settings afterward does NOT affect conversations already created - each one keeps using its own snapshot for every follow-up, for its whole lifetime
- Conversations created before this feature existed have no `council_roles` key; `council.resolve_conversation_roles()` falls back to `DEFAULT_COUNCIL_ROLES` for those, and `main.py` persists that fallback back onto the conversation the first time a message is sent post-upgrade (lazy migration), so it becomes a stable snapshot too instead of silently tracking future changes to `config.py`
- The Chairman (`CHAIRMAN_MODEL`) is explicitly OUT of scope for this - it stays a global constant, not part of the editable roster
- The model `<select>` in `RolesSettings.jsx` is populated from a live call to `GET /api/models` (which calls the real Anthropic Models API via `claude_client.list_available_models()`), not a hardcoded list - `config.FALLBACK_MODELS` is the safety net if that call fails
- Role names must be unique roster-wide (case-insensitive, enforced in `main.py` on create/update) because `stage2_collect_rankings()`'s `label_to_model` and `calculate_aggregate_rankings()` both key by role name - two roles sharing a name would silently merge their ranking positions

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
The Chairman is still hardcoded in `backend/config.py` to `CHAIRMAN_MODEL = "claude-opus-5"` (out of scope for the roles editor). Council seats are NOT hardcoded anymore - each role in the (editable) roster carries its own `model`/`effort`, defaulting to `claude-opus-5`/`"high"` only as the initial seed. Because multiple seats can still end up pointing at the same model identifier, `query_models_parallel()` must return a list (not a dict) to avoid collapsing duplicate keys - see `claude_client.py` notes above.

### Council Roles
`DEFAULT_COUNCIL_ROLES` in `backend/config.py` seeds `data/council_roles.json` (see "Council Roles Configuration" above) with 5 advisor personas via per-seat `system_prompt`/`model`/`effort`. They are thinking styles, not job titles, chosen to create natural tension - this is the starting roster, fully editable/deletable at runtime, not a hardcoded constant used directly by the pipeline anymore:
- **The Contrarian** - looks for what's wrong, missing, or likely to fail (downside)
- **The First Principles Thinker** - strips away assumptions, asks what's actually being solved
- **The Expansionist** - looks for missed upside and adjacent opportunities (upside, opposite of Contrarian)
- **The Outsider** - zero context, reacts only to what's in front of it, catches blind spots
- **The Executor** - only cares if/how it can be done fastest (opposite of First Principles)

Both `stage1_collect_responses()` and `stage2_collect_rankings()` query the same `roles` list (the conversation's snapshot, same personas) passed in from `run_full_council()`, so each advisor evaluates rankings from its own persona's perspective, not a neutral one.

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
5. **Follow-up Cost**: Every message, including follow-ups, re-runs all 11 model calls of the full pipeline - there's no lightweight "just answer inline" mode. A conversation with N turns costs N full council rounds, not N single-query calls
6. **Role Roster Has No "Reset to Defaults" Button**: deleting a role is permanent; there's no UI undo. To get back to the original 5, delete `data/council_roles.json` and restart the backend - it re-seeds from `DEFAULT_COUNCIL_ROLES` on next read. Deliberately left out of scope to avoid a destructive "wipe the whole roster" action nobody asked for
7. **`PUT /api/roles/{id}` Partial Updates**: must build the update dict with Pydantic's `exclude_unset=True`, not a plain `.dict()`/`.model_dump()` - otherwise an update that only touches `name` would silently null out the existing `effort`

## Future Enhancement Ideas

- Configurable Chairman via UI (council roles are now configurable - see "Council Roles Configuration"; the Chairman model/effort is still a hardcoded constant)
- "Reset to defaults" button for the role roster (currently: delete `data/council_roles.json` and restart the backend)
- Export conversations to markdown/PDF
- Model performance analytics over time
- Custom ranking criteria (not just accuracy/insight)
- Support for reasoning models (o1, etc.) with special handling

## Testing Notes

Use a small script with the `anthropic` SDK to verify API connectivity and test different Claude model identifiers before adding them to the council.

## Data Flow Summary

```
Conversation's council_roles snapshot → resolve_conversation_roles() → roles (or DEFAULT_COUNCIL_ROLES fallback)
Prior conversation messages → build_history_messages() → history (user query + Chairman answer per turn)
    ↓
User Query (+ roles, + history)
    ↓
Stage 1: Parallel queries to `roles` (with history) → [individual responses]
    ↓
Stage 2: Anonymize → Parallel ranking queries (no history) → [evaluations + parsed rankings]
    ↓
Aggregate Rankings Calculation → [sorted by avg position]
    ↓
Stage 3: Chairman synthesis with full context (+ history)
    ↓
Emit via SSE as each stage completes: stage1_complete → stage2_complete → stage3_complete → complete
    ↓
Frontend: Display with tabs + validation UI, progressively as each stage arrives
```

The entire flow is async/parallel where possible to minimize latency. Every user message (first or follow-up) runs this full flow from scratch - `history` only adds context, it never skips a stage.
