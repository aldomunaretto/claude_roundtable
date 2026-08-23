"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# Anthropic API key
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Council members - list of Claude model identifiers
COUNCIL_MODELS = [
    "claude-opus-4-1-20250805",
    "claude-sonnet-4-5-20250929",
    "claude-3-7-sonnet-20250219",
    "claude-3-5-haiku-20241022",
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "claude-opus-4-1-20250805"

# Data directory for conversation storage
DATA_DIR = "data/conversations"
