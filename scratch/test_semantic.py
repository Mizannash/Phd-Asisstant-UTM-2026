import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))
from threat_detector import check_novelty_threat

# Pre-populate candidate titles for the test to work
base_dir = os.path.dirname(os.path.dirname(__file__))
titles_file = os.path.join(base_dir, "config", "candidate_titles.md")
os.makedirs(os.path.dirname(titles_file), exist_ok=True)
with open(titles_file, "w", encoding="utf-8") as f:
    f.write("# Candidate Titles\n1. AI technology integration among construction technology teachers in Malaysia\n")

print("--- Testing Semantic Novelty Threat ---")

print("\n[Case A] True Positive: Low word overlap, High Semantic Match")
# Candidate: AI technology integration among construction technology teachers in Malaysia
# Test: Digital competency of vocational college instructors in Malaysia: a mixed-methods study
res_a = check_novelty_threat(
    "Digital competency of vocational college instructors in Malaysia: a mixed-methods study", 
    "This study evaluates how well KV teachers use digital tools for teaching.", 
    8.5, 2024
)
print(f"Threat detected: {res_a.get('threat')}")
if res_a.get("threat"):
    print(f"Level: {res_a.get('level')}")
    print(f"Similarity: {res_a.get('similarity')*100:.0f}%")
    print(f"Explanation: {res_a.get('explanation')}")

print("\n[Case B] True Negative: No Semantic Match")
res_b = check_novelty_threat(
    "Deep learning for stock price prediction", 
    "An LSTM model is used to forecast S&P500 index.", 
    8.5, 2024
)
print(f"Threat detected: {res_b.get('threat')}")
if res_b.get("threat"):
    print(f"Similarity: {res_b.get('similarity')*100:.0f}%")
