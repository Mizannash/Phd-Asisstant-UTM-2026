 # 🎓 PhD Assistant UTM: Project Recap Report

This report serves as a complete module overview of the **CrewAI Research Assistant** built from the ground up. The system is designed specifically for a PhD researcher at UTM focusing on **Malaysian TVET (Technical and Vocational Education and Training) and Kolej Vokasional (KV)**, specifically in *Teknologi Pembinaan*.

---

## 🏗️ 1. Core Architecture & Technologies
- **Frameworks**: Built using **CrewAI** for multi-agent orchestration, **Streamlit** for the frontend dashboard, and **LangChain** for chatbot memory.
- **LLM Engine**: Powered exclusively by **Google Gemini 3.7 Flash** (Free Tier), making it fast and highly intelligent, with a lightweight fallback to `gemini-3.5-flash-lite`.
- **Centralized Configuration**: All model strings are managed globally in `src/config.py` to prevent configuration drift and ensure 100% compatibility across the stack.

---

## 🛡️ 2. Resilience & Quota Management

### ✅ VERIFIED BEHAVIORS (Tested Live)
- **Centralized Configuration**: All model strings are managed globally in `src/config.py`.
- **4-Key Multi-Account Pool**: The system loads 4 API keys dynamically. Since free-tier daily quotas (limit 20) are enforced per-project, these keys must come from 4 *different* Google accounts to provide a true combined daily budget of ~80 requests.
- **Intelligent Key Rotation**: If a key hits its Daily Quota Limit (429), the system correctly records the exact reason and rotates to the next available key (e.g., Key 2, Key 3, Key 4).
- **Self-Healing Recovery Probe**: If all keys are marked as exhausted, it fires a direct REST probe to the `gemini-3.7-flash` endpoint. Exhaustion flags automatically reset on a new calendar day.
- **Transparent Diagnostics**: If the probe fails, the system outputs the exact failure reason for every single key (e.g., `Key 1: Daily Quota limit`), effectively eliminating silent crashes.
- **Model Fallback**: The fallback model `gemini-3.5-flash-lite` exists and responds with 200 OK. It acts as the final safety net when all 4 primary keys are drained.
- **5-Tier Jittered Backoff (503/429)**: The logic to wait and retry on the exact same API key during Google server overloads is fully implemented and tested with a 5-tier jittered exponential wait (`[30, 60, 120, 120, 120]`).
- **CrewAI 400 Bug Mitigation**: The system catches and suppresses the LiteLLM `forced-final-answer` 400 bad request bug without crashing.
- **Semantic Scholar Support**: Integrated API key with a custom backoff loop respecting 429 `Retry-After`.

### ⚠️ IMPLEMENTED BUT UNVERIFIED BEHAVIORS
*(None at this time; live end-to-end runs successfully completed.)*

---

## 🤖 3. The AI Agents
The system utilizes a team of specialized AI agents acting as a rigorous academic committee:
1. **The Background Literature Scout**: Armed with internet search tools, this agent continuously hunts for the latest publications across academic databases.
2. **The TVET Domain Expert**: A ruthless filter. It rejects generic technology adoption studies (like TAM/UTAUT) and strictly demands pedagogical rigor and direct relevance to the Malaysian Kolej Vokasional context.
3. **The Relevance Checker AI**: Evaluates manually submitted papers and ranks them out of 10 based on their usefulness to the thesis.
4. **The Literature Summarizer AI**: Extracts methodologies, findings, and explicit research gaps from highly relevant papers.
5. **The Exacting PhD Co-Supervisor**: A conversational persona that brutally critiques research proposals, ensuring extreme academic rigor and alignment with the KV scope.

---

## 🛠️ 4. Integrated Search Tools (`src/tools/search_tools.py`)
To bypass basic web scraping blocks, the agents are equipped with specialized search APIs:
- **OpenAlex Search**: Directly queries the OpenAlex academic database for open-access scholarly articles, filtering by publication date and relevance.
- **Google Scholar Search (SerpApi)**: Scrapes Google Scholar for high-impact citations and papers.
- **Google Web Search (SerpApi)**: Performs broad internet queries to find grey literature, policy documents (like KPM guidelines), and news.
- **Semantic Scholar Search**: Enhances discovery with deep semantic matching for academic papers.

---

## 🖥️ 5. The 5-Tab Command Center Dashboard
The `src/dashboard.py` file serves as the interactive UI for the entire system, divided into 5 powerful modules:

### 💬 Tab 1: Research Chatbot & Advisor
- A persistent chat interface where you can debate methodologies, ask for gap matrices, or test your hypotheses against the strict PhD Co-Supervisor persona.
- Features a **Semantic Threat Scan** button to bulk-analyze your entire historical library for overlapping studies that could destroy your research gap novelty.

### 📡 Tab 2: The Daily Radar (Scout)
- Displays a feed of papers discovered by the Background Scout.
- Intelligently splits findings into **🌟 Today's Latest Discoveries** and **📚 Previous Discoveries**.
- Includes a **"Trigger Scout Manually"** button to force the agents to hunt for new papers immediately, complete with real-time threaded terminal outputs showing the CrewAI execution directly in the UI.

### 🎯 Tab 3: Title & Gap Studio
- The **Thesis Title Leaderboard**.
- At the click of a button, the AI analyzes all the gaps found in your library and generates novel, highly defensible thesis titles.
- Titles are scored out of 10 for novelty and color-coded (Green for great, Red for weak).

### 🧠 Tab 4: Literature Command Center
- **Manual Paper Analysis**: Upload a **PDF**, paste raw text, or provide a **Web Link**. The agents will read the paper, score it, and summarize the gaps.
- **Supervisor Priority**: A checkbox to flag a paper as highly important.
- **Chapter 2 Generator**: A dedicated button to synthesize your entire saved library into a cohesive *APA 7th Edition Literature Review Draft* which can be downloaded as a Markdown file.

### 📚 Tab 5: Master Library Data
- The central repository for all saved data.
- **Automated Scout Feed**: Displays `library.json` in an interactive, Excel-style DataFrame where you can sort by year, relevance, or title. Includes a button to **Download as CSV**.
- **Manual Analysis History**: A cleanly formatted archive of every paper you manually uploaded and analyzed via Tab 4 (saved to `library.md`).

---

## ⚙️ 6. Automation & Background Jobs
- **The Dual-Path 2 AM Scout**: The background scout (`src/scout.py`) is designed to run automatically at 2:00 AM every day. It uses a dual-path architecture:
  1. **Primary OS Task**: A Windows Task Scheduler job executes the script cleanly in the background.
  2. **Secondary In-App Daemon**: An `APScheduler` daemon runs within the Streamlit dashboard as a fallback in case the OS task fails or is skipped, ensuring the scout runs if the app is left open.
- Both paths are protected by a strict Date Lock on `library.json` (preventing double execution) and a Pre-Flight Quota Guard that safely aborts the run if all API keys are exhausted, logging the outcome to `scout_log.txt`.

## 🚨 7. Known Issues & Live Verification Status
- **Live Verification**: **[PASSED]**. Live end-to-end runs have successfully completed. The scout effectively extracts papers, rotates keys, and handles limits.
- **CrewAI 400 Bug Mitigation**: The system catches and suppresses the LiteLLM `forced-final-answer` 400 bad request bug without crashing.
- **Aggressive Rate-Limiting**: Frequent or heavy sequential LLM calls (especially testing loops) will rapidly hit the 15 RPM (Requests-Per-Minute) Google free tier limit. 503/429 QuotaManager backoff upgraded to 5-tier jittered exponential wait.
- **Known Issue - Quota Pools**: Primary-model daily budget is ~80 requests across 4 keys (assuming separate Google accounts); one scout run consumes 10-20. The lite fallback model has a separate pool.
- **SerpApi Ceiling**: The 100 searches/month free tier is a hard limit; if the agents hallucinate loops, it exhausts rapidly.
- **Live Upgrade Ghost Cache**: After upgrading dependencies (`crewai`, `litellm`, etc.), **ALWAYS restart the dashboard** — live upgrades cause stale `sys.modules` ImportErrors.
- **Peak-Hour 503s**: The 2:00 AM MYT run coincides with US daytime peak hours, increasing the likelihood of Google Gemini 503 Overloaded errors (mitigated by the FRESH-Crew fallback).

## 🧪 8. Testing Conventions
- **Always run tests after touching core logic (`scout.py`, `quota_manager.py`, `dashboard.py`):**
  - Run `python -m unittest tests.test_features` from the project root.
  - Run `python -m unittest tests.test_backoff` from the project root.

## 🚀 9. Next Steps & Future Expansions
Future improvements could include:
- Expanding the AI's ability to read larger books by chunking PDFs.
- Fine-tuning the background scout with specific keyword triggers dynamically adjusted by your chat history.
