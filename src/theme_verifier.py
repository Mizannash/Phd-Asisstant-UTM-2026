import os
import json
import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.quota.budget import BudgetManager
from src.quota_manager import QuotaManager
from src.rag.vectorstore import search_similar
from src.models.schemas import validate_theme_report, ThemeReport
from src.models.prompts import SUPERVISOR_PERSONA
from src.config import LANGCHAIN_PRIMARY_MODEL

def verify_theme(theme_name: str, theme_description: str) -> str:
    """
    Verifies a literature theme strictly against the RAG database.
    Returns the markdown report.
    """
    # 1. Budget Check
    bm = BudgetManager()
    dev_state = bm.get_mode()
    provider = "groq" if dev_state.get("dev_mode") else "gemini"
    dev_mock = dev_state.get("dev_mock", False)
    
    # We estimate 1 call for a single pass
    if not dev_mock and not bm.can_afford(1, provider=provider):
        return f"BUDGET_BLOCKED: Budget exhausted for {provider}."
        
    # 2. Retrieve Context
    chunks = search_similar(theme_description, k=8)
    
    # 3. Insufficient Library Guard
    if len(chunks) < 3:
        return _format_markdown_report(
            theme_name,
            ThemeReport(
                verdict="UNSUPPORTED",
                supporting_claims=[],
                unverified_claims=["The entire theme needs more literature."],
                suggested_queries=[theme_description]
            ),
            is_insufficient=True
        )
        
    allowed_wiki_links = []
    context_text = "RETRIEVED LIBRARY CONTEXT:\n\n"
    for idx, c in enumerate(chunks, 1):
        wiki_link = c.metadata.get("wiki_link", "")
        if wiki_link:
            allowed_wiki_links.append(wiki_link)
        title = c.metadata.get("title", "")
        content = c.page_content
        context_text += f"--- Source {idx} ---\nTitle: {title}\nWiki-Link: {wiki_link}\nContent:\n{content}\n\n"
        
    # 4. Construct Prompt
    system_prompt = f"""{SUPERVISOR_PERSONA}

You are acting as a strict Literature Map Verifier for Chapter 2.
Your task is to verify the researcher's thematic claim strictly against the provided retrieved context.

STRICT DEFINITIONS:
- SUPPORTED: The retrieved context provides strong evidence for the theme.
- WEAKLY SUPPORTED: The retrieved context provides tangential or minor evidence.
- UNSUPPORTED: The retrieved context does not provide evidence for the theme.
- CONTRADICTED: A retrieved paper EXPLICITLY argues AGAINST a claim in the theme. Mere absence of support is UNSUPPORTED, not CONTRADICTED.

STRICT CITATION RULE:
For every supporting claim you make, you MUST provide the EXACT 'Wiki-Link' and 'Title' from the retrieved context.
If you cite a paper that is NOT in the retrieved context, it is a hallucination and you will fail.

STRICT REFUSAL DISCIPLINE:
When the retrieved library context does not contain information to support a claim, you MUST NOT: (a) rely on your general knowledge, (b) make claims about curricula, institutions, or policies, (c) offer 'academic assessments' or feasibility opinions. A theme report must contain ONLY claims traceable to retrieved chunks.

OUTPUT FORMAT:
You must output a raw, valid JSON object exactly matching this schema:
{{
  "verdict": "SUPPORTED" | "WEAKLY SUPPORTED" | "UNSUPPORTED" | "CONTRADICTED",
  "supporting_claims": [
    {{"claim": "Claim text", "wiki_link": "Exact wiki link from context", "paper_title": "Title from context"}}
  ],
  "unverified_claims": [
    "List of sub-claims in the theme that have no evidence in the context"
  ],
  "suggested_queries": [
    "Search queries to find missing literature"
  ]
}}
Do NOT wrap the output in markdown code blocks like ```json ... ```. Output raw JSON only.
"""

    human_prompt = f"Theme to verify: {theme_name}\nDescription: {theme_description}\n\n{context_text}"
    
    # 5. Execute LLM Call
    if dev_mock:
        raw_output = json.dumps({
            "verdict": "SUPPORTED",
            "supporting_claims": [],
            "unverified_claims": [],
            "suggested_queries": []
        })
    else:
        current_key = QuotaManager.get_current_key()
        if not current_key and provider == "gemini":
            return "ERROR: No API Key."
            
        from src.quota.budget import LLMCallTracker
        tracker = LLMCallTracker(pipeline_name="theme_verifier")
        llm = ChatGoogleGenerativeAI(
            model=LANGCHAIN_PRIMARY_MODEL,
            google_api_key=current_key,
            temperature=0.1,
            callbacks=[tracker]
        )
        
        from src.utils.llm_safety import safe_llm_call
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]
        
        def run_llm_call(msgs):
            def do_call():
                response = llm.invoke(msgs)
                if isinstance(response.content, list):
                    texts = [b["text"] for b in response.content if isinstance(b, dict) and "text" in b]
                    return "".join(texts)
                return str(response.content)
                
            result = safe_llm_call(do_call)
            return result
            
        raw_output = run_llm_call(messages)
        if not raw_output:
            return "LLM Call Failed: Empty response."
            
    # 6. Validate & Retry
    def retry_callable(error_msg: str) -> str:
        retry_messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt),
            SystemMessage(content=f"Previous attempt failed: {error_msg}\nTry again.")
        ]
        return run_llm_call(retry_messages)
        
    report = validate_theme_report(raw_output, allowed_wiki_links, retry_callable)
    
    if not report:
        return "Validation failed entirely. Check output/failed_json/."
        
    # 7. Generate & Save Markdown
    md_content = _format_markdown_report(theme_name, report)
    
    base_dir = os.path.dirname(os.path.dirname(__file__))
    out_dir = os.path.join(base_dir, "output", "Obsidian_Vault", "01_Projects", "Chapter2_LitReview")
    os.makedirs(out_dir, exist_ok=True)
    
    date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_theme = "".join([c if c.isalnum() else "_" for c in theme_name])[:20]
    filename = f"Theme_Verification_{safe_theme}_{date_str}.md"
    
    filepath = os.path.join(out_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_content)
        
    return md_content

def _format_markdown_report(theme_name: str, report: ThemeReport, is_insufficient: bool = False) -> str:
    md = f"# Theme Verification Report: {theme_name}\n\n"
    
    if is_insufficient:
        md += "## ⚠️ VERDICT: INSUFFICIENT_LIBRARY\n\n"
        md += "The RAG database contains fewer than 3 relevant chunks for this theme. Verification was aborted to prevent premature false negatives.\n\n"
        md += "**Guidance**: Please scout and analyze more papers related to this theme before verifying.\n\n"
    else:
        verdict_str = report.verdict.value if hasattr(report.verdict, 'value') else report.verdict
        verdict_icon = {
            "SUPPORTED": "✅",
            "WEAKLY SUPPORTED": "⚠️",
            "UNSUPPORTED": "❌",
            "CONTRADICTED": "🛑"
        }.get(verdict_str, "❓")
        
        md += f"## {verdict_icon} VERDICT: {verdict_str}\n\n"
        
    md += "### 📌 Supporting Claims\n"
    if report.supporting_claims:
        for sc in report.supporting_claims:
            md += f"- **Claim**: {sc.claim}\n"
            md += f"  - **Source**: {sc.wiki_link} (*{sc.paper_title}*)\n"
    else:
        md += "*No supporting claims found.*\n"
        
    md += "\n### 🚨 Unverified Claims (Requires Literature)\n"
    if report.unverified_claims:
        for uc in report.unverified_claims:
            md += f"- {uc}\n"
    else:
        md += "*All claims verified.*\n"
        
    md += "\n### 🔍 Suggested Queries for Gaps\n"
    if report.suggested_queries:
        for sq in report.suggested_queries:
            md += f"- `{sq}`\n"
    else:
        md += "*No further queries suggested.*\n"
        
    return md
