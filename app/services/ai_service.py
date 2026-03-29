import os
import json
from groq import Groq
import requests
import pdfplumber
import io
import re

def clean_json(text):
    # Strip markdown code block wrappers if they exist
    text = text.strip()
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()
    return text

def setup_groq():
    api_key = os.environ.get('GROQ_API_KEY', 'mock-groq-key')
    if api_key and api_key != 'mock-groq-key':
        return Groq(api_key=api_key)
    return None

def extract_text_from_url(url, file_type):
    # This is a basic mock handler, normally we'd download and parse PDF/Image
    if file_type == 'pdf':
        try:
            if '/uploads/' in url:
                # Handle local file directly to avoid blocking
                filename = url.split('/')[-1]
                filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'uploads', filename)
                with pdfplumber.open(filepath) as pdf:
                    text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
                return text
            else:
                r = requests.get(url)
                with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                    text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
                return text
        except Exception as e:
            print("PDF Extraction error:", e)
            return "Failed to parse PDF."
    # OCR for images would go here with pytesseract
    return "Extracted text content from file."

def generate_quiz(text, difficulty, total_q=5):
    client = setup_groq()
    if not client:
        raise Exception("Groq API key is not configured in .env")
        
    prompt = f"""
    Given this educational content, generate a {difficulty} level multiple-choice quiz with {total_q} questions.
    Return ONLY a raw JSON array where each object has:
    - question_text (string)
    - option_a (string)
    - option_b (string)
    - option_c (string)
    - option_d (string)
    - correct_option (string, 'a', 'b', 'c', or 'd')
    - explanation (string)
    - topic_tag (string)
    
    Content: {text[:4000]} # Limit tokens
    """
    
    try:
        res = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"} if "llama" not in "llama-3.1-8b-instant" else None
        )
        
        text_ans = clean_json(res.choices[0].message.content)
        
        # sometimes Llama returns an object with a "questions" array
        parsed = json.loads(text_ans)
        if isinstance(parsed, dict) and 'questions' in parsed:
            return parsed['questions']
        return parsed
    except Exception as e:
        print("Groq API error in generate_quiz:", e)
        raise Exception(f"AI Generation failed: {str(e)}")

def refine_notes(text):
    client = setup_groq()
    if not client:
        raise Exception("Groq API key is not configured in .env")
        
    prompt = f"""
    Refine these raw student notes into: 1. A clean summary. 2. Key points. 3. 3-4 Flashcards.
    Return ONLY JSON:
    {{
        "summary": "...",
        "key_points": ["..."],
        "flashcards": [{{"question": "...", "answer": "..."}}]
    }}
    
    Raw Notes: {text[:4000]}
    """
    
    try:
        res = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        text_ans = clean_json(res.choices[0].message.content)
        return json.loads(text_ans)
    except Exception as e:
        print("Groq refine error:", e)
        raise Exception(f"AI Refinement failed: {str(e)}")

def chat_tutor(message, context=""):
    client = setup_groq()
    if not client:
        return "Error: Groq API key is not configured."
        
    try:
        system_prompt = "You are the Synapse AI Tutor. Answer this student's query clearly and concisely."
        if context:
            system_prompt += f"\n\nContext about the student:\n{context}"
            
        res = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ]
        )
        return res.choices[0].message.content
    except Exception as e:
        print("Groq chat error:", e)
        return f"AI Tutor is currently unavailable due to an API error: {str(e)}"
