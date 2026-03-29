import uuid
import json
from flask import Blueprint, request, jsonify
from .auth import login_required
from ..database import get_db

bp = Blueprint('friends', __name__, url_prefix='/social')

# ─── Leaderboard ─────────────────────────────────────────────────────────────
@bp.route('/leaderboard', methods=['GET'])
@login_required
def global_leaderboard():
    uid = request.user.get('uid')
    db = get_db()
    rows = db.execute('''
        SELECT u.id, u.name, g.xp, g.streak 
        FROM game_profiles g
        JOIN users u ON g.user_id = u.id
        WHERE u.id = ? 
           OR EXISTS (
               SELECT 1 FROM friends f 
               WHERE ((f.user1_id = ? AND f.user2_id = u.id) 
                  OR (f.user2_id = ? AND f.user1_id = u.id))
                 AND f.status = 'accepted'
           )
        ORDER BY g.xp DESC LIMIT 50
    ''', (uid, uid, uid)).fetchall()
    return jsonify({'leaderboard': [dict(r) for r in rows]})

# ─── Friends ──────────────────────────────────────────────────────────────────
@bp.route('/friends', methods=['GET'])
@login_required
def get_friends():
    uid = request.user.get('uid')
    db = get_db()
    
    f_rows = db.execute('''
        SELECT u.id, u.name, g.xp, g.streak 
        FROM friends f
        JOIN users u ON (f.user1_id = u.id OR f.user2_id = u.id)
        JOIN game_profiles g ON u.id = g.user_id
        WHERE (f.user1_id = ? OR f.user2_id = ?) AND u.id != ? AND f.status = 'accepted'
    ''', (uid, uid, uid)).fetchall()
    
    r_rows = db.execute('''
        SELECT f.id, u.name as from_name
        FROM friends f
        JOIN users u ON f.user1_id = u.id
        WHERE f.user2_id = ? AND f.status = 'pending'
    ''', (uid,)).fetchall()
    
    return jsonify({
        'friends': [dict(r) for r in f_rows],
        'requests': [dict(r) for r in r_rows]
    })

@bp.route('/friends/request', methods=['POST'])
@login_required
def send_request():
    uid = request.user.get('uid')
    db = get_db()
    
    # Support both email and user_id
    friend_email = request.json.get('friend_email')
    friend_user_id = request.json.get('friend_user_id')
    
    if friend_user_id:
        target = db.execute('SELECT id FROM users WHERE id = ?', (friend_user_id,)).fetchone()
    elif friend_email:
        target = db.execute('SELECT id FROM users WHERE email = ?', (friend_email,)).fetchone()
    else:
        return jsonify({'error': 'friend_email or friend_user_id required'}), 400
    
    if not target: return jsonify({'error': 'User not found'}), 404
    tid = target['id']
    if tid == uid: return jsonify({'error': "Can't add yourself"}), 400
    
    # Check if friendship already exists in either direction
    existing = db.execute(
        'SELECT id, status FROM friends WHERE (user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?)',
        (uid, tid, tid, uid)
    ).fetchone()
    if existing:
        if existing['status'] == 'accepted':
            return jsonify({'error': 'Already friends'}), 400
        return jsonify({'error': 'Request already pending'}), 400
    
    try:
        db.execute('INSERT INTO friends (id, user1_id, user2_id, status) VALUES (?, ?, ?, ?)', 
                   (str(uuid.uuid4()), uid, tid, 'pending'))
        db.commit()
        return jsonify({'message': 'Request sent'})
    except Exception as e:
        return jsonify({'error': 'Request already exists'}), 400

@bp.route('/friends/respond', methods=['POST'])
@login_required
def respond_request():
    req_id = request.json.get('request_id')
    act = request.json.get('action')  # 'accept' or 'reject'
    db = get_db()
    
    if act == 'accept':
        db.execute("UPDATE friends SET status = 'accepted' WHERE id = ?", (req_id,))
    else:
        db.execute("DELETE FROM friends WHERE id = ?", (req_id,))
    db.commit()
    return jsonify({'message': 'Done'})

# ─── Boss Battles (private 2-player raids) ───────────────────────────────────
@bp.route('/battles', methods=['GET'])
@login_required
def active_battles():
    uid = request.user.get('uid')
    db = get_db()
    
    rows = db.execute('''
        SELECT b.id, b.status, b.winner_id, b.created_at,
               u1.id as player1_id, u1.name as player1_name,
               u2.id as player2_id, u2.name as player2_name,
               b.challenger_score, b.opponent_score,
               b.badge_awarded
        FROM battles b
        JOIN users u1 ON b.challenger_id = u1.id
        JOIN users u2 ON b.opponent_id = u2.id
        WHERE (b.challenger_id = ? OR b.opponent_id = ?)
        ORDER BY b.created_at DESC
    ''', (uid, uid)).fetchall()
    
    battles = []
    for r in rows:
        d = dict(r)
        d['is_challenger'] = (r['player1_id'] == uid)
        battles.append(d)
    
    return jsonify({'battles': battles})

@bp.route('/battles/challenge', methods=['POST'])
@login_required
def challenge_friend():
    uid = request.user.get('uid')
    target_id = request.json.get('target_user_id')
    db = get_db()
    
    # Verify they are friends
    friendship = db.execute(
        "SELECT id FROM friends WHERE ((user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?)) AND status = 'accepted'",
        (uid, target_id, target_id, uid)
    ).fetchone()
    if not friendship:
        return jsonify({'error': 'You must be friends to battle'}), 403
    
    # Check no active battle between them already
    existing = db.execute(
        "SELECT id FROM battles WHERE ((challenger_id = ? AND opponent_id = ?) OR (challenger_id = ? AND opponent_id = ?)) AND status IN ('pending', 'active')",
        (uid, target_id, target_id, uid)
    ).fetchone()
    if existing:
        return jsonify({'error': 'A battle between you two is already active'}), 400
    
    battle_id = str(uuid.uuid4())
    db.execute('''
        INSERT INTO battles (id, challenger_id, opponent_id, status, challenger_score, opponent_score, badge_awarded)
        VALUES (?, ?, ?, 'pending', -1, -1, 0)
    ''', (battle_id, uid, target_id))
    db.commit()
    
    return jsonify({'message': 'Boss battle initiated!', 'battle_id': battle_id})

@bp.route('/battles/questions', methods=['GET'])
@login_required
def get_battle_questions():
    uid = request.user.get('uid')
    db = get_db()
    
    rows = db.execute('''
        SELECT qq.id, qq.question_text, qq.option_a, qq.option_b, qq.option_c, qq.option_d, qq.correct_option
        FROM quiz_questions qq
        JOIN quizzes q ON qq.quiz_id = q.id
        JOIN enrollments e ON q.classroom_id = e.classroom_id
        WHERE e.student_id = ?
        ORDER BY RANDOM() LIMIT 10
    ''', (uid,)).fetchall()
    
    if len(rows) < 5:
        # Fallback questions if they don't have enough real ones
        fallback = [
            {'id': 'f1', 'question_text': 'What is the main function of red blood cells?', 'option_a': 'Carry oxygen', 'option_b': 'Fight infection', 'option_c': 'Clot blood', 'option_d': 'Digestion', 'correct_option': 'a'},
            {'id': 'f2', 'question_text': 'Which physics principle explains why ships float?', 'option_a': 'Newton\'s Third Law', 'option_b': 'Bernoulli\'s Principle', 'option_c': 'Archimedes\' Principle', 'option_d': 'Boyle\'s Law', 'correct_option': 'c'},
            {'id': 'f3', 'question_text': 'What is the chemical symbol for Gold?', 'option_a': 'Go', 'option_b': 'Au', 'option_c': 'Ag', 'option_d': 'Gd', 'correct_option': 'b'},
            {'id': 'f4', 'question_text': 'Solve for x: 2x + 5 = 15', 'option_a': '5', 'option_b': '10', 'option_c': '4', 'option_d': '20', 'correct_option': 'a'},
            {'id': 'f5', 'question_text': 'What is the powerhouse of the cell?', 'option_a': 'Nucleus', 'option_b': 'Mitochondria', 'option_c': 'Ribosome', 'option_d': 'Endoplasmic Reticulum', 'correct_option': 'b'},
            {'id': 'f6', 'question_text': 'What is the largest organ in the human body?', 'option_a': 'Heart', 'option_b': 'Brain', 'option_c': 'Liver', 'option_d': 'Skin', 'correct_option': 'd'},
            {'id': 'f7', 'question_text': 'What type of rock is formed from volcanic magma?', 'option_a': 'Sedimentary', 'option_b': 'Igneous', 'option_c': 'Metamorphic', 'option_d': 'Fossilized', 'correct_option': 'b'}
        ]
        return jsonify({'questions': fallback})
        
    return jsonify({'questions': [dict(r) for r in rows]})


@bp.route('/battles/<battle_id>/accept', methods=['POST'])
@login_required
def accept_battle(battle_id):
    uid = request.user.get('uid')
    db = get_db()
    
    battle = db.execute("SELECT * FROM battles WHERE id = ? AND opponent_id = ? AND status = 'pending'", (battle_id, uid)).fetchone()
    if not battle:
        return jsonify({'error': 'Battle not found or not yours to accept'}), 404
    
    db.execute("UPDATE battles SET status = 'active' WHERE id = ?", (battle_id,))
    db.commit()
    return jsonify({'message': 'Battle accepted! The boss has spawned!'})

@bp.route('/battles/<battle_id>/submit', methods=['POST'])
@login_required
def submit_battle_score(battle_id):
    uid = request.user.get('uid')
    score = request.json.get('score', 0)
    db = get_db()
    
    battle = db.execute("SELECT * FROM battles WHERE id = ? AND status = 'active'", (battle_id,)).fetchone()
    if not battle:
        return jsonify({'error': 'Battle not found or not active'}), 404
    
    if uid == battle['challenger_id']:
        db.execute("UPDATE battles SET challenger_score = ? WHERE id = ?", (score, battle_id))
    elif uid == battle['opponent_id']:
        db.execute("UPDATE battles SET opponent_score = ? WHERE id = ?", (score, battle_id))
    else:
        return jsonify({'error': 'You are not part of this battle'}), 403
    
    db.commit()
    
    # Re-fetch to check if both have submitted
    updated = db.execute("SELECT * FROM battles WHERE id = ?", (battle_id,)).fetchone()
    c_score = updated['challenger_score']
    o_score = updated['opponent_score']
    
    # Check if both players have submitted (score is no longer -1)
    if c_score is not None and o_score is not None and c_score >= 0 and o_score >= 0:
        winner_id = battle['challenger_id'] if c_score >= o_score else battle['opponent_id']
        
        db.execute("UPDATE battles SET status = 'completed', winner_id = ? WHERE id = ?", (winner_id, battle_id))
        
        # Award XP to both participants (50 XP each for completing the boss raid)
        db.execute("UPDATE game_profiles SET xp = xp + 50 WHERE user_id = ?", (battle['challenger_id'],))
        db.execute("UPDATE game_profiles SET xp = xp + 50 WHERE user_id = ?", (battle['opponent_id'],))
        
        # Extra 25 XP to winner
        db.execute("UPDATE game_profiles SET xp = xp + 25 WHERE user_id = ?", (winner_id,))
        
        # Mark badge awarded
        db.execute("UPDATE battles SET badge_awarded = 1 WHERE id = ?", (battle_id,))
        
        db.commit()
        
        return jsonify({
            'message': 'Battle complete! Badges awarded to both warriors!',
            'winner_id': winner_id,
            'challenger_score': c_score,
            'opponent_score': o_score,
            'battle_complete': True,
            'xp_awarded': 50
        })
    
    return jsonify({'message': 'Score recorded. Waiting for opponent...', 'battle_complete': False})

@bp.route('/battles/<battle_id>', methods=['GET'])
@login_required
def get_battle(battle_id):
    uid = request.user.get('uid')
    db = get_db()
    
    battle = db.execute('''
        SELECT b.*, 
               u1.name as player1_name, u2.name as player2_name
        FROM battles b
        JOIN users u1 ON b.challenger_id = u1.id
        JOIN users u2 ON b.opponent_id = u2.id
        WHERE b.id = ? AND (b.challenger_id = ? OR b.opponent_id = ?)
    ''', (battle_id, uid, uid)).fetchone()
    
    if not battle:
        return jsonify({'error': 'Battle not found or not yours'}), 404
    
    return jsonify({'battle': dict(battle)})

@bp.route('/battles/<battle_id>', methods=['DELETE'])
@login_required
def delete_battle(battle_id):
    uid = request.user.get('uid')
    db = get_db()
    
    battle = db.execute('''
        SELECT id FROM battles 
        WHERE id = ? AND (challenger_id = ? OR opponent_id = ?)
    ''', (battle_id, uid, uid)).fetchone()
    
    if not battle:
        return jsonify({'error': 'Battle not found or access denied'}), 404
        
    db.execute('DELETE FROM battles WHERE id = ?', (battle_id,))
    db.commit()
    return jsonify({'message': 'Battle removed successfully'})

