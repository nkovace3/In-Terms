import time

import httpx
from config import get_settings
from schemas.search import Source, SearchResult
from services.usage import record_call

TAVILY_SEARCH_URL = 'https://api.tavily.com/search'

async def search_web(query: str) -> list[SearchResult]:
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            TAVILY_SEARCH_URL,
            headers={'Authorization': f'Bearer {get_settings().tavily_api_key}'},
            json={
                'query': query,
                'topic': 'news',
                'time_range': 'week',
                'max_results': 5,
                'include_answer': False,
                'include_raw_content': False
            }
        )
        response.raise_for_status()
        data = response.json()

    record_call("search", "tavily", time.perf_counter() - start)

    return [
        SearchResult(
            source=Source(
                title=result['title'],
                url=result['url']
            ),
            content=result['content'],
            score=result['score']
        )

        for result in data['results']
    ]
