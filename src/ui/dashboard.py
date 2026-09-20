import streamlit as st
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))



from streamlit_option_menu import option_menu
from src.core.library_state import library_state
from src.core.budget import budget_manager
import src.core.llm_factory as llm_factory
from src.core.analyze import analyze_paper, estimate_cost
from src.core.gap_engine import _run_t0_clustering, run_gap_engine_t0_t1, run_gap_engine_t2_verification

st.set_page_config(page_title="Research Dashboard", layout="wide")

with st.sidebar:
    selected = option_menu(
        menu_title="Navigation",
        options=["Command Deck", "Analyze Paper", "Gap Engine"],
        icons=["speedometer2", "file-text", "search"],
        menu_icon="cast",
        default_index=0,
    )

if selected == "Command Deck":
    st.title("Command Deck")

    st.header("Library KPIs")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Papers", len(library_state.state.get("papers", [])))
    with col2:
        st.metric("Identified Gaps (Verified)", len([g for g in library_state.state.get("gaps", []) if g.get("status") == "verified"]))
    with col3:
        st.metric("Rejected Gaps", len(library_state.state.get("rejected_candidates", [])))

    st.markdown("---")
    
    st.header("Gap Ledger")
    verified_gaps = [g for g in library_state.state.get("gaps", []) if g.get("status") == "verified"]
    if not verified_gaps:
        st.info("No verified gaps in the ledger yet. Run the Gap Engine!")
    else:
        for i, gap in enumerate(verified_gaps):
            with st.expander(f"Gap {i+1}: {gap.get('statement', 'Unknown')[:60]}... (Supporting Papers: {len(gap.get('evidence', []))})"):
                st.write(f"**Statement:** {gap.get('statement')}")
                st.write(f"**Rationale:** {gap.get('rationale')}")
                st.write("**Evidence:**")
                for ev in gap.get("evidence", []):
                    st.write(f"- *ID: {ev.get('paper_id')}* | {ev.get('evidence')}")
                    
    st.markdown("---")
    
    st.header("Budget & Tracking")
    total_cost, total_calls = budget_manager.calculate_current_usage()
    
    col4, col5 = st.columns(2)
    with col4:
        st.metric("Total Successful Calls", total_calls)
    with col5:
        st.metric("Estimated Cost ($)", f"{total_cost:.5f}")
        
    last_action = budget_manager.get_last_action_breakdown()
    if last_action:
        st.subheader("Last Action Breakdown")
        st.json(last_action)
    else:
        st.info("No recorded actions yet.")

elif selected == "Analyze Paper":
    st.title("Analyze Paper")
    st.write("Paste the text of a research paper below to extract metadata, methodology, findings, and relevance signals.")
    
    paper_text = st.text_area("Paper Text (Paste here)", height=300)
    
    if paper_text:
        st.subheader("Cost Preview")
        preview = estimate_cost(paper_text)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Tier / Model", preview["model"] if not preview["is_cached"] else "CACHE")
        with col2:
            st.metric("Estimated Tokens", preview["estimated_tokens"])
        with col3:
            st.metric("Cache Hit Expected?", "Yes 🟢" if preview["is_cached"] else "No 🔴")
            
        if st.button("Execute Analysis", type="primary"):
            with st.spinner("Analyzing paper..."):
                try:
                    result = analyze_paper(paper_text)
                    st.success("Paper analyzed successfully and saved to Library State!")
                    st.json(result)
                except Exception as e:
                    st.error(f"Analysis failed: {str(e)}")

elif selected == "Gap Engine":
    st.title("Gap Engine")
    
    st.header("T0: Library Clustering")
    if st.button("Run T0 Clustering"):
        with st.spinner("Extracting clusters from abstract and findings..."):
            clusters = _run_t0_clustering()
            st.session_state["clusters"] = clusters
            
    if "clusters" in st.session_state:
        st.write("**Top Semantic Clusters (Keywords):**")
        st.write(", ".join(st.session_state["clusters"]))
        
        st.markdown("---")
        st.header("T1: Gap Synthesis")
        if st.button("Synthesize Candidate Gaps (T1)"):
            with st.spinner("Synthesizing candidate gaps..."):
                try:
                    res = run_gap_engine_t0_t1()
                    st.session_state["candidate_gaps"] = res["candidate_gaps"]
                    st.success(f"Synthesized {len(res['candidate_gaps'])} candidate gaps.")
                except Exception as e:
                    st.error(f"Synthesis failed: {str(e)}")
                    
    if "candidate_gaps" in st.session_state:
        st.subheader("Candidate Gaps")
        st.json(st.session_state["candidate_gaps"])
        
        st.markdown("---")
        st.header("T2: Verification Pass")
        st.warning("⚠️ T2 Verification runs on Gemini and requires confirm_expensive=True.")
        
        if st.button("Run Deep Verification (T2)", type="primary"):
            with st.spinner("Verifying gaps against library evidence..."):
                try:
                    res = run_gap_engine_t2_verification(st.session_state["candidate_gaps"])
                    st.success(f"Verification complete! Verified: {len(res['verified_gaps'])}, Rejected: {len(res['rejected_gaps'])}")
                    st.write("Verified Gaps added to ledger:")
                    st.json(res["verified_gaps"])
                    st.write("Rejected Gaps:")
                    st.json(res["rejected_gaps"])
                    del st.session_state["candidate_gaps"] # Clear candidates after running
                except Exception as e:
                    st.error(f"Verification failed: {str(e)}")
