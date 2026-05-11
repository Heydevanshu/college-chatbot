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
    department TEXT NOT NULL,
    subject TEXT NOT NULL,
    phone TEXT,
    email TEXT
    )
    ''')

# Exam Schedule
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS exam_schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
def add_faculty(name, department, subject, phone, email):
    """Insert faculty information"""

    connection = create_connection()
    cursor = connection.cursor()

    cursor.execute("""
                   INSERT INTO faculty
                   (name, department, subject, phone, email)
                   VALUES (?, ?, ?, ?, ?)
               """, (name, department, subject, phone, email))
    connection.commit()
    connection.close()
    print("Faculty member added successfully.")

# Exam Schedule
def add_exam_schedule(subject, exam_date, exam_time):
    """Insert exam schedule"""

    connection = create_connection()
    cursor = connection.cursor()

    cursor.execute("""
                   INSERT INTO exam_schedule
                   (subject, exam_date, exam_time)
                   VALUES (?, ?, ?)
               """, (subject, exam_date, exam_time))
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

# Run directly
if __name__ == "__main__":
    create_tables()

    # Sample data insertion
    add_notice("Midterm Exams Scheduled", "http://college.edu/notices/midterm-exams", "2024-10-01")
    add_faculty("Dr. John Doe", "Computer Science", "Data Structures", "123-456-7890", "john.doe@college.edu")
    add_exam_schedule("Data Structures", "2024-10-15", "10:00 AM")
    add_syllabus("Fall 2024", "Data Structures", "http://college.edu/syllabi/data-structures.pdf")
