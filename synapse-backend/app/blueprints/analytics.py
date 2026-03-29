from flask import Blueprint, jsonify, request
from .auth import login_required
from ..database import get_db
import uuid

bp = Blueprint('analytics', __name__)

@bp.route('/analytics/summary', methods=['GET'])
@login_required
def get_teacher_summary():
    uid = request.user.get('uid')
    db = get_db()
    # Number of classrooms
    classes = db.execute('SELECT COUNT(*) as c FROM classrooms WHERE teacher_id = ?', (uid,)).fetchone()['c']
    # Number of unique students
    students = db.execute('''
        SELECT COUNT(DISTINCT e.student_id) as c 
        FROM enrollments e 
        JOIN classrooms c ON e.classroom_id = c.id 
        WHERE c.teacher_id = ?
    ''', (uid,)).fetchone()['c']
    
    # Number of quizzes created
    quizzes = db.execute('''
        SELECT COUNT(*) as c
        FROM quizzes q
        JOIN classrooms c ON q.classroom_id = c.id
        WHERE c.teacher_id = ?
    ''', (uid,)).fetchone()['c']

    # Average score across all quizzes taken by students
    avg_score_row = db.execute('''
        SELECT AVG(CAST(qa.score AS FLOAT) * 100 / qa.total_questions) as avg_score
        FROM quiz_attempts qa
        JOIN quizzes q ON qa.quiz_id = q.id
        JOIN classrooms c ON q.classroom_id = c.id
        WHERE c.teacher_id = ? AND qa.total_questions > 0
    ''', (uid,)).fetchone()
    avg_score = avg_score_row['avg_score'] if avg_score_row and avg_score_row['avg_score'] is not None else 0
    
    return jsonify({
        'stats': {
            'classrooms': classes,
            'students': students,
            'quizzes': quizzes,
            'avg_score': avg_score
        },
        'recent': []
    }), 200

@bp.route('/analytics/class/<class_id>', methods=['GET'])
@login_required
def get_class_analytics(class_id):
    db = get_db()
    
    # Simple aggregates
    student_count = db.execute('SELECT COUNT(*) as c FROM enrollments WHERE classroom_id = ?', (class_id,)).fetchone()['c']
    
    # Category counts
    cats = db.execute('''
        SELECT category, COUNT(*) as c 
        FROM student_performance 
        WHERE classroom_id = ? 
        GROUP BY category
    ''', (class_id,)).fetchall()
    
    cat_counts = { 'weak': 0, 'average': 0, 'above_average': 0, 'topper': 0, 'new': 0 }
    for c in cats:
        cat_counts[c['category']] = c['c']
        
    # Real Topic Weakness Base
    weaknesses = db.execute('''
        SELECT error_category as topic, 
               CAST(COUNT(DISTINCT student_id) AS FLOAT) * 100 / ? as weakness_pct
        FROM mistakes
        WHERE classroom_id = ? AND error_category IS NOT NULL AND error_category != ''
        GROUP BY error_category
        ORDER BY weakness_pct DESC
        LIMIT 5
    ''', (max(student_count, 1), class_id)).fetchall()

    # Real Quiz Trends Base
    trends = db.execute('''
        SELECT strftime('%Y-%m-%d', qa.completed_at) as date, 
               AVG(CAST(qa.score AS FLOAT) * 100 / qa.total_questions) as avg_score
        FROM quiz_attempts qa
        JOIN quizzes q ON qa.quiz_id = q.id
        WHERE q.classroom_id = ? AND qa.total_questions > 0
        GROUP BY strftime('%Y-%m-%d', qa.completed_at)
        ORDER BY date ASC
        LIMIT 7
    ''', (class_id,)).fetchall()

    return jsonify({
        'analytics': {
            'total_students': student_count,
            'category_counts': cat_counts,
            'quiz_trend': [{'date': r['date'], 'avg_score': round(r['avg_score'], 1)} for r in trends],
            'topic_weakness': [{'topic': r['topic'], 'weakness_pct': round(r['weakness_pct'], 1)} for r in weaknesses],
            'score_distribution': [
                {'range': '0-40', 'count': cat_counts['weak']},
                {'range': '41-70', 'count': cat_counts['average']},
                {'range': '71-90', 'count': cat_counts['above_average']},
                {'range': '91-100', 'count': cat_counts['topper']},
            ]
        }
    }), 200

@bp.route('/classrooms/<class_id>/real-tests', methods=['GET', 'POST'])
@login_required
def manage_real_tests(class_id):
    db = get_db()
    if request.method == 'GET':
        rows = db.execute('SELECT * FROM real_tests WHERE classroom_id = ? ORDER BY test_date DESC', (class_id,)).fetchall()
        return jsonify({'tests': [dict(r) for r in rows]})
    
    # POST
    data = request.json
    tid = str(uuid.uuid4())
    db.execute('INSERT INTO real_tests (id, classroom_id, name, max_marks, test_date) VALUES (?, ?, ?, ?, ?)',
               (tid, class_id, data['name'], data['max_marks'], data['test_date']))
    db.commit()
    return jsonify({'test': {'id': tid, 'name': data['name'], 'max_marks': data['max_marks'], 'test_date': data.get('test_date', '')}}), 201


@bp.route('/real-tests/<test_id>/marks', methods=['GET', 'POST'])
@login_required
def manage_test_marks(test_id):
    db = get_db()

    if request.method == 'GET':
        # Return saved marks for this test
        rows = db.execute(
            'SELECT student_id, marks_obtained FROM real_test_marks WHERE real_test_id = ?',
            (test_id,)
        ).fetchall()
        return jsonify({'marks': [dict(r) for r in rows]}), 200

    # POST — save/update marks and update student_performance
    data = request.json
    marks_list = data.get('marks', [])  # [{student_id, marks}, ...]

    # Get the test to know max_marks and classroom_id
    test = db.execute('SELECT * FROM real_tests WHERE id = ?', (test_id,)).fetchone()
    if not test:
        return jsonify({'error': 'Test not found'}), 404

    max_marks = test['max_marks']
    classroom_id = test['classroom_id']

    summary = {'weak': 0, 'average': 0, 'above_average': 0, 'topper': 0}

    for entry in marks_list:
        sid = entry['student_id']
        m   = float(entry.get('marks', 0))
        pct = (m / max_marks * 100) if max_marks > 0 else 0

        # Determine category from score
        if pct >= 90:
            cat = 'topper'
        elif pct >= 70:
            cat = 'above_average'
        elif pct >= 45:
            cat = 'average'
        else:
            cat = 'weak'

        summary[cat] += 1

        # Upsert into real_test_marks
        existing = db.execute(
            'SELECT id FROM real_test_marks WHERE real_test_id = ? AND student_id = ?',
            (test_id, sid)
        ).fetchone()

        if existing:
            db.execute(
                'UPDATE real_test_marks SET marks_obtained = ? WHERE real_test_id = ? AND student_id = ?',
                (m, test_id, sid)
            )
        else:
            db.execute(
                'INSERT INTO real_test_marks (id, real_test_id, student_id, marks_obtained) VALUES (?, ?, ?, ?)',
                (str(uuid.uuid4()), test_id, sid, m)
            )

        # Update student_performance
        db.execute('''
            UPDATE student_performance
            SET last_real_test_score = ?, category = ?, last_active = CURRENT_TIMESTAMP
            WHERE student_id = ? AND classroom_id = ?
        ''', (m, cat, sid, classroom_id))

    db.commit()
    return jsonify({'message': 'Marks saved', 'summary': summary}), 200


