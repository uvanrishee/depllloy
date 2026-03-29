-- Initialize Database Schema for Synapse Classroom

-- 1. Users table (Maps to Firebase Auth users)
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, -- Firebase UID
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    role TEXT CHECK(role IN ('teacher', 'student')) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Classrooms table
CREATE TABLE IF NOT EXISTS classrooms (
    id TEXT PRIMARY KEY, -- UUID
    name TEXT NOT NULL,
    subject TEXT NOT NULL,
    description TEXT,
    join_code TEXT UNIQUE NOT NULL,
    teacher_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(teacher_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 3. Enrollments table (Students in Classrooms)
CREATE TABLE IF NOT EXISTS enrollments (
    id TEXT PRIMARY KEY, -- UUID
    student_id TEXT NOT NULL,
    classroom_id TEXT NOT NULL,
    enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(classroom_id) REFERENCES classrooms(id) ON DELETE CASCADE,
    UNIQUE(student_id, classroom_id)
);

-- 4. Materials table (Files/Links uploaded by teacher)
CREATE TABLE IF NOT EXISTS materials (
    id TEXT PRIMARY KEY, -- UUID
    classroom_id TEXT NOT NULL,
    title TEXT NOT NULL,
    file_url TEXT NOT NULL,
    file_type TEXT,
    size_kb REAL,
    is_announcement BOOLEAN DEFAULT 0,
    announcement_text TEXT,
    topic_tags TEXT, -- JSON array string
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(classroom_id) REFERENCES classrooms(id) ON DELETE CASCADE
);

-- 5. Quizzes table
CREATE TABLE IF NOT EXISTS quizzes (
    id TEXT PRIMARY KEY, -- UUID
    classroom_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    difficulty_level TEXT CHECK(difficulty_level IN ('basic', 'intermediate', 'advanced', 'expert')),
    points_multiplier REAL DEFAULT 1.0,
    is_published INTEGER DEFAULT 0,  -- 1 = teacher-published, 0 = AI on-demand
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(classroom_id) REFERENCES classrooms(id) ON DELETE CASCADE
);

-- 6. Quiz Questions table
CREATE TABLE IF NOT EXISTS quiz_questions (
    id TEXT PRIMARY KEY, -- UUID
    quiz_id TEXT NOT NULL,
    question_text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_option TEXT CHECK(correct_option IN ('a', 'b', 'c', 'd')) NOT NULL,
    explanation TEXT,
    topic_tag TEXT,
    FOREIGN KEY(quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
);

-- 7. Quiz Attempts table
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id TEXT PRIMARY KEY, -- UUID
    student_id TEXT NOT NULL,
    quiz_id TEXT NOT NULL,
    score INTEGER NOT NULL,
    total_questions INTEGER NOT NULL,
    xp_earned INTEGER DEFAULT 0,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
);

-- 8. Student Performance table (Teacher Analytics Dashboard)
CREATE TABLE IF NOT EXISTS student_performance (
    student_id TEXT NOT NULL,
    classroom_id TEXT NOT NULL,
    category TEXT CHECK(category IN ('weak', 'average', 'above_average', 'topper')) DEFAULT 'new',
    avg_score REAL DEFAULT 0,
    tests_taken INTEGER DEFAULT 0,
    last_real_test_score REAL,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(student_id, classroom_id),
    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(classroom_id) REFERENCES classrooms(id) ON DELETE CASCADE
);

-- 9. Real Tests table (Offline test records by Teacher)
CREATE TABLE IF NOT EXISTS real_tests (
    id TEXT PRIMARY KEY,
    classroom_id TEXT NOT NULL,
    name TEXT NOT NULL,
    max_marks REAL NOT NULL,
    test_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(classroom_id) REFERENCES classrooms(id) ON DELETE CASCADE
);

-- 10. Real Test Marks
CREATE TABLE IF NOT EXISTS real_test_marks (
    id TEXT PRIMARY KEY,
    real_test_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    marks_obtained REAL NOT NULL,
    FOREIGN KEY(real_test_id) REFERENCES real_tests(id) ON DELETE CASCADE,
    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(real_test_id, student_id)
);

-- 11. Notes table (AI Refined notes)
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    classroom_id TEXT,
    material_id TEXT,
    title TEXT,
    original_text TEXT,
    refined_summary TEXT,
    flashcards_json TEXT, -- JSON array of QA
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 12. Mistakes table
CREATE TABLE IF NOT EXISTS mistakes (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    classroom_id TEXT NOT NULL,
    question_text TEXT NOT NULL,
    student_input TEXT,
    correct_answer TEXT,
    error_category TEXT,
    ai_explanation TEXT,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'resolved')),
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 13. Friends table
CREATE TABLE IF NOT EXISTS friends (
    id TEXT PRIMARY KEY,
    user1_id TEXT NOT NULL,
    user2_id TEXT NOT NULL,
    status TEXT CHECK(status IN ('pending', 'accepted')) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user1_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(user2_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user1_id, user2_id)
);

-- 14. Forum Posts table
CREATE TABLE IF NOT EXISTS forum_posts (
    id TEXT PRIMARY KEY,
    classroom_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    upvotes INTEGER DEFAULT 0,
    parent_post_id TEXT, -- For replies
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(classroom_id) REFERENCES classrooms(id) ON DELETE CASCADE,
    FOREIGN KEY(author_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 15. Battles table (Boss Raid 2-player challenges, private)
CREATE TABLE IF NOT EXISTS battles (
    id TEXT PRIMARY KEY,
    challenger_id TEXT NOT NULL,
    opponent_id TEXT NOT NULL,
    quiz_id TEXT,
    status TEXT CHECK(status IN ('pending', 'active', 'completed')) DEFAULT 'pending',
    winner_id TEXT,
    challenger_score INTEGER DEFAULT 0,
    opponent_score INTEGER DEFAULT 0,
    badge_awarded INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(challenger_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(opponent_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 16. User Game Profile
CREATE TABLE IF NOT EXISTS game_profiles (
    user_id TEXT PRIMARY KEY,
    xp INTEGER DEFAULT 0,
    streak INTEGER DEFAULT 0,
    last_active DATE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
