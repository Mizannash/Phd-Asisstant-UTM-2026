import os
import json
import csv

ANALYTICS_DIR = os.path.join("output", "analytics")
ACTUAL_CALLS_FILE = os.path.join(ANALYTICS_DIR, "actual_calls.csv")
BUDGET_FILE = os.path.join(ANALYTICS_DIR, "budget.json")

# Approximate costs for foundation
COSTS = {
    "groq/openai/gpt-oss-120b": 0.0,
    "gemini/gemini-1.5-flash": 0.00001, # Example mock cost per token
    "CACHE": 0.0
}

class BudgetManager:
    def __init__(self):
        self.actual_calls_file = ACTUAL_CALLS_FILE
        self.budget_file = BUDGET_FILE

    def calculate_current_usage(self):
        if not os.path.exists(self.actual_calls_file):
            return 0.0, 0
            
        total_cost = 0.0
        total_calls = 0
        
        with open(self.actual_calls_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                model = row.get("model", "")
                # Fallback to total_tokens if tokens not present (migration)
                tokens_str = row.get("total_tokens") or row.get("tokens", "0")
                tokens = int(tokens_str) if tokens_str.isdigit() else 0
                
                if model == "CACHE":
                    total_calls += 1
                    continue
                
                cost_per_token = COSTS.get(model, 0.0)
                total_cost += cost_per_token * tokens
                total_calls += 1
                
        self._save_state(total_cost, total_calls)
        return total_cost, total_calls

    def _save_state(self, total_cost, total_calls):
        state = {
            "total_cost": total_cost,
            "total_successful_calls": total_calls
        }
        with open(self.budget_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
            
    def get_last_action_breakdown(self):
        if not os.path.exists(self.actual_calls_file):
            return None
            
        last_row = None
        with open(self.actual_calls_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                last_row = row
                
        return last_row

budget_manager = BudgetManager()
