import pytest
import os
import sys
import shutil
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from src.analytics import SystemAnalytics
from datetime import datetime

@pytest.fixture
def analytics_instance(tmp_path):
    # Mock the paths in SystemAnalytics
    analytics = SystemAnalytics()
    
    # We will use tmp_path as the base_dir
    analytics.base_dir = str(tmp_path)
    analytics.analytics_dir = os.path.join(analytics.base_dir, "output", "analytics")
    os.makedirs(analytics.analytics_dir, exist_ok=True)
    
    return analytics

def test_missing_csv_robustness(analytics_instance):
    # CSVs don't exist yet, should not crash
    ts = analytics_instance.get_token_stats()
    assert ts["total_calls"] == 0
    assert ts["total_tokens"] == 0
    
    ps = analytics_instance.get_prefilter_stats()
    assert ps["total_in"] == 0
    assert ps["total_survived"] == 0
    
    rcs = analytics_instance.get_rejection_and_cache_stats()
    assert rcs["cache_hits"] == 0
    assert rcs["rejections"] == 0

def test_csv_parsing(analytics_instance):
    # Write some dummy CSVs
    import csv
    with open(os.path.join(analytics_instance.analytics_dir, "actual_calls.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "Pipeline", "Total_Tokens"])
        writer.writerow([datetime.now().isoformat(), "test_pipeline", "1000"])
        
    ts = analytics_instance.get_token_stats()
    assert ts["total_calls"] == 1
    assert ts["total_tokens"] == 1000

def test_digest_generation(analytics_instance):
    digest, path = analytics_instance.generate_weekly_digest()
    assert "Weekly System Digest" in digest
    assert os.path.exists(path)

def test_rejection_audit_parsing(analytics_instance):
    vault_dir = os.path.join(analytics_instance.base_dir, "output", "Obsidian_Vault", "03_System")
    os.makedirs(vault_dir, exist_ok=True)
    audit_path = os.path.join(vault_dir, "rejection_audit.md")
    
    with open(audit_path, "w", encoding="utf-8") as f:
        f.write("# Rejection Audit\n\n| Timestamp | Title | Score | Reasoning |\n| --- | --- | --- | --- |\n")
        f.write("| 2026-09-14 | Bad Paper | 2 | Not relevant |\n")
        f.write("| 2026-09-14 | Another Bad Paper | 3 | Out of scope |\n")
        
    rcs = analytics_instance.get_rejection_and_cache_stats()
    assert rcs["rejections"] == 2
