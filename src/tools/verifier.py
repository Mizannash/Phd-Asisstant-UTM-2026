import os
import requests
import urllib.parse
from typing import Dict, Any

class CitationVerifier:
    @classmethod
    def verify_paper(cls, title: str) -> Dict[str, Any]:
        """
        Verify if a paper exists in the OpenAlex database by title.
        """
        from src.core.config import get_secret
        mailto = get_secret("OPENALEX_MAILTO")
        headers = {}
        if mailto:
            headers["User-Agent"] = f"mailto:{mailto}"
            
        encoded_title = urllib.parse.quote(title)
        url = f"https://api.openalex.org/works?filter=title.search:{encoded_title}"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("meta", {}).get("count", 0) > 0 and data.get("results"):
                # Take the top match
                best_match = data["results"][0]
                return {
                    "verified": True,
                    "title": best_match.get("title"),
                    "doi": best_match.get("doi"),
                    "year": best_match.get("publication_year"),
                    "cited_by_count": best_match.get("cited_by_count", 0),
                    "source": "OpenAlex"
                }
            
            return {"verified": False}
        except Exception as e:
            print(f"Error querying OpenAlex API: {e}")
            return {"verified": False, "error": str(e)}
