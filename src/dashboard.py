import os
import sys
import pathlib

# Ensure the project root is in sys.path so 'src' can be imported anywhere
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import streamlit as st

@st.cache_resource
def get_library_db():
    from src.db.library import LibraryDB
    return LibraryDB()

@st.cache_resource
def get_budget_manager():
    from src.quota.budget import BudgetManager
    return BudgetManager()

@st.cache_resource
def get_system_analytics():
    from src.analytics import SystemAnalytics
    return SystemAnalytics()

import io
import io
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    elif hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
    elif hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
except Exception:
    pass
import json
import pandas as pd
import requests
from bs4 import BeautifulSoup
import PyPDF2
import time
# Ensure src/ is in the python path
sys.path.append(os.path.dirname(__file__))

# Import all core modules
from src.main import run_crew_pipeline
from src.chatbot import chat_with_supervisor, generate_dynamic_titles, generate_lit_review
from src.scout import run_scout_pipeline
from src.quota_manager import QuotaManager
from src.open_vault import launch_obsidian

def extract_text_from_pdf(uploaded_file):
    try:
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        text = ""
        # Extract only first 3 pages to avoid token limit overload
        for page in pdf_reader.pages[:3]:
            if page.extract_text():
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return f"Error reading PDF: {e}"

def extract_text_from_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        # Kill script and style elements
        for script in soup(["script", "style"]):
            script.extract()
        text = soup.get_text(separator=' ', strip=True)
        # Return first 10000 chars roughly to avoid token overload
        return text[:10000]
    except Exception as e:
        return f"Error reading URL: {e}"

def check_comparison_keywords(paper):
    keywords = ["kolej vokasional", "vocational", "tvet", "ai", "learning", "pembinaan", "construction", "malaysia", "adoption", "teaching"]
    text = (str(paper.get('title', '')) + " " + str(paper.get('abstract', ''))).lower()
    matches = [kw for kw in keywords if kw in text]
    return matches

def render_paper_card(paper, index_prefix):
    with st.container(border=True):
        st.markdown(f"#### {paper.get('title', 'Unknown Title')}")
        st.markdown(f"**Authors:** {paper.get('authors', 'Unknown')} | **Year:** {paper.get('year', 'N/A')}")
        st.markdown(f"**Relevance Score:** {paper.get('relevance_score', 'N/A')}/10 | *Scouted at: {paper.get('scouted_at')}*")
        
        matches = check_comparison_keywords(paper)
        if matches:
            st.info(f"🔍 **Possible comparison candidate** — Keyword matches: {', '.join(matches)}")
            
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Assess for Comparison", key=f"assess_{index_prefix}_{paper.get('title')}", use_container_width=True):
                with st.spinner("Assessing..."):
                    from chatbot import assess_paper_for_comparison
                    import state_manager
                    res = assess_paper_for_comparison(paper.get('title'), paper.get('abstract'), str(paper.get('year')))
                    state_manager.update_paper_assessment(paper.get('title'), res.get('verdict'), res.get('advice'))
                    st.success("Assessment Complete!")
                    st.rerun()
        
        # Display existing assessments
        assessments = paper.get("assessments", [])
        if assessments:
            st.markdown("---")
            st.markdown("##### 📝 Supervisor's Comparison Notes")
            for i, ass in enumerate(reversed(assessments)):
                st.markdown(f"**{ass['verdict']}** *(Assessed on {ass['date'][:10]})*")
                if i == 0:
                    st.write(ass['advice'])
                else:
                    with st.expander(f"Previous Assessment ({ass['date'][:10]})"):
                        st.write(ass['advice'])
                
        with st.expander("Read Abstract / Notes"):
            st.write(paper.get('abstract', 'No abstract provided.'))

def main():
    if "storage_pulled" not in st.session_state:
        try:
            from src.core.storage import StorageHandler
            StorageHandler.pull_state()
        except Exception as e:
            print(f"Failed to pull state on start: {e}")
        st.session_state.storage_pulled = True
        
    if "cache_hits" not in st.session_state:
        st.session_state.cache_hits = 0
        
    try:
        from src.quota.budget import BudgetManager
        bm = get_budget_manager()
        dev_state = bm.get_mode()
        if dev_state.get("dev_mode"):
            st.warning("⚠️ **DEVELOPER MODE ACTIVE (Groq)**: Outputs routed to dev_runs/. Vault untouched.", icon="🛠️")
        if dev_state.get("dev_mock"):
            st.error("🚨 **MOCK MODE ACTIVE**: Zero LLM calls. Using Fake data.", icon="🚨")
    except: pass

    # Initialize APScheduler Daemon for 2 AM Scout (Secondary Path)
    if "scheduler_started" not in st.session_state:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        
        def scheduled_scout_job():
            try:
                import scout
                print("[Daemon] Triggering background scout at 2:00 AM...")
                scout.run_scout_pipeline()
            except Exception as e:
                print(f"[Daemon] Error running scout: {e}")
                
        scheduler = BackgroundScheduler()
        # Schedule to run every day at 02:00 AM
        scheduler.add_job(scheduled_scout_job, trigger=CronTrigger(hour=2, minute=0))
        scheduler.start()
        st.session_state.scheduler_started = True

    # 1. Page Config
    st.set_page_config(
        page_title="PhD Assistant UTM - Command Center",
        layout="wide",
        page_icon="🎓"
    )

    # --- Authentication Layer ---
    # Change "hamizan00" to your desired default password, or set APP_PASSWORD in .env
    expected_password = os.getenv("APP_PASSWORD", "hamizan00")
    
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔒 Access Restricted")
        st.markdown("Please enter the system password to access the PhD Assistant UTM Command Center.")
        
        pwd = st.text_input("Password", type="password")
        if st.button("Login", type="primary"):
            if pwd == expected_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.stop()
    # ----------------------------

    # Hot-reload .env so users don't have to restart Streamlit when changing keys
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    load_dotenv(env_path, override=True)

    # Sidebar: Key Statuses
    st.sidebar.title("🔑 API Key Status (Today)")
    statuses = QuotaManager.get_key_statuses()
    for status in statuses:
        if status["state"] == "serving":
            st.sidebar.markdown(f"🟡 **{status['key']}** (Serving)")
        elif status["state"] == "exhausted":
            st.sidebar.markdown(f"❌ **{status['key']}** (Exhausted: {status['reason']})")
        else:
            st.sidebar.markdown(f"✅ **{status['key']}** (Available)")
    
    st.sidebar.markdown("---")

    # Check for novelty threats in the log
    try:
        import datetime
        threat_log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "threat_log.md")
        if os.path.exists(threat_log_path):
            with open(threat_log_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                
            if content:
                # Split by main list item
                entries = content.split("\n- **[")
                last_entry = entries[-1] if len(entries) == 1 else "- **[" + entries[-1]
                
                today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                if today_str in last_entry and "NOVELTY THREAT" in last_entry:
                    if "(RED)" in last_entry or "🚨" in last_entry:
                        st.error(last_entry, icon="🚨")
                    elif "(YELLOW)" in last_entry or "⚠️" in last_entry:
                        st.warning(last_entry, icon="⚠️")
                    else:
                        st.error(last_entry, icon="🚨")
    except Exception as e:
        pass

    # 2. Sidebar Configuration
    with st.sidebar:
        st.header("🎓 PhD Assistant UTM")
        st.subheader("Doctoral Command Center")
        
        st.markdown("---")
        if st.button("🧠 Open Second Brain in Obsidian", type="primary", use_container_width=True):
            try:
                launch_obsidian()
                st.success("Vault launching...")
            except Exception as e:
                st.error(f"Error launching Obsidian: {e}")
                
        st.markdown("---")
        
        st.markdown("**System Status**")
        st.success("Core Pipeline: Online")
        st.success("Advisor Agent: Online")
        if st.session_state.cache_hits > 0:
            st.info(f"⚡ Saved **{st.session_state.cache_hits}** API calls via cache today.")
        
        try:
            from src.quota.budget import BudgetManager
            bm = get_budget_manager()
            rem = bm.remaining()
            dev_state = bm.get_mode()
            
            st.markdown("**Budget & API Quota**")
            
            new_dev = st.checkbox("Enable Developer Mode (Groq)", value=dev_state.get("dev_mode", False))
            new_mock = st.checkbox("Enable Mock Mode (Fake)", value=dev_state.get("dev_mock", False))
            if new_dev != dev_state.get("dev_mode") or new_mock != dev_state.get("dev_mock"):
                bm.set_mode(new_dev, new_mock)
                st.rerun()

            gemini_rem = rem['gemini']
            st.metric("Gemini Quota (Today)", f"{gemini_rem['remaining']} / {gemini_rem['limit']} left")
            
            groq_rem = rem['groq']
            st.caption(f"Groq Usage: {groq_rem['used']} / {groq_rem['soft_limit']} (soft)")
            
            if gemini_rem['remaining'] <= 0 and not new_dev:
                st.error("Gemini Quota Exhausted!")
                estimate = bm.config.get("estimates", {}).get("single_paper", 5)
                if bm.can_afford(estimate, provider="groq"):
                    st.warning(f"Analysis quality may be slightly lower on Groq. A run costs ~{estimate} calls.")
                    if st.button("Switch to Groq"):
                        bm.set_mode(True, False)
                        st.rerun()
                else:
                    st.error("Groq Quota also exhausted today.")
            
            st.markdown("---")
            st.markdown("**Last Action Call Breakdown**")
            try:
                import pandas as pd
                csv_path = os.path.join(bm.analytics_dir, "actual_calls.csv")
                if os.path.exists(csv_path):
                    df = pd.read_csv(csv_path)
                    if not df.empty:
                        last_row = df.iloc[-1]
                        pipeline_name = last_row.get('Pipeline', last_row.get('pipeline', 'Unknown'))
                        model_name = last_row.get('Model', last_row.get('model', 'Unknown'))
                        st.caption(f"**Pipeline:** {pipeline_name} | **Model:** {model_name}")
                        
                        pt = last_row.get('PromptTokens', last_row.get('prompt_tokens', 0))
                        ct = last_row.get('CompletionTokens', last_row.get('completion_tokens', 0))
                        tt = last_row.get('TotalTokens', last_row.get('total_tokens', 0))
                        
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Prompt", pt)
                        c2.metric("Comp", ct)
                        c3.metric("Total", tt)
                    else:
                        st.caption("No API calls recorded yet.")
            except Exception as e:
                st.caption(f"Could not load breakdown: {e}")
            
            st.markdown("---")
            st.markdown("**Database Backups**")
            db = get_library_db()
            backups = glob.glob(os.path.join(db.backups_dir, "library_*.json"))
            if backups:
                backups.sort(key=os.path.getmtime, reverse=True)
                backup_names = [os.path.basename(b) for b in backups]
                selected_backup = st.selectbox("Available Backups", backup_names)
                if st.button("Restore Backup"):
                    full_path = backups[backup_names.index(selected_backup)]
                    try:
                        import shutil
                        shutil.copy2(full_path, db.db_path)
                        st.success(f"Restored {selected_backup}!")
                    except Exception as e:
                        st.error("Restore failed.")
            else:
                st.caption("No backups available yet.")
            
            st.markdown("---")
            st.markdown("**Vector Store (RAG)**")
            if st.button("Rebuild RAG Index", use_container_width=True):
                with st.spinner("Re-embedding library to ChromaDB..."):
                    from src.rag.vectorstore import rebuild_index
                    try:
                        rebuild_index()
                        st.success("Index rebuilt successfully!")
                    except Exception as e:
                        st.error(f"Error rebuilding index: {e}")
        except Exception:
            pass
            
        st.markdown("---")
        st.markdown("**Title Lock Mechanism**")
        base_dir = os.path.dirname(os.path.dirname(__file__))
        final_title_path = os.path.join(base_dir, "config", "final_title.txt")
        if os.path.exists(final_title_path):
            with open(final_title_path, "r", encoding="utf-8") as f:
                locked_title = f.read().strip()
            # truncate for display if too long
            short_title = locked_title if len(locked_title) < 50 else locked_title[:47] + "..."
            st.success(f"🔒 **TITLE LOCKED:**\n*{short_title}*")
            unlock_confirm = st.text_input("Type 'UNLOCK' to release:", key="unlock_input")
            if unlock_confirm == "UNLOCK" and st.button("Unlock Title"):
                os.remove(final_title_path)
                st.rerun()
        else:
            st.info("🔓 **TITLE DISCOVERY MODE**")
            title_to_lock = st.text_area("Paste Confirmed Thesis Title:", key="title_lock_input")
            lock_confirm = st.text_input("Type 'CONFIRM' to lock:", key="lock_confirm_input")
            if lock_confirm == "CONFIRM" and st.button("Lock Final Title"):
                if title_to_lock.strip():
                    os.makedirs(os.path.dirname(final_title_path), exist_ok=True)
                    with open(final_title_path, "w", encoding="utf-8") as f:
                        f.write(title_to_lock.strip())
                    st.rerun()
                else:
                    st.warning("Cannot lock an empty title.")
        
        st.markdown("---")
        
        # API key is now fully managed dynamically by QuotaManager
        api_key = QuotaManager.get_current_key()
        st.markdown("---")
        st.markdown("**Backward Compatibility**")
        if st.button("Run Full Semantic Scan on Library", help="Re-scan old library entries with the new Semantic AI."):
            from src.db.library import LibraryDB
            db = get_library_db()
            data = db._read()
            papers = data.get("papers", [])
            if papers:
                with st.spinner("Scanning all past papers..."):
                    from threat_detector import check_novelty_threat
                    threats_found = 0
                    for paper in papers:
                        res = check_novelty_threat(paper.get("title", ""), paper.get("abstract", ""), paper.get("relevance_score", 0), paper.get("year", 0))
                        if res.get("threat"):
                            threats_found += 1
                    if threats_found > 0:
                        st.success(f"Scan complete. Found {threats_found} threats. Reloading...", icon="✅")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.success("Scan complete. No semantic threats found in the library.", icon="✅")
            else:
                st.info("No library.json found to scan.")

    # 3. Top KPI Metrics (Global)
    st.title("Research Dashboard")
    
    # Calculate real metrics
    total_papers = 0
    gaps_found = 0
    base_dir = os.path.dirname(os.path.dirname(__file__))
    md_file = os.path.join(base_dir, "output", "library.md")
    json_file = os.path.join(base_dir, "output", "library.json")
    
    # Count manual analyses
    if os.path.exists(md_file):
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()
            total_papers += content.count("## Entry (Mode:")
            gaps_found += content.count("[GAP FOUND]")
            
    # Count scouted JSON papers
    try:
        from src.db.library import LibraryDB
        db = get_library_db()
        data = db._read()
        total_papers += len(data.get("papers", []))
    except Exception:
        pass

    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    with col_kpi1:
        st.metric(label="Total Papers in Library", value=str(total_papers))
    with col_kpi2:
        st.metric(label="Clear Gaps Found", value=str(gaps_found))
    with col_kpi3:
        st.metric(label="Saturated Topics", value="0", help="Under development.")
        
    st.divider()

    if st.session_state.get("novelty_threat"):
        st.error("🚨 **CRITICAL NOVELTY THREAT DETECTED!** 🚨\nThe system has identified a highly similar Malaysian study (2020-2026). Please review the Literature Command Center output immediately to adjust your thesis gap.", icon="🛑")
        st.divider()

    # System Analytics Lazy Trigger
    from src.analytics import SystemAnalytics
    analytics = get_system_analytics()
    analytics.lazy_generate_weekly_digest()

    # 4. The 7-Tab Architecture
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "💬 Research Chatbot & Advisor", 
        "📡 The Daily Radar (Scout)", 
        "🎯 Title & Gap Studio", 
        "🧠 Literature Command Center",
        "📚 Master Library Data",
        "📊 System Analytics",
        "🗺️ Literature Map Verifier"
    ])

    # ---------------- TAB 1: Chatbot ----------------
    with tab1:
        import state_manager
        
        chat_col, context_col = st.columns([2, 1])
        
        with context_col:
            st.markdown("### 📋 Research Context Registry")
            st.markdown("These parameters are permanently saved and injected into every conversation with your PhD Advisor.")
            
            context = state_manager.load_research_context()
            
            with st.form("context_registry_form"):
                sample_scope = st.text_area("Sample Scope (n, type)", value=context.get("sample_scope", ""), help="e.g., 8-10 KVs, stratified")
                states_zones = st.text_input("States/Zones Covered", value=context.get("states_zones", ""))
                study_duration = st.text_input("Study Duration", value=context.get("study_duration", ""), help="e.g., 12-month longitudinal")
                methodology = st.text_input("Methodology Leanings", value=context.get("methodology", ""), help="e.g., explanatory sequential mixed-methods")
                target = st.text_input("Target", value=context.get("target", ""), help="e.g., fast-track PhD 2026")
                current_stage = st.selectbox("Current Stage", ["Proposal", "Ethics", "Data Collection", "Analysis", "Writing"], index=["Proposal", "Ethics", "Data Collection", "Analysis", "Writing"].index(context.get("current_stage", "Proposal")) if context.get("current_stage", "Proposal") in ["Proposal", "Ethics", "Data Collection", "Analysis", "Writing"] else 0)
                
                if st.form_submit_button("Save Context"):
                    new_context = {
                        "sample_scope": sample_scope,
                        "states_zones": states_zones,
                        "study_duration": study_duration,
                        "methodology": methodology,
                        "target": target,
                        "current_stage": current_stage
                    }
                    state_manager.append_to_changelog(context, new_context)
                    state_manager.save_research_context(new_context)
                    st.success("Context saved!")
                    st.rerun()

        with chat_col:
            st.subheader("Exacting PhD Co-Supervisor")
            st.markdown("Discuss titles, methodologies, or ask for gap matrices. **Warning:** This supervisor is extremely strict regarding Kolej Vokasional scope.")
            
            if "messages" not in st.session_state:
                st.session_state.messages = state_manager.load_recent_chat_history(limit=30)

        # Display chat messages from history
        for msg in st.session_state.messages:
            role = msg["role"]
            with st.chat_message("human" if role == "user" else "ai"):
                st.markdown(msg["content"])
                if "sources" in msg and msg["sources"]:
                    from src.open_vault import get_obsidian_uri
                    sources_str = ", ".join([f"[{s}]({get_obsidian_uri(s)})" for s in msg["sources"]])
                    st.caption(f"📚 Sources: {sources_str}")

        # Accept user input
        if prompt := st.chat_input("Ask your supervisor a question..."):
            # Add user message to state and display
            st.session_state.messages.append({"role": "user", "content": prompt})
            state_manager.save_chat_history(st.session_state.messages)
            
            with st.chat_message("human"):
                st.markdown(prompt)

            # Connect to LangChain Backend
            if not api_key:
                st.error("Please enter your Gemini API Key in the sidebar.")
            else:
                with st.chat_message("ai"):
                    with st.spinner("Supervisor is thinking..."):
                        # Convert session_state format to tuples expected by chatbot
                        history_tuples = [(m["role"], m["content"]) for m in st.session_state.messages[:-1]]
                        try:
                            response, sources = chat_with_supervisor(prompt, history_tuples)
                            
                            if response.startswith("BUDGET_BLOCKED"):
                                st.error(response)
                            else:
                                st.markdown(response)
                                if sources:
                                    from src.open_vault import get_obsidian_uri
                                    sources_str = ", ".join([f"[{s}]({get_obsidian_uri(s)})" for s in sources])
                                    st.caption(f"📚 Sources: {sources_str}")
                                st.session_state.messages.append({
                                    "role": "ai", 
                                    "content": response,
                                    "sources": sources
                                })
                                state_manager.save_chat_history(st.session_state.messages)
                                
                            # Debate Mode: Check for JSON diff proposal
                            if "```json" in response and "proposed_research_context" in response:
                                st.session_state.pending_context_update = response
                                st.rerun()
                                
                        except Exception as e:
                            st.error(f"API Error: {e}")
                            
            # Render Apply/Cancel buttons for Debate Mode
            if st.session_state.get("pending_context_update"):
                response_text = st.session_state.pending_context_update
                try:
                    import re
                    json_match = re.search(r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL)
                    if json_match:
                        proposed_json = json.loads(json_match.group(1))
                        if "proposed_research_context" in proposed_json:
                            st.warning("⚠️ The Advisor has proposed a change to your Research Context Registry.")
                            col_a, col_b = st.columns(2)
                            if col_a.button("✅ Apply Changes", use_container_width=True):
                                old_ctx = state_manager.load_research_context()
                                new_ctx = proposed_json["proposed_research_context"]
                                # Merge with existing context in case the AI only provided a partial update
                                merged_ctx = {**old_ctx, **new_ctx}
                                state_manager.append_to_changelog(old_ctx, merged_ctx)
                                state_manager.save_research_context(merged_ctx)
                                st.session_state.pending_context_update = None
                                st.success("Research Context Updated!")
                                st.rerun()
                            if col_b.button("❌ Cancel", use_container_width=True):
                                st.session_state.pending_context_update = None
                                st.rerun()
                except Exception as e:
                    st.error(f"Failed to parse proposed context: {e}")
                    st.session_state.pending_context_update = None

    # ---------------- TAB 2: Scout Radar ----------------
    with tab2:
        st.subheader("Background Literature Scout")
        st.markdown("View papers automatically discovered by your background agents.")
        
        col_btn, col_timer = st.columns([1, 1])
        with col_btn:
            scout_btn_placeholder = st.empty()
        with col_timer:
            rate_limit_container = st.empty()
        
        if scout_btn_placeholder.button("🚀 Trigger Scout Manually", key="scout_btn"):
            scout_btn_placeholder.button("⏳ Scout is running... (Locked)", disabled=True, key="scout_lock")
            st.markdown("### 📡 Scout Agent Live Terminal")
            st_expander = st.expander("View Real-time Terminal Output", expanded=True)
            log_container = st_expander.empty()
            
            from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
            ctx = get_script_run_ctx()
            
            class StreamlitCapture:
                def __init__(self, st_empty):
                    self.st_empty = st_empty
                    self.text = ""
                    self.ctx = ctx
                    self.encoding = "utf-8"
                def write(self, text):
                    try:
                        if isinstance(text, bytes):
                            text = text.decode("utf-8", "replace")
                        self.text += str(text)
                        if len(self.text) > 50000:
                            self.text = self.text[-50000:]
                        import threading

                        if not get_script_run_ctx():
                            add_script_run_ctx(threading.current_thread(), self.ctx)
                        self.st_empty.code(self.text, language="text")
                    except Exception:
                        pass
                def flush(self): pass
            # rate_limit_container instantiated above
            
            def handle_scout_rate_limit(wait_time, attempt, max_retries):
                import threading

                if not get_script_run_ctx():
                    add_script_run_ctx(threading.current_thread(), ctx)
                for i in range(wait_time, 0, -1):
                    mins, secs = divmod(i, 60)
                    rate_limit_container.error(f"## 🚨 API Rate Limit Hit!\n### ⏱️ Cooldown: {mins:02d}:{secs:02d}\n*(Attempt {attempt}/{max_retries}) Scout will automatically resume.*")
                    time.sleep(1)
                rate_limit_container.empty()
                
            original_stdout = sys.stdout
            sys.stdout = StreamlitCapture(log_container)
            
            try:
                with st.spinner("Scout Agents are searching... This may take a minute."):
                    run_scout_pipeline(on_rate_limit_callback=handle_scout_rate_limit)
                    st.success("Scout run complete! Refreshing feed...")
            except Exception as e:
                import traceback
                traceback.print_exc()
                err_msg = str(e) if str(e).strip() else repr(e)
                st.error(f"Error during manual scout: {err_msg}", icon="⚠️")
            finally:
                sys.stdout = original_stdout
                scout_btn_placeholder.button("🚀 Trigger Scout Manually", key="scout_done")
                
        st.divider()
        
        if not os.path.exists(json_file):
            st.info("No papers scanned yet. The library database is empty.")
        else:
            try:
                from src.db.library import LibraryDB
                db = get_library_db()
                data = db._read()
                papers = data.get("papers", [])
                
                if not papers:
                    st.info("No papers scanned yet. The library database is empty.")
                else:
                    from datetime import datetime, date
                    today_str = date.today().isoformat()
                    
                    latest_papers = []
                    previous_papers = []
                    
                    for p in papers:
                        scouted = p.get('scouted_at', '2000-01-01T00:00:00')
                        if scouted.startswith(today_str):
                            latest_papers.append(p)
                        else:
                            previous_papers.append(p)
                            
                    st.markdown("### 🌟 Today's Latest Discoveries")
                    if not latest_papers:
                        st.info("No new papers scouted today.")
                    else:
                        for i, paper in enumerate(reversed(latest_papers)):
                            render_paper_card(paper, f"tab2_latest_{i}")
                                    
                    st.markdown("### 📚 Previous Discoveries")
                    if not previous_papers:
                        st.info("No older papers in the database.")
                    else:
                        for i, paper in enumerate(reversed(previous_papers)):
                            render_paper_card(paper, f"tab2_prev_{i}")
                                    
            except Exception as e:
                st.error(f"Error reading JSON database: {e}")

    # ---------------- TAB 3: Title & Gap Studio ----------------
    with tab3:
        st.subheader("Thesis Title Leaderboard")
        st.markdown("Surviving titles based on literature gaps and supervisor approval.")
        
        col_btn_tab3, col_timer_tab3 = st.columns([1, 1])
        with col_btn_tab3:
            gen_btn_placeholder = st.empty()
        with col_timer_tab3:
            tab3_rate_limit_container = st.empty()
            
        if gaps_found < 1:
            gen_clicked = gen_btn_placeholder.button("🚀 Generate Novel Titles", key="gen_btn", disabled=True)
            st.warning("No verified gaps. Run gap analysis first.", icon="⚠️")
        else:
            gen_clicked = gen_btn_placeholder.button("🚀 Generate Novel Titles", key="gen_btn")
            
        if gen_clicked:
            gen_btn_placeholder.button("⏳ Generating... (Locked)", disabled=True, key="gen_lock")
            with st.spinner("AI Supervisor is analyzing gaps..."):
                max_retries = 4
                for attempt in range(max_retries):
                    try:
                        result = generate_dynamic_titles()
                        st.session_state.dynamic_titles = result.get("titles", [])
                        break
                    except Exception as e:
                        error_str = str(e)
                        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                            if attempt < max_retries - 1:
                                wait_time = 60
                                for i in range(wait_time, 0, -1):
                                    mins, secs = divmod(i, 60)
                                    tab3_rate_limit_container.error(f"## 🚨 API Rate Limit Hit!\n### ⏱️ Cooldown: {mins:02d}:{secs:02d}\n*(Attempt {attempt+1}/{max_retries}) Title generator will resume.*")
                                    time.sleep(1)
                                tab3_rate_limit_container.empty()
                            else:
                                st.error(f"Error generating titles after {max_retries} attempts: {e}")
                        else:
                            st.error(f"Error generating titles: {e}")
                            break
            gen_btn_placeholder.button("🚀 Generate Novel Titles", key="gen_done")
                    
        if "dynamic_titles" in st.session_state:
            st.markdown("---")
            for idx, title_obj in enumerate(st.session_state.dynamic_titles, 1):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"### {idx}. {title_obj['title']}")
                    st.caption(title_obj['justification'])
                with col2:
                    score = title_obj['novelty_score']
                    color = "green" if score >= 8 else ("orange" if score >= 5 else "red")
                    st.markdown(f"### Score: {score}/10")
                st.markdown("---")
        else:
            st.info("Click the button above to generate dynamic titles based on your library.")

    # ---------------- TAB 4: Literature Command Center ----------------
    with tab4:
        left_col, right_col = st.columns([1, 1], gap="large")

        with left_col:
            st.subheader("📝 Manual Paper Analysis")
            
            input_mode = st.radio("Select Input Method:", ["Paste Text", "Upload PDF", "Web Link"], horizontal=True)
            
            paper_input = ""
            if input_mode == "Paste Text":
                paper_input = st.text_area("Paper Abstract or Title:", height=200, placeholder="Paste the abstract or title here for the AI crew to process...")
            elif input_mode == "Upload PDF":
                uploaded_file = st.file_uploader("Upload PDF file", type=["pdf"])
                if uploaded_file is not None:
                    paper_input = extract_text_from_pdf(uploaded_file)
                    st.success("PDF loaded successfully! Click Analyze below.")
            elif input_mode == "Web Link":
                url_input = st.text_input("Enter URL (e.g., Journal Link):", placeholder="https://...")
                if url_input:
                    with st.spinner("Fetching web page..."):
                        paper_input = extract_text_from_url(url_input)
                    if "Error" in paper_input:
                        st.error(paper_input)
                    else:
                        st.success("URL loaded successfully! Click Analyze below.")
            
            is_supervisor = st.checkbox("Supervisor Recommended (High Priority)", value=False)
            
            col_btn, col_timer = st.columns([1, 1])
            with col_btn:
                analyze_btn_placeholder = st.empty()
            with col_timer:
                rate_limit_container = st.empty()
            
            analyze_clicked = analyze_btn_placeholder.button("🚀 Analyze Paper (Filter & Summarize)", type="primary", use_container_width=True, key="analyze_btn")
            if analyze_clicked:
                analyze_btn_placeholder.button("⏳ Processing (Locked)...", type="primary", use_container_width=True, disabled=True, key="analyze_lock")
            
            st.divider()
            st.subheader("📚 Literature Review Generation")
            st.markdown("Draft Chapter 2 based on your entire saved library.")
            
            if st.button("📝 Generate APA 7th Lit Review Draft", use_container_width=True):
                with st.spinner("Synthesizing your library into a cohesive literature review..."):
                    try:
                        draft = generate_lit_review()
                        st.session_state.lit_review_draft = draft
                    except Exception as e:
                        st.error(f"Error generating review: {e}")
                        
            if "lit_review_draft" in st.session_state:
                st.success("Draft Generated Successfully!")
                st.download_button(
                    label="📥 Download Draft (Markdown)",
                    data=st.session_state.lit_review_draft,
                    file_name="Chapter2_Draft.md",
                    mime="text/markdown",
                    use_container_width=True
                )
                with st.expander("Preview Draft"):
                    st.markdown(st.session_state.lit_review_draft)
                    
            st.divider()
            st.subheader("🛡️ Anti-Hallucination Layer")
            if st.button("🔍 Verify All Citations", use_container_width=True):
                with st.spinner("Extracting and verifying citations across library and drafts..."):
                    import re
                    from chatbot import CitationsList, get_llm
                    from langchain_core.prompts import ChatPromptTemplate
                    sys.path.append(os.path.dirname(__file__))
                    from tools.verifier import CitationVerifier
                    
                    combined_text = st.session_state.get("lit_review_draft", "")
                    try:
                        with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "library.md"), "r", encoding="utf-8") as f:
                            combined_text += "\n" + f.read()
                    except:
                        pass
                        
                    if not combined_text.strip():
                        st.warning("No literature found to verify.")
                    else:
                        ext_prompt = ChatPromptTemplate.from_messages([
                            ("system", "Extract a list of all unique academic in-text citations from the text. Return ONLY the JSON list."),
                            ("human", "{draft}")
                        ])
                        
                        try:
                            ext_response = QuotaManager.execute_call(
                                lambda kwargs: (ext_prompt | get_llm().with_structured_output(CitationsList)).invoke(kwargs),
                                {"draft": combined_text}
                            )
                            
                            report_data = []
                            for citation in set(ext_response.citations):
                                clean_query = re.sub(r'[\(\)]', '', citation)
                                if not clean_query.strip(): continue
                                
                                result = CitationVerifier.verify_paper(clean_query)
                                report_data.append({
                                    "Citation": citation,
                                    "Status": "✅ VERIFIED" if result.get("verified") else "❌ NOT FOUND",
                                    "Source": result.get("source", "N/A"),
                                    "Matched Title": result.get("title", "N/A")
                                })
                                
                            if report_data:
                                df = pd.DataFrame(report_data)
                                st.dataframe(df, use_container_width=True)
                            else:
                                st.success("No citations found to verify.")
                        except Exception as e:
                            st.error(f"Verification failed: {e}")

        with right_col:
            st.subheader("🤖 Real-time Agent Console")
            
            if analyze_clicked:
                if not paper_input.strip():
                    st.warning("Please provide a paper abstract or title first.")
                elif not api_key:
                    st.error("⚠️ Please enter your Gemini API Key in the sidebar.")
                else:
                    mode = "supervisor" if is_supervisor else "standard"
                    
                    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
                    
                    class StreamlitCapture:
                        def __init__(self, st_empty):
                            self.st_empty = st_empty
                            self.text = ""
                            self.encoding = "utf-8"
                        def write(self, text):
                            try:
                                if isinstance(text, bytes):
                                    text = text.decode("utf-8", "replace")
                                self.text += str(text)
                                if len(self.text) > 50000:
                                    self.text = self.text[-50000:]
                                
                                # Only write to UI if we have a context, or inject it
                                if not get_script_run_ctx():
                                    return
                                self.st_empty.code(self.text, language="text")
                            except Exception as e:
                                pass # Swallow capture errors so they don't crash the event bus
                        def flush(self): pass

                    st.markdown("### 🧠 Agent Thought Process")
                    st_expander = st.expander("View Real-time Terminal Output", expanded=True)
                    log_container = st_expander.empty()
                    
                    # rate_limit_container instantiated above
                    
                    def handle_rate_limit(wait_time, attempt, max_retries):
                        for i in range(wait_time, 0, -1):
                            mins, secs = divmod(i, 60)
                            rate_limit_container.error(f"## 🚨 API Rate Limit Hit!\n### ⏱️ Cooldown: {mins:02d}:{secs:02d}\n*(Attempt {attempt}/{max_retries}) Agents will automatically resume.*")
                            time.sleep(1)
                        rate_limit_container.empty()
                    
                    original_stdout = sys.stdout
                    sys.stdout = StreamlitCapture(log_container)
                    
                    try:
                        sys.path.append(os.path.dirname(__file__))
                        from utils import trim_paper_input
                        from src.db.library import LibraryDB
                        
                        trimmed_input = trim_paper_input(paper_input)
                        proxy_title = trimmed_input[:150].replace('\n', ' ')
                        
                        db = get_library_db()
                        status_info = db.check_status(proxy_title)
                        
                        force_analyze = st.session_state.get("force_analyze", False)
                        if force_analyze:
                            st.session_state.force_analyze = False # Reset for next run
                        
                        if not force_analyze and status_info and status_info.get("status") == "analyzed":
                            st.success("✅ **CACHE HIT:** Paper already analyzed. 0 API calls used.", icon="⚡")
                            st.session_state.cache_hits += 1
                            try:
                                from logger import log_event
                                log_event("CACHE_HIT", f"Saved API call for paper: {proxy_title[:100]}")
                            except: pass
                            result = "This paper was already analyzed and saved in your library."
                            st.markdown("### Outputs from Systematic Reviewer AI")
                            st.info(result, icon="🧠")
                            st.stop()
                            
                        elif not force_analyze and status_info and status_info.get("status") == "scouted":
                            st.info(f"📚 **Paper found in scout library** ({status_info.get('confidence', 0):.1f}% match).")
                            if st.button("Promote to full analysis", type="primary"):
                                st.session_state.force_analyze = True
                                # Need to overwrite input with the scout context so the LLM gets everything
                                paper_input = f"Title: {status_info.get('title')}\nAbstract/Context: {status_info.get('scout_verdict')}"
                                st.rerun()
                            else:
                                st.stop()
                                
                        with st.spinner("Agents are analyzing your paper..."):
                            # If force_analyze is true and we arrived here, trimmed_input needs to be refreshed from session state if it changed
                            if status_info and status_info.get("status") == "scouted":
                                trimmed_input = f"Title: {status_info.get('title')}\nAbstract/Context: {status_info.get('scout_verdict')}"
                                
                            result = run_crew_pipeline(paper_text=trimmed_input, mode=mode, api_key=api_key, on_rate_limit_callback=handle_rate_limit)
                            if "BUDGET_BLOCKED" in result:
                                st.error(result)
                                st.stop()
                                
                                if "CRITICAL_NOVELTY_THREAT" in result:
                                    st.session_state.novelty_threat = True
                                    st.rerun() # Force a rerun to show the banner at the top
                                
                                log_container.success("Analysis complete!")
                                
                                try:
                                    from logger import log_event
                                    log_event("MANUAL_ANALYSIS", f"Completed manual analysis for mode '{mode}'")
                                except: pass
                                
                                # Parse to display success message
                                import json, re
                                clean_result = re.sub(r'```json\s*', '', result)
                                clean_result = re.sub(r'```\s*', '', clean_result).strip()
                                
                                try:
                                    parsed_result = json.loads(clean_result)
                                    filename = parsed_result.get("filename", "Untitled.md")
                                    
                                    st.markdown("### Outputs from Systematic Reviewer AI")
                                    st.success(f"Obsidian Vault Updated! Created `{filename}` and updated `index.md` & `log.md`.", icon="✅")
                                    
                                except Exception as e:
                                    st.error(f"Error parsing agent output: {e}")
                                    st.info(result, icon="🧠")
                                
                                # Snowballing Extraction
                                try:
                                    with st.spinner("Extracting snowballing references from paper..."):
                                        from chatbot import CitationsList, get_llm
                                        from langchain_core.prompts import ChatPromptTemplate
                                        snowball_prompt = ChatPromptTemplate.from_messages([
                                            ("system", "Extract exactly 5 of the most highly relevant reference titles from the 'References' or 'Bibliography' section of the provided paper text. Focus on Malaysian TVET or related subjects. Return ONLY a JSON list of the titles."),
                                            ("human", "{paper}")
                                        ])
                                        snowball_res = QuotaManager.execute_call(
                                            lambda kwargs: (snowball_prompt | get_llm().with_structured_output(CitationsList)).invoke(kwargs),
                                            {"paper": trimmed_input[-10000:]}
                                        )
                                        st.session_state.snowball_references = snowball_res.citations
                                except Exception as e:
                                    st.warning(f"Could not extract references for snowballing: {e}")
                                
                                st.download_button(
                                    label="📥 Download this result as Markdown",
                                    data=result,
                                    file_name="literature_synthesis.md",
                                    mime="text/markdown"
                                )
                    except KeyError as e:
                        st.error(f"Agent/Task config mismatch: Could not find configuration for {e}. Please check config/agents.yaml or config/tasks.yaml.", icon="⚠️")
                    except ImportError as e:
                        import traceback
                        traceback.print_exc()
                        st.error(f"Dependency changed — please restart the dashboard. (Live upgrade conflict detected: {e})", icon="⚠️")
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        err_msg = str(e) if str(e).strip() else repr(e)
                        st.error(f"An error occurred during analysis: {err_msg}", icon="⚠️")
                    finally:
                        sys.stdout = original_stdout
                        analyze_btn_placeholder.button("🚀 Analyze Paper (Filter & Summarize)", type="primary", use_container_width=True, key="analyze_done")
            else:
                st.info("Awaiting input. Paste a paper on the left to see the agents in action here.", icon="⏳")
                
            if st.session_state.get("snowball_references"):
                st.divider()
                st.subheader("❄️ Snowballing Suggestions")
                st.markdown("Top references extracted from the last analyzed paper. Send them to Scout to find the full papers.")
                
                for i, ref in enumerate(st.session_state.snowball_references):
                    col_ref, col_btn = st.columns([4, 1])
                    with col_ref:
                        st.write(f"**{i+1}.** {ref}")
                    with col_btn:
                        if st.button("Send to Scout", key=f"scout_{i}", use_container_width=True):
                            try:
                                # Append to a queue file that a future scout update could read
                                queue_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "scout_queue.txt")
                                os.makedirs(os.path.dirname(queue_file), exist_ok=True)
                                with open(queue_file, "a", encoding="utf-8") as f:
                                    f.write(ref + "\n")
                                st.toast(f"Added to Scout Queue: {ref[:30]}...")
                            except:
                                st.toast("Sent to Scout!")

    # ---------------- TAB 5: Master Library Data ----------------
    with tab5:
        st.subheader("📚 Master Library Database")
        st.markdown("Your interactive repository for all scouted and analyzed literature.")
        
        st.markdown("### 1. Automated Scout Feed")
        try:
            from src.db.library import LibraryDB
            db = get_library_db()
            data = db._read()
            papers = data.get("papers", [])
            if papers:
                filter_option = st.radio("Filter Papers:", ["All Papers", "Comparison Candidates Only"], horizontal=True)
                
                # Apply filter
                display_papers = []
                if filter_option == "Comparison Candidates Only":
                    for p in papers:
                        assessments = p.get("assessments", [])
                        if assessments:
                            latest_verdict = assessments[-1]["verdict"]
                            if "✅" in latest_verdict or "🟡" in latest_verdict:
                                display_papers.append(p)
                else:
                    display_papers = papers
                    
                st.markdown(f"**Showing {len(display_papers)} papers.**")
                
                # Render as cards
                for i, paper in enumerate(reversed(display_papers)):
                    render_paper_card(paper, f"tab5_{i}")
                
                # Retain the DataFrame creation just for the Export functionality
                df = pd.DataFrame(papers)
                cols = df.columns.tolist()
                preferred_order = ["scouted_at", "year", "title", "authors", "relevance_score", "abstract"]
                final_cols = [c for c in preferred_order if c in cols] + [c for c in cols if c not in preferred_order]
                df = df[final_cols]
                
                if "scouted_at" in df.columns:
                    df = df.sort_values(by="scouted_at", ascending=False)
                
                # Export Options
                st.markdown("### Export")
                col_csv, col_bib = st.columns(2)
                with col_csv:
                    csv_data = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Database as CSV",
                        data=csv_data,
                        file_name='master_library_database.csv',
                        mime='text/csv',
                        use_container_width=True
                    )
                with col_bib:
                    # Generate BibTeX
                    bibtex_str = ""
                    skipped = []
                    for paper in papers:
                        # Only export verified/authentic entries (proxy: has DOI)
                        doi = paper.get("doi", "")
                        if doi and str(doi).strip().lower() not in ["", "nan", "none", "unknown"]:
                            title = paper.get("title", "Unknown")
                            author = paper.get("authors", "Unknown")
                            year = paper.get("year", "Unknown")
                            # Create simple citation key
                            key_author = re.sub(r'[^a-zA-Z]', '', str(author).split(",")[0].split()[0]) if author else "Unknown"
                            key = f"{key_author}{year}"
                            
                            bibtex_str += f"@article{{{key},\n"
                            bibtex_str += f"  title={{{title}}},\n"
                            bibtex_str += f"  author={{{author}}},\n"
                            bibtex_str += f"  year={{{year}}},\n"
                            bibtex_str += f"  doi={{{doi}}}\n"
                            bibtex_str += f"}}\n\n"
                        else:
                            skipped.append(paper.get("title", "Unknown"))
                            
                    if bibtex_str:
                        st.download_button(
                            label="📥 Export as BibTeX (.bib)",
                            data=bibtex_str.encode('utf-8'),
                            file_name='library_export.bib',
                            mime='text/plain',
                            use_container_width=True
                        )
                    else:
                        st.button("📥 Export as BibTeX (.bib)", disabled=True, use_container_width=True)
                        
                    if skipped:
                        with st.expander(f"⚠️ {len(skipped)} entries skipped (Unverified)"):
                            for s in skipped:
                                st.caption(f"- {s}")
                st.markdown("---")
            else:
                st.info("The automated scout database is currently empty.")
        except Exception as e:
            st.error(f"Error loading database: {e}")
            
        st.divider()
        st.markdown("### 2. Manual Analysis History")
        st.caption("Detailed syntheses generated from Tab 4.")
        
        if os.path.exists(md_file):
            with open(md_file, "r", encoding="utf-8") as f:
                md_content = f.read()
            with st.expander("View Full Manual History", expanded=False):
                st.markdown(md_content)
        else:
            st.info("No manual analyses have been saved yet.")
            
        st.divider()
        st.markdown("### 📊 System Statistics")
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        
        total_papers = len(papers) if 'papers' in locals() else 0
        verified_count = sum(1 for p in (papers if 'papers' in locals() else []) if p.get("doi") and str(p.get("doi")).strip().lower() not in ["", "nan", "none", "unknown"])
        verified_pct = f"{(verified_count/total_papers)*100:.1f}%" if total_papers > 0 else "0%"
        
        cache_hits = 0
        try:
            log_path = os.path.join(base_dir, "output", "research_log.md")
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8") as f:
                    cache_hits = f.read().count("CACHE_HIT")
        except: pass
        
        threats_count = 0
        try:
            threat_log = os.path.join(base_dir, "output", "threat_log.md")
            if os.path.exists(threat_log):
                with open(threat_log, "r", encoding="utf-8") as f:
                    threats_count = f.read().count("NOVELTY THREAT")
        except: pass

        col_s1.metric("Total Papers", total_papers)
        col_s2.metric("Verified Citations", verified_pct)
        col_s3.metric("API Cache Hits", cache_hits)
        col_s4.metric("Threats Detected", threats_count)

    # ---------------- TAB 6: System Analytics ----------------
    with tab6:
        st.header("System Analytics & Observability")
        
        # Row 1: Token Stats
        ts = analytics.get_token_stats()
        st.subheader("Usage Statistics")
        col1, col2, col3 = st.columns(3)
        col1.metric("Calls Today", ts['today_calls'], f"Tokens: {ts['today_tokens']}")
        col2.metric("Calls This Week", ts['week_calls'], f"Tokens: {ts['week_tokens']}")
        col3.metric("Total Calls", ts['total_calls'], f"Tokens: {ts['total_tokens']}")
        
        # Row 2: Prefilter & Caching
        ps = analytics.get_prefilter_stats()
        rcs = analytics.get_rejection_and_cache_stats()
        st.subheader("Efficiency Metrics")
        col4, col5, col6 = st.columns(3)
        col4.metric("Prefilter Survival Rate", f"{ps['survival_rate']}%", f"{ps['total_survived']} / {ps['total_in']}")
        col5.metric("Duplicate/Cache Skips", rcs['scout_dedups'] + rcs['cache_hits'], f"Scout: {rcs['scout_dedups']}, Manual: {rcs['cache_hits']}")
        col6.metric("Papers Rejected", rcs['rejections'])
        
        # Budget Estimation vs Actuals
        budget_data = analytics.get_budget_estimates_vs_actuals()
        estimates = budget_data["budget"].get("estimates", {})
        actuals = budget_data["actuals"]
        
        if actuals:
            st.subheader("Estimation Accuracy")
            # For simplicity, we just compare the total actual calls by pipeline
            # If the user averages >20% than estimate, give a warning.
            # In actual_calls, we have the total calls per pipeline, not "calls per paper". 
            # A more detailed computation could be done, but for now we just show raw counts.
            st.markdown("**(Feature under active recalibration mapping)**")
            
        st.divider()
        # Row 3: Weekly Digest
        st.subheader("Weekly Digest")
        if st.button("Generate / Refresh Weekly Digest"):
            digest_content, digest_path = analytics.generate_weekly_digest()
            st.success(f"Digest generated at {digest_path}")
            st.markdown(digest_content)
        else:
            # show latest digest if exists
            import glob
            from datetime import datetime, timedelta
            today = datetime.now()
            start_of_week = today - timedelta(days=today.weekday())
            weekly_dir = os.path.join(analytics.analytics_dir, "weekly")
            out_path = os.path.join(weekly_dir, f"digest_{start_of_week.strftime('%Y_%m_%d')}.md")
            if os.path.exists(out_path):
                with open(out_path, 'r', encoding='utf-8') as f:
                    st.markdown(f.read())
            else:
                st.info("No digest found for this week.")

    # ---------------- TAB 7: Literature Map Verifier ----------------
    with tab7:
        st.header("Literature Map Verifier (Chapter 2)")
        st.markdown("Strictly verify your thematic claims against the actual retrieved literature in the RAG database.")
        
        from src.theme_verifier import verify_theme
        
        themes = {
            "Tema 1": {
                "name": "Tema 1: TPACK-AI framework",
                "desc": "TPACK-AI as a framework for Kolej Vokasional teacher readiness."
            },
            "Tema 2": {
                "name": "Tema 2: Pedagogical AI agents",
                "desc": "Pedagogical AI agents in vocational education."
            },
            "Tema 3": {
                "name": "Tema 3: Teknologi Pembinaan",
                "desc": "Teknologi Pembinaan (CIDB/BIM/construction tech) pedagogy in Kolej Vokasional."
            }
        }
        
        selected_theme = st.selectbox("Select Theme to Verify", list(themes.keys()))
        t_data = themes[selected_theme]
        st.info(f"**Description:** {t_data['desc']}")
        
        if st.button("Run Verification (Costs ~1 Call)", type="primary"):
            with st.spinner("Retrieving RAG chunks and running strict verification..."):
                report_md = verify_theme(t_data['name'], t_data['desc'])
                
                if report_md.startswith("BUDGET_BLOCKED"):
                    st.error(report_md)
                elif "Validation failed entirely" in report_md or "LLM Call Failed" in report_md:
                    st.error(report_md)
                else:
                    st.success("Verification Complete! Report saved to Vault.")
                    with st.expander("View Verification Report", expanded=True):
                        st.markdown(report_md)

if __name__ == "__main__":
    main()
