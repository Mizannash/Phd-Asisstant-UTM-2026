import os
import sys
import json
import yaml
from datetime import datetime
from dotenv import load_dotenv

import io
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Ensure we're in the right directory and load env
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
load_dotenv(os.path.join(project_root, ".env"))

from crewai import Agent, Task, Crew, Process
from src.tools.search_tools import openalex_search_tool

def load_yaml(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def write_scout_log(message: str):
    """Appends a message to the scout_log.txt with a timestamp."""
    log_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "scout_log.txt")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()[:19]}] {message}\n")

def run_scout_pipeline(on_rate_limit_callback=None, force_run=False):
    """Runs the background literature scout pipeline."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    
    # 1. Date Lock Check
    library_path = os.path.join(base_dir, "output", "library.json")
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if not force_run and os.path.exists(library_path):
        try:
            with open(library_path, "r", encoding="utf-8") as f:
                lib_data = json.load(f)
            if lib_data.get("last_scout_date") == today_str:
                write_scout_log("Scout skipped — already ran today.")
                return
        except Exception:
            pass

    # 2. Quota Guard Pre-flight Check
    from quota_manager import QuotaManager
    keys_loaded = QuotaManager.get_total_keys()
    print(f"[QuotaManager] Loaded {keys_loaded} API keys at startup.")
    print(f"[QuotaManager] Starting with Key {QuotaManager.get_active_key_index() + 1}.")
    if QuotaManager.all_keys_exhausted():
        write_scout_log("Scout skipped — no quota available")
        return

    write_scout_log("Scout started.")
    
    agents_config = load_yaml(os.path.join(base_dir, "config", "agents.yaml"))
    tasks_config = load_yaml(os.path.join(base_dir, "config", "tasks.yaml"))

    import time
    try:
        # Kickoff the crew with retry logic for 429 Rate Limits
        result = None
        from config import CREWAI_PRIMARY_MODEL
        from crewai import LLM
        
        def create_scout_crew(model_string=CREWAI_PRIMARY_MODEL):
            current_key = QuotaManager.get_current_key()
            if current_key:
                os.environ["GEMINI_API_KEY"] = current_key
                
            crewai_llm = LLM(model=model_string)

            scout = Agent(
                config=agents_config["literature_scout"],
                llm=crewai_llm,
                tools=[openalex_search_tool],
                max_iter=3
            )

            expert = Agent(
                config=agents_config["tvet_domain_expert"],
                llm=crewai_llm,
                tools=[],  
                max_iter=3
            )

            scout_task = Task(config=tasks_config["scout_task"], agent=scout)
            filter_task = Task(config=tasks_config["filter_task"], agent=expert)

            return Crew(
                agents=[scout, expert],
                tasks=[scout_task, filter_task],
                process=Process.sequential,
                verbose=True
            )

        if force_run == "MOCK":
            print("Mock mode enabled. Bypassing CrewAI.")
            result_str = json.dumps({"papers": [{"title": "Mock Paper for Task Scheduler Test", "authors": "Ahmad et al.", "year": "2026", "abstract": "This is a mock abstract for logging verification.", "relevance_score": 9, "url": "http://mock.url"}]})
        else:
            from config import CREWAI_FALLBACK_MODEL, CREWAI_PRIMARY_MODEL
            import sys
            
            max_attempts = 2
            attempts = 0
            server_error_count = 0
            
            while attempts < max_attempts:
                model_to_use = CREWAI_PRIMARY_MODEL if attempts == 0 else CREWAI_FALLBACK_MODEL
                print(f"Starting pipeline attempt {attempts + 1}/{max_attempts} with model {model_to_use}...")
                
                # CREW IS ALWAYS CREATED FRESH INSIDE THE LOOP
                scout_crew = create_scout_crew(model_string=model_to_use)
                
                try:
                    result = scout_crew.kickoff()
                    QuotaManager.record_call()
                    break
                except Exception as e:
                    err_str = str(e)
                    if "400" in err_str and "ending with a model turn are not supported" in err_str:
                        global _logged_400
                        if '_logged_400' not in globals():
                            import traceback
                            print("\n[WARNING] Encountered known LiteLLM 400 forced-final-answer bug. Suppressing this error and aborting attempt safely. Traceback:")
                            traceback.print_exc()
                            _logged_400 = True
                        else:
                            print("[WARNING] Encountered known LiteLLM 400 bug again. Suppressing.")
                        break
                        
                    action = QuotaManager.handle_error(e)
                    
                    if action == "RETRYABLE_SERVER_ERROR":
                        wait_times = [30, 60, 120, 120, 120]
                        base_wait = wait_times[server_error_count] if server_error_count < len(wait_times) else 120
                        import random
                        wait_time = base_wait * random.uniform(0.8, 1.2)
                        
                        key_idx = QuotaManager.get_active_key_index() + 1
                        if on_rate_limit_callback:
                            on_rate_limit_callback(int(wait_time), server_error_count + 1, 5)
                        else:
                            print(f"[QuotaManager] 503 overloaded. Retrying (Attempt {server_error_count + 1}/5) in {wait_time:.1f}s on Key {key_idx}...")
                            time.sleep(wait_time)
                            
                        server_error_count += 1
                        
                        # Hard cap logic for 503
                        if server_error_count >= 5:
                            attempts += 1
                            if attempts >= max_attempts:
                                msg = "503 persisted — scout aborted, will retry on next schedule"
                                print(msg)
                                write_scout_log(msg)
                                sys.exit(0)
                            else:
                                print(f"Triggering Fallback to {CREWAI_FALLBACK_MODEL} as a fresh session.")
                                server_error_count = 0
                        
                        continue
                        
                    elif action == "ROTATED_KEY":
                        # We rotated the key, we should recreate crew and try again without counting as a pipeline attempt failure
                        continue
                        
                    elif action == "PER_MINUTE_LIMIT":
                        wait_time = 20
                        if on_rate_limit_callback:
                            on_rate_limit_callback(int(wait_time), server_error_count + 1, 3)
                        else:
                            print(f"Rate limit hit. Waiting {wait_time}s...")
                            time.sleep(wait_time)
                        
                        server_error_count += 1
                        if server_error_count >= 3:
                            attempts += 1
                            if attempts >= max_attempts:
                                msg = "Rate limit persisted — scout aborted, will retry on next schedule"
                                print(msg)
                                write_scout_log(msg)
                                sys.exit(0)
                            else:
                                print(f"Triggering Fallback to {CREWAI_FALLBACK_MODEL} as a fresh session.")
                                server_error_count = 0
                        continue
                        
                    elif action == "ALL_KEYS_EXHAUSTED":
                        if QuotaManager.run_recovery_probe():
                            print(f"\n[QuotaManager] Key Recovery Probe SUCCESS! Resetting to Key 1.")
                            continue
                            
                        reasons = []
                        keys = QuotaManager._get_keys()
                        for i in range(len(keys)):
                            r = QuotaManager.get_state(f"exhaustion_reason_{i}", "Unknown")
                            reasons.append(f"Key {i+1}: {r}")
                        raise Exception("ALL API KEYS EXHAUSTED.\n" + "\n".join(reasons)) from e
                        
                    else:
                        print(f"Unhandled error ({e}), aborting attempt...")
                        server_error_count += 1
                        if server_error_count >= 3:
                            attempts += 1
                            if attempts >= max_attempts:
                                raise e
                            else:
                                print(f"Triggering Fallback to {CREWAI_FALLBACK_MODEL} as a fresh session.")
                                server_error_count = 0
                        continue
            
            result_str = str(result) if result else ""
        
        # CrewAI output might have markdown formatting if the agent disobeys. Let's clean it up.
        result_str = result_str.strip()
        if result_str.startswith("```json"):
            result_str = result_str.replace("```json", "", 1)
            if result_str.endswith("```"):
                result_str = result_str[:-3]
        elif result_str.startswith("```"):
            result_str = result_str.replace("```", "", 1)
            if result_str.endswith("```"):
                result_str = result_str[:-3]
                
        result_str = result_str.strip()

        try:
            new_data = json.loads(result_str)
            if "papers" not in new_data:
                print("Warning: JSON output did not contain 'papers' array.")
                return
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON output from agent: {e}")
            print(f"Raw Output:\n{result_str}")
            return

        # Save to JSON database
        output_file = os.path.join(base_dir, "output", "library.json")
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        existing_data = {"papers": []}
        if os.path.exists(output_file):
            try:
                with open(output_file, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
            except json.JSONDecodeError:
                print("Warning: existing library.json is corrupted. Starting fresh.")

        from src.db.library import LibraryDB
        from src.logger import log_event
        import sys
        sys.path.append(os.path.dirname(__file__))
        from src.threat_detector import check_novelty_threat
        
        # Create a set of existing lowercase titles for deduplication
        existing_titles = {p.get("title", "").strip().lower() for p in existing_data.get("papers", [])}
        
        # Append new papers (ignoring duplicates)
        newly_added_count = 0
        for paper in new_data.get("papers", []):
            paper_title = paper.get("title", "").strip().lower()
            if paper_title and paper_title not in existing_titles:
                paper["scouted_at"] = datetime.now().isoformat()
                existing_data["papers"].append(paper)
                existing_titles.add(paper_title)
                newly_added_count += 1
                check_novelty_threat(paper.get("title", ""), paper.get("abstract", ""), paper.get("relevance_score", 0), paper.get("year", 0))

        # Update Date Lock
        today_str = datetime.now().strftime("%Y-%m-%d")
        existing_data["last_scout_date"] = today_str

        success = False
        try:
            LibraryDB()._write_atomic(existing_data, output_file)
            success = True
        except Exception as e:
            print(f"Error writing to library: {e}")
        if success:
            if len(new_data.get('papers', [])) > 0 and newly_added_count == 0:
                print(f"No new papers found - all {len(new_data.get('papers', []))} candidates are duplicates/already analyzed")
                write_scout_log(f"Scout complete. No new papers found (all {len(new_data.get('papers', []))} duplicates).")
            else:
                msg = f"Successfully scouted and saved {newly_added_count} new papers (ignored {len(new_data.get('papers', [])) - newly_added_count} duplicates)."
                print(f"[{datetime.now()}] {msg}")
                log_event("SCOUT_SUCCESS", msg)
                current_key = QuotaManager.get_current_key()
                key_index = QuotaManager._get_keys().index(current_key) + 1 if current_key in QuotaManager._get_keys() else "Unknown"
                write_scout_log(f"Scout complete. Found {newly_added_count} new papers. Used Key {key_index}.")
        else:
            print("Failed to save scouted papers.")
            write_scout_log("Scout failed during library write.")

    except Exception as e:
        print(f"An error occurred during scout pipeline: {e}")
        write_scout_log(f"Scout crashed with error: {e}")
        raise e

if __name__ == "__main__":
    run_scout_pipeline()
