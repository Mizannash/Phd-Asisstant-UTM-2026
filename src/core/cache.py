import json
import hashlib
import os
import time
from datetime import datetime, timedelta

CACHE_FILE = os.path.join("data", "cache", "llm_cache.json")
MAX_ENTRIES = 5000
MAX_AGE_DAYS = 90

class LLMCache:
    def __init__(self):
        self.cache_file = CACHE_FILE
        self._cache = {}
        self._load()
        self._prune()

    def _load(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except Exception:
                self._cache = {}

    def _save(self):
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self._cache, f)

    def _generate_key(self, model, messages):
        messages_str = json.dumps(messages, sort_keys=True)
        raw = f"{model}:{messages_str}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _prune(self):
        changed = False
        now = datetime.now()
        keys_to_delete = []

        for key, data in self._cache.items():
            timestamp = data.get("timestamp", 0)
            entry_time = datetime.fromtimestamp(timestamp)
            if now - entry_time > timedelta(days=MAX_AGE_DAYS):
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self._cache[key]
            changed = True

        if len(self._cache) > MAX_ENTRIES:
            sorted_entries = sorted(self._cache.items(), key=lambda x: x[1].get("timestamp", 0))
            excess = len(self._cache) - MAX_ENTRIES
            for i in range(excess):
                del self._cache[sorted_entries[i][0]]
            changed = True

        if changed:
            self._save()

    def get(self, model, messages):
        key = self._generate_key(model, messages)
        if key in self._cache:
            return self._cache[key].get("response")
        return None

    def set(self, model, messages, response):
        key = self._generate_key(model, messages)
        self._cache[key] = {
            "response": response,
            "timestamp": time.time()
        }
        self._save()

cache = LLMCache()
