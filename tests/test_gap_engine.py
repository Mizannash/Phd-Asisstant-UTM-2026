import pytest
from src.core.gap_engine import _tokenize, _run_t0_clustering, run_gap_engine_t0_t1, run_gap_engine_t2_verification
from src.core.library_state import library_state

def test_tokenize():
    tokens = _tokenize("The quick brown fox jumps over the lazy dog.")
    assert "quick" in tokens
    assert "fox" in tokens
    assert "the" not in tokens

def test_t0_clustering(mocker):
    # Mock library state
    mocker.patch.object(library_state, 'state', {
        "papers": [
            {"abstract": "artificial intelligence in education", "findings": "ai improves learning"},
            {"abstract": "machine learning for predictive models", "topics": ["artificial intelligence"]}
        ]
    })
    clusters = _run_t0_clustering()
    assert "artificial" in clusters
    assert "intelligence" in clusters

def test_t1_synthesis(mocker):
    mocker.patch("src.core.gap_engine._run_t0_clustering", return_value=["ai", "education"])
    mocker.patch.object(library_state, 'state', {"threats": [{"date": "2024", "text": "threat1"}]})
    
    mock_resp = '[{"statement": "Gap 1", "rationale": "Rat 1", "status": "CANDIDATE"}]'
    mocker.patch("src.core.gap_engine.get_llm_response", return_value=mock_resp)
    
    res = run_gap_engine_t0_t1()
    assert len(res["candidate_gaps"]) == 1
    assert res["candidate_gaps"][0]["statement"] == "Gap 1"

def test_t2_verification_programmatic_rejection(mocker):
    candidate_gaps = [{"statement": "Gap 1", "rationale": "Rat 1"}]
    
    # LLM says valid but only provides 1 supporting paper
    mock_resp = '{"is_valid": true, "rejection_reason": "", "supporting_evidence": [{"paper_id": "1", "evidence": "ev1"}]}'
    mocker.patch("src.core.gap_engine.get_llm_response", return_value=mock_resp)
    
    original_gaps = library_state.state.get("gaps", []).copy()
    original_rejected = library_state.state.get("rejected_candidates", []).copy()
    
    try:
        res = run_gap_engine_t2_verification(candidate_gaps)
        # Should be rejected because len(evidence) < 2
        assert len(res["verified_gaps"]) == 0
        assert len(res["rejected_gaps"]) == 1
        assert "programmatic rejection" in res["rejected_gaps"][0]["rejection_reason"].lower()
    finally:
        library_state.state["gaps"] = original_gaps
        library_state.state["rejected_candidates"] = original_rejected
        library_state.save_state()
