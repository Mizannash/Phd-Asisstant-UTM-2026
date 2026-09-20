import os
from litellm import completion
from dotenv import load_dotenv

load_dotenv()

try:
    print("Trying Groq direct Llama...")
    res = completion(model="groq/llama-3.3-70b-versatile", messages=[{"role": "user", "content": "hi"}])
    print("Success!", res.choices[0].message.content)
except Exception as e:
    print("Error:", e)

try:
    print("Trying Groq direct OSS 20b...")
    res = completion(model="groq/openai/gpt-oss-20b", messages=[{"role": "user", "content": "hi"}])
    print("Success!", res.choices[0].message.content)
except Exception as e:
    print("Error:", e)
