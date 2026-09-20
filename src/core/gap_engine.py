import json
from collections import Counter
import re
from src.core.llm_factory import get_llm_response
from src.core.library_state import library_state

# Simple stop words for basic NLP
STOP_WORDS = set([
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "in", "on", "at", "to", "for", 
    "with", "by", "about", "as", "of", "this", "that", "it", "which", "study", "research", "paper",
    "results", "findings", "methodology", "data", "analysis", "based", "using", "from", "their", "these"
])

def _tokenize(text):
    if not text:
        return []
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    return [w for w in words if w not in STOP_WORDS]

def _run_t0_clustering():
    """T0 Clustering: Extract top keywords from all papers' abstract/findings/topics."""
    all_words = []
    for paper in library_state.state.get("papers", []):
        all_words.extend(_tokenize(paper.get("abstract", "")))
        all_words.extend(_tokenize(paper.get("findings", "")))
        for topic in paper.get("topics", []):
            all_words.extend(_tokenize(topic))
            
    word_counts = Counter(all_words)
    # Get top 20 keywords as "clusters"
    clusters = [word for word, count in word_counts.most_common(20)]
    return clusters

def run_gap_engine_t0_t1():
    """Runs T0 Clustering and T1 Synthesis to propose candidate gaps."""
    clusters = _run_t0_clustering()
    threats = library_state.state.get("threats", [])
    
    threats_text = "\n".join([f"- {t['date']}: {t['text']}" for t in threats])
    clusters_text = ", ".join(clusters)
    
    papers_context = []
    for p in library_state.state.get("papers", []):
        p_id = p.get("id") or p.get("title")
        abs_t = p.get('abstract', '')
        fin_t = p.get('findings', '')
        if len(abs_t) > 300: abs_t = abs_t[:300] + "..."
        if len(fin_t) > 300: fin_t = fin_t[:300] + "..."
        papers_context.append(f"ID: {p_id} | Title: {p.get('title')} | Text: {abs_t} {fin_t}")
    papers_text = "\n".join(papers_context)
    
    prompt = f"""You are a senior academic researcher. 
    Based on the following extracted topic clusters from our current library:
    {clusters_text}
    
    And the following novelty threats (which we must avoid or pivot from):
    {threats_text}
    
    And the following library papers:
    {papers_text}
    
    Synthesize 3-5 high-quality candidate research gaps. 
    CRITICAL: You must propose gaps ONLY grounded in the provided library papers.
    Attach candidate supporting paper IDs to each gap.
    If the provided papers cannot provide at least 2 supporting papers for a gap, mark the gap status as 'LOW_EVIDENCE' (otherwise 'CANDIDATE').
    
    Format your output strictly as a JSON array of objects with keys:
    - statement (string)
    - rationale (string)
    - supporting_paper_ids (list of strings)
    - status (string, 'CANDIDATE' or 'LOW_EVIDENCE')
    
    ONLY output valid JSON array.
    """
    
    messages = [
        {"role": "system", "content": "You are a gap synthesis engine. Output JSON only."},
        {"role": "user", "content": prompt}
    ]
    
    raw_resp = get_llm_response(messages, tier="T1", pipeline="gap_engine_t1")
    
    try:
        import re
        # Extract each JSON object individually since the output may be truncated
        objects = re.findall(r'\{[^{}]*\"status\"[^{}]*\}', raw_resp, re.DOTALL)
        candidate_gaps = []
        for obj in objects:
            try:
                candidate_gaps.append(json.loads(obj))
            except json.JSONDecodeError:
                pass
    except Exception as e:
        candidate_gaps = []
        
    if not candidate_gaps:
        print(f"DEBUG T1 output: {raw_resp}".encode('ascii', 'replace').decode('ascii'))
            
    return {
        "clusters": clusters,
        "candidate_gaps": candidate_gaps
    }

def run_gap_engine_t2_verification(candidate_gaps, confirm_expensive=False):
    """Runs T2 Verification on candidate gaps. Requires confirm_expensive=True."""
    
    papers_context = []
    for p in library_state.state.get("papers", []):
        p_id = p.get("id") or p.get("title") # fallback to title if ID missing (migration papers)
        abs_t = p.get('abstract', '')
        if abs_t and len(abs_t) > 300: abs_t = abs_t[:300] + "..."
        papers_context.append(f"ID: {p_id} | Title: {p.get('title')} | Abstract: {abs_t}")
        
    papers_text = "\n\n".join(papers_context)
    
    verified_gaps = []
    rejected_gaps = []
    
    for gap in candidate_gaps:
        prompt = f"""We are verifying a proposed research gap against our library.
        Gap Statement: {gap.get('statement')}
        Rationale: {gap.get('rationale')}
        
        Library Papers:
        {papers_text}
        
        Does this gap genuinely exist in the library, and is it supported/motivated by at least 2 papers?
        If yes, provide the supporting paper IDs and a 1-sentence evidence for each.
        Format your output strictly as JSON:
        {{
            "is_valid": true/false,
            "rejection_reason": "if false, why",
            "supporting_evidence": [
                {{"paper_id": "ID here", "evidence": "1 sentence here"}}
            ]
        }}
        """
        
        messages = [{"role": "system", "content": "You are a gap verification engine. Output JSON only."}, {"role": "user", "content": prompt}]
        
        # This will raise ValueError if confirm_expensive is False
        raw_resp = get_llm_response(messages, tier="T2", pipeline="gap_engine_t2", confirm_expensive=confirm_expensive)
        
        try:
            clean_resp = raw_resp.strip()
            if clean_resp.startswith("```json"): clean_resp = clean_resp[7:]
            if clean_resp.endswith("```"): clean_resp = clean_resp[:-3]
            verification = json.loads(clean_resp)
        except json.JSONDecodeError:
            verification = {"is_valid": False, "rejection_reason": "Failed to parse T2 response"}
            
        # Programmatic Enforcement: >= 2 papers
        evidence_list = verification.get("supporting_evidence", [])
        
        unique_titles = set()
        for ev in evidence_list:
            p_id = ev.get("paper_id")
            title = "unknown"
            for p in library_state.state.get("papers", []):
                if str(p.get("id")) == str(p_id) or p.get("title") == p_id:
                    title = p.get("title", "unknown")
                    break
            if title != "unknown" and title:
                unique_titles.add(title.strip().lower())
                
        if verification.get("is_valid") and len(unique_titles) >= 2:
            gap["evidence"] = evidence_list
            gap["status"] = "verified"
            verified_gaps.append(gap)
        else:
            gap["status"] = "rejected"
            if len(unique_titles) < 2 and verification.get("is_valid"):
                gap["rejection_reason"] = f"Programmatic rejection: Only {len(unique_titles)} distinct supporting papers found (requires >= 2). Note: original evidence returned {len(evidence_list)} items but they mapped to the same paper(s)."
            else:
                gap["rejection_reason"] = verification.get("rejection_reason", "Insufficient evidence.")
            rejected_gaps.append(gap)
            
        import time
        print(f"Verified gap. Sleeping 65s for Groq TPM limit before next gap...")
        time.sleep(65)
            
    # Update state
    library_state.state.setdefault("gaps", []).extend(verified_gaps)
    library_state.state.setdefault("rejected_candidates", []).extend(rejected_gaps)
    library_state.save_state()
    
    return {
        "verified_gaps": verified_gaps,
        "rejected_gaps": rejected_gaps
    }
