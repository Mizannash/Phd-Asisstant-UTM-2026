import sys
import os

# Dummy key for litellm
os.environ["GEMINI_API_KEY"] = "dummy"
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.main import run_crew_pipeline

print("--- Starting Dashboard Manual Analysis Trace Test ---")
try:
    print("Executing run_crew_pipeline (the exact function called by dashboard.py Analyze button)...")
    # Using a dummy rate limit callback like dashboard does
    result = run_crew_pipeline(
        paper_text="This is a test paper abstract.",
        mode="standard",
        api_key="dummy_key",
        on_rate_limit_callback=lambda w, a, m: None
    )
    print("SUCCESS: Pipeline executed past Agent instantiation successfully.")
except ValueError as e:
    if "Agent callbacks.0" in str(e):
        print(f"FAILED: The validation error remains: {e}")
        sys.exit(1)
    else:
        print(f"FAILED: Different ValueError: {e}")
        sys.exit(1)
except Exception as e:
    if "AuthenticationError" in str(e) or "API_KEY_INVALID" in str(e) or "VertexAIException" in str(e):
        print(f"SUCCESS: Reached LLM API layer but failed with expected dummy key error: {type(e).__name__}")
    else:
        print(f"WARNING: Pipeline progressed past Agent instantiation but hit a different error: {e}")
