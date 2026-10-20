from fastapi import APIRouter, HTTPException
from database import SessionLocal
from repository import get_all_articles, get_article
from services.in_terms import get_or_generate_in_terms

from schemas.outputs import ArticleResponse, InTermsResponse

router = APIRouter()

CATEGORIES = {
    "nba": "NBA",
    "nfl": "NFL",
    "mlb": "MLB",
    "reality tv": "Reality TV",
    "us politics": "US Politics",
    "business": "Business",
}

@router.get("/articles", response_model=list[ArticleResponse])
async def read_articles():
    db = SessionLocal()

    try:
        return await get_all_articles(db)
    finally:
        db.close()

@router.get("/articles/{article_id}", response_model=ArticleResponse)
async def read_article(article_id: int):
    db = SessionLocal()

    try:
        article =  await get_article(db, article_id)

        if article is None:
            raise HTTPException(
                status_code=404,
                detail="Article not found"
            )

        return article
    finally:
        db.close()

@router.get("/articles/{article_id}/in-terms/{target_category}", response_model=InTermsResponse)
async def get_article_in_terms(article_id: int, target_category: str):
    db = SessionLocal()

    target_category = CATEGORIES.get(target_category.lower())
    if target_category is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid target category",
    )

    try:
        result = await get_or_generate_in_terms(db=db, article_id=article_id, target_category=target_category)

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Article not found"
            )

        return result

    finally:
        db.close()