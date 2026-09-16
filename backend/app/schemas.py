from pydantic import BaseModel, Field

from .config import (
    MAX_DESCRIPTION_CHARS,
    MAX_INSTRUCTION_CHARS,
    MAX_QUERY_CHARS,
    MAX_XML_CHARS,
)


class GenerateRequest(BaseModel):
    description: str = Field(..., min_length=3, max_length=MAX_DESCRIPTION_CHARS)


class XmlRequest(BaseModel):
    xml: str = Field(..., min_length=1, max_length=MAX_XML_CHARS)


class FixRequest(BaseModel):
    xml: str = Field(..., min_length=1, max_length=MAX_XML_CHARS)
    issues: list[dict] = []


class ExplainRequest(BaseModel):
    xml: str = Field(..., min_length=1, max_length=MAX_XML_CHARS)
    persona: str = "auditor"


class SuggestRequest(BaseModel):
    query: str = Field(..., max_length=MAX_QUERY_CHARS)


class EditRequest(BaseModel):
    xml: str = Field(..., min_length=1, max_length=MAX_XML_CHARS)
    instruction: str = Field(..., min_length=2, max_length=MAX_INSTRUCTION_CHARS)


class EnhanceRequest(BaseModel):
    description: str = Field(..., min_length=3, max_length=MAX_DESCRIPTION_CHARS)


class ReviewExportRequest(BaseModel):
    report: dict
    format: str = "md"         
    processName: str | None = None
