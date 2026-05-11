from typing import Literal

from pydantic import BaseModel, Field

CriticVerdict = Literal["ok", "revise"]
CriticSeverity = Literal["blocker", "major", "minor"]


class CriticIssue(BaseModel):
    page: int | None = Field(default=None)
    category: str
    severity: CriticSeverity
    evidence: str
    explanation: str
    suggested_fix: str


class CriticResult(BaseModel):
    overall_verdict: CriticVerdict
    issues: list[CriticIssue] = Field(default_factory=list)
    global_notes: list[str] = Field(default_factory=list)
