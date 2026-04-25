"""
Documents module — public API for document retrieval.

Now backed by ChromaDB + Local Embeddings + Chunking (see chroma_store.py).
The search_documents() function is kept for backward compatibility with graph.py.
"""

import json
import logging
import os
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ─── Legacy: raw JSON loader (still used by ingest scripts / tests) ──────────

DOCUMENTS_PATH = os.path.join(os.path.dirname(__file__), "docs", "documents.json")


def load_documents() -> List[Dict[str, Any]]:
    """Load raw documents from JSON file."""
    if not os.path.exists(DOCUMENTS_PATH):
        logger.warning(f"Documents file not found: {DOCUMENTS_PATH}")
        return []
    try:
        with open(DOCUMENTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading documents: {e}")
        return []


# ─── Public search API (used by graph.py retriever node) ─────────────────────

async def search_documents(
    query: str,
    top_k: int = 5,
    score_threshold: float = 0.2,
    query_embedding: Optional[List[float]] = None,
) -> List[Dict[str, Any]]:
    """
    Semantic search via ChromaDB + Local Embeddings + Chunking.

    Args:
        query: Search query text
        top_k: Max results
        score_threshold: Minimum similarity to include (replaces doc_grader)
        query_embedding: Pre-computed embedding vector (reuse from pipeline)

    Returns a list of dicts with keys: id, content, title, score.
    Falls back to keyword search if ChromaDB is unavailable.
    """
    try:
        from src.backend.rag.chroma_store import search_documents_chroma
        results = await search_documents_chroma(
            query,
            top_k=top_k,
            score_threshold=score_threshold,
            query_embedding=query_embedding,
        )
        if results:
            return results
        logger.warning("ChromaDB returned no results — trying keyword fallback.")
    except Exception as e:
        logger.warning(f"ChromaDB search failed, using keyword fallback: {e}")

    # ── Keyword fallback ──────────────────────────────────────────────────────
    return _keyword_search(query, top_k)


def _keyword_search(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Simple token-overlap keyword search as a safety fallback."""
    docs = load_documents()
    if not docs:
        return []

    query_tokens = set(query.lower().split())
    scored: List[Dict[str, Any]] = []

    for doc in docs:
        text = (doc.get("title", "") + " " + doc.get("content", "")).lower()
        hits = sum(1 for token in query_tokens if token in text)
        if hits > 0:
            scored.append({"doc": doc, "hits": hits})

    scored.sort(key=lambda x: x["hits"], reverse=True)
    return [
        {
            "id": item["doc"]["id"],
            "title": item["doc"].get("title", ""),
            "content": item["doc"]["content"],
            "score": 0.0,   # no similarity score in fallback
        }
        for item in scored[:top_k]
    ]
