"""
Cost/latency accounting for every LLM, embedding, and search call.

The three choke points (execute_query, create_embedding, search_web) call
`record_call` after each request. Callers that want a total — "what did
ingesting this one article cost?" — wrap the work in `track_usage()`:

    with track_usage() as usage:
        story = await process_article(article)
    logger.info("done [%s]", usage.summary())

A ContextVar (not a global) holds the active report, so totals stay
per-article even though the calls happen deep inside other modules, and
concurrent work in other asyncio tasks doesn't bleed in. Calls made with no
active report are simply not tallied.
"""

import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Iterator, Literal

CallKind = Literal["llm", "embedding", "search"]


@dataclass
class CallRecord:
    kind: CallKind
    label: str
    latency_s: float
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class Pricing:
    """USD rates. Kept out of code so a price change is a config change."""
    llm_input_per_mtok: float
    llm_output_per_mtok: float
    search_per_call: float


@dataclass
class UsageReport:
    calls: list[CallRecord] = field(default_factory=list)
    wall_time_s: float = 0.0

    def count(self, kind: CallKind) -> int:
        return sum(1 for call in self.calls if call.kind == kind)

    @property
    def input_tokens(self) -> int:
        return sum(call.input_tokens for call in self.calls)

    @property
    def output_tokens(self) -> int:
        return sum(call.output_tokens for call in self.calls)

    def cost_usd(self, pricing: Pricing) -> float:
        return (
            self.input_tokens / 1_000_000 * pricing.llm_input_per_mtok
            + self.output_tokens / 1_000_000 * pricing.llm_output_per_mtok
            + self.count("search") * pricing.search_per_call
        )

    def summary(self, pricing: Pricing | None = None) -> str:
        parts = [
            f"llm_calls={self.count('llm')}",
            f"searches={self.count('search')}",
            f"tokens_in={self.input_tokens}",
            f"tokens_out={self.output_tokens}",
            f"wall={self.wall_time_s:.1f}s",
        ]
        if pricing:
            parts.append(f"cost=${self.cost_usd(pricing):.4f}")
        return " ".join(parts)


_current_report: ContextVar[UsageReport | None] = ContextVar(
    "usage_report", default=None
)


def record_call(
    kind: CallKind,
    label: str,
    latency_s: float,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    report = _current_report.get()
    if report is not None:
        report.calls.append(
            CallRecord(kind, label, latency_s, input_tokens, output_tokens)
        )


@contextmanager
def track_usage() -> Iterator[UsageReport]:
    report = UsageReport()
    token = _current_report.set(report)
    start = time.perf_counter()
    try:
        yield report
    finally:
        report.wall_time_s = time.perf_counter() - start
        _current_report.reset(token)
