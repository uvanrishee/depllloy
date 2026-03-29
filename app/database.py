import sqlite3
import os
from flask import g, current_app

def get_db():
    if 'db' not in g:
        db_path = current_app.config['DATABASE']
        # Create instance folder if doesn't exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        g.db = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
        # Enable foreign keys
        g.db.execute('PRAGMA foreign_keys = ON;')
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    
    schema_path = os.path.join(current_app.root_path, 'schema.sql')
    if os.path.exists(schema_path):
        with open(schema_path, 'r', encoding='utf-8') as f:
            db.executescript(f.read())
        db.commit()

def init_app(app):
    app.teardown_appcontext(close_db)
    
    # Initialize DB on start if not exists
    with app.app_context():
        db_path = app.config['DATABASE']
        if not os.path.exists(db_path):
            init_db()
        # Safe migrations — run every startup, only do work if column missing
        _run_migrations()

def _run_migrations():
    """Safe schema migrations that add missing columns to existing databases."""
    db = get_db()
    # Add is_published to quizzes if it doesn't exist
    cols = [row[1] for row in db.execute("PRAGMA table_info(quizzes)").fetchall()]
    if 'is_published' not in cols:
        db.execute('ALTER TABLE quizzes ADD COLUMN is_published INTEGER DEFAULT 0')
        db.commit()
