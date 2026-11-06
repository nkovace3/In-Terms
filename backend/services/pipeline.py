import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from config import get_settings
from services.researcher import research_article, synthesize_search
from services.editor import edit_story
from services.rss import FeedUnavailableError, get_latest_articles, feeds, feed_name
from services.dynamics import extract_dynamics, embed_dynamics
from services.usage import track_usage
from schemas.rss import RSSResult
from database import SessionLocal
from repository import save_article, article_exists

logger = logging.getLogger(__name__)

@dataclass
class FeedResult:
    feed: str
    fetched: int = 0
    saved: int = 0
    skipped: int = 0
    failed: int = 0
    deferred: int = 0
    error: str | None = None

async def run_ingestion() -> list[FeedResult]:
    db = SessionLocal()
    results = []

    try:
        for feed in feeds:
            results.append(await ingest_feed(db, feed))
    finally:
        db.close()

    for result in results:
        log = logger.warning if result.error or result.failed else logger.info
        log(
            "Feed %s: fetched=%d saved=%d skipped=%d deferred=%d failed=%d%s",
            result.feed,
            result.fetched,
            result.saved,
            result.skipped,
            result.deferred,
            result.failed,
            f" error={result.error}" if result.error else "",
        )

    return results

async def ingest_feed(db: Session, feed) -> FeedResult:
    """
    Ingest one feed. Never raises: a feed that can't be fetched, or an
    article that fails partway through, is logged and counted so the rest of
    the run carries on.
    """
    result = FeedResult(feed=feed_name(feed))
    settings = get_settings()
    pricing = settings.pricing()
    limit = settings.max_new_articles_per_feed

    try:
        articles = await get_latest_articles(feed)
    except FeedUnavailableError as exc:
        # Expected failure mode (feed down or blocking us) — one clear line,
        # no stack trace.
        logger.error("%s", exc)
        result.error = f"{type(exc).__name__}: {exc}"
        return result
    except Exception as exc:
        logger.exception("Could not fetch feed %s", result.feed)
        result.error = f"{type(exc).__name__}: {exc}"
        return result

    result.fetched = len(articles)

    for article in articles:
        # Count attempts, not just successes, so a run of failures or
        # deferrals can't blow through the cost cap either.
        if result.saved + result.failed + result.deferred >= limit:
            logger.info("Feed %s hit the cap of %d new articles this run", result.feed, limit)
            break
        try:
            if await article_exists(db, article.url):
                result.skipped += 1
                continue

            with track_usage() as usage:
                story = await process_article(article)
                dynamics = await extract_dynamics(story)
                embedding = await embed_dynamics(dynamics)
                await save_article(db=db, article=article, story=story, dynamics=dynamics, embedding=embedding)

            result.saved += 1
            logger.info("Saved %r [%s]", article.title, usage.summary(pricing))
        except InsufficientResearch as exc:
            # Not saved, so the next run retries it once coverage exists.
            # Not a failure either: a too-new story shouldn't turn the run red.
            result.deferred += 1
            logger.warning("Deferred %r: research didn't cover the story (%s) [%s]", article.title, exc, usage.summary(pricing))
        except Exception:
            # A failed commit leaves the session unusable until rolled back —
            # without this, every later article in the run failed too.
            db.rollback()
            result.failed += 1
            logger.exception("Failed to process %r", article.title)

    return result

class InsufficientResearch(Exception):
    """Research didn't cover the story, so there's nothing to write a card from."""

async def process_article(article: RSSResult):
    intermediary_research = await research_article(article)

    research_results = await synthesize_search(intermediary_research)

    # Without this, the editor still had to fill every card field and
    # published what it was given: "No Information Available" when search
    # found nothing (a story ingested ~2h after publishing), or a card about
    # RealityBlurb itself when search returned the site instead of the story.
    if not research_results.on_topic or not research_results.facts:
        raise InsufficientResearch(
            f"on_topic={research_results.on_topic}, facts={len(research_results.facts)}, "
            f"search results={len(intermediary_research.sources)}"
        )

    final_story = await edit_story(research_results, article.title)

    return final_story
