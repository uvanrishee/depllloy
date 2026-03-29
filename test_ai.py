import os
import sys
from dotenv import load_dotenv

with open("test_ai_log.txt", "w") as f:
    try:
        load_dotenv()
        api_key = os.environ.get('GEMINI_API_KEY', 'mock-gemini-key')
        f.write(f"API Key read: {api_key[:10]}...\n")
        
        import google.generativeai as genai
        f.write("genai imported\n")
        genai.configure(api_key=api_key)
        chat_model = genai.GenerativeModel('gemini-1.5-flash')
        res = chat_model.generate_content("Hello")
        f.write(f"Response: {res.text}\n")
    except Exception as e:
        import traceback
        f.write(f"Error: {e}\n{traceback.format_exc()}\n")
