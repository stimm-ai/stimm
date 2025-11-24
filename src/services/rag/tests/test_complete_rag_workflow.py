"""
Comprehensive test for the complete RAG workflow: retrieval + context management + LLM generation streaming + conversation management
"""
import pytest
import asyncio
import uuid
import sys
import os
from fastapi.testclient import TestClient
from services.rag.rag_routes import app
from services.rag.rag_state import RagState
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

# Add the parent directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

# Mock the LLM service to avoid configuration issues in test environment
class MockLLMService:
    """Mock LLM service for testing without external dependencies"""
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """Mock generation that returns a simple response based on the prompt"""
        if "personal banking" in prompt.lower():
            return "Bayview Horizon Bank offers personal banking services including checking accounts, savings accounts, and personal loans."
        elif "business banking" in prompt.lower():
            return "Business banking services include business checking accounts, merchant services, and business loans up to $500,000."
        else:
            return "I'm a helpful banking assistant. How can I help you with your banking needs today?"
    
    async def generate_stream(self, prompt: str, **kwargs):
        """Mock streaming generation that yields chunks"""
        response = await self.generate(prompt, **kwargs)
        # Split response into chunks to simulate streaming
        words = response.split()
        for word in words:
            yield word + " "
        yield ""  # Final empty chunk to signal completion

client = TestClient(app)

@pytest.mark.asyncio
async def test_complete_rag_workflow():
    """Test the complete RAG workflow from document ingestion to LLM generation with conversation context."""
    
    # Initialize the RAG service components
    embedder = SentenceTransformer("BAAI/bge-base-en-v1.5")
    qdrant_client = QdrantClient(host="qdrant", port=6333)
    rag_state = RagState()
    rag_state.embedder = embedder
    rag_state.client = qdrant_client
    app.state.rag = rag_state

    # Initialize LLM service
    llm_service = MockLLMService()

    # Store document IDs for cleanup
    ingested_document_ids = []

    # Step 1: Document Ingestion
    print("Step 1: Ingesting test documents...")
    banking_documents = {
        "documents": [
            {
                "text": "Bayview Horizon Bank offers personal banking services including checking accounts, savings accounts, and personal loans.",
                "id": str(uuid.uuid4()),
                "namespace": "banking",
                "metadata": {"source": "website", "category": "personal_banking"}
            },
            {
                "text": "Business banking services include business checking accounts, merchant services, and business loans up to $500,000.",
                "id": str(uuid.uuid4()),
                "namespace": "banking",
                "metadata": {"source": "website", "category": "business_banking"}
            },
            {
                "text": "Our mortgage department offers fixed-rate mortgages, adjustable-rate mortgages, and refinancing options.",
                "id": str(uuid.uuid4()),
                "namespace": "banking",
                "metadata": {"source": "website", "category": "mortgage"}
            }
        ]
    }
    
    # Store document IDs for cleanup
    for doc in banking_documents["documents"]:
        ingested_document_ids.append(doc["id"])
    
    response = client.post("/knowledge/documents", json=banking_documents)
    assert response.status_code == 200
    assert response.json()["inserted"] == 3
    print(f"✓ Ingested {response.json()['inserted']} documents")

    # Step 2: Conversation Management - Start a conversation
    print("Step 2: Starting conversation...")
    conversation_id = "test-complete-workflow-1"
    
    # Add initial user message
    initial_message = {
        "conversation_id": conversation_id,
        "message": {
            "role": "user",
            "content": "Hello, I'm interested in your banking services",
            "metadata": {}
        }
    }
    response = client.post("/conversation/message", json=initial_message)
    assert response.status_code == 200
    assert response.json()["conversation_id"] == conversation_id
    assert len(response.json()["messages"]) == 1
    print("✓ Added initial conversation message")

    # Step 3: Query Retrieval with Context
    print("Step 3: Querying for relevant contexts...")
    query_request = {
        "question": "What personal banking services do you offer?",
        "conversation_id": conversation_id,
        "namespace": "banking",
        "top_k": 3
    }
    
    response = client.post("/rag/query", json=query_request)
    assert response.status_code == 200
    response_data = response.json()
    
    assert "question" in response_data
    assert "conversation_id" in response_data
    assert "contexts" in response_data
    assert "conversation" in response_data
    
    # Verify contexts were retrieved
    contexts = response_data["contexts"]
    assert len(contexts) > 0
    print(f"✓ Retrieved {len(contexts)} relevant contexts")
    
    # Verify conversation history is maintained
    conversation = response_data["conversation"]
    assert len(conversation) == 2  # Initial message + current query
    print("✓ Conversation history maintained")

    # Step 4: LLM Generation with Retrieved Contexts
    print("Step 4: Generating LLM response with retrieved contexts...")
    
    # Build a comprehensive prompt with retrieved contexts
    context_texts = [ctx["text"] for ctx in contexts]
    context_summary = "\n".join([f"- {text}" for text in context_texts])
    
    system_prompt = """You are a helpful banking assistant. Use the provided context to answer the user's question accurately and helpfully."""
    
    user_prompt = f"""Context information:
{context_summary}

User question: {query_request['question']}

Conversation history:
{chr(10).join([f"{msg['role']}: {msg['content']}" for msg in conversation])}

Please provide a helpful response based on the context and conversation history."""
    
    # Test both regular generation and streaming
    print("Testing regular LLM generation...")
    regular_response = await llm_service.generate(user_prompt)
    assert isinstance(regular_response, str)
    assert len(regular_response) > 0
    print("✓ Regular LLM generation successful")
    
    print("Testing LLM streaming generation...")
    chunks = []
    async for chunk in llm_service.generate_stream(user_prompt):
        chunks.append(chunk)
    
    assert len(chunks) > 0
    streamed_response = "".join(chunks)
    assert isinstance(streamed_response, str)
    assert len(streamed_response) > 0
    print("✓ LLM streaming generation successful")

    # Step 5: Add Assistant Response to Conversation
    print("Step 5: Adding assistant response to conversation...")
    assistant_message = {
        "conversation_id": conversation_id,
        "message": {
            "role": "assistant",
            "content": streamed_response,
            "metadata": {"generation_type": "streaming"}
        }
    }
    response = client.post("/conversation/message", json=assistant_message)
    assert response.status_code == 200
    assert len(response.json()["messages"]) == 3  # Initial + query + assistant
    print("✓ Added assistant response to conversation")

    # Step 6: Verify Conversation State
    print("Step 6: Verifying conversation state...")
    response = client.get(f"/conversation/{conversation_id}")
    assert response.status_code == 200
    conversation_state = response.json()
    assert conversation_state["conversation_id"] == conversation_id
    assert len(conversation_state["messages"]) == 3
    
    # Verify message order and content
    messages = conversation_state["messages"]
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello, I'm interested in your banking services"
    assert messages[1]["role"] == "user" 
    assert messages[1]["content"] == "What personal banking services do you offer?"
    assert messages[2]["role"] == "assistant"
    assert len(messages[2]["content"]) > 0
    print("✓ Conversation state verified")

    # Step 7: Test Follow-up Query with Conversation Context
    print("Step 7: Testing follow-up query with conversation context...")
    follow_up_query = {
        "question": "What about business banking?",
        "conversation_id": conversation_id,
        "namespace": "banking",
        "top_k": 2
    }
    
    response = client.post("/rag/query", json=follow_up_query)
    assert response.status_code == 200
    follow_up_data = response.json()
    
    # Should have more conversation history now
    assert len(follow_up_data["conversation"]) == 4  # All previous messages + current query
    assert len(follow_up_data["contexts"]) > 0
    print("✓ Follow-up query with conversation context successful")

    # Step 8: Cleanup - Reset Conversation
    print("Step 8: Cleaning up...")
    response = client.delete(f"/conversation/{conversation_id}")
    assert response.status_code == 200
    assert len(response.json()["messages"]) == 0
    print("✓ Conversation reset successfully")

    # Verify conversation is actually gone
    response = client.get(f"/conversation/{conversation_id}")
    assert response.status_code == 200
    assert len(response.json()["messages"]) == 0
    print("✓ Conversation cleanup verified")

    # Step 9: Cleanup - Delete Ingested Documents from Qdrant
    print("Step 9: Cleaning up ingested documents from Qdrant...")
    if ingested_document_ids:
        try:
            # Use the correct collection name from retrieval config
            from services.retrieval.config import retrieval_config
            collection_name = retrieval_config.qdrant_collection
            qdrant_client.delete(
                collection_name=collection_name,
                points_selector=qmodels.PointIdsList(
                    points=ingested_document_ids
                )
            )
            print(f"✓ Deleted {len(ingested_document_ids)} test documents from Qdrant")
        except Exception as e:
            print(f"⚠️ Warning: Could not delete test documents from Qdrant: {e}")
            print("This is expected if the collection doesn't exist or documents were already deleted")

    print("🎉 Complete RAG workflow test passed successfully!")

if __name__ == "__main__":
    asyncio.run(test_complete_rag_workflow())