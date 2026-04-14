# contracts.py
"""
Data contracts for RXO Document Normalizer
- WorkbookProfile
- CanonicalSchema
- AgentResponse
- ExecutionResult
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class SheetProfile(BaseModel):
    name: str
    visible: bool
    used_range: Optional[str]
    header_row: Optional[int]
    header_row_candidates: List[int] = Field(default_factory=list)
    columns: List[str]
    inferred_types: Dict[str, str]
    sample_rows: List[Dict[str, Any]]
    duplicate_headers: List[str] = Field(default_factory=list)
    empty_column_ratio: Optional[float]
    likely_business_meaning: Optional[str]
    classifier_hints: List[str] = Field(default_factory=list)
    notes: Optional[str]

class WorkbookProfile(BaseModel):
    workbook_name: str
    sheets: List[SheetProfile]
    notes: Optional[str]

class CanonicalSchemaColumn(BaseModel):
    name: str
    dtype: str
    required: bool = False
    normalization: Optional[str] = None
    default: Optional[Any] = None
    allowed_values: Optional[List[Any]] = None
    derived_formula: Optional[str] = None

class CanonicalSchema(BaseModel):
    schema_name: str
    columns: List[CanonicalSchemaColumn]
    description: Optional[str] = None

class AgentResponse(BaseModel):
    relevant_sheets: List[str]
    ignored_sheets: List[str]
    mapping_plan: Dict[str, Any]
    constants: Dict[str, Any]
    enrichments: Dict[str, Any]
    assumptions: List[str]
    confidence_scores: Dict[str, float]
    python_script: str
    tests: Optional[List[str]]

class ExecutionResult(BaseModel):
    status: str
    run_id: str
    output_path: Optional[str]
    artifacts: Optional[List[str]]
    validation_summary: Optional[Dict[str, Any]]
    error: Optional[str]
