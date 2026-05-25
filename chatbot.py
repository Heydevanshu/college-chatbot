import re
from html import escape
from sqlite3 import Error

from database import create_connection, get_exam_schedule, get_faculty, get_syllabus


ROMAN_TO_NUMBER = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
}

NUMBER_TO_ROMAN = {value: key for key, value in ROMAN_TO_NUMBER.items()}


def _safe_text(value):
    """Escape database values before rendering them through safe HTML."""
    return escape(str(value or ""))


def _normalize(value):
    """Normalize short, mixed user input for simple rule-based matching."""
    text = str(value or "").lower()
    for old, new in {
        "-": " ",
        "_": " ",
        ".": " ",
        ",": " ",
        "semester": "sem",
        "sixth": "6th",
        "fifth": "5th",
        "fourth": "4th",
        "third": "3rd",
        "second": "2nd",
        "first": "1st",
    }.items():
        text = text.replace(old, new)

    return " ".join(text.split())


def _fetch_distinct(query, params=()):
    """Return a list of unique text values from a small SQLite query."""
    connection = create_connection()
    if connection is None:
        return []

    try:
        rows = connection.execute(query, params).fetchall()
        values = []
        for row in rows:
            value = row[0]
            if value and str(value).strip() not in values:
                values.append(str(value).strip())
        return values
    except Error as exc:
        print(f"Chatbot database lookup error: {exc}")
        return []
    finally:
        connection.close()


def _fetch_rows(query, params=()):
    """Fetch lightweight row dictionaries for chatbot responses."""
    connection = create_connection()
    if connection is None:
        return []

    try:
        return [dict(row) for row in connection.execute(query, params).fetchall()]
    except Error as exc:
        print(f"Chatbot database fetch error: {exc}")
        return []
    finally:
        connection.close()


def _available_branches():
    return _fetch_distinct(
        """
        SELECT DISTINCT branch FROM faculty
        UNION
        SELECT DISTINCT branch FROM exam_schedule
        ORDER BY branch
        """
    )


def _available_semesters(branch=None):
    params = []
    branch_filter = ""

    if branch:
        branch_filter = "WHERE branch = ?"
        params.append(branch)

    return _fetch_distinct(
        f"""
        SELECT DISTINCT semester FROM faculty {branch_filter}
        UNION
        SELECT DISTINCT semester FROM exam_schedule {branch_filter}
        UNION
        SELECT DISTINCT semester FROM syllabus
        ORDER BY semester
        """,
        tuple(params * 2),
    )


def _available_exam_types(branch=None, semester=None):
    filters = []
    params = []

    if branch:
        filters.append("branch = ?")
        params.append(branch)

    if semester:
        filters.append("semester = ?")
        params.append(semester)

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    return _fetch_distinct(
        f"""
        SELECT DISTINCT exam_type
        FROM exam_schedule
        {where_clause}
        ORDER BY exam_type
        """,
        tuple(params),
    )


def _detect_branch(message):
    """Match any branch currently stored in SQLite; no branch is hardcoded."""
    normalized = f" {_normalize(message)} "

    for branch in _available_branches():
        branch_text = _normalize(branch)
        if f" {branch_text} " in normalized:
            return branch

    return None


def _semester_number(value):
    value = str(value or "").strip().upper()

    if value in ROMAN_TO_NUMBER:
        return ROMAN_TO_NUMBER[value]

    digits = "".join(ch for ch in value if ch.isdigit())
    return int(digits) if digits else None


def _semester_label(value):
    number = _semester_number(value)
    if not number:
        return _safe_text(value)

    suffix = "th"
    if number % 100 not in (11, 12, 13):
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")

    return f"{number}{suffix} Semester"


def _semester_query_text(value):
    number = _semester_number(value)
    return f"{number} sem" if number else str(value or "")


def _detect_semester(message):
    normalized = f" {_normalize(message)} "
    generic_match = re.search(
        r"\b(?:sem\s*)?([1-9][0-9]?)(?:st|nd|rd|th)?(?:\s*sem)?\b",
        normalized,
    )
    generic_number = int(generic_match.group(1)) if generic_match else None

    for semester in _available_semesters():
        number = _semester_number(semester)
        labels = {_normalize(semester)}
        if number:
            labels.update(
                {
                    f"sem {number}",
                    f"{number} sem",
                    f"{number}th sem",
                    f"{number}st sem",
                    f"{number}nd sem",
                    f"{number}rd sem",
                }
            )

        if any(f" {label} " in normalized for label in labels if label):
            return semester

        if generic_number and number == generic_number:
            return semester

    if generic_number:
        return NUMBER_TO_ROMAN.get(generic_number, str(generic_number))

    return None


def _detect_exam_type(message, branch=None, semester=None):
    normalized = f" {_normalize(message)} "

    for exam_type in _available_exam_types(branch, semester):
        exam_text = _normalize(exam_type)
        if f" {exam_text} " in normalized:
            return exam_type

        compact = exam_text.replace("sem", "").replace("  ", " ").strip()
        if compact and f" {compact} " in normalized:
            return exam_type

    return None


def _simple_response(message):
    return f"<p>{message}</p>"


def _missing_response(intro, fields):
    items = "".join(f"<li>{_safe_text(field)}</li>" for field in fields)
    return f"<p>{_safe_text(intro)}</p><ul>{items}</ul>"


def _looks_like_exam_request(message):
    normalized = _normalize(message)
    words = set(normalized.split())
    exam_words = {
        "exam",
        "exams",
        "timetable",
        "schedule",
        "mid",
        "final",
        "paper",
        "test",
    }

    return bool(words & exam_words) or (
        _detect_branch(message) is not None and _detect_semester(message) is not None
    )


def _render_table(title, headers, rows):
    if not rows:
        return ""

    header_html = "".join(f"<th>{_safe_text(header)}</th>" for header in headers)
    row_html = ""

    for row in rows:
        cells = "".join(f"<td>{cell}</td>" for cell in row)
        row_html += f"<tr>{cells}</tr>"

    return f"""
    <h3>{_safe_text(title)}</h3>
    <table>
        <tr>{header_html}</tr>
        {row_html}
    </table>
    """


def _link_cell(link):
    safe_link = _safe_text(link)
    if not safe_link:
        return "N/A"
    return f"<a href='{safe_link}' target='_blank' rel='noopener'>Open</a>"


def get_notices(limit=None):
    query = """
        SELECT title, link, date
        FROM notices
        ORDER BY date DESC, id DESC
    """
    params = ()

    if limit:
        query += " LIMIT ?"
        params = (limit,)

    notices = _fetch_rows(query, params)
    if not notices:
        return "No notices are available right now."

    rows = [
        (
            _safe_text(notice["title"]),
            _safe_text(notice["date"]),
            _link_cell(notice["link"]),
        )
        for notice in notices
    ]

    title = "Latest Notices" if limit else "All Notices"
    return _render_table(title, ["Title", "Date", "Link"], rows)


def get_latest_notices():
    return get_notices(limit=5)


def _handle_notice(message):
    normalized = _normalize(message)

    if "latest" in normalized or "recent" in normalized or "new" in normalized:
        return get_latest_notices()

    if "all" in normalized or "list" in normalized or "show" in normalized:
        return get_notices()

    return _simple_response("Would you like latest notices or all notices?")


def _handle_pdf(message):
    normalized = _normalize(message)

    if "notice" in normalized:
        return get_latest_notices()

    if "syllabus" in normalized:
        return _handle_syllabus(normalized)

    if "document" in normalized or "pdf" in normalized or "upload" in normalized:
        explicit_documents = "document" in normalized or "uploaded" in normalized
        documents = _fetch_rows(
            """
            SELECT filename, pdf_type, pdf_link, uploaded_at
            FROM uploaded_pdfs
            ORDER BY uploaded_at DESC, id DESC
            LIMIT 10
            """
        )

        if explicit_documents:
            if not documents:
                return "No uploaded documents are available right now."

            rows = [
                (
                    _safe_text(item["filename"]),
                    _safe_text(item["pdf_type"]),
                    _link_cell(item["pdf_link"]),
                )
                for item in documents
            ]
            return _render_table("Uploaded Documents", ["File", "Type", "Link"], rows)

        return _simple_response("Please specify which PDF information you need.")

    return _simple_response("Please choose the PDF information you need.")


def _handle_exam(message):
    branch = _detect_branch(message)
    semester = _detect_semester(message)
    exam_type = _detect_exam_type(message, branch, semester)

    branch_options = _available_branches()

    missing = []

    if not branch:
        missing.append("Branch")
        if not branch_options:
            return "No exam schedules are available right now."

    if not semester:
        missing.append("Semester")

    if not exam_type:
        missing.append("Exam Type")

    if missing:
        return _missing_response("Please provide:", missing)

    exams = get_exam_schedule(branch, semester, exam_type)
    if not exams:
        return (
            f"No {escape(exam_type)} exam schedule is available for "
            f"{escape(branch)} {_semester_label(semester)}."
        )

    rows = [
        (
            _safe_text(exam["subject"] if "subject" in exam.keys() else exam[0]),
            _safe_text(exam["exam_date"] if "exam_date" in exam.keys() else exam[1]),
            _safe_text(exam["exam_time"] if "exam_time" in exam.keys() else exam[2]),
        )
        for exam in exams
    ]

    return _render_table(
        f"{branch} {_semester_label(semester)} - {exam_type}",
        ["Subject", "Date", "Time"],
        rows,
    )


def _handle_faculty(message):
    branch = _detect_branch(message)
    branch_options = _available_branches()

    if not branch:
        if not branch_options:
            return "No faculty information is available right now."

        return _simple_response("Please provide branch to view faculty information.")

    faculty = get_faculty(branch)
    if not faculty:
        return f"No faculty information is available for {escape(branch)}."

    rows = [
        (
            _safe_text(teacher["name"] if "name" in teacher.keys() else teacher[0]),
            _safe_text(teacher["phone"] if "phone" in teacher.keys() else teacher[1]),
            _safe_text(teacher["email"] if "email" in teacher.keys() else teacher[2]),
        )
        for teacher in faculty
    ]

    return _render_table(f"{branch} Faculty", ["Name", "Phone", "Email"], rows)


def _handle_syllabus(message):
    branch = _detect_branch(message)
    semester = _detect_semester(message)
    missing = []

    if not branch:
        missing.append("Branch")

    if not semester:
        missing.append("Semester")

    if missing:
        return _missing_response("Please provide:", missing)

    syllabus = get_syllabus()
    if not syllabus:
        return "No syllabus information is available right now."

    syllabus = [
        item
        for item in syllabus
        if (item["semester"] if "semester" in item.keys() else item[0]) == semester
    ]

    if not syllabus:
        return f"No syllabus information is available for {escape(branch)} {_semester_label(semester)}."

    rows = [
        (
            _semester_label(item["semester"] if "semester" in item.keys() else item[0]),
            _safe_text(item["subject"] if "subject" in item.keys() else item[1]),
            _link_cell(item["pdf_link"] if "pdf_link" in item.keys() else item[2]),
        )
        for item in syllabus
    ]

    return _render_table("Syllabus", ["Semester", "Subject", "PDF"], rows)


def get_chatbot_response(user_message):
    """Generate a short, professional response using rule-based understanding."""
    if not user_message or not user_message.strip():
        return "Please enter a message."

    normalized = _normalize(user_message)
    words = set(normalized.split())

    if {"hello", "hi", "hey"} & words:
        return _simple_response("Hello. How can I help you?")

    if "notice" in normalized or "notices" in normalized or "circular" in normalized:
        return _handle_notice(normalized)

    if "faculty" in normalized or "teacher" in normalized or "professor" in normalized:
        return _handle_faculty(normalized)

    if "syllabus" in normalized:
        return _handle_syllabus(normalized)

    if _looks_like_exam_request(normalized):
        return _handle_exam(normalized)

    if "pdf" in normalized or "document" in normalized or "uploaded" in normalized:
        return _handle_pdf(normalized)

    return _simple_response("Please ask a specific college-related question.")
