"""
ChromaDB Vector Store — Persistent embedding store for RAG documents.

UPDATED: Sử dụng local SentenceTransformer + chunking thay vì OpenAI API.

Handles:
- Loading documents from docs/documents.json
- Chunking documents (400 chars, overlap 80)
- Generating LOCAL embeddings (SentenceTransformer)
- Persisting vectors in ChromaDB (local on-disk)
- Semantic search via cosine similarity
"""

import json
import logging
import os
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

import chromadb
from chromadb.config import Settings

from src.backend.rag.local_embeddings import (
    embed_query,
    embed_documents,
    aembed_query,
    get_embedding_dimension,
)
from src.backend.rag.chunker import chunk_all_documents

logger = logging.getLogger(__name__)

# ─── Paths ───────────────────────────────────────────────────────────────────

_RAG_DIR = Path(__file__).parent
DOCUMENTS_PATH = _RAG_DIR / "docs" / "documents.json"

# ChromaDB persistent storage lives next to this file
CHROMA_PERSIST_DIR = str(_RAG_DIR / "chroma_db")

# Collection name
COLLECTION_NAME = "hr_chunks"  # Renamed: chunks, not whole docs


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _load_json_documents() -> List[Dict[str, Any]]:
    """Load raw documents from JSON file."""
    if not DOCUMENTS_PATH.exists():
        logger.warning(f"Documents file not found: {DOCUMENTS_PATH}")
        return []
    try:
        with open(DOCUMENTS_PATH, "r", encoding="utf-8") as f:
            docs = json.load(f)
        logger.info(f"Loaded {len(docs)} documents from {DOCUMENTS_PATH}")
        return docs
    except Exception as e:
        logger.error(f"Failed to load documents: {e}")
        return []


# ─── ChromaVectorStore ────────────────────────────────────────────────────────

class ChromaVectorStore:
    """
    Wraps ChromaDB + Local Embeddings for persistent chunk retrieval.

    Usage:
        store = ChromaVectorStore()
        store.ingest()          # One-time: chunk, embed & store all documents
        results = store.search("nghỉ phép năm", top_k=5)
    """

    def __init__(
        self,
        persist_dir: str = CHROMA_PERSIST_DIR,
        collection_name: str = COLLECTION_NAME,
    ):
        self._persist_dir = persist_dir
        self._collection_name = collection_name

        # ChromaDB persistent client
        os.makedirs(self._persist_dir, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=self._persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )

        # Get or create collection (ChromaDB manages its own storage)
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},  # Use cosine similarity
        )
        logger.info(
            f"ChromaDB ready — collection='{self._collection_name}', "
            f"path='{self._persist_dir}', "
            f"chunks_stored={self._collection.count()}"
        )

    # ── Ingestion ─────────────────────────────────────────────────────────────

    def ingest(self, force: bool = False) -> int:
        """
        Chunk, embed and store all documents from the JSON file into ChromaDB.

        Args:
            force: If True, wipe existing vectors and re-ingest everything.

        Returns:
            Number of chunks ingested.
        """
        documents = _load_json_documents()
        if not documents:
            logger.warning("No documents to ingest.")
            return 0

        existing_count = self._collection.count()

        if existing_count > 0 and not force:
            logger.info(
                f"Collection already has {existing_count} chunks. "
                "Skipping ingest (use force=True to re-embed)."
            )
            return existing_count

        if force and existing_count > 0:
            logger.info(f"Force re-ingest: deleting {existing_count} existing vectors.")
            self._client.delete_collection(self._collection_name)
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )

        # 1. Chunk documents
        all_chunks = chunk_all_documents(documents, chunk_size=400, overlap=80)

        if not all_chunks:
            logger.warning("No chunks generated.")
            return 0

        # 2. Build texts, ids, and metadata
        ids: List[str] = []
        texts: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for chunk in all_chunks:
            chunk_id = chunk["chunk_id"]
            title = chunk["title"]
            content = chunk["content"]
            category = chunk["category"]

            # Combine title + content for richer embedding context
            full_text = f"{title}: {content}"

            ids.append(chunk_id)
            texts.append(full_text)
            metadatas.append({
                "chunk_id": chunk_id,
                "doc_id": chunk["doc_id"],
                "title": title,
                "category": category,
                "content": content,
                "chunk_index": chunk["chunk_index"],
            })

        # 3. Generate embeddings (LOCAL — fast)
        logger.info(f"Generating local embeddings for {len(texts)} chunks...")
        embeddings = embed_documents(texts)

        # 4. Upsert into ChromaDB
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        count = self._collection.count()
        logger.info(f"✅ Ingested {count} chunks into ChromaDB.")
        return count

    # ── Search ────────────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.2,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search: embed query → find nearest chunks.

        Args:
            query: Search query text
            top_k: Max number of results
            score_threshold: Minimum cosine similarity to include
            query_embedding: Pre-computed embedding (reuse from pipeline state)

        Returns list of dicts with keys: chunk_id, doc_id, title, category, content, score.
        """
        if self._collection.count() == 0:
            logger.warning("Collection is empty. Call ingest() first.")
            return []

        # Reuse embedding if provided, otherwise compute
        if query_embedding is None:
            query_embedding = await aembed_query(query)

        try:
            results = await asyncio.to_thread(
                self._collection.query,
                query_embeddings=[query_embedding],
                n_results=min(top_k, self._collection.count()),
                include=["metadatas", "distances"],
            )
        except Exception as e:
            logger.error(f"ChromaDB query failed: {e}")
            return []

        hits: List[Dict[str, Any]] = []
        metadatas_list = results.get("metadatas", [[]])[0]
        distances_list = results.get("distances", [[]])[0]

        for meta, dist in zip(metadatas_list, distances_list):
            # ChromaDB cosine distance → similarity = 1 - distance
            similarity = round(1.0 - dist, 4)

            # Filter by score threshold (replaces doc_grader)
            if similarity < score_threshold:
                continue

            hits.append({
                "chunk_id": meta.get("chunk_id", ""),
                "doc_id": meta.get("doc_id", ""),
                "id": meta.get("doc_id", ""),  # backward compat
                "title": meta.get("title", ""),
                "category": meta.get("category", ""),
                "content": meta.get("content", ""),
                "score": similarity,
            })

        logger.info(
            f"Search '{query[:60]}' → {len(hits)} results "
            f"(top score: {hits[0]['score'] if hits else 'N/A'})"
        )
        return hits

    # ── Status ────────────────────────────────────────────────────────────────

    def count(self) -> int:
        """Return number of chunks stored."""
        return self._collection.count()

    def is_ready(self) -> bool:
        """True if the collection has at least one chunk."""
        return self._collection.count() > 0


# ─── Module-level Singleton ──────────────────────────────────────────────────

_store: Optional[ChromaVectorStore] = None
_store_lock: Optional[asyncio.Lock] = None

async def get_chroma_store() -> ChromaVectorStore:
    """
    Return the singleton ChromaVectorStore, creating and ingesting if needed.
    Thread-safe for single-process use (FastAPI default).
    """
    global _store, _store_lock
    if _store_lock is None:
        _store_lock = asyncio.Lock()

    if _store is None:
        async with _store_lock:
            # Double check inside the lock
            if _store is None:
                temp_store = ChromaVectorStore()
                if not temp_store.is_ready():
                    logger.info("ChromaDB is empty — running first-time ingestion...")
                    await asyncio.to_thread(temp_store.ingest)
                _store = temp_store
    return _store


# ─── Convenience search function (used by graph.py retriever node) ────────────

async def search_documents_chroma(
    query: str,
    top_k: int = 5,
    score_threshold: float = 0.2,
    query_embedding: Optional[List[float]] = None,
) -> List[Dict[str, Any]]:
    """
    Drop-in replacement for the old search_documents().

    Returns list of dicts with: id, content, title, score.
    """
    store = await get_chroma_store()
    return await store.search(
        query,
        top_k=top_k,
        score_threshold=score_threshold,
        query_embedding=query_embedding,
    )
