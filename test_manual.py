import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.dirname(__file__))
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

print("--- Testing Supervisor Chat ---")
try:
    from src.chatbot import chat_with_supervisor
    # We pass empty history and a simple message
    reply, sources = chat_with_supervisor([], "Hello! Are you working?")
    print("Success. Reply:", reply)
    print("Sources:", sources)
except Exception as e:
    print("Chat Failed:", e)

print("\n--- Testing DEV_MOCK Pipeline ---")
try:
    os.environ["DEV_MOCK"] = "1"
    from src.main import run_crew_pipeline
    run_crew_pipeline()
    print("Pipeline DEV_MOCK completed.")
except Exception as e:
    print("Pipeline DEV_MOCK failed:", e)
