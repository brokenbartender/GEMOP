from __future__ import annotations

import os
from typing import List, Any
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP
app = FastMCP("semantic-search")

# Placeholder for the embedding model (lazy load)
_model = None

def get_model():
    global _model
    if _model is None:
        try:
            from fastembed import TextEmbedding
            _model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        except ImportError:
            raise ImportError("fastembed is not installed. Please run 'pip install fastembed'.")
    return _model

@app.tool()
def search(query: str, documents: List[str], top_k: int = 3) -> List[str]:
    """
    Perform semantic search over a list of documents.
    Returns the top_k most relevant documents.
    """
    if not documents:
        return []
    
    model = get_model()
    
    # Embed query and docs
    query_embeddings = list(model.embed([query]))
    doc_embeddings = list(model.embed(documents))
    
    # Calculate similarities (simple dot product for normalized embeddings)
    import numpy as np
    
    q_emb = np.array(query_embeddings[0])
    scores = []
    
    for i, d_emb in enumerate(doc_embeddings):
        score = np.dot(q_emb, d_emb)
        scores.append((score, documents[i]))
    
    # Sort by score desc
    scores.sort(key=lambda x: x[0], reverse=True)
    
    return [s[1] for s in scores[:top_k]]

@app.tool()
def embed(text: str) -> List[float]:
    """Generate an embedding vector for a text string."""
    model = get_model()
    embeddings = list(model.embed([text]))
    return [float(x) for x in embeddings[0]]

if __name__ == "__main__":
    app.run()
