import os
import sys
import yaml
import time
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process

# Import custom tools (adjust path if needed depending on where you run this from)
sys.path.append(os.path.join(os.path.dirname(__file__)))
from src.tools.verifier import CitationVerifier
from src.tools.search_tools import openalex_search_tool
from src.quota_manager import QuotaManager

def load_yaml(filepath):
    with open(filepath, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def initialize_obsidian_vault(base_dir):
    """
    Creates the foundational directories and files for an Obsidian Vault.
    """
    vault_dir = os.path.join(base_dir, "output", "Obsidian_Vault")
    dirs = [
        os.path.join(vault_dir, "01_Raw_Sources"),
        os.path.join(vault_dir, "02_Wiki"),
        os.path.join(vault_dir, "03_System"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)

    system_dir = os.path.join(vault_dir, "03_System")

    index_path = os.path.join(system_dir, "index.md")
    if not os.path.exists(index_path):
        with open(index_path, "w", encoding="utf-8") as f:
            f.write("# PhD Wiki Index\n_A catalog of all AI-generated literature concepts._\n")

    log_path = os.path.join(system_dir, "log.md")
    if not os.path.exists(log_path):
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("# AI Maintenance Log\n_Chronological record of Agent M2 actions._\n")

    schema_path = os.path.join(system_dir, "GEMINI_SCHEMA.md")
    if not os.path.exists(schema_path):
        with open(schema_path, "w", encoding="utf-8") as f:
            f.write("Rule: Use Obsidian [[Wiki-Links]] for cross-referencing related concepts and sources.\n")

def run_crew_pipeline(paper_text: str, mode: str = "standard", api_key: str = None, on_rate_limit_callback = None) -> str:
    """
    Executes the CrewAI Systematic Reviewer pipeline.
    """
    import sys, os
    sys.path.append(os.path.dirname(__file__))
    from utils import trim_paper_input
    
    # Fallback trim for safety to avoid massive context
    paper_text = trim_paper_input(paper_text)
    
    if mode == "supervisor":
        paper_text = f"[SUPERVISOR RECOMMENDED — MUST PROCESS]\n{paper_text}"
        
    base_dir = os.path.dirname(os.path.dirname(__file__))
    agents_config = load_yaml(os.path.join(base_dir, "config", "agents.yaml"))
    tasks_config = load_yaml(os.path.join(base_dir, "config", "tasks.yaml"))

    # Use provided API key or fallback to environment variable
    key_to_use = api_key if api_key else os.getenv("GEMINI_API_KEY")
    if not key_to_use:
        raise ValueError("GEMINI_API_KEY is not provided or set in environment variables.")

    # Set the API key in the environment for LiteLLM (used by CrewAI under the hood)
    
    # Load library context
    library_context = "Library Database: No papers found in the database yet."
    from src.db.library import LibraryDB
    try:
        db = LibraryDB()
        data = db._read()
        papers = data.get("papers", [])
        if papers:
            context_str = f"Library Database contains {len(papers)} papers:\n"
            for i, p in enumerate(papers, 1):
                title = p.get("title", "Unknown")
                year = p.get("year", "Unknown")
                context_str += f"{i}. [{year}] {title}\n"
            library_context = context_str
    except:
        pass

    from src.quota.budget import BudgetManager, LLMCallTracker, validate_groq_dev_model
    bm = BudgetManager()
    dev_state = bm.get_mode()
    dev_mode = dev_state.get("dev_mode", False)
    dev_mock = dev_state.get("dev_mock", False)
    
    provider = "groq" if dev_mode else "gemini"
    estimate = bm.config.get("estimates", {}).get("single_paper", 5)
    
    if not dev_mock and not bm.can_afford(estimate, provider=provider):
        return f"BUDGET_BLOCKED: This run needs ~{estimate} {provider} calls. Budget exhausted today. Enable Developer Mode to test without quota."
        
    if dev_mode:
        validate_groq_dev_model()
        
    tracker = LLMCallTracker(pipeline_name="systematic_reviewer")

    from config import CREWAI_PRIMARY_MODEL
    def create_scout_crew(mode=mode, model_string=CREWAI_PRIMARY_MODEL):
        current_key = QuotaManager.get_current_key()
        if current_key and not dev_mode and not dev_mock:
            os.environ["GEMINI_API_KEY"] = current_key

        from crewai import LLM
        model_kwargs = {"llm": LLM(model=model_string, callbacks=[tracker])}
        if dev_mock:
            from langchain_community.llms import FakeListLLM
            fake_llm = FakeListLLM(responses=['```json\n{"filename": "Paper_Fake.md", "content": "Fake content\\nVerdict: RELEVANT\\nScore: 10", "index_entry": "Fake", "log_entry": "Fake"}\n```'] * 10)
            model_kwargs = {"llm": fake_llm}
        elif dev_mode:
            model_kwargs = {"llm": LLM(model="groq/llama3-70b-8192", callbacks=[tracker])}

        systematic_reviewer = Agent(
            config=agents_config["systematic_reviewer"],
            tools=[openalex_search_tool],
            max_iter=3,
            **model_kwargs
        )
        
        comprehensive_review = Task(
            config=tasks_config["comprehensive_review_task"],
            agent=systematic_reviewer
        )

        return Crew(
            agents=[systematic_reviewer],
            tasks=[comprehensive_review],
            process=Process.sequential,
            verbose=True,
            max_rpm=10
        )

    scout_crew = create_scout_crew()
    server_error_count = 0
    while True:
        try:
            if server_error_count == 3:
                from config import CREWAI_FALLBACK_MODEL
                print(f"Triggering Fallback to {CREWAI_FALLBACK_MODEL} on attempt 4")
                scout_crew = create_scout_crew(mode=mode, model_string=CREWAI_FALLBACK_MODEL)
            
            raw_result = scout_crew.kickoff(inputs={"paper_text": paper_text, "library_context": library_context})
            QuotaManager.record_call()
            import json
            import datetime
            from src.models.schemas import validate_gemini_output
            
            result_str = str(raw_result)
            
            def retry_func(error_msg):
                print(f"Validation failed. Retrying... {error_msg}")
                new_prompt = paper_text + f"\n\nCRITICAL SYSTEM FEEDBACK: {error_msg}"
                return str(scout_crew.kickoff(inputs={"paper_text": new_prompt, "library_context": library_context}))
                
            validated_paper = validate_gemini_output(result_str, retry_func)
            
            if not validated_paper:
                return "Failed to parse JSON. Saved raw output to output/failed_json/."
                
            from src.db.library import LibraryDB
            db = LibraryDB()
            
            filename = db.generate_safe_filename(validated_paper.filename)
            content = validated_paper.content
            index_entry = validated_paper.index_entry
            log_entry = validated_paper.log_entry
            
            if dev_mode or dev_mock:
                dev_dir = os.path.join(base_dir, "output", "dev_runs")
                os.makedirs(dev_dir, exist_ok=True)
                dev_path = os.path.join(dev_dir, filename)
                with open(dev_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return f"Dev Mode active. Wrote output to {dev_path} instead of library."
            
            try:
                
                vault_dir = os.path.join(base_dir, "output", "Obsidian_Vault")
                
                wiki_path = os.path.join(vault_dir, "02_Wiki", filename)
                with open(wiki_path, "w", encoding="utf-8") as f:
                    f.write(content)
                    
                log_path = os.path.join(vault_dir, "03_System", "log.md")
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"\n- [{now_str}] {log_entry}")
                
                title_clean = validated_paper.filename.replace("Paper_", "").replace(".md", "").replace("_", " ")
                import re
                verdict_match = re.search(r'Verdict:\s*(RELEVANT|PARTIAL|REJECT)', content, re.IGNORECASE)
                verdict = verdict_match.group(1).upper() if verdict_match else "UNKNOWN"
                
                new_entry = {
                    "title": title_clean,
                    "status": "analyzed",
                    "verdict": verdict,
                    "index_entry": index_entry
                }
                
                if db.exists(title_clean):
                    db.promote(title_clean, new_entry)
                else:
                    db.append(new_entry)
                    
                db.render_index()
                
                try:
                    from src.rag.vectorstore import index_sync
                    # We sync the whole library incrementally since it's local and very fast
                    # Alternatively, just pass the dict. But reading from db gives full content if needed.
                    # Wait, the RAG index needs abstract and content. 
                    # new_entry doesn't have it. We must build it.
                    full_entry = {
                        "title": title_clean,
                        "year": str(datetime.datetime.now().year), # approximate
                        "abstract": str(paper_text[:500]), # fallback if not in db
                        "content": content,
                        "verdict": verdict,
                        "status": "analyzed",
                        "filename": filename
                    }
                    index_sync(full_entry)
                except Exception as e:
                    print(f"Failed to sync RAG index: {e}")
                    
                # Rejection Audit
                if verdict == "REJECT":
                    try:
                        audit_path = os.path.join(vault_dir, "03_System", "rejection_audit.md")
                        score_match = re.search(r'Score:\s*(\d+)', content, re.IGNORECASE)
                        score = score_match.group(1) if score_match else "N/A"
                        # Clean content for table cell (remove newlines and truncate)
                        reasoning = content.replace("\n", " ").replace("|", " ")[:300] + "..."
                        
                        file_exists = os.path.exists(audit_path)
                        with open(audit_path, "a", encoding="utf-8") as f:
                            if not file_exists:
                                f.write("# Rejection Audit\n\n| Timestamp | Title | Score | Reasoning |\n| --- | --- | --- | --- |\n")
                            f.write(f"| {now_str} | {title_clean} | {score} | {reasoning} |\n")
                    except Exception as e:
                        print(f"WARNING: Failed to append to rejection audit: {e}")
                        
            except Exception as e:
                print(f"Failed to write to Obsidian Vault: {e}")
                
            return result_str
        except Exception as e:
            action = QuotaManager.handle_error(e)
            
            if action == "ROTATED_KEY":
                scout_crew = create_scout_crew(mode=mode)
                continue
            elif action == "RETRYABLE_SERVER_ERROR":
                if server_error_count < 3:
                    wait_times = [15, 30, 60]
                    wait_time = wait_times[server_error_count] if server_error_count < len(wait_times) else 60
                    if on_rate_limit_callback:
                        on_rate_limit_callback(int(wait_time), server_error_count + 1, 3)
                    else:
                        print(f"503 overloaded. Waiting {wait_time}s before retry {server_error_count + 1}/3...")
                        time.sleep(wait_time)
                    # NO ROTATION
                    server_error_count += 1
                    continue
                else:
                    raise Exception("Google servers are busy — try again in a few minutes.") from e
            elif action == "PER_MINUTE_LIMIT":
                if server_error_count < 3:
                    wait_time = 20
                    if on_rate_limit_callback:
                        on_rate_limit_callback(int(wait_time), server_error_count + 1, 3)
                    else:
                        print(f"Rate limit hit. Waiting {wait_time}s...")
                        time.sleep(wait_time)
                    server_error_count += 1
                    continue
                else:
                    raise Exception(f"Rate limit exceeded after retries.") from e
            elif action == "ALL_KEYS_EXHAUSTED":
                if QuotaManager.run_recovery_probe():
                    print(f"\n[QuotaManager] Key Recovery Probe SUCCESS! Resetting to Key 1.")
                    scout_crew = create_scout_crew(mode=mode)
                    continue
                    
                reasons = []
                keys = QuotaManager._get_keys()
                for i in range(len(keys)):
                    r = QuotaManager.get_state(f"exhaustion_reason_{i}", "Unknown")
                    reasons.append(f"Key {i+1}: {r}")
                raise Exception("ALL API KEYS EXHAUSTED.\n" + "\n".join(reasons)) from e
            else:
                raise e

def main():
    # Load environment variables
    load_dotenv()
    
    # Graceful handling of API Key
    if not os.getenv("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY not found in environment variables. Please check your .env file.")
        sys.exit(1)

    base_dir = os.path.dirname(os.path.dirname(__file__))
    initialize_obsidian_vault(base_dir)

    if len(sys.argv) < 2:
        print("Usage: python src/main.py [--input | --supervisor | --verify]")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "--verify":
        title = input("Enter paper title to verify: ")
        result = CitationVerifier.verify_paper(title)
        print("\n--- Verification Result ---")
        print(result)
        sys.exit(0)

    elif mode in ["--input", "--supervisor"]:
        paper_text = input("Paste paper abstract or title: ")
        
        from src.db.library import LibraryDB
        db = LibraryDB()
        db.backup()
        
        res = db.check_status(paper_text)
        if res:
            status = res.get("status")
            title = res.get("title")
            if status == "analyzed":
                print(f"\n[CACHE HIT] Paper already analyzed: {title}")
                try:
                    import csv
                    from datetime import datetime
                    cache_log = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "analytics", "cache_hits.csv")
                    os.makedirs(os.path.dirname(cache_log), exist_ok=True)
                    log_exists = os.path.exists(cache_log)
                    with open(cache_log, "a", newline="", encoding="utf-8") as cf:
                        writer = csv.writer(cf)
                        if not log_exists:
                            writer.writerow(["Timestamp", "Title"])
                        writer.writerow([datetime.now().isoformat(), title])
                except Exception as e:
                    print(f"Warning: Failed to log cache hit: {e}")
                sys.exit(0)
            elif status == "scouted":
                ans = input(f"\n[SCOUTED] Paper found in scout library ({res.get('confidence', 0):.1f}% match): {title}. Promote to full analysis? (y/n): ")
                if ans.lower() != 'y':
                    sys.exit(0)
                else:
                    paper_text = f"Title: {title}\nAbstract/Context: {res.get('scout_verdict', '')}"
        
        print("\nRunning CrewAI Pipeline...")
        # Note: 'mode' here expects "supervisor" or "standard" inside the function
        func_mode = "supervisor" if mode == "--supervisor" else "standard"
        
        result = run_crew_pipeline(paper_text, mode=func_mode)
        
        # The output is now written to the Obsidian Vault in run_crew_pipeline
        print(f"\nPipeline complete. Results added to Obsidian Vault.")

    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python src/main.py [--input | --supervisor | --verify]")
        sys.exit(1)

if __name__ == "__main__":
    main()
