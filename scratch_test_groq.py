import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

try:
    resp = requests.get("https://api.groq.com/openai/v1/models", headers=headers)
    print("Status:", resp.status_code)
    if resp.status_code == 200:
        models = [m['id'] for m in resp.json().get("data", [])]
        print("Models:", models)
        if "openai/gpt-oss-120b" in models:
            print("120b is available!")
        if "gpt-oss-120b" in models:
            print("Without openai/ prefix it's available!")
    else:
        print("Error:", resp.text)
except Exception as e:
    print(e)
