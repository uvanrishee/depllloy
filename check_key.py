import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get('GEMINI_API_KEY')

try:
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    res = requests.get(url)
    
    with open("key_models.txt", "w") as f:
        f.write(f"Status Code: {res.status_code}\n")
        f.write(f"Response: {res.text}\n")
except Exception as e:
    with open("key_models.txt", "w") as f:
        f.write(f"Request failed: {str(e)}\n")
