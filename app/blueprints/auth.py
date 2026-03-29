import functools
import os
from flask import Blueprint, request, jsonify
from firebase_admin import auth as firebase_auth
from ..database import get_db
from datetime import datetime, date, timedelta

bp = Blueprint('auth', __name__, url_prefix='/auth')

def verify_token(token):
    # Mock token verification for dev without real firebase keys
    if not os.path.exists(os.path.join(os.path.dirname(os.path.dirname(__file__)), '../firebase-service-account.json')):
        # MOCK IMPLEMENTATION
        return {'uid': token if token != 'null' else 'mock_user_123', 'email': 'mock@example.com'}
    
    # REAL IMPLEMENTATION
    try:
        decoded_token = firebase_auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        return None

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized: Missing or invalid token'}), 401
        
        token = auth_header.split(' ')[1]
        user_info = verify_token(token)
        
        if not user_info:
            return jsonify({'error': 'Unauthorized: Invalid token'}), 401
            
        request.user = user_info
        return view(**kwargs)
    return wrapped_view

@bp.route('/register', methods=['POST'])
@login_required
def register():
    data = request.json
    uid = request.user.get('uid')
    email = data.get('email', request.user.get('email'))
    name = data.get('name')
    role = data.get('role')

    if not all([uid, email, name, role]):
        return jsonify({'error': 'Missing required fields'}), 400

    db = get_db()
    try:
        # Check if user exists
        existing = db.execute('SELECT id FROM users WHERE id = ?', (uid,)).fetchone()
        if existing:
            return jsonify({'message': 'User already registered', 'uid': uid}), 200

        db.execute(
            'INSERT INTO users (id, email, name, role) VALUES (?, ?, ?, ?)',
            (uid, email, name, role)
        )
        
        # Give student an initial game profile
        if role == 'student':
            db.execute(
                'INSERT INTO game_profiles (user_id, xp, streak) VALUES (?, 0, 0)',
                (uid,)
            )
            
        db.commit()
        return jsonify({'message': 'User registered successfully', 'uid': uid}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/profile', methods=['GET'])
@login_required
def profile():
    uid = request.user.get('uid')
    db = get_db()
    
    user = db.execute('SELECT id, email, name, role FROM users WHERE id = ?', (uid,)).fetchone()
    if not user:
        return jsonify({'error': 'User not found in DB but token is valid.'}), 404
        
    res = dict(user)
    
    if res['role'] == 'student':
        gp = db.execute('SELECT xp, streak, last_active FROM game_profiles WHERE user_id = ?', (uid,)).fetchone()
        if gp:
            res['xp'] = gp['xp']
            
            # ── Streak Logic ── (Student only)
            today = date.today()
            last_active_str = gp['last_active']
            current_streak  = gp['streak'] or 0
            
            # Badge lookup
            badge_count = db.execute('''
                SELECT COUNT(*) as cnt FROM battles 
                WHERE (challenger_id = ? OR opponent_id = ?) 
                AND badge_awarded = 1
            ''', (uid, uid)).fetchone()['cnt']
            res['badges'] = badge_count
            
            # Simple streak calculation
            if not last_active_str:
                new_streak = 1
                db.execute('UPDATE game_profiles SET streak = ?, last_active = ? WHERE user_id = ?', (new_streak, today, uid))
            else:
                try:
                    # SQLite DATE usually 'YYYY-MM-DD'
                    last_active = datetime.strptime(last_active_str, '%Y-%m-%d').date()
                except:
                    last_active = None
                
                if last_active == today:
                    new_streak = current_streak
                elif last_active == today - timedelta(days=1):
                    new_streak = current_streak + 1
                    db.execute('UPDATE game_profiles SET streak = ?, last_active = ? WHERE user_id = ?', (new_streak, today, uid))
                else:
                    new_streak = 1
                    db.execute('UPDATE game_profiles SET streak = ?, last_active = ? WHERE user_id = ?', (new_streak, today, uid))
            
            res['streak'] = new_streak
            db.commit()
            
    return jsonify(res), 200
