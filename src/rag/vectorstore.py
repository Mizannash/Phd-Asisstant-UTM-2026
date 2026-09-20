import os
import hashlib
import chromadb
from chromadb.utils import embedding_functions
import streamlit as st

MODEL_NAME = "all-MiniLM-L6-v2"
COLLECTION_NAME = "library_chunks"

@st.cache_resource
def get_db_client():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    db_dir = os.path.join(base_dir, "output", "chroma_db")
    os.makedirs(db_dir, exist_ok=True)
    return chromadb.PersistentClient(path=db_dir)

def get_collection():
    client = get_db_client()
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=MODEL_NAME)
    
    # We check if collection exists and has matching metadata
    try:
        collection = client.get_collection(name=COLLECTION_NAME, embedding_function=sentence_transformer_ef)
        metadata = collection.metadata or {}
        if metadata.get("model_name") != MODEL_NAME:
            raise ValueError(f"Embedding model mismatch. Expected {MODEL_NAME}, found {metadata.get('model_name')}. Please rebuild index.")
        return collection
    except ValueError as e:
        if "does not exist" in str(e).lower():
            # Collection doesn't exist, create it
            return client.create_collection(
                name=COLLECTION_NAME, 
                embedding_function=sentence_transformer_ef,
                metadata={"model_name": MODEL_NAME}
            )
        else:
            raise e
            
def _generate_chunk_id(title, chunk_type):
    # deterministic ID based on title hash + type
    hash_str = hashlib.sha256(title.lower().encode("utf-8")).hexdigest()[:16]
    return f"{hash_str}_{chunk_type}"

def index_sync(paper_dict=None):
    """
    Syncs papers to the local ChromaDB vector store.
    If paper_dict is None, syncs all analyzed relevant papers in library.json.
    """
    collection = get_collection()
    
    papers_to_sync = []
    if paper_dict is not None:
        papers_to_sync.append(paper_dict)
    else:
        from src.db.library import LibraryDB
        db = LibraryDB()
        data = db._read()
        papers_to_sync = data.get("papers", [])
        
    ids = []
    documents = []
    metadatas = []
    
    for paper in papers_to_sync:
        if paper.get("status") != "analyzed" or paper.get("verdict") != "RELEVANT":
            continue
            
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")
        content = paper.get("content", "")
        
        # Abstract Chunk
        abs_id = _generate_chunk_id(title, "abstract")
        abs_doc = f"Title: {title}\nAbstract: {abstract}\nVerdict: {paper.get('verdict')}\nScore: {paper.get('score', 'N/A')}"
        abs_meta = {
            "title": title,
            "year": paper.get("year", "N/A"),
            "doi": paper.get("doi", ""),
            "verdict": paper.get("verdict", ""),
            "themes": str(paper.get("themes", "")),
            "wiki_link": paper.get("filename", ""),
            "status": paper.get("status", "")
        }
        
        # Content Chunk
        cont_id = _generate_chunk_id(title, "content")
        cont_doc = f"Title: {title}\nAnalysis Findings:\n{content}"
        cont_meta = abs_meta.copy()
        
        ids.extend([abs_id, cont_id])
        documents.extend([abs_doc, cont_doc])
        metadatas.extend([abs_meta, cont_meta])
        
    if ids:
        collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
    return len(ids)

def rebuild_index():
    client = get_db_client()
    try:
        client.delete_collection(name=COLLECTION_NAME)
    except:
        pass
    index_sync(None)

def search_similar(query_text: str, k: int = 8):
    """
    Searches the collection for similar chunks.
    Returns a list of dict-like objects mimicking Document.
    """
    collection = get_collection()
    results = collection.query(
        query_texts=[query_text],
        n_results=k
    )
    
    # Format to look like langchain documents for the verifier
    class Document:
        def __init__(self, page_content, metadata):
            self.page_content = page_content
            self.metadata = metadata
            
    documents = []
    if results and results.get("documents") and len(results["documents"]) > 0:
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        for i in range(len(docs)):
            documents.append(Document(page_content=docs[i], metadata=metas[i]))
            
    return documents
