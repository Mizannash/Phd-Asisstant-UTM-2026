import os
from dotenv import load_dotenv

load_dotenv(override=True)
key = os.getenv("GROQ_API_KEY")
print("Key repr:", repr(key))
print("Key length:", len(key) if key else 0)
