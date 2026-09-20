import sys
import os
sys.path.insert(0, r"D:\PhD_Assistant_UTM\src")
from main import run_crew_pipeline
import logging

try:
    print("Testing pipeline with fake key...")
    run_crew_pipeline(paper_text="Test paper about AI in TVET Kolej Vokasional", mode="standard", api_key="FAKE_KEY_FOR_TESTING")
except Exception as e:
    import traceback
    traceback.print_exc()
