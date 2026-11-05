"""
Measure what ingesting an article actually costs, without saving anything.

Runs the full pipeline (research -> edit -> dynamics -> embedding) on the
newest article from each of the first N feeds and prints per-article totals
plus a per-step breakdown. Uses real API calls (Gemini + Tavily), so it
spends real credits — keep N small.

    uv run python -m scripts.measure_pipeline           # 3 articles
    uv run python -m scripts.measure_pipeline --count 6

Set LLM_INPUT_USD_PER_MTOK / LLM_OUTPUT_USD_PER_MTOK / SEARCH_USD_PER_CALL
in .env to get dollar figures as well as tokens.
"""

import argparse
import asyncio
import statistics
from collections import defaultdict

from config import get_settings
from logging_config import configure_logging
from services.dynamics import embed_dynamics, extract_dynamics
from services.pipeline import process_article
from services.rss import feed_name, feeds, get_latest_articles
from services.usage import UsageReport, track_usage


async def measure(count: int) -> list[UsageReport]:
    reports = []
    for feed in feeds[:count]:
        articles = await get_latest_articles(feed)
        if not articles:
            print(f"{feed_name(feed)}: no articles, skipping")
            continue

        article = articles[0]
        with track_usage() as usage:
            story = await process_article(article)
            dynamics = await extract_dynamics(story)
            await embed_dynamics(dynamics)

        print(f"{feed_name(feed):<24} {usage.summary(get_settings().pricing())}")
        print(f"{'':<24} {article.title}")
        reports.append(usage)
    return reports


def print_breakdown(reports: list[UsageReport]) -> None:
    by_step = defaultdict(list)
    for report in reports:
        for call in report.calls:
            by_step[(call.kind, call.label)].append(call)

    print("\nPer step (averaged per article):")
    print(f"  {'step':<34}{'calls':>7}{'avg s':>8}{'tok in':>9}{'tok out':>9}")
    for (kind, label), calls in sorted(by_step.items()):
        n = len(reports)
        print(
            f"  {kind + ':' + label:<34}"
            f"{len(calls) / n:>7.1f}"
            f"{statistics.mean(c.latency_s for c in calls):>8.2f}"
            f"{sum(c.input_tokens for c in calls) / n:>9.0f}"
            f"{sum(c.output_tokens for c in calls) / n:>9.0f}"
        )

    walls = [r.wall_time_s for r in reports]
    print(
        f"\nPer article: wall time mean={statistics.mean(walls):.1f}s "
        f"max={max(walls):.1f}s, "
        f"llm calls mean={statistics.mean(r.count('llm') for r in reports):.1f}, "
        f"searches mean={statistics.mean(r.count('search') for r in reports):.1f}, "
        f"tokens in/out mean={statistics.mean(r.input_tokens for r in reports):.0f}"
        f"/{statistics.mean(r.output_tokens for r in reports):.0f}"
    )
    pricing = get_settings().pricing()
    if pricing:
        costs = [r.cost_usd(pricing) for r in reports]
        print(f"Cost per article: mean=${statistics.mean(costs):.4f} max=${max(costs):.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--count", type=int, default=3)
    args = parser.parse_args()

    configure_logging()
    reports = asyncio.run(measure(args.count))
    if reports:
        print_breakdown(reports)


if __name__ == "__main__":
    main()
