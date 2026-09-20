import os
import sys
import io
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
import json
import yaml
from datetime import datetime
from dotenv import load_dotenv

# Ensure we're in the right directory and load env
sys.path.insert(0, os.path.dirname(__file__))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from crewai import Agent, Task, Crew, Process
from src.tools.search_tools import fetch_openalex
from src.tools.prefilter import prefilter_openalex_results
from langchain_openai import ChatOpenAI
from src.models.schemas import validate_scout_output

def load_yaml(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def write_scout_log(message: str):
    """Appends a message to the scout_groq.log with a timestamp."""
    log_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "scout_groq.log")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()[:19]}] {message}\n")

def run_groq_scout():
    write_scout_log("Groq Scout started.")
    
    from src.db.library import LibraryDB
    LibraryDB().backup()
    
    from src.quota.budget import BudgetManager, LLMCallTracker
    bm = BudgetManager()
    dev_state = bm.get_mode()
    dev_mode = dev_state.get("dev_mode", False)
    dev_mock = dev_state.get("dev_mock", False)
    if dev_mock:
        write_scout_log("Warning: Scheduled scout run ignoring DEV_MOCK. Proceeding with real LLM.")
        dev_mock = False
        
    estimate = bm.config.get("estimates", {}).get("scout_run", 3)
    if not bm.can_afford(estimate, provider="groq"):
        write_scout_log(f"BUDGET BLOCKED: Scout run needs ~{estimate} groq calls but budget is exhausted.")
        sys.exit(0)
        
    tracker = LLMCallTracker(pipeline_name="scout_groq")
    
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        write_scout_log("Error: GROQ_API_KEY not found in .env")
        sys.exit(1)
        
    # Standardize litellm groq api key format if needed by crewai
    os.environ["GROQ_API_KEY"] = groq_api_key

    base_dir = os.path.dirname(os.path.dirname(__file__))
    agents_config = load_yaml(os.path.join(base_dir, "config", "agents.yaml"))
    tasks_config = load_yaml(os.path.join(base_dir, "config", "tasks.yaml"))

    try:
        groq_llm = ChatOpenAI(
            model="groq/qwen/qwen3.8-27b",
            api_key=groq_api_key,
            max_tokens=450,
            callbacks=[tracker]
        )
        
        # 1. Python-based OpenAlex Search & Prefilter
        filters_config = load_yaml(os.path.join(base_dir, "config", "filters.yaml"))
        queries = filters_config.get("queries", [])
        
        all_candidates = []
        for q in queries:
            results = fetch_openalex(q, limit=20)
            all_candidates.extend(results)
            
        # Quick dedupe by DOI before deep prefilter (which hits LibraryDB)
        unique_candidates = []
        seen_dois = set()
        seen_titles = set()
        # Sort newest first
        all_candidates.sort(key=lambda x: str(x.get("year", "0")), reverse=True)
        
        for c in all_candidates:
            doi = c.get("doi", "")
            title = c.get("title", "").lower()
            if doi and doi != "No DOI" and doi in seen_dois:
                continue
            if title in seen_titles:
                continue
            seen_dois.add(doi)
            seen_titles.add(title)
            unique_candidates.append(c)
            
        unique_candidates = unique_candidates[:25] # Cap at 25
        
        # 2. Prefilter
        survivors = prefilter_openalex_results(unique_candidates)
        
        if not survivors:
            write_scout_log("Prefilter: all candidates rejected — no API calls made.")
            sys.exit(0)
            
        # Format for agent
        filtered_papers_str = ""
        for i, s in enumerate(survivors, 1):
            filtered_papers_str += f"{i}. **{s['title']}**\n   - Authors: {s['authors']}\n   - Year: {s['year']}\n   - DOI: {s['doi']}\n   - Abstract: {s['abstract']}\n\n"

        # 3. Agent Execution
        scout = Agent(
            config=agents_config["groq_literature_scout"],
            llm=groq_llm,
            tools=[], # Removed openalex_search_tool
            max_iter=3
        )

        expert = Agent(
            config=agents_config["groq_tvet_domain_expert"],
            llm=groq_llm,
            tools=[],
            max_iter=3
        )

        scout_task = Task(
            config=tasks_config["groq_scout_task"], 
            agent=scout
        )
        
        filter_task = Task(config=tasks_config["groq_filter_task"], agent=expert)

        scout_crew = Crew(
            agents=[scout, expert],
            tasks=[scout_task, filter_task],
            process=Process.sequential,
            max_rpm=1,
            verbose=True
        )

        result = scout_crew.kickoff(inputs={"filtered_papers": filtered_papers_str})
        result_str = str(result).strip()

        valid_papers = validate_scout_output(result_str)
        if not valid_papers:
            write_scout_log("No valid papers returned from scout JSON. Exiting.")
            sys.exit(0)
            
        papers_found = len(valid_papers)
        write_scout_log(f"Groq Crew AI completed. Found {papers_found} valid papers.")

        from src.db.library import LibraryDB
        db = LibraryDB()
        
        if dev_mode:
            write_scout_log("Dev Mode active. Writing output to dev_runs/scout_raw.json instead of library.json.")
            dev_dir = os.path.join(base_dir, "output", "dev_runs")
            os.makedirs(dev_dir, exist_ok=True)
            with open(os.path.join(dev_dir, "scout_raw.json"), "w", encoding="utf-8") as f:
                f.write(result_str)
            write_scout_log(f"Saved {papers_found} papers to dev_runs/.")
            sys.exit(0)
            
        newly_added_count = 0
        for paper_obj in valid_papers:
            paper_dict = paper_obj.model_dump()
            paper_dict["scouted_at"] = datetime.now().isoformat()
            paper_dict["status"] = "scouted"
            if db.append(paper_dict):
                newly_added_count += 1
                
        write_scout_log(f"Groq Scout complete. Approved and appended {newly_added_count} new papers.")
        sys.exit(0)

    except Exception as e:
        write_scout_log(f"Groq Scout crashed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_groq_scout()
