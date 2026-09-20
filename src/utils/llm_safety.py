import time
import json
from typing import Callable, Any, Tuple, Optional

def default_sleep(seconds: float):
    time.sleep(seconds)

def safe_llm_call(call_fn: Callable[[], Any], max_retries: int = 2, sleep_fn: Callable[[float], None] = default_sleep) -> Optional[Any]:
    """
    Executes an LLM call. If the response is None, empty, or whitespace, it retries up to max_retries times.
    Returns the response on success, or None if all retries fail.
    """
    for attempt in range(max_retries + 1):
        try:
            response = call_fn()
        except Exception as e:
            response = None
            print(f"LLM call exception: {e}")
            
        # For strings, check if empty/whitespace
        if isinstance(response, str):
            if response.strip():
                return response
        # For dicts/objects (e.g. from with_structured_output), if it's truthy, return it
        elif response:
            return response
            
        print(f"Empty LLM response, retry {attempt + 1}/{max_retries}")
        if attempt < max_retries:
            sleep_fn(2.0)
            
    return None

def safe_json_call(call_fn: Callable[[], Any], parse_fn: Callable[[str], Any] = json.loads, max_retries: int = 1, sleep_fn: Callable[[float], None] = default_sleep) -> Tuple[Optional[str], Any]:
    """
    Executes an LLM call, then attempts to parse the response as JSON using parse_fn.
    If parsing fails with JSONDecodeError, retries the ENTIRE call up to max_retries times.
    Returns (raw_text, parsed_json). On ultimate failure, parsed_json is None.
    """
    for attempt in range(max_retries + 1):
        raw_text = safe_llm_call(call_fn, max_retries=2, sleep_fn=sleep_fn)
        
        if not raw_text:
            return None, None
            
        try:
            parsed = parse_fn(str(raw_text))
            return raw_text, parsed
        except json.JSONDecodeError as e:
            print(f"JSON decode failed: {e}, retry {attempt + 1}/{max_retries}")
            if attempt < max_retries:
                sleep_fn(2.0)
                continue
            return raw_text, None
        except Exception as e:
            print(f"Unexpected parse error: {e}")
            return raw_text, None
            
    return None, None
