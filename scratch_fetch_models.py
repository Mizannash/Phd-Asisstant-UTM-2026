import os
import requests
from dotenv import load_dotenv

load_dotenv(override=True)
key = os.getenv("GROQ_API_KEY")

resp = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {key}"})
if resp.status_code == 200:
    models = resp.json().get("data", [])
    print("Available Groq models:")
    for m in models:
        print(f"- {m['id']}")
else:
    print(f"Error {resp.status_code}: {resp.text}")
