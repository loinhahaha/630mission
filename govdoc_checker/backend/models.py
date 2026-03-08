\
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class Issue(BaseModel):
    issue_type: str
    severity: str  # "error" | "warning" | "info"
    message: str
    paragraph_index: Optional[int] = None
    evidence: Optional[str] = None
    suggestion: Optional[str] = None
