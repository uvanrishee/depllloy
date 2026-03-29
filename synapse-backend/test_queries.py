import sqlite3

with open('test_queries.log', 'w') as f:
    db = sqlite3.connect(r"c:\Academic\hackathon\synapse-backend\instance\synapse.db")
    db.row_factory = sqlite3.Row

    uid = db.execute("SELECT id FROM users WHERE role='student' LIMIT 1").fetchone()
    if not uid:
        f.write("No students found\n")
    else:
        uid = uid[0]
        f.write(f"Testing student UID: {uid}\n")
        
        try:
            db.execute('''
                SELECT c.id, c.name, c.subject, c.description, u.name as teacher_name
                FROM classrooms c
                JOIN enrollments e ON c.id = e.classroom_id
                JOIN users u ON c.teacher_id = u.id
                WHERE e.student_id = ?
            ''', (uid,)).fetchall()
            f.write("Query 1 [CLASSROOMS] passed\n")
        except Exception as e:
            f.write(f"Query 1 [CLASSROOMS] FAILED: {e}\n")

        try:
            db.execute('''
                SELECT q.title as action, qa.xp_earned as xp, qa.completed_at as time
                FROM quiz_attempts qa
                JOIN quizzes q ON qa.quiz_id = q.id
                WHERE qa.student_id = ?
                ORDER BY qa.completed_at DESC
                LIMIT 10
            ''', (uid,)).fetchall()
            f.write("Query 2 [ACTIVITY] passed\n")
        except Exception as e:
            f.write(f"Query 2 [ACTIVITY] FAILED: {e}\n")

        try:
            db.execute('''
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
            f.write("Query 3 [TOPICS] passed\n")
        except Exception as e:
            f.write(f"Query 3 [TOPICS] FAILED: {e}\n")
