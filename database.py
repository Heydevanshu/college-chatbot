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
        connection = sqlite3.connect(DATABASE_PATH)
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

def create_tables():
    """Create necessary tables in the database."""
    connection = create_connection()
    if connection is None:
        print("Failed to connect to database.")
        return
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
                   branch TEXT NOT NULL,
                   semester TEXT NOT NULL,
                   exam_type TEXT NOT NULL,
                   subject TEXT NOT NULL,
                   exam_date TEXT NOT NULL,
                   exam_time TEXT NOT NULL
                   )
    ''')

# Syllabus Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS syllabus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    semester TEXT NOT NULL,
    subject TEXT NOT NULL,
    pdf_link TEXT NOT NULL
    )
    ''')
    
    connection.commit()
    connection.close()

    print("Database tables created successfully.")

# Notices fetch
def add_notice(title, link, date):
    """Insert notice into database."""
    connection = create_connection()
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

    cursor.execute("""
        SELECT subject, exam_date, exam_time
        FROM exam_schedule
        WHERE branch = ?
        AND semester = ?
        AND exam_type = ?
        ORDER BY exam_date
    """, (branch, semester, exam_type))

    exams = cursor.fetchall()

    connection.close()

    return exams

# Get latest exam schedule
def get_latest_exam():

    connection = create_connection()

    if connection is None:
        return None
    
    cursor = connection.cursor()

    cursor.execute("""
                   SELECT subject, exam_date, exam_time
                   FROM exam_schedule
                   ORDER BY exam_date DESC, exam_time DESC
                   LIMIT 1
               """)
    exam = cursor.fetchone()
    connection.close()
    return exam

# Get Faculty Information
# Fetch faculty data from database
def get_faculty(branch):

    connection = create_connection()

    if connection is None:
        return []

    cursor = connection.cursor()

    cursor.execute("""
        SELECT name, phone, email
        FROM faculty
        WHERE branch = ?
    """, (branch,))

    faculty = cursor.fetchall()

    connection.close()

    return faculty

# Get Syllabus Information
def get_syllabus():

    connection = create_connection()

    if connection is None:
        return None
    
    cursor = connection.cursor()

    cursor.execute("""
                   SELECT semester, pdf_link
                   FROM syllabus
               """)
    syllabus = cursor.fetchone()
    connection.close()
    return syllabus

# Fetch all exam schedules for a specific semester and branch
def get_all_exams(branch, semester):

    connection = create_connection()

    if connection is None:
        return []
    
    cursor = connection.cursor()

    cursor.execute("""
                   SELECT subject, exam_date, exam_time
                   FROM exam_schedule
                   WHERE branch = ? AND semester = ?
                   ORDER BY exam_date ASC, exam_time ASC
               """, (branch, semester))
    exams = cursor.fetchall()
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