import os
import time
from datetime import datetime
import json
import logging
import importlib

try:
    import streamlit as st
    from streamlit.runtime.scriptrunner import get_script_run_ctx
except ImportError:
    st = None
    get_script_run_ctx = lambda: None

from src.config import LANGCHAIN_PRIMARY_MODEL, CREWAI_FALLBACK_MODEL

class QuotaManager:
    _cli_state = {
        "active_key_index": 0,
        "active_date": "",
        "key_usage": {}
    }

    @classmethod
    def _is_streamlit(cls):
        if st is None:
            return False
        import sys
        if not sys.argv or not sys.argv[0].endswith("streamlit"):
            return False
        return get_script_run_ctx() is not None

    @classmethod
    def get_state(cls, key, default):
        if cls._is_streamlit():
            if key not in st.session_state:
                st.session_state[key] = default
            return st.session_state[key]
        else:
            if key not in cls._cli_state:
                cls._cli_state[key] = default
            return cls._cli_state[key]

    @classmethod
    def set_state(cls, key, value):
        if cls._is_streamlit():
            st.session_state[key] = value
        else:
            cls._cli_state[key] = value

    @classmethod
    def _get_keys(cls):
        keys = []
        for i in range(1, 10):
            key = os.getenv(f"GEMINI_API_KEY_{i}")
            if key:
                keys.append(key)
        if not keys:
            # Fallback to the default key
            default = os.getenv("GEMINI_API_KEY")
            if default:
                keys.append(default)
        return keys

    @classmethod
    def _check_rollover(cls):
        today = datetime.now().strftime("%Y-%m-%d")
        last_date = cls.get_state("active_date", "")
        if last_date and last_date != today:
            # Reset exhaustion flags and active key index for the new day
            cls.set_state("active_key_index", 0)
            keys = cls._get_keys()
            for i in range(len(keys)):
                cls.set_state(f"exhaustion_reason_{i}", "")
        cls.set_state("active_date", today)

    @classmethod
    def get_key_statuses(cls):
        """Returns a list of dicts with statuses for the dashboard UI"""
        cls._check_rollover()
        keys = cls._get_keys()
        active_idx = cls.get_active_key_index()
        statuses = []
        
        for i in range(len(keys)):
            reason = cls.get_state(f"exhaustion_reason_{i}", "")
            if reason:
                status = {"key": f"Key {i+1}", "state": "exhausted", "reason": reason}
            elif i == active_idx:
                status = {"key": f"Key {i+1}", "state": "serving", "reason": "Active"}
            else:
                status = {"key": f"Key {i+1}", "state": "available", "reason": "Ready"}
            statuses.append(status)
        return statuses

    @classmethod
    def get_active_key_index(cls):
        cls._check_rollover()
        return cls.get_state("active_key_index", 0)
        
    @classmethod
    def get_total_keys(cls):
        return len(cls._get_keys())

    @classmethod
    def get_current_key(cls):
        cls._check_rollover()
        keys = cls._get_keys()
        idx = cls.get_active_key_index()
        if idx < len(keys):
            return keys[idx]
        return None

    @classmethod
    def all_keys_exhausted(cls) -> bool:
        """Returns True if all available keys have been marked as exhausted."""
        cls._check_rollover()
        keys = cls._get_keys()
        for i in range(len(keys)):
            if not cls.get_state(f"exhaustion_reason_{i}", ""):
                return False
        return True

    @classmethod
    def record_call(cls):
        idx = cls.get_active_key_index()
        usage_key = f"key_usage_{idx}"
        current = cls.get_state(usage_key, 0)
        cls.set_state(usage_key, current + 1)

    @classmethod
    def get_usage(cls, index):
        return cls.get_state(f"key_usage_{index}", 0)

    @classmethod
    def rotate_key(cls, reason="exhaustion"):
        keys = cls._get_keys()
        idx = cls.get_active_key_index()
        cls.set_state(f"exhaustion_reason_{idx}", reason)
        if idx + 1 < len(keys):
            cls.set_state("active_key_index", idx + 1)
            new_key = keys[idx + 1]
            os.environ["GEMINI_API_KEY"] = new_key
            try:
                import sys
                sys.path.append(os.path.dirname(__file__))
                from logger import log_event
                log_event("QUOTA_ROTATION", f"Rotated to Key {idx+2} due to {reason}.")
            except: pass
            if cls._is_streamlit():
                st.warning(f"🔄 Rotating to Key {idx+2} due to {reason}...")
            else:
                print(f"\n[!] Rotating to Key {idx+2} due to {reason}...")
            return "ROTATED_KEY"
        return "ALL_KEYS_EXHAUSTED"
        
    @classmethod
    def run_recovery_probe(cls):
        try:
            import requests
            
            keys = cls._get_keys()
            if not keys: return False
            api_key = keys[0]
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{LANGCHAIN_PRIMARY_MODEL}:generateContent?key={api_key}"
            payload = {"contents": [{"parts": [{"text": "hello"}]}]}
            resp = requests.post(url, json=payload, timeout=10)
            
            if resp.status_code == 200:
                cls.set_state("active_key_index", 0)
                for i in range(len(keys)):
                    cls.set_state(f"exhaustion_reason_{i}", "")
                return True
            else:
                # Log diagnostic information about why the probe failed
                error_msg = f"[QuotaManager] Probe failed! Status: {resp.status_code}, Body: {resp.text}"
                print(error_msg)
                
                # If it's a 404 or 400, it's likely a misconfigured model name!
                if resp.status_code in [404, 400]:
                    raise RuntimeError(f"CRITICAL CONFIG ERROR: The recovery probe failed with {resp.status_code}. The model '{LANGCHAIN_PRIMARY_MODEL}' may not exist or is disabled in your account. Details: {resp.text}")
                
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise e # Re-raise config errors so they crash loudly
            print(f"[QuotaManager] Probe exception: {e}")
        return False

    @classmethod
    def handle_error(cls, e):
        error_str = str(e).lower()
        if "429" in error_str or "resource_exhausted" in error_str:
            if "quota" in error_str or "exceeded" in error_str or "daily" in error_str:
                return cls.rotate_key(reason="Daily Quota limit")
            else:
                return "PER_MINUTE_LIMIT"
        elif any(code in error_str for code in ["503", "500", "502", "504", "overloaded", "high demand"]):
            return "RETRYABLE_SERVER_ERROR"
            
        import traceback
        print(f"[QuotaManager] UNKNOWN_ERROR encountered:")
        traceback.print_exc()
        return "UNKNOWN_ERROR"

    @classmethod
    def execute_call(cls, func, *args, **kwargs):
        server_error_count = 0
        backoff_times = [30, 60, 120, 120, 120]
        has_fallen_back = False
        import random
        
        while True:
            try:
                current_key = cls.get_current_key()
                if current_key:
                    os.environ["GEMINI_API_KEY"] = current_key
                
                print(f"[QuotaManager] Executing LLM call using Key {cls.get_active_key_index() + 1}")
                result = func(*args, **kwargs)
                cls.record_call()
                return result
            except Exception as e:
                action = cls.handle_error(e)
                
                if action == "RETRYABLE_SERVER_ERROR":
                    if server_error_count < 5:
                        base_wait = backoff_times[server_error_count]
                        wait_t = base_wait * random.uniform(0.8, 1.2)
                        key_idx = cls.get_active_key_index() + 1
                        print(f"[QuotaManager] 503 overloaded. Retrying (Attempt {server_error_count + 1}/5) in {wait_t:.1f}s on Key {key_idx}...")
                        time.sleep(wait_t)
                        server_error_count += 1
                        continue
                    else:
                        raise Exception("Google servers are busy — max retries exceeded.") from e
                
                elif action == "ROTATED_KEY":
                    continue
                elif action == "PER_MINUTE_LIMIT":
                    if server_error_count < 3:
                        time.sleep(20)
                        server_error_count += 1
                        continue
                    else:
                        raise Exception("Rate limit exceeded after retries.") from e
                elif action == "ALL_KEYS_EXHAUSTED":
                    if cls.run_recovery_probe():
                        print(f"\n[QuotaManager] Key Recovery Probe SUCCESS! Resetting to Key 1.")
                        continue
                        
                    if not has_fallen_back and "model_string" in kwargs:
                        kwargs["model_string"] = CREWAI_FALLBACK_MODEL
                        print("[QuotaManager] Primary model exhausted — falling back to lite model.")
                        has_fallen_back = True
                        # Reset keys to try the new model pool
                        cls.set_state("active_key_index", 0)
                        for i in range(len(cls._get_keys())):
                            cls.set_state(f"exhaustion_reason_{i}", "")
                        continue
                        
                    reasons = []
                    keys = cls._get_keys()
                    for i in range(len(keys)):
                        r = cls.get_state(f"exhaustion_reason_{i}", "Unknown")
                        reasons.append(f"Key {i+1}: {r}")
                    raise Exception("All API keys exhausted — daily quota resets at midnight Pacific.\n" + "\n".join(reasons)) from e
                else:
                    raise e

# Run startup check when module is imported
_initial_keys = QuotaManager._get_keys()
print(f"[QuotaManager] Loaded {len(_initial_keys)} API keys at startup.")
if len(_initial_keys) == 0:
    raise RuntimeError("CRITICAL ERROR: Zero Gemini API keys loaded. Please configure GEMINI_API_KEY_1 in your .env file or Streamlit sidebar.")
