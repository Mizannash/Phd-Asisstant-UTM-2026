import os
import csv
import json
from datetime import datetime, timedelta

def parse_iso_date(date_str):
    try:
        return datetime.fromisoformat(date_str)
    except Exception:
        return datetime.now()

class SystemAnalytics:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(__file__))
        self.analytics_dir = os.path.join(self.base_dir, "output", "analytics")
        os.makedirs(self.analytics_dir, exist_ok=True)
        
    def _read_csv(self, filename):
        filepath = os.path.join(self.analytics_dir, filename)
        if not os.path.exists(filepath):
            return []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                return list(reader)
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            return []

    def get_token_stats(self):
        # reads actual_calls.csv if exists, else usage.csv
        rows = self._read_csv("actual_calls.csv") or self._read_csv("usage.csv")
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        
        stats = {
            "today_calls": 0, "week_calls": 0, "total_calls": len(rows),
            "today_tokens": 0, "week_tokens": 0, "total_tokens": 0
        }
        
        for row in rows:
            ts_str = row.get("Timestamp") or row.get("timestamp")
            if not ts_str: continue
            dt = parse_iso_date(ts_str).date()
            tokens = int(row.get("Total_Tokens", row.get("tokens", 0)))
            
            stats["total_tokens"] += tokens
            if dt == today:
                stats["today_calls"] += 1
                stats["today_tokens"] += tokens
            if dt >= start_of_week:
                stats["week_calls"] += 1
                stats["week_tokens"] += tokens
                
        return stats

    def get_budget_estimates_vs_actuals(self):
        try:
            budget_path = os.path.join(self.analytics_dir, "budget.json")
            if os.path.exists(budget_path):
                with open(budget_path, 'r') as f:
                    budget_data = json.load(f)
            else:
                budget_data = {}
        except:
            budget_data = {}
            
        rows = self._read_csv("actual_calls.csv")
        pipeline_counts = {}
        for r in rows:
            p = r.get("Pipeline", "unknown")
            pipeline_counts[p] = pipeline_counts.get(p, 0) + 1
            
        return {
            "budget": budget_data,
            "actuals": pipeline_counts
        }

    def get_prefilter_stats(self):
        rows = self._read_csv("prefilter_stats.csv")
        total_in = 0
        total_survived = 0
        for r in rows:
            total_in += int(r.get("Total_In", 0))
            total_survived += int(r.get("Survived", 0))
            
        survival_rate = (total_survived / total_in * 100) if total_in > 0 else 0
        return {
            "total_in": total_in,
            "total_survived": total_survived,
            "survival_rate": round(survival_rate, 1)
        }

    def get_rejection_and_cache_stats(self):
        # Cache hits from cache_hits.csv
        cache_rows = self._read_csv("cache_hits.csv")
        cache_hits = len(cache_rows)
        
        # Scout dedups from prefilter_decisions.csv
        decisions = self._read_csv("prefilter_decisions.csv")
        scout_dedups = sum(1 for d in decisions if d.get("Reason/Score") == "dedup-skipped")
        
        # Rejections from rejection_audit.md
        rejections = 0
        audit_path = os.path.join(self.base_dir, "output", "Obsidian_Vault", "03_System", "rejection_audit.md")
        if os.path.exists(audit_path):
            with open(audit_path, 'r', encoding='utf-8') as f:
                # Count table rows (skip header and separator)
                lines = f.readlines()
                if len(lines) > 4:
                    rejections = len([l for l in lines if l.strip().startswith("|")]) - 2
                    
        return {
            "cache_hits": cache_hits,
            "scout_dedups": scout_dedups,
            "rejections": max(0, rejections)
        }

    def generate_weekly_digest(self):
        today = datetime.now()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        ts = self.get_token_stats()
        ps = self.get_prefilter_stats()
        rcs = self.get_rejection_and_cache_stats()
        
        digest = f"""# Weekly System Digest ({start_of_week.strftime('%Y-%m-%d')} to {end_of_week.strftime('%Y-%m-%d')})

## Processing Pipeline
- **Papers Scouted (Raw):** {ps['total_in']}
- **Prefilter Survived:** {ps['total_survived']} (Survival Rate: {ps['survival_rate']}%)
- **Papers Analyzed (Total LLM Calls):** {ts['week_calls']} (This week)
- **Papers Rejected by Agent:** {rcs['rejections']}

## Efficiency & Savings
- **Duplicate Papers Skipped by Scout:** {rcs['scout_dedups']}
- **Manual Pipeline Cache Hits:** {rcs['cache_hits']}
- **Estimated Savings:** By dropping {ps['total_in'] - ps['total_survived']} papers in prefilter and caching {rcs['cache_hits']} manual inputs, the system saved significant LLM quota.

## Quota Consumed
- **API Calls (This Week):** {ts['week_calls']}
- **Tokens Consumed (This Week):** {ts['week_tokens']}
"""
        weekly_dir = os.path.join(self.analytics_dir, "weekly")
        os.makedirs(weekly_dir, exist_ok=True)
        out_path = os.path.join(weekly_dir, f"digest_{start_of_week.strftime('%Y_%m_%d')}.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(digest)
            
        return digest, out_path

    def lazy_generate_weekly_digest(self):
        """Generates the digest if it doesn't exist for the current week (post-Monday 00:00)."""
        today = datetime.now()
        start_of_week = today - timedelta(days=today.weekday())
        weekly_dir = os.path.join(self.analytics_dir, "weekly")
        out_path = os.path.join(weekly_dir, f"digest_{start_of_week.strftime('%Y_%m_%d')}.md")
        if not os.path.exists(out_path):
            self.generate_weekly_digest()
