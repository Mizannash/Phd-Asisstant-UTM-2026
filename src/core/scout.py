import requests
import time
import json
import os
import hashlib
from src.core.library_state import library_state
from src.core.analyze import analyze_paper

def prefilter_paper(title, abstract):
    # Programmatic keyword score
    keywords = ["ai", "artificial intelligence", "psychomotor", "vocational", "tvet", "construction technology", "malaysia", "kolej vokasional"]
    text = f"{title or ''} {abstract or ''}".lower()
    
    score = 0
    for kw in keywords:
        if kw in text:
            score += 1
            
    # Require at least 2 keywords to be relevant
    return score >= 2, score

def fetch_openalex_papers(query, max_papers=40):
    from src.core.config import get_secret
    email = get_secret("OPENALEX_MAILTO")
    url = f"https://api.openalex.org/works?search={query}&mailto={email}&per-page={max_papers}&sort=publication_year:desc"
    
    papers = []
    print(f"Fetching papers from OpenAlex: {url}")
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        for work in data.get('results', []):
            title = work.get('title')
            abstract_inv = work.get('abstract_inverted_index')
            abstract = ""
            if abstract_inv:
                # reconstruct abstract
                words = {}
                for word, positions in abstract_inv.items():
                    for pos in positions:
                        words[pos] = word
                abstract = " ".join([words[i] for i in sorted(words.keys())])
            
            if not title or not abstract:
                continue
                
            papers.append({
                "title": title,
                "abstract": abstract,
                "doi": work.get('doi'),
                "authors": [a.get('author', {}).get('display_name') for a in work.get('authorships', [])],
                "year": work.get('publication_year')
            })
            time.sleep(0.1) # Throttle OpenAlex slightly
    return papers

def scout_and_ingest(target_count=20):
    # Fix old papers missing schema fields
    for p in library_state.state.get("papers", []):
        if "doi" not in p:
            p["doi"] = None
        if "authors" not in p:
            p["authors"] = []
    library_state.save_state()

    # Query for papers
    query = '("Artificial Intelligence" OR "AI") AND ("TVET" OR "psychomotor" OR "Kolej Vokasional" OR "construction technology")'
    raw_papers = fetch_openalex_papers(query, max_papers=100)
    
    rejected_file = "output/scout_rejected.json"
    rejected_list = []
    if os.path.exists(rejected_file):
        with open(rejected_file, 'r', encoding='utf-8') as f:
            rejected_list = json.load(f)
            
    added_count = 0
    print(f"\nFound {len(raw_papers)} papers from OpenAlex. Pre-filtering...")
    
    # Estimate cost
    total_estimated_tokens = sum([len(p['abstract'])/4 for p in raw_papers])
    print(f"Cost Preview: Estimated {len(raw_papers)} calls on T1, {total_estimated_tokens} estimated tokens.")
    
    for i, p in enumerate(raw_papers):
        if added_count >= target_count:
            print(f"Reached target {target_count} papers. Pausing scout.")
            break
            
        # Safe print for Windows console
        safe_title = p['title'].encode('ascii', 'replace').decode('ascii')
        print(f"Processing {i+1}/{len(raw_papers)}: {safe_title}")
        
        # Check if already in source hashes to support pause/resume
        text_hash = hashlib.sha256((p['title'] + " " + p['abstract']).encode('utf-8')).hexdigest()
        if text_hash in library_state.state.get("source_hashes", {}):
            print(" -> Skipping (already in source_hashes)")
            continue
            
        is_relevant, score = prefilter_paper(p['title'], p['abstract'])
        if not is_relevant:
            reason = f"Keyword score too low: {score}"
            rejected_list.append({"title": p['title'], "reason": reason})
            print(f" -> Rejected: {reason.encode('ascii', 'replace').decode('ascii')}")
            continue
            
        text = f"Title: {p['title']}\nAuthors: {', '.join(p['authors'])}\nYear: {p['year']}\nDOI: {p['doi']}\nAbstract: {p['abstract']}"
        try:
            analyze_paper(text)
            added_count += 1
            print(" -> Successfully ingested.")
        except Exception as e:
            if "duplicate" in str(e).lower():
                print(f" -> Duplicate ignored: {e}")
            else:
                print(f" -> Analysis failed: {e}")
                
    with open(rejected_file, 'w', encoding='utf-8') as f:
        json.dump(rejected_list, f, indent=2)
        
    print(f"Scout complete. Added {added_count} papers.")
    return added_count
