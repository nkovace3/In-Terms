import asyncio
import logging
import re
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

# feedparser's default User-Agent identifies it as a script, which some bot
# protection rejects outright. A browser User-Agent avoids that — though it
# can't get past IP-based blocking (ESPN refuses GitHub Actions regardless).
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

feeds = [
    # Sports come from CBS rather than ESPN: ESPN's feeds return an empty 202
    # to requests from GitHub Actions (where ingestion runs), even with a
    # browser User-Agent. Verify any new feed with the "Check feeds" workflow.
    # CBS mixes betting picks/odds pieces into its headlines; exclude_betting
    # drops them before they cost anything to process.
    {
        "url": "https://www.cbssports.com/rss/headlines/nba/",
        "source": "CBS Sports",
        "category": "NBA",
        "exclude_betting": True,
    },
    {
        "url": "https://www.cbssports.com/rss/headlines/nfl/",
        "source": "CBS Sports",
        "category": "NFL",
        "exclude_betting": True,
    },
    {
        "url": "https://www.cbssports.com/rss/headlines/mlb/",
        "source": "CBS Sports",
        "category": "MLB",
        "exclude_betting": True,
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

class FeedUnavailableError(Exception):
    """The feed responded with no entries — down, moved, or blocking us."""

async def get_latest_articles(feed) -> list[RSSResult]:
    # feedparser does blocking network I/O — run it off the event loop.
    executed_feed = await asyncio.to_thread(
        feedparser.parse, feed['url'], agent=USER_AGENT
    )
    name = feed_name(feed)

    if not executed_feed.entries:
        # feedparser never raises on HTTP/network errors; it just returns
        # nothing. Raise instead, so the pipeline records it as a failure and
        # the scheduled run goes red rather than quietly saving nothing.
        raise FeedUnavailableError(
            f"Feed {name} returned no entries "
            f"(status={executed_feed.get('status')}, error={executed_feed.get('bozo_exception')})"
        )

    articles = [
        article
        for article in (parse_entry(entry, feed) for entry in executed_feed.entries)
        if article is not None
    ]

    if feed.get('exclude_betting'):
        kept = [article for article in articles if not is_betting_content(article.title)]
        if len(kept) < len(articles):
            logger.info("Feed %s: skipped %d betting articles", name, len(articles) - len(kept))
        articles = kept

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

# Phrases, not single words: "picks" alone would also drop "Mock Draft Top 10
# Picks", and "bets" would drop real business news like "Flutter CEO bets on
# FanDuel promotions". Matched against headlines, case-insensitively.
BETTING_PATTERNS = re.compile(
    r"""
      \bodds\b                                      # "NFL odds, picks, predictions"
    | \bbest\ bets?\b
    | \bprops\b                                     # "player props"
    | \bparlays?\b
    | \bsportsbooks?\b
    | \bbetting\b
    | \b(?:promo|bonus)\ codes?\b
    | \bsportsline\b                                # CBS's betting-model brand
    | \b(?:computer|projection)\ model\b           # "Computer model backs Chiefs"
    | \b(?:nba|nfl|mlb|college\ football|college\ basketball)\ picks\b   # "NBA picks:"
    | \bexpert\ picks\b                             # "Week 9 NFL expert picks"
    """,
    re.IGNORECASE | re.VERBOSE,
)

def is_betting_content(title: str) -> bool:
    return BETTING_PATTERNS.search(title) is not None

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