"""
Semantic FAQ Cache — Giảm thiểu số lần gọi LLM API.

UPDATED: Dùng local embedding (SentenceTransformer) thay vì OpenAI API.
         Hỗ trợ reuse embedding vector để tránh embed cùng câu hỏi 2 lần.

Cơ chế:
  1. Khi câu hỏi đến, embed nó bằng local model (~0.05s).
  2. Tìm câu hỏi tương tự nhất trong cache (ChromaDB collection "faq_cache").
  3. Nếu similarity >= threshold → trả về câu trả lời đã cache (0 LLM call).
  4. Nếu không → chạy full pipeline, lưu kết quả vào cache.

Collections:
  - "faq_cache"         : câu hỏi thực tế từ người dùng (auto-learned)
  - "faq_predefined"    : FAQ được seed sẵn bởi admin
"""

import json
import logging
import os
import time
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from chromadb.config import Settings

from src.backend.rag.local_embeddings import (
    embed_query,
    embed_documents,
    aembed_query,
)

logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────

_RAG_DIR = Path(__file__).parent
CHROMA_PERSIST_DIR = str(_RAG_DIR / "chroma_db")

# Minimum cosine similarity để coi là "same question"
DEFAULT_SIMILARITY_THRESHOLD = 0.82

# Số lần một câu trả lời được cache hit trước khi expire (0 = không expire)
MAX_CACHE_SIZE = 500          # số entry tối đa trong auto-cache
CACHE_TTL_SECONDS = 86400 * 7  # 7 ngày (0 = không TTL)


# ─── FAQ Cache ────────────────────────────────────────────────────────────────

class FAQCache:
    """
    Semantic cache cho chatbot responses.

    Ví dụ:
        cache = FAQCache()
        hit, result = cache.lookup("Tôi được nghỉ bao nhiêu ngày phép?")
        if hit:
            return result  # instant, no LLM
        else:
            result = run_full_pipeline(question)
            cache.store(question, result, question_embedding=result["embedding"])
    """

    def __init__(
        self,
        persist_dir: str = CHROMA_PERSIST_DIR,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ):
        self._threshold = similarity_threshold

        # ChromaDB client (shared persist dir with document store)
        os.makedirs(persist_dir, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )

        # Auto-learned cache (filled at runtime)
        self._auto_col = self._client.get_or_create_collection(
            name="faq_cache",
            metadata={"hnsw:space": "cosine"},
        )

        # Pre-defined FAQ (seeded by admin)
        self._predef_col = self._client.get_or_create_collection(
            name="faq_predefined",
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(
            f"FAQCache ready — threshold={self._threshold}, "
            f"auto={self._auto_col.count()} entries, "
            f"predefined={self._predef_col.count()} entries"
        )

    # ── Lookup ────────────────────────────────────────────────────────────────

    async def lookup(self, question: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Tìm câu trả lời đã cache cho câu hỏi.

        Returns:
            (True, cached_result)  nếu tìm thấy match đủ tốt
                cached_result chứa: final_answer, sources, actions_taken, cache_score,
                                    cached_question, question_embedding (để reuse)
            (False, {"question_embedding": [...]})  nếu cache miss (trả embedding để reuse)
        """
        try:
            # Embed bằng local model (~0.05s thay vì ~8s)
            q_embedding = await aembed_query(question)
        except Exception as e:
            logger.warning(f"FAQ cache embed failed: {e}")
            return False, None

        # Tìm trong cả 2 collections, lấy match tốt nhất
        best_score = 0.0
        best_result = None

        for col in (self._predef_col, self._auto_col):
            if col.count() == 0:
                continue
            try:
                res = await asyncio.to_thread(
                    col.query,
                    query_embeddings=[q_embedding],
                    n_results=1,
                    include=["metadatas", "distances"],
                )
                if res["metadatas"] and res["metadatas"][0]:
                    dist = res["distances"][0][0]
                    score = round(1.0 - dist, 4)   # cosine similarity
                    meta = res["metadatas"][0][0]
                    if score > best_score:
                        best_score = score
                        best_result = meta
            except Exception as e:
                logger.warning(f"FAQ cache query error on '{col.name}': {e}")

        if best_score >= self._threshold and best_result:
            logger.info(
                f"✅ FAQ cache HIT (score={best_score:.4f}): "
                f"'{best_result.get('question', '')[:60]}'"
            )
            # Deserialize stored JSON fields
            return True, {
                "final_answer": best_result.get("answer", ""),
                "sources": json.loads(best_result.get("sources", "[]")),
                "actions_taken": json.loads(best_result.get("actions_taken", "[]")) + ["FAQ cache hit"],
                "cache_score": best_score,
                "cached_question": best_result.get("question", ""),
                "question_embedding": q_embedding,  # Trả về để reuse
            }

        logger.info(
            f"❌ FAQ cache MISS (best_score={best_score:.4f}): '{question[:60]}'"
        )
        # Cache miss — vẫn trả embedding để pipeline reuse
        return False, {"question_embedding": q_embedding}

    # ── Store ─────────────────────────────────────────────────────────────────

    async def store(
        self,
        question: str,
        answer: str,
        sources: Optional[List[str]] = None,
        actions_taken: Optional[List[str]] = None,
        question_embedding: Optional[List[float]] = None,
    ) -> bool:
        """
        Lưu kết quả mới vào auto-cache.

        Args:
            question_embedding: Pre-computed embedding (reuse từ lookup).
                                Nếu None → sẽ embed lại.

        Returns True nếu lưu thành công.
        """
        # Giới hạn cache size (xóa entry cũ nhất nếu full)
        await asyncio.to_thread(self._evict_if_needed)

        # Reuse embedding nếu có, không gọi API lại
        if question_embedding is None:
            try:
                question_embedding = await aembed_query(question)
            except Exception as e:
                logger.warning(f"FAQ cache store embed failed: {e}")
                return False

        entry_id = f"cache_{int(time.time() * 1000)}"
        try:
            await asyncio.to_thread(
                self._auto_col.upsert,
                ids=[entry_id],
                embeddings=[question_embedding],
                documents=[question],
                metadatas=[{
                    "question": question,
                    "answer": answer,
                    "sources": json.dumps(sources or [], ensure_ascii=False),
                    "actions_taken": json.dumps(actions_taken or [], ensure_ascii=False),
                    "timestamp": int(time.time()),
                }],
            )
            logger.info(f"📥 FAQ cache STORE: '{question[:60]}'")
            return True
        except Exception as e:
            logger.warning(f"FAQ cache store failed: {e}")
            return False

    # ── Predefined FAQ seed ───────────────────────────────────────────────────

    def seed_predefined(self, faqs: List[Dict[str, Any]], force: bool = False) -> int:
        """
        Seed FAQ được định nghĩa sẵn (không auto-generated).

        faqs: list of {id, question, answer, sources (list), category}
        Returns: số lượng FAQ đã seed.
        """
        if self._predef_col.count() > 0 and not force:
            logger.info(f"Predefined FAQ already seeded ({self._predef_col.count()} entries). Skip.")
            return self._predef_col.count()

        if force and self._predef_col.count() > 0:
            self._client.delete_collection("faq_predefined")
            self._predef_col = self._client.get_or_create_collection(
                name="faq_predefined",
                metadata={"hnsw:space": "cosine"},
            )

        ids, documents, metadatas = [], [], []

        logger.info(f"Embedding {len(faqs)} predefined FAQs (local)...")
        texts = [f["question"] for f in faqs]
        embs = embed_documents(texts)

        for faq, emb in zip(faqs, embs):
            ids.append(faq.get("id", f"faq_{len(ids)}"))
            documents.append(faq["question"])
            metadatas.append({
                "question": faq["question"],
                "answer": faq["answer"],
                "sources": json.dumps(faq.get("sources", []), ensure_ascii=False),
                "actions_taken": json.dumps([], ensure_ascii=False),
                "category": faq.get("category", "general"),
                "timestamp": int(time.time()),
            })

        self._predef_col.upsert(
            ids=ids,
            embeddings=embs,
            documents=documents,
            metadatas=metadatas,
        )
        count = self._predef_col.count()
        logger.info(f"✅ Seeded {count} predefined FAQs.")
        return count

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _evict_if_needed(self):
        """Xóa các entry cũ nhất nếu cache đầy."""
        count = self._auto_col.count()
        if count < MAX_CACHE_SIZE:
            return
        # Lấy tất cả metadata để tìm entry cũ nhất
        try:
            all_items = self._auto_col.get(include=["metadatas"])
            pairs = list(zip(all_items["ids"], all_items["metadatas"]))
            pairs.sort(key=lambda x: x[1].get("timestamp", 0))
            # Xóa 10% entry cũ nhất
            to_delete = [p[0] for p in pairs[: max(1, count // 10)]]
            self._auto_col.delete(ids=to_delete)
            logger.info(f"FAQ cache evicted {len(to_delete)} old entries.")
        except Exception as e:
            logger.warning(f"Cache eviction failed: {e}")

    def stats(self) -> Dict[str, Any]:
        """Trả về thống kê cache hiện tại."""
        return {
            "predefined_count": self._predef_col.count(),
            "auto_cache_count": self._auto_col.count(),
            "similarity_threshold": self._threshold,
            "max_cache_size": MAX_CACHE_SIZE,
        }

    def clear_auto_cache(self) -> int:
        """Xóa toàn bộ auto-learned cache (giữ lại predefined)."""
        count = self._auto_col.count()
        self._client.delete_collection("faq_cache")
        self._auto_col = self._client.get_or_create_collection(
            name="faq_cache",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"Cleared {count} auto-cache entries.")
        return count


# ─── Singleton ────────────────────────────────────────────────────────────────

_faq_cache: Optional[FAQCache] = None


def get_faq_cache() -> FAQCache:
    """Return module-level singleton FAQCache."""
    global _faq_cache
    if _faq_cache is None:
        _faq_cache = FAQCache()
    return _faq_cache
