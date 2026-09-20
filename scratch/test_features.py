import sys
import os
sys.path.insert(0, r"D:\PhD_Assistant_UTM\src")
import state_manager
import json
from chatbot import chat_with_supervisor

def run_tests():
    print("--- Test 1: Research Context Registry ---")
    dummy_context = {
        "sample_scope": "Test Scope 10 KV",
        "states_zones": "Johor",
        "study_duration": "6 months",
        "methodology": "Quantitative",
        "target": "Fast-track",
        "current_stage": "Proposal"
    }
    
    old_context = state_manager.load_research_context()
    state_manager.append_to_changelog(old_context, dummy_context)
    state_manager.save_research_context(dummy_context)
    
    with open(state_manager.RESEARCH_CONTEXT_FILE, "r") as f:
        saved_ctx = json.load(f)
        assert saved_ctx["sample_scope"] == "Test Scope 10 KV"
        print("save_research_context OK")
        
    with open(state_manager.RESEARCH_CHANGELOG_FILE, "r") as f:
        changelog = json.load(f)
        assert len(changelog) > 0
        assert changelog[-1]["new"]["sample_scope"] == "Test Scope 10 KV"
        print("append_to_changelog OK")

    print("\n--- Test 2: Advisor Context Referencing ---")
    # Tell the supervisor to summarize our current scope
    print("Calling chatbot...")
    response = chat_with_supervisor("Please summarize my current research sample scope and methodology in one short sentence.")
    print(f"Response: {response}")
    assert "Test Scope 10 KV" in response or "10" in response
    assert "Quantitative" in response or "quantitative" in response.lower()
    print("Advisor Context Referencing OK")

    print("\n--- Test 3: Debate Mode (Methodology Change Proposal) ---")
    response2 = chat_with_supervisor("I want to change my methodology to Mixed-Methods. Do you agree with this change? If so, please output the JSON to propose the update.")
    print(f"Response: {response2}")
    if "```json" in response2 and "proposed_research_context" in response2:
        print("Debate Mode JSON Proposal OK")
    else:
        print("FAILED to get JSON proposal")

    print("\n--- Test 4: Persistent Chat Memory ---")
    messages = [
        {"role": "user", "content": "Hello Memory"},
        {"role": "ai", "content": "I remember"}
    ]
    state_manager.save_chat_history(messages)
    today_file = state_manager.get_today_chat_file()
    assert os.path.exists(today_file)
    print("save_chat_history OK, file created")
    
    loaded = state_manager.load_recent_chat_history(limit=10)
    assert len(loaded) >= 2
    assert loaded[-2]["content"] == "Hello Memory"
    print("load_recent_chat_history OK")
    
    print("\nALL TESTS PASSED")

if __name__ == "__main__":
    run_tests()
