import os
import json
import yaml
import datetime
import csv
from filelock import FileLock
from langchain_core.callbacks.base import BaseCallbackHandler
from litellm.integrations.custom_logger import CustomLogger

def get_myt_date():
    myt = datetime.timezone(datetime.timedelta(hours=8))
    return datetime.datetime.now(myt).strftime("%Y-%m-%d")

class BudgetManager:
    def __init__(self, base_dir=None):
        if not base_dir:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.base_dir = base_dir
        self.config_path = os.path.join(base_dir, "config", "budget.yaml")
        self.analytics_dir = os.path.join(base_dir, "output", "analytics")
        self.db_path = os.path.join(self.analytics_dir, "budget.json")
        self.mode_path = os.path.join(self.analytics_dir, "mode.json")
        self.lock_path = self.db_path + ".lock"
        self.mode_lock_path = self.mode_path + ".lock"
        
        os.makedirs(self.analytics_dir, exist_ok=True)
        self._load_config()

    def _load_config(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)
        except Exception:
            self.config = {
                "daily_limits": {"gemini": 80, "groq_soft": 200, "groq_hard": 400},
                "estimates": {"single_paper": 5, "promote": 5, "scout_run": 3}
            }

    def get_mode(self):
        if not os.path.exists(self.mode_path):
            return {"dev_mode": False, "dev_mock": False}
        try:
            with open(self.mode_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"dev_mode": False, "dev_mock": False}

    def set_mode(self, dev_mode: bool, dev_mock: bool):
        with FileLock(self.mode_lock_path, timeout=5):
            data = {"dev_mode": dev_mode, "dev_mock": dev_mock}
            with open(self.mode_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

    def _read_budget(self):
        if not os.path.exists(self.db_path):
            return {"date": "", "gemini_used": 0, "groq_used": 0}
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"date": "", "gemini_used": 0, "groq_used": 0}

    def _write_budget(self, data):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def _check_rollover(self, data):
        today = get_myt_date()
        if data.get("date") != today:
            data["date"] = today
            data["gemini_used"] = 0
            data["groq_used"] = 0
            self._write_budget(data)
        return data

    def get_limits(self):
        lim = self.config.get("daily_limits", {})
        return {
            "gemini": lim.get("gemini", 80),
            "groq_soft": lim.get("groq_soft", 200),
            "groq_hard": lim.get("groq_hard", 400)
        }

    def can_afford(self, estimate: int, provider="gemini") -> bool:
        with FileLock(self.lock_path, timeout=5):
            data = self._check_rollover(self._read_budget())
            limits = self.get_limits()
            if provider == "gemini":
                return (data.get("gemini_used", 0) + estimate) <= limits["gemini"]
            elif provider == "groq":
                return (data.get("groq_used", 0) + estimate) <= limits["groq_hard"]
            return False

    def spend(self, n: int, provider="gemini"):
        with FileLock(self.lock_path, timeout=5):
            data = self._check_rollover(self._read_budget())
            if provider == "gemini":
                data["gemini_used"] = data.get("gemini_used", 0) + n
            elif provider == "groq":
                data["groq_used"] = data.get("groq_used", 0) + n
            self._write_budget(data)
            
            # Removed StorageHandler.push_state to prevent Streamlit Cloud from restarting the app.

    def remaining(self) -> dict:
        with FileLock(self.lock_path, timeout=5):
            data = self._check_rollover(self._read_budget())
            limits = self.get_limits()
            return {
                "gemini": {
                    "limit": limits["gemini"],
                    "used": data.get("gemini_used", 0),
                    "remaining": max(0, limits["gemini"] - data.get("gemini_used", 0))
                },
                "groq": {
                    "soft_limit": limits["groq_soft"],
                    "hard_limit": limits["groq_hard"],
                    "used": data.get("groq_used", 0),
                    "remaining_soft": max(0, limits["groq_soft"] - data.get("groq_used", 0)),
                    "remaining_hard": max(0, limits["groq_hard"] - data.get("groq_used", 0))
                },
                "reset_date_myt": data.get("date")
            }

class LLMCallTracker(BaseCallbackHandler, CustomLogger):
    def __init__(self, pipeline_name: str, base_dir: str = None):
        super().__init__()
        if not base_dir:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.pipeline_name = pipeline_name
        self.analytics_dir = os.path.join(base_dir, "output", "analytics")
        os.makedirs(self.analytics_dir, exist_ok=True)
        self.csv_path = os.path.join(self.analytics_dir, "actual_calls.csv")
        
        # We need a BudgetManager instance to actually decrement budget
        self.bm = BudgetManager(base_dir=base_dir)

        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Pipeline", "Model", "TotalTokens", "PromptTokens", "CompletionTokens"])

    def on_llm_end(self, response, **kwargs):
        try:
            llm_output = response.llm_output or {}
            token_usage = llm_output.get("token_usage", {})
            model_name = llm_output.get("model_name", "unknown")
            
            with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.datetime.now().isoformat(),
                    self.pipeline_name,
                    model_name,
                    token_usage.get("total_tokens", 0),
                    token_usage.get("prompt_tokens", 0),
                    token_usage.get("completion_tokens", 0)
                ])
                
            provider = "groq" if "groq" in model_name.lower() or "groq" in self.pipeline_name.lower() else "gemini"
            self.bm.spend(1, provider=provider)
        except Exception as e:
            print(f"Error logging LLM call in on_llm_end: {e}")

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        """LiteLLM custom logger integration for crewai.LLM"""
        try:
            usage = response_obj.get("usage", None)
            if usage:
                # Usage is usually an object in litellm, fallback to dict if needed
                total_tokens = getattr(usage, "total_tokens", usage.get("total_tokens", 0)) if hasattr(usage, "total_tokens") else usage.get("total_tokens", 0)
                prompt_tokens = getattr(usage, "prompt_tokens", usage.get("prompt_tokens", 0)) if hasattr(usage, "prompt_tokens") else usage.get("prompt_tokens", 0)
                completion_tokens = getattr(usage, "completion_tokens", usage.get("completion_tokens", 0)) if hasattr(usage, "completion_tokens") else usage.get("completion_tokens", 0)
                
                model_name = kwargs.get("model", "unknown")
                
                with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        datetime.datetime.now().isoformat(),
                        self.pipeline_name,
                        model_name,
                        total_tokens,
                        prompt_tokens,
                        completion_tokens
                    ])
                    
                provider = "groq" if "groq" in model_name.lower() or "groq" in self.pipeline_name.lower() else "gemini"
                self.bm.spend(1, provider=provider)
        except Exception as e:
            print(f"Error logging LLM call in log_success_event: {e}")

def validate_groq_dev_model():
    import requests
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("CRITICAL ERROR: GROQ_API_KEY is required for Developer Mode.")
    
    url = "https://api.groq.com/openai/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            raise RuntimeError(f"CRITICAL ERROR: Groq API validation failed: {resp.text}")
        
        models = resp.json().get("data", [])
        model_ids = [m.get("id") for m in models]
        target_model = "llama3-70b-8192"
        if target_model not in model_ids:
            raise RuntimeError(f"CRITICAL ERROR: Groq dev-mode model '{target_model}' is not available or valid.")
    except Exception as e:
        if isinstance(e, RuntimeError):
            raise e
        raise RuntimeError(f"CRITICAL ERROR during Groq validation: {e}")
