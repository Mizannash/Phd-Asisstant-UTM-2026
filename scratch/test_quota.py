import os
import sys

# Ensure we're in the right directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from quota_manager import QuotaManager

# Mock multiple keys in the environment
os.environ["GEMINI_API_KEY_1"] = "FAKE_KEY_1"
os.environ["GEMINI_API_KEY_2"] = "FAKE_KEY_2"
os.environ["GEMINI_API_KEY_3"] = "FAKE_KEY_3"

def mock_llm_call_daily_exhaustion():
    print(f"Calling LLM with key: {os.environ.get('GEMINI_API_KEY')}")
    # Simulate a daily quota exhaustion
    raise Exception("429 Resource has been exhausted (e.g. check quota).")

def test():
    print("--- STARTING TEST ---")
    try:
        QuotaManager.execute_call(mock_llm_call_daily_exhaustion)
    except Exception as e:
        print(f"Final error caught: {e}")
        
if __name__ == "__main__":
    test()
