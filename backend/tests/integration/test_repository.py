"""
Integration tests for the repository layer, run against the real database
(docker-compose.yml's Postgres + pgvector container must be running).

Each test gets an isolated `db_session` (see conftest.py) that's rolled
back afterward, so nothing here touches real data.
"""

from datetime import datetime, timedelta

from repository import article_exists, count_in_terms_since, find_similar_articles, get_article, save_article, save_in_terms
from schemas.outputs import FinalStory, InTermsResult, StoryDynamics
from schemas.rss import RSSResult


def make_article(url: str, category: str = "NBA") -> RSSResult:
    return RSSResult(
        title="Example headline",
        url=url,
        published_at=datetime.utcnow(),
        summary="A short summary.",
        source="ESPN",
        category=category,
    )


def make_story(sensitive: bool | None = False) -> FinalStory:
    return FinalStory(
        headline="A clearer headline",
        summary="A short summary.",
        # FinalStory requires 3-5 key points.
        key_points=["Point one", "Point two", "Point three"],
        sources=[],
        sensitive=sensitive,
    )


async def test_save_and_get_article_roundtrip(db_session):
    article = make_article("https://example.com/roundtrip-test")

    saved = await save_article(
        db=db_session,
        article=article,
        story=make_story(),
        dynamics=StoryDynamics(situation=["milestone"]),
        embedding=[0.1] * 768,
    )

    assert saved.id is not None

    fetched = await get_article(db_session, saved.id)

    assert fetched is not None
    assert fetched.url == "https://example.com/roundtrip-test"
    assert fetched.headline == "A clearer headline"
    assert fetched.key_points == ["Point one", "Point two", "Point three"]
    assert fetched.sensitive is False


async def test_article_exists_before_and_after_save(db_session):
    url = "https://example.com/exists-test"

    assert await article_exists(db_session, url) is False

    await save_article(
        db=db_session,
        article=make_article(url),
        story=make_story(),
        dynamics=StoryDynamics(situation=["milestone"]),
        embedding=[0.1] * 768,
    )

    assert await article_exists(db_session, url) is True


async def test_find_similar_articles_orders_by_distance(db_session):
    # A vector identical to the query (distance 0) should rank ahead of one
    # pointing the opposite direction (maximum cosine distance).
    close_embedding = [1.0] * 768
    far_embedding = [-1.0] * 768
    query_embedding = [1.0] * 768

    close_article = await save_article(
        db=db_session,
        article=make_article("https://example.com/similar-close", category="NBA"),
        story=make_story(),
        dynamics=StoryDynamics(situation=["milestone"]),
        embedding=close_embedding,
    )
    far_article = await save_article(
        db=db_session,
        article=make_article("https://example.com/similar-far", category="NBA"),
        story=make_story(),
        dynamics=StoryDynamics(situation=["milestone"]),
        embedding=far_embedding,
    )

    # A generous limit, not 5: this runs against the real dev database, which
    # already has plenty of NBA articles from actual ingestion runs. We only
    # care that both synthetic rows show up and are correctly ordered
    # relative to each other, not how many real rows rank between them.
    results = await find_similar_articles(
        db=db_session,
        category="NBA",
        embedding=query_embedding,
        limit=1000,
    )

    result_ids = [article.id for article in results]

    assert close_article.id in result_ids
    assert far_article.id in result_ids
    assert result_ids.index(close_article.id) < result_ids.index(far_article.id)


async def test_find_similar_articles_excludes_old_articles(db_session):
    old_article = await save_article(
        db=db_session,
        article=make_article("https://example.com/similar-old", category="NBA"),
        story=make_story(),
        dynamics=StoryDynamics(situation=["milestone"]),
        embedding=[1.0] * 768,
    )
    # find_similar_articles only looks at the last 14 days; backdate this
    # row past that window directly, since save_article always stamps "now".
    old_article.published_at = datetime.utcnow() - timedelta(days=30)
    db_session.flush()

    results = await find_similar_articles(
        db=db_session,
        category="NBA",
        embedding=[1.0] * 768,
        limit=5,
    )

    assert old_article.id not in [article.id for article in results]


async def test_count_in_terms_since_counts_new_generations(db_session):
    # Relative counts, since the dev database may already hold today's rows.
    since = datetime.utcnow() - timedelta(minutes=1)
    before = await count_in_terms_since(db_session, since)

    article = await save_article(
        db=db_session,
        article=make_article("https://example.com/in-terms-count"),
        story=make_story(),
        dynamics=StoryDynamics(situation=["milestone"]),
        embedding=[0.1] * 768,
    )
    await save_in_terms(
        db=db_session,
        article_id=article.id,
        target_category="Reality TV",
        result=InTermsResult.model_construct(headline="h", summary="s", key_points=["a", "b", "c"]),
    )

    assert await count_in_terms_since(db_session, since) == before + 1
    # Rows created before the window don't count.
    assert await count_in_terms_since(db_session, datetime.utcnow() + timedelta(minutes=1)) == 0


async def test_find_similar_articles_can_exclude_sensitive(db_session):
    # In Terms compares against these, so a sensitive (or unclassified) story
    # must never be offered as a parallel.
    ids = {}
    for label, sensitive in (("ok", False), ("sensitive", True), ("unclassified", None)):
        saved = await save_article(
            db=db_session,
            article=make_article(f"https://example.com/similar-{label}", category="NBA"),
            story=make_story(sensitive=sensitive),
            dynamics=StoryDynamics(situation=["milestone"]),
            embedding=[1.0] * 768,
        )
        ids[label] = saved.id

    results = await find_similar_articles(
        db=db_session, category="NBA", embedding=[1.0] * 768, limit=1000, exclude_sensitive=True,
    )
    result_ids = {article.id for article in results}

    assert ids["ok"] in result_ids
    assert ids["sensitive"] not in result_ids
    assert ids["unclassified"] not in result_ids


async def test_find_similar_articles_days_back_widens_the_window(db_session):
    article = await save_article(
        db=db_session,
        article=make_article("https://example.com/similar-60-days", category="NBA"),
        story=make_story(),
        dynamics=StoryDynamics(situation=["milestone"]),
        embedding=[1.0] * 768,
    )
    article.published_at = datetime.utcnow() - timedelta(days=60)
    db_session.flush()

    default_window = await find_similar_articles(db=db_session, category="NBA", embedding=[1.0] * 768, limit=1000)
    wide_window = await find_similar_articles(
        db=db_session, category="NBA", embedding=[1.0] * 768, limit=1000, days_back=90,
    )

    assert article.id not in [a.id for a in default_window]
    assert article.id in [a.id for a in wide_window]
