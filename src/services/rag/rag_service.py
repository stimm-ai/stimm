"""
RAG Service Core Logic

This module contains the core service logic for conversation management and document handling.
"""

import time
from typing import Any, Dict, List, Optional

from .rag_models import ConversationEntry
from .rag_state import RagState
from .config import rag_config

# Configuration constants
CONV_CACHE_LIMIT = rag_config.conv_cache_limit
CONV_CACHE_TTL_SECONDS = rag_config.conv_cache_ttl_seconds
CONV_MAX_RETURN_MESSAGES = rag_config.conv_max_return_messages


async def _prune_conversations(state: RagState) -> None:
    """Prune expired conversations from the cache."""
    now = time.time()
    while state.conversations:
        conv_id, entry = next(iter(state.conversations.items()))
        if entry.expiry > now:
            break
        state.conversations.pop(conv_id, None)


async def _touch_conversation(
    state: RagState, conversation_id: str, message: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Update conversation with new message and return recent messages."""
    await _prune_conversations(state)
    now = time.time()
    entry = state.conversations.get(conversation_id)
    if not entry:
        entry = ConversationEntry(messages=[], expiry=now + CONV_CACHE_TTL_SECONDS)
        state.conversations[conversation_id] = entry
    else:
        entry.expiry = now + CONV_CACHE_TTL_SECONDS
        # Ensure LRU ordering is maintained when touched
        state.conversations.move_to_end(conversation_id)
    if message:
        entry.messages.append(message)
        if len(entry.messages) > CONV_CACHE_LIMIT:
            entry.messages[:] = entry.messages[-CONV_CACHE_LIMIT:]
    return entry.messages[-CONV_MAX_RETURN_MESSAGES:]