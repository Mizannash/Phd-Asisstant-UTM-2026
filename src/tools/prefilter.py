import os
import yaml
import re
import csv
from datetime import datetime
from src.db.library import LibraryDB

def load_filters():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    config_path = os.path.join(base_dir, "config", "filters.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def log_decision(decision_row):
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    out_dir = os.path.join(base_dir, "output", "analytics")
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "prefilter_decisions.csv")
    
    file_exists = os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Title", "DOI", "Status", "Reason/Score", "Matched_Signals"])
        writer.writerow(decision_row)

def log_stats(total_in, survived, saved):
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    out_dir = os.path.join(base_dir, "output", "analytics")
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "prefilter_stats.csv")
    
    file_exists = os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Total_In", "Survived", "API_Calls_Saved"])
        writer.writerow([datetime.now().isoformat(), total_in, survived, saved])

def prefilter_openalex_results(raw_results: list[dict]) -> list[dict]:
    filters = load_filters()
    exclusions = filters.get("exclusions", [])
    inclusions = filters.get("inclusions", [])
    threshold = filters.get("threshold", 1)
    
    db = LibraryDB()
    survivors = []
    
    for paper in raw_results:
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")
        institutions = paper.get("institutions", "")
        doi = paper.get("doi", "")
        timestamp = datetime.now().isoformat()
        
        # 1. Deduplication
        # Exact match first inside check_status
        status = db.check_status(title)
        if status:
            log_decision([timestamp, title, doi, "Excluded", "dedup-skipped", ""])
            continue
            
        # 2. Check Inclusion Signals (Title + Abstract)
        matched_inclusions = []
        full_text = (title + " " + abstract).lower()
        for inc in inclusions:
            if inc.lower() in full_text:
                matched_inclusions.append(inc)
                
        # 3. Check Exclusion (Title + Institutions ONLY) if no strong inclusion
        excluded = False
        exclusion_reason = ""
        if not matched_inclusions:
            title_inst = (title + " " + institutions).lower()
            for exc in exclusions:
                if exc.lower() in ["smk", "smks"]:
                    if re.search(rf"\b{exc.lower()}\b", title_inst):
                        excluded = True
                        exclusion_reason = f"exclusion_keyword_{exc}"
                        break
                else:
                    if exc.lower() in title_inst:
                        excluded = True
                        exclusion_reason = f"exclusion_keyword_{exc}"
                        break
                        
        if excluded:
            log_decision([timestamp, title, doi, "Excluded", exclusion_reason, ""])
            continue
            
        # 4. Scoring
        score = len(matched_inclusions)
        if score < threshold:
            log_decision([timestamp, title, doi, "Excluded", "below_threshold", str(matched_inclusions)])
            continue
            
        # Survived
        paper["relevance_score_prefilter"] = score
        survivors.append(paper)
        log_decision([timestamp, title, doi, "Survived", score, str(matched_inclusions)])
        
    api_calls_saved = len(raw_results) - len(survivors)
    print(f"Prefilter: {len(raw_results)} in, {len(survivors)} survived, {api_calls_saved} API calls saved")
    log_stats(len(raw_results), len(survivors), api_calls_saved)
    
    return survivors
