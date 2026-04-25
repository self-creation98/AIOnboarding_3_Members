#!/usr/bin/env python3
"""
seed_faq.py — Seed predefined FAQ vào ChromaDB để warm-up FAQ cache.

Chạy một lần (hoặc sau khi cập nhật faq_predefined.json):
    python scripts/seed_faq.py
    python scripts/seed_faq.py --force   # Re-embed toàn bộ
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# ── Project root on sys.path ──────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("seed_faq")

FAQ_PATH = ROOT / "src" / "backend" / "rag" / "docs" / "faq_predefined.json"


def main():
    parser = argparse.ArgumentParser(description="Seed predefined FAQ vào ChromaDB")
    parser.add_argument("--force", action="store_true", help="Xóa và re-seed lại")
    args = parser.parse_args()

    logger.info("=== FAQ Predefined Seeding ===")

    if not FAQ_PATH.exists():
        logger.error(f"FAQ file not found: {FAQ_PATH}")
        sys.exit(1)

    with open(FAQ_PATH, "r", encoding="utf-8") as f:
        faqs = json.load(f)

    logger.info(f"Loaded {len(faqs)} predefined FAQs from {FAQ_PATH}")

    from src.backend.rag.faq_cache import FAQCache
    cache = FAQCache()

    count = cache.seed_predefined(faqs, force=args.force)

    if count > 0:
        logger.info(f"✅ Done! {count} predefined FAQs are ready.")

        # Smoke test
        logger.info("\n🔍 Smoke tests:")
        test_cases = [
            "Tôi được nghỉ phép mấy ngày?",
            "Giờ làm việc là mấy giờ?",
            "Làm sao để xin laptop mới?",
            "Thưởng cuối năm như thế nào?",
        ]
        for q in test_cases:
            hit, result = cache.lookup(q)
            status = f"HIT (score={result.get('cache_score', 0):.3f})" if hit else "MISS"
            logger.info(f"  [{status}] '{q}'")

        logger.info(f"\n📊 Cache stats: {cache.stats()}")
    else:
        logger.error("❌ Seeding failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
