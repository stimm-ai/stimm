"""
LLM Streaming Tests
"""

import pytest
import asyncio
import sys
import os

# Add the parent directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.llm.llm import LLMService

@pytest.mark.asyncio
async def test_llm_generation():
    """Test LLM text generation"""
    llm_service = LLMService()
    prompt = "Test prompt"
    result = await llm_service.generate(prompt)

    assert isinstance(result, str)
    assert len(result) > 0

@pytest.mark.asyncio
async def test_llm_streaming():
    """Test LLM streaming generation"""
    llm_service = LLMService()
    prompt = "Test prompt"
    
    chunks = []
    async for chunk in llm_service.generate_stream(prompt):
        chunks.append(chunk)
    
    assert len(chunks) > 0
    full_text = "".join(chunks)
    assert isinstance(full_text, str)
    assert len(full_text) > 0