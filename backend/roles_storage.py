"""JSON-based storage for the editable council roles roster."""

import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import DATA_ROOT, DEFAULT_COUNCIL_ROLES

ROLES_PATH = os.path.join(DATA_ROOT, "council_roles.json")


def ensure_data_dir():
    """Ensure the data directory exists."""
    Path(DATA_ROOT).mkdir(parents=True, exist_ok=True)


def _seed_defaults() -> List[Dict[str, Any]]:
    return [
        {
            "id": str(uuid.uuid4()),
            "name": role["name"],
            "system_prompt": role["system_prompt"],
            "model": role["model"],
            "effort": role["effort"],
            "is_default": True,
        }
        for role in DEFAULT_COUNCIL_ROLES
    ]


def load_roles() -> List[Dict[str, Any]]:
    """
    Load the roles roster, seeding it from DEFAULT_COUNCIL_ROLES on first access.

    Returns:
        List of role dicts: {id, name, system_prompt, model, effort, is_default}
    """
    if not os.path.exists(ROLES_PATH):
        roles = _seed_defaults()
        save_roles(roles)
        return roles

    with open(ROLES_PATH, 'r') as f:
        return json.load(f)


def save_roles(roles: List[Dict[str, Any]]):
    """Persist the full roles roster."""
    ensure_data_dir()
    with open(ROLES_PATH, 'w') as f:
        json.dump(roles, f, indent=2)


def create_role(
    name: str,
    system_prompt: str,
    model: str,
    effort: Optional[str] = None
) -> Dict[str, Any]:
    """
    Add a new role to the roster.

    Args:
        name: Display name for the role (must be unique, case-insensitive)
        system_prompt: Persona/system prompt for this seat
        model: Claude model identifier to use for this seat
        effort: Effort level, or None to omit it (e.g. for models that don't support it)

    Returns:
        The newly created role dict
    """
    roles = load_roles()
    role = {
        "id": str(uuid.uuid4()),
        "name": name,
        "system_prompt": system_prompt,
        "model": model,
        "effort": effort,
        "is_default": False,
    }
    roles.append(role)
    save_roles(roles)
    return role


def update_role(role_id: str, **fields) -> Optional[Dict[str, Any]]:
    """
    Update an existing role. Only keys present in `fields` are touched, so an
    explicit `effort=None` is respected (it means "no effort"), while an
    omitted `effort` key leaves the stored value untouched.

    Args:
        role_id: Role identifier
        **fields: Any of name/system_prompt/model/effort to update

    Returns:
        The updated role dict, or None if role_id doesn't exist
    """
    roles = load_roles()
    for role in roles:
        if role["id"] == role_id:
            role.update(fields)
            save_roles(roles)
            return role
    return None


def delete_role(role_id: str) -> bool:
    """
    Remove a role from the roster.

    Args:
        role_id: Role identifier

    Returns:
        True if the role was deleted, False if it didn't exist
    """
    roles = load_roles()
    remaining = [r for r in roles if r["id"] != role_id]
    if len(remaining) == len(roles):
        return False
    save_roles(remaining)
    return True
