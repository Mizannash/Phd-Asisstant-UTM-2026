import pytest
import os
import shutil
from src.core.llm_factory import get_llm_response, ACTUAL_CALLS_FILE, FAILURES_FILE, _custom_success_callback, _custom_failure_callback
from src.core.budget import budget_manager
from src.core.cache import cache

@pytest.fixture(autouse=True)
def clean_env():
    if os.path.exists("output/analytics"):
        shutil.rmtree("output/analytics")
    os.makedirs("output/analytics")
    
    from src.core.llm_factory import _init_csv, ACTUAL_CALLS_FILE, FAILURES_FILE
    _init_csv(ACTUAL_CALLS_FILE, ["timestamp", "pipeline", "model", "total_tokens", "prompt_tokens", "completion_tokens"])
    _init_csv(FAILURES_FILE, ["timestamp", "pipeline", "model", "error"])
    
    if os.path.exists("data/cache/llm_cache.json"):
        os.remove("data/cache/llm_cache.json")
    cache._cache = {}
    yield

def test_t2_refusal():
    with pytest.raises(ValueError, match="confirm_expensive=True"):
        get_llm_response([{"role": "user", "content": "test"}], tier="T2", confirm_expensive=False)
    
    assert os.path.exists(FAILURES_FILE)
    with open(FAILURES_FILE, "r", encoding="utf-8") as f:
        content = f.read()
        assert "T2-rejected" in content

def test_budget_integration(mocker):
    _custom_success_callback(
        {"model": "gemini/gemini-1.5-flash", "litellm_params": {"metadata": {"pipeline": "test"}}},
        {"usage": {"total_tokens": 1000}},
        None, None
    )
    
    cost, calls = budget_manager.calculate_current_usage()
    assert calls == 1
    assert cost == 0.01 # 1000 * 0.00001 (mock cost)

def test_budget_ignores_failures():
    _custom_failure_callback(
        {"model": "gemini/gemini-1.5-flash", "exception": "API Error"},
        None, None, None
    )
    
    cost, calls = budget_manager.calculate_current_usage()
    assert calls == 0
    assert cost == 0.0
