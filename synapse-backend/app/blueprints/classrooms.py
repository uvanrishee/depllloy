import uuid
import random
import string
from flask import Blueprint, request, jsonify
from .auth import login_required
from ..database import get_db

bp = Blueprint('classrooms', __name__)

def generate_join_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

@bp.route('/classrooms', methods=['GET', 'POST'])
@login_required
def manage_classrooms():
    uid = request.user.get('uid')
    db = get_db()
    
    if request.method == 'GET':
        # Check role to determine what to return
        user = db.execute('SELECT role FROM users WHERE id = ?', (uid,)).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404
            
        role = user['role']
        if role == 'teacher':
            rows = db.execute('''
                SELECT c.id, c.name, c.subject, c.description, c.join_code, 
                       (SELECT COUNT(*) FROM enrollments e WHERE e.classroom_id = c.id) as student_count
                FROM classrooms c 
                WHERE c.teacher_id = ?
            ''', (uid,)).fetchall()
        else:
            # Student classrooms
            rows = db.execute('''
                SELECT c.id, c.name, c.subject, c.description, u.name as teacher_name
                FROM classrooms c
                JOIN enrollments e ON c.id = e.classroom_id
                JOIN users u ON c.teacher_id = u.id
                WHERE e.student_id = ?
            ''', (uid,)).fetchall()
            
        return jsonify({'classrooms': [dict(r) for r in rows]}), 200

    if request.method == 'POST':
        # Teacher creates classroom
        data = request.json
        name = data.get('name')
        subject = data.get('subject')
        desc = data.get('description', '')
        
        if not name or not subject:
             return jsonify({'error': 'Name and Subject required'}), 400
             
        class_id = str(uuid.uuid4())
        join_code = generate_join_code()
        
        db.execute(
            'INSERT INTO classrooms (id, name, subject, description, join_code, teacher_id) VALUES (?, ?, ?, ?, ?, ?)',
            (class_id, name, subject, desc, join_code, uid)
        )
        db.commit()
        
        return jsonify({
            'message': 'Classroom created', 
            'classroom': {'id': class_id, 'name': name, 'join_code': join_code}
        }), 201

# Teacher endpoints
@bp.route('/classrooms/<class_id>', methods=['GET'])
@login_required
def get_teacher_classroom_info(class_id):
    uid = request.user.get('uid')
    db = get_db()
    c = db.execute('''
        SELECT c.*, 
        (SELECT COUNT(*) FROM enrollments WHERE classroom_id = c.id) as student_count
        FROM classrooms c
        WHERE c.id = ? AND c.teacher_id = ?
    ''', (class_id, uid)).fetchone()
    
    if not c: return jsonify({'error': 'Not found or unauthorized'}), 404
    return jsonify({'classroom': dict(c)}), 200


# Teacher endpoints
@bp.route('/classrooms/<class_id>/students', methods=['GET'])
@login_required
def get_students(class_id):
    db = get_db()
    rows = db.execute('''
        SELECT u.id, u.name, u.email, sp.category, sp.avg_score, sp.last_real_test_score, sp.last_active, e.enrolled_at
        FROM enrollments e
        JOIN users u ON e.student_id = u.id
        LEFT JOIN student_performance sp ON u.id = sp.student_id AND sp.classroom_id = ?
        WHERE e.classroom_id = ?
    ''', (class_id, class_id)).fetchall()
    return jsonify({'students': [dict(r) for r in rows]}), 200

@bp.route('/classrooms/<class_id>/students/<student_id>', methods=['DELETE'])
@login_required
def remove_student(class_id, student_id):
    uid = request.user.get('uid')
    db = get_db()
    
    c = db.execute('SELECT id FROM classrooms WHERE id = ? AND teacher_id = ?', (class_id, uid)).fetchone()
    if not c:
        return jsonify({'error': 'Unauthorized or classroom not found'}), 403
        
    db.execute('DELETE FROM enrollments WHERE classroom_id = ? AND student_id = ?', (class_id, student_id))
    db.execute('DELETE FROM student_performance WHERE classroom_id = ? AND student_id = ?', (class_id, student_id))
    db.commit()
    
    return jsonify({'message': 'Student removed from classroom'}), 200

# Student endpoints
@bp.route('/student/classrooms/join', methods=['POST'])
@login_required
def join_classroom():
    uid = request.user.get('uid')
    code = request.json.get('join_code')
    if not code: return jsonify({'error': 'Join code required'}), 400
    
    db = get_db()
    c = db.execute('SELECT id, name FROM classrooms WHERE join_code = ?', (code,)).fetchone()
    if not c:
        return jsonify({'error': 'Invalid join code'}), 404
        
    class_id = c['id']

    # Check if already enrolled
    already = db.execute(
        'SELECT id FROM enrollments WHERE student_id = ? AND classroom_id = ?', (uid, class_id)
    ).fetchone()
    if already:
        return jsonify({'error': 'You are already enrolled in this classroom.'}), 400

    try:
        db.execute(
            'INSERT INTO enrollments (id, student_id, classroom_id) VALUES (?, ?, ?)',
            (str(uuid.uuid4()), uid, class_id)
        )
        # Explicitly set category='average' — 'new' is not in the CHECK constraint
        db.execute(
            'INSERT OR IGNORE INTO student_performance (student_id, classroom_id, category) VALUES (?, ?, ?)',
            (uid, class_id, 'average')
        )
        db.commit()
        return jsonify({'message': f"Joined {c['name']} successfully!", 'classroom_id': class_id}), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': f'Could not join classroom: {str(e)}'}), 400

@bp.route('/student/classrooms/<class_id>', methods=['GET'])
@login_required
def get_classroom_info(class_id):
    db = get_db()
    c = db.execute('''
        SELECT c.*, u.name as teacher_name,
        (SELECT COUNT(*) FROM enrollments WHERE classroom_id = c.id) as student_count
        FROM classrooms c
        JOIN users u ON c.teacher_id = u.id
        WHERE c.id = ?
    ''', (class_id,)).fetchone()
    if not c: return jsonify({'error': 'Not found'}), 404
    return jsonify({'classroom': dict(c)}), 200

@bp.route('/student/classrooms/<class_id>/classmates', methods=['GET'])
@login_required
def get_classmates(class_id):
    uid = request.user.get('uid')
    db = get_db()
    
    # Check if student is actually enrolled in this classroom
    enrolled = db.execute('SELECT 1 FROM enrollments WHERE classroom_id = ? AND student_id = ?', (class_id, uid)).fetchone()
    if not enrolled:
        return jsonify({'error': 'Unauthorized'}), 403
        
    # Return just student IDs and names, preserving privacy
    rows = db.execute('''
        SELECT u.id, u.name
        FROM enrollments e
        JOIN users u ON e.student_id = u.id
        WHERE e.classroom_id = ?
        ORDER BY u.name ASC
    ''', (class_id,)).fetchall()
    
    return jsonify({'classmates': [dict(r) for r in rows]}), 200
