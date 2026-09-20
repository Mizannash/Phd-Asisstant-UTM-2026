# PROJECT BLUEPRINT: PhD Assistant

*Document Status: ACTIVE MASTER REFERENCE*
*Path: `D:\PhD_Assistant_UTM\BLUEPRINT.md`*

This is the permanent master reference for the PhD Assistant system. It relies purely on verified facts from the source code. Any future developer, agent, or the user can rely on this document to understand, maintain, and extend the system.

---

## 1. PROJECT STORY & VISION

The PhD Assistant is an autonomous, multi-agent AI system designed to support a PhD thesis focusing on TVET, Kolej Vokasional (KV), and Teknologi Pembinaan in Malaysia. 

- **🌙 The Night Shift (The Autonomous Scout):** Executes automatically at 2:00 AM ONLY IF the "Wake the computer" setting is enabled in Task Scheduler AND a valid `SERPAPI_KEY` is present in the `.env` file. It searches the internet and academic databases, reads abstracts, filters out irrelevant literature, and saves the relevant papers to a JSON database so the researcher never does duplicate work.
- **☀️ The Day Shift (The Interactive Dashboard):** A Streamlit application used during the day to browse the newly scouted literature and chat with an AI advisor to synthesize findings for Chapter 2.

---

## 2. SYSTEM ARCHITECTURE (HOW IT WORKS)

### High-Level Data Flow
```text
[ Task Scheduler (2:00 AM) ]
       │
       ▼
  scout.py ────► [ QuotaManager (4 Gemini Keys, 429/503 Handle) ]
       │
       ▼
 [ CrewAI ] ◄──► [ Tools (SerpApi, OpenAlex, Semantic Scholar) ]
 (Scout & Expert)
       │
       ▼
[ output/library.json ] (Data Storage)
       │
       ▼
[ Streamlit Dashboard ] (Day Shift - dashboard.py)
```

### Data Structures
**The Library (`output/library.json`) Schema:**
The data is stored as a JSON object containing a `"papers"` array and a `"last_scout_date"` string.
*Example Paper Entry:*
```json
{
    "title": "Kompetensi guru dalam pengajaran amali teknologi pembinaan di kolej vokasional",
    "authors": ["Syed Rashid Ali", "Syed Hussin Jaafar"],
    "year": 2014,
    "abstract": "Focusses directly on teacher competency in practical teaching...",
    "relevance_score": 10,
    "scouted_at": "2026-09-02T02:03:36.997049"
}
```
**Scout Log (`output/scout_log.txt`):** Records timestamped pipeline startups, SerpApi query strings, success/paper counts, and clean failure aborts.
**Chat History (`output/chat_history/session_YYYY-MM-DD.json`):** Records Day Shift Streamlit chat messages.

### Project File Map (`src/`)
- `app.py`: Legacy alternative Streamlit entry point (UI for manual CrewAI pipeline).
- `chatbot.py`: Handles the conversational interface and AI Advisor logic for the dashboard.
- `config.py`: Centralized configuration (defines `CREWAI_PRIMARY_MODEL`, `CREWAI_FALLBACK_MODEL`, etc.).
- `dashboard.py`: The primary Streamlit Daytime UI (Library Browser and Chat).
- `library_manager.py`: Safely reads/writes `library.json` and creates rotating `.json` backups.
- `logger.py`: Centralized logging utility for system events.
- `main.py`: CLI entry point for manually running CrewAI pipelines (`--input`, `--supervisor`, `--verify`).
- `quota_manager.py`: Core resilience engine. Handles 4-key rotation, 429/503 backoffs, and fallback triggering.
- `scout.py`: The Night Shift autonomous pipeline. Executes CrewAI agents on a schedule with Date Locks.
- `state_manager.py`: Manages reading/writing `research_context.json` and chat history files.
- `threat_detector.py`: Uses `sentence_transformers` (`all-MiniLM-L6-v2`) to detect if newly found papers overlap heavily with the candidate thesis titles.
- `tools/search_tools.py`: Contains API search tools (OpenAlex, Google Scholar via SerpApi, Web Search via SerpApi). Enforces the strict 1-query limit per task.
- `tools/verifier.py`: Citation verifier tool.
- `utils.py`: Utility functions, including `is_already_analyzed` to prevent duplicate papers.

---

## 3. AGENT ROSTER

**1. Background Literature Scout (`literature_scout`)**
- *Role:* Finds papers via tools.
- *Model:* `gemini-3.7-flash` (primary).
- *Tools:* OpenAlex, Google Scholar, Web Search, Semantic Scholar.
- *Purpose:* Searches web/databases for TVET & Kolej Vokasional keywords to gather raw paper data.

**2. Strict TVET Domain Filter (`tvet_domain_expert` / The Scope Guardian)**
- *Role:* Aggressively filters incoming literature.
- *Model:* `gemini-3.7-flash` (primary).
- *Tools:* None (Analytical).
- *Purpose:* Ruthlessly discards Indonesian SMK, secondary school RBT, Politeknik, ILP, or IPT papers. Enforces the strict **Kolej Vokasional + Teknologi Pembinaan** anchor. Formats passing papers as JSON.

**3. UTM PhD Co-Supervisor (`phd_co_supervisor`)**
- *Role:* Chat advisor for the researcher.
- *Model:* `gemini-3.7-flash`.
- *Tools:* None.
- *Purpose:* Challenges academic rigor, novelty, and feasibility. Understands fast-track constraints (12 months, 3-5 KV access). Is strictly methodology-neutral.

**4. TVET Literature Screener & Synthesizer (`systematic_reviewer`)**
- *Role:* Used in manual pipeline (`main.py` / `app.py`).
- *Model:* `gemini-3.7-flash`.
- *Tools:* Search tools.
- *Purpose:* Evaluates relevance and structures findings into APA 7 citations and synthesis notes.

---

## 4. RESILIENCE ENGINEERING (THE BATTLE SCARS)

1. **Multi-Key QuotaManager (`quota_manager.py`)**
   - Loads 4 Gemini keys. Catches `429` (Quota/Rate Limit) errors and hot-swaps the `GEMINI_API_KEY` to the next available key without crashing the pipeline. 
   - Exits cleanly if `all_keys_exhausted()` is true.
2. **503 Backoff & FRESH-Crew Fallback (`scout.py` & `quota_manager.py`)**
   - On `503 Overloaded` errors, backs off for 15s → 30s → 60s.
   - If 3 server errors occur, it triggers a **FRESH-Crew fallback** to `gemini-3.5-flash-lite`.
   - *The Dirty-State Bug Fix:* The system is hard-capped to 2 full attempts, and the `Crew` object is recreated *fresh* inside the loop to prevent the CrewAI dirty-state `400 Bad Request` bug.
3. **Date Lock (`scout.py`)**
   - Reads `last_scout_date` from `library.json`. If it matches today, the scout aborts to prevent double-runs.
   - *Clean-Abort Logging:* If the scout crashes, it logs the error but explicitly does NOT falsely update the Date Lock, allowing safe retries.
4. **SerpApi Call Discipline (`search_tools.py`)**
   - The `@tool` descriptions strictly enforce: *"Perform a MAXIMUM of 1 search query per task."*
   - Each Google Scholar/Web query is logged directly to `scout_log.txt` *before* the API call, enabling accurate usage audits.

---

## 5. FUNCTION REFERENCE (THESIS MAPPING)

- **Literature Discovery (Scout):** Serves **Chapter 2 (Literature Review)**. Automates the grueling process of finding and extracting relevant abstracts.
- **Scope Filtering (Domain Expert):** Serves **Proposal Phase & Gap Defense**. Ensures the literature anchor (KV + Teknologi Pembinaan) remains unpolluted, keeping the thesis highly focused.
- **Novelty Threat Detection (`threat_detector.py`):** Serves **Proposal Phase**. Alerts the researcher if a newly published paper is too similar (semantically) to their proposed title, protecting the research gap.
- **Advisor Synthesis (Chatbot):** Serves **Chapter 2 & Chapter 3**. Helps synthesize reading materials into arguments and brainstorms methodology trade-offs safely.
- **Debate Mode:** Serves **Chapter 3 (Methodology)**. Two agents arguing opposing viewpoints on a methodology choice, presented in the UI, complete with "Confirm-then-write" UI verification.
- **Research Context Registry (`state_manager.py`):** Serves **Chapter 1 & 3**. A dashboard interface that permanently saves research parameters (sample size, methodology). The Advisor dynamically reads this and can propose "Confirm-then-write" JSON updates during debates.
- **Persistent Chat Memory:** Serves **Continuous Synthesis**. Saves all Advisor interactions to `output/chat_history/` daily logs, ensuring long-term continuity across dashboard reboots.

---

## 6. USER MANUAL — USING THE SYSTEM AS A PhD STUDENT

**1. Morning Routine**
- Open `D:\PhD_Assistant_UTM\output\scout_log.txt`.
- *Success:* You will see `Scout started.` followed by `Scout complete. Found X new papers.`
- *Failure:* You will see `Scout crashed with error: ALL API KEYS EXHAUSTED.` (In this case, do nothing; wait for tomorrow's quota reset).
- Open the dashboard, go to the "Library" tab, and review the new papers.

**2. Chatting with the Advisor**
- Open the "Advisor" tab in the dashboard.
- Example prompts: *"Synthesize the 3 most recent papers in the library regarding AR in construction."* or *"What are the data-access trade-offs between DDR and a Quantitative Survey for a 12-month timeline?"*

**3. Manual Execution**
- Start Dashboard: `cd /d D:\PhD_Assistant_UTM && set PYTHONPATH=D:\PhD_Assistant_UTM\src && venv\Scripts\streamlit run src\dashboard.py --server.port 8506`
- Start Scout (Manual): `cd /d D:\PhD_Assistant_UTM && set PYTHONPATH=D:\PhD_Assistant_UTM\src && venv\Scripts\python src\scout.py` *(Note: A manual run counts as today's run; the Date Lock will skip tonight's 2 AM scheduled run).*
- Manual Backup: Double click `D:\PhD_Assistant_UTM\backup.bat`.

**4. What NOT to Do**
- Do NOT edit `.env` key variable names (they must be `GEMINI_API_KEY_1`, `_2`, etc.).
- Do NOT delete `library.json` (you will lose your Date Lock and all saved papers).
- Do NOT edit files in the `scratch/` backup folder. `D:\PhD_Assistant_UTM` is the ONLY active root.

---

## 7. OPERATIONS RUNBOOK

1. **Morning Health Check:** Audit `scout_log.txt` daily for successes or API exhaustion.
2. **SerpApi Budget Rule:** The free tier is exactly 100 searches/month. Count the `[SerpApi] Query:` lines in `scout_log.txt`. If it averages **>3 calls per run**, switch the Windows Task Scheduler to every 2nd night.
3. **Backup Policy:** The system automatically runs `backup.bat` every Sunday at 3:00 AM. 
   - **Target:** `C:\Users\user\OneDrive\PhD_Backups\PhD_Assistant_UTM`
   - If the OneDrive parent folder is missing or disconnected, the backup aborts safely. The script automatically excludes `venv\` to save space and sync time.
4. **Disaster Recovery (New PC):** 
   - Copy the latest backup from `C:\Users\user\OneDrive\PhD_Backups\PhD_Assistant_UTM` to your new machine's `D:\PhD_Assistant_UTM`.
   - Run: `python -m venv venv` and `venv\Scripts\pip install -r requirements.txt`.
   - Right-click and Run as Administrator on `setup_scout_task.bat` and `setup_backup_task.bat`.
   - Verify `.env` has the keys.

---

## 8. CONFIGURATION REFERENCE

- **`.env` Variables:** `GEMINI_API_KEY_1`, `GEMINI_API_KEY_2`, `GEMINI_API_KEY_3`, `GEMINI_API_KEY_4`, `OPENALEX_MAILTO`, `SERPAPI_KEY`.
- **`config.py`:**
  - `CREWAI_PRIMARY_MODEL`: `gemini/gemini-3.7-flash`
  - `CREWAI_FALLBACK_MODEL`: `gemini/gemini-3.5-flash-lite`
  - `LANGCHAIN_PRIMARY_MODEL`: `gemini-3.7-flash`
- **Windows Scheduled Tasks:**
  - `PhD_Assistant_Scout`: Runs daily at 2:00 AM.
  - `PhD_Assistant_Backup`: Runs Sunday at 3:00 AM.

---

## 9. KNOWN ISSUES & LIMITATIONS (HONEST LEDGER)

- **Manual Dashboard Workflow:** The dashboard is run manually by the user via `start_dashboard.bat` (port 8506), not as an Antigravity background task. After any code edit to `dashboard.py` or core files, the system must instruct the user to restart the dashboard to pick up changes.
- **Verified Live End-to-End:** The Scout has successfully completed live end-to-end runs. `crewai` and `litellm` dependencies were upgraded to latest.
- **CrewAI 400 Bug Mitigation:** The system now catches and suppresses the LiteLLM `forced-final-answer` 400 bad request bug without crashing.
- **Robust Backoff:** 503/429 QuotaManager backoff upgraded to 5-tier jittered exponential wait (`[30, 60, 120, 120, 120]`).
- **Semantic Scholar Limits:** Integrated `SEMANTIC_SCHOLAR_API_KEY` with a custom backoff loop respecting 429 `Retry-After`.
- **SerpApi Ceiling:** The 100 searches/month free tier is a hard limit; if the agents hallucinate loops, it exhausts rapidly.
- **Live Upgrade Ghost Cache:** After upgrading dependencies (`crewai`, `litellm`, etc.), **ALWAYS restart the dashboard** — live upgrades cause stale `sys.modules` ImportErrors (e.g., `cannot import name LLMCallBlockedError`).
- **Peak-Hour 503s:** The 2:00 AM MYT run coincides with US daytime peak hours, increasing the likelihood of Google Gemini 503 Overloaded errors (mitigated by the FRESH-Crew fallback, but still a factor).

---

## 10. FUTURE ROADMAP (DESIGNED, NOT BUILT)

- **Bahasa Melayu Support:** Native system prompts enforcing Malay language generation for thesis drafting.
- **Proactive Fast-Track Mentor:** An agent that analyzes the Date Lock and timeline, actively suggesting "Langkah Seterusnya" (Next Steps) in the UI.
- **Assess-for-Comparison & Comparison Ledger:** A feature to flag papers specifically for methodology comparison, building a distinct ledger separate from the main library.

---

## 11. VERSION HISTORY (THE ORIGIN STORY)

- **Phase 1 (The Exhaustion Saga):** Initial single-key design repeatedly crashed during overnight runs due to Gemini rate limits.
- **Phase 2 (The QuotaManager):** Implemented a 4-key hot-swap system.
- **Phase 3 (AppTest Verification):** System modularized and verified via UI.
- **Phase 4 (The 503 Fallback & Dirty-Crew Fix):** Discovered that Google 503s caused CrewAI to enter a dirty `400 Bad Request` state upon retry. Engineered the 2-attempt hard cap and FRESH-crew recreation loop, falling back to Flash-Lite.
- **Phase 5 (Migration to D: & Dual-Path):** System moved to `D:\PhD_Assistant_UTM` and locked down. Implemented `last_scout_date` to prevent double-runs. 
- **Phase 6 (Dependency & Tool Audit):** Performed a full environment validation and discovered SerpApi keys were required. Added strict query-limit instructions and query logging to protect the SerpApi 100/month free tier.
- **Phase 7 (Blueprint & Final Verification):** Created BLUEPRINT.md; proved backup automation and SerpApi discipline are actually built; corrected documented facts against reality.
- **Phase 8 (The Maiden Voyage & Robustness Upgrade):** Executed the first live end-to-end run. Upgraded `crewai` and `litellm`. Implemented 5-tier jittered backoff for 503/429 errors. Added Semantic Scholar API key support and 429 retries. Caught and suppressed the 400 dirty-state bug. Silenced Streamlit warnings for headless runs.

---
*End of Blueprint.*

## 12. TESTING CONVENTIONS
- **Always run tests after touching core logic (scout.py, quota_manager.py, dashboard.py):**
  - Run python -m unittest tests.test_features from the project root.
  - Run python -m unittest tests.test_backoff from the project root.
