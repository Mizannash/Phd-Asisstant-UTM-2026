import sys
import time
from src.db.library import LibraryDB

def run(pid, base_dir):
    db = LibraryDB(base_dir=base_dir)
    for i in range(20):
        entry = {
            "title": f"Process_{pid}_Paper_{i}",
            "status": "scouted"
        }
        db.append(entry)
        time.sleep(0.01)

if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])
