import os
import sys
from streamlit.testing.v1 import AppTest

print("Running AppTest on dashboard.py...")
try:
    at = AppTest.from_file('../src/dashboard.py').run(timeout=30)
    print("App loaded.")
    
    if len(at.chat_input) > 0:
        at.chat_input[0].set_value("masalah pembelajaran di Kolej Vokasional")
        # In newer streamlit, it's just .run() or .submit() isn't needed if set_value triggers?
        # Let's try .set_value().run()
        try:
            at.chat_input[0].set_value("masalah pembelajaran di Kolej Vokasional").run(timeout=120)
        except Exception as e:
            print("Run exception:", e)
    else:
        print("No chat input found.")
        
    print("Test complete.")
    for msg in at.chat_message:
        print(f"\n--- CHAT MSG from {msg.name} ---")
        for md in msg.markdown:
            print(md.value)
except Exception as e:
    print("Test failed:", e)
