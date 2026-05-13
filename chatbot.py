
from database import (
    create_connection,
    get_latest_exam,
    get_faculty,
    get_syllabus,
    get_all_exams
)

def get_latest_notices():
    """Fetch latest notice from database."""
    connection = create_connection()
    

    if connection is None:
        return "Database connection failed.0"
    
    cursor = connection.cursor()
    cursor.execute("""
                   SELECT title, link, date
                    FROM notice
                   ORDER BY date DESC
                   LIMIT 5
               """)
    notice = cursor.fetchone()
    connection.close()

    if notice:
        return f"Latest Notice: {notice[0]} ({notice[1]})"
    
    return "No notices available."

def get_chatbot_response(user_message):
    """Generate chatbot response."""

    user_message = user_message.lower()

    # Greeting
    if "hello" in user_message or "hi" in user_message:
        return "Hello! How can I assist you today?"

    # Latest Notice
    elif "exam" in user_message:
        exams = get_all_exams("CSE", "Semester VI")
        if exams:
            response = "CSE Semester VI Exam Schedule:\n"
            for exam in exams:
                response += f"- {exam[0]} on {exam[1]} at {exam[2]}\n"
            return response
        else:
            return "No exam schedule available."

    # Faculty Information
    elif "faculty" in user_message or "teacher" in user_message:
        faculty = get_faculty()

        if faculty:

            response = "Faculty List:\n"
            for teacher in faculty:
                response += f"- {teacher[0]} ({teacher[1]})\n"
            return response
        
        return "No faculty information available."
    
    # Syllabus Information
    elif "syllabus" in user_message:
        syllabus = get_syllabus()

        if syllabus:
            response = "Syllabus links:\n"

            for item in syllabus:
                response += f"- {item[0]}: {item[1]} ({item[2]})\n"
            return response
        
        return "No syllabus information available."
    
    # Default response
    else:
        return "Sorry, I didn't understand that. Please ask about notices, faculty, syllabus, or exams."