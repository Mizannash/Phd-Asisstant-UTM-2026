import os
import yaml

def load_supervisor_persona():
    # __file__ is src/models/prompts.py -> root is 3 levels up
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    agents_config_path = os.path.join(base_dir, "config", "agents.yaml")
    try:
        with open(agents_config_path, "r", encoding="utf-8") as f:
            agents_config = yaml.safe_load(f)
        role = agents_config.get("phd_co_supervisor", {}).get("role", "")
        goal = agents_config.get("phd_co_supervisor", {}).get("goal", "")
        backstory = agents_config.get("phd_co_supervisor", {}).get("backstory", "")
        
        # Inject Final Title if locked
        final_title_path = os.path.join(base_dir, "config", "final_title.txt")
        locked_context = ""
        if os.path.exists(final_title_path):
            with open(final_title_path, "r", encoding="utf-8") as f:
                locked_title = f.read().strip()
            locked_context = f"\n\n[CRITICAL DIRECTIVE: The researcher has LOCKED their final thesis title as: '{locked_title}'. You MUST treat this title and its implied methodology as FIXED. Do not debate alternative titles or methodologies, BUT you MUST immediately alert the researcher if new evidence in the library (especially NOVELTY THREAT detections) undermines or closes the locked title's research gap. Locking the decision does not silence the alarm.]"
            
        return f"Role: {role}\nGoal: {goal}\nBackstory: {backstory}{locked_context}"
    except Exception as e:
        print(f"Failed to load supervisor persona from agents.yaml: {e}")
        return ""

SUPERVISOR_PERSONA = load_supervisor_persona()
