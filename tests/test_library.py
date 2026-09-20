import pytest
import os
import sys
import subprocess
import time
import json

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from src.db.library import LibraryDB

@pytest.fixture
def temp_db(tmp_path):
    db = LibraryDB(base_dir=str(tmp_path))
    return db

def test_append_duplicate(temp_db):
    entry = {"title": "Unique Title", "status": "scouted"}
    assert temp_db.append(entry) is True
    assert temp_db.append(entry) is False
    
    entry2 = {"title": "UNIQUE TITLE", "status": "analyzed"}
    assert temp_db.append(entry2) is False

def test_promote_merge(temp_db):
    entry = {
        "title": "Promote Me",
        "status": "scouted",
        "scout_verdict": "Very good",
        "source": "OpenAlex",
        "doi": "10.1234/test"
    }
    temp_db.append(entry)
    
    new_analysis = {
        "verdict": "RELEVANT",
        "content": "APA citation..."
    }
    assert temp_db.promote("Promote Me", new_analysis) is True
    
    res = temp_db.check_status("Promote Me")
    assert res is not None
    assert res["status"] == "analyzed"
    
    data = temp_db._read()
    p = data["papers"][0]
    assert p["status"] == "analyzed"
    assert p["source"] == "OpenAlex"
    assert p["verdict"] == "RELEVANT"
    assert "promoted_date" in p

def test_backup_pruning(temp_db):
    # Ensure db_path exists so backup runs
    temp_db.append({"title": "Test DB", "status": "scouted"})
    
    # Mock datetime to create different files fast
    for i in range(20):
        # We just touch files directly to simulate backups
        file_path = os.path.join(temp_db.backups_dir, f"library_{i}.json")
        with open(file_path, "w") as f:
            f.write('{"papers": []}')
        time.sleep(0.01)
        
    temp_db.backup() # This will create the 21st and then prune down to 14
    
    backups = os.listdir(temp_db.backups_dir)
    assert len(backups) == 14
    
def test_backup_invalid_json(temp_db):
    with open(temp_db.db_path, "w") as f:
        f.write("{invalid json")
        
    temp_db.backup() 
    
    backups = os.listdir(temp_db.backups_dir)
    assert len(backups) == 0

def test_concurrent_writes(tmp_path):
    base_dir = str(tmp_path)
    script = os.path.join(os.path.dirname(__file__), "concurrent_test_script.py")
    
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    
    p1 = subprocess.Popen([sys.executable, script, "1", base_dir], env=env)
    p2 = subprocess.Popen([sys.executable, script, "2", base_dir], env=env)
    
    p1.wait()
    p2.wait()
    
    db = LibraryDB(base_dir=base_dir)
    data = db._read()
    assert len(data.get("papers", [])) == 40
