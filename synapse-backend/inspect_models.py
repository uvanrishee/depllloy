import os
from dotenv import load_dotenv

with open("inspect_models_output.txt", "w") as f:
    try:
        load_dotenv()
        api_key = os.environ.get("GEMINI_API_KEY", "")
        f.write(f"Key checked: {api_key[:5]}...\n")
        
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        f.write("Available models for this key:\n")
        models = genai.list_models()
        for m in models:
            if 'generateContent' in m.supported_generation_methods:
                f.write(f"- {m.name}\n")
    except Exception as e:
        import traceback
        f.write(f"Error: {e}\n{traceback.format_exc()}\n")
