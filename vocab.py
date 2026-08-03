"""Controlled vocabulary for image/post subjects.

This module is the SOURCE OF TRUTH. The `subjects` table is seeded from it,
never the other way around — that keeps the Python Enum and the DB in sync
and lets Pydantic validate against a static type.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Subject(str, Enum):
    """Canonical subject ids. UNKNOWN is load-bearing — see schemas.py."""

    RED_FOX = "red_fox"
    GRAY_WOLF = "gray_wolf"
    DOMESTIC_DOG = "domestic_dog"
    RED_PANDA = "red_panda"
    RACCOON = "raccoon"
    DOMESTIC_CAT = "domestic_cat"
    UNKNOWN = "unknown"


class SubjectDef(BaseModel):
    canonical: Subject
    display: str
    synonyms: list[str] = Field(default_factory=list)
    family: str | None = None


VOCAB: dict[Subject, SubjectDef] = {
    Subject.RED_FOX: SubjectDef(
        canonical=Subject.RED_FOX,
        display="red fox",
        synonyms=["fox", "red fox", "vulpes vulpes", "silver fox"],
        family="canid",
    ),
    Subject.GRAY_WOLF: SubjectDef(
        canonical=Subject.GRAY_WOLF,
        display="gray wolf",
        synonyms=["wolf", "grey wolf", "gray wolf", "canis lupus", "timber wolf"],
        family="canid",
    ),
    Subject.DOMESTIC_DOG: SubjectDef(
        canonical=Subject.DOMESTIC_DOG,
        display="dog",
        synonyms=["dog", "puppy", "canis familiaris", "husky", "shepherd"],
        family="canid",
    ),
    Subject.RED_PANDA: SubjectDef(
        canonical=Subject.RED_PANDA,
        display="red panda",
        synonyms=["red panda", "ailurus fulgens", "lesser panda"],
        family="musteloid",
    ),
    Subject.RACCOON: SubjectDef(
        canonical=Subject.RACCOON,
        display="raccoon",
        synonyms=["raccoon", "procyon lotor", "racoon"],
        family="musteloid",
    ),
    Subject.DOMESTIC_CAT: SubjectDef(
        canonical=Subject.DOMESTIC_CAT,
        display="cat",
        synonyms=["cat", "kitten", "felis catus"],
        family="feline",
    ),
    Subject.UNKNOWN: SubjectDef(
        canonical=Subject.UNKNOWN,
        display="unknown",
        synonyms=[],
        family=None,
    ),
}


def prompt_vocab_block() -> str:
    """Renders the vocab for injection into the vision / extraction prompt."""
    lines = []
    for s, d in VOCAB.items():
        if s is Subject.UNKNOWN:
            continue
        lines.append(f"- {s.value}: {d.display} (also: {', '.join(d.synonyms)})")
    lines.append("- unknown: none of the above, or you are not confident")
    return "\n".join(lines)


def same_family(a: Subject, b: Subject) -> bool:
    fa, fb = VOCAB[a].family, VOCAB[b].family
    return fa is not None and fa == fb