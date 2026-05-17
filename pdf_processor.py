"""
PDF upload processing helpers.

This module intentionally stays lightweight:
- pdfplumber is the only PDF reader.
- No OCR is attempted.
- Parsing uses small regex-based heuristics so the app runs well on low-end
  systems.
"""

import os
import re
from datetime import date, datetime
from sqlite3 import Error

import pdfplumber
from werkzeug.utils import secure_filename

from database import create_connection, create_tables, create_uploaded_pdf


class PDFProcessingError(Exception):
    """Raised when an uploaded PDF cannot be validated or processed."""


DATE_PATTERN = re.compile(
    r"\b("
    r"\d{4}[-/]\d{1,2}[-/]\d{1,2}|"
    r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|"
    r"\d{1,2}\s+"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)"
    r"[a-z]*\s+\d{2,4}"
    r")\b",
    re.IGNORECASE,
)
TIME_PATTERN = re.compile(
    r"\b(?:\d{1,2}:\d{2}\s*(?:am|pm)?|\d{1,2}\s*(?:am|pm))\s*"
    r"(?:-|to)\s*"
    r"(?:\d{1,2}:\d{2}\s*(?:am|pm)?|\d{1,2}\s*(?:am|pm))\b",
    re.IGNORECASE,
)
SUBJECT_CODE_PATTERN = re.compile(r"\b[A-Z]{2,6}\s*-?\s*\d{2,4}\b")

BRANCH_KEYWORDS = {
    "CSE": ("cse", "computer science"),
    "ECE": ("ece", "electronics"),
    "MECH": ("mech", "mechanical"),
    "CIVIL": ("civil",),
    "EE": ("ee", "electrical"),
}
SEMESTER_KEYWORDS = {
    "VIII": ("sem 8", "8th sem", "semester 8", "viii"),
    "VII": ("sem 7", "7th sem", "semester 7", "vii"),
    "VI": ("sem 6", "6th sem", "semester 6", "vi"),
    "V": ("sem 5", "5th sem", "semester 5", "v"),
    "IV": ("sem 4", "4th sem", "semester 4", "iv"),
    "III": ("sem 3", "3rd sem", "semester 3", "iii"),
    "II": ("sem 2", "2nd sem", "semester 2", "ii"),
    "I": ("sem 1", "1st sem", "semester 1", "i"),
}


def extract_pdf_text(pdf_path):
    """Extract text from a PDF file using pdfplumber only."""
    if not pdf_path:
        raise PDFProcessingError("No PDF path was provided.")

    if not os.path.isfile(pdf_path):
        raise PDFProcessingError("Uploaded PDF file was not found.")

    if not pdf_path.lower().endswith(".pdf"):
        raise PDFProcessingError("Only PDF files can be processed.")

    pages = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(text.strip())
    except Exception as exc:
        raise PDFProcessingError(f"Could not read PDF file: {exc}") from exc

    return "\n".join(pages).strip()


def detect_pdf_type(extracted_text):
    """Detect whether extracted PDF text looks like a timetable, notice, or syllabus."""
    lower_text = (extracted_text or "").lower()

    if not lower_text.strip():
        return "unknown"

    if (
        "time table" in lower_text
        or "timetable" in lower_text
        or "examination" in lower_text
        or "day & date" in lower_text
    ):
        return "timetable"

    if (
        "notice" in lower_text
        or "circular" in lower_text
        or "important" in lower_text
    ):
        return "notice"

    if (
        "syllabus" in lower_text
        or "course outcome" in lower_text
        or "unit i" in lower_text
        or "unit 1" in lower_text
    ):
        return "syllabus"

    return "unknown"


def parse_timetable(extracted_text):
    """Parse timetable rows into exam_schedule-compatible dictionaries."""
    lines = _text_lines(extracted_text)
    joined_text = " ".join(lines)
    metadata = {
        "branch": _detect_branch(joined_text),
        "semester": _detect_semester(joined_text),
        "exam_type": _detect_exam_type(joined_text),
    }
    records = []
    warnings = []

    for line in lines:
        clean_line = _normalize_separators(line)
        exam_date = _first_match(DATE_PATTERN, clean_line)
        exam_time = _first_match(TIME_PATTERN, clean_line)

        if not exam_date or not exam_time:
            continue

        subject = _clean_timetable_subject(clean_line, exam_date, exam_time)

        if not subject:
            continue

        records.append(
            {
                "branch": metadata["branch"] or "",
                "semester": metadata["semester"] or "",
                "exam_type": metadata["exam_type"] or "",
                "subject": subject,
                "exam_date": exam_date,
                "exam_time": exam_time,
            }
        )

    for key, label in (
        ("branch", "branch"),
        ("semester", "semester"),
        ("exam_type", "exam type"),
    ):
        if not metadata[key]:
            warnings.append(f"Could not detect timetable {label}.")

    if not records:
        warnings.append("No timetable rows were detected.")

    return {
        "records": records,
        "metadata": metadata,
        "warnings": warnings,
    }


def parse_notice(extracted_text, pdf_link=""):
    """Parse notice text into notices-compatible dictionaries."""
    lines = _text_lines(extracted_text)
    warnings = []
    title = _detect_notice_title(lines)
    notice_date = _detect_notice_date(lines)
    link = _detect_link(lines) or pdf_link

    if not title:
        title = "Uploaded Notice"
        warnings.append("Could not detect notice title; using a default title.")

    if not notice_date:
        notice_date = date.today().isoformat()
        warnings.append("Could not detect notice date; using today's date.")

    return {
        "records": [
            {
                "title": title,
                "link": link,
                "date": notice_date,
            }
        ],
        "metadata": {},
        "warnings": warnings,
    }


def parse_syllabus(extracted_text, pdf_link=""):
    """Parse syllabus text into syllabus-compatible dictionaries."""
    lines = _text_lines(extracted_text)
    semester = _detect_semester(" ".join(lines)) or "Unknown"
    records = []
    warnings = []

    for line in lines:
        subject = _extract_syllabus_subject(line)
        if not subject:
            continue

        records.append(
            {
                "semester": semester,
                "subject": subject,
                "pdf_link": pdf_link,
            }
        )

    if not records:
        records.append(
            {
                "semester": semester,
                "subject": "Syllabus PDF",
                "pdf_link": pdf_link,
            }
        )
        warnings.append("No subject lines were detected; saved the PDF as a syllabus link.")

    return {
        "records": _unique_records(records),
        "metadata": {"semester": semester},
        "warnings": warnings,
    }


def process_uploaded_pdf(file_storage, upload_folder, save_to_database=True):
    """Validate, save, extract, classify, parse, and optionally persist a PDF upload."""
    saved_path, filename = _save_pdf_upload(file_storage, upload_folder)
    pdf_link = _relative_pdf_link(filename)
    extracted_text = extract_pdf_text(saved_path)
    pdf_type = detect_pdf_type(extracted_text)
    parsed_data = _parse_by_type(pdf_type, extracted_text, pdf_link)
    save_summary = {
        "saved_count": 0,
        "skipped_count": 0,
        "errors": [],
    }

    if save_to_database and pdf_type != "unknown":
        save_summary = save_parsed_data(pdf_type, parsed_data)

    if not extracted_text:
        parsed_data["warnings"].append(
            "No readable text was found. OCR is not enabled for this project."
        )

    upload_id = None

    if save_to_database:
        upload_id = create_uploaded_pdf(
            filename,
            saved_path,
            pdf_link,
            pdf_type,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            len(parsed_data.get("records", [])),
        )

    return {
        "upload_id": upload_id,
        "filename": filename,
        "file_path": saved_path,
        "pdf_link": pdf_link,
        "pdf_type": pdf_type,
        "extracted_text": extracted_text,
        "parsed_data": parsed_data,
        "save_summary": save_summary,
    }


def save_parsed_data(pdf_type, parsed_data):
    """Persist parsed PDF records into the existing SQLite tables."""
    create_tables(verbose=False)
    connection = create_connection()

    if connection is None:
        raise PDFProcessingError("Database connection failed.")

    saved_count = 0
    skipped_count = 0
    errors = []
    cursor = connection.cursor()

    try:
        for record in parsed_data.get("records", []):
            if pdf_type == "timetable":
                if not _has_required(record, "branch", "semester", "exam_type", "subject", "exam_date", "exam_time"):
                    skipped_count += 1
                    continue

                cursor.execute(
                    """
                    INSERT INTO exam_schedule
                    (branch, semester, exam_type, subject, exam_date, exam_time)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["branch"],
                        record["semester"],
                        record["exam_type"],
                        record["subject"],
                        record["exam_date"],
                        record["exam_time"],
                    ),
                )
                saved_count += 1

            elif pdf_type == "notice":
                if not _has_required(record, "title", "link", "date"):
                    skipped_count += 1
                    continue

                cursor.execute(
                    """
                    INSERT INTO notices
                    (title, link, date)
                    VALUES (?, ?, ?)
                    """,
                    (record["title"], record["link"], record["date"]),
                )
                saved_count += 1

            elif pdf_type == "syllabus":
                if not _has_required(record, "semester", "subject", "pdf_link"):
                    skipped_count += 1
                    continue

                cursor.execute(
                    """
                    INSERT INTO syllabus
                    (semester, subject, pdf_link)
                    VALUES (?, ?, ?)
                    """,
                    (record["semester"], record["subject"], record["pdf_link"]),
                )
                saved_count += 1

        connection.commit()
    except Error as exc:
        connection.rollback()
        errors.append(str(exc))
    finally:
        connection.close()

    return {
        "saved_count": saved_count,
        "skipped_count": skipped_count,
        "errors": errors,
    }


def _save_pdf_upload(file_storage, upload_folder):
    if not file_storage or not file_storage.filename:
        raise PDFProcessingError("Please select a PDF file.")

    filename = secure_filename(file_storage.filename)

    if not filename:
        raise PDFProcessingError("Uploaded file has an invalid filename.")

    if not filename.lower().endswith(".pdf"):
        raise PDFProcessingError("Only PDF files are allowed.")

    os.makedirs(upload_folder, exist_ok=True)
    saved_path = os.path.join(upload_folder, filename)
    file_storage.save(saved_path)

    return saved_path, filename


def _parse_by_type(pdf_type, extracted_text, pdf_link):
    if pdf_type == "timetable":
        return parse_timetable(extracted_text)

    if pdf_type == "notice":
        return parse_notice(extracted_text, pdf_link)

    if pdf_type == "syllabus":
        return parse_syllabus(extracted_text, pdf_link)

    return {
        "records": [],
        "metadata": {},
        "warnings": ["Could not detect a supported PDF type."],
    }


def _text_lines(text):
    return [
        _normalize_separators(line.strip())
        for line in (text or "").splitlines()
        if line.strip()
    ]


def _normalize_separators(value):
    return (
        value.replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u00a0", " ")
    )


def _first_match(pattern, value):
    match = pattern.search(value or "")
    return match.group(0).strip() if match else ""


def _detect_branch(text):
    lower_text = (text or "").lower()

    for branch, keywords in BRANCH_KEYWORDS.items():
        if any(keyword in lower_text for keyword in keywords):
            return branch

    return ""


def _detect_semester(text):
    lower_text = (text or "").lower()
    lower_text = lower_text.replace("-", " ")

    for semester, keywords in SEMESTER_KEYWORDS.items():
        if any(keyword in lower_text for keyword in keywords):
            return semester

    return ""


def _detect_exam_type(text):
    lower_text = (text or "").lower()

    if "mid sem 1" in lower_text or "mid 1" in lower_text:
        return "Mid Sem 1"

    if "mid sem 2" in lower_text or "mid 2" in lower_text:
        return "Mid Sem 2"

    if "final" in lower_text or "rgpv" in lower_text:
        return "Final"

    return ""


def _clean_timetable_subject(line, exam_date, exam_time):
    subject = line.replace(exam_date, " ").replace(exam_time, " ")
    subject = re.sub(r"\b(mon|tue|wed|thu|fri|sat|sun)(day)?\b", " ", subject, flags=re.IGNORECASE)
    subject = re.sub(r"\b(day|date|time|subject|paper|code)\b", " ", subject, flags=re.IGNORECASE)
    subject = re.sub(r"[:|,]+", " ", subject)
    subject = re.sub(r"\s+", " ", subject).strip(" -")

    return subject


def _detect_notice_title(lines):
    for line in lines:
        lower_line = line.lower().strip()
        if lower_line in {"notice", "circular"}:
            continue

        if len(line) > 3:
            return line[:200]

    return ""


def _detect_notice_date(lines):
    for line in lines:
        notice_date = _first_match(DATE_PATTERN, line)
        if notice_date:
            return notice_date

    return ""


def _detect_link(lines):
    link_pattern = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)

    for line in lines:
        link = _first_match(link_pattern, line)
        if link:
            return link.rstrip(".,)")

    return ""


def _extract_syllabus_subject(line):
    lower_line = line.lower()

    if any(
        keyword in lower_line
        for keyword in (
            "syllabus",
            "course outcome",
            "unit ",
            "reference",
            "text book",
            "objectives",
        )
    ):
        return ""

    if "subject" in lower_line and ":" in line:
        subject = line.split(":", 1)[1].strip()
        return subject[:200] if subject else ""

    if SUBJECT_CODE_PATTERN.search(line):
        subject = re.sub(r"\s+", " ", line).strip(" -")
        return subject[:200]

    return ""


def _relative_pdf_link(filename):
    return f"uploads/pdfs/{filename}"


def _has_required(record, *keys):
    return all(str(record.get(key, "")).strip() for key in keys)


def _unique_records(records):
    unique = []
    seen = set()

    for record in records:
        key = tuple(sorted(record.items()))
        if key in seen:
            continue

        seen.add(key)
        unique.append(record)

    return unique
