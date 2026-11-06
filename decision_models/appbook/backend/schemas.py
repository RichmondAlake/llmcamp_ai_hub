"""Request bodies. Text is capped so a page cannot send a model an unbounded state."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from backend.config import BACKENDS

Backend = Literal["local", "jev", "openai"]


class Decide(BaseModel):
    backends: Optional[list[Backend]] = None
    typical: bool = False


class TrySwap(Decide):
    text: Optional[str] = Field(default=None, max_length=4000)
    stored: Optional[str] = Field(default=None, max_length=1000)
    new: Optional[str] = Field(default=None, max_length=1000)


class RunLabelled(BaseModel):
    backend: Backend


class PlaygroundQuestion(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    type: Literal["noul", "choice", "score"]
    instructions: str = Field(min_length=1, max_length=600)
    true: Optional[str] = Field(default=None, max_length=300)
    false: Optional[str] = Field(default=None, max_length=300)
    options: Optional[dict[str, str]] = None
    levels: Optional[list[str]] = None

    @field_validator("options")
    @classmethod
    def _options(cls, v):
        if v is not None and not (2 <= len(v) <= 20):
            raise ValueError("a choice needs 2 to 20 options")
        return v

    @field_validator("levels")
    @classmethod
    def _levels(cls, v):
        if v is not None and not (2 <= len(v) <= 10):
            raise ValueError("a score needs 2 to 10 levels")
        return v


class Playground(Decide):
    state: str = Field(min_length=1, max_length=4000)
    questions: list[PlaygroundQuestion] = Field(min_length=1, max_length=8)


assert set(Backend.__args__) == set(BACKENDS)
