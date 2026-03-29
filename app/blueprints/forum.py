import uuid
from flask import Blueprint, request, jsonify
from .auth import login_required
from ..database import get_db

bp = Blueprint('forum', __name__, url_prefix='/forum')

@bp.route('/<classroom_id>', methods=['GET'])
@login_required
def get_posts(classroom_id):
    db = get_db()
    # Get all parent posts
    parents = db.execute('''
        SELECT f.*, u.role as author_role, u.name as raw_author_name
        FROM forum_posts f
        JOIN users u ON f.author_id = u.id
        WHERE f.classroom_id = ? AND f.parent_post_id IS NULL
        ORDER BY f.created_at DESC
    ''', (classroom_id,)).fetchall()
    
    # Get all replies for this classroom
    replies_query = db.execute('''
        SELECT f.*, u.role as author_role, u.name as raw_author_name
        FROM forum_posts f
        JOIN users u ON f.author_id = u.id
        WHERE f.classroom_id = ? AND f.parent_post_id IS NOT NULL
        ORDER BY f.created_at ASC
    ''', (classroom_id,)).fetchall()
    
    replies_by_parent = {}
    for r in replies_query:
        pid = r['parent_post_id']
        if pid not in replies_by_parent:
            replies_by_parent[pid] = []
        
        is_teacher = (r['author_role'] == 'teacher')
        replies_by_parent[pid].append({
            'id': r['id'],
            'body': r['body'],
            'created_at': r['created_at'],
            'upvotes': r['upvotes'],
            'is_teacher': is_teacher,
            'author_name': r['raw_author_name'] if is_teacher else ''
        })
        
    posts = []
    for p in parents:
        is_teacher = (p['author_role'] == 'teacher')
        posts.append({
            'id': p['id'],
            'title': p['title'],
            'body': p['body'],
            'created_at': p['created_at'],
            'upvotes': p['upvotes'],
            'is_teacher': is_teacher,
            'author_name': p['raw_author_name'] if is_teacher else '',
            'replies': replies_by_parent.get(p['id'], [])
        })
        
    return jsonify({'posts': posts}), 200

@bp.route('/<classroom_id>', methods=['POST'])
@login_required
def create_post(classroom_id):
    uid = request.user.get('uid')
    data = request.json
    title = data.get('title', '').strip()
    body = data.get('body', '').strip()
    
    if not title or not body:
        return jsonify({'error': 'Title and Body are required'}), 400
        
    db = get_db()
    post_id = str(uuid.uuid4())
    db.execute('''
        INSERT INTO forum_posts (id, classroom_id, author_id, title, body)
        VALUES (?, ?, ?, ?, ?)
    ''', (post_id, classroom_id, uid, title, body))
    db.commit()
    
    return jsonify({'message': 'Post created', 'id': post_id}), 201

@bp.route('/posts/<post_id>/reply', methods=['POST'])
@login_required
def reply_post(post_id):
    uid = request.user.get('uid')
    data = request.json
    body = data.get('body', '').strip()
    
    if not body:
        return jsonify({'error': 'Reply body is required'}), 400
        
    db = get_db()
    parent = db.execute('SELECT classroom_id FROM forum_posts WHERE id = ?', (post_id,)).fetchone()
    if not parent:
        return jsonify({'error': 'Parent post not found'}), 404
        
    reply_id = str(uuid.uuid4())
    # title can't be null based on schema, so we just supply "Reply"
    db.execute('''
        INSERT INTO forum_posts (id, classroom_id, author_id, title, body, parent_post_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (reply_id, parent['classroom_id'], uid, "Reply", body, post_id))
    db.commit()
    
    return jsonify({'message': 'Reply added', 'id': reply_id}), 201

@bp.route('/posts/<post_id>/vote', methods=['POST'])
@login_required
def vote_post(post_id):
    data = request.json
    vote = data.get('vote', 1)
    db = get_db()
    
    # In a real app we'd track who voted, but here we just increment
    db.execute('UPDATE forum_posts SET upvotes = upvotes + ? WHERE id = ?', (vote, post_id))
    db.commit()
    
    return jsonify({'message': 'Vote processed'}), 200
