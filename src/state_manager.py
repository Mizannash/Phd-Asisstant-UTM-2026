import os
import json
import datetime
import glob

try:
    from supabase import create_client, Client
    from dotenv import load_dotenv
    load_dotenv()
    supa_url = os.environ.get("SUPABASE_URL")
    supa_key = os.environ.get("SUPABASE_KEY")
    supabase: Client = None
    if supa_url and supa_key:
        supabase = create_client(supa_url, supa_key)
except ImportError:
    supabase = None

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
CHAT_HISTORY_DIR = os.path.join(OUTPUT_DIR, "chat_history")
RESEARCH_CONTEXT_FILE = os.path.join(OUTPUT_DIR, "research_context.json")
RESEARCH_CHANGELOG_FILE = os.path.join(OUTPUT_DIR, "research_context_changelog.json")

os.makedirs(CHAT_HISTORY_DIR, exist_ok=True)

def load_research_context():
    if supabase:
        try:
            response = supabase.table("json_store").select("data").eq("id", "research_context").execute()
            if response.data and len(response.data) > 0:
                return response.data[0]["data"]
        except Exception as e:
            print(f"Supabase read error (falling back to local): {e}")

    if not os.path.exists(RESEARCH_CONTEXT_FILE):
        return {
            "sample_scope": "",
            "states_zones": "",
            "study_duration": "",
            "methodology": "",
            "target": "",
            "current_stage": "Proposal Phase"
        }
    with open(RESEARCH_CONTEXT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_research_context(context_dict):
    if supabase:
        try:
            supabase.table("json_store").upsert({"id": "research_context", "data": context_dict}).execute()
        except Exception as e:
            print(f"Supabase write error: {e}")

    with open(RESEARCH_CONTEXT_FILE, "w", encoding="utf-8") as f:
        json.dump(context_dict, f, indent=4)

def append_to_changelog(old_context, new_context):
    changelog = []
    
    if supabase:
        try:
            response = supabase.table("json_store").select("data").eq("id", "research_changelog").execute()
            if response.data and len(response.data) > 0:
                changelog = response.data[0]["data"]
        except Exception:
            pass

    if not changelog and os.path.exists(RESEARCH_CHANGELOG_FILE):
        with open(RESEARCH_CHANGELOG_FILE, "r", encoding="utf-8") as f:
            try:
                changelog = json.load(f)
            except: pass
            
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "old": old_context,
        "new": new_context
    }
    changelog.append(entry)
    
    if supabase:
        try:
            supabase.table("json_store").upsert({"id": "research_changelog", "data": changelog}).execute()
        except Exception:
            pass

    with open(RESEARCH_CHANGELOG_FILE, "w", encoding="utf-8") as f:
        json.dump(changelog, f, indent=4)

def get_today_chat_file():
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    return os.path.join(CHAT_HISTORY_DIR, f"session_{today_str}.json")

def load_recent_chat_history(limit=30):
    messages = []
    if supabase:
        try:
            response = supabase.table("json_store").select("id, data").like("id", "chat_history_%").execute()
            if response.data:
                sorted_records = sorted(response.data, key=lambda x: x['id'], reverse=True)
                for record in sorted_records:
                    if len(messages) >= limit:
                        break
                    messages = record["data"] + messages
                return messages[-limit:]
        except Exception as e:
            print(f"Supabase read error (falling back to local): {e}")

    files = glob.glob(os.path.join(CHAT_HISTORY_DIR, "session_*.json"))
    files.sort(reverse=True) # newest first
    
    messages = []
    # Read files backwards until we have enough messages
    for file in files:
        if len(messages) >= limit:
            break
        with open(file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                # messages in file are chronological. We prepend them.
                messages = data + messages
            except: pass
            
    return messages[-limit:] # return strictly up to the limit

def save_chat_history(messages):
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    if supabase:
        try:
            supabase.table("json_store").upsert({"id": f"chat_history_{today_str}", "data": messages}).execute()
        except Exception as e:
            print(f"Supabase write error: {e}")

    file_path = get_today_chat_file()
    # Read existing messages from today, or start fresh
    existing_messages = []
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                existing_messages = json.load(f)
            except: pass
            
    # we just overwrite the whole file with the current session's state (which might be spanning multiple days if the server stayed up, but we'll save it into today's file). 
    # Wait, st.session_state.messages will have all the messages in memory. 
    # It's better to just overwrite today's file with the full session state history.
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=4)

def update_paper_assessment(paper_title: str, verdict: str, advice: str):
    import datetime
    from src.db.library import LibraryDB
    try:
        db = LibraryDB()
        from filelock import FileLock
        with FileLock(db.lock_path, timeout=10):
            data = db._read()
            papers = data.get("papers", [])
            for p in papers:
                if p.get("title") == paper_title:
                    if "assessments" not in p:
                        p["assessments"] = []
                    p["assessments"].append({
                        "verdict": verdict,
                        "advice": advice,
                        "date": datetime.datetime.now().isoformat()
                    })
                    break
            db._write_atomic(data, db.db_path)
    except:
        return

