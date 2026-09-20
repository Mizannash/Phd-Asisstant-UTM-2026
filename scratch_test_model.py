from dotenv import load_dotenv
load_dotenv()
from src.core.llm_factory import get_llm_response
try:
    print("Testing 20b...")
    get_llm_response([{"role": "user", "content": "hi"}], tier="T1", pipeline="test") # T1 is 120b right now!
except Exception as e:
    print("Failed 120b:", e)

from src.core.llm_factory import cache
try:
    print("Testing 20b manually...")
    import litellm
    resp = litellm.completion(model="groq/openai/gpt-oss-20b", messages=[{"role": "user", "content": "hi"}])
    print("20b success!")
except Exception as e:
    print("Failed 20b:", e)
