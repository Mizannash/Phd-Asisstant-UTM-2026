import pytest
import json
from src.utils.llm_safety import safe_llm_call, safe_json_call

def test_safe_llm_call_success():
    calls = 0
    def mock_call():
        nonlocal calls
        calls += 1
        return "Valid response"
    
    result = safe_llm_call(mock_call, max_retries=2, sleep_fn=lambda x: None)
    assert result == "Valid response"
    assert calls == 1

def test_safe_llm_call_empty_retry_then_success():
    calls = 0
    def mock_call():
        nonlocal calls
        calls += 1
        if calls < 3:
            return ""
        return "Recovered response"
    
    result = safe_llm_call(mock_call, max_retries=2, sleep_fn=lambda x: None)
    assert result == "Recovered response"
    assert calls == 3

def test_safe_llm_call_empty_exhausted():
    calls = 0
    def mock_call():
        nonlocal calls
        calls += 1
        return "   \n  "
    
    result = safe_llm_call(mock_call, max_retries=2, sleep_fn=lambda x: None)
    assert result is None
    assert calls == 3

def test_safe_llm_call_exception():
    calls = 0
    def mock_call():
        nonlocal calls
        calls += 1
        raise ValueError("Network Error")
    
    result = safe_llm_call(mock_call, max_retries=2, sleep_fn=lambda x: None)
    assert result is None
    assert calls == 3

def test_safe_json_call_success():
    calls = 0
    def mock_call():
        nonlocal calls
        calls += 1
        return '{"status": "ok"}'
    
    raw, parsed = safe_json_call(mock_call, max_retries=1, sleep_fn=lambda x: None)
    assert parsed == {"status": "ok"}
    assert raw == '{"status": "ok"}'
    assert calls == 1

def test_safe_json_call_retry_then_success():
    calls = 0
    def mock_call():
        nonlocal calls
        calls += 1
        if calls == 1:
            return "```json\nbad\n```"
        return '{"status": "ok"}'
    
    raw, parsed = safe_json_call(mock_call, max_retries=1, sleep_fn=lambda x: None)
    assert parsed == {"status": "ok"}
    assert calls == 2

def test_safe_json_call_exhausted():
    calls = 0
    def mock_call():
        nonlocal calls
        calls += 1
        return "bad data"
        
    raw, parsed = safe_json_call(mock_call, max_retries=1, sleep_fn=lambda x: None)
    assert parsed is None
    assert raw == "bad data"
    assert calls == 2
