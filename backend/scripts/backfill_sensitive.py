"""
Classify articles saved before the `sensitive` column existed.

Only touches rows where `sensitive` IS NULL, so it's safe to re-run. One
cheap LLM call per article. Dry run by default — prints what it would set.

    uv run python -m scripts.backfill_sensitive           # dry run
    uv run python -m scripts.backfill_sensitive --apply   # write results
"""

import argparse
import asyncio

from sqlalchemy import select

from database import SessionLocal
from models import Article
from services.sensitivity import classify_sensitivity


async def backfill(apply: bool) -> None:
    db = SessionLocal()
    try:
        articles = db.scalars(select(Article).where(Article.sensitive.is_(None)).order_by(Article.id)).all()
        flagged = 0

        for article in articles:
            sensitive = await classify_sensitivity(article.headline, article.summary, article.key_points)
            if sensitive:
                flagged += 1
                print(f"SENSITIVE {article.id:>4} [{article.category}] {article.headline}")
            article.sensitive = sensitive

        print(f"\n{flagged} of {len(articles)} unclassified articles flagged sensitive.")

        if apply:
            db.commit()
            print("Saved.")
        else:
            db.rollback()
            print("Dry run, nothing saved. Re-run with --apply to write.")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--apply", action="store_true", help="write results (default: dry run)")
    asyncio.run(backfill(parser.parse_args().apply))


if __name__ == "__main__":
    main()
