import os
import sys
import json
from dotenv import load_dotenv

import io
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Ensure we're in the right directory and load env
sys.path.append(os.path.dirname(__file__))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from pydantic import BaseModel, Field
from typing import List

from src.config import LANGCHAIN_PRIMARY_MODEL

def get_llm():
    from quota_manager import QuotaManager
    # Lazily fetch the active key so LangChain rotation works dynamically
    current_key = QuotaManager.get_current_key()
    from src.quota.budget import LLMCallTracker
    tracker = LLMCallTracker(pipeline_name="chatbot")
    return ChatGoogleGenerativeAI(
        model=LANGCHAIN_PRIMARY_MODEL,
        google_api_key=current_key,
        temperature=0.3,
        callbacks=[tracker]
    )

def get_groq_llm():
    import os
    from langchain_openai import ChatOpenAI
    from src.quota.budget import LLMCallTracker
    tracker = LLMCallTracker(pipeline_name="title_generator")
    groq_key = os.environ.get("GROQ_API_KEY", "")
    return ChatOpenAI(
        model="llama-3.3-70b-versatile",
        api_key=groq_key,
        base_url="https://api.groq.com/openai/v1",
        temperature=0.3,
        callbacks=[tracker]
    )

import yaml

from src.models.prompts import load_supervisor_persona, SUPERVISOR_PERSONA

def format_library_context() -> str:
    """Reads the JSON library and extracts minimal metadata to save tokens using LibraryDB."""
    from src.db.library import LibraryDB
    try:
        db = LibraryDB()
        data = db._read()
        papers = data.get("papers", [])
        if not papers:
            return "Library Database: No papers found in the database yet."
            
        # Format a condensed string
        context_str = f"Library Database contains {len(papers)} papers:\n"
        for i, p in enumerate(papers, 1):
            title = p.get("title", "Unknown")
            year = p.get("year", "Unknown")
            rel = p.get("relevance_score", "N/A")
            context_str += f"{i}. [{year}] {title} (Relevance: {rel})\n"
            
        return context_str
    except Exception as e:
        return f"Library Database Error: Could not read library ({e})"

def extract_text(response_content) -> str:
    """Helper to safely extract text if LangChain returns a list of blocks instead of a string."""
    if isinstance(response_content, list):
        texts = []
        for block in response_content:
            if isinstance(block, dict) and "text" in block:
                texts.append(block["text"])
            elif isinstance(block, str):
                texts.append(block)
        return "".join(texts)
    return str(response_content)

def get_library_summary() -> str:
    from src.db.library import LibraryDB
    try:
        db = LibraryDB()
        data = db._read()
        papers = data.get("papers", [])
        rel = [p for p in papers if p.get("status") == "analyzed" and p.get("verdict") == "RELEVANT"]
        return f"The library currently contains {len(papers)} total papers, with {len(rel)} analyzed as RELEVANT to the research."
    except Exception as e:
        return f"Library Database Error: Could not read library ({e})"

def chat_with_supervisor(user_input: str, chat_history: list = None) -> tuple[str, list[str]]:
    """
    Main entry point for chatting with the AI advisor.
    chat_history should be a list of tuples: [("user", "Hello"), ("ai", "Hi there")]
    Returns a tuple of (response_text, list_of_wiki_link_sources)
    """
    from src.quota.budget import BudgetManager
    bm = BudgetManager()
    dev_state = bm.get_mode()
    provider = "groq" if dev_state.get("dev_mode") else "gemini"
    dev_mock = dev_state.get("dev_mock", False)
    
    if not dev_mock and not bm.can_afford(1, provider=provider):
        return "BUDGET_BLOCKED: Supervisor chat needs 1 API call. Budget exhausted. Enable Developer Mode to test.", []
        
    if chat_history is None:
        chat_history = []
        
    # 1. Local RAG Retrieval
    sources_list = []
    context_str = "<RETRIEVED_CONTEXT>\n"
    try:
        from src.rag.vectorstore import get_collection
        collection = get_collection()
        results = collection.query(query_texts=[user_input], n_results=5)
        retrieved_chunks = results["documents"][0] if results["documents"] else []
        metadatas = results["metadatas"][0] if results["metadatas"] else []
        
        for i, (chunk, m) in enumerate(zip(retrieved_chunks, metadatas)):
            wiki_link = m.get('wiki_link', '')
            if wiki_link:
                sources_list.append(wiki_link)
            context_str += f"Source {i+1} ({wiki_link}):\n{chunk}\n\n"
    except Exception as e:
        context_str += f"Error accessing local vector store: {e}\n"
    context_str += "</RETRIEVED_CONTEXT>\n"
    
    summary = get_library_summary()
    context_str += f"<LIBRARY_SUMMARY>\n{summary}\n</LIBRARY_SUMMARY>\n"
    
    # 2. Load the dynamic research context
    import state_manager
    research_ctx = state_manager.load_research_context()
    ctx_str = f"""
<RESEARCH_CONTEXT>
Sample Scope: {research_ctx.get('sample_scope', 'Not defined')}
States/Zones Covered: {research_ctx.get('states_zones', 'Not defined')}
Study Duration: {research_ctx.get('study_duration', 'Not defined')}
Methodology Leanings: {research_ctx.get('methodology', 'Not defined')}
Target (e.g. Fast-track): {research_ctx.get('target', 'Not defined')}
Current Stage: {research_ctx.get('current_stage', 'Not defined')}
</RESEARCH_CONTEXT>
"""
    
    # 3. Compile the advanced behavioral instructions
    advanced_instructions = """
**BEHAVIORAL DIRECTIVES:**

1. **BAHASA SUPPORT**: You must reply in the language of the user's last message. If they ask in Bahasa Melayu, answer in Bahasa Melayu. However, you MUST preserve English academic terminology exactly.

2. **FAST-TRACK PHD MENTOR MODE**: You are a roadmap mentor. Give concrete, sequential "do this now" advice. At the very end of EVERY substantive reply, add a short section titled exactly "📌 Langkah Seterusnya (Next Steps):" followed by 1) ... 2) ... 3) ... with realistic timeframes.

3. **EVALUATION & ADVICE**: If the user proposes a thesis title, methodology, or asks for general academic advice, you should act as an exacting PhD supervisor. Critique their ideas, suggest improvements, and leverage your general academic knowledge. 

4. **LITERATURE GROUNDING**: When the user specifically asks about the literature, previous studies, or gaps, you MUST base your answer on the retrieved library context and cite it (e.g. 'According to Source 1...'). If the context doesn't have the specific literature they are asking about, you can suggest what kind of literature they should look for, but do not hallucinate citations.

5. **DEBATE MODE & CONTEXT UPDATES**: If the user proposes a design change (like expanding the sample), you must propose an update to the Research Context Registry by outputting a JSON block EXACTLY in this format:
```json
{{
  "proposed_research_context": {{
    "sample_scope": "updated value",
    "states_zones": "updated value"
  }}
}}
```
Only include the fields that are changing. Do not output this JSON unless a change is actually being proposed or finalized.
"""

    # 4. Build the prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", SUPERVISOR_PERSONA + "\n\n" + ctx_str + "\n" + advanced_instructions + "\n\n{library_context}"),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{user_input}")
    ])
    
    # 3. Format history for LangChain
    formatted_history = []
    for role, text in chat_history:
        if role == "user":
            formatted_history.append(HumanMessage(content=text))
        elif role == "ai":
            formatted_history.append(AIMessage(content=text))
            
    # 4. Execute Chain with lazy LLM instantiation for key rotation
    from quota_manager import QuotaManager
    from src.utils.llm_safety import safe_llm_call
    
    if dev_mock:
        response_text = "MOCK SUPERVISOR REPLY. The retrieved library context does not contain information to support this."
    else:
        def do_call():
            response = QuotaManager.execute_call(
                lambda kwargs: (prompt | get_llm()).invoke(kwargs), 
                {
                    "library_context": context_str,
                    "history": formatted_history,
                    "user_input": user_input
                }
            )
            return extract_text(response.content)
            
        response_text = safe_llm_call(do_call)
        
        if response_text is None:
            return "The AI service returned an empty response (possibly rate limiting). Please try again in a moment.", []
    
    # The structural refusal guard has been removed to allow the LLM to give advice on titles even if they aren't in the library.

    return response_text, list(set(sources_list))

class Title(BaseModel):
    title: str = Field(description="The proposed thesis title")
    novelty_score: float = Field(description="Novelty score from 1.0 to 10.0")
    justification: str = Field(description="Why this title is a good gap to fill")
    source_gap_ids: List[str] = Field(description="List of source gap IDs that this title addresses", default_factory=list)
    citations: List[str] = Field(description="List of supporting paper citations for this title", default_factory=list)

class TitleLeaderboard(BaseModel):
    titles: List[Title] = Field(description="List of exactly 3 generated titles")

def generate_dynamic_titles() -> dict:
    """Uses Structured Outputs to generate a strictly formatted list of titles based on library context."""
    library_context = format_library_context()
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", SUPERVISOR_PERSONA + "\n\nAnalyze the following literature database and suggest exactly 3 highly novel thesis titles filling the gaps. Provide a novelty score (1-10) and a brief justification for each.\n\n{library_context}"),
        ("human", "Generate the title leaderboard.")
    ])
    
    # Use with_structured_output to force Pydantic schema
    from src.utils.llm_safety import safe_llm_call
    
    def do_call():
        response = (prompt | get_groq_llm().with_structured_output(TitleLeaderboard)).invoke({"library_context": library_context})
        if hasattr(response, 'dict'):
            return response.dict()
        elif hasattr(response, 'model_dump'):
            return response.model_dump()
        return None
        
    result = safe_llm_call(do_call, max_retries=1) # Limit to max 2 calls (1 initial + 1 retry)
    return result if result else {"titles": []}

import re
from enum import Enum

class CitationsList(BaseModel):
    citations: List[str] = Field(description="A list of full APA or standard academic references found in the text.")

def generate_lit_review() -> str:
    """Generates a Chapter 2 draft using the library."""
    from src.db.library import LibraryDB
    try:
        db = LibraryDB()
        data = db._read()
        papers = data.get("papers", [])
    except Exception:
        papers = []
        
    if not papers:
        return "Library is empty. Cannot generate review."
        
    context = "Here are the papers to synthesize for Chapter 2:\n\n"
    for p in papers:
        context += f"- **{p.get('title', 'Unknown')}** ({p.get('year', 'N/A')}): {p.get('abstract', 'No abstract')}\n"
        
    prompt = ChatPromptTemplate.from_messages([
        ("system", SUPERVISOR_PERSONA + "\n\nYou are an expert academic writer. Synthesize the provided literature into a cohesive Chapter 2: Literature Review draft in APA 7th style. Identify themes, gaps, and methodological trends. DO NOT HALLUCINATE CITATIONS. Only cite the provided papers."),
        ("human", "{context}")
    ])
    
    from quota_manager import QuotaManager
    from src.utils.llm_safety import safe_llm_call
    
    def do_call():
        response = QuotaManager.execute_call(
            lambda kwargs: (prompt | get_llm()).invoke(kwargs),
            {"context": context}
        )
        return extract_text(response.content)
        
    draft_text = safe_llm_call(do_call)
    if not draft_text:
        return "The AI service returned an empty response (possibly rate limiting). Please try again in a moment."

    # Auto-Verification Layer
    try:
        # Extract citations
        ext_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an AI assistant. Extract a list of all unique academic in-text citations (e.g. '(Smith, 2020)') from the provided text. Return ONLY the JSON list."),
            ("human", "{draft}")
        ])
        
        def ext_call():
            return QuotaManager.execute_call(
                lambda kwargs: (ext_prompt | get_llm().with_structured_output(CitationsList)).invoke(kwargs), 
                {"draft": draft_text}
            )
            
        ext_response = safe_llm_call(ext_call)
        
        if ext_response:
            # Verify and replace
            sys.path.append(os.path.dirname(__file__))
            from tools.verifier import CitationVerifier
            
            for citation in ext_response.citations:
                # Clean up parenthesis for search
                clean_query = re.sub(r'[\(\)]', '', citation)
                if not clean_query.strip(): continue
                
                result = CitationVerifier.verify_paper(clean_query)
                if not result.get("verified"):
                    # Replace in draft
                    draft_text = draft_text.replace(citation, f"{citation} [UNVERIFIED - CHECK MANUALLY]")
                
    except Exception as e:
        print(f"Citation verification step failed: {e}")

    return draft_text

class VerdictEnum(str, Enum):
    PRIMARY = "✅ Layak sebagai perbandingan utama"
    SECONDARY = "🟡 Layak sebagai sokongan/secondary reference sahaja"
    REJECT = "❌ Tidak sesuai untuk perbandingan"

class PaperAssessment(BaseModel):
    verdict: VerdictEnum = Field(description="The final verdict on comparability.")
    advice: str = Field(description="Concrete advice on how to use it (benchmark findings / justify gap / position methodology) and how to cite its role in Bab 2, including reasons for the verdict.")

def assess_paper_for_comparison(paper_title: str, paper_abstract: str, paper_year: str) -> dict:
    """Evaluates a paper against the research context for suitability as a comparison study."""
    import state_manager
    research_ctx = state_manager.load_research_context()
    ctx_str = f"""
<RESEARCH_CONTEXT>
Sample Scope: {research_ctx.get('sample_scope', 'Not defined')}
States/Zones Covered: {research_ctx.get('states_zones', 'Not defined')}
Study Duration: {research_ctx.get('study_duration', 'Not defined')}
Methodology Leanings: {research_ctx.get('methodology', 'Not defined')}
Target (e.g. Fast-track): {research_ctx.get('target', 'Not defined')}
Current Stage: {research_ctx.get('current_stage', 'Not defined')}
</RESEARCH_CONTEXT>
"""
    
    instructions = f"""
You are the Exacting PhD Co-Supervisor evaluating a discovered paper against the student's RESEARCH CONTEXT to see if it can be used as a COMPARISON STUDY in the thesis.

{ctx_str}

Evaluate the following paper on:
1. Context fit: Malaysia? Kolej Vokasional? Or international/other-institution?
2. Population & sample alignment with the student's study.
3. Variable/focus alignment (e.g., AI in learning/TVET pedagogy).
4. Methodological comparability and quality.

CRITICAL SCOPE RULE: Papers from Politeknik/ILP/IPT or international contexts can be 🟡 supporting references at most, NEVER ✅ primary comparison without explicit scope-change justification. Only highly aligned KV Malaysia studies can be ✅.

Provide a Verdict and detailed Advice in Bahasa Melayu or English (based on the abstract language).
"""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", instructions),
        ("human", f"Paper Title: {paper_title}\nYear: {paper_year}\nAbstract/Summary: {paper_abstract}")
    ])
    
    from quota_manager import QuotaManager
    from src.utils.llm_safety import safe_llm_call
    
    def do_call():
        response = QuotaManager.execute_call(
            lambda kwargs: (prompt | get_llm().with_structured_output(PaperAssessment)).invoke(kwargs),
            {}
        )
        if hasattr(response, 'dict'):
            return response.dict()
        elif hasattr(response, 'model_dump'):
            return response.model_dump()
        return None
        
    try:
        result = safe_llm_call(do_call)
        if result:
            return result
        else:
            return {"verdict": VerdictEnum.REJECT.value, "advice": "Error: Empty response from LLM."}
    except Exception as e:
        return {"verdict": VerdictEnum.REJECT.value, "advice": f"Assessment Failed: {e}"}


if __name__ == "__main__":
    print("🎓 AI PhD Co-Supervisor Initialized. Type 'exit' to quit.\n")
    
    history = []
    while True:
        user_text = input("You: ")
        if user_text.lower() == 'exit':
            break
            
        print("Supervisor is typing...")
        try:
            response_text = chat_with_supervisor(user_text, history)
            print(f"\nSupervisor: {response_text}\n")
            
            # Append to history
            history.append(("user", user_text))
            history.append(("ai", response_text))
        except Exception as e:
            print(f"\nError connecting to supervisor: {e}\n")
