import os
import sys
import json
import time

# Ensure we're in the right directory
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from chatbot import chat_with_supervisor
import state_manager

def run_tests():
    print("--- Starting Conversational Advisor Test ---")
    
    # 1. Setup a fresh context
    test_context = {
        "sample_scope": "Testing 5 KVs",
        "states_zones": "Johor only",
        "study_duration": "6 months",
        "methodology": "Qualitative",
        "target": "Fast-track 2026",
        "current_stage": "Proposal"
    }
    state_manager.save_research_context(test_context)
    
    chat_history = []
    
    # Turn 1: Bahasa Melayu Input + Setting memory fact
    print("\nTurn 1 (Bahasa + Fact injection):")
    prompt1 = "Boleh tak saya gunakan stratified purposeful sampling? Saya ada akses kepada 10 Kolej Vokasional across 4 states sekarang."
    print(f"User: {prompt1}")
    
    res1 = chat_with_supervisor(prompt1, chat_history)
    print(f"AI: {res1}\n")
    
    assert "Langkah Seterusnya" in res1 or "Next Steps" in res1, "Missing Langkah Seterusnya marker!"
    
    chat_history.append(("user", prompt1))
    chat_history.append(("ai", res1))
    
    # Turn 2: Debate mode / context update
    print("\nTurn 2 (Debate Mode / Context Update):")
    prompt2 = "Yes, let's update my sample to those 10 KVs and 4 states. Please update my registry."
    print(f"User: {prompt2}")
    
    res2 = chat_with_supervisor(prompt2, chat_history)
    print(f"AI: {res2}\n")
    
    assert "```json" in res2, "AI did not output a JSON diff for context update!"
    
    chat_history.append(("user", prompt2))
    chat_history.append(("ai", res2))
    
    # Turn 3: Memory check
    print("\nTurn 3 (Memory Check):")
    prompt3 = "Wait, how many states did I say I had access to earlier?"
    print(f"User: {prompt3}")
    
    res3 = chat_with_supervisor(prompt3, chat_history)
    print(f"AI: {res3}\n")
    
    assert "4" in res3 or "empat" in res3.lower(), "AI failed to recall memory from Turn 1!"
    
    print("\n✅ All tests passed successfully!")

if __name__ == "__main__":
    run_tests()
