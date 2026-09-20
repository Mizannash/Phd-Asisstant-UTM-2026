import pytest
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from src.rag.vectorstore import index_sync, get_collection, get_db_client, COLLECTION_NAME

def test_sync_correctness():
    client = get_db_client()
    try:
        client.delete_collection(name=COLLECTION_NAME)
    except:
        pass
        
    papers = [
        {
            "title": "Relevant Paper 1",
            "abstract": "This is a great paper.",
            "content": "Found XYZ.",
            "verdict": "RELEVANT",
            "status": "analyzed",
            "filename": "Paper_1.md"
        },
        {
            "title": "Scouted Paper",
            "abstract": "Scouted only.",
            "verdict": "UNKNOWN",
            "status": "scouted",
            "filename": "Paper_2.md"
        },
        {
            "title": "Rejected Paper",
            "abstract": "Irrelevant.",
            "content": "Found nothing.",
            "verdict": "REJECTED",
            "status": "analyzed",
            "filename": "Paper_3.md"
        }
    ]
    
    # Sync each
    for p in papers:
        index_sync(p)
        
    collection = get_collection()
    count = collection.count()
    # Only "Relevant Paper 1" should be embedded (2 chunks)
    assert count == 2

def test_retrieval_relevance():
    client = get_db_client()
    try:
        client.delete_collection(name=COLLECTION_NAME)
    except:
        pass
        
    p = {
        "title": "Unique Keyword Paper",
        "abstract": "Supercalifragilisticexpialidocious.",
        "content": "The quick brown fox jumps over the lazy dog.",
        "verdict": "RELEVANT",
        "status": "analyzed",
        "filename": "Paper_Unique.md"
    }
    index_sync(p)
    
    collection = get_collection()
    results = collection.query(query_texts=["brown fox"], n_results=1)
    
    assert results["documents"]
    assert len(results["documents"][0]) == 1
    # It should match the content chunk
    assert "brown fox" in results["documents"][0][0]
    assert results["metadatas"][0][0]["wiki_link"] == "Paper_Unique.md"

def test_no_prompt_bloat():
    # Simulate a large library query by seeing how many chunks we get
    # We requested n_results=5 in chatbot.py
    # So max chunks is 5.
    
    client = get_db_client()
    try:
        client.delete_collection(name=COLLECTION_NAME)
    except:
        pass
        
    # Index 10 papers
    for i in range(10):
        index_sync({
            "title": f"Paper {i}",
            "abstract": "Abstract " * 20,
            "content": "Content " * 50,
            "verdict": "RELEVANT",
            "status": "analyzed",
            "filename": f"Paper_{i}.md"
        })
        
    collection = get_collection()
    results = collection.query(query_texts=["Content"], n_results=5)
    
    # We should get exactly 5 chunks back, preventing prompt bloat
    assert len(results["documents"][0]) == 5
