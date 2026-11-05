import asyncio
import logging
from datetime import datetime, timedelta, timezone

import feedparser
from schemas.rss import RSSResult
from dateutil import parser
from dateutil.tz import gettz

logger = logging.getLogger(__name__)

# ESPN_NBA_RSS_URL = "https://www.espn.com/espn/rss/nba/news"
tzinfos = {"EST": gettz("America/New_York")}

# Every feed here publishes several times a day, so a newest entry older
# than this almost always means the feed is dead or has moved (which is
# exactly what happened to the old WSJ business feed, unnoticed).
STALE_FEED_AFTER = timedelta(hours=72)

feeds = [
    {
        "url": "https://www.espn.com/espn/rss/nba/news",
        "source": "ESPN",
        "category": "NBA",
    },
    {
        "url": "https://www.espn.com/espn/rss/nfl/news",
        "source": "ESPN",
        "category": "NFL",
    },
    {
        "url": "https://www.espn.com/espn/rss/mlb/news",
        "source": "ESPN",
        "category": "MLB",
    },
    {
        'url': 'https://realityblurb.com/feed/',
        'source': 'RealityBlurb',
        'category': 'Reality TV'
    },
    {
        'url': 'https://feeds.npr.org/1014/rss.xml',
        'source': 'NPR',
        'category': 'US Politics'
    },
    {
        'url': 'https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147',
        'source': 'CNBC',
        'category': 'Business'
    }

]

async def get_latest_articles(feed) -> list[RSSResult]:
    # feedparser does blocking network I/O — run it off the event loop.
    executed_feed = await asyncio.to_thread(feedparser.parse, feed['url'])
    name = feed_name(feed)

    if not executed_feed.entries:
        # feedparser never raises on HTTP/network errors; it just returns
        # nothing, which is how a dead feed used to fail silently.
        logger.warning(
            "Feed %s returned no entries (status=%s, error=%s)",
            name,
            executed_feed.get('status'),
            executed_feed.get('bozo_exception'),
        )
        return []

    articles = [
        article
        for article in (parse_entry(entry, feed) for entry in executed_feed.entries)
        if article is not None
    ]

    newest = newest_published_at(articles)
    if newest is None or is_stale(newest):
        logger.warning(
            "Feed %s looks stale — newest entry published %s. The URL may have moved or the feed may be dead.",
            name,
            newest,
        )

    return articles

def parse_entry(entry, feed) -> RSSResult | None:
    """
    Build an RSSResult from one feed entry, or return None (and log) if the
    entry is missing a field we need. One malformed entry used to raise and
    abort ingestion for every feed after it.
    """
    try:
        return RSSResult(
            title=entry.title,
            url=entry.link,
            published_at=parser.parse(entry.published, tzinfos=tzinfos),
            summary=entry.summary,
            source=feed['source'],
            category=feed['category']
        )
    # AttributeError: feedparser entries raise it for missing fields.
    # ValueError/OverflowError: unparseable dates (and pydantic's
    # ValidationError, which subclasses ValueError).
    except (AttributeError, ValueError, OverflowError) as exc:
        logger.warning(
            "Skipping malformed entry in %s (%s: %s): %r",
            feed_name(feed),
            type(exc).__name__,
            exc,
            entry.get('title', '<no title>'),
        )
        return None

def feed_name(feed) -> str:
    return f"{feed['source']}/{feed['category']}"

def as_utc(value: datetime) -> datetime:
    # Some feeds give dates with no timezone; treat those as UTC so they
    # can be compared with timezone-aware ones.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

def newest_published_at(articles: list[RSSResult]) -> datetime | None:
    if not articles:
        return None
    return max(as_utc(article.published_at) for article in articles)

def is_stale(newest: datetime, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return now - as_utc(newest) > STALE_FEED_AFTER