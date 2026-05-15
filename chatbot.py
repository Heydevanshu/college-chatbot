from database import (
    create_connection,
    get_exam_schedule,
    get_faculty,
    get_syllabus
)


def get_latest_notices():

    """Fetch latest notice from database."""

    connection = create_connection()

    if connection is None:
        return "Database connection failed."

    cursor = connection.cursor()

    cursor.execute("""
        SELECT title, link, date
        FROM notices
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

    # Normalize user input
    user_message = user_message.replace("-", " ")
    user_message = user_message.replace("_", " ")
    user_message = user_message.replace("semester", "sem")
    user_message = user_message.replace("sixth", "6th")
    user_message = user_message.replace("fifth", "5th")
    user_message = user_message.replace("fourth", "4th")
    user_message = user_message.replace("third", "3rd")
    user_message = user_message.replace("second", "2nd")
    user_message = user_message.replace("first", "1st")

    # Greeting
    if "hello" in user_message or "hi" in user_message:

        return "Hello! How can I assist you today?"

    # Exam Information
    elif "exam" in user_message:

        branch = None
        semester = None
        exam_type = None

        # Branch Detection
        if (
            "cse" in user_message or
            "computer science" in user_message
        ):
            branch = "CSE"

        elif (
            "ece" in user_message or
            "electronics" in user_message
        ):
            branch = "ECE"

        elif (
            "mech" in user_message or
            "mechanical" in user_message
        ):
            branch = "MECH"

        elif "civil" in user_message:
            branch = "CIVIL"

        elif (
            "ee" in user_message or
            "electrical" in user_message
        ):
            branch = "EE"

        # Semester Detection
        if (
            "sem 8" in user_message or
            "8th sem" in user_message
        ):
            semester = "VIII"

        elif (
            "sem 7" in user_message or
            "7th sem" in user_message
        ):
            semester = "VII"

        elif (
            "sem 6" in user_message or
            "6th sem" in user_message
        ):
            semester = "VI"

        elif (
            "sem 5" in user_message or
            "5th sem" in user_message
        ):
            semester = "V"

        elif (
            "sem 4" in user_message or
            "4th sem" in user_message
        ):
            semester = "IV"

        elif (
            "sem 3" in user_message or
            "3rd sem" in user_message
        ):
            semester = "III"

        elif (
            "sem 2" in user_message or
            "2nd sem" in user_message
        ):
            semester = "II"

        elif (
            "sem 1" in user_message or
            "1st sem" in user_message
        ):
            semester = "I"

        # Exam Type Detection
        if (
            "mid sem 1" in user_message or
            "mid 1" in user_message
        ):
            exam_type = "Mid Sem 1"

        elif (
            "mid sem 2" in user_message or
            "mid 2" in user_message
        ):
            exam_type = "Mid Sem 2"

        elif (
            "final" in user_message or
            "rgpv" in user_message
        ):
            exam_type = "Final"

        # Validation
        if (
            branch is None or
            semester is None or
            exam_type is None
        ):

            return (
                "Please specify:\n"
                "- Branch\n"
                "- Semester\n"
                "- Exam Type\n\n"
                "Example:\n"
                "CSE 6th Sem Mid Sem 2 Exam"
            )

        exams = get_exam_schedule(
            branch,
            semester,
            exam_type
        )

        if exams:

            response = f"""
            <h3>
                {branch} {semester} - {exam_type} Examination
            </h3>

            <table
                border='1'
                cellpadding='8'
                cellspacing='0'
                style='border-collapse: collapse; width: 100%;'
            >

                <tr>
                    <th>Subject</th>
                    <th>Date</th>
                    <th>Time</th>
                </tr>
            """

            for exam in exams:

                response += f"""
                <tr>
                    <td>{exam[0]}</td>
                    <td>{exam[1]}</td>
                    <td>{exam[2]}</td>
                </tr>
                """

            response += "</table>"

            return response

        return (
            f"No {exam_type} exam schedule available "
            f"for {branch} {semester}."
        )

    # Faculty Information
    elif (
        "faculty" in user_message or
        "teacher" in user_message
    ):

        branch = None

        # Branch Detection
        if (
            "cse" in user_message or
            "computer science" in user_message
        ):
            branch = "CSE"

        elif (
            "ece" in user_message or
            "electronics" in user_message
        ):
            branch = "ECE"

        elif (
            "mech" in user_message or
            "mechanical" in user_message
        ):
            branch = "MECH"

        elif "civil" in user_message:
            branch = "CIVIL"

        elif (
            "ee" in user_message or
            "electrical" in user_message
        ):
            branch = "EE"

        # Validation
        if branch is None:

            return (
                "Please specify branch.\n"
                "Example: CSE faculty"
            )

        faculty = get_faculty(branch)

        if faculty:

            response = f"""
            <h3>{branch} Faculty List</h3>

            <table
                border='1'
                cellpadding='8'
                cellspacing='0'
                style='border-collapse: collapse; width: 100%;'
            >

                <tr>
                    <th>Name</th>
                    <th>Phone</th>
                    <th>Email</th>
                </tr>
            """

            for teacher in faculty:

                response += f"""
                <tr>
                    <td>{teacher[0]}</td>
                    <td>{teacher[1]}</td>
                    <td>{teacher[2]}</td>
                </tr>
                """

            response += "</table>"

            return response

        return f"No faculty information available for {branch}."

    # Syllabus Information
    elif "syllabus" in user_message:

        syllabus = get_syllabus()

        if syllabus:

            response = """
            <h3>Syllabus Links</h3>

            <table
                border='1'
                cellpadding='8'
                cellspacing='0'
                style='border-collapse: collapse; width: 100%;'
            >

                <tr>
                    <th>Semester</th>
                    <th>Subject</th>
                </tr>
            """

            for item in syllabus:

                response += f"""
                <tr>
                    <td>{item[0]}</td>
                    <td>{item[1]}</td>
                </tr>
                """

            response += "</table>"

            return response

        return "No syllabus available."

    # Default Response
    else:

        return (
            "Sorry, I didn't understand that. "
            "Please ask about notices, faculty, syllabus, or exams."
        )