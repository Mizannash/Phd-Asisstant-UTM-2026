import os
import json
import sys

STATE_FILE = os.path.join("data", "library_state.json")
BACKUP_LIBRARY_FILE = os.path.join("output_backup", "library.json")

class LibraryState:
    def __init__(self):
        self.state_file = STATE_FILE
        self.state = {
            "papers": [],
            "gaps": [],
            "titles": []
        }
        self.load_state()

    def load_state(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r', encoding='utf-8') as f:
                self.state = json.load(f)

    def save_state(self):
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, indent=4)
        
        # Removed StorageHandler.push_state to prevent Streamlit Cloud from restarting the app.

    def migrate_from_backup(self):
        if not os.path.exists(BACKUP_LIBRARY_FILE):
            print("No backup library found to migrate.")
            return

        with open(BACKUP_LIBRARY_FILE, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
            
        old_papers = old_data.get("papers", [])
        
        migrated_papers = []
        dropped_papers = []
        reasons = {}

        for p in old_papers:
            if not p.get("title"):
                dropped_papers.append(p)
                reasons[p.get("title", "Unknown")] = "Missing title"
                continue
            
            # Normalize authors to list
            authors = p.get("authors", [])
            if isinstance(authors, str):
                authors = [a.strip() for a in authors.split(",")]
                
            new_p = {
                "title": p.get("title"),
                "authors": authors,
                "year": p.get("year"),
                "abstract": p.get("abstract", ""),
                "relevance_score": p.get("relevance_score", 0),
                "scouted_at": p.get("scouted_at", "")
            }
            migrated_papers.append(new_p)

        self.state["papers"] = migrated_papers
        self.state["titles"] = [p["title"] for p in migrated_papers]
        self.save_state()

        print("=== Library Migration Reconciliation Report ===")
        print(f"Total old papers: {len(old_papers)}")
        print(f"Total migrated: {len(migrated_papers)}")
        print(f"Total dropped: {len(dropped_papers)}")
        
        if dropped_papers:
            print("Reasons for dropped papers:")
            for title, reason in reasons.items():
                print(f" - {title}: {reason}")

        if len(old_papers) != len(migrated_papers) + len(dropped_papers):
            print("ERROR: Unexplained mismatch in paper counts!")
            sys.exit(1)
            
        print("Migration successful.")

    def migrate_threats(self):
        threat_log_file = os.path.join("output_backup", "threat_log.md")
        if not os.path.exists(threat_log_file):
            print("No threat log found to migrate.")
            return

        threats = []
        with open(threat_log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        current_threat = None
        for line in lines:
            line = line.strip()
            if line.startswith("- **["):
                # New threat
                if current_threat:
                    threats.append(current_threat)
                
                # Parse timestamp and text
                try:
                    timestamp_end = line.index("]**")
                    timestamp = line[5:timestamp_end]
                    text = line[timestamp_end+3:].strip()
                    current_threat = {
                        "date": timestamp,
                        "text": text,
                        "details": []
                    }
                except ValueError:
                    pass
            elif line.startswith("- **") and current_threat:
                current_threat["details"].append(line)
                
        if current_threat:
            threats.append(current_threat)
            
        self.state["threats"] = threats
        self.save_state()
        print(f"=== Threat Migration Reconciliation Report ===")
        print(f"Total threats migrated: {len(threats)}")

library_state = LibraryState()

if __name__ == "__main__":
    library_state.migrate_from_backup()
