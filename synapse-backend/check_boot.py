import sys
import traceback

with open("boot_log.txt", "w") as f:
    try:
        from app import create_app
        import groq
        import flask
        import flask_cors
        import firebase_admin
        import pdfplumber
        import requests
        
        f.write("All imports successful!\n")
        
        app = create_app()
        f.write("App created successfully!\n")
    except Exception as e:
        f.write(f"Exception exactly: {e}\n")
        f.write(traceback.format_exc() + "\n")
