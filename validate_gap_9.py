import os
from src.core.reporting import validate_citations
from src.core.library_state import library_state

def main():
    with open('output/reports/gap_report_9.md', 'r', encoding='utf-8') as f:
        markdown = f.read()

    gaps = library_state.state.get("gaps", [])
    gap_9 = gaps[8] # Gap 9
    
    evidence_list = gap_9.get("evidence", [])
    allowed_ids = [sp.get("paper_id") for sp in evidence_list]

    print("=== VALIDATING CORRECTED GAP 9 ===")
    is_valid, err_msg = validate_citations(markdown, allowed_ids)
    
    if is_valid:
        print("VALIDATION PASSED: All citations are strictly grounded and fully cover the evidence list.\n")
        print("--- CORRECTED MARKDOWN ---")
        print(markdown.encode('ascii', 'replace').decode('ascii'))
    else:
        print(f"VALIDATION FAILED: {err_msg}")

if __name__ == "__main__":
    main()
