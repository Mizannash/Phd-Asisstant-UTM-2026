import json
import os
import sys

from src.core.library_state import library_state
from src.core.gap_engine import _run_t0_clustering

def curate_library(remove_titles_file):
    if not os.path.exists(remove_titles_file):
        print(f"Error: {remove_titles_file} not found.")
        sys.exit(1)
        
    with open(remove_titles_file, 'r', encoding='utf-8') as f:
        titles_to_remove = [line.strip().lower() for line in f if line.strip()]
        
    all_papers = library_state.state.get("papers", [])
    before_count = len(all_papers)
    
    retained_papers = []
    removed_papers = []
    
    for p in all_papers:
        title = p.get("title", "").strip().lower()
        # Direct exact match or if the exact title string is in the list
        if title in titles_to_remove:
            removed_papers.append(p.get("title"))
        else:
            retained_papers.append(p)
            
    after_count = len(retained_papers)
    
    # Update state
    library_state.state["papers"] = retained_papers
    library_state.save_state()
    
    # Run T0 clusters
    new_clusters = _run_t0_clustering()
    
    print("\n=== CURATION RECONCILIATION ===")
    print(f"Before: {before_count}")
    print(f"Removed: {len(removed_papers)}")
    print(f"After: {after_count}")
    
    if removed_papers:
        print("\n[Removed Titles]:")
        for t in removed_papers:
            print(f" - {t}")
            
    print("\n[New T0 Clusters on Clean Library]:")
    print(", ".join(new_clusters))
    
    # We also need to clear source_hashes for these removed papers so they could theoretically be re-ingested if desired?
    # For now, just removing from 'papers' is enough for the user's manual review purge.

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python curate.py <titles_to_remove.txt>")
        sys.exit(1)
    curate_library(sys.argv[1])
