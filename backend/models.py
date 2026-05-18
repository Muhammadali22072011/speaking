from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from backend.database import Base


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    part: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    subtype: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(String(16), default="seed", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    times_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parts: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    total_score_75: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    band: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    answers: Mapped[list["Answer"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    grade: Mapped[Optional["Grade"]] = relationship(back_populates="session", uselist=False, cascade="all, delete-orphan")


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    question_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    audio_path: Mapped[str] = mapped_column(String(512), nullable=False)
    transcript: Mapped[str] = mapped_column(Text, nullable=False, default="")
    punctuated_transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    intonation_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prosody_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_sec: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    session: Mapped["Session"] = relationship(back_populates="answers")
    question: Mapped["Question"] = relationship()


class Grade(Base):
    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), unique=True, nullable=False)
    discourse: Mapped[float] = mapped_column(Float, nullable=False)
    grammar: Mapped[float] = mapped_column(Float, nullable=False)
    vocabulary: Mapped[float] = mapped_column(Float, nullable=False)
    pronunciation: Mapped[float] = mapped_column(Float, nullable=False)
    raw_sum: Mapped[float] = mapped_column(Float, nullable=False)
    score_75: Mapped[int] = mapped_column(Integer, nullable=False)
    band: Mapped[str] = mapped_column(String(16), nullable=False)
    feedback_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    graded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    session: Mapped["Session"] = relationship(back_populates="grade")
