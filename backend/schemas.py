from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class StartSessionRequest(BaseModel):
    parts: list[int] = Field(..., description="Subset of [1, 2, 3]")
    use_custom_only: bool = Field(False, description="Use only user-uploaded questions")

    @field_validator("parts")
    @classmethod
    def validate_parts(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError("parts must not be empty")
        for p in v:
            if p not in (1, 2, 3):
                raise ValueError(f"Invalid part {p}; must be 1, 2, or 3")
        # de-duplicate while preserving order
        seen: set[int] = set()
        out: list[int] = []
        for p in v:
            if p not in seen:
                out.append(p)
                seen.add(p)
        return out


class PromptPayload(BaseModel):
    question_id: int
    type: str
    data: dict
    prep_sec: int
    rec_sec: int


class PartPayload(BaseModel):
    part: int
    prompts: list[PromptPayload]


class StartSessionResponse(BaseModel):
    session_id: int
    parts: list[PartPayload]


class TranscribeResponse(BaseModel):
    transcript: str
    punctuated_transcript: str = ""
    intonation_note: str = ""
    word_count: int
    duration_sec: float


class GenerateQuestionsRequest(BaseModel):
    part: int = Field(..., ge=1, le=3)
    count: int = Field(5, ge=1, le=10)


class GenerateQuestionsResponse(BaseModel):
    inserted_ids: list[int]
    count: int


class CustomQuestionsStats(BaseModel):
    part1_personal: int
    part1_compare: int
    part2: int
    part3: int
    total: int


class UploadQuestionsResponse(BaseModel):
    inserted: CustomQuestionsStats
    skipped: int
    errors: list[str]


class ClearCustomQuestionsResponse(BaseModel):
    deleted: int


class GradeFeedback(BaseModel):
    discourse: str
    grammar: str
    vocabulary: str
    pronunciation: str
    overall: str
    improvement_tips: list[str]


class GradeResponse(BaseModel):
    session_id: int
    discourse: float
    grammar: float
    vocabulary: float
    pronunciation: float
    raw_sum: float
    score_75: int
    band: str
    feedback: GradeFeedback
    graded_at: datetime


class AnswerOut(BaseModel):
    id: int
    question_idx: int
    question_part: int
    question_subtype: str
    question_data: dict
    transcript: str
    punctuated_transcript: Optional[str] = None
    intonation_note: Optional[str] = None
    prosody: Optional[dict] = None
    word_count: int
    duration_sec: float
    audio_url: str


class SessionResultResponse(BaseModel):
    session_id: int
    parts: list[int]
    started_at: datetime
    finished_at: Optional[datetime]
    grade: Optional[GradeResponse]
    answers: list[AnswerOut]


class ProgressSession(BaseModel):
    session_id: int
    parts: list[int]
    started_at: datetime
    finished_at: Optional[datetime]
    score_75: Optional[int]
    band: Optional[str]
