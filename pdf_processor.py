def detect_pdf_type(extracted_text):

    """
    Detect uploaded PDF type.
    """

    pdf_type = "unknown"

    lower_text = extracted_text.lower()

    # Timetable Detection
    if (
        "time table" in lower_text or
        "examination" in lower_text or
        "day & date" in lower_text
    ):

        pdf_type = "timetable"

    # Notice Detection
    elif (
        "notice" in lower_text or
        "circular" in lower_text or
        "important" in lower_text
    ):

        pdf_type = "notice"

    # Syllabus Detection
    elif (
        "syllabus" in lower_text or
        "unit" in lower_text or
        "course outcome" in lower_text
    ):

        pdf_type = "syllabus"

    return pdf_type