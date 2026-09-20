import os
import sys
import time

base_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.append(os.path.join(base_dir, "src"))

import scout
from quota_manager import QuotaManager
import google.genai.models
from google.genai.errors import ClientError

# 1. Patch QuotaManager so we don't fail Pre-flight check
QuotaManager.all_keys_exhausted = lambda: False
QuotaManager.get_current_key = lambda: "MOCK_KEY"
QuotaManager._get_keys = lambda: ["MOCK_KEY"]
os.environ["GEMINI_API_KEY"] = "MOCK_KEY"

# 2. Patch time.sleep to avoid waiting 105 seconds during the test
original_sleep = time.sleep
def fast_sleep(seconds):
    print(f"[MOCK] Skipping time.sleep({seconds}s)")
time.sleep = fast_sleep

# 3. Save original generate_content
original_generate_content = google.genai.models.Models.generate_content

class MockResponse:
    status_code = 503
    def json(self): return {}

def run_test_abort():
    print("\n" + "="*50)
    print("TEST 1: FULL ABORT PATH (Persistent 503)")
    print("="*50)
    
    # Mock to ALWAYS raise 503
    def mock_generate_always_503(self, *args, **kwargs):
        raise ClientError(503, {}, MockResponse())
        
    google.genai.models.Models.generate_content = mock_generate_always_503
    
    try:
        scout.run_scout_pipeline()
    except SystemExit as e:
        print(f"[TEST 1] SystemExit caught with code: {e.code}")
    except Exception as e:
        print(f"[TEST 1] FAILED: Unexpected exception: {e}")
        
def run_test_recovery():
    print("\n" + "="*50)
    print("TEST 2: RECOVERY PATH (3x 503 -> Fallback -> Success)")
    print("="*50)
    
    # Restore the real API key so the fallback actually runs!
    from dotenv import load_dotenv
    load_dotenv(os.path.join(base_dir, ".env"))
    QuotaManager.get_current_key = lambda: os.environ.get("GEMINI_API_KEY_1", "")
    QuotaManager._get_keys = lambda: [os.environ.get("GEMINI_API_KEY_1", "")]
    os.environ["GEMINI_API_KEY"] = QuotaManager.get_current_key()
    
    call_count = 0
    def mock_generate_3x_503(self, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 3:
            print(f"[MOCK LLM] Simulating 503 error on LLM call #{call_count}")
            raise ClientError(503, {}, MockResponse())
        else:
            print(f"[MOCK LLM] Allowing real LLM call #{call_count} on Fallback model...")
            return original_generate_content(self, *args, **kwargs)
            
    google.genai.models.Models.generate_content = mock_generate_3x_503
    
    try:
        scout.run_scout_pipeline()
        print("[TEST 2] Pipeline finished naturally.")
    except Exception as e:
        print(f"[TEST 2] FAILED with exception: {e}")

if __name__ == "__main__":
    run_test_abort()
    run_test_recovery()
    
    # Check if library.json datestamp was touched
    import json
    lib_path = os.path.join(base_dir, "output", "library.json")
    if os.path.exists(lib_path):
        with open(lib_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"\n[VERIFICATION] library.json last_scout_date: {data.get('last_scout_date')}")
            
    # Check scout_log.txt
    log_path = os.path.join(base_dir, "output", "scout_log.txt")
    if os.path.exists(log_path):
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            print("\n[VERIFICATION] Last 3 lines of scout_log.txt:")
            for line in lines[-3:]:
                print(line.strip())
