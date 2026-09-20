import os
import re
from src.core.llm_factory import get_llm_response
from src.core.library_state import library_state

def generate_gap_report(gap, gap_index, confirm_expensive=False):
    """
    Generates a markdown report for a verified gap.
    Enforces two-way citation validation with one LLM corrective retry.
    """
    if not confirm_expensive:
        raise ValueError("Generating a report requires confirm_expensive=True as it charges T3.")

    statement = gap.get("statement")
    rationale = gap.get("rationale")
    evidence_list = gap.get("evidence", [])
    
    allowed_ids = [sp.get("paper_id") for sp in evidence_list]
    
    # Gather context from the library only for allowed_ids
    papers_context = []
    all_papers = library_state.state.get("papers", [])
    for pid in allowed_ids:
        # Find paper in library
        paper = next((p for p in all_papers if p.get("id") == pid or p.get("title") == pid), None)
        if paper:
            abs_t = paper.get('abstract', '')
            fin_t = paper.get('findings', '')
            met_t = paper.get('methodology', '')
            
            # Truncate to avoid limits
            if len(abs_t) > 300: abs_t = abs_t[:300] + "..."
            if len(fin_t) > 300: fin_t = fin_t[:300] + "..."
            if len(met_t) > 300: met_t = met_t[:300] + "..."
            
            papers_context.append(f"ID: [{pid}] | Title: {paper.get('title')}\nAbstract: {abs_t}\nFindings: {fin_t}\nMethodology: {met_t}")
        else:
            papers_context.append(f"ID: [{pid}] | Details missing from library.")

    papers_text = "\n\n".join(papers_context)
    
    prompt = f"""You are generating an academic gap report section.
    
Gap Statement: {statement}
Rationale: {rationale}

Supporting Papers:
{papers_text}

Write a structured draft section containing:
1. Gap Statement & Context
2. Evidence Summary per Paper
3. Methodological Recommendations
4. Reference List (auto-generated from context)

STRICT CITATION RULES:
- You MUST cite the exact paper ID inline for every claim using the format [@ID], e.g., [@{allowed_ids[0]}].
- EVERY single claim must be cited.
- DO NOT make claims not found in the provided papers.
- You MUST cite every provided paper ID at least once in your report.
- DO NOT cite any ID not in the allowed list: {', '.join(allowed_ids)}
- REGRESSION RULE: You are strictly forbidden from attributing specific data types (e.g., qualitative, quantitative, interviews, surveys) to a source unless those methodological details are explicitly present in the provided analysis fields. Do not hallucinate study designs.
"""

    messages = [
        {"role": "system", "content": "You are a research synthesis engine. Output standard markdown."},
        {"role": "user", "content": prompt}
    ]

    # Preview cost
    prompt_len = sum(len(m["content"]) for m in messages)
    est_tokens = prompt_len // 4
    print(f"\n--- Cost Preview: Gap {gap_index} Report ---")
    print(f"Tier: T3 (charged call)")
    print(f"Est. Input Tokens: {est_tokens}")
    print("----------------------------------------")

    def run_generation(msgs):
        return get_llm_response(msgs, tier="T3", pipeline="reporting_t3", confirm_expensive=confirm_expensive)

    raw_markdown = run_generation(messages)
    
    # Validation loop (max 1 retry)
    for attempt in range(2):
        is_valid, err_msg = validate_citations(raw_markdown, allowed_ids)
        if is_valid:
            save_report(raw_markdown, gap_index)
            return raw_markdown
            
        if attempt == 0:
            print(f"Validation failed (Attempt 1): {err_msg}. Retrying...")
            messages.append({"role": "assistant", "content": raw_markdown})
            messages.append({"role": "user", "content": f"Your previous response failed validation: {err_msg}. Please correct the citations. Remember, use [@ID] format. The ONLY allowed IDs are: {', '.join(allowed_ids)}. You MUST cite all of them at least once, and you MUST NOT cite any other ID."})
            raw_markdown = run_generation(messages)
        else:
            raise ValueError(f"Unsupported claim detected after retry. Violation: {err_msg}")

def validate_citations(markdown, allowed_ids):
    """
    Two-way citation check:
    1. No cited ID outside supporting_evidence.
    2. Every supporting_evidence ID cited at least once.
    """
    # Find all [@...] citations
    matches = set(re.findall(r'\[@(.*?)\]', markdown))
    
    cited_ids = set()
    invalid_citations = set()
    
    for match in matches:
        match_clean = match.strip()
        if match_clean in allowed_ids:
            cited_ids.add(match_clean)
        else:
            invalid_citations.add(match_clean)

    missing_ids = set(allowed_ids) - cited_ids
    
    errors = []
    if invalid_citations:
        errors.append(f"Invalid/hallucinated citations found: {', '.join(invalid_citations)}")
    if missing_ids:
        errors.append(f"Missing mandatory citations (papers not cited): {', '.join(missing_ids)}")
        
    if errors:
        return False, " | ".join(errors)
    return True, ""

def save_report(markdown, gap_index):
    os.makedirs(os.path.join("output", "reports"), exist_ok=True)
    out_path = os.path.join("output", "reports", f"gap_report_{gap_index}.md")
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(markdown)
    print(f"Report saved to {out_path}")
