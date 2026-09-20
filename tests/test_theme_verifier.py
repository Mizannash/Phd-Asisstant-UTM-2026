import pytest
import os
import sys
import json
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.models.schemas import validate_theme_report, ThemeReport

def test_hallucination_rejection():
    # LLM hallucinated a wiki_link not in allowed list
    raw = json.dumps({
        "verdict": "SUPPORTED",
        "supporting_claims": [
            {"claim": "AI is good", "wiki_link": "[[Paper_Fake.md]]", "paper_title": "Fake Paper"}
        ],
        "unverified_claims": [],
        "suggested_queries": []
    })
    
    retries = 0
    def mock_retry(err):
        nonlocal retries
        retries += 1
        # In retry, fix it
        return json.dumps({
            "verdict": "SUPPORTED",
            "supporting_claims": [],
            "unverified_claims": ["AI is good"],
            "suggested_queries": []
        })
        
    allowed = ["[[Paper_Real.md]]"]
    report = validate_theme_report(raw, allowed, mock_retry)
    
    assert retries == 1
    assert report is not None
    assert len(report.supporting_claims) == 0
    assert "AI is good" in report.unverified_claims

def test_valid_pass():
    raw = json.dumps({
        "verdict": "SUPPORTED",
        "supporting_claims": [
            {"claim": "AI is good", "wiki_link": "[[Paper_Real.md]]", "paper_title": "Real Paper"}
        ],
        "unverified_claims": [],
        "suggested_queries": ["Search for something else"]
    })
    
    retries = 0
    def mock_retry(err):
        nonlocal retries
        retries += 1
        return raw
        
    allowed = ["[[Paper_Real.md]]"]
    report = validate_theme_report(raw, allowed, mock_retry)
    
    assert retries == 0
    assert report is not None
    assert report.verdict == "SUPPORTED"
    assert len(report.suggested_queries) == 1

def test_enum_rejection():
    # Invalid verdict
    raw = json.dumps({
        "verdict": "PARTIALLY_TRUE", # invalid
        "supporting_claims": [],
        "unverified_claims": [],
        "suggested_queries": []
    })
    
    retries = 0
    def mock_retry(err):
        nonlocal retries
        retries += 1
        # Fix the verdict
        return json.dumps({
            "verdict": "WEAKLY SUPPORTED",
            "supporting_claims": [],
            "unverified_claims": [],
            "suggested_queries": []
        })
        
    allowed = []
    report = validate_theme_report(raw, allowed, mock_retry)
    
    assert retries == 1
    assert report is not None
    assert report.verdict == "WEAKLY SUPPORTED"

def test_retry_budget_accounting():
    # If it fails twice, we return None
    raw = json.dumps({"bad": "data"})
    
    retries = 0
    def mock_retry(err):
        nonlocal retries
        retries += 1
        return json.dumps({"still_bad": "data"})
        
    allowed = []
    report = validate_theme_report(raw, allowed, mock_retry)
    
    assert retries == 1
    assert report is None
