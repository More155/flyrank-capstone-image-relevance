"""Pydantic schemas — the single definition used for vision-output validation,
DB row shapes, and the FastAPI request/response layer.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from vocab import Subject


# ---------------------------------------------------------------------------
# 1. What the vision model is allowed to return
# ---------------------------------------------------------------------------


class Category(str, Enum):
    MAMMAL = "mammal"
    BIRD = "bird"
    REPTILE = "reptile"
    OTHER_ANIMAL = "other_animal"
    NOT_AN_ANIMAL = "not_an_animal"


class VisionTagOutput(BaseModel):
    """The forced tool-use input schema. Nothing here is derivable by us —
    every field is something only the model can supply.
    """

    model_config = ConfigDict(extra="forbid")

    subject: Subject
    category: Category
    attributes: list[str] = Field(default_factory=list, max_length=8)
    caption: str = Field(min_length=10, max_length=300)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str | None = Field(default=None, max_length=300)

    @field_validator("attributes")
    @classmethod
    def _normalize(cls, v: list[str]) -> list[str]:
        seen, out = set(), []
        for a in v:
            a = a.strip().lower()
            if a and a not in seen:
                seen.add(a)
                out.append(a)
        return out


class SubjectExtraction(BaseModel):
    """Same idea, applied to post text instead of pixels."""

    model_config = ConfigDict(extra="forbid")

    subject: Subject
    confidence: float = Field(ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# 2. What we store (model output + provenance we add ourselves)
# ---------------------------------------------------------------------------


class TagStatus(str, Enum):
    OK = "ok"
    LOW_CONFIDENCE = "low_confidence"
    UNKNOWN_SUBJECT = "unknown_subject"
    INVALID_OUTPUT = "invalid_output"


class ImageTagRecord(BaseModel):
    image_id: UUID
    subject: Subject
    category: Category
    attributes: list[str]
    caption: str
    confidence: float
    status: TagStatus
    model: str
    created_at: datetime


class PostRecord(BaseModel):
    id: UUID
    title: str
    body: str
    subject: Subject
    subject_confidence: float


# ---------------------------------------------------------------------------
# 3. Guard
# ---------------------------------------------------------------------------


class Verdict(str, Enum):
    SUGGEST = "suggest"
    FLAG = "flag"
    NO_MATCH = "no_match"
    REJECT = "reject"


class GuardReason(str, Enum):
    OK = "ok"
    BELOW_SIMILARITY_FLOOR = "below_similarity_floor"
    SUBJECT_MISMATCH = "subject_mismatch"
    SUBJECT_UNKNOWN = "subject_unknown"
    LOW_TAG_CONFIDENCE = "low_tag_confidence"
    PROMOTED_OVER_TOP_HIT = "promoted_over_top_hit"


class Candidate(BaseModel):
    """The guard's input unit — deliberately tiny so step 1 can mock it."""

    image_id: UUID
    subject: Subject
    similarity: float = Field(ge=-1.0, le=1.0)
    tag_confidence: float = Field(ge=0.0, le=1.0)
    caption: str = ""


class GuardDecision(BaseModel):
    verdict: Verdict
    reason: GuardReason
    explanation: str
    image_id: UUID | None = None
    similarity: float | None = None


# ---------------------------------------------------------------------------
# 4. Cost ledger
# ---------------------------------------------------------------------------


class CallKind(str, Enum):
    VISION = "vision"
    EMBED_IMAGE = "embed_image"
    EMBED_POST = "embed_post"
    EXTRACT_SUBJECT = "extract_subject"


class ModelCall(BaseModel):
    kind: CallKind
    model: str
    input_units: int
    output_units: int
    cost_usd: float
    ref_id: UUID | None = None
    ok: bool = True
    attempt: int = 1
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# 5. API surface
# ---------------------------------------------------------------------------


class PairingStatus(str, Enum):
    SUGGESTED = "suggested"
    APPROVED = "approved"
    REJECTED = "rejected"
    REFUSED_BY_GUARD = "refused_by_guard"


class MatchResponse(BaseModel):
    post_id: UUID
    decision: GuardDecision
    ranked: list[Candidate]


class ReviewAction(BaseModel):
    action: PairingStatus
    note: str | None = Field(default=None, max_length=500)