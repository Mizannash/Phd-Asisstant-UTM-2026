import os
import requests

key = os.getenv("GROQ_API_KEY")
if not key:
    with open(".env") as f:
        for line in f:
            if line.startswith("GROQ_API_KEY="):
                key = line.strip().split("=", 1)[1]

headers = {
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json"
}

data = {
    "model": "llama3-8b-8192",
    "messages": [{"role": "user", "content": "hi"}]
}

resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data)
print("Status:", resp.status_code)
print("Response:", resp.text)
