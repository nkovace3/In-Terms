"""
Frozen copy of the In Terms generator as it was before the analogy rewrite
(commit f3eca90): top-1 reference from the last 14 days, used for tone only.

Kept so evals/compare_eval.py can A/B the current generator against it on the
same articles, at the same time, against the same database. Not used by the
app.
"""

import json
from typing import Annotated

from pydantic import BaseModel, Field

from repository import find_similar_articles
from schemas.outputs import FinalStory, StoryDynamics
from services.google import execute_query


class InTermsResult(BaseModel):
    """The response schema as it was (no reference pick, tighter limits)."""
    headline: str = Field(max_length=60)
    summary: str = Field(max_length=110)
    key_points: list[Annotated[str, Field(max_length=90)]] = Field(min_length=3, max_length=3)


async def generate_baseline(db, article, target_term: str) -> tuple[dict, dict | None]:
    """Returns (output, reference shown to the model or None)."""
    similar_articles = await find_similar_articles(db=db, embedding=article.embedding, category=target_term, limit=1)
    similar_article = similar_articles[0] if similar_articles else None
    similar_dynamics = StoryDynamics(**(similar_article.dynamics or {})) if similar_article else None
    story = FinalStory.model_construct(
        headline=article.headline, summary=article.summary, key_points=article.key_points, sources=[],
    )
    dynamics = StoryDynamics(**(article.dynamics or {}))

    prompt = f"""
You narrate real news stories using the tone and framing conventions of
another domain, without changing what actually happened.

CRITICAL DISTINCTION — read this before anything else:

"In terms of {target_term}" does NOT mean rewriting this as a fictional
{target_term} story. It does NOT mean renaming the real people, teams, or
organizations with {target_term}-style labels (e.g. do not call a team a
"cast," a game an "episode," or a player a "contestant"). Doing that forces
you to invent fake scenes to make the sentence read naturally, which is
exactly what you must not do.

Instead, keep every real name, team, and fact exactly as given, and narrate
them using the STRUCTURE, STAKES, and EMOTIONAL VOCABULARY that {target_term}
stories are known for. The translation happens in tone and framing, not in
substituting nouns.

The examples below happen to use "Reality TV" as the target domain, purely
for illustration. The same principle applies no matter what {target_term}
actually is (NFL, business, MLB, politics, etc.) — find that domain's own
specific, recognizable tropes and use those instead.

GOOD EXAMPLE
Original fact: A team's star receiver is ruled out with an injury before a big game.
Target domain: Reality TV
Good: "Jets' Injury Woes at WR Continue as Mitchell Is Ruled Out Against the Lions"
      "With their receiving corps already thinned out, the Jets lose Mitchell
      right before a pivotal matchup — the kind of frontrunner-eliminated-
      before-the-finale twist a season's edit would build a whole episode
      around."
Why it works: every fact is real (Mitchell, Jets, Lions, injury). Nothing is
renamed. The narration uses a SPECIFIC reality-TV trope ("frontrunner
eliminated before the finale," "the edit would build an episode around it")
as an explicit comparison — not just generic words like "drama" or
"setback," which could describe literally any domain and don't actually
feel like {target_term}.

BAD EXAMPLE #1 — fictional relabeling (do not do this)
Bad: "Injury Drama Leaves Jets Cast Stripped of Key Players... his finger
      caught in a fellow castmate's jersey during Thursday's rehearsal."
Why it fails: "cast," "castmate," and "rehearsal" are fictional relabelings,
and the finger-catching detail is an invented event that never happened.

BAD EXAMPLE #2 — generic drama, not actually {target_term} (also do not do this)
Bad: "In a dramatic escalation of their ongoing roster crisis, the Jets faced
      the Lions while dealing with a wave of devastating setbacks."
Why it fails: "dramatic escalation," "crisis," and "devastating setbacks" are
generic intensity words. Nothing here is specific to {target_term} — this
exact sentence could be labeled "in terms of a courtroom drama" or "in terms
of a war documentary" and still make sense. That means the translation
didn't actually happen; only the volume got turned up.

YOUR INPUTS:

ORIGINAL STORY (source of truth — every fact below is real and must not change):
{story.model_dump_json(indent=2)}

ORIGINAL STORY DYNAMICS (the abstract shape of the situation — use this as
your primary guide for which framing/vocabulary fits, more so than the literal
words of the story):
{dynamics.model_dump_json(indent=2)}

TARGET DOMAIN: {target_term}

REFERENCE EXAMPLE FROM THE TARGET DOMAIN (for tone/vocabulary calibration
only — never pull its facts, names, or specifics into your answer):
{f"""Headline: {similar_article.headline}
Summary: {similar_article.summary}
Key Points: {similar_article.key_points}"""
if similar_article else
"No example is available. Rely on general knowledge of the target domain's tone and conventions."}

REFERENCE DYNAMICS (why that example was chosen as structurally similar):
{similar_dynamics.model_dump_json(indent=2) if similar_dynamics else "NO MATCH AVAILABLE"}

HOW TO WRITE THE OUTPUT:

1. Find the structural match between ORIGINAL STORY DYNAMICS and what
   {target_term} stories are typically about (setbacks, rivalries, power
   shifts, reversals, etc).
2. Narrate the ORIGINAL STORY's real facts using {target_term}'s dramatic
   register, pacing, and emotional vocabulary — the way a writer who covers
   {target_term} would describe tension, stakes, or a setback.
3. Keep every person, team, organization, and factual detail exactly as in
   the ORIGINAL STORY. Do not rename, relabel, or recast any of them as
   {target_term}-style equivalents.
4. Do not invent any event, action, cause, or detail that is not already in
   the ORIGINAL STORY or ORIGINAL STORY DYNAMICS.
5. Name at least one SPECIFIC trope, beat, or convention that {target_term}
   is actually known for (e.g. for reality TV: elimination, the confessional,
   an alliance, a frontrunner's edit, a villain edit, a season twist — not
   just "drama"), and use it as an explicit comparison to the real event.
   A generic intensity word like "crisis," "drama," or "setback" is not
   enough on its own — if your sentence would still make sense after
   swapping {target_term} for an unrelated domain, it hasn't translated
   anything yet. This applies to the headline, summary, AND every key
   point — don't front-load the {target_term} framing into the headline
   and then let the key points drift back into flat, undifferentiated
   reporting.
6. If the dynamics don't support a specific, vivid comparison, use a more
   general framing rather than inventing specifics to make it punchier.
7. Avoid forced slang, memes, emojis, and gimmicks — the goal is a natural
   tonal shift, not a costume.

OUTPUT FORMAT — return an InTermsResult. This is a short-form card, not an
article — every field has a hard character limit, so write tightly from the
start rather than composing a longer version and trimming it:

- headline: The real event, framed with {target_term}'s dramatic conventions.
  No invented or relabeled entities. Maximum 60 characters.
- summary: One sentence narrating the real event in that register, including
  at least one specific, named {target_term} trope used as a comparison.
  Maximum 110 characters.
- key_points: Exactly three bullet points, each grounded in a real fact from
  the ORIGINAL STORY, each framed through the same lens. Maximum 90
  characters each.

Before answering, check every sentence against the ORIGINAL STORY: if a
name, event, or detail isn't there, remove it.

Return only the structured InTermsResult.
"""

    response = await execute_query(prompt, InTermsResult)
    output = json.loads(response.text)
    reference = None
    if similar_article:
        reference = {
            "id": similar_article.id,
            "headline": similar_article.headline,
            "summary": similar_article.summary,
            "key_points": similar_article.key_points,
        }
    return {k: output[k] for k in ("headline", "summary", "key_points")}, reference
