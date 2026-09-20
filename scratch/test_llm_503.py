import os
import sys
import time
from dotenv import load_dotenv

# Force UTF-8
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Load environment
load_dotenv()
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from quota_manager import QuotaManager

# Mock Crew class to simulate failures
class MockCrew:
    def __init__(self):
        self.call_count = 0

    def kickoff(self, model_string=None):
        self.call_count += 1
        print(f"\n[MockCrew] Kickoff attempt {self.call_count} with model: {model_string or 'gemini/gemini-3.7-flash'}")
        
        if self.call_count <= 3:
            # Throw 503 Overload for the first 3 attempts
            raise Exception("Google Gemini API error: 503 - This model is currently experiencing high demand.")
        else:
            # Succeed on the 4th attempt (which should be the fallback model)
            if model_string == "gemini/gemini-3.5-flash-lite":
                return f"Success! Fallback model {model_string} answered the prompt."
            else:
                raise Exception("Did not receive fallback model on 4th attempt!")

def test_llm_503():
    print(f"Total API Keys configured: {QuotaManager.get_total_keys()}")
    print("\n--- Starting Simulated 503 Overload Test ---")
    
    mock_crew = MockCrew()
    
    # Redefine wait times in QuotaManager to be extremely fast for the test script
    # We will temporarily patch execute_call's internal logic just for this test script so we don't wait 105 seconds!
    # Wait, patching a local variable inside execute_call is hard. Let's just patch time.sleep!
    
    original_sleep = time.sleep
    def fast_sleep(seconds):
        print(f"*(Test Mock)* Sleeping for {seconds}s (skipped)")
    time.sleep = fast_sleep

    # The function we pass to QuotaManager
    def run_crew(model_string="gemini/gemini-3.7-flash"):
        return mock_crew.kickoff(model_string=model_string)

    try:
        result = QuotaManager.execute_call(run_crew, model_string="gemini/gemini-3.7-flash")
        print("\n\n=== TEST SUCCESS ===")
        print(f"Used API Key Index: {QuotaManager.get_active_key_index()}")
        print(f"Result:\n{result}")
    except Exception as e:
        print("\n\n=== TEST FAILED ===")
        import traceback
        traceback.print_exc()
    finally:
        time.sleep = original_sleep

if __name__ == "__main__":
    test_llm_503()
