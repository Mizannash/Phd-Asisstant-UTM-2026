import pytest
from src.core.analyze import estimate_cost, analyze_paper
from src.core.library_state import library_state

def test_estimate_cost(mocker):
    # Mock cache to return None
    mocker.patch("src.core.analyze.cache.get", return_value=None)
    text = "A " * 100 # 100 words, length ~ 200 chars. 200/4 = 50 tokens
    result = estimate_cost(text)
    assert result["estimated_tokens"] == len(text) // 4
    assert result["is_cached"] is False
    assert result["model"] == "groq/openai/gpt-oss-120b"

def test_analyze_paper_success(mocker):
    mock_resp = '{"title": "Test Title", "authors": ["A"], "year": 2024, "summary": "test", "methodology": "test", "findings": "test", "topics_covered": ["t1"], "population": "pop", "malaysian_context": true, "psychomotor_tvet_signals": "sig"}'
    mocker.patch("src.core.analyze.get_llm_response", return_value=mock_resp)
    
    # Save original state to restore
    original_papers = library_state.state.get("papers", []).copy()
    
    try:
        entry = analyze_paper("some text")
        assert entry["title"] == "Test Title"
        assert entry["malaysian_context"] is True
        assert len(library_state.state["papers"]) > len(original_papers)
    finally:
        library_state.state["papers"] = original_papers
        # cleanup hashes
        if "source_hashes" in library_state.state:
            library_state.state["source_hashes"].clear()
        library_state.save_state()

def test_analyze_paper_duplicate(mocker):
    mock_resp = '{"title": "Test Title", "authors": ["A"], "year": 2024, "summary": "test", "methodology": "test", "findings": "test", "topics_covered": ["t1"], "population": "pop", "malaysian_context": true, "psychomotor_tvet_signals": "sig"}'
    mocker.patch("src.core.analyze.get_llm_response", return_value=mock_resp)
    
    original_papers = library_state.state.get("papers", []).copy()
    original_hashes = library_state.state.get("source_hashes", {}).copy()
    
    text = "duplicate text test"
    try:
        analyze_paper(text)
        with pytest.raises(ValueError, match="duplicate"):
            analyze_paper(text)
    finally:
        library_state.state["papers"] = original_papers
        library_state.state["source_hashes"] = original_hashes
        library_state.save_state()
