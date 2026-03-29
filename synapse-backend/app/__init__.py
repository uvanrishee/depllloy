import os
import firebase_admin
from firebase_admin import credentials
from flask import Flask, jsonify
from flask_cors import CORS
from .database import init_app

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    
    # Base Config
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev'),
        DATABASE=os.path.join(app.instance_path, 'synapse.db'),
    )

    if test_config is None:
        app.config.from_pyfile('config.py', silent=True)
    else:
        app.config.from_mapping(test_config)

    # Ensure instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)

    # Enable CORS
    CORS(app)

    # Initialize Firebase Admin SDK if not already initialized
    if not firebase_admin._apps:
        firebase_creds_json = os.environ.get('FIREBASE_CREDENTIALS')
        if firebase_creds_json:
            import json
            try:
                cred_dict = json.loads(firebase_creds_json)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
            except Exception as e:
                print(f"ERROR: Failed to initialize Firebase from FIREBASE_CREDENTIALS env var: {e}")
        else:
            # Check if service account file exists, else use mock for dev
            cred_path = os.path.join(os.path.dirname(app.root_path), 'firebase-service-account.json')
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
            else:
                print("WARNING: firebase-service-account.json not found and FIREBASE_CREDENTIALS env var missing! Using mock auth.")

    # Init DB
    init_app(app)

    # Health check route
    @app.route('/health')
    def health():
        return jsonify({'status': 'ok'})

    # Serve uploaded files statically
    uploads_dir = os.path.join(os.path.dirname(app.root_path), 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)

    from flask import send_from_directory
    @app.route('/uploads/<path:filename>')
    def serve_upload(filename):
        return send_from_directory(uploads_dir, filename)


    # Register Blueprints
    from .blueprints import auth, classrooms, materials, quizzes, ai_routes, analytics, friends, mistakes, notes, forum
    
    app.register_blueprint(auth.bp)
    app.register_blueprint(classrooms.bp)
    app.register_blueprint(materials.bp)
    app.register_blueprint(quizzes.bp)
    app.register_blueprint(ai_routes.bp)
    app.register_blueprint(analytics.bp)
    app.register_blueprint(friends.bp)
    app.register_blueprint(mistakes.bp)
    app.register_blueprint(notes.bp)
    app.register_blueprint(forum.bp)

    return app
