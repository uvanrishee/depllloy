from flask import Blueprint, jsonify, request
from .auth import login_required
from ..database import get_db

bp = Blueprint('mistakes', __name__)

@bp.route('/student/mistakes', methods=['GET'])
@login_required
def get_mistakes():
    uid = request.user.get('uid')
    db = get_db()
    rows = db.execute('''
        SELECT m.*, c.subject as classroom_subject 
        FROM mistakes m
        LEFT JOIN classrooms c ON m.classroom_id = c.id
        WHERE m.student_id = ? 
        ORDER BY m.logged_at DESC
    ''', (uid,)).fetchall()
    return jsonify({'mistakes': [dict(r) for r in rows]})

@bp.route('/student/mistakes/<mistake_id>/resolve', methods=['POST'])
@login_required
def resolve_mistake(mistake_id):
    uid = request.user.get('uid')
    db = get_db()
    db.execute('UPDATE mistakes SET status = "resolved" WHERE id = ? AND student_id = ?', (mistake_id, uid))
    db.commit()
    return jsonify({'message': 'Mistake resolved'}), 200

@bp.route('/student/mistakes/<mistake_id>', methods=['DELETE'])
@login_required
def delete_mistake(mistake_id):
    uid = request.user.get('uid')
    db = get_db()
    db.execute('DELETE FROM mistakes WHERE id = ? AND student_id = ?', (mistake_id, uid))
    db.commit()
    return jsonify({'message': 'Mistake deleted'}), 200

@bp.route('/student/activity', methods=['GET'])
@login_required
def student_activity():
    uid = request.user.get('uid')
    db = get_db()
    # Get recent completed quizzes for activity
    # Fetch recent quiz activity
    quiz_attempts = db.execute('''
        SELECT q.title as title, qa.xp_earned, qa.completed_at
        FROM quiz_attempts qa
        JOIN quizzes q ON qa.quiz_id = q.id
        WHERE qa.student_id = ?
        ORDER BY qa.completed_at DESC
        LIMIT 10
    ''', (uid,)).fetchall()
    
    activity = []
    for qa in quiz_attempts:
        time_str = str(qa['completed_at']).split()[0] if qa['completed_at'] else 'Recently'
        activity.append({
            'emoji': '🎯',
            'text': f"Completed '{qa['title']}' Quiz",
            'time_ago': time_str
        })
        if qa['xp_earned'] and qa['xp_earned'] > 0:
            activity.append({
                'emoji': '⭐',
                'text': f"Earned {qa['xp_earned']} XP in '{qa['title']}'",
                'time_ago': time_str
            })
    
    return jsonify({'activity': activity})

@bp.route('/student/topics', methods=['GET'])
@login_required
def student_topics():
    uid = request.user.get('uid')
    db = get_db()
    # Fetch materials from enrolled classrooms as topics
    rows = db.execute('''
        SELECT m.id, m.title as topic_name, c.name as classroom_name, c.subject as subject, 
               c.id as classroom_id, m.file_url,
               COALESCE((SELECT AVG(qa.score*100.0/qa.total_questions) 
                         FROM quiz_attempts qa 
                         JOIN quizzes q ON qa.quiz_id = q.id 
                         WHERE qa.student_id = ? AND q.classroom_id = c.id), 0) as progress,
               m.topic_tags
        FROM materials m
        JOIN classrooms c ON m.classroom_id = c.id
        JOIN enrollments e ON c.id = e.classroom_id
        WHERE e.student_id = ? AND m.is_announcement = 0
        LIMIT 10
    ''', (uid, uid)).fetchall()
    
    topics = []
    for r in rows:
        import json
        subtopics = []
        try:
            if r['topic_tags']:
                tags = json.loads(r['topic_tags'])
                for tag in tags:
                    subtopics.append({'name': tag, 'mastery': int(r['progress'])})
        except:
            pass
        topics.append({
            'id': r['id'],
            'topic_name': r['topic_name'],
            'classroom_id': r['classroom_id'],
            'file_url': r['file_url'],
            'classroom_name': r['classroom_name'],
            'subject': r['subject'],
            'progress': int(r['progress']),
            'subtopics': subtopics
        })
    return jsonify({'topics': topics})
