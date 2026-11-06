from sqlalchemy.orm import Session
from sqlalchemy import select, text
from datetime import datetime, timedelta

from models import Article, InTerms
from schemas.rss import RSSResult
from schemas.outputs import FinalStory, StoryDynamics, InTermsResult

async def save_article(db: Session, article: RSSResult, story: FinalStory, dynamics: StoryDynamics, embedding: list[float]) -> Article:
    db_article = Article(
        title=article.title,
        url=article.url,
        published_at=article.published_at,
        source=article.source,
        headline=story.headline,
        summary=story.summary,
        key_points=story.key_points,
        category=article.category,
        dynamics=dynamics.model_dump(),
        embedding=embedding
    )

    db.add(db_article)
    db.commit()
    db.refresh(db_article)

    return db_article

async def get_all_articles(db: Session) -> list[Article]:
    statement = (
        select(Article)
        .from_statement(text("SELECT * FROM articles ORDER BY published_at DESC"))
    )

    return list(db.scalars(statement).all())

async def get_article(db: Session, article_id: int) -> Article | None:
    statement = (
            select(Article)
            .from_statement(text("SELECT * FROM articles WHERE id = :article_id"))
            .params(article_id=article_id)
        )
    return db.scalars(statement).first()

async def article_exists(db: Session, check_url: str) -> bool:
    statement = (
        select(Article)
        .from_statement(text("SELECT id FROM articles WHERE url = :check_url"))
        .params(check_url=check_url)
    )   
    return db.scalar(statement) is not None

async def find_similar_articles(db: Session, category: str, embedding: list[float], limit: int = 5) -> list[Article]:
    time_cutoff = datetime.utcnow() - timedelta(days=14)
    statement = (
        select(Article)
        .from_statement(text("SELECT * FROM articles WHERE embedding IS NOT NULL AND category = :category AND published_at >= :time_cutoff ORDER BY embedding <=> CAST(:embedding AS vector) LIMIT :limit"))
        .params(embedding=embedding, category=category, time_cutoff=time_cutoff, limit=limit)
        )

    return list(db.scalars(statement).all())

async def get_in_terms(db: Session, article_id: int, target_category: str) -> InTerms | None:
    statement = (
        select(InTerms)
        .from_statement(text("SELECT * FROM in_terms WHERE article_id = :article_id AND target_category = :target_category"))
        .params(article_id=article_id, target_category=target_category)
    )

    return db.scalars(statement).first()

async def count_in_terms_since(db: Session, since: datetime) -> int:
    statement = (
        text("SELECT COUNT(*) FROM in_terms WHERE created_at >= :since")
        .bindparams(since=since)
    )
    return db.scalar(statement)

async def save_in_terms(db: Session, article_id: int, target_category: str, result: InTermsResult) -> InTerms:
    db_in_terms = InTerms(
        article_id=article_id,
        target_category=target_category,
        headline=result.headline,
        summary=result.summary,
        key_points=result.key_points,
    )

    db.add(db_in_terms)
    db.commit()
    db.refresh(db_in_terms)

    return db_in_terms