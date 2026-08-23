"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# Anthropic API key
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Council members - all seats use Claude Opus 5
COUNCIL_MODELS = [
    "claude-opus-5",
    "claude-opus-5",
    "claude-opus-5",
    "claude-opus-5",
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "claude-opus-5"

# Effort level applied to every request (max token/reasoning spend)
MODEL_EFFORT = "high"

# Data directory for conversation storage
DATA_DIR = "data/conversations"
