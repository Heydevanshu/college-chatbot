"""
database.py

This file handles:
1. Database connection
2. Table Creation
3. Insert operations
4. Fetch operations

"""

import os
import sqlite3 
from sqlite3 import Error

# Database file path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE_PATH = os.path.join(BASE_DIR,"database", "college.db")

def create_connection():
    """Create and return SQLite database connection."""
    connection = None
    try:
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        connection = sqlite3.connect(DATABASE_PATH)
        connection.row_factory = sqlite3.Row
        return connection
    except Error as e:
        print(f"Error connecting to database: {e}")
    return connection

# Test databse connection
if __name__ == "__main__":
    conn = create_connection()
    if conn:
        print("Database connection successful.")
        conn.close()
    else:
        print("Database connection failed.")

def create_tables(verbose=True):
    """Create necessary tables in the database."""
    connection = create_connection()
    if connection is None:
        print("Failed to connect to database.")
        return False
    cursor = connection.cursor()

# Notices table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS notices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    link TEXT NOT NULL,
    date TEXT NOT NULL
        )
    ''')

# Faculty Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS faculty (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   name TEXT NOT NULL,
                   branch TEXT NOT NULL,
                   semester TEXT NOT NULL,
                   subject TEXT NOT NULL,
                   phone TEXT,
                   email TEXT
    )
    ''')

# Exam Schedule
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS exam_schedule (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   subject_code TEXT,
                   branch TEXT NOT NULL,
                   semester TEXT NOT NULL,
                   exam_type TEXT NOT NULL,
                   subject TEXT NOT NULL,
                   exam_date TEXT NOT NULL,
                   exam_time TEXT NOT NULL
                   )
    ''')
    _add_column_if_missing(cursor, "exam_schedule", "subject_code", "TEXT")

# Syllabus Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS syllabus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    semester TEXT NOT NULL,
    subject TEXT NOT NULL,
    pdf_link TEXT NOT NULL
    )
    ''')

# Uploaded PDFs Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS uploaded_pdfs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    pdf_link TEXT NOT NULL,
    pdf_type TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    parsed_records INTEGER DEFAULT 0
    )
    ''')

# Exam Instructions Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS exam_instructions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instruction_text TEXT NOT NULL,
    source_pdf TEXT,
    created_at TEXT NOT NULL
    )
    ''')

    cursor.execute('''
    CREATE UNIQUE INDEX IF NOT EXISTS idx_exam_schedule_unique
    ON exam_schedule (
        COALESCE(subject_code, ''),
        branch,
        semester,
        exam_type,
        subject,
        exam_date,
        exam_time
    )
    ''')

    cursor.execute('''
    CREATE UNIQUE INDEX IF NOT EXISTS idx_notices_unique
    ON notices (title, link, date)
    ''')

    cursor.execute('''
    CREATE UNIQUE INDEX IF NOT EXISTS idx_syllabus_unique
    ON syllabus (semester, subject, pdf_link)
    ''')

    cursor.execute('''
    CREATE UNIQUE INDEX IF NOT EXISTS idx_uploaded_pdfs_unique
    ON uploaded_pdfs (file_path)
    ''')

    cursor.execute('''
    CREATE UNIQUE INDEX IF NOT EXISTS idx_exam_instructions_unique
    ON exam_instructions (instruction_text, source_pdf)
    ''')
    
    connection.commit()
    connection.close()

    if verbose:
        print("Database tables created successfully.")

    return True


def _add_column_if_missing(cursor, table_name, column_name, column_type):
    """Add a simple SQLite column when an existing database is missing it."""
    columns = [
        row["name"]
        for row in cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
    ]

    if column_name not in columns:
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        )


def _fetch_all(query, params=()):
    """Return query results as a list of dictionaries."""
    connection = create_connection()
    if connection is None:
        return []

    try:
        rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    except Error as e:
        print(f"Database fetch error: {e}")
        return []
    finally:
        connection.close()


def _fetch_one(query, params=()):
    """Return one query result as a dictionary, or None."""
    connection = create_connection()
    if connection is None:
        return None

    try:
        row = connection.execute(query, params).fetchone()
        return dict(row) if row else None
    except Error as e:
        print(f"Database fetch error: {e}")
        return None
    finally:
        connection.close()


def _execute_write(query, params=()):
    """Execute INSERT, UPDATE, or DELETE and return the last inserted id."""
    connection = create_connection()
    if connection is None:
        return None

    try:
        cursor = connection.execute(query, params)
        connection.commit()
        return cursor.lastrowid
    except Error as e:
        connection.rollback()
        print(f"Database write error: {e}")
        return None
    finally:
        connection.close()


def count_records(table_name):
    """Count records for known admin tables."""
    allowed_tables = {
        "notices",
        "faculty",
        "exam_schedule",
        "exam_instructions",
        "uploaded_pdfs",
    }

    if table_name not in allowed_tables:
        return 0

    row = _fetch_one(f"SELECT COUNT(*) AS total FROM {table_name}")
    return row["total"] if row else 0


def insert_faculty_if_new(name, branch, semester, subject, phone="", email=""):
    """Insert a faculty row only when the same record is not already present."""
    return _execute_write(
        """
        INSERT INTO faculty (name, branch, semester, subject, phone, email)
        SELECT ?, ?, ?, ?, ?, ?
        WHERE NOT EXISTS (
            SELECT 1 FROM faculty
            WHERE name = ?
            AND branch = ?
            AND semester = ?
            AND subject = ?
            AND COALESCE(phone, '') = ?
            AND COALESCE(email, '') = ?
        )
        """,
        (
            name,
            branch,
            semester,
            subject,
            phone,
            email,
            name,
            branch,
            semester,
            subject,
            phone,
            email,
        ),
    )


def list_notices():
    return _fetch_all("SELECT * FROM notices ORDER BY date DESC, id DESC")


def get_notice(notice_id):
    return _fetch_one("SELECT * FROM notices WHERE id = ?", (notice_id,))


def create_notice(title, link, notice_date):
    return _execute_write(
        """
        INSERT INTO notices (title, link, date)
        VALUES (?, ?, ?)
        """,
        (title, link, notice_date),
    )


def update_notice(notice_id, title, link, notice_date):
    return _execute_write(
        """
        UPDATE notices
        SET title = ?, link = ?, date = ?
        WHERE id = ?
        """,
        (title, link, notice_date, notice_id),
    )


def delete_notice(notice_id):
    return _execute_write("DELETE FROM notices WHERE id = ?", (notice_id,))


def list_faculty_members():
    return _fetch_all(
        """
        SELECT *
        FROM faculty
        ORDER BY branch, semester, name
        """
    )


def get_faculty_member(faculty_id):
    return _fetch_one("SELECT * FROM faculty WHERE id = ?", (faculty_id,))


def create_faculty_member(name, branch, semester, subject, phone, email):
    return _execute_write(
        """
        INSERT INTO faculty (name, branch, semester, subject, phone, email)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (name, branch, semester, subject, phone, email),
    )


def update_faculty_member(faculty_id, name, branch, semester, subject, phone, email):
    return _execute_write(
        """
        UPDATE faculty
        SET name = ?, branch = ?, semester = ?, subject = ?, phone = ?, email = ?
        WHERE id = ?
        """,
        (name, branch, semester, subject, phone, email, faculty_id),
    )


def delete_faculty_member(faculty_id):
    return _execute_write("DELETE FROM faculty WHERE id = ?", (faculty_id,))


def list_exam_schedules():
    return _fetch_all(
        """
        SELECT *
        FROM exam_schedule
        ORDER BY branch, semester, exam_type, exam_date, exam_time
        """
    )


def get_exam_schedule_record(exam_id):
    return _fetch_one("SELECT * FROM exam_schedule WHERE id = ?", (exam_id,))


def create_exam_schedule(branch, semester, exam_type, subject, exam_date, exam_time):
    return _execute_write(
        """
        INSERT INTO exam_schedule
        (branch, semester, exam_type, subject, exam_date, exam_time)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (branch, semester, exam_type, subject, exam_date, exam_time),
    )


def update_exam_schedule(exam_id, branch, semester, exam_type, subject, exam_date, exam_time):
    return _execute_write(
        """
        UPDATE exam_schedule
        SET branch = ?, semester = ?, exam_type = ?, subject = ?, exam_date = ?, exam_time = ?
        WHERE id = ?
        """,
        (branch, semester, exam_type, subject, exam_date, exam_time, exam_id),
    )


def delete_exam_schedule(exam_id):
    return _execute_write("DELETE FROM exam_schedule WHERE id = ?", (exam_id,))


def list_uploaded_pdfs():
    return _fetch_all(
        """
        SELECT *
        FROM uploaded_pdfs
        ORDER BY uploaded_at DESC, id DESC
        """
    )


def get_uploaded_pdf(pdf_id):
    return _fetch_one("SELECT * FROM uploaded_pdfs WHERE id = ?", (pdf_id,))


def create_uploaded_pdf(filename, file_path, pdf_link, pdf_type, uploaded_at, parsed_records):
    existing = _fetch_one(
        "SELECT id FROM uploaded_pdfs WHERE file_path = ?",
        (file_path,),
    )

    if existing:
        return existing["id"]

    return _execute_write(
        """
        INSERT INTO uploaded_pdfs
        (filename, file_path, pdf_link, pdf_type, uploaded_at, parsed_records)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (filename, file_path, pdf_link, pdf_type, uploaded_at, parsed_records),
    )


def update_uploaded_pdf(pdf_id, filename, pdf_type):
    return _execute_write(
        """
        UPDATE uploaded_pdfs
        SET filename = ?, pdf_type = ?
        WHERE id = ?
        """,
        (filename, pdf_type, pdf_id),
    )


def delete_uploaded_pdf(pdf_id):
    return _execute_write("DELETE FROM uploaded_pdfs WHERE id = ?", (pdf_id,))

# Notices fetch
def add_notice(title, link, date):
    """Insert notice into database."""
    connection = create_connection()
    if connection is None:
        print("Failed to connect to database.")
        return
    cursor = connection.cursor()

    cursor.execute("""
                   INSERT INTO notices
                   (title, link, date)
                   VALUES (?, ?, ?)
               """, (title, link, date))
    connection.commit()
    connection.close()
    print("Notice added successfully.")

# Faculty Information
def add_faculty(name, branch, semester, subject, phone, email):
    """Insert faculty information"""

    connection = create_connection()
    if connection is None:
        print("Failed to connect to database.")
        return
    cursor = connection.cursor()

    cursor.execute("""
                   INSERT INTO faculty
                   (name, branch, semester, subject, phone, email)
                   VALUES (?, ?, ?, ?, ?, ?)
               """, (name, branch, semester, subject, phone, email))
    connection.commit()
    connection.close()
    print("Faculty member added successfully.")

# Exam Schedule
def add_exam_schedule(branch, semester, exam_type, subject, exam_date, exam_time):
    """Insert exam schedule"""

    connection = create_connection()
    if connection is None:
        print("Failed to connect to database.")
        return
    cursor = connection.cursor()

    cursor.execute("""
                   INSERT INTO exam_schedule
                     (branch, semester, exam_type, subject, exam_date, exam_time)
                     VALUES (?, ?, ?, ?, ?, ?)
               """, (branch, semester, exam_type, subject, exam_date, exam_time))
    connection.commit()
    connection.close()
    print("Exam schedule added successfully.")

# Syllabus Information
def add_syllabus(semester, subject, pdf_link):
    """Insert syllabus information"""

    connection = create_connection()
    if connection is None:
        print("Failed to connect to database.")
        return
    cursor = connection.cursor()

    cursor.execute("""
                   INSERT INTO syllabus
                   (semester, subject, pdf_link)
                   VALUES (?, ?, ?)
               """, (semester, subject, pdf_link))
    connection.commit()
    connection.close()
    print("Syllabus information added successfully.")

# Fetch exams for a specific branch, semester and exam type
def get_exam_schedule(branch, semester, exam_type):

    connection = create_connection()

    if connection is None:
        return []

    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT subject, exam_date, exam_time
            FROM exam_schedule
            WHERE branch = ?
            AND semester = ?
            AND exam_type = ?
            ORDER BY exam_date
        """, (branch, semester, exam_type))

        exams = cursor.fetchall()
    except Error as e:
        print(f"Error fetching exam schedule: {e}")
        exams = []

    connection.close()

    return exams

# Get latest exam schedule
def get_latest_exam():

    connection = create_connection()

    if connection is None:
        return None
    
    cursor = connection.cursor()

    try:
        cursor.execute("""
                       SELECT subject, exam_date, exam_time
                       FROM exam_schedule
                       ORDER BY exam_date DESC, exam_time DESC
                       LIMIT 1
                   """)
        exam = cursor.fetchone()
    except Error as e:
        print(f"Error fetching latest exam: {e}")
        exam = None
    connection.close()
    return exam

# Get Faculty Information
# Fetch faculty data from database
def get_faculty(branch):

    connection = create_connection()

    if connection is None:
        return []

    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT name, phone, email
            FROM faculty
            WHERE branch = ?
        """, (branch,))

        faculty = cursor.fetchall()
    except Error as e:
        print(f"Error fetching faculty: {e}")
        faculty = []

    connection.close()

    return faculty

# Get Syllabus Information
def get_syllabus():

    connection = create_connection()

    if connection is None:
        return []
    
    cursor = connection.cursor()

    try:
        cursor.execute("""
                       SELECT semester, subject, pdf_link
                       FROM syllabus
                       ORDER BY semester, subject
                   """)
        syllabus = cursor.fetchall()
    except Error as e:
        print(f"Error fetching syllabus: {e}")
        syllabus = []
    connection.close()
    return syllabus

# Fetch all exam schedules for a specific semester and branch
def get_all_exams(branch, semester):

    connection = create_connection()

    if connection is None:
        return []
    
    cursor = connection.cursor()

    try:
        cursor.execute("""
                       SELECT subject, exam_date, exam_time
                       FROM exam_schedule
                       WHERE branch = ? AND semester = ?
                       ORDER BY exam_date ASC, exam_time ASC
                   """, (branch, semester))
        exams = cursor.fetchall()
    except Error as e:
        print(f"Error fetching exams: {e}")
        exams = []
    connection.close()
    return exams

# Run directly
if __name__ == "__main__":
    create_tables()

    # Faculty
    add_faculty("Smita Mishra", "CSE", "VI", "Machine Learning", "", "")
    add_faculty("Ichchha Shrivastava", "CSE", "VI", "Computer Network", "", "")
    add_faculty("Dr. Preeti Verma", "CSE", "VI", "Project Management", "", "")
    add_faculty("Ritu Singh", "CSE", "VI", "Compiler Design", "", "")
    add_faculty("Pratima Singh", "CSE", "VI", "SD Lab", "", "")

    # # Exam Schedule
    # add_exam_schedule("CSE", "VI", "Mid Sem 2", "Machine Learning", "2026-05-20", "11:00 AM - 12:30 PM")
    # add_exam_schedule("CSE", "VI", "Mid Sem 2", "Computer Network", "2026-05-21", "11:00 AM - 12:30 PM")
    # add_exam_schedule("CSE", "VI", "Mid Sem 2", "Project Management", "2026-05-22", "11:00 AM - 12:30 PM")
    # add_exam_schedule("CSE", "VI", "Mid Sem 2", "Compiler Design", "2026-05-23", "11:00 AM - 12:30 PM")
    # add_exam_schedule("CSE", "VI", "Mid Sem 2", "Software Development Lab", "2026-05-23", "1:00 AM - 5:00 PM")
    # add_exam_schedule("CSE", "VI", "Mid Sem 2", "Minor Project", "2026-05-25", "11:00 AM - 12:30 PM")
    
    # # Test fetch
    # data = get_exam_schedule(
    #     "CSE",
    #     "VI",
    #     "Mid Sem 2"
    # )

    # print(data)
