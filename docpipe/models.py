"""Data contracts. The LLM schema lives in the prompt; these models validate every response."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

PageType = Literal["balance_sheet", "income_statement", "cash_flow", "notes", "other"]


class Item(BaseModel):
    label: str
    current: Optional[float] = None
    prior: Optional[float] = None
    quote: str = Field(description="the row text exactly as printed on the page")


class PageExtraction(BaseModel):
    page_type: PageType
    unit: str = Field(description="e.g. 'Triệu VND', 'VND', 'Nghìn đồng'")
    period_current: str
    period_prior: str
    items: list[Item]


class PageKind(BaseModel):
    page_type: PageType


class DocMeta(BaseModel):
    company: str
    fiscal_year: Optional[int] = None
    period: Literal["FY", "H1", "Q1", "Q2", "Q3", "Q4", "unknown"] = "unknown"
    scope: Literal["consolidated", "separate", "unknown"] = "unknown"
    audited: Optional[bool] = None
    doc_type: str
    confidence: float = Field(ge=0, le=1, description="your confidence in doc_type and the other fields")
    evidence: str = Field(description="short quote from the pages supporting doc_type")


class Check(BaseModel):
    name: str
    status: Literal["pass", "fail", "skip"]
    detail: str = ""
