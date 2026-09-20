import pytest
import litellm
from src.core.llm_factory import get_llm_response, groq_manager

def test_get_llm_response_rate_limit_backoff(mocker):
    # Mock litellm.completion to raise RateLimitError twice, then succeed
    mock_completion = mocker.patch("src.core.llm_factory.litellm.completion")
    
    class MockChoice:
        class MockMessage:
            content = "Success after backoff"
        message = MockMessage()
        
    class MockResponse:
        choices = [MockChoice()]
        
    # Raise RateLimitError on first two calls, succeed on third
    mock_completion.side_effect = [
        litellm.exceptions.RateLimitError("Rate limit 1", llm_provider="groq", model="test"),
        litellm.exceptions.RateLimitError("Rate limit 2", llm_provider="groq", model="test"),
        MockResponse()
    ]
    
    # Mock time.sleep to avoid actually waiting during tests
    mock_sleep = mocker.patch("src.core.llm_factory.time.sleep")
    
    import uuid
    msg = f"test_backoff_{uuid.uuid4()}"
    resp = get_llm_response([{"role": "user", "content": msg}])
    
    assert resp == "Success after backoff"
    assert mock_completion.call_count == 3
    assert mock_sleep.call_count == 2
    mock_sleep.assert_any_call(5)
    mock_sleep.assert_any_call(15)


def test_get_llm_response_auth_error_rotation(mocker):
    # Mock litellm.completion to raise AuthenticationError on first call, succeed on second
    mock_completion = mocker.patch("src.core.llm_factory.litellm.completion")
    
    class MockChoice:
        class MockMessage:
            content = "Success after rotation"
        message = MockMessage()
        
    class MockResponse:
        choices = [MockChoice()]
        
    mock_completion.side_effect = [
        litellm.exceptions.AuthenticationError("Auth failed", llm_provider="groq", model="test"),
        MockResponse()
    ]
    
    # Setup multiple keys
    groq_manager.keys = ["key1", "key2"]
    groq_manager.current_idx = 0
    
    import uuid
    msg = f"test_auth_{uuid.uuid4()}"
    resp = get_llm_response([{"role": "user", "content": msg}])
    
    assert resp == "Success after rotation"
    assert mock_completion.call_count == 2
    # Check that key rotated
    assert groq_manager.current_idx == 1
    assert groq_manager.get_current_key() == "key2"
