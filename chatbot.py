"""
chatbot.py

This file handles:
1. User input processing
2. database queries
3. Chatbot response
"""

from enum import member

from database import create_connection

def get_latest_notice():
    """fetch latest notice from database."""
    connection = create_connection()
    cursor = connection.cursor()

    cursor.execute("""
            SELECT title, link, date
            FROM notices
            ORDER BY date DESC
            LIMIT 1
        """)
    
    notice = cursor.fetchone()
    connection.close()

    if notice:
        return (
            f"Latest Notice:\n"
            f"Title: {notice[0]}\n"
            f"date: {notice[2]}\n"
            f"Link: {notice[1]}"
        )
    
    return "No notices found."

def get_exam_schedule():
    """fetch exam schedeule"""
    connection = create_connection()
    cursor = connection.cursor()

    cursor.execute("""
            SELECT subject, exam_data, exam_time
            FROM exam_schedule
        """)
    
    exams = cursor.fetchall()
    connection.close()

    if exams:
        response = "Exam Schedule:\n"
        for exam in exams:
            response += (
                f"Subject: {exam[0]}\n"
                f"Date: {exam[1]}\n"
                f"Time: {exam[2]}\n\n"
            )
        return response
    
    return "No exam schedule found."

def get_faculty_information():
    """fetch faculty details."""
    connection = create_connection()
    cursor = connection.cursor()

    cursor.execute("""
            SELECT name, subject, phone, email
            FROM faculty
        """)
    
    faculty_data = cursor.fetchall()
    connection.close()

    if faculty_data:
        response = "Faculty Information:\n"
        for faculty in faculty_data:
            response += (
                f"Name: {faculty[0]}\n"
                f"Subject: {faculty[1]}\n"
                f"Phone: {faculty[2]}\n"
                f"Email: {faculty[3]}\n\n"
            )
        return response
    
    return "No faculty information found."


def get_syllabus():
    """fetch syllabus PDF links."""

    connection = create_connection()
    cursor = connection.cursor()

    cursor.execute("""
            SELECT semester, subject, pdf_link
            FROM syllabus
        """)
    
    syllabus_data = cursor.fetchall()
    connection.close()

    if syllabus_data:
        response = "Syllabus Information:\n"

        for syllabus in syllabus_data:
            response += (
                f"Semester: {syllabus[0]}\n"
                f"Subject: {syllabus[1]}\n"
                f"PDF: {syllabus[2]}\n\n"
            )
        return response
    
    return "No syllabus information found."

def get_chatbot_response(user_message):

    """Generate chatbot response based on user input."""

    message = user_message.lower()

    # latest Notice
    if "notice" in message:
        return get_latest_notice()
    
    # Exam Schedule
    elif "exam" in message:
        return get_exam_schedule()
    
    # Faculty Information
    elif "faculty" in message or "teacher" in message:
        return get_faculty_information()
    
    # Syllabus Information
    elif "syllabus" in message:
        return get_syllabus()
    else:
        return "Sorry, I didn't understand that. Please ask about notices, exam schedule, faculty, or syllabus."