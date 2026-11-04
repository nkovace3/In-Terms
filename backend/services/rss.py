import feedparser
from schemas.rss import RSSResult
from dateutil import parser
from dateutil.tz import gettz

# ESPN_NBA_RSS_URL = "https://www.espn.com/espn/rss/nba/news"
tzinfos = {"EST": gettz("America/New_York")}

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
    executed_feed = feedparser.parse(feed['url'])
    articles = []
    for entry in executed_feed.entries:
        article = RSSResult(
            title=entry.title,
            url=entry.link,
            published_at=parser.parse(entry.published, tzinfos=tzinfos),
            summary=entry.summary,
            source=feed['source'],
            category=feed['category']
        )
        articles.append(article)
    # print(articles)
    return articles