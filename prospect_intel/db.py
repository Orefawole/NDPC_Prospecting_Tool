"""Database models. SQLite by default, Postgres via DATABASE_URL."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from .config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    sector: Mapped[str] = mapped_column(String(40), index=True)  # finance | health | insurance
    subsector: Mapped[str | None] = mapped_column(String(80))  # e.g. commercial_bank, hospital
    city: Mapped[str | None] = mapped_column(String(80))
    address: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(String(500))
    domain: Mapped[str | None] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(60))
    rc_number: Mapped[str | None] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(80))  # google_places | csv:<file> | demo
    source_ref: Mapped[str | None] = mapped_column(String(300))  # place_id, row id, etc.
    review_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    evidence: Mapped[list["Evidence"]] = relationship(back_populates="business", cascade="all, delete-orphan")
    lead: Mapped["Lead | None"] = relationship(back_populates="business", cascade="all, delete-orphan", uselist=False)


class Evidence(Base):
    """One observed public signal, with the URL it was seen on."""

    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    signal: Mapped[str] = mapped_column(String(60))  # e.g. booking_form, privacy_policy
    detail: Mapped[str | None] = mapped_column(Text)  # short snippet
    url: Mapped[str] = mapped_column(String(800))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    business: Mapped[Business] = relationship(back_populates="evidence")


class NdpcRecord(Base):
    """A row imported from an NDPC public list (e.g. registered DCPMI)."""

    __tablename__ = "ndpc_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    list_name: Mapped[str] = mapped_column(String(60), index=True)  # dcmi | dpco | enforcement
    name: Mapped[str] = mapped_column(String(300), index=True)
    category: Mapped[str | None] = mapped_column(String(40))  # UHL/EHL/OHL when published
    year: Mapped[str | None] = mapped_column(String(10))
    rc_number: Mapped[str | None] = mapped_column(String(40))
    domain: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str] = mapped_column(String(800))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), unique=True)

    # AI / heuristic analysis
    data_categories: Mapped[list] = mapped_column(JSON, default=list)
    sensitive_data: Mapped[list] = mapped_column(JSON, default=list)
    likely_tier: Mapped[str] = mapped_column(String(20), default="unknown")  # UHL | EHL | OHL | unknown
    tier_reason: Mapped[str | None] = mapped_column(Text)
    gap_signals: Mapped[list] = mapped_column(JSON, default=list)
    analysis_summary: Mapped[str | None] = mapped_column(Text)
    analysis_method: Mapped[str] = mapped_column(String(20), default="heuristic")  # claude | heuristic

    # NDPC cross-check
    ndpc_status: Mapped[str] = mapped_column(String(20), default="Unmatched")  # Verified | Unmatched | Manual review
    ndpc_match_name: Mapped[str | None] = mapped_column(String(300))
    ndpc_match_score: Mapped[float | None] = mapped_column(Float)
    ndpc_match_basis: Mapped[str | None] = mapped_column(String(120))

    # Contacts (public business channels only)
    public_email: Mapped[str | None] = mapped_column(String(255))
    public_phone: Mapped[str | None] = mapped_column(String(60))
    contact_page: Mapped[str | None] = mapped_column(String(800))

    score: Mapped[int] = mapped_column(Integer, default=0)
    score_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    next_step: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    business: Mapped[Business] = relationship(back_populates="lead")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    action: Mapped[str] = mapped_column(String(60))
    detail: Mapped[str | None] = mapped_column(Text)


_engine = None


def engine(url: str | None = None):
    global _engine
    if url is not None:
        return create_engine(url)
    if _engine is None:
        _engine = create_engine(settings.database_url)
    return _engine


def init_db(eng=None) -> None:
    Base.metadata.create_all(eng or engine())


def session(eng=None) -> Session:
    return Session(eng or engine(), expire_on_commit=False)


def audit(s: Session, action: str, detail: str = "") -> None:
    s.add(AuditLog(action=action, detail=detail[:4000]))
