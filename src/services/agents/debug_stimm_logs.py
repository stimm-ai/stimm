#!/usr/bin/env python3
"""
Script de diagnostic pour identifier où le processus Stimm se bloque.

Ce script teste chaque étape de la chaîne voix -> STT -> LLM -> TTS
"""

import asyncio
import logging
import time

from services.llm.llm import LLMService
from services.rag.chatbot_service import chatbot_service
from services.rag.rag_state import get_rag_state

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def test_step_1_chatbot_service():
    """Test 1: ChatbotService direct"""
    logger.info("🧪 Test 1: ChatbotService direct")
    try:
        start_time = time.time()

        # Test with simple message
        test_message = "Bonjour, comment ça va ?"
        logger.info(f"📝 Sending test message: {test_message}")

        # Get rag state
        rag_state = await get_rag_state()
        logger.info(f"✅ RAG State loaded: client={rag_state.client is not None}, embedder={rag_state.embedder is not None}")

        # Test chatbot service
        response_count = 0
        async for chunk in chatbot_service.process_chat_message(message=test_message, conversation_id="test-conv", rag_state=rag_state, agent_id=None, session_id=None):
            response_count += 1
            chunk_type = chunk.get("type", "unknown")
            content = chunk.get("content", "")

            logger.info(f"📨 Chunk #{response_count}: {chunk_type} - '{content[:50]}...'")

            # Stop after a few chunks to avoid too much output
            if response_count >= 5:
                break

        elapsed = time.time() - start_time
        logger.info(f"✅ Test 1 completed: {response_count} chunks in {elapsed:.2f}s")
        return True

    except Exception as e:
        logger.error(f"❌ Test 1 failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_step_2_llm_service():
    """Test 2: LLMService direct"""
    logger.info("🧪 Test 2: LLMService direct")
    try:
        start_time = time.time()

        llm_service = LLMService()
        logger.info(f"✅ LLM Service initialized: {llm_service.provider.__class__.__name__}")

        test_prompt = "Bonjour, comment ça va ?"
        logger.info(f"📝 Sending test prompt: {test_prompt}")

        response_count = 0
        async for chunk in llm_service.generate_stream(test_prompt):
            response_count += 1
            logger.info(f"📨 LLM Chunk #{response_count}: '{chunk[:30]}...'")

            if response_count >= 3:
                break

        elapsed = time.time() - start_time
        logger.info(f"✅ Test 2 completed: {response_count} chunks in {elapsed:.2f}s")
        return True

    except Exception as e:
        logger.error(f"❌ Test 2 failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_step_3_rag_state():
    """Test 3: RAG State"""
    logger.info("🧪 Test 3: RAG State")
    try:
        start_time = time.time()

        rag_state = await get_rag_state()
        logger.info("🔧 RAG State details:")
        logger.info(f"   - Client: {rag_state.client}")
        logger.info(f"   - Embedder: {rag_state.embedder}")
        logger.info(f"   - Reranker: {rag_state.reranker}")
        logger.info(f"   - Documents count: {len(rag_state.documents) if rag_state.documents else 0}")
        logger.info(f"   - Conversations: {len(rag_state.conversations) if rag_state.conversations else 0}")

        # Test readiness
        async with rag_state.lock:
            await rag_state.ensure_ready()
            logger.info("✅ RAG State is ready")

        elapsed = time.time() - start_time
        logger.info(f"✅ Test 3 completed in {elapsed:.2f}s")
        return True

    except Exception as e:
        logger.error(f"❌ Test 3 failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_step_4_integration():
    """Test 4: Full integration test"""
    logger.info("🧪 Test 4: Full integration")
    try:
        start_time = time.time()

        # Simulate what happens in event_loop
        test_message = "Bonjour, quels services bancaires proposez-vous ?"
        rag_state = await get_rag_state()

        logger.info(f"🔄 Processing message: {test_message}")

        # Step 1: Process through chatbot
        logger.info("📡 Step 1: Chatbot processing...")
        chatbot_response_count = 0
        async for chunk in chatbot_service.process_chat_message(
            message=test_message,
            conversation_id="test-integration",
            rag_state=rag_state,
            agent_id=None,
            session_id=None,
        ):
            chatbot_response_count += 1
            chunk_type = chunk.get("type", "unknown")

            if chunk_type == "first_token":
                logger.info("🎯 First token received!")
            elif chunk_type == "chunk":
                content = chunk.get("content", "")
                logger.info(f"📝 Chunk: '{content[:30]}...'")
            elif chunk_type == "complete":
                logger.info("✅ Chatbot processing complete")
                break
            elif chunk_type == "error":
                logger.error(f"❌ Chatbot error: {chunk.get('content')}")
                break

            # Limit output
            if chatbot_response_count >= 10:
                break

        elapsed = time.time() - start_time
        logger.info(f"✅ Test 4 completed: {chatbot_response_count} chunks in {elapsed:.2f}s")

        # Summary
        logger.info("📊 INTEGRATION TEST SUMMARY:")
        logger.info("   - Message processed: ✅")
        logger.info(f"   - Chatbot responses: {chatbot_response_count}")
        logger.info(f"   - Processing time: {elapsed:.2f}s")

        if chatbot_response_count > 0:
            logger.info("✅ FULL INTEGRATION WORKING!")
            return True
        else:
            logger.error("❌ NO RESPONSES FROM CHATBOT!")
            return False

    except Exception as e:
        logger.error(f"❌ Test 4 failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Main diagnostic function"""
    logger.info("🔍 Stimm Diagnostic Starting")
    logger.info("=" * 60)

    tests = [
        ("RAG State", test_step_3_rag_state),
        ("LLM Service", test_step_2_llm_service),
        ("Chatbot Service", test_step_1_chatbot_service),
        ("Full Integration", test_step_4_integration),
    ]

    results = {}

    for test_name, test_func in tests:
        logger.info(f"\n🚀 Running {test_name}...")
        try:
            success = await test_func()
            results[test_name] = success
            if success:
                logger.info(f"✅ {test_name}: PASSED")
            else:
                logger.error(f"❌ {test_name}: FAILED")
        except Exception as e:
            logger.error(f"💥 {test_name}: EXCEPTION - {e}")
            results[test_name] = False

    # Final summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 DIAGNOSTIC SUMMARY:")
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"   {test_name}: {status}")

    # Analysis
    logger.info("\n🔍 ANALYSIS:")
    if results.get("RAG State", False) and results.get("LLM Service", False):
        if results.get("Chatbot Service", False):
            logger.info("✅ Core services are working - issue might be in WebRTC integration")
        else:
            logger.error("❌ Chatbot service is failing - this explains why bot doesn't respond")
    else:
        logger.error("❌ Core services are failing - fundamental issue with RAG/LLM setup")

    return all(results.values())


if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)
