import os
from datetime import datetime

def log_event(event_type: str, details: str):
    """
    Appends a timestamped line to output/research_log.md
    Format: [date] [event] [details]
    """
    base_dir = os.path.dirname(os.path.dirname(__file__))
    log_dir = os.path.join(base_dir, "output")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "research_log.md")
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"- **[{timestamp}]** `[{event_type}]` {details}\n"
    
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Failed to write to research log: {e}")
