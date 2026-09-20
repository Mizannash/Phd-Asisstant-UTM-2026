import os
import requests
import urllib.parse
from crewai.tools import tool

def fetch_openalex(query: str, limit: int = 5) -> list[dict]:
    """
    Core function to fetch and parse OpenAlex results natively.
    Returns a list of dictionaries with raw data.
    """
    from src.core.config import get_secret
    mailto = get_secret("OPENALEX_MAILTO")
    headers = {}
    if mailto:
        headers["User-Agent"] = f"mailto:{mailto}"
        
    encoded_query = urllib.parse.quote(query)
    url = f"https://api.openalex.org/works?search={encoded_query}&per-page={limit}"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", [])
        parsed_results = []
        for work in results:
            title = work.get("title") or "Unknown Title"
            year = work.get("publication_year") or "Unknown Year"
            doi = work.get("doi") or "No DOI"
            
            # Abstract logic: OpenAlex returns abstract_inverted_index
            abstract_inverted = work.get("abstract_inverted_index")
            abstract = ""
            if abstract_inverted:
                # Reconstruct abstract
                words = max(max(positions) for positions in abstract_inverted.values()) + 1
                abstract_arr = [""] * words
                for word, positions in abstract_inverted.items():
                    for pos in positions:
                        if pos < words:
                            abstract_arr[pos] = word
                abstract = " ".join(abstract_arr)
                
            authorships = work.get("authorships", [])
            author_names = [a.get("author", {}).get("display_name", "") for a in authorships if a.get("author")]
            institutions = []
            for a in authorships:
                for inst in a.get("institutions", []):
                    institutions.append(inst.get("display_name", ""))
            
            parsed_results.append({
                "title": title,
                "year": year,
                "doi": doi,
                "authors": ", ".join(author_names) if author_names else "Unknown Authors",
                "institutions": ", ".join(institutions) if institutions else "Unknown Institutions",
                "abstract": abstract
            })
            
        return parsed_results
    except Exception as e:
        print(f"Error fetching OpenAlex: {e}")
        return []

@tool("OpenAlex Search Tool")
def openalex_search_tool(query: str, limit: int = 5) -> str:
    """
    Search the OpenAlex database for academic papers using a query string.
    Returns a formatted markdown string of academic references including Title, Authors, Year, and DOI.
    """
    results = fetch_openalex(query, limit)
    if not results:
        return f"No results found for query: '{query}'"
        
    formatted = [f"### Search Results for '{query}'\n"]
    for idx, w in enumerate(results, 1):
        formatted.append(f"{idx}. **{w['title']}**\n   - **Authors:** {w['authors']}\n   - **Year:** {w['year']}\n   - **DOI:** {w['doi']}\n")
        
    return "\n".join(formatted)
