from pydantic import BaseModel

from services.google import execute_query

# One definition, shared by the editor (new articles) and classify_sensitivity
# (backfilling old ones), so the two can't drift apart.
#
# Classified by an LLM, not keywords: a keyword list flagged "Warriors",
# "strikeouts" and "trade deadline" but missed "under professional care".
# In production, before this existed, a rape conviction was translated as an
# NFL "playoff blowout" and a planned military strike as an MLB "opening series".
SENSITIVE_DEFINITION = """
A story is SENSITIVE if a reasonable reader would find it tasteless to
retell it with sports, entertainment, or reality-TV framing. That includes:
- sexual violence, harassment, or abuse of any kind (domestic, child, elder)
- a person's death, or serious harm from violence, disaster, or accident
- war, military strikes, armed conflict, terrorism, mass shootings
- suicide, self-harm, addiction, overdose, or a mental-health crisis
- violent crime, or a person's arrest or trial for one

NOT sensitive: sports injuries, firings, trades, feuds, breakups and
divorces, lawsuits over money, elections, layoffs, earnings, or ordinary
political and business conflict.

When unsure, choose sensitive.
"""


class SensitivityResult(BaseModel):
    sensitive: bool


async def classify_sensitivity(headline: str, summary: str, key_points: list[str]) -> bool:
    """For already-saved articles. New articles get this from the editor call."""
    prompt = f"""
        Classify whether this news story is sensitive.

        {SENSITIVE_DEFINITION}

        STORY
        Headline: {headline}
        Summary: {summary}
        Key points:
        {chr(10).join(f"- {point}" for point in key_points)}
        """
    response = await execute_query(prompt, SensitivityResult)
    return SensitivityResult.model_validate_json(response.text).sensitive
