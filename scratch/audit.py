import os
import sys
import json
import glob

D_PATH = r"D:\PhD_Assistant_UTM"
SCRATCH_PATH = r"c:\Users\user\.gemini\antigravity-ide\scratch\crewai_research_assistant"

def check_1_env():
    print("--- 1. ENV FILE INTEGRITY ---")
    env_path = os.path.join(D_PATH, ".env")
    if not os.path.exists(env_path):
        print(f"[FAIL] .env missing at {env_path}")
        return
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    keys = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"): continue
        if "=" in line:
            k, v = line.split("=", 1)
            keys[k.strip()] = v.strip()
    
    print(f"Total key=value lines found: {len(keys)}")
    expected_keys = ["GEMINI_API_KEY_1", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3", "GEMINI_API_KEY_4", "SERPER_API_KEY"]
    for ek in expected_keys:
        if ek not in keys:
            print(f"[FAIL] Missing expected key: {ek}")
        elif not keys[ek]:
            print(f"[FAIL] Empty expected key: {ek}")
        else:
            print(f"[PASS] Found {ek}")

def check_3_data():
    print("--- 3. DATA INTEGRITY ---")
    def cmp_file(rel_path, is_json=False):
        d_file = os.path.join(D_PATH, rel_path)
        s_file = os.path.join(SCRATCH_PATH, rel_path)
        
        if os.path.exists(s_file) and not os.path.exists(d_file):
            print(f"[FAIL] {rel_path} exists in scratch backup but MISSING from D: drive")
            return
        if not os.path.exists(d_file):
            print(f"[INFO] {rel_path} does not exist in D: or scratch")
            return
            
        print(f"[PASS] {rel_path} exists in D:")
        if is_json:
            try:
                with open(d_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                print(f"  Valid JSON.")
                if "library.json" in rel_path:
                    print(f"  Number of papers: {len(data.get('papers', []))}")
                    print(f"  last_scout_date: {data.get('last_scout_date', 'N/A')}")
            except Exception as e:
                print(f"[FAIL] {rel_path} invalid JSON: {e}")
                
        if "scout_log.txt" in rel_path:
            with open(d_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            print("  Last 3 lines:")
            for l in lines[-3:]:
                print("  > " + l.strip())

    cmp_file("output/library.json", is_json=True)
    cmp_file("output/scout_log.txt")
    
    # check chat_history
    d_chat = os.path.join(D_PATH, "output/chat_history")
    if os.path.exists(d_chat):
        files = os.listdir(d_chat)
        print(f"[PASS] chat_history exists, {len(files)} files")
        for f in files:
            if f.endswith(".json"):
                try:
                    with open(os.path.join(d_chat, f), "r") as fj:
                        json.load(fj)
                except:
                    print(f"[FAIL] invalid JSON in {f}")
    else:
        print("[FAIL] chat_history missing")

    # check backups
    d_bak = os.path.join(D_PATH, "output/backups")
    if os.path.exists(d_bak):
        print(f"[PASS] backups exists, {len(os.listdir(d_bak))} files")
    else:
        print("[FAIL] backups missing")

    cmp_file("research_context.json", is_json=True)

def check_4_quota():
    print("--- 4. QUOTAMANAGER LIVE TEST ---")
    sys.path.insert(0, os.path.join(D_PATH, "src"))
    try:
        import dotenv
        dotenv.load_dotenv(os.path.join(D_PATH, ".env"))
        from quota_manager import QuotaManager
        qm = QuotaManager()
        print(f"[PASS] QuotaManager loaded successfully")
        print(f"Keys loaded: {len(qm.api_keys)}")
        print(f"Active key index: {qm.current_key_idx}")
        print(f"all_keys_exhausted(): {qm.all_keys_exhausted()}")
    except Exception as e:
        print(f"[FAIL] Error loading QuotaManager: {e}")

def check_7_leak():
    print("--- 7. PATH LEAK CHECK ---")
    import os
    leaks = []
    for root, dirs, files in os.walk(D_PATH):
        if "venv" in root or "__pycache__" in root or ".git" in root:
            continue
        for f in files:
            if f.endswith((".py", ".bat", ".md", ".json", ".txt", ".env")):
                path = os.path.join(root, f)
                try:
                    with open(path, "r", encoding="utf-8") as file:
                        content = file.read()
                        if "antigravity-ide" in content or "crewai_research_assistant" in content:
                            leaks.append(path)
                except:
                    pass
    if leaks:
        print(f"[FAIL] Found leaks in {len(leaks)} files:")
        for l in leaks:
            print(f"  - {l}")
    else:
        print("[PASS] No path leaks found.")

if __name__ == '__main__':
    check_1_env()
    check_3_data()
    check_4_quota()
    check_7_leak()
