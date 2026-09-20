import os
import difflib
import numpy as np
import datetime
from logger import log_event

# Global model initialization (loaded on first use)
_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        # Load a small, fast model explicitly on CPU
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
    return _embedding_model

def load_candidate_titles():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    titles_file = os.path.join(base_dir, "config", "candidate_titles.md")
    titles = []
    if os.path.exists(titles_file):
        with open(titles_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if line[0].isdigit() and ". " in line:
                        line = line.split(". ", 1)[1]
                    titles.append(line)
    return titles

def get_candidate_embeddings(candidates):
    base_dir = os.path.dirname(os.path.dirname(__file__))
    cache_file = os.path.join(base_dir, "config", "candidate_embeddings.npz")
    
    # Check if cache exists and matches current candidates
    if os.path.exists(cache_file):
        data = np.load(cache_file)
        cached_titles = data['titles']
        if list(cached_titles) == candidates:
            return data['embeddings']
            
    # Compute embeddings if cache miss
    model = get_embedding_model()
    embeddings = model.encode(candidates, convert_to_numpy=True)
    
    # Save cache
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    np.savez(cache_file, titles=candidates, embeddings=embeddings)
    return embeddings

def cosine_similarity(v1, v2):
    dot_product = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0: return 0.0
    return dot_product / (norm1 * norm2)

def generate_threat_explanation(paper_title, paper_abstract, candidate_title):
    try:
        import sys
        sys.path.append(os.path.dirname(__file__))
        from quota_manager import QuotaManager
        from langchain_google_genai import ChatGoogleGenerativeAI
        import time
        
        # Use existing API key if available
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return "No API key available to generate explanation."
        from config import LANGCHAIN_PRIMARY_MODEL
        llm = ChatGoogleGenerativeAI(model=LANGCHAIN_PRIMARY_MODEL, google_api_key=os.getenv("GEMINI_API_KEY"))
        prompt = f"""
        Candidate Thesis Title: {candidate_title}
        
        New Paper Title: {paper_title}
        New Paper Abstract: {paper_abstract}
        
        In 2-3 sentences, what exactly overlaps between this new paper and the candidate thesis title — population, topic, or method? Is the research gap threatened?
        """
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                QuotaManager.record_call()
                res = llm.invoke(prompt)
                return res.content.strip()
            except Exception as e:
                action = QuotaManager.handle_error(e)
                if action == "ROTATED_KEY":
                    llm = ChatGoogleGenerativeAI(model=LANGCHAIN_PRIMARY_MODEL, google_api_key=os.getenv("GEMINI_API_KEY"))
                    continue
                time.sleep(5)
        return "Explanation failed due to API limits."
    except Exception as e:
        return f"Error generating explanation: {e}"

def check_novelty_threat(paper_title: str, paper_abstract: str, relevance_score: float, year: int) -> dict:
    """
    Checks if a highly relevant recent paper threatens the candidate titles.
    Uses Semantic Similarity (SentenceTransformers) + LLM Explanation.
    Returns {"threat": bool, "level": "RED"|"YELLOW", "title": candidate_title, "similarity": float, "paper": paper_title, "explanation": str}
    """
    try:
        score = float(relevance_score)
    except:
        score = 0.0

    try:
        yr = int(year)
    except:
        yr = 0

    if score >= 8.0 and 2020 <= yr <= 2026:
        candidates = load_candidate_titles()
        if not candidates:
            return {"threat": False}
            
        paper_text = (paper_title + " " + paper_abstract).lower()
        
        # 1. Cheap pre-filter (String match)
        highest_word_overlap = 0.0
        for candidate in candidates:
            cand_lower = candidate.lower()
            cand_words = set(cand_lower.split())
            paper_words = set(paper_text.split())
            if not cand_words: continue
            overlap = len(cand_words.intersection(paper_words)) / len(cand_words)
            if overlap > highest_word_overlap:
                highest_word_overlap = overlap
        
        # Compute Semantic Similarity
        try:
            cand_embeddings = get_candidate_embeddings(candidates)
            model = get_embedding_model()
            paper_emb = model.encode(paper_title + " " + paper_abstract, convert_to_numpy=True)
            
            highest_sim = 0.0
            threatened_title = ""
            for i, cand_emb in enumerate(cand_embeddings):
                sim = cosine_similarity(paper_emb, cand_emb)
                if sim > highest_sim:
                    highest_sim = sim
                    threatened_title = candidates[i]
        except Exception as e:
            highest_sim = highest_word_overlap
            threatened_title = "Unknown (ML Error)"
            
        # Scale the semantic similarity for display (MiniLM outputs 0.4-0.6 for strong matches)
        # This aligns it with the user's requested 0.75-0.85 threshold logic
        adjusted_sim = highest_sim * 1.75
        
        # Cheap Pre-filter exit
        if highest_word_overlap < 0.10 and adjusted_sim < 0.5:
            return {"threat": False}
            
        # Threat detected
        if adjusted_sim >= 0.75:
            level = "RED" if adjusted_sim >= 0.85 else "YELLOW"
            explanation = generate_threat_explanation(paper_title, paper_abstract, threatened_title)
            
            log_event(f"NOVELTY_THREAT_{level}", f"Paper '{paper_title}' has {adjusted_sim*100:.0f}% semantic overlap with '{threatened_title}'.")
            
            # Log to threat_log.md
            threat_log = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "threat_log.md")
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                os.makedirs(os.path.dirname(threat_log), exist_ok=True)
                with open(threat_log, "a", encoding="utf-8") as f:
                    icon = "🚨" if level == "RED" else "⚠️"
                    f.write(f"- **[{timestamp}]** {icon} NOVELTY THREAT ({level}): {paper_title}\n")
                    f.write(f"  - **Threatens:** {threatened_title} (Similarity: {adjusted_sim*100:.0f}%)\n")
                    f.write(f"  - **AI Analysis:** {explanation}\n\n")
            except:
                pass
                
            return {
                "threat": True, 
                "level": level, 
                "title": threatened_title, 
                "similarity": adjusted_sim, 
                "paper": paper_title,
                "explanation": explanation
            }
            
    return {"threat": False}
