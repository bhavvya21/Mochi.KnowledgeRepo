from typing import Literal
from pydantic import BaseModel, Field, model_validator


class Page(BaseModel):
    page: int = Field(ge=1, le=10000)
    topic: str = Field(default="", max_length=300)
    text: str = Field(min_length=1, max_length=200000)
    method: str = "text"


class DocumentInput(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    type: Literal["PDF", "XLSX", "CSV", "TXT", "MD", "JSON", "IMAGE", "DOCX"]
    collection: str = Field(default="My uploads", max_length=80)
    pages: list[Page] = Field(min_length=1, max_length=200)
    size: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_pages(self):
        if not self.name.strip() or any(not p.text.strip() for p in self.pages):
            raise ValueError("Names and pages must not be blank")
        if len({p.page for p in self.pages}) != len(self.pages):
            raise ValueError("Duplicate page numbers")
        if sum(len(p.text) for p in self.pages) > 200000:
            raise ValueError("Document exceeds 200,000 extracted characters")
        return self


class Query(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    scope: Literal["uploads", "samples"] = "uploads"
    collection: str = Field(default="All knowledge", max_length=80)
    mode: Literal["hybrid", "dense", "bm25", "tfidf"] = "hybrid"
    strategy: Literal["structure", "fixed", "sentence", "semantic"] = "structure"
    generate: bool = True
    decompose: bool = True


class Evidence(BaseModel):
    source: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=1500)


class Claim(BaseModel):
    text: str = Field(min_length=1, max_length=1500)
    evidence: list[Evidence] = Field(min_length=1, max_length=5)


class Draft(BaseModel):
    supported: bool
    claims: list[Claim] = Field(max_length=8)


class Plan(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=4)


class Verification(BaseModel):
    supported: list[bool]


class VisionDescription(BaseModel):
    description: str = Field(max_length=4000)
