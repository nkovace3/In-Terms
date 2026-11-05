"""
Check whether RSS feeds are reachable and parseable from *this machine*.

Useful because some publishers block datacenter IPs: a feed that works on
your laptop can return nothing from GitHub Actions. Run it there via the
"Check feeds" workflow to see what the scheduled ingestion will actually get.

    uv run python -m scripts.check_feeds              # current feeds
    uv run python -m scripts.check_feeds --candidates # possible replacements
"""

import argparse
import asyncio

from services.rss import feed_name, feeds, get_latest_articles, newest_published_at

# Possible replacements for the ESPN sports feeds, which block GitHub Actions.
CANDIDATES = [
    {"url": "https://www.cbssports.com/rss/headlines/nba/", "source": "CBS Sports", "category": "NBA"},
    {"url": "https://www.cbssports.com/rss/headlines/nfl/", "source": "CBS Sports", "category": "NFL"},
    {"url": "https://www.cbssports.com/rss/headlines/mlb/", "source": "CBS Sports", "category": "MLB"},
    {"url": "https://sports.yahoo.com/nba/rss/", "source": "Yahoo Sports", "category": "NBA"},
    {"url": "https://sports.yahoo.com/nfl/rss/", "source": "Yahoo Sports", "category": "NFL"},
    {"url": "https://sports.yahoo.com/mlb/rss/", "source": "Yahoo Sports", "category": "MLB"},
    {"url": "https://www.mlb.com/feeds/news/rss.xml", "source": "MLB.com", "category": "MLB"},
    {"url": "https://profootballtalk.nbcsports.com/feed/", "source": "ProFootballTalk", "category": "NFL"},
    {"url": "https://www.sbnation.com/rss/nba/index.xml", "source": "SB Nation", "category": "NBA"},
    {"url": "https://www.sbnation.com/rss/nfl/index.xml", "source": "SB Nation", "category": "NFL"},
    {"url": "https://www.sbnation.com/rss/mlb/index.xml", "source": "SB Nation", "category": "MLB"},
]


async def check(to_check: list[dict]) -> int:
    failures = 0
    for feed in to_check:
        label = f"{feed_name(feed):<26}"
        try:
            articles = await get_latest_articles(feed)
            if not articles:
                # Entries came back but none were usable (e.g. all missing a
                # summary) — as useless to ingestion as an empty feed.
                failures += 1
                print(f"FAIL  {label} entries returned but none parseable  {feed['url']}")
                continue
            print(f"OK    {label} {len(articles):>3} entries, newest {newest_published_at(articles)}  {feed['url']}")
        except Exception as exc:
            failures += 1
            print(f"FAIL  {label} {exc}  {feed['url']}")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Check RSS feed reachability.")
    parser.add_argument("--candidates", action="store_true", help="Check replacement candidates instead of current feeds.")
    args = parser.parse_args()
    asyncio.run(check(CANDIDATES if args.candidates else feeds))


if __name__ == "__main__":
    main()
