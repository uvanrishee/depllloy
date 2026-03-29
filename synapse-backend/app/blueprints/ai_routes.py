import uuid
from flask import Blueprint, request, jsonify
from .auth import login_required
from ..database import get_db
from ..services.ai_service import generate_quiz, extract_text_from_url, refine_notes, chat_tutor

bp = Blueprint('ai_routes', __name__, url_prefix='/ai')

@bp.route('/quiz/generate', methods=['POST'])
@login_required
def gen_quiz():
    data = request.json
    class_id = data.get('classroom_id')
    diff = data.get('difficulty', 'intermediate')
    mode = data.get('source_mode', 'url')
    text = data.get('source_text', '')
    url = data.get('source_url', '')
    mat_id = data.get('material_id')
    total_q = data.get('total_questions', 5)
    do_save = data.get('save_to_db', False)
    
    db = get_db()
    
    # If a material ID is given (Teacher AI Generator), resolve its URL
    if mat_id:
        mat = db.execute('SELECT file_url FROM materials WHERE id = ?', (mat_id,)).fetchone()
        if mat and mat['file_url']:
            url = mat['file_url']
            mode = 'url'

    if mode == 'url' and url:
        text = extract_text_from_url(url, 'pdf')
        
    try:
        questions = generate_quiz(text, diff, total_q)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    # Save the quiz directly if requested (e.g. Student On-Demand quizzes)
    if do_save and class_id:
        qid = str(uuid.uuid4())
        db.execute('INSERT INTO quizzes (id, classroom_id, title, difficulty_level) VALUES (?, ?, ?, ?)',
                   (qid, class_id, data.get('title', f'AI Quiz - {diff.capitalize()}'), diff))
        for q in questions:
            db.execute('''
                INSERT INTO quiz_questions (id, quiz_id, question_text, option_a, option_b, option_c, option_d, correct_option, explanation, topic_tag)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (str(uuid.uuid4()), qid, q['question_text'], q['option_a'], q['option_b'], q['option_c'], q['option_d'], q['correct_option'], q.get('explanation', ''), q.get('topic_tag', '')))
        db.commit()
        return jsonify({'message': 'Quiz created', 'quiz_id': qid, 'questions': questions}), 201

    return jsonify({'questions': questions}), 200

@bp.route('/notes/refine', methods=['POST'])
@login_required
def ai_refine_notes():
    text = request.json.get('text', '')
    url = request.json.get('file_url')
    if url:
        text = extract_text_from_url(url, request.json.get('file_type', 'pdf'))
        
    try:
        refined = refine_notes(text)
        return jsonify({'refined': refined}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/chat', methods=['POST'])
@login_required
def ai_chat():
    msg = request.json.get('message', '')
    ctx = request.json.get('context', '')
    reply = chat_tutor(msg, ctx)
    return jsonify({'reply': reply}), 200
