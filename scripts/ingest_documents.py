#!/usr/bin/env python3
"""
ingest_documents.py — One-time script to embed and store documents into ChromaDB.

Run once (or whenever documents.json changes):
    python scripts/ingest_documents.py
    python scripts/ingest_documents.py --force   # Re-embed everything
"""

import argparse
import logging
import sys
from pathlib import Path

# ── Project root on sys.path ──────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── Load env vars ─────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("ingest")


def main():
    parser = argparse.ArgumentParser(description="Ingest HR documents into ChromaDB")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete existing vectors and re-ingest from scratch",
    )
    args = parser.parse_args()

    logger.info("=== HR Document Ingestion ===")
    logger.info(f"Force re-ingest: {args.force}")

    from src.backend.rag.chroma_store import ChromaVectorStore, DOCUMENTS_PATH, CHROMA_PERSIST_DIR

    logger.info(f"Documents source : {DOCUMENTS_PATH}")
    logger.info(f"ChromaDB storage : {CHROMA_PERSIST_DIR}")

    store = ChromaVectorStore()
    count = store.ingest(force=args.force)

    if count > 0:
        logger.info(f"✅ Done! {count} documents are ready for semantic search.")
        # Smoke-test with a sample query
        test_query = "nghỉ phép năm bao nhiêu ngày"
        logger.info(f"\n🔍 Smoke test: '{test_query}'")
        import asyncio
        results = asyncio.run(store.search(test_query, top_k=2))
        for i, r in enumerate(results, 1):
            logger.info(f"  [{i}] {r['title']} (score={r['score']:.4f})")
    else:
        logger.error("❌ Ingestion failed or no documents found.")
        sys.exit(1)


if __name__ == "__main__":
    main()
