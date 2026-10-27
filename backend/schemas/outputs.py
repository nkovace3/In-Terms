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

    model_config = ConfigDict(from_attributes=True)

class StoryDynamics(BaseModel):
    situation: list[str] = []
    relationships: list[str] = []
    actions: list[str] = []
    power_dynamics: list[str] = []
    emotional_dynamics: list[str] = []

class InTermsResult(BaseModel):
    headline: str = Field(max_length=60)
    summary: str = Field(max_length=110)
    key_points: list[Annotated[str, Field(max_length=90)]] = Field(
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

    model_config = ConfigDict(from_attributes=True)
