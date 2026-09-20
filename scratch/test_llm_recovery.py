import os
import sys
import time
from dotenv import load_dotenv

# Force UTF-8
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

load_dotenv()
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from quota_manager import QuotaManager

class MockCrew:
    def __init__(self):
        self.call_count = 0

    def kickoff(self, model_string=None):
        self.call_count += 1
        active_key = QuotaManager.get_active_key_index() + 1
        print(f"\n[MockCrew] Kickoff attempt {self.call_count} on Key {active_key} using model {model_string}")
        
        if self.call_count == 1:
            # 1st call: Throw a 503 Overload
            raise Exception("Google Gemini API error: 503 - This model is currently experiencing high demand.")
        elif self.call_count in [2, 3, 4, 5]:
            # Next calls: Throw a 429 Quota Exhausted to force key rotation (K1 -> K2 -> K3 -> K4)
            raise Exception("429 Resource Exhausted: daily quota exceeded.")
        else:
            # On 6th call, it should be the fallback model if probe failed
            return f"Success! Served by {model_string}"

def test_llm_recovery():
    # Mock _get_keys so we simulate exactly 4 keys regardless of .env
    original_get_keys = QuotaManager._get_keys
    QuotaManager._get_keys = classmethod(lambda cls: ["key1", "key2", "key3", "key4"])

    print(f"Total API Keys configured: {QuotaManager.get_total_keys()}")
    print("\n--- Starting Simulated Recovery Test ---")
    
    # Reset QuotaManager state for test
    QuotaManager.set_state("active_key_index", 0)
    for i in range(4):
        QuotaManager.set_state(f"exhaustion_reason_{i}", "")
        
    mock_crew = MockCrew()
    
    # Patch time.sleep to run instantly
    original_sleep = time.sleep
    def fast_sleep(seconds):
        print(f"*(Test Mock)* Sleeping for {seconds}s (skipped)")
    time.sleep = fast_sleep

    # Mock the recovery probe to fail so that fallback model triggers
    original_probe = QuotaManager.run_recovery_probe
    def mock_fail_probe():
        print("[MockProbe] Simulating probe failure to trigger lite model fallback")
        return False
    QuotaManager.run_recovery_probe = mock_fail_probe

    def run_crew(model_string="gemini/gemini-3.7-flash"):
        return mock_crew.kickoff(model_string=model_string)

    try:
        result = QuotaManager.execute_call(run_crew, model_string="gemini/gemini-3.7-flash")
        print("\n\n=== TEST SUCCESS ===")
        print(f"Final Used API Key Index: {QuotaManager.get_active_key_index()}")
        print(f"Result:\n{result}")
    except Exception as e:
        print("\n\n=== TEST FAILED ===")
        import traceback
        traceback.print_exc()
    finally:
        time.sleep = original_sleep
        QuotaManager.run_recovery_probe = original_probe
        QuotaManager._get_keys = original_get_keys

if __name__ == "__main__":
    test_llm_recovery()
