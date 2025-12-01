"""
Chatbot Service for RAG Integration

This module provides a service layer for the chatbot functionality
that avoids circular dependencies with the RAG routes.
"""

import json
import logging
import uuid
import time
from typing import Dict, Any, AsyncIterator

from .rag_models import QueryRequest, ConversationUpdateRequest
from .rag_service import _touch_conversation
from .rag_state import RagState
from .config import rag_config
from services.retrieval import _retrieve_contexts, _ultra_fast_retrieve_contexts
from ..llm.llm import LLMService

LOGGER = logging.getLogger("rag_chatbot")

class ChatbotService:
    """Service for handling chatbot operations with RAG integration"""
    
    def __init__(self):
        # LLM service will be created per request with agent configuration
        self.llm_service = None
        self._is_prewarmed = False
    
    async def prewarm_models(self, agent_id: str = None, session_id: str = None):
        """Pre-warm models and connections at startup"""
        if self._is_prewarmed:
            return
            
        LOGGER.info("Pre-warming chatbot models and connections...")
        start_time = time.time()
        
        try:
            # Create LLM service with agent configuration for pre-warming
            llm_service = LLMService(agent_id=agent_id, session_id=session_id)
            
            # Pre-warm with a simple query to load models
            dummy_query = "hello"
            try:
                # This will trigger model loading if not already loaded
                async for _ in llm_service.generate_stream(dummy_query):
                    break
            except Exception as e:
                LOGGER.debug(f"Pre-warm query completed (expected): {e}")
            
            self._is_prewarmed = True
            prewarm_time = time.time() - start_time
            LOGGER.info(f"Chatbot models pre-warmed in {prewarm_time:.2f}s")
            
        except Exception as e:
            LOGGER.error(f"Failed to pre-warm chatbot models: {e}")
        finally:
            if 'llm_service' in locals() and llm_service:
                await llm_service.close()
    
    async def process_chat_message(self, message: str, conversation_id: str = None, rag_state: RagState = None, agent_id: str = None, session_id: str = None):
        """
        Process a chat message with RAG context and return a streaming response
        
        Args:
            message: User message
            conversation_id: Optional conversation ID
            rag_state: RAG state instance
            agent_id: Optional agent ID for provider configuration
            session_id: Optional session ID for tracking
            
        Yields:
            Dict with response data
        """
        conversation_id = conversation_id or str(uuid.uuid4())
        processing_start = time.time()
        
        try:
            # Create LLM service with agent configuration
            self.llm_service = LLMService(agent_id=agent_id, session_id=session_id)
            
            # Ensure models are pre-warmed
            if not self._is_prewarmed:
                await self.prewarm_models(agent_id=agent_id, session_id=session_id)
            
            # Check if RAG state is properly initialized
            if rag_state.client is None or rag_state.embedder is None:
                LOGGER.warning("RAG state not fully initialized - falling back to basic LLM response")
                yield {
                    "type": "chunk",
                    "content": "⚠️ RAG system is not available. ",
                    "conversation_id": conversation_id
                }
                yield {
                    "type": "chunk",
                    "content": "I'll answer your question without access to the knowledge base: ",
                    "conversation_id": conversation_id
                }
                context_text = ""
            else:
                # Step 1: Retrieve relevant contexts using RAG
                rag_start = time.time()
                async with rag_state.lock:
                    await rag_state.ensure_ready()
                    
                    # Add user message to conversation
                    user_message = {
                        "role": "user",
                        "content": message,
                        "metadata": {},
                        "created_at": time.time(),
                    }
                    conversation_messages = await _touch_conversation(
                        rag_state, conversation_id, user_message
                    )
                    
                    # Always use ultra-low latency retrieval for voicebot
                    LOGGER.info("Using ultra-low latency retrieval mode")
                    contexts = await _ultra_fast_retrieve_contexts(
                        rag_state.embedder,
                        rag_state.client,
                        rag_state.lexical_index,
                        rag_state.documents,
                        text=message,
                        namespace=None,
                    )
                
                rag_time = time.time() - rag_start
                LOGGER.info(f"RAG retrieval completed in {rag_time:.3f}s (ultra-low latency mode)")
                LOGGER.info(f"Retrieved {len(contexts)} context chunks")
                for i, ctx in enumerate(contexts):
                    LOGGER.info(f"Context {i+1}: {ctx.text[:100]}...")
                
                # Step 2: Build the prompt with retrieved contexts
                context_text = "\n\n".join([ctx.text for ctx in contexts])
            
            # Step 3: Build conversation history for context
            conversation_history = ""
            if rag_state and conversation_id in rag_state.conversations:
                conv_entry = rag_state.conversations[conversation_id]
                # Get recent messages (excluding current one being processed)
                recent_messages = conv_entry.messages[:-1] if conv_entry.messages else []
                if recent_messages:
                    conversation_history = "\n\nHistorique de la conversation:\n"
                    for msg in recent_messages[-4:]:  # Last 4 messages for context
                        role = msg.get("role", "unknown")
                        content = msg.get("content", "")
                        if role == "user":
                            conversation_history += f"Client: {content}\n"
                        elif role == "assistant":
                            conversation_history += f"Assistant: {content}\n"
            
            # Step 4: Build the prompt using the configured system prompt
            # Use the agent's system prompt if available, otherwise fallback to the hardcoded French prompt
            if self.llm_service.agent_config and self.llm_service.agent_config.system_prompt:
                base_system_prompt = self.llm_service.agent_config.system_prompt
            else:
                base_system_prompt = rag_config.get_system_prompt()
            
            # Build the complete prompt with system instructions, conversation history, and user message
            if context_text:
                # Include context and conversation history in the system prompt for RAG
                enhanced_system_prompt = f"{base_system_prompt}\n\nContexte fourni:\n{context_text}{conversation_history}\n\nQuestion actuelle de l'utilisateur: {message}"
            else:
                # No context available, use base system prompt with conversation history and user message
                enhanced_system_prompt = f"{base_system_prompt}{conversation_history}\n\nQuestion actuelle de l'utilisateur: {message}"
            
            # Step 4: Stream the LLM response with first token tracking
            full_response = ""
            first_token_sent = False
            llm_start = time.time()
            
            async for chunk in self.llm_service.generate_stream(enhanced_system_prompt):
                full_response += chunk
                
                # Track first token
                if not first_token_sent:
                    first_token_sent = True
                    first_token_time = time.time() - processing_start
                    LOGGER.info(f"First token received in {first_token_time:.3f}s")
                    yield {
                        "type": "first_token",
                        "content": chunk,
                        "conversation_id": conversation_id,
                        "latency_metrics": {
                            "rag_retrieval_time": rag_time if 'rag_time' in locals() else 0,
                            "first_token_time": first_token_time,
                            "total_processing_time": first_token_time
                        }
                    }
                else:
                    yield {
                        "type": "chunk",
                        "content": chunk,
                        "conversation_id": conversation_id
                    }
            
            llm_time = time.time() - llm_start
            total_time = time.time() - processing_start
            
            # Step 4: Add assistant response to conversation
            if rag_state and rag_state.client and rag_state.embedder:
                async with rag_state.lock:
                    await rag_state.ensure_ready()
                    assistant_message = {
                        "role": "assistant",
                        "content": full_response,
                        "metadata": {"contexts_used": [ctx.metadata.get('doc_id', str(i)) for i, ctx in enumerate(contexts)]},
                        "created_at": time.time(),
                    }
                    await _touch_conversation(rag_state, conversation_id, assistant_message)
            
            yield {
                "type": "complete",
                "conversation_id": conversation_id,
                "latency_metrics": {
                    "rag_retrieval_time": rag_time if 'rag_time' in locals() else 0,
                    "llm_generation_time": llm_time,
                    "total_processing_time": total_time
                }
            }
            
            LOGGER.info(f"Total processing time: {total_time:.3f}s (RAG: {rag_time if 'rag_time' in locals() else 0:.3f}s, LLM: {llm_time:.3f}s)")
            
        except Exception as e:
            LOGGER.error(f"Error in chat message processing: {e}")
            yield {
                "type": "error",
                "content": str(e)
            }
        finally:
            if self.llm_service:
                await self.llm_service.close()

# Global chatbot service instance
chatbot_service = ChatbotService()