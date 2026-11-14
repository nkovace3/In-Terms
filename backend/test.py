import asyncio

from database import SessionLocal
from services.rss import feeds, get_latest_articles
from services.pipeline import process_article
from services.dynamics import extract_dynamics, embed_dynamics
from repository import save_article, article_exists, get_article, find_similar_articles
from services.in_terms import generate_in_terms_for_article, get_or_generate_in_terms

async def end_to_end_with_embedding():
    db = SessionLocal()

    try:
        for feed in feeds:
            print(f"\n{'=' * 60}")
            print(f"Processing feed: {feed['source']} / {feed['category']}")
            print(f"{'=' * 60}")

            articles = await get_latest_articles(feed)

            print(f"Found {len(articles)} RSS articles")

            for article in articles[:10]:
                print(f"\nChecking: {article.title}")

                if await article_exists(db, article.url):
                    print("Already exists — skipping")
                    continue

                try:
                    print(f"Processing: {article.title}")

                    story = await process_article(article)

                    print("✓ Story generated")

                    dynamics = await extract_dynamics(story)

                    print("✓ Dynamics extracted")

                    embedding = await embed_dynamics(dynamics)

                    print(f"✓ Embedding generated ({len(embedding)} dimensions)")

                    saved = await save_article(
                        db=db,
                        article=article,
                        story=story,
                        dynamics=dynamics,
                        embedding=embedding,
                    )

                    print(f"✓ Saved article ID: {saved.id}")

                except Exception as e:
                    print(f"✗ Failed: {article.title}")
                    print(f"  {e}")

    finally:
        db.close()

async def test_similar_search():
    db = SessionLocal()

    try:
        article = await get_article(db, 5)

        if article is None:
            print("Article not found")
            return

        print(f"Query article: {article.headline}\n")

        similar = await find_similar_articles(
            db,
            'NFL',
            article.embedding,
            limit=1,
        )

        for result in similar:
            print(f"{result.id}: {result.headline}")

    finally:
        db.close()

async def test_in_terms_generation():
    db = SessionLocal()

    try:
        article = await get_article(db, 23)

        if article is None:
            print("Article not found")
            return

        print("\nOriginal article:")
        print(article.headline)

        generation = await generate_in_terms_for_article(db, article, "Reality TV")

        print("\nCandidates:")
        for candidate in generation.candidates:
            print(f"  {candidate.id}: {candidate.headline}")
        print(f"\nParallel: {generation.reference.headline if generation.reference else 'none'}")
        print("\nIn Terms:")
        print(generation.result)

    finally:
        db.close()

async def tiny_test():
    db = SessionLocal()

    try:
        result = await get_or_generate_in_terms(
            db=db,
            article_id=23,
            target_category="Finance",
        )

        print(result.term)
        print(result.explanation)

    finally:
        db.close()

if __name__ == "__main__":
    # asyncio.run(end_to_end_with_embedding())
    asyncio.run(end_to_end_with_embedding())
