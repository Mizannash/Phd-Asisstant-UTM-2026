import sys
import os
sys.path.insert(0, r"D:\PhD_Assistant_UTM\src")
from scout import run_scout_pipeline
print("Starting force run...")
run_scout_pipeline(force_run="MOCK")
print("Run complete.")
