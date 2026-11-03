import sqlite3
import numpy as np
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent / "attendance.db"

def get_connection():
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Students table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        roll_no TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        branch TEXT NOT NULL,
        email TEXT,
        photo_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    try:
        cursor.execute("ALTER TABLE students ADD COLUMN email TEXT")
    except Exception:
        pass

    # Self-Registration Pending & OTP verification table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS email_verifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        otp_hash TEXT NOT NULL,
        verified INTEGER DEFAULT 0,
        expires_at TIMESTAMP NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Cryptographically signed onboarding session tokens (single-use anti-replay)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS onboarding_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token_id TEXT UNIQUE NOT NULL,
        email TEXT NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        used INTEGER DEFAULT 0,
        used_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Student Embeddings table (can store multiple embeddings per student)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS student_embeddings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        vector BLOB NOT NULL,
        source_photo TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    );
    """)

    # Courses table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        branch TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Course Enrollments
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS course_enrollments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(course_id, student_id),
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    );
    """)

    # Class Sessions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        session_date TEXT NOT NULL,
        session_time TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    """)
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN session_time TEXT DEFAULT ''")
    except Exception:
        pass

    # Attendance Records
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('Present', 'Absent')),
        confidence REAL DEFAULT 0.0,
        marked_method TEXT NOT NULL,
        marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(session_id, student_id),
        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()

def seed_existing_data():
    """Migrate existing student_embeddings.npz and photos into DB if empty."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM students")
    count = cursor.fetchone()["cnt"]

    if count == 0:
        npz_path = Path(__file__).resolve().parent / "student_embeddings.npz"
        photos_dir = Path(__file__).resolve().parent / "student_photos"
        
        default_students = [
            {"roll_no": "524CS0019", "name": "Aman", "branch": "Computer Science"},
            {"roll_no": "124AD0029", "name": "Dilnawaz", "branch": "AI&DS"},
            {"roll_no": "124AD0019", "name": "Pankaj", "branch": "AI&DS"},
        ]

        # Seed initial courses
        default_courses = [
            ("CS101", "Artificial Intelligence & ML", "Computer Science"),
            ("CS102", "Computer Vision & Robotics", "Computer Science"),
            ("CS103", "Data Structures & Algorithms", "Computer Science"),
        ]
        cursor.executemany("INSERT OR IGNORE INTO courses (code, name, branch) VALUES (?, ?, ?)", default_courses)

        student_id_map = {}
        for st in default_students:
            # find photo
            st_folder = photos_dir / st["name"]
            first_photo = None
            if st_folder.exists():
                for p in st_folder.iterdir():
                    if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                        first_photo = str(p.relative_to(Path(__file__).resolve().parent))
                        break

            cursor.execute(
                "INSERT INTO students (roll_no, name, branch, photo_path) VALUES (?, ?, ?, ?)",
                (st["roll_no"], st["name"], st["branch"], first_photo)
            )
            student_id_map[st["name"]] = cursor.lastrowid

        # Enroll all students in all default courses
        cursor.execute("SELECT id FROM courses")
        course_ids = [row["id"] for row in cursor.fetchall()]
        for c_id in course_ids:
            for s_id in student_id_map.values():
                cursor.execute(
                    "INSERT OR IGNORE INTO course_enrollments (course_id, student_id) VALUES (?, ?)",
                    (c_id, s_id)
                )

        # Load embeddings from npz if present
        if npz_path.exists():
            data = np.load(str(npz_path))
            embeddings = data["embeddings"]
            student_names = data["student_ids"]
            image_paths = data["image_paths"] if "image_paths" in data.files else [""] * len(embeddings)

            for emb, s_name, img_path in zip(embeddings, student_names, image_paths):
                if s_name in student_id_map:
                    emb_bytes = emb.astype(np.float32).tobytes()
                    cursor.execute(
                        "INSERT INTO student_embeddings (student_id, vector, source_photo) VALUES (?, ?, ?)",
                        (student_id_map[s_name], emb_bytes, str(img_path))
                    )

        conn.commit()
    conn.close()

# ----------------- Student Management ----------------- #

def add_student(roll_no: str, name: str, branch: str, photo_path: str, embeddings: list = None, email: str = None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO students (roll_no, name, branch, photo_path, email) VALUES (?, ?, ?, ?, ?)",
        (roll_no.strip().upper(), name.strip(), branch.strip(), photo_path, email.strip() if email else None)
    )
    student_id = cursor.lastrowid

    if embeddings:
        for item in embeddings:
            if isinstance(item, (tuple, list)):
                emb, p_path = item[0], item[1]
            else:
                emb, p_path = item, photo_path
            cursor.execute(
                "INSERT INTO student_embeddings (student_id, vector, source_photo) VALUES (?, ?, ?)",
                (student_id, emb.astype(np.float32).tobytes(), p_path)
            )

    conn.commit()
    conn.close()
    return student_id

def add_embedding_to_student(student_id: int, embedding: np.ndarray, source_photo: str = ""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO student_embeddings (student_id, vector, source_photo) VALUES (?, ?, ?)",
        (student_id, embedding.astype(np.float32).tobytes(), source_photo)
    )
    conn.commit()
    conn.close()

def get_all_students():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.*, COUNT(e.id) as embedding_count 
        FROM students s 
        LEFT JOIN student_embeddings e ON s.id = e.student_id 
        GROUP BY s.id 
        ORDER BY s.roll_no ASC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_student_by_roll(roll_no: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE UPPER(roll_no) = UPPER(?)", (roll_no.strip(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_student_by_email(email: str):
    if not email:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE LOWER(email) = LOWER(?)", (email.strip(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_student_by_id(student_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_student(student_id: int, name: str = None, roll_no: str = None, branch: str = None):
    conn = get_connection()
    cursor = conn.cursor()
    updates = []
    params = []
    if name is not None:
        updates.append("name = ?")
        params.append(name.strip())
    if roll_no is not None:
        updates.append("roll_no = ?")
        params.append(roll_no.strip().upper())
    if branch is not None:
        updates.append("branch = ?")
        params.append(branch.strip())
    if updates:
        params.append(student_id)
        query = f"UPDATE students SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, tuple(params))
        conn.commit()
    conn.close()

# ----------------- Course Management ----------------- #

def create_course(code: str, name: str, branch: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO courses (code, name, branch) VALUES (?, ?, ?)",
        (code.strip().upper(), name.strip(), branch.strip())
    )
    course_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return course_id

def get_all_courses():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, 
                (SELECT COUNT(*) FROM course_enrollments ce WHERE ce.course_id = c.id) as enrolled_count,
                (SELECT COUNT(*) FROM sessions s WHERE s.course_id = c.id) as session_count
        FROM courses c 
        ORDER BY c.code ASC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_course_by_id(course_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_course(course_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    # Clean up attendance for all sessions under this course
    cursor.execute("""
        DELETE FROM attendance 
        WHERE session_id IN (SELECT id FROM sessions WHERE course_id = ?)
    """, (course_id,))
    # Clean up sessions for this course
    cursor.execute("DELETE FROM sessions WHERE course_id = ?", (course_id,))
    # Clean up course enrollments
    cursor.execute("DELETE FROM course_enrollments WHERE course_id = ?", (course_id,))
    # Delete the course record
    cursor.execute("DELETE FROM courses WHERE id = ?", (course_id,))
    conn.commit()
    conn.close()
    return True

def enroll_student_in_course(course_id: int, student_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO course_enrollments (course_id, student_id) VALUES (?, ?)",
        (course_id, student_id)
    )
    # Also initialize attendance for existing sessions of this course
    cursor.execute("SELECT id FROM sessions WHERE course_id = ?", (course_id,))
    sessions = cursor.fetchall()
    for s in sessions:
        cursor.execute(
            """INSERT OR IGNORE INTO attendance (session_id, student_id, status, confidence, marked_method)
               VALUES (?, ?, 'Absent', 0.0, 'Initial')""",
            (s["id"], student_id)
        )
    conn.commit()
    conn.close()

def unenroll_student_from_course(course_id: int, student_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM course_enrollments WHERE course_id = ? AND student_id = ?",
        (course_id, student_id)
    )
    # Also clean up attendance records for this student in this course's sessions
    cursor.execute("""
        DELETE FROM attendance 
        WHERE student_id = ? AND session_id IN (SELECT id FROM sessions WHERE course_id = ?)
    """, (student_id, course_id))
    conn.commit()
    conn.close()

def get_unenrolled_students(course_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM students 
        WHERE id NOT IN (SELECT student_id FROM course_enrollments WHERE course_id = ?)
        ORDER BY roll_no ASC
    """, (course_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_course_attendance_report(course_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    # Fetch course details
    cursor.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
    course = cursor.fetchone()
    if not course:
        conn.close()
        return None
    course = dict(course)

    # Fetch all sessions for this course
    cursor.execute("""
        SELECT id, title, session_date 
        FROM sessions 
        WHERE course_id = ? 
        ORDER BY session_date ASC, id ASC
    """, (course_id,))
    sessions = [dict(r) for r in cursor.fetchall()]

    # Fetch all enrolled students
    cursor.execute("""
        SELECT s.id as student_id, s.roll_no, s.name, s.branch, s.photo_path
        FROM students s
        JOIN course_enrollments ce ON s.id = ce.student_id
        WHERE ce.course_id = ?
        ORDER BY s.roll_no ASC
    """, (course_id,))
    students = [dict(r) for r in cursor.fetchall()]

    # Fetch all attendance entries for these sessions
    session_ids = [s["id"] for s in sessions]
    attendance_map = {}  # (student_id, session_id) -> status
    if session_ids:
        placeholders = ",".join("?" for _ in session_ids)
        cursor.execute(f"""
            SELECT session_id, student_id, status, confidence, marked_method, marked_at
            FROM attendance
            WHERE session_id IN ({placeholders})
        """, session_ids)
        for row in cursor.fetchall():
            attendance_map[(row["student_id"], row["session_id"])] = dict(row)

    conn.close()

    total_sessions_count = len(sessions)
    students_report = []

    for st in students:
        s_id = st["student_id"]
        attended = 0
        session_details = {}

        for sess in sessions:
            sess_id = sess["id"]
            record = attendance_map.get((s_id, sess_id))
            status = record["status"] if record else "Absent"
            if status == "Present":
                attended += 1
            session_details[sess_id] = {
                "status": status,
                "confidence": record["confidence"] if record else 0.0,
                "marked_method": record["marked_method"] if record else "None"
            }

        pct = round((attended / total_sessions_count * 100), 1) if total_sessions_count > 0 else 0.0
        students_report.append({
            "student_id": s_id,
            "roll_no": st["roll_no"],
            "name": st["name"],
            "branch": st["branch"],
            "photo_path": st["photo_path"],
            "attended_sessions": attended,
            "total_sessions": total_sessions_count,
            "percentage": pct,
            "is_eligible": pct >= 75.0,
            "sessions": session_details
        })

    return {
        "course": course,
        "sessions": sessions,
        "students": students_report
    }

def get_course_enrolled_students(course_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.* FROM students s
        JOIN course_enrollments ce ON s.id = ce.student_id
        WHERE ce.course_id = ?
        ORDER BY s.roll_no ASC
    """, (course_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

# ----------------- Session Management ----------------- #

def create_session(course_id: int, title: str, session_date: str = None, session_time: str = None):
    now = datetime.now()
    if not session_date:
        session_date = now.strftime("%Y-%m-%d")
    if not session_time:
        session_time = now.strftime("%H:%M")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sessions (course_id, title, session_date, session_time) VALUES (?, ?, ?, ?)",
        (course_id, title.strip(), session_date, session_time)
    )
    session_id = cursor.lastrowid

    # Automatically initialize all enrolled students as 'Absent' by default
    cursor.execute("SELECT student_id FROM course_enrollments WHERE course_id = ?", (course_id,))
    enrolled = cursor.fetchall()
    for row in enrolled:
        cursor.execute(
            """INSERT OR IGNORE INTO attendance 
               (session_id, student_id, status, confidence, marked_method) 
               VALUES (?, ?, 'Absent', 0.0, 'Initial')""",
            (session_id, row["student_id"])
        )

    conn.commit()
    conn.close()
    return session_id

def get_all_sessions(course_id: int = None):
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT s.*, c.code as course_code, c.name as course_name,
               (SELECT COUNT(*) FROM attendance a WHERE a.session_id = s.id AND a.status = 'Present') as present_count,
               (SELECT COUNT(*) FROM attendance a WHERE a.session_id = s.id) as total_count
        FROM sessions s
        JOIN courses c ON s.course_id = c.id
    """
    params = []
    if course_id:
        query += " WHERE s.course_id = ?"
        params.append(course_id)
    query += " ORDER BY s.session_date DESC, s.id DESC"
    
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_session_by_id(session_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.*, c.code as course_code, c.name as course_name, c.branch as course_branch
        FROM sessions s
        JOIN courses c ON s.course_id = c.id
        WHERE s.id = ?
    """, (session_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# ----------------- Attendance Operations ----------------- #

def mark_student_attendance(session_id: int, student_id: int, status: str, confidence: float = 0.0, method: str = "Manual"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO attendance (session_id, student_id, status, confidence, marked_method, marked_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(session_id, student_id) DO UPDATE SET
            status = excluded.status,
            confidence = excluded.confidence,
            marked_method = excluded.marked_method,
            marked_at = CURRENT_TIMESTAMP
    """, (session_id, student_id, status, float(confidence), method))
    conn.commit()
    conn.close()

def mark_students_attendance_batch(session_id: int, updates: list):
    """Batch-marks attendance for multiple students in a single atomic transaction."""
    if not updates:
        return
    conn = get_connection()
    cursor = conn.cursor()
    params = [
        (session_id, u["student_id"], u.get("status", "Present"), float(u.get("confidence", 0.0)), u.get("method", "Group Photo AI"))
        for u in updates
    ]
    cursor.executemany("""
        INSERT INTO attendance (session_id, student_id, status, confidence, marked_method, marked_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(session_id, student_id) DO UPDATE SET
            status = excluded.status,
            confidence = excluded.confidence,
            marked_method = excluded.marked_method,
            marked_at = CURRENT_TIMESTAMP
    """, params)
    conn.commit()
    conn.close()

def get_session_attendance_list(session_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id as student_id, s.roll_no, s.name, s.branch, s.photo_path,
               COALESCE(a.status, 'Absent') as status,
               COALESCE(a.confidence, 0.0) as confidence,
               COALESCE(a.marked_method, 'None') as marked_method,
               a.marked_at
        FROM students s
        JOIN course_enrollments ce ON s.id = ce.student_id
        JOIN sessions sess ON ce.course_id = sess.course_id
        LEFT JOIN attendance a ON a.session_id = sess.id AND a.student_id = s.id
        WHERE sess.id = ?
        ORDER BY CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END ASC, s.roll_no ASC
    """, (session_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_registered_embeddings_for_session(session_id: int):
    """Retrieve all embeddings for students enrolled in the course associated with this session."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.student_id, s.roll_no, s.name, e.vector
        FROM student_embeddings e
        JOIN students s ON e.student_id = s.id
        JOIN course_enrollments ce ON s.id = ce.student_id
        JOIN sessions sess ON ce.course_id = sess.course_id
        WHERE sess.id = ?
    """, (session_id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return None, None, None

    embeddings = []
    student_ids = []
    metadata = {}
    for r in rows:
        vec = np.frombuffer(r["vector"], dtype=np.float32)
        embeddings.append(vec)
        student_ids.append(r["student_id"])
        metadata[r["student_id"]] = {"roll_no": r["roll_no"], "name": r["name"]}

    return np.asarray(embeddings, dtype=np.float32), np.asarray(student_ids), metadata

def get_student_portal_stats(roll_no: str):
    """Fetch total percentage, course-wise percentage, and detailed attendance log for student."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Fetch student info
    cursor.execute("SELECT * FROM students WHERE UPPER(roll_no) = UPPER(?)", (roll_no.strip(),))
    student = cursor.fetchone()
    if not student:
        conn.close()
        return None

    student = dict(student)

    # 2. Fetch course-wise stats
    cursor.execute("""
        SELECT c.id as course_id, c.code, c.name,
               COUNT(s.id) as total_sessions,
               SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as attended_sessions
        FROM courses c
        JOIN course_enrollments ce ON c.id = ce.course_id AND ce.student_id = ?
        LEFT JOIN sessions s ON c.id = s.course_id
        LEFT JOIN attendance a ON s.id = a.session_id AND a.student_id = ?
        GROUP BY c.id
        ORDER BY c.code ASC
    """, (student["id"], student["id"]))
    
    courses = []
    total_conducted = 0
    total_attended = 0
    for r in cursor.fetchall():
        item = dict(r)
        tot = item["total_sessions"] or 0
        att = item["attended_sessions"] or 0
        pct = round((att / tot * 100), 1) if tot > 0 else 0.0
        item["percentage"] = pct
        courses.append(item)
        total_conducted += tot
        total_attended += att

    overall_pct = round((total_attended / total_conducted * 100), 1) if total_conducted > 0 else 0.0

    # 3. Fetch detailed session records
    cursor.execute("""
        SELECT s.session_date, s.title as session_title, c.code as course_code, c.name as course_name,
               COALESCE(a.status, 'Absent') as status, a.marked_method, a.confidence, a.marked_at
        FROM sessions s
        JOIN courses c ON s.course_id = c.id
        JOIN course_enrollments ce ON c.id = ce.course_id AND ce.student_id = ?
        LEFT JOIN attendance a ON s.id = a.session_id AND a.student_id = ?
        ORDER BY s.session_date DESC, s.id DESC
        LIMIT 50
    """, (student["id"], student["id"]))
    history = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        "student": student,
        "overall_percentage": overall_pct,
        "total_conducted": total_conducted,
        "total_attended": total_attended,
        "courses": courses,
        "history": history
    }

# ----------------- Email Verification & Self-Enrollment ----------------- #

def save_email_otp(email: str, otp_hash: str, expires_at: datetime):
    conn = get_connection()
    cursor = conn.cursor()
    # Invalidate previous unverified OTPs for this email
    cursor.execute("DELETE FROM email_verifications WHERE email = ?", (email.strip().lower(),))
    cursor.execute("""
        INSERT INTO email_verifications (email, otp_hash, verified, expires_at)
        VALUES (?, ?, 0, ?)
    """, (email.strip().lower(), otp_hash, expires_at.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def verify_email_otp(email: str, check_hash_fn) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, otp_hash, expires_at FROM email_verifications
        WHERE email = ? AND verified = 0
        ORDER BY id DESC LIMIT 1
    """, (email.strip().lower(),))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False

    exp = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
    if datetime.now() > exp:
        conn.close()
        return False

    if check_hash_fn(row["otp_hash"]):
        cursor.execute("UPDATE email_verifications SET verified = 1 WHERE id = ?", (row["id"],))
        conn.commit()
        conn.close()
        return True

    conn.close()
    return False

def is_email_verified(email: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, expires_at FROM email_verifications
        WHERE email = ? AND verified = 1
        ORDER BY id DESC LIMIT 1
    """, (email.strip().lower(),))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return False
    exp = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
    # Verified token remains valid for 60 minutes for registration completion
    return (datetime.now() - exp).total_seconds() < 3600

def get_pending_raw_photo_students():
    """Returns students who have photos saved in their folder but 0 embeddings in DB."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id, s.roll_no, s.name, s.branch, s.email, s.photo_path,
               COUNT(e.id) as embedding_count
        FROM students s
        LEFT JOIN student_embeddings e ON s.id = e.student_id
        GROUP BY s.id
        HAVING embedding_count = 0
        ORDER BY s.id DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def store_onboarding_token(token_id: str, email: str, expires_at: datetime):
    """Saves a cryptographically signed onboarding token nonce."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO onboarding_tokens (token_id, email, expires_at, used)
        VALUES (?, ?, ?, 0)
    """, (token_id, email.strip().lower(), expires_at.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def is_onboarding_token_valid(token_id: str) -> bool:
    """Verifies that the token has not been used or expired."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT token_id, expires_at, used FROM onboarding_tokens
        WHERE token_id = ?
    """, (token_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return False
    if row["used"] == 1:
        return False
    exp = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
    return datetime.now() <= exp

def consume_onboarding_token(token_id: str) -> bool:
    """Single-use revocation of onboarding token."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE onboarding_tokens
        SET used = 1, used_at = CURRENT_TIMESTAMP
        WHERE token_id = ? AND used = 0
    """, (token_id,))
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

if __name__ == "__main__":
    init_db()
    seed_existing_data()
    print("Database initialized and seeded successfully.")
