# 🎓 PhD Assistant UTM
> **A Systematic Review & Novelty Protection System**

This system is **production-ready for single-user local use**, designed specifically for fast-track PhD researchers who need to scout, synthesize, and organize literature while defending their thesis gap.

## 🚀 Quick Start
To launch the Command Center dashboard, simply double-click the **`run_dashboard.bat`** file in the root directory. This will automatically activate the Python virtual environment and start the Streamlit server.

To instantly open your AI-generated Knowledge Vault in Obsidian, double-click the **`open_second_brain.bat`** file.

## System Statistics
| Metric | Count |
|--------|-------|
| **Total Papers in Library** | `[Placeholder: E.g. 154]` |
| **Verified Citations (%)** | `[Placeholder: E.g. 98.2%]` |
| **API Cache Hits Saved** | `[Placeholder: E.g. 1,023]` |
| **Novelty Threats Detected** | `[Placeholder: E.g. 3]` |

## Core Architecture
- **CrewAI Core:** Uses multiple autonomous agents (Scout, Domain Filter, Systematic Reviewer, PhD Co-Supervisor).
- **LLM Engine:** Powered by **Google Gemini 1.5 Flash** (Free Tier) to keep costs near zero.
- **Novelty Defense:** Semantic AI (`sentence-transformers`) running locally on your CPU monitors all incoming papers to ensure your final title remains novel.
- **Safety First:** Modifying the library automatically triggers a JSON validity check and saves a backup. 

## Data Backups (Retention Policy)
Every time a modification is made to the library, a timestamped snapshot is stored in `output/backups/`. 
> The system strictly retains the **10 most recent backups** and automatically prunes any older backups to save disk space.
