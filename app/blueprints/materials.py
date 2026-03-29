import uuid, os
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from .auth import login_required
from ..database import get_db

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'pptx', 'docx', 'jpg', 'jpeg', 'png', 'gif', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


bp = Blueprint('materials', __name__)

@bp.route('/classrooms/<class_id>/materials', methods=['GET', 'POST'])
@login_required
def manage_materials(class_id):
    db = get_db()
    
    if request.method == 'GET':
        rows = db.execute('SELECT * FROM materials WHERE classroom_id = ? ORDER BY created_at DESC', (class_id,)).fetchall()
        return jsonify({'materials': [dict(r) for r in rows]}), 200
        
    if request.method == 'POST':
        data = request.json
        title = data.get('title')
        is_announcement = data.get('is_announcement', False)
        
        m_id = str(uuid.uuid4())
        
        db.execute('''
            INSERT INTO materials (id, classroom_id, title, file_url, file_type, size_kb, is_announcement, announcement_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            m_id, class_id, title,
            data.get('file_url', ''), data.get('file_type', ''), data.get('size_kb', 0),
            1 if is_announcement else 0, data.get('announcement_text', '')
        ))
        db.commit()
        return jsonify({'message': 'Added successfully', 'id': m_id}), 201

# Duplicate route for student explicitly (could also use the same route with auth logic check)
@bp.route('/student/classrooms/<class_id>/materials', methods=['GET'])
@login_required
def student_materials(class_id):
    db = get_db()
    rows = db.execute('SELECT * FROM materials WHERE classroom_id = ? ORDER BY created_at DESC', (class_id,)).fetchall()
    return jsonify({'materials': [dict(r) for r in rows]}), 200

# ── Multipart file upload endpoint (no Firebase required) ──────────────
@bp.route('/classrooms/<class_id>/materials/upload', methods=['POST'])
@login_required
def upload_material_file(class_id):
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400

    # Save file to uploads folder
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4()}.{ext}"
    save_path = os.path.join(UPLOAD_FOLDER, unique_name)
    file.save(save_path)

    size_kb = os.path.getsize(save_path) // 1024
    file_url = f"/uploads/{unique_name}"  # relative URL served statically

    title = request.form.get('title', file.filename)
    topic_tags_raw = request.form.get('topic_tags', '[]')
    try:
        import json
        topic_tags = json.loads(topic_tags_raw)
    except Exception:
        topic_tags = []

    m_id = str(uuid.uuid4())
    db = get_db()
    db.execute('''
        INSERT INTO materials (id, classroom_id, title, file_url, file_type, size_kb, is_announcement, announcement_text)
        VALUES (?, ?, ?, ?, ?, ?, 0, '')
    ''', (m_id, class_id, title, file_url, ext, size_kb))
    db.commit()

    return jsonify({'message': 'Uploaded successfully', 'id': m_id, 'file_url': file_url}), 201

@bp.route('/classrooms/<class_id>/materials/<material_id>', methods=['DELETE'])
@login_required
def delete_material(class_id, material_id):
    db = get_db()
    # verify material belongs to class
    mat = db.execute('SELECT * FROM materials WHERE id = ? AND classroom_id = ?', (material_id, class_id)).fetchone()
    if not mat:
        return jsonify({'error': 'Material not found'}), 404
    
    # Optional: Delete physical file if it exists
    file_url = mat['file_url']
    if file_url and file_url.startswith('/uploads/'):
        filename = file_url.split('/')[-1]
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                pass # ignore if file couldn't be deleted from disk
                
    db.execute('DELETE FROM materials WHERE id = ?', (material_id,))
    db.commit()
    
    return jsonify({'message': 'Material deleted successfully'}), 200
