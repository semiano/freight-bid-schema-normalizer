# enums.py
"""
Enumerations for RXO Document Normalizer
"""
from enum import Enum

class RunStatus(str, Enum):
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    RUNNING = "Running"
    VALIDATION_FAILED = "ValidationFailed"

class OutputFormat(str, Enum):
    XLSX = "xlsx"
    CSV = "csv"
    BOTH = "both"
