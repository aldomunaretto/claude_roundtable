"""FastAPI backend for Claude Roundtable."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import json
import asyncio

from . import storage
from . import roles_storage
from .claude_client import list_available_models
from .council import (
    run_full_council,
    generate_conversation_title,
    stage1_collect_responses,
    stage2_collect_rankings,
    stage3_synthesize_final,
    calculate_aggregate_rankings,
    build_history_messages,
    resolve_conversation_roles,
)

app = FastAPI(title="Claude Roundtable API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    role_ids: List[str]


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]
    council_roles: List[Dict[str, Any]] = []


class RoleIn(BaseModel):
    """Request to create a new council role."""
    name: str
    system_prompt: str
    model: str
    effort: Optional[str] = None


class RoleUpdate(BaseModel):
    """Request to partially update a council role. Omitted fields are left
    untouched; an explicit `effort: null` clears the effort."""
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    effort: Optional[str] = None


class RoleOut(BaseModel):
    """A council role as stored in the roster."""
    id: str
    name: str
    system_prompt: str
    model: str
    effort: Optional[str] = None
    is_default: bool


class ModelOption(BaseModel):
    """A Claude model available for use in a role."""
    id: str
    display_name: str


def _validate_role_fields(name: str, system_prompt: str, model: str):
    if not name.strip():
        raise HTTPException(status_code=400, detail="Role name cannot be empty")
    if not system_prompt.strip():
        raise HTTPException(status_code=400, detail="System prompt cannot be empty")
    if not model.strip():
        raise HTTPException(status_code=400, detail="Model cannot be empty")


def _validate_unique_name(name: str, exclude_id: Optional[str] = None):
    existing = roles_storage.load_roles()
    normalized = name.strip().lower()
    for role in existing:
        if role["id"] == exclude_id:
            continue
        if role["name"].strip().lower() == normalized:
            raise HTTPException(status_code=400, detail=f'A role named "{name}" already exists')


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "Claude Roundtable API"}


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    return storage.list_conversations()


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation with a snapshot of the selected council roles."""
    roster = {role["id"]: role for role in roles_storage.load_roles()}
    selected_roles = [roster[role_id] for role_id in request.role_ids if role_id in roster]
    if not selected_roles:
        raise HTTPException(status_code=400, detail="At least one valid role must be selected")

    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id, council_roles=selected_roles)
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    deleted = storage.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "ok"}


@app.get("/api/roles", response_model=List[RoleOut])
async def list_roles():
    """List the current council roles roster."""
    return roles_storage.load_roles()


@app.post("/api/roles", response_model=RoleOut, status_code=201)
async def create_role(request: RoleIn):
    """Add a new council role to the roster."""
    _validate_role_fields(request.name, request.system_prompt, request.model)
    _validate_unique_name(request.name)
    return roles_storage.create_role(
        request.name.strip(), request.system_prompt, request.model, request.effort
    )


@app.put("/api/roles/{role_id}", response_model=RoleOut)
async def update_role(role_id: str, request: RoleUpdate):
    """Partially update a council role (only the fields provided are changed)."""
    updates = request.model_dump(exclude_unset=True)
    if "name" in updates:
        if not updates["name"].strip():
            raise HTTPException(status_code=400, detail="Role name cannot be empty")
        _validate_unique_name(updates["name"], exclude_id=role_id)
        updates["name"] = updates["name"].strip()
    if "system_prompt" in updates and not updates["system_prompt"].strip():
        raise HTTPException(status_code=400, detail="System prompt cannot be empty")
    if "model" in updates and not updates["model"].strip():
        raise HTTPException(status_code=400, detail="Model cannot be empty")

    updated = roles_storage.update_role(role_id, **updates)
    if updated is None:
        raise HTTPException(status_code=404, detail="Role not found")
    return updated


@app.delete("/api/roles/{role_id}")
async def delete_role(role_id: str):
    """Remove a council role from the roster."""
    deleted = roles_storage.delete_role(role_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Role not found")
    return {"status": "ok"}


@app.get("/api/models", response_model=List[ModelOption])
async def list_models():
    """List Claude models available for use in a role, for the role editor's dropdown."""
    return await list_available_models()


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the 3-stage council process.
    Returns the complete response with all stages.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Build history from prior turns before appending the new user message
    history = build_history_messages(conversation["messages"])

    # Resolve which roles this conversation uses (falls back to the original
    # defaults for conversations created before this feature existed, and
    # persists that fallback so it's stable even if the defaults change later)
    roles = resolve_conversation_roles(conversation)
    if "council_roles" not in conversation:
        conversation["council_roles"] = roles
        storage.save_conversation(conversation)

    # Add user message
    storage.add_user_message(conversation_id, request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    # Run the 3-stage council process
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        request.content, roles, history=history
    )

    # Add assistant message with all stages
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result
    )

    # Return the complete response with metadata
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the 3-stage council process.
    Returns Server-Sent Events as each stage completes.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Build history from prior turns before appending the new user message
    history = build_history_messages(conversation["messages"])

    # Resolve which roles this conversation uses (falls back to the original
    # defaults for conversations created before this feature existed, and
    # persists that fallback so it's stable even if the defaults change later)
    roles = resolve_conversation_roles(conversation)
    if "council_roles" not in conversation:
        conversation["council_roles"] = roles
        storage.save_conversation(conversation)

    async def event_generator():
        try:
            # Add user message
            storage.add_user_message(conversation_id, request.content)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # Stage 1: Collect responses
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = await stage1_collect_responses(request.content, roles, history=history)
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2: Collect rankings
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_model = await stage2_collect_rankings(request.content, stage1_results, roles)
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Stage 3: Synthesize final answer
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(request.content, stage1_results, stage2_results, history=history)
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Save complete assistant message
            storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result
            )

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Send error event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
