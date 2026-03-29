import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get('GROQ_API_KEY')
print("Key starts with:", api_key[:10] if api_key else "None")
try:
    client = Groq(api_key=api_key)
    res = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{"role": "user", "content": "Say OK"}]
    )
    print("Success:", res.choices[0].message.content)
except Exception as e:
    print("Error:", e)
