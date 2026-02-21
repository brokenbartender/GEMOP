import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    from scripts.memory_manager import MemoryManager
except ImportError:
    from memory_manager import MemoryManager
import numpy as np

def test_memory():
    print("--- MemoryManager Integration Test ---")
    mem = MemoryManager()
    
    # 1. Test Cache
    print("\n[Testing Cache]")
    test_key = "test_prompt_123"
    test_val = "This is a cached response."
    mem.cache_response(test_key, test_val)
    hit = mem.get_cached_response(test_key)
    print(f"Cache Hit: {hit == test_val} ('{hit}')")

    # 2. Test Vector Storage (ChromaDB Fallback)
    print("\n[Testing Vector Memory]")
    # Mock embedding (1536 dims for standard compatibility)
    mock_emb = np.random.rand(1536).tolist()
    content = "The secret code for the vault is 8899."
    mem.store_memory(agent_id="test_agent", content=content, embedding=mock_emb)
    print(f"Stored Memory: '{content}'")

    # 3. Test Vector Search
    print("\n[Testing Vector Search]")
    # Search with same embedding should yield high similarity
    results = mem.search_memory(query_embedding=mock_emb, limit=1)
    if results:
        doc, score = results[0]
        print(f"Search Result: '{doc}' (Similarity: {score:.4f})")
    else:
        print("Search Result: (none)")

    mem.close()
    print("\nTest Complete.")

if __name__ == "__main__":
    test_memory()
