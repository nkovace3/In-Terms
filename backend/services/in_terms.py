import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from config import get_settings
from services.google import execute_query
from services.usage import track_usage
from schemas.outputs import InTermsResult
from models import Article
from sqlalchemy.orm import Session
from repository import get_in_terms, get_article, find_similar_articles, save_in_terms, count_in_terms_since

logger = logging.getLogger(__name__)

# How many candidate parallels the model chooses from, and how far back to
# look for them. Retrieval over the coarse dynamics labels is rough, so the
# nearest neighbor alone is often only a surface match; giving the model a
# few to pick from (or reject) is what makes the comparison land. Ingestion
# adds ~2 articles per category per day, so 14 days was ~28 candidates.
CANDIDATE_COUNT = 5
CANDIDATE_DAYS_BACK = 90

class DailyLimitReached(Exception):
    """Raised on a cache miss once today's generation cap is used up."""

class SensitiveStory(Exception):
    """Raised for stories that shouldn't be reframed (see services/sensitivity.py)."""

@dataclass
class InTermsGeneration:
    result: InTermsResult
    # The candidate the model compared against, or None if it found no
    # genuine parallel and fell back to plain framing.
    reference: Article | None
    candidates: list[Article]

# Before this, the prompt narrated the original story in the target domain's
# vocabulary and told the model to use the retrieved story "for tone only —
# never pull its facts". The retrieval ran but its result never reached the
# reader, and output read like keyword swapping. The frozen old version is
# evals/baseline_in_terms.py; evals/compare_eval.py measures one against the other.
def build_prompt(article: Article, target_term: str, candidates: list[Article]) -> str:
    story = {"headline": article.headline, "summary": article.summary, "key_points": article.key_points}
    candidate_blocks = "\n\n".join(
        f"CANDIDATE {n}\n"
        + json.dumps(
            {
                "headline": c.headline,
                "summary": c.summary,
                "key_points": c.key_points,
                "dynamics": c.dynamics or {},
            },
            indent=2,
            ensure_ascii=False,
        )
        for n, c in enumerate(candidates, 1)
    ) or "No candidates are available."

    return f"""
You explain a real news story to someone who follows {target_term}, by
comparing it to a real {target_term} story. The reader should understand the
original story better because it works like something they already know.

GOOD (an NBA story explained to a politics reader):
  "The Mavericks sending Luka Dončić to the Lakers for Anthony Davis is like
  [a real politics story]: two heavyweights each giving up something huge to
  fix a deal that wasn't working for either side."
BAD (vocabulary swap, which teaches the reader nothing):
  "In a stunning cabinet reshuffle, the Mavericks traded their party leader."

ORIGINAL STORY (every fact here is real):
{json.dumps(story, indent=2, ensure_ascii=False)}

ORIGINAL STORY DYNAMICS (its abstract shape):
{json.dumps(article.dynamics or {}, indent=2)}

CANDIDATE {target_term.upper()} STORIES (real stories, retrieved because their
dynamics labels resemble the original's; retrieval is rough, so most will
only share surface labels):

{candidate_blocks}

STEP 1 — CHOOSE THE PARALLEL (or none)
First describe the original's situation in one sentence with no names, e.g.
"a team trades its young star for an older one to win now" or "an employer
fires someone and the dispute plays out in public". A candidate is a
parallel only if that SAME sentence describes it without stretching: the
same kind of move, similar roles (who holds power, who needs whom), similar
stakes. Sharing a topic, a mood ("high stakes", "under pressure"), or a
label is not enough. Usually one candidate fits at best, and often none do.
- why_it_matches: "Shape: <the nameless sentence>. Candidate <n> fits
  because <reason>." Or, if none fits, "Shape: <sentence>. None fit."
- reference_number: that candidate's number, or null if none fits.
A forced comparison is worse than none: a reader who knows the parallel
will see straight through it.

STEP 2 — WRITE THE CARD
With a parallel:
- headline: the original's real event, plainly.
- summary: "<original event> is like <parallel event>: <the shared shape>."
- key_points, exactly 3:
  1. What happened in the original (its own facts).
  2. What happened in the parallel (its own facts).
  3. What the two share, or the one way they differ that matters.
  Only the overall shape has to match. Do NOT pair up individual details
  (a score with a ratings number, a fan with an ally): that is where
  comparisons turn into nonsense and invented facts.
Without a parallel:
- Narrate the original's real facts with one specific, recognizable
  {target_term} convention used as an explicit comparison, in the same
  fields. Generic words like "drama" or "crisis" don't count.

It's a phone-sized card, so keep each field to one idea: a headline of a
few words, a one-sentence summary, and short key points. Accuracy matters
more than brevity: never cut a qualifier if that makes a claim untrue.

FACT RULES
1. Facts about the original come only from ORIGINAL STORY. Facts about the
   parallel come only from the chosen candidate. Use real names from both.
2. Never move facts between the stories: no event, number, or person from
   one may be attributed to the other.
3. Never relabel real people or organizations as {target_term} roles (don't
   call a team a "cast" or a GM "the Speaker"). It's a comparison ("like",
   "mirrors", "the same move as"), not a story set in the other world.
4. Don't invent details to sharpen the comparison.
5. No forced slang, memes, or emojis.

Before answering, check each sentence: every fact must be in the story it's
attributed to.
"""

async def generate_in_terms_for_article(db: Session, article: Article, target_category: str) -> InTermsGeneration:
    """
    Retrieve candidate parallels and generate one In Terms result. No cache
    lookup and no save — get_or_generate_in_terms handles those for the API;
    the evals call this directly to score fresh output from the current prompt.
    """
    candidates = await find_similar_articles(
        db=db,
        embedding=article.embedding,
        category=target_category,
        limit=CANDIDATE_COUNT,
        days_back=CANDIDATE_DAYS_BACK,
        exclude_sensitive=True,
    )

    if not candidates:
        # If ingestion stalls long enough, every generation silently loses
        # its parallel and falls back to plain framing.
        logger.warning("No candidate parallels in %s for article %d", target_category, article.id)

    response = await execute_query(build_prompt(article, target_category, candidates), InTermsResult)
    # model_construct, not model_validate_json — see the matching comment
    # in services/editor.py for why.
    result = InTermsResult.model_construct(**json.loads(response.text))

    return InTermsGeneration(
        result=result,
        reference=resolve_reference(result.reference_number, candidates, article.id),
        candidates=candidates,
    )

def resolve_reference(reference_number: int | None, candidates: list[Article], article_id: int) -> Article | None:
    if reference_number is None:
        return None
    if 1 <= reference_number <= len(candidates):
        return candidates[reference_number - 1]
    # The card text may still lean on a parallel, but we can't say which;
    # better to show no "Compared with" than the wrong one.
    logger.warning("Article %d: reference_number %s out of range (%d candidates)", article_id, reference_number, len(candidates))
    return None

async def get_or_generate_in_terms(db: Session, article_id: int, target_category: str):
    article = await get_article(db, article_id)

    if article is None:
        return None

    # Before the cache lookup, so a translation cached before this check
    # existed is never served either. `is not False`: unclassified (None)
    # is blocked too — fail closed.
    if article.sensitive is not False:
        raise SensitiveStory()

    cached = await get_in_terms(db=db, article_id=article_id, target_category=target_category)

    if cached:
        return cached

    if target_category == article.category:
        return None

    # Checked only on a cache miss, so cached translations keep working
    # after the cap is hit. Not atomic: a few concurrent requests can slip
    # past the limit, which is fine for a cost ceiling.
    limit = get_settings().max_in_terms_generations_per_day
    # Naive UTC, to match how created_at is stored.
    start_of_day = datetime.now(UTC).replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)
    if await count_in_terms_since(db, start_of_day) >= limit:
        logger.warning("Daily In Terms cap of %d reached — refusing article %d -> %s", limit, article_id, target_category)
        raise DailyLimitReached()

    # Generated on a cache miss while the user waits, so this latency is
    # directly user-facing — worth logging every time.
    with track_usage() as usage:
        generation = await generate_in_terms_for_article(db, article, target_category)
    logger.info(
        "Generated In Terms for article %d -> %s (parallel: %s) [%s]",
        article_id,
        target_category,
        generation.reference.id if generation.reference else "none",
        usage.summary(get_settings().pricing()),
    )

    saved = await save_in_terms(
        db=db,
        article_id=article_id,
        target_category=target_category,
        result=generation.result,
        reference_article_id=generation.reference.id if generation.reference else None,
    )

    return saved
