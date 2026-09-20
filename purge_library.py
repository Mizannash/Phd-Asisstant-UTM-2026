import json
import os

state_path = "output/library_state.json"
if os.path.exists(state_path):
    with open(state_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Keep only the original 12 papers from migration
    if "papers" in data and len(data["papers"]) > 12:
        data["papers"] = data["papers"][:12]
        
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"Library state reset to {len(data['papers'])} papers.")
