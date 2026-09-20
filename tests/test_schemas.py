import pytest
import os
import sys

# Ensure pytest can find the src module
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from src.models.schemas import (
    PaperAnalysis, 
    ScoutPaper, 
    validate_gemini_output, 
    validate_scout_output,
    clean_json_string
)

def test_paper_analysis_valid():
    data = {
        "filename": "Paper_test.md",
        "content": "APA citation\nVerdict: RELEVANT\nScore: 8",
        "index_entry": "Test entry",
        "log_entry": "Test log"
    }
    model = PaperAnalysis(**data)
    assert model.filename == "Paper_test.md"

def test_paper_analysis_invalid_filename():
    data = {
        "filename": "test.txt",
        "content": "APA citation\nVerdict: RELEVANT\nScore: 8",
        "index_entry": "Test entry",
        "log_entry": "Test log"
    }
    with pytest.raises(ValueError, match="must start with 'Paper_'"):
        PaperAnalysis(**data)

def test_paper_analysis_invalid_content():
    data = {
        "filename": "Paper_test.md",
        "content": "Just some text",
        "index_entry": "Test entry",
        "log_entry": "Test log"
    }
    with pytest.raises(ValueError, match="must contain 'APA'"):
        PaperAnalysis(**data)

def test_scout_paper_valid():
    data = {
        "title": "A Great Study",
        "authors": ["John Doe"],
        "year": 2024,
        "source": "OpenAlex",
        "scout_verdict": "Very relevant study."
    }
    model = ScoutPaper(**data)
    assert model.title == "A Great Study"
    assert model.doi is None

def test_clean_json_string():
    raw = "```json\n{\"key\": \"value\"}\n```"
    assert clean_json_string(raw) == '{"key": "value"}'

def test_validate_gemini_output_success():
    raw = '{"filename": "Paper_test.md", "content": "APA Verdict Score", "index_entry": "x", "log_entry": "y"}'
    result = validate_gemini_output(raw, lambda e: "")
    assert result is not None
    assert result.filename == "Paper_test.md"

def test_validate_gemini_output_retry_success():
    raw_invalid = '{"filename": "test.txt", "content": "APA Verdict Score", "index_entry": "x", "log_entry": "y"}'
    raw_valid = '{"filename": "Paper_test.md", "content": "APA Verdict Score", "index_entry": "x", "log_entry": "y"}'
    
    def mock_retry(error_msg):
        return raw_valid
        
    result = validate_gemini_output(raw_invalid, mock_retry)
    assert result is not None
    assert result.filename == "Paper_test.md"

def test_validate_gemini_output_total_failure(tmp_path, monkeypatch):
    import src.models.schemas as schemas
    monkeypatch.setattr(schemas, "write_failed_json", lambda r, s: None) # Mock file writing
    raw_invalid = '{"filename": "test.txt", "content": "bad content", "index_entry": "x", "log_entry": "y"}'
    
    def mock_retry(error_msg):
        return raw_invalid # Fail again
        
    result = validate_gemini_output(raw_invalid, mock_retry)
    assert result is None

def test_validate_scout_output_skips_invalid():
    raw = '''
    {
        "papers": [
            {
                "title": "Good Paper",
                "authors": ["A"],
                "year": 2020,
                "source": "OpenAlex",
                "scout_verdict": "Relevant"
            },
            {
                "title": "Bad Paper Missing Year"
            }
        ]
    }
    '''
    papers = validate_scout_output(raw)
    assert len(papers) == 1
    assert papers[0].title == "Good Paper"
