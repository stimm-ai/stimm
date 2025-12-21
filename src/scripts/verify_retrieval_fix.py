import asyncio
import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.rag.retrieval_engine import RetrievalEngine


async def verify_retrieval():
    print("🚀 Verifying RAG Retrieval Fix")
    print("=" * 60)

    # Question from the user
    query = "Quel est le plafond de revenus pour un ménage aux revenus très modestes Hors île de France avec une personne au foyer ?"

    # Target document ID (17 173 €)
    target_id = "77506116-d2dc-5a40-bb34-5f6ead012f94"

    print(f"Query: {query}")
    print(f"Target Document ID: {target_id}")

    try:
        # Initialize engine with reranker enabled
        print("\n1. Initializing RetrievalEngine with reranker ENABLED...")
        engine = RetrievalEngine(collection_name="MPR", enable_reranker=True, reranker_model="cross-encoder/ms-marco-MiniLM-L-6-v2", top_k=5)

        # Check if reranker loaded correctly
        if engine.reranker:
            print("✅ Reranker loaded successfully!")
        else:
            print("❌ Reranker FAILED to load. Check onnx_models.py mapping.")
            return False

        # Perform retrieval
        print("\n2. Performing retrieval with reranker...")
        contexts = await engine.retrieve_contexts(query, use_cache=False)

        if not contexts:
            print("❌ No contexts retrieved.")
            return False

        print(f"\nTop {len(contexts)} results with reranker:")
        found_target = False
        for i, ctx in enumerate(contexts):
            doc_id = ctx.metadata.get("doc_id")
            score = ctx.score
            is_target = doc_id == target_id
            marker = "🎯" if is_target else "  "

            # Extract the amount from text to show it's working
            # Looking for something like "1 17 173" or similar
            text_snippet = ctx.text[:100].replace("\n", " ")

            print(f"{i + 1}. {marker} ID: {doc_id} | Score: {score:.4f} | Snippet: {text_snippet}...")

            if is_target:
                found_target = True
                if i == 0:
                    print("   🏆 SUCCESS: Correct document is ranked #1!")
                else:
                    print(f"   ⚠️ Correct document is ranked #{i + 1}")

        if not found_target:
            print(f"❌ Target document {target_id} not found in top results.")
            return False

        return contexts[0].metadata.get("doc_id") == target_id

    except Exception as e:
        print(f"❌ Error during verification: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(verify_retrieval())
    if success:
        print("\n✅ VERIFICATION PASSED")
        sys.exit(0)
    else:
        print("\n❌ VERIFICATION FAILED")
        sys.exit(1)
