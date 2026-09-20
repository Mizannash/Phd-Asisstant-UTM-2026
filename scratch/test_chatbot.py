import os
import sys
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

load_dotenv()
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from chatbot import chat_with_supervisor
from quota_manager import QuotaManager

print("Testing chat_with_supervisor end-to-end:")
print(f"Current active key index: {QuotaManager.get_active_key_index()}")

try:
    response = chat_with_supervisor("masalah pembelajaran di Kolej Vokasional", [])
    print(f"\nResponse received successfully!\n")
    print(response)
    print(f"\nFinished on key index: {QuotaManager.get_active_key_index()}")
except Exception as e:
    print(f"\nError: {e}")
