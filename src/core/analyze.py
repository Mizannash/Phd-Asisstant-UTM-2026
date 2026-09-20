import json
import uuid
import hashlib
import string
from datetime import datetime
from src.core.llm_factory import get_llm_response, cache
from src.core.library_state import library_state

def estimate_cost(text: str) -> dict:
    """Estimates the cost of analyzing a paper."""
    estimated_tokens = len(text) // 4
    
    # We create a dummy prompt just to check the cache hash
    messages = [
        {"role": "system", "content": "You are a research paper analyzer. Extract the following fields in JSON format: title, authors, year, DOI, summary, methodology, findings, topics covered, population, Malaysian context y/n, psychomotor/TVET signals."},
        {"role": "user", "content": f"Analyze this paper:\n\n{text}"}
    ]
    model_name = "groq/openai/gpt-oss-120b"
    is_cached = cache.get(model_name, messages) is not None
    
    return {
        "estimated_tokens": estimated_tokens,
        "is_cached": is_cached,
        "model": model_name
    }

def analyze_paper(text: str) -> dict:
    text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
    hashes = library_state.state.get("source_hashes", {})
    if text_hash in hashes:
        raise ValueError(f"duplicate: already analyzed as {hashes[text_hash]}")
        
    messages = [
        {"role": "system", "content": "You are a research paper analyzer. Extract the following fields in JSON format: title (string), authors (list of strings), year (int), DOI (string or null), summary (string), methodology (string), findings (string), topics_covered (list of strings), population (string), malaysian_context (boolean), psychomotor_tvet_signals (string). ONLY OUTPUT VALID JSON."},
        {"role": "user", "content": f"Analyze this paper:\n\n{text}"}
    ]
    
    # Litellm supports standard structured output with json format, but to be robust against raw models, 
    # we just instruct JSON and parse it.
    raw_resp = get_llm_response(messages, tier="T1", pipeline="analyze_paper")
    
    try:
        # Strip potential markdown fences
        clean_resp = raw_resp.strip()
        if clean_resp.startswith("```json"):
            clean_resp = clean_resp[7:]
        if clean_resp.endswith("```"):
            clean_resp = clean_resp[:-3]
            
        data = json.loads(clean_resp)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {e}\nRaw: {raw_resp}")
        
    # Near-dup guard
    new_doi = data.get("DOI")
    new_title = data.get("title", "Unknown")
    
    def normalize_title(t):
        if not t: return ""
        # first 60 chars stripped of punctuation
        t = t[:60].lower()
        return t.translate(str.maketrans('', '', string.punctuation)).strip()

    norm_new_title = normalize_title(new_title)
    
    for existing in library_state.state.get("papers", []):
        if new_doi and existing.get("doi") == new_doi:
            raise ValueError(f"duplicate: DOI {new_doi} already exists in library")
        if norm_new_title and normalize_title(existing.get("title")) == norm_new_title:
            raise ValueError(f"duplicate: Title fuzzy matches existing paper '{existing.get('title')}'")
        if new_title.strip().lower() == existing.get("title", "").strip().lower():
            raise ValueError(f"duplicate: Title exact matches existing paper '{existing.get('title')}'")

    # Append to library state
    paper_entry = {
        "id": str(uuid.uuid4()),
        "title": new_title,
        "authors": data.get("authors", []),
        "year": data.get("year", None),
        "doi": new_doi,
        "abstract": data.get("summary", ""),
        "methodology": data.get("methodology", ""),
        "findings": data.get("findings", ""),
        "topics": data.get("topics_covered", []),
        "population": data.get("population", ""),
        "malaysian_context": data.get("malaysian_context", False),
        "psychomotor_tvet_signals": data.get("psychomotor_tvet_signals", ""),
        "analyzed_at": datetime.now().isoformat()
    }
    
    library_state.state.setdefault("papers", []).append(paper_entry)
    library_state.state.setdefault("titles", []).append(paper_entry["title"])
    library_state.state.setdefault("source_hashes", {})[text_hash] = paper_entry["id"]
    library_state.save_state()
    
    return paper_entry
