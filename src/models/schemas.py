import os
import re
import json
import datetime
from typing import List, Optional, Callable
from pydantic import BaseModel, Field, field_validator, ValidationError

class PaperAnalysis(BaseModel):
    filename: str = Field(..., description="Must start with Paper_ and end with .md")
    content: str
    index_entry: str
    log_entry: str

    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v: str) -> str:
        if not v.startswith("Paper_"):
            raise ValueError("filename must start with 'Paper_'")
        if not v.endswith(".md"):
            raise ValueError("filename must end with '.md'")
        return v

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        if "APA" not in v:
            raise ValueError("content must contain 'APA'")
        if "Verdict" not in v:
            raise ValueError("content must contain 'Verdict'")
        if "Score" not in v:
            raise ValueError("content must contain 'Score'")
        return v

class ScoutPaper(BaseModel):
    title: str
    authors: List[str]
    year: int
    doi: Optional[str] = None
    source: str
    scout_verdict: str

def clean_json_string(raw_str: str) -> str:
    """Strips markdown code fences from the raw string."""
    clean_str = re.sub(r'^```[a-zA-Z]*\s*', '', raw_str.strip())
    clean_str = re.sub(r'```\s*$', '', clean_str).strip()
    return clean_str

def validate_gemini_output(raw_str: str, retry_callable: Callable[[str], str]) -> Optional[PaperAnalysis]:
    """
    Validates Gemini's strict 4-key JSON output.
    On failure, calls retry_callable(error_msg) ONCE.
    On second failure, writes to failed_json/ and returns None.
    """
    def attempt_parse(text: str) -> PaperAnalysis:
        cleaned = clean_json_string(text)
        data = json.loads(cleaned)
        return PaperAnalysis(**data)

    try:
        return attempt_parse(raw_str)
    except Exception as e:
        error_msg = f"JSON Validation Error: {str(e)}. Please output valid JSON strictly matching the schema."
        print(f"Validation failed. Retrying once: {e}")
        try:
            # Trigger retry
            second_raw = retry_callable(error_msg)
            return attempt_parse(second_raw)
        except Exception as e2:
            print(f"Second validation failed: {e2}. Writing raw output to failed_json/.")
            write_failed_json(raw_str, "gemini")
            return None

def validate_scout_output(raw_str: str) -> List[ScoutPaper]:
    """
    Validates Groq Scout's output containing a list of papers.
    Skips invalid papers. No retries.
    """
    valid_papers = []
    cleaned = clean_json_string(raw_str)
    try:
        data = json.loads(cleaned)
        papers = data.get("papers", [])
        for paper_data in papers:
            try:
                # Add default source if missing
                if "source" not in paper_data:
                    paper_data["source"] = "OpenAlex"
                
                # Tolerate abstract -> scout_verdict mappings if needed
                if "scout_verdict" not in paper_data and "abstract" in paper_data:
                    paper_data["scout_verdict"] = paper_data.pop("abstract")
                    
                valid_papers.append(ScoutPaper(**paper_data))
            except ValidationError as ve:
                print(f"Skipping malformed scout paper entry: {ve}")
    except Exception as e:
        print(f"Failed to parse scout JSON completely: {e}")
        write_failed_json(raw_str, "groq_scout")
        
    return valid_papers

def write_failed_json(raw_str: str, source: str):
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    failed_dir = os.path.join(base_dir, "output", "failed_json")
    os.makedirs(failed_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(failed_dir, f"failed_{source}_{timestamp}.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(raw_str)

from enum import Enum

class VerdictEnum(str, Enum):
    SUPPORTED = "SUPPORTED"
    WEAKLY_SUPPORTED = "WEAKLY SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"

class SupportingClaim(BaseModel):
    claim: str
    wiki_link: str
    paper_title: str

class ThemeReport(BaseModel):
    verdict: VerdictEnum
    supporting_claims: List[SupportingClaim]
    unverified_claims: List[str]
    suggested_queries: List[str]

def validate_theme_report(raw_str: str, allowed_wiki_links: List[str], retry_callable: Callable[[str], str]) -> Optional[ThemeReport]:
    def attempt_parse(text: str) -> ThemeReport:
        cleaned = clean_json_string(text)
        data = json.loads(cleaned)
        report = ThemeReport(**data)
        
        # Hallucination check
        for sc in report.supporting_claims:
            if sc.wiki_link not in allowed_wiki_links:
                raise ValueError(f"Citation Hallucination Detected: [{sc.wiki_link}] was not in the retrieved context.")
        return report

    try:
        return attempt_parse(raw_str)
    except Exception as e:
        error_msg = f"JSON Validation Error: {str(e)}. Please output valid JSON matching the schema and strictly only cite allowed wiki_links."
        print(f"Validation failed. Retrying once: {e}")
        try:
            second_raw = retry_callable(error_msg)
            return attempt_parse(second_raw)
        except Exception as e2:
            print(f"Second validation failed: {e2}. Writing raw output to failed_json/.")
            write_failed_json(raw_str, "theme_verifier")
            return None
