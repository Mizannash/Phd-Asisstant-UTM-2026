import json
import os

library_path = 'output/library.json'
with open(library_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

papers = data.get('papers', [])
seen_titles = set()
deduped_papers = []

# We want to keep the OLDEST scouted version ideally, so we iterate and only keep the first one we see.
# Or wait, the user might want the newest. Let's just keep the first one we see in the array (which is the oldest, since new ones are appended).
for p in papers:
    title = p.get('title', '').strip().lower()
    if title not in seen_titles:
        seen_titles.add(title)
        deduped_papers.append(p)

data['papers'] = deduped_papers

from src.library_manager import safe_write_library
safe_write_library(data)
print(f"Removed {len(papers) - len(deduped_papers)} duplicate papers.")
