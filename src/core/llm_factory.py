import litellm
import os
import csv
from dotenv import load_dotenv
load_dotenv()
import time
from datetime import datetime
from src.core.cache import cache

from src.core.config import get_secret, get_masked_key

def mask_key(key):
    return get_masked_key(key)

class GroqKeyManager:
    def __init__(self):
        self.keys = []
        for i in range(1, 5):
            try:
                k = get_secret(f"GROQ_API_KEY_{i}")
                self.keys.append(k)
            except ValueError:
                pass
        if not self.keys:
            try:
                k = get_secret("GROQ_API_KEY")
                self.keys.append(k)
            except ValueError:
                pass
        self.current_idx = 0
        
    def get_current_key(self):
        if not self.keys:
            return None
        return self.keys[self.current_idx]
        
    def rotate(self):
        if not self.keys:
            return None
        old_key = self.keys[self.current_idx]
        self.current_idx = (self.current_idx + 1) % len(self.keys)
        new_key = self.keys[self.current_idx]
        print(f"KEY_ROTATED: {mask_key(old_key)} -> {mask_key(new_key)}")
        return new_key

groq_manager = GroqKeyManager()

ANALYTICS_DIR = os.path.join("output", "analytics")
ACTUAL_CALLS_FILE = os.path.join(ANALYTICS_DIR, "actual_calls.csv")
FAILURES_FILE = os.path.join(ANALYTICS_DIR, "llm_failures.csv")

os.makedirs(ANALYTICS_DIR, exist_ok=True)

def _init_csv(file_path, headers):
    if not os.path.exists(file_path):
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)

_init_csv(ACTUAL_CALLS_FILE, ["timestamp", "pipeline", "model", "tokens"])
_init_csv(FAILURES_FILE, ["timestamp", "pipeline", "model", "error"])

def _custom_success_callback(kwargs, completion_response, start_time, end_time):
    pipeline = kwargs.get("litellm_params", {}).get("metadata", {}).get("pipeline", "default")
    model = kwargs.get("litellm_params", {}).get("metadata", {}).get("logging_model", kwargs.get("model", "unknown"))
    
    # Extract token usage from the unified litellm response
    usage = completion_response.get("usage", {}) if isinstance(completion_response, dict) else getattr(completion_response, "usage", None)
    
    total_tokens = 0
    prompt_tokens = 0
    completion_tokens = 0
    
    if usage:
        if hasattr(usage, "total_tokens"):
            total_tokens = getattr(usage, "total_tokens", 0)
            prompt_tokens = getattr(usage, "prompt_tokens", 0)
            completion_tokens = getattr(usage, "completion_tokens", 0)
        elif isinstance(usage, dict):
            total_tokens = usage.get("total_tokens", 0)
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

    # Initialize CSV files to ensure headers exist
    _init_csv(ACTUAL_CALLS_FILE, ["timestamp", "pipeline", "model", "total_tokens", "prompt_tokens", "completion_tokens"])
    _init_csv(FAILURES_FILE, ["timestamp", "pipeline", "model", "error"])
        
    with open(ACTUAL_CALLS_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now().isoformat(), pipeline, model, total_tokens, prompt_tokens, completion_tokens])

def _custom_failure_callback(kwargs, completion_response, start_time, end_time):
    model = kwargs.get("litellm_params", {}).get("metadata", {}).get("logging_model", kwargs.get("model", "unknown"))
    pipeline = kwargs.get("litellm_params", {}).get("metadata", {}).get("pipeline", "default")
    error = kwargs.get("exception", "unknown error")
    
    with open(FAILURES_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now().isoformat(), pipeline, model, str(error)])

litellm.success_callback = [_custom_success_callback]
litellm.failure_callback = [_custom_failure_callback]

def get_llm_response(messages, tier="T1", confirm_expensive=False, pipeline="default"):
    if tier == "T2":
        if not confirm_expensive:
            error_msg = "Refused: confirm_expensive=True required for T2"
            with open(FAILURES_FILE, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([datetime.now().isoformat(), pipeline, "T2-rejected", error_msg])
            raise ValueError(error_msg)
        model_name = "openai/gpt-oss-120b"
    else:
        model_name = "openai/gpt-oss-120b"
        
    cached_resp = cache.get(model_name, messages)
    if cached_resp:
        with open(ACTUAL_CALLS_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([datetime.now().isoformat(), pipeline, "CACHE", 0, 0, 0])
        return cached_resp
        
    if "gemini" in model_name:
        try:
            api_key = get_secret("GEMINI_API_KEY_1")
        except ValueError:
            try:
                api_key = get_secret("GEMINI_API_KEY")
            except ValueError:
                api_key = None
        if api_key:
            os.environ["GEMINI_API_KEY"] = api_key
        api_base = None
        routing_model = model_name
    else:
        api_key = groq_manager.get_current_key()
        api_base = None
        routing_model = f"groq/{model_name}"

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = litellm.completion(
                model=routing_model,
                messages=messages,
                api_key=api_key,
                api_base=api_base,
                metadata={"pipeline": pipeline, "logging_model": model_name},
                max_tokens=4096
            )
            content = response.choices[0].message.content
            cache.set(model_name, messages, content)
            return content
        except Exception as e:
            err_type = type(e).__name__
            if "AuthenticationError" in err_type or "BadRequestError" in err_type or "401" in str(e) or "api_key" in str(e).lower():
                api_key = groq_manager.rotate()
                if attempt == max_retries:
                    raise e
            elif "RateLimitError" in err_type or "429" in str(e):
                if attempt == 0:
                    print(f"RateLimitError caught. Backing off 5s...")
                    time.sleep(5)
                elif attempt == 1:
                    print(f"RateLimitError caught again. Backing off 15s...")
                    time.sleep(15)
                else:
                    raise e
            else:
                raise e
