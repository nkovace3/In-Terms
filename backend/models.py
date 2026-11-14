from datetime import datetime

from sqlalchemy import Boolean, String, DateTime, JSON, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from database import Base

class Article(Base):
    __tablename__ = 'articles'

    id: Mapped[int] = mapped_column(primary_key=True)

    title: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String, unique=True)
    published_at: Mapped[datetime] = mapped_column(DateTime)
    source: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String, nullable=False)

    headline: Mapped[str] = mapped_column(String)
    summary: Mapped[str] = mapped_column(String)
    key_points: Mapped[list[str]] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    dynamics: Mapped[dict] = mapped_column(JSON, nullable=True)

    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=True)

    # None = not classified yet; In Terms treats that as sensitive.
    sensitive: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # foreign_keys: in_terms also points here via reference_article_id.
    in_terms: Mapped[list["InTerms"]] = relationship(
        back_populates="article", cascade="all, delete-orphan", foreign_keys="InTerms.article_id"
    )

class InTerms(Base):
    __tablename__ = 'in_terms'

    __table_args__ = (UniqueConstraint('article_id', 'target_category', name='uq_in_terms_article_category'),)

    id: Mapped[int] = mapped_column(primary_key=True)

    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"),nullable=False)

    target_category: Mapped[str] = mapped_column(String, nullable=False)

    headline: Mapped[str] = mapped_column(String, nullable=False)

    summary: Mapped[str] = mapped_column(String, nullable=False)

    key_points: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # The real target-domain story this translation compares against. None
    # when no candidate was a genuine parallel, or the reference was deleted.
    reference_article_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id", ondelete="SET NULL"), nullable=True
    )

    article: Mapped["Article"] = relationship(back_populates="in_terms", foreign_keys=[article_id])
    reference_article: Mapped["Article | None"] = relationship(foreign_keys=[reference_article_id])

    @property
    def reference_headline(self) -> str | None:
        return self.reference_article.headline if self.reference_article else None
