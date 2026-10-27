import asyncio

from database import SessionLocal
from services.rss import feeds, get_latest_articles
from services.pipeline import process_article
from services.dynamics import extract_dynamics, embed_dynamics
from repository import save_article, article_exists, get_article, find_similar_articles, save_in_terms
from schemas.outputs import FinalStory, StoryDynamics
from services.in_terms import generate_in_terms, get_or_generate_in_terms

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
        # Get the Batum article
        article = await get_article(db, 23)

        if article is None:
            print("Article not found")
            return

        print("\nOriginal article:")
        print(article.headline)

        # Find the closest Reality TV story
        similar_articles = await find_similar_articles(
            db=db,
            embedding=article.embedding,
            category="Reality TV",
            limit=1,
            # days_back=14,
        )

        similar_article = similar_articles[0] if similar_articles else None

        print("\nClosest Reality TV article:")
        if similar_article:
            print(similar_article.headline)
        else:
            print("None found")

        # Extract dynamics from the retrieved story
        similar_dynamics = None

        if similar_article:
            similar_dynamics = StoryDynamics(**similar_article.dynamics)

        print("\nOriginal dynamics:")
        print(article.dynamics)

        print("\nRetrieved story dynamics:")
        if similar_dynamics:
            print(similar_dynamics)
        else:
            print("None")

        # Reconstruct the original story
        story = FinalStory(
            headline=article.headline,
            summary=article.summary,
            key_points=article.key_points,
            sources=[],
        )

        dynamics = StoryDynamics(**article.dynamics)

        # Generate the In Terms translation
        result = await generate_in_terms(
            story=story,
            dynamics=dynamics,
            target_term="Reality TV",
            similar_article=similar_article,
            similar_dynamics=similar_dynamics,
        )

        print("\nIn Terms:")
        print(result)

        await save_in_terms(db=db, article_id=23, target_category='Reality TV', result=result )

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
