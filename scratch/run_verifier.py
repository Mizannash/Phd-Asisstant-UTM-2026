import os
import sys
import io
from dotenv import load_dotenv

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from src.theme_verifier import verify_theme

if __name__ == "__main__":
    report = verify_theme(
        "Tema 1: TPACK-AI framework",
        "TPACK-AI as a framework for Kolej Vokasional teacher readiness."
    )
    print("\n--- REPORT OUTPUT ---")
    print(report)
