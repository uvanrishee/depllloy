import uuid
import json
from flask import Blueprint, request, jsonify
from .auth import login_required
from ..database import get_db

bp = Blueprint('quizzes', __name__)

# ─── Teacher: list quizzes for a specific classroom ──────────────────────────
@bp.route('/classrooms/<class_id>/quizzes', methods=['GET'])
@login_required
def get_classroom_quizzes(class_id):
    db = get_db()
    rows = db.execute('''
        SELECT q.*, 
               (SELECT COUNT(*) FROM quiz_questions WHERE quiz_id = q.id) as question_count,
               (SELECT COUNT(*) FROM quiz_attempts WHERE quiz_id = q.id) as attempt_count
        FROM quizzes q WHERE q.classroom_id = ? ORDER BY q.created_at DESC
    ''', (class_id,)).fetchall()
    return jsonify({'quizzes': [dict(r) for r in rows]}), 200

# ─── Teacher: publish a manually-written quiz ────────────────────────────────
@bp.route('/quizzes', methods=['POST'])
@login_required
def create_quiz():
    data = request.json
    classroom_id = data.get('classroom_id')
    title        = data.get('title', 'Untitled Quiz')
    description  = data.get('description', '')
    difficulty   = data.get('difficulty_level', 'intermediate')
    time_limit   = data.get('time_limit', 15)
    raw_q        = data.get('questions', {})  # can be dict (AI) or list (manual)
    
    if not classroom_id:
        return jsonify({'error': 'classroom_id required'}), 400

    db  = get_db()
    qid = str(uuid.uuid4())
    db.execute(
        'INSERT INTO quizzes (id, classroom_id, title, description, difficulty_level, is_published) VALUES (?, ?, ?, ?, ?, 1)',
        (qid, classroom_id, title, description, difficulty)
    )

    # Flatten questions — accept both list and dict-of-levels format
    questions_list = []
    if isinstance(raw_q, list):
        questions_list = raw_q
    elif isinstance(raw_q, dict):
        for level_qs in raw_q.values():
            questions_list.extend(level_qs)

    for q in questions_list:
        db.execute('''
            INSERT INTO quiz_questions (id, quiz_id, question_text, option_a, option_b, option_c, option_d, correct_option, explanation, topic_tag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()), qid,
            q.get('question_text', ''), q.get('option_a', ''), q.get('option_b', ''),
            q.get('option_c', ''), q.get('option_d', ''), q.get('correct_option', 'a'),
            q.get('explanation', ''), q.get('topic_tag', '')
        ))

    db.commit()
    return jsonify({'quiz_id': qid, 'message': 'Quiz published'}), 201

# ─── Student: list all available quizzes across enrolled classrooms ───────────
@bp.route('/student/quizzes', methods=['GET'])
@login_required
def list_student_quizzes():
    uid = request.user.get('uid')
    db  = get_db()
    
    # Get only TEACHER-PUBLISHED quizzes from classrooms this student is enrolled in
    rows = db.execute('''
        SELECT q.id, q.title, q.description, q.difficulty_level, q.created_at,
               c.name as classroom_name, c.subject,
               (SELECT COUNT(*) FROM quiz_questions WHERE quiz_id = q.id) as question_count,
               (SELECT COUNT(*) FROM quiz_attempts WHERE quiz_id = q.id AND student_id = ?) as attempts_made
        FROM quizzes q
        JOIN classrooms c ON q.classroom_id = c.id
        JOIN enrollments e ON c.id = e.classroom_id
        WHERE e.student_id = ? AND q.is_published = 1
        ORDER BY q.created_at DESC
    ''', (uid, uid)).fetchall()
    
    return jsonify({'quizzes': [dict(r) for r in rows]}), 200

# ─── Student: get one quiz to take ───────────────────────────────────────────
@bp.route('/student/quizzes/<quiz_id>', methods=['GET'])
@login_required
def get_student_quiz(quiz_id):
    db = get_db()
    q = db.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
    if not q: return jsonify({'error': 'Not found'}), 404
    
    questions = db.execute('''
        SELECT id, question_text, option_a, option_b, option_c, option_d 
        FROM quiz_questions WHERE quiz_id = ?
    ''', (quiz_id,)).fetchall()
    
    return jsonify({'quiz': dict(q), 'questions': [dict(x) for x in questions]}), 200

# ─── Student: submit a quiz attempt ──────────────────────────────────────────
@bp.route('/student/quizzes/<quiz_id>/submit', methods=['POST'])
@login_required
def submit_quiz(quiz_id):
    uid = request.user.get('uid')
    answers = request.json.get('answers', []) # [{question_id, selected_option}]
    
    db = get_db()
    questions = db.execute('SELECT id, correct_option, explanation, question_text, topic_tag FROM quiz_questions WHERE quiz_id = ?', (quiz_id,)).fetchall()
    
    q_dict = {q['id']: dict(q) for q in questions}
    
    correct = 0
    total = len(questions)
    details = []
    
    for a in answers:
        q_id = a.get('question_id')
        sel = a.get('selected_option')
        
        if q_id in q_dict:
            q_info = q_dict[q_id]
            is_correct = (sel == q_info['correct_option'])
            if is_correct: 
                correct += 1
            else:
                db.execute('''
                    INSERT INTO mistakes (id, student_id, classroom_id, question_text, student_input, correct_answer, error_category)
                    VALUES (?, ?, (SELECT classroom_id FROM quizzes WHERE id = ?), ?, ?, ?, ?)
                ''', (
                    str(uuid.uuid4()), uid, quiz_id,
                    q_info['question_text'], sel or 'No answer', q_info['correct_option'], q_info['topic_tag'] or 'Concept'
                ))
            
            details.append({
                'question_id': q_id,
                'question_text': q_info['question_text'],
                'is_correct': is_correct,
                'selected': sel,
                'correct': q_info['correct_option'],
                'explanation': q_info['explanation']
            })
            
    pct = (correct / total) * 100 if total > 0 else 0
    
    # Check if student already has a previous attempt for this quiz
    prev_attempt = db.execute('SELECT id FROM quiz_attempts WHERE student_id = ? AND quiz_id = ?', (uid, quiz_id)).fetchone()
    
    if prev_attempt:
        xp_earned = 0
    else:
        xp_earned = int((pct / 100) * 50)
        if pct >= 80: xp_earned += 20
    
    db.execute('''
        INSERT INTO quiz_attempts (id, student_id, quiz_id, score, total_questions, xp_earned)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (str(uuid.uuid4()), uid, quiz_id, correct, total, xp_earned))
    
    if xp_earned > 0:
        db.execute('UPDATE game_profiles SET xp = xp + ? WHERE user_id = ?', (xp_earned, uid))
    db.commit()
    
    return jsonify({
        'score': correct,
        'total': total,
        'percentage': pct,
        'xp_earned': xp_earned,
        'details': details
    }), 200


# ─── Teacher: get quiz analytics (student performance) ──────────────────────
@bp.route('/quizzes/<quiz_id>/analytics', methods=['GET'])
@login_required
def get_quiz_analytics(quiz_id):
    db = get_db()
    
    # 1. Get quiz info
    quiz = db.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
    if not quiz:
        return jsonify({'error': 'Quiz not found'}), 404
    
    # 2. Get attempts with student names
    # We take the BEST attempt per student for simplicity in the main list, 
    # but we can also return all if needed. Let's return all attempts for now.
    attempts_rows = db.execute('''
        SELECT qa.*, u.name as student_name, u.email as student_email
        FROM quiz_attempts qa
        JOIN users u ON qa.student_id = u.id
        WHERE qa.quiz_id = ?
        ORDER BY qa.completed_at DESC
    ''', (quiz_id,)).fetchall()
    
    attempts = [dict(r) for r in attempts_rows]
    
    if not attempts:
        return jsonify({
            'quiz': dict(quiz),
            'attempts': [],
            'stats': {
                'avg_score_pct': 0,
                'max_score_pct': 0,
                'min_score_pct': 0,
                'total_attempts': 0,
                'unique_students': 0
            }
        }), 200
        
    # 3. Calculate Stats
    scores_pct = [(r['score'] * 100 / r['total_questions']) if r['total_questions'] > 0 else 0 for r in attempts]
    unique_students = len(set(r['student_id'] for r in attempts))
    
    stats = {
        'avg_score_pct': round(sum(scores_pct) / len(scores_pct), 1),
        'max_score_pct': round(max(scores_pct), 1),
        'min_score_pct': round(min(scores_pct), 1),
        'total_attempts': len(attempts),
        'unique_students': unique_students
    }
    
    # 4. Score Distribution (0-25, 26-50, 51-75, 76-100)
    dist = {'0-25%': 0, '26-50%': 0, '51-75%': 0, '76-100%': 0}
    for s in scores_pct:
        if s <= 25: dist['0-25%'] += 1
        elif s <= 50: dist['26-50%'] += 1
        elif s <= 75: dist['51-75%'] += 1
        else: dist['76-100%'] += 1
        
    stats['distribution'] = [{'range': k, 'count': v} for k, v in dist.items()]
    
    return jsonify({
        'quiz': dict(quiz),
        'attempts': attempts,
        'stats': stats
    }), 200
