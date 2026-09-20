import os
import json
import hashlib
import shutil
import tempfile
import glob
import datetime
import re
from filelock import FileLock
from rapidfuzz import fuzz

def _normalize_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'[^\w\s]', '', text)
    return " ".join(text.lower().split())

class LibraryDB:
    def __init__(self, base_dir=None):
        if not base_dir:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.base_dir = base_dir
        self.db_path = os.path.join(base_dir, "output", "library.json")
        self.lock_path = self.db_path + ".lock"
        self.backups_dir = os.path.join(base_dir, "output", "backups")
        self.vault_dir = os.path.join(base_dir, "output", "Obsidian_Vault")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.backups_dir, exist_ok=True)

    def _read(self) -> dict:
        if not os.path.exists(self.db_path):
            return {"papers": []}
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "papers" not in data:
                    return {"papers": []}
                return data
        except Exception:
            return {"papers": []}

    def _write_atomic(self, data: dict, path: str):
        dir_name = os.path.dirname(path)
        os.makedirs(dir_name, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=dir_name, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            os.replace(temp_path, path)
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise e

    def backup(self):
        with FileLock(self.lock_path, timeout=10):
            if not os.path.exists(self.db_path):
                return
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            backup_path = os.path.join(self.backups_dir, f"library_{timestamp}.json")
            
            try:
                shutil.copy2(self.db_path, backup_path)
                
                # Validate JSON parses before pruning
                with open(backup_path, "r", encoding="utf-8") as f:
                    json.load(f)
            except Exception as e:
                print(f"Backup failed to parse as JSON or copy failed: {e}. Pruning aborted.")
                if os.path.exists(backup_path):
                    os.remove(backup_path) # Cleanup invalid backup
                return

            backups = glob.glob(os.path.join(self.backups_dir, "library_*.json"))
            backups.sort(key=os.path.getmtime, reverse=True)
            
            if len(backups) > 14:
                for old_backup in backups[14:]:
                    try:
                        os.remove(old_backup)
                    except Exception:
                        pass

    def check_status(self, title: str) -> dict:
        """Returns None if not found, else dict with status, match_title, confidence, scout_verdict"""
        with FileLock(self.lock_path, timeout=10):
            data = self._read()
            papers = data.get("papers", [])
            norm_target = _normalize_text(title)
            
            if not norm_target:
                return None
                
            # Exact Match First
            for p in papers:
                db_title = p.get("title", "")
                if _normalize_text(db_title) == norm_target:
                    return {
                        "status": p.get("status", "unknown"),
                        "title": db_title,
                        "confidence": 100.0,
                        "scout_verdict": p.get("scout_verdict", "")
                    }
            
            # Fuzzy match
            best_match = None
            best_score = 0
            for p in papers:
                db_title = p.get("title", "")
                score = fuzz.token_sort_ratio(norm_target, _normalize_text(db_title))
                if score > best_score:
                    best_score = score
                    best_match = p
            
            if best_match and best_score >= 92.0:
                return {
                    "status": best_match.get("status", "unknown"),
                    "title": best_match.get("title", ""),
                    "confidence": best_score,
                    "scout_verdict": best_match.get("scout_verdict", "")
                }
            return None

    def exists(self, title: str) -> bool:
        res = self.check_status(title)
        return res is not None

    def append(self, entry: dict) -> bool:
        """Appends a new entry if it doesn't exist."""
        with FileLock(self.lock_path, timeout=10):
            data = self._read()
            papers = data.get("papers", [])
            norm_target = _normalize_text(entry.get("title", ""))
            
            for p in papers:
                if _normalize_text(p.get("title", "")) == norm_target:
                    return False
            
            data["papers"].append(entry)
            self._write_atomic(data, self.db_path)
            return True

    def promote(self, title: str, new_entry: dict) -> bool:
        """Merges new_entry into existing scouted paper."""
        with FileLock(self.lock_path, timeout=10):
            data = self._read()
            norm_target = _normalize_text(title)
            
            # Fuzzy matching isn't used here because we want precise promotion
            # However, the user might provide the fuzzy matched title exactly.
            for p in data.get("papers", []):
                if _normalize_text(p.get("title", "")) == norm_target:
                    p.update(new_entry)
                    p["status"] = "analyzed"
                    p["promoted_date"] = datetime.datetime.now().isoformat()
                    self._write_atomic(data, self.db_path)
                    return True
            return False

    def generate_safe_filename(self, title: str) -> str:
        safe_title = title.replace(" ", "_").replace(":", "").replace("/", "").replace("\\", "")
        safe_title = safe_title.replace("Paper_", "").replace(".md", "")
        filename = f"Paper_{safe_title}.md"
        
        wiki_dir = os.path.join(self.vault_dir, "02_Wiki")
        if os.path.exists(os.path.join(wiki_dir, filename)):
            hash_str = hashlib.sha256(title.encode('utf-8')).hexdigest()[:8]
            filename = f"Paper_{safe_title}_{hash_str}.md"
            
        return filename

    def render_index(self):
        """Rebuilds the index.md atomically from library.json"""
        with FileLock(self.lock_path, timeout=10):
            data = self._read()
            papers = data.get("papers", [])
            
            # Filter for analyzed and RELEVANT
            valid_papers = []
            for p in papers:
                if p.get("status") == "analyzed" and p.get("verdict", "").strip().upper() == "RELEVANT":
                    valid_papers.append(p)
                    
            index_content = "# PhD Wiki Index\n_A catalog of all AI-generated literature concepts._\n\n"
            for p in valid_papers:
                idx = p.get("index_entry", f"[[{self.generate_safe_filename(p.get('title', ''))}]] - {p.get('title', '')}")
                index_content += f"- {idx}\n"
                
            index_path = os.path.join(self.vault_dir, "03_System", "index.md")
            
            dir_name = os.path.dirname(index_path)
            os.makedirs(dir_name, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(dir=dir_name, text=True)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(index_content)
                os.replace(temp_path, index_path)
            except Exception as e:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise e
