import os
import re
import json

def _normalize_text(text: str) -> str:
    """Normalizes text by converting to lowercase and stripping all punctuation and extra whitespace."""
    if not text:
        return ""
    # Remove punctuation
    text = re.sub(r'[^\w\s]', '', text)
    # Convert to lowercase and normalize whitespace
    return " ".join(text.lower().split())

def is_already_analyzed(paper_title: str, doi: str = None) -> bool:
    """
    Checks if a paper is already in the library.json or library.md database.
    Matches using normalized title or DOI.
    """
    from src.db.library import LibraryDB
    res = LibraryDB().check_status(paper_title)
    if res and res.get("status") == "analyzed":
        return True
        
    # Check MD library (fallback)
    base_dir = os.path.dirname(os.path.dirname(__file__))
    md_path = os.path.join(base_dir, "output", "library.md")
    
    normalized_title = _normalize_text(paper_title)
    if os.path.exists(md_path):
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                md_content = f.read()
            norm_md = _normalize_text(md_content)
            if normalized_title and len(normalized_title) > 20 and normalized_title in norm_md:
                return True
            if doi and _normalize_text(doi) in norm_md:
                return True
        except Exception:
            pass
            
    return False

def trim_paper_input(text: str, max_words: int = 3000) -> str:
    """
    Trims the input text to a maximum number of words.
    Prioritizes Abstract, Methodology, Findings, Discussion, and References if possible.
    Otherwise, grabs the first 1500 words and the last 1500 words.
    """
    if not text:
        return ""
    words = text.split()
    if len(words) <= max_words:
        return text
        
    # If the text is very long, try to find sections
    # A simple fallback for now: take first max_words // 2 and last max_words // 2
    half_words = max_words // 2
    first_part = " ".join(words[:half_words])
    last_part = " ".join(words[-half_words:])
    
    return f"{first_part}\n\n... [CONTENT TRUNCATED FOR API LIMITS] ...\n\n{last_part}"
