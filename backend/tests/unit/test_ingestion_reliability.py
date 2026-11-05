"""
Ingestion failure handling — no database, no network, no API keys required.

The pipeline's collaborators (feed fetching, the LLM steps, the DB session)
are swapped for fakes so each failure mode can be triggered on purpose.
"""

from datetime import datetime, timedelta, timezone

import pytest
from feedparser import FeedParserDict

from schemas.rss import RSSResult
from services import pipeline, rss
from services.usage import Pricing, record_call, track_usage

FEED = {"url": "https://example.com/rss", "source": "Example", "category": "NBA"}


def make_entry(**overrides) -> FeedParserDict:
    fields = {
        "title": "A headline",
        "link": "https://example.com/story",
        "published": "Tue, 03 Nov 2026 12:00:00 EST",
        "summary": "A summary.",
    }
    fields.update(overrides)
    return FeedParserDict({k: v for k, v in fields.items() if v is not None})


def make_article(url: str) -> RSSResult:
    return RSSResult(
        title=f"Story at {url}",
        url=url,
        published_at=datetime(2026, 11, 3, tzinfo=timezone.utc),
        summary="A summary.",
        source="Example",
        category="NBA",
    )


# --- rss.parse_entry ----------------------------------------------------------


def test_parse_entry_builds_result_from_valid_entry():
    article = rss.parse_entry(make_entry(), FEED)

    assert article is not None
    assert article.url == "https://example.com/story"
    assert article.category == "NBA"
    # "EST" resolves via tzinfos, so the result is timezone-aware.
    assert article.published_at.tzinfo is not None


@pytest.mark.parametrize("missing", ["title", "link", "published", "summary"])
def test_parse_entry_skips_entry_missing_a_field(missing):
    assert rss.parse_entry(make_entry(**{missing: None}), FEED) is None


def test_parse_entry_skips_unparseable_date():
    assert rss.parse_entry(make_entry(published="not a date"), FEED) is None


# --- rss betting filter -------------------------------------------------------
# Real headlines from the CBS feeds and earlier ingestion runs.


@pytest.mark.parametrize("title", [
    "Pacers vs. Grizzlies NBA picks: Indiana should have more players available against surprising Memphis",
    "NBA player props, odds, picks: Kyrie Irving among best bets for Wednesday, Nov. 4",
    "Week 9 NFL odds, picks, predictions: Computer model backs Chiefs and Commanders",
    "Best NFL parlay for Sunday from a proven model",
    "FanDuel promo code: Get $200 in bonus bets",
    "Prisco's Week 9 NFL expert picks: Jaguars roll over Lamar Jackson-less Ravens, Cowboys rebound",
])
def test_betting_headlines_are_detected(title):
    assert rss.is_betting_content(title)


@pytest.mark.parametrize("title", [
    "Field Yates Drops 2027 NFL Mock Draft Top 10 Picks",          # draft picks, not betting picks
    "Grading every NBA lottery pick's first two weeks as impressive 2026 rookie class dazzles early",
    "Jordan Love picks Panthers apart; Christian Watson's midgame hospital trip",  # "picks" as a verb
    "New Flutter CEO bets on FanDuel promotions to win customers as profits suffer",  # "bets" as a verb
    "Matthew Stafford's wife calls out NFL over apparent scheduling disadvantage given to Rams",
    "Former Yankees, Rangers All-Star Mark Teixeira wins U.S. House seat in Texas",
    "MLB rumors: The only Oriole not on the trading block, Rays' Drew Rasmussen plan and Astros add to manager hunt",
])
def test_real_news_headlines_are_kept(title):
    assert not rss.is_betting_content(title)


# --- rss staleness ------------------------------------------------------------


def test_recent_feed_is_not_stale():
    now = datetime(2026, 11, 3, tzinfo=timezone.utc)
    assert not rss.is_stale(now - timedelta(hours=5), now=now)


def test_old_feed_is_stale():
    now = datetime(2026, 11, 3, tzinfo=timezone.utc)
    assert rss.is_stale(now - timedelta(days=4), now=now)


def test_staleness_treats_naive_datetimes_as_utc():
    now = datetime(2026, 11, 3, tzinfo=timezone.utc)
    # Would raise TypeError comparing naive and aware without as_utc.
    assert rss.is_stale(datetime(2025, 1, 24), now=now)


# --- pipeline.ingest_feed -----------------------------------------------------


class FakeSession:
    def __init__(self):
        self.rollbacks = 0

    def rollback(self):
        self.rollbacks += 1


@pytest.fixture
def fake_pipeline(monkeypatch):
    """
    Replaces every external step of ingest_feed. Returns a dict of knobs:
    `articles` (what the feed returns), `existing` (URLs already saved),
    `fail_urls` (URLs whose processing raises), and `saved` (what got saved).
    """
    state = {"articles": [], "existing": set(), "fail_urls": set(), "saved": [], "cap": 10}

    async def fake_get_latest_articles(feed):
        return state["articles"]

    async def fake_article_exists(db, url):
        return url in state["existing"]

    async def fake_process_article(article):
        if article.url in state["fail_urls"]:
            raise RuntimeError("LLM call failed")
        return "story"

    async def fake_extract_dynamics(story):
        return "dynamics"

    async def fake_embed_dynamics(dynamics):
        return [0.0]

    async def fake_save_article(db, article, **kwargs):
        state["saved"].append(article.url)

    class FakeSettings:
        max_new_articles_per_feed = state["cap"]

        def pricing(self):
            return None

    monkeypatch.setattr(pipeline, "get_latest_articles", fake_get_latest_articles)
    monkeypatch.setattr(pipeline, "article_exists", fake_article_exists)
    monkeypatch.setattr(pipeline, "process_article", fake_process_article)
    monkeypatch.setattr(pipeline, "extract_dynamics", fake_extract_dynamics)
    monkeypatch.setattr(pipeline, "embed_dynamics", fake_embed_dynamics)
    monkeypatch.setattr(pipeline, "save_article", fake_save_article)
    monkeypatch.setattr(pipeline, "get_settings", lambda: FakeSettings())
    return state


async def test_one_failed_article_does_not_stop_the_rest(fake_pipeline):
    fake_pipeline["articles"] = [make_article(f"https://example.com/{i}") for i in range(3)]
    fake_pipeline["fail_urls"] = {"https://example.com/1"}
    db = FakeSession()

    result = await pipeline.ingest_feed(db, FEED)

    assert fake_pipeline["saved"] == ["https://example.com/0", "https://example.com/2"]
    assert (result.saved, result.failed) == (2, 1)
    # The failure must roll back, or the session stays broken for the next article.
    assert db.rollbacks == 1


async def test_existing_articles_are_skipped(fake_pipeline):
    fake_pipeline["articles"] = [make_article("https://example.com/old"), make_article("https://example.com/new")]
    fake_pipeline["existing"] = {"https://example.com/old"}

    result = await pipeline.ingest_feed(FakeSession(), FEED)

    assert fake_pipeline["saved"] == ["https://example.com/new"]
    assert (result.fetched, result.saved, result.skipped) == (2, 1, 1)


async def test_cost_cap_limits_new_articles_per_feed(monkeypatch, fake_pipeline):
    class CappedSettings:
        max_new_articles_per_feed = 2

        def pricing(self):
            return None

    monkeypatch.setattr(pipeline, "get_settings", lambda: CappedSettings())
    fake_pipeline["articles"] = [make_article(f"https://example.com/{i}") for i in range(5)]
    # Already-saved articles don't count toward the cap — they cost nothing.
    fake_pipeline["existing"] = {"https://example.com/0"}
    fake_pipeline["fail_urls"] = {"https://example.com/1"}

    result = await pipeline.ingest_feed(FakeSession(), FEED)

    # /0 skipped (free), /1 failed (counts), /2 saved (counts) -> cap of 2 hit.
    assert fake_pipeline["saved"] == ["https://example.com/2"]
    assert (result.skipped, result.failed, result.saved) == (1, 1, 1)


async def test_feed_fetch_error_is_reported_not_raised(fake_pipeline, monkeypatch):
    async def broken_fetch(feed):
        raise ConnectionError("DNS failure")

    monkeypatch.setattr(pipeline, "get_latest_articles", broken_fetch)

    result = await pipeline.ingest_feed(FakeSession(), FEED)

    assert result.error == "ConnectionError: DNS failure"
    assert result.saved == 0


async def test_empty_feed_counts_as_a_failure(fake_pipeline, monkeypatch):
    # A blocked/dead feed returns nothing. It must be recorded as an error so
    # the scheduled run goes red — it used to be a warning and the run passed.
    async def empty_feed(feed):
        raise rss.FeedUnavailableError("Feed Example/NBA returned no entries (status=202, error=None)")

    monkeypatch.setattr(pipeline, "get_latest_articles", empty_feed)

    result = await pipeline.ingest_feed(FakeSession(), FEED)

    assert result.error.startswith("FeedUnavailableError")


# --- scheduler --once exit code -----------------------------------------------


@pytest.mark.parametrize(
    "results, expected_exit",
    [
        ([pipeline.FeedResult("A", saved=2), pipeline.FeedResult("B", skipped=5)], 0),
        ([pipeline.FeedResult("A", saved=2), pipeline.FeedResult("B", failed=1)], 1),
        ([pipeline.FeedResult("A", error="ConnectionError: boom")], 1),
    ],
)
def test_run_once_exit_code_reflects_failures(monkeypatch, results, expected_exit):
    # A non-zero exit is what turns the GitHub Actions run red and triggers
    # the failure email, so this is the alerting contract.
    import scheduler

    async def fake_run_ingestion():
        return results

    monkeypatch.setattr(scheduler, "run_ingestion", fake_run_ingestion)
    assert scheduler.run_once() == expected_exit


# --- usage tracking -----------------------------------------------------------


def test_track_usage_totals_calls_inside_the_block_only():
    record_call("llm", "outside", 1.0, input_tokens=999)

    with track_usage() as usage:
        record_call("llm", "ResearchPlan", 0.5, input_tokens=1_000, output_tokens=200)
        record_call("llm", "FinalStory", 0.5, input_tokens=2_000, output_tokens=300)
        record_call("search", "tavily", 0.2)

    assert usage.count("llm") == 2
    assert usage.count("search") == 1
    assert (usage.input_tokens, usage.output_tokens) == (3_000, 500)


def test_cost_estimate():
    with track_usage() as usage:
        record_call("llm", "x", 0.1, input_tokens=1_000_000, output_tokens=500_000)
        record_call("search", "tavily", 0.1)

    pricing = Pricing(llm_input_per_mtok=0.10, llm_output_per_mtok=0.40, search_per_call=0.008)

    # 0.10 (input) + 0.20 (output) + 0.008 (one search)
    assert usage.cost_usd(pricing) == pytest.approx(0.308)
    assert "cost=$0.3080" in usage.summary(pricing)
