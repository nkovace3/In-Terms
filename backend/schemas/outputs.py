from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field
from schemas.search import Source
from datetime import datetime

class FinalStory(BaseModel):
    headline: str = Field(max_length=60)
    summary: str = Field(max_length=110)
    key_points: list[Annotated[str, Field(max_length=90)]] = Field(
        min_length=3, max_length=5
    )
    sources: list[Source]
    # Classified by the editor in the same call (see services/sensitivity.py).
    # Last, so it's judged after the story is written.
    sensitive: bool

class ArticleResponse(BaseModel):
    id: int
    title: str
    url: str
    published_at: datetime
    source: str
    headline: str
    summary: str
    key_points: list[str]
    created_at: datetime
    category: str
    sensitive: bool | None = None

    model_config = ConfigDict(from_attributes=True)

class StoryDynamics(BaseModel):
    situation: list[str] = []
    relationships: list[str] = []
    actions: list[str] = []
    power_dynamics: list[str] = []
    emotional_dynamics: list[str] = []

class InTermsResult(BaseModel):
    # Reasoning and the pick come before the card fields on purpose, so the
    # model commits to a parallel (or to none) before writing around it.
    why_it_matches: str = Field(
        description="One sentence: the shared structure between the original and the chosen candidate, naming both. Empty if none chosen."
    )
    reference_number: int | None = Field(
        description="Number of the candidate story used as the parallel, or null if none genuinely mirrors the original."
    )
    # Looser than the original card's limits: a comparison has to name two
    # stories, and accuracy comes before brevity. These are "reasonable"
    # ceilings (not enforced — results are model_construct'ed), flagged by
    # the eval's format check.
    headline: str = Field(max_length=80)
    summary: str = Field(max_length=200)
    key_points: list[Annotated[str, Field(max_length=140)]] = Field(
        min_length=3, max_length=3
    )

class InTermsResponse(BaseModel):
    id: int
    article_id: int
    target_category: str
    headline: str
    summary: str
    key_points: list[str] = Field(min_length=3, max_length=3)
    created_at: datetime
    # Headline of the real story the card compares against, if any.
    reference_headline: str | None = None

    model_config = ConfigDict(from_attributes=True)
