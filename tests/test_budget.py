import pytest
import os
import json
import datetime
from filelock import FileLock
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from src.quota.budget import BudgetManager, get_myt_date

@pytest.fixture
def temp_budget(tmp_path):
    bm = BudgetManager(base_dir=str(tmp_path))
    return bm

def test_budget_blocking(temp_budget):
    # limit is 80 by default. Set usage to 78.
    data = {"date": get_myt_date(), "gemini_used": 78, "groq_used": 0}
    temp_budget._write_budget(data)
    
    assert temp_budget.can_afford(1, provider="gemini") is True
    assert temp_budget.can_afford(3, provider="gemini") is False
    assert temp_budget.can_afford(5, provider="groq") is True # Groq limit is 400

def test_spend_accounting(temp_budget):
    data = {"date": get_myt_date(), "gemini_used": 10, "groq_used": 20}
    temp_budget._write_budget(data)
    
    temp_budget.spend(5, provider="gemini")
    temp_budget.spend(15, provider="groq")
    
    rem = temp_budget.remaining()
    assert rem["gemini"]["used"] == 15
    assert rem["groq"]["used"] == 35

def test_midnight_reset_simulation(temp_budget):
    # Simulate data from yesterday
    yesterday = (datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))) - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    data = {"date": yesterday, "gemini_used": 80, "groq_used": 400}
    temp_budget._write_budget(data)
    
    # Should automatically reset on next check
    assert temp_budget.can_afford(5, provider="gemini") is True
    assert temp_budget.can_afford(10, provider="groq") is True
    
    rem = temp_budget.remaining()
    assert rem["gemini"]["used"] == 0
    assert rem["groq"]["used"] == 0
    assert rem["reset_date_myt"] == get_myt_date()

def test_dev_mode_isolation(temp_budget):
    # We test isolation logic by verifying the mode state
    temp_budget.set_mode(dev_mode=True, dev_mock=False)
    mode = temp_budget.get_mode()
    assert mode["dev_mode"] is True
    assert mode["dev_mock"] is False
    
    temp_budget.set_mode(dev_mode=False, dev_mock=True)
    mode = temp_budget.get_mode()
    assert mode["dev_mode"] is False
    assert mode["dev_mock"] is True
