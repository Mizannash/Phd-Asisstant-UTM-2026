import os
from dotenv import load_dotenv

print("Before dotenv:", os.environ.get("GROQ_API_KEY"))
load_dotenv()
print("After dotenv:", os.environ.get("GROQ_API_KEY"))
