"""
Local Embedding Model — Shared singleton cho toàn bộ RAG pipeline.

Dùng SentenceTransformer chạy local trên GPU/CPU thay vì gọi OpenAI API.
- Model: paraphrase-multilingual-MiniLM-L12-v2 (hỗ trợ tiếng Việt)
- Kích thước: ~480MB, download tự động lần đầu
- Tốc độ: ~0.05s/query (GPU) vs ~8s/query (OpenAI API qua mạng)

Usage:
    from src.backend.rag.local_embeddings import get_embedding_model
    model = get_embedding_model()
    vector = model.encode("Chính sách nghỉ phép")
    vectors = model.encode(["doc1", "doc2", "doc3"])
"""

import logging
import asyncio
from typing import List, Optional

logger = logging.getLogger(__name__)

# ─── Model config ─────────────────────────────────────────────────────────────

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# ─── Singleton ────────────────────────────────────────────────────────────────

_model = None
_model_lock: Optional[asyncio.Lock] = None


def get_embedding_model():
    """
    Return shared SentenceTransformer singleton (sync init).
    Thread-safe for single-process FastAPI.
    """
    global _model
    if _model is None:
        logger.info(f"Loading local embedding model: {MODEL_NAME} ...")
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
        dim = _model.get_embedding_dimension()
        logger.info(f"✅ Local embedding model ready — dim={dim}")
    return _model


def embed_query(text: str) -> List[float]:
    """Embed 1 câu hỏi → vector (sync)."""
    model = get_embedding_model()
    return model.encode(text, normalize_embeddings=True).tolist()


def embed_documents(texts: List[str]) -> List[List[float]]:
    """Embed nhiều texts → list vectors (sync, batch)."""
    model = get_embedding_model()
    embeddings = model.encode(texts, normalize_embeddings=True, batch_size=32)
    return embeddings.tolist()


async def aembed_query(text: str) -> List[float]:
    """Async wrapper — chạy embedding trong thread pool."""
    return await asyncio.to_thread(embed_query, text)


async def aembed_documents(texts: List[str]) -> List[List[float]]:
    """Async wrapper — chạy batch embedding trong thread pool."""
    return await asyncio.to_thread(embed_documents, texts)


def get_embedding_dimension() -> int:
    """Trả về chiều của embedding vector."""
    model = get_embedding_model()
    return model.get_embedding_dimension()
