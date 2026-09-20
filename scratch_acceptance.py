import json
import os
import sys
from pprint import pprint
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv(override=True)

from src.core.analyze import analyze_paper
from src.core.gap_engine import run_gap_engine_t0_t1, run_gap_engine_t2_verification
from src.core.budget import budget_manager
from src.core.library_state import library_state

def dump_file(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            print(f.read())
    else:
        print(f"File {path} not found.")

def main():
    print("--- PRE-FLIGHT: PURGE MOCK DATA ---")
    papers = library_state.state.get("papers", [])
    print(f"Initial paper count: {len(papers)}")
    
    # Purge stub entries
    purged_papers = []
    for p in papers:
        title = p.get("title") or ""
        abstract = p.get("abstract") or ""
        if "Gap 1" in title or "Test Paper" in title or "Gap 1" in abstract or "Test Title" in title:
            continue
        purged_papers.append(p)
        
    library_state.state["papers"] = purged_papers
    library_state.save_state()
    print(f"Reconciliation after purge: {len(purged_papers)} papers remaining (expected 12).")
    for p in purged_papers:
        print(f" - {p.get('id', 'N/A')}: {p.get('title')}")

    print("\n--- ACCEPTANCE 1: INGEST PAPER ---")
    test_paper = "This paper explores the usage of Artificial Intelligence in Kolej Vokasional to teach Construction Technology. We found that psychomotor skills significantly improved."
    print("Ingesting paper...")
    try:
        res = analyze_paper(test_paper)
        print("Analyze Output:")
        pprint(res)
    except Exception as e:
        print(f"Error during ingestion: {e}")
        sys.exit(1)
        
    print("\nIngested paper library_state entry:")
    new_paper = library_state.state["papers"][-1]
    pprint(new_paper)

    print("\n--- ACCEPTANCE 2: REPEAT ANALYSIS (CACHE TEST) ---")
    print("Re-running ingestion...")
    analyze_paper(test_paper)
    print("Cache test complete.")

    print("\n--- CSV TRACKER STATE AFTER INGESTION & CACHE ---")
    dump_file(budget_manager.actual_calls_file)

    print("\n--- ACCEPTANCE 3: GAP ENGINE T0+T1 ---")
    print(f"Running on {len(library_state.state.get('papers', []))} papers...")
    try:
        t1_res = run_gap_engine_t0_t1()
        print("T0 Clusters (Top keywords):")
        print(t1_res["clusters"])
        print("\nT1 Candidate Gaps (Verbatim JSON):")
        print(json.dumps(t1_res["candidate_gaps"], indent=2))
    except Exception as e:
        print(f"Error during T1: {e}")
        sys.exit(1)

    print("\n--- ACCEPTANCE 4: T2 DEFAULT BLOCK ---")
    try:
        print("Attempting to run T2 verification WITHOUT confirm_expensive=True...")
        res = run_gap_engine_t2_verification([{"statement": "Fake gap", "rationale": "fake"}])
        print("Wait, T2 ran successfully without confirm_expensive?!")
    except ValueError as e:
        print(f"T2 Blocked as expected: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

    print("\n--- ACCEPTANCE 5: T2 WITH CONFIRM_EXPENSIVE ---")
    try:
        print("Running T2 verification WITH confirm_expensive=True...")
        t2_res = run_gap_engine_t2_verification(t1_res["candidate_gaps"], confirm_expensive=True)
        print("\nT2 Verified Gaps:")
        pprint(t2_res["verified_gaps"])
        print("\nT2 Rejected Candidates (with reasons):")
        pprint(t2_res["rejected_gaps"])
    except Exception as e:
        print(f"Error during T2: {e}")

    print("\n--- FINAL CSV TRACKER STATE ---")
    dump_file(budget_manager.actual_calls_file)

if __name__ == "__main__":
    main()
