"""
Generic PDF parsing and database insertion helpers.

The parser is intentionally lightweight:
- pdfplumber is the only PDF reader.
- No OCR is used.
- Regex heuristics are generic and avoid university, branch, or subject-code
  specific assumptions.
"""

import os
import csv
import re
import zipfile
from collections import Counter
from datetime import date, datetime
from sqlite3 import Error
from xml.etree import ElementTree

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
SUBJECT_CODE_PATTERN = re.compile(
    r"\b[A-Z]{2,8}\s*[-/]?\s*\d{2,4}[A-Z]?\b"
)
LINK_PATTERN = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
SUPPORTED_EXTENSIONS = {".pdf", ".xlsx", ".csv"}

NOISE_PATTERNS = (
    re.compile(r"^\s*page\s+\d+(\s+of\s+\d+)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d+\s*$"),
    re.compile(r"^\s*[-_=]{3,}\s*$"),
    re.compile(
        r"\b(signature|signed|controller|registrar|principal|director|"
        r"prepared by|checked by|seal|footer)\b",
        re.IGNORECASE,
    ),
)
INSTRUCTION_START_PATTERN = re.compile(
    r"\b(instructions?|important instructions?|notes?|guidelines?)\b",
    re.IGNORECASE,
)


def extract_pdf_text(pdf_path):
    """Extract readable PDF text with pdfplumber only."""
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
    """Detect timetable, notice, syllabus, or unknown from generic keywords."""
    lower_text = (extracted_text or "").lower()

    if not lower_text.strip():
        return "unknown"

    timetable_score = _keyword_score(
        lower_text,
        ("time table", "timetable", "exam schedule", "examination", "exam date", "exam time"),
    )
    notice_score = _keyword_score(
        lower_text,
        ("notice", "circular", "notification", "important", "announcement"),
    )
    syllabus_score = _keyword_score(
        lower_text,
        ("syllabus", "course outcome", "unit", "credits", "reference books"),
    )

    scores = {
        "timetable": timetable_score,
        "notice": notice_score,
        "syllabus": syllabus_score,
    }
    pdf_type, score = max(scores.items(), key=lambda item: item[1])

    return pdf_type if score else "unknown"


def parse_timetable(extracted_text):
    """Parse exam rows and instructions from timetable-like PDF text."""
    lines = _clean_lines(extracted_text)
    table_lines, instruction_lines = _split_instruction_lines(lines)
    metadata = _extract_common_metadata(lines)
    records = []
    warnings = []

    for line in table_lines:
        exam_date = _first_match(DATE_PATTERN, line)
        exam_time = _first_match(TIME_PATTERN, line)

        if not exam_date or not exam_time:
            continue

        subject_code = _first_match(SUBJECT_CODE_PATTERN, line)
        subject_name = _extract_subject_name(line, exam_date, exam_time, subject_code)

        if not subject_code and not subject_name:
            continue

        records.append(
            {
                "subject_code": subject_code,
                "subject": subject_name or subject_code,
                "exam_date": exam_date,
                "exam_time": exam_time,
                "branch": metadata.get("branch", "General"),
                "semester": metadata.get("semester", "General"),
                "exam_type": metadata.get("exam_type", "General"),
            }
        )

    instructions = _unique_text(instruction_lines)

    if not records:
        warnings.append("No timetable rows with both exam date and exam time were detected.")

    if not instructions:
        warnings.append("No instructions section was detected.")

    return {
        "records": _unique_records(records),
        "instructions": instructions,
        "metadata": metadata,
        "warnings": warnings,
    }


def parse_notice(extracted_text, pdf_link=""):
    """Parse notice title, date, and link from notice-like PDF text."""
    lines = _clean_lines(extracted_text)
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
        "instructions": [],
        "metadata": {},
        "warnings": warnings,
    }


def parse_syllabus(extracted_text, pdf_link=""):
    """Parse subject-like syllabus entries without hardcoded subject codes."""
    lines = _clean_lines(extracted_text)
    metadata = _extract_common_metadata(lines)
    semester = metadata.get("semester", "General")
    records = []
    warnings = []

    for line in lines:
        subject_code = _first_match(SUBJECT_CODE_PATTERN, line)
        subject_name = _extract_syllabus_subject(line, subject_code)

        if not subject_code and not subject_name:
            continue

        subject = " - ".join(
            value
            for value in (subject_code, subject_name)
            if value
        )

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
        warnings.append("No subject entries were detected; saved the PDF as a syllabus link.")

    return {
        "records": _unique_records(records),
        "instructions": [],
        "metadata": metadata,
        "warnings": warnings,
    }


def process_uploaded_pdf(file_storage, upload_folder, save_to_database=True):
    """Validate, save, parse, and optionally insert uploaded PDF data."""
    saved_path, filename = _save_pdf_upload(file_storage, upload_folder)
    pdf_link = _relative_pdf_link(filename)
    extracted_text = extract_pdf_text(saved_path)
    pdf_type = detect_pdf_type(extracted_text)
    parsed_data = _parse_by_type(pdf_type, extracted_text, pdf_link)
    upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_summary = _empty_save_summary()

    if not extracted_text:
        parsed_data["warnings"].append(
            "No readable text was found. OCR is not enabled for this project."
        )

    if save_to_database and pdf_type != "unknown":
        save_summary = save_parsed_data(pdf_type, parsed_data, pdf_link)

    upload_id = None

    if save_to_database:
        upload_id = create_uploaded_pdf(
            filename,
            saved_path,
            pdf_link,
            pdf_type,
            upload_time,
            len(parsed_data.get("records", [])),
        )

    return {
        "upload_id": upload_id,
        "filename": filename,
        "file_path": saved_path,
        "pdf_link": pdf_link,
        "pdf_type": pdf_type,
        "uploaded_at": upload_time,
        "extracted_text": extracted_text,
        "parsed_data": parsed_data,
        "save_summary": save_summary,
    }


def process_uploaded_file(file_storage, upload_folder, save_to_database=True, pdf_upload_folder=None):
    """Process PDF, Excel, or CSV uploads through one admin-facing entry point."""
    file_type = detect_uploaded_file_type(file_storage.filename if file_storage else "")
    target_folder = pdf_upload_folder if file_type == "pdf" and pdf_upload_folder else upload_folder
    saved_path, filename = _save_file_upload(file_storage, target_folder)
    file_link = _relative_pdf_link(filename) if file_type == "pdf" else _relative_upload_link(filename)

    if file_type == "pdf":
        # Preserve the existing PDF behavior and return shape.
        result = _process_saved_pdf(saved_path, filename, file_link, save_to_database)
    elif file_type == "excel":
        result = _process_saved_excel(saved_path, filename, file_link, save_to_database)
    elif file_type == "csv":
        result = _process_saved_csv(saved_path, filename, file_link, save_to_database)
    else:
        raise PDFProcessingError("Unsupported file type. Upload PDF, XLSX, or CSV.")

    result["file_type"] = file_type
    result["detected_type"] = result.get("data_type") or result.get("pdf_type", "unknown")

    return result


def process_management_upload(file_storage, upload_folder, target, save_to_database=True, pdf_upload_folder=None):
    """Process uploads from a specific admin management section."""
    allowed_targets = {"faculty", "exam_schedule", "notice"}

    if target not in allowed_targets:
        raise PDFProcessingError("Unsupported management upload target.")

    file_type = detect_uploaded_file_type(file_storage.filename if file_storage else "")
    _validate_management_file_type(target, file_type)

    target_folder = pdf_upload_folder if file_type == "pdf" and pdf_upload_folder else upload_folder
    saved_path, filename = _save_file_upload(file_storage, target_folder)
    file_link = _relative_pdf_link(filename) if file_type == "pdf" else _relative_upload_link(filename)
    upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    extracted_text = ""

    if target == "faculty":
        parsed_data = (
            parse_excel_faculty(saved_path)
            if file_type == "excel"
            else parse_csv_data(saved_path, expected_data_type="faculty")
        )
        data_type = "faculty"
        save_summary = save_tabular_data(data_type, parsed_data) if save_to_database else _empty_save_summary()

    elif target == "exam_schedule":
        if file_type == "pdf":
            extracted_text = extract_pdf_text(saved_path)
            parsed_data = parse_timetable(extracted_text)
            data_type = "timetable"
            save_summary = save_parsed_data("timetable", parsed_data, file_link) if save_to_database else _empty_save_summary()
        else:
            parsed_data = parse_excel_exam_schedule(saved_path)
            data_type = "exam_schedule"
            save_summary = save_tabular_data(data_type, parsed_data) if save_to_database else _empty_save_summary()

    else:
        extracted_text = extract_pdf_text(saved_path)
        parsed_data = parse_notice(extracted_text, file_link)
        data_type = "notice"
        save_summary = save_parsed_data("notice", parsed_data, file_link) if save_to_database else _empty_save_summary()

    detected_type = f"{file_type}_{data_type}" if file_type != "pdf" else data_type
    upload_id = None

    if save_to_database:
        upload_id = create_uploaded_pdf(
            filename,
            saved_path,
            file_link,
            detected_type,
            upload_time,
            len(parsed_data.get("records", [])),
        )

    result = _upload_result(
        upload_id,
        filename,
        saved_path,
        file_link,
        detected_type,
        data_type,
        upload_time,
        extracted_text,
        parsed_data,
        save_summary,
    )
    result["file_type"] = file_type
    result["detected_type"] = data_type

    return result


def detect_uploaded_file_type(filename):
    """Detect upload type from extension without reading the whole file."""
    extension = os.path.splitext(filename or "")[1].lower()

    if extension == ".pdf":
        return "pdf"

    if extension == ".xlsx":
        return "excel"

    if extension == ".csv":
        return "csv"

    return "unknown"


def _validate_management_file_type(target, file_type):
    allowed = {
        "faculty": {"excel", "csv"},
        "exam_schedule": {"pdf", "excel"},
        "notice": {"pdf"},
    }

    if file_type not in allowed[target]:
        messages = {
            "faculty": "Faculty uploads support Excel (.xlsx) and CSV files.",
            "exam_schedule": "Exam uploads support PDF and Excel (.xlsx) files.",
            "notice": "Notice uploads support PDF files.",
        }
        raise PDFProcessingError(messages[target])


def parse_excel_faculty(file_path):
    """Parse faculty records from a simple XLSX sheet."""
    rows = _read_xlsx_rows(file_path)
    records, warnings = _parse_faculty_rows(rows)

    return _tabular_result("faculty", records, warnings)


def parse_excel_exam_schedule(file_path):
    """Parse exam schedule rows from a simple XLSX sheet."""
    rows = _read_xlsx_rows(file_path)
    records, warnings = _parse_exam_rows(rows)

    return _tabular_result("exam_schedule", records, warnings)


def parse_csv_data(file_path, source_link="", expected_data_type=None):
    """Parse CSV data and infer whether it contains faculty, exams, or notices."""
    rows = _read_csv_rows(file_path)
    data_type = expected_data_type or _detect_tabular_data_type(rows)

    return _parse_tabular_rows(rows, data_type, source_link)


def save_parsed_data(pdf_type, parsed_data, source_pdf=""):
    """Persist parsed records into SQLite while skipping duplicates."""
    create_tables(verbose=False)
    connection = create_connection()

    if connection is None:
        raise PDFProcessingError("Database connection failed.")

    summary = _empty_save_summary()

    try:
        cursor = connection.cursor()

        for record in parsed_data.get("records", []):
            inserted = _insert_record(cursor, pdf_type, record)

            if inserted:
                summary["saved_count"] += 1
            else:
                summary["skipped_count"] += 1

        if pdf_type == "timetable":
            for instruction in parsed_data.get("instructions", []):
                inserted = _insert_instruction(cursor, instruction, source_pdf)

                if inserted:
                    summary["instructions_saved"] += 1
                else:
                    summary["instructions_skipped"] += 1

        connection.commit()
    except Error as exc:
        connection.rollback()
        summary["errors"].append(str(exc))
    finally:
        connection.close()

    return summary


def save_tabular_data(data_type, parsed_data):
    """Persist parsed Excel/CSV records into SQLite while skipping duplicates."""
    create_tables(verbose=False)
    connection = create_connection()

    if connection is None:
        raise PDFProcessingError("Database connection failed.")

    summary = _empty_save_summary()

    try:
        cursor = connection.cursor()

        for record in parsed_data.get("records", []):
            inserted = _insert_tabular_record(cursor, data_type, record)

            if inserted:
                summary["saved_count"] += 1
            else:
                summary["skipped_count"] += 1

        connection.commit()
    except Error as exc:
        connection.rollback()
        summary["errors"].append(str(exc))
    finally:
        connection.close()

    return summary


def _process_saved_pdf(saved_path, filename, file_link, save_to_database):
    extracted_text = extract_pdf_text(saved_path)
    pdf_type = detect_pdf_type(extracted_text)
    parsed_data = _parse_by_type(pdf_type, extracted_text, file_link)
    upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_summary = _empty_save_summary()

    if not extracted_text:
        parsed_data["warnings"].append(
            "No readable text was found. OCR is not enabled for this project."
        )

    if save_to_database and pdf_type != "unknown":
        save_summary = save_parsed_data(pdf_type, parsed_data, file_link)

    upload_id = None

    if save_to_database:
        upload_id = create_uploaded_pdf(
            filename,
            saved_path,
            file_link,
            pdf_type,
            upload_time,
            len(parsed_data.get("records", [])),
        )

    return _upload_result(
        upload_id,
        filename,
        saved_path,
        file_link,
        pdf_type,
        pdf_type,
        upload_time,
        extracted_text,
        parsed_data,
        save_summary,
    )


def _process_saved_excel(saved_path, filename, file_link, save_to_database):
    rows = _read_xlsx_rows(saved_path)
    data_type = _detect_tabular_data_type(rows)

    if data_type == "faculty":
        parsed_data = parse_excel_faculty(saved_path)
    elif data_type == "exam_schedule":
        parsed_data = parse_excel_exam_schedule(saved_path)
    elif data_type == "notice":
        parsed_data = _parse_tabular_rows(rows, data_type, file_link)
    else:
        parsed_data = _tabular_result(
            "unknown",
            [],
            ["Could not detect whether this Excel file contains faculty, exams, or notices."],
        )

    return _finish_tabular_upload(
        saved_path,
        filename,
        file_link,
        "excel",
        data_type,
        parsed_data,
        save_to_database,
    )


def _process_saved_csv(saved_path, filename, file_link, save_to_database):
    parsed_data = parse_csv_data(saved_path, file_link)
    data_type = parsed_data.get("data_type", "unknown")

    return _finish_tabular_upload(
        saved_path,
        filename,
        file_link,
        "csv",
        data_type,
        parsed_data,
        save_to_database,
    )


def _finish_tabular_upload(saved_path, filename, file_link, file_type, data_type, parsed_data, save_to_database):
    upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    detected_type = f"{file_type}_{data_type}" if data_type != "unknown" else f"{file_type}_unknown"
    save_summary = _empty_save_summary()

    if save_to_database and data_type != "unknown":
        save_summary = save_tabular_data(data_type, parsed_data)

    upload_id = None

    if save_to_database:
        upload_id = create_uploaded_pdf(
            filename,
            saved_path,
            file_link,
            detected_type,
            upload_time,
            len(parsed_data.get("records", [])),
        )

    return _upload_result(
        upload_id,
        filename,
        saved_path,
        file_link,
        detected_type,
        data_type,
        upload_time,
        "",
        parsed_data,
        save_summary,
    )


def _upload_result(upload_id, filename, file_path, file_link, pdf_type, data_type, upload_time, extracted_text, parsed_data, save_summary):
    return {
        "upload_id": upload_id,
        "filename": filename,
        "file_path": file_path,
        "pdf_link": file_link,
        "pdf_type": pdf_type,
        "data_type": data_type,
        "uploaded_at": upload_time,
        "extracted_text": extracted_text,
        "parsed_data": parsed_data,
        "save_summary": save_summary,
    }


def _insert_record(cursor, pdf_type, record):
    if pdf_type == "timetable":
        if not _has_required(record, "subject", "exam_date", "exam_time"):
            return False

        cursor.execute(
            """
            INSERT INTO exam_schedule
            (subject_code, branch, semester, exam_type, subject, exam_date, exam_time)
            SELECT ?, ?, ?, ?, ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM exam_schedule
                WHERE COALESCE(subject_code, '') = ?
                AND branch = ?
                AND semester = ?
                AND exam_type = ?
                AND subject = ?
                AND exam_date = ?
                AND exam_time = ?
            )
            """,
            (
                record.get("subject_code", ""),
                record.get("branch", "General"),
                record.get("semester", "General"),
                record.get("exam_type", "General"),
                record["subject"],
                record["exam_date"],
                record["exam_time"],
                record.get("subject_code", ""),
                record.get("branch", "General"),
                record.get("semester", "General"),
                record.get("exam_type", "General"),
                record["subject"],
                record["exam_date"],
                record["exam_time"],
            ),
        )
        return cursor.rowcount > 0

    if pdf_type == "notice":
        if not _has_required(record, "title", "link", "date"):
            return False

        cursor.execute(
            """
            INSERT INTO notices (title, link, date)
            SELECT ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM notices
                WHERE title = ? AND link = ? AND date = ?
            )
            """,
            (
                record["title"],
                record["link"],
                record["date"],
                record["title"],
                record["link"],
                record["date"],
            ),
        )
        return cursor.rowcount > 0

    if pdf_type == "syllabus":
        if not _has_required(record, "semester", "subject", "pdf_link"):
            return False

        cursor.execute(
            """
            INSERT INTO syllabus (semester, subject, pdf_link)
            SELECT ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM syllabus
                WHERE semester = ? AND subject = ? AND pdf_link = ?
            )
            """,
            (
                record["semester"],
                record["subject"],
                record["pdf_link"],
                record["semester"],
                record["subject"],
                record["pdf_link"],
            ),
        )
        return cursor.rowcount > 0

    return False


def _insert_tabular_record(cursor, data_type, record):
    if data_type == "faculty":
        if not _has_required(record, "name", "subject"):
            return False

        cursor.execute(
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
                record["name"],
                record.get("branch", "General"),
                record.get("semester", "General"),
                record["subject"],
                record.get("phone", ""),
                record.get("email", ""),
                record["name"],
                record.get("branch", "General"),
                record.get("semester", "General"),
                record["subject"],
                record.get("phone", ""),
                record.get("email", ""),
            ),
        )
        return cursor.rowcount > 0

    if data_type == "exam_schedule":
        return _insert_record(cursor, "timetable", record)

    if data_type == "notice":
        return _insert_record(cursor, "notice", record)

    return False


def _insert_instruction(cursor, instruction_text, source_pdf):
    if not instruction_text:
        return False

    cursor.execute(
        """
        INSERT INTO exam_instructions (instruction_text, source_pdf, created_at)
        SELECT ?, ?, ?
        WHERE NOT EXISTS (
            SELECT 1 FROM exam_instructions
            WHERE instruction_text = ?
            AND COALESCE(source_pdf, '') = ?
        )
        """,
        (
            instruction_text,
            source_pdf,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            instruction_text,
            source_pdf,
        ),
    )
    return cursor.rowcount > 0


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


def _save_file_upload(file_storage, upload_folder):
    if not file_storage or not file_storage.filename:
        raise PDFProcessingError("Please select a file.")

    filename = secure_filename(file_storage.filename)

    if not filename:
        raise PDFProcessingError("Uploaded file has an invalid filename.")

    extension = os.path.splitext(filename)[1].lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise PDFProcessingError("Only PDF, XLSX, and CSV files are allowed.")

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
        "instructions": [],
        "metadata": {},
        "warnings": ["Could not detect a supported PDF type."],
    }


def _read_csv_rows(file_path):
    try:
        with open(file_path, "r", encoding="utf-8-sig", newline="") as csv_file:
            rows = [
                [cell.strip() for cell in row]
                for row in csv.reader(csv_file)
                if any(cell.strip() for cell in row)
            ]
    except UnicodeDecodeError:
        with open(file_path, "r", encoding="latin-1", newline="") as csv_file:
            rows = [
                [cell.strip() for cell in row]
                for row in csv.reader(csv_file)
                if any(cell.strip() for cell in row)
            ]
    except OSError as exc:
        raise PDFProcessingError(f"Could not read CSV file: {exc}") from exc

    if not rows:
        raise PDFProcessingError("CSV file is empty.")

    return rows


def _read_xlsx_rows(file_path):
    try:
        with zipfile.ZipFile(file_path) as workbook:
            shared_strings = _read_xlsx_shared_strings(workbook)
            sheet_name = _first_xlsx_sheet_name(workbook)
            sheet_xml = workbook.read(sheet_name)
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise PDFProcessingError(f"Could not read Excel file: {exc}") from exc

    root = ElementTree.fromstring(sheet_xml)
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows = []

    for row in root.findall(".//x:sheetData/x:row", namespace):
        values = []

        for cell in row.findall("x:c", namespace):
            column_index = _xlsx_column_index(cell.attrib.get("r", ""))

            while len(values) < column_index:
                values.append("")

            values.append(_xlsx_cell_value(cell, shared_strings, namespace).strip())

        if any(values):
            rows.append(values)

    if not rows:
        raise PDFProcessingError("Excel file is empty.")

    return rows


def _read_xlsx_shared_strings(workbook):
    try:
        xml = workbook.read("xl/sharedStrings.xml")
    except KeyError:
        return []

    root = ElementTree.fromstring(xml)
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings = []

    for item in root.findall("x:si", namespace):
        parts = [
            node.text or ""
            for node in item.findall(".//x:t", namespace)
        ]
        strings.append("".join(parts))

    return strings


def _first_xlsx_sheet_name(workbook):
    sheet_names = sorted(
        name
        for name in workbook.namelist()
        if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
    )

    if not sheet_names:
        raise PDFProcessingError("No worksheet was found in the Excel file.")

    return sheet_names[0]


def _xlsx_cell_value(cell, shared_strings, namespace):
    cell_type = cell.attrib.get("t", "")

    if cell_type == "s":
        value_node = cell.find("x:v", namespace)
        if value_node is None or value_node.text is None:
            return ""

        index = int(value_node.text)
        return shared_strings[index] if index < len(shared_strings) else ""

    if cell_type == "inlineStr":
        return "".join(
            node.text or ""
            for node in cell.findall(".//x:t", namespace)
        )

    value_node = cell.find("x:v", namespace)
    return value_node.text if value_node is not None and value_node.text else ""


def _xlsx_column_index(cell_reference):
    letters = re.sub(r"[^A-Z]", "", (cell_reference or "").upper())

    if not letters:
        return 0

    index = 0

    for letter in letters:
        index = index * 26 + (ord(letter) - ord("A") + 1)

    return index - 1


def _parse_tabular_rows(rows, data_type, source_link=""):
    if data_type == "faculty":
        records, warnings = _parse_faculty_rows(rows)
    elif data_type == "exam_schedule":
        records, warnings = _parse_exam_rows(rows)
    elif data_type == "notice":
        records, warnings = _parse_notice_rows(rows, source_link)
    else:
        records = []
        warnings = ["Could not detect whether this file contains faculty, exams, or notices."]

    return _tabular_result(data_type, records, warnings)


def _parse_faculty_rows(rows):
    records = []
    warnings = []
    header, data_rows = _split_header_rows(rows)

    for row in data_rows:
        item = _row_dict(header, row)
        name = _pick(item, "name", "faculty", "faculty_name", "teacher", "teacher_name")
        subject = _pick(item, "subject", "subject_name", "course", "paper")

        if not name or not subject:
            warnings.append("Skipped a faculty row missing name or subject.")
            continue

        records.append(
            {
                "name": name,
                "branch": _pick(item, "branch", "program", "department") or "General",
                "semester": _pick(item, "semester", "sem") or "General",
                "subject": subject,
                "phone": _pick(item, "phone", "mobile", "contact") or "",
                "email": _pick(item, "email", "mail") or "",
            }
        )

    return _unique_records(records), warnings


def _parse_exam_rows(rows):
    records = []
    warnings = []
    header, data_rows = _split_header_rows(rows)

    for row in data_rows:
        item = _row_dict(header, row)
        subject = _pick(item, "subject", "subject_name", "course", "paper")
        exam_date = _pick(item, "exam_date", "date", "day_date")
        exam_time = _pick(item, "exam_time", "time", "timing", "shift")

        if not subject or not exam_date or not exam_time:
            warnings.append("Skipped an exam row missing subject, date, or time.")
            continue

        records.append(
            {
                "subject_code": _pick(item, "subject_code", "code", "paper_code") or "",
                "branch": _pick(item, "branch", "program", "department") or "General",
                "semester": _pick(item, "semester", "sem") or "General",
                "exam_type": _pick(item, "exam_type", "type", "assessment") or "General",
                "subject": subject,
                "exam_date": exam_date,
                "exam_time": exam_time,
            }
        )

    return _unique_records(records), warnings


def _parse_notice_rows(rows, source_link):
    records = []
    warnings = []
    header, data_rows = _split_header_rows(rows)

    for row in data_rows:
        item = _row_dict(header, row)
        title = _pick(item, "title", "notice", "notice_title", "subject", "announcement")

        if not title:
            warnings.append("Skipped a notice row missing title.")
            continue

        records.append(
            {
                "title": title,
                "link": _pick(item, "link", "url", "pdf_link") or source_link,
                "date": _pick(item, "date", "notice_date", "uploaded_at") or date.today().isoformat(),
            }
        )

    return _unique_records(records), warnings


def _detect_tabular_data_type(rows):
    header, _ = _split_header_rows(rows)
    headers = set(header)

    faculty_score = _header_score(headers, ("name", "faculty", "teacher", "subject", "email", "phone"))
    exam_score = _header_score(headers, ("exam_date", "date", "exam_time", "time", "subject", "subject_code"))
    notice_score = _header_score(headers, ("title", "notice", "notice_date", "date", "link", "url"))
    scores = {
        "faculty": faculty_score,
        "exam_schedule": exam_score,
        "notice": notice_score,
    }
    data_type, score = max(scores.items(), key=lambda item: item[1])

    return data_type if score >= 2 else "unknown"


def _split_header_rows(rows):
    header = [_normalize_header(value) for value in rows[0]]
    return header, rows[1:]


def _row_dict(header, row):
    item = {}

    for index, key in enumerate(header):
        if not key:
            continue

        item[key] = row[index].strip() if index < len(row) else ""

    return item


def _normalize_header(value):
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def _pick(item, *keys):
    for key in keys:
        value = item.get(key, "").strip()

        if value:
            return value

    return ""


def _header_score(headers, names):
    return sum(1 for name in names if name in headers)


def _tabular_result(data_type, records, warnings):
    return {
        "data_type": data_type,
        "records": records,
        "instructions": [],
        "metadata": {"data_type": data_type},
        "warnings": warnings,
    }


def _clean_lines(text):
    raw_lines = [
        _normalize_line(line)
        for line in (text or "").splitlines()
    ]
    raw_lines = [line for line in raw_lines if line]
    counts = Counter(line.lower() for line in raw_lines)
    clean = []

    for line in raw_lines:
        lower_line = line.lower()

        if any(pattern.search(line) for pattern in NOISE_PATTERNS):
            continue

        # Repeated lines without row data are usually headers or footers.
        if counts[lower_line] > 1 and not DATE_PATTERN.search(line) and not TIME_PATTERN.search(line):
            continue

        clean.append(line)

    return clean


def _split_instruction_lines(lines):
    table_lines = []
    instruction_lines = []
    in_instruction_section = False

    for line in lines:
        if INSTRUCTION_START_PATTERN.search(line):
            in_instruction_section = True
            instruction = _strip_instruction_heading(line)
            if instruction:
                instruction_lines.append(instruction)
            continue

        if in_instruction_section:
            instruction_lines.append(_strip_bullet(line))
        else:
            table_lines.append(line)

    return table_lines, [line for line in instruction_lines if line]


def _extract_common_metadata(lines):
    metadata = {}

    for line in lines[:20]:
        for key, label in (
            ("branch", "branch|program|course|department"),
            ("semester", "semester|sem"),
            ("exam_type", "exam(?:ination)?\\s*type|exam|assessment"),
        ):
            value = _extract_labeled_value(line, label)

            if value and key not in metadata:
                metadata[key] = value[:80]

    return metadata


def _extract_labeled_value(line, label_pattern):
    match = re.search(
        rf"\b(?:{label_pattern})\b\s*[:\-]\s*([A-Za-z0-9 .,/()_-]+)",
        line,
        re.IGNORECASE,
    )

    if not match:
        return ""

    value = match.group(1).strip(" -")
    value = re.split(r"\s{2,}|\|", value)[0].strip(" -")

    return value


def _extract_subject_name(line, exam_date, exam_time, subject_code):
    subject = line

    for value in (exam_date, exam_time, subject_code):
        if value:
            subject = subject.replace(value, " ")

    subject = re.sub(r"\b(mon|tue|wed|thu|fri|sat|sun)(day)?\b", " ", subject, flags=re.IGNORECASE)
    subject = re.sub(r"\b(date|day|time|subject|paper|code|exam|shift)\b", " ", subject, flags=re.IGNORECASE)
    subject = re.sub(r"[:|,]+", " ", subject)
    subject = re.sub(r"\s+", " ", subject).strip(" -")

    return subject[:160]


def _extract_syllabus_subject(line, subject_code):
    lower_line = line.lower()

    if any(
        keyword in lower_line
        for keyword in (
            "syllabus",
            "course outcome",
            "course objectives",
            "unit ",
            "reference",
            "text book",
            "credits",
        )
    ):
        return ""

    if re.search(r"\b(semester|sem|branch|program|course|department)\b\s*[:\-]", line, re.IGNORECASE):
        return ""

    if "subject" in lower_line and ":" in line:
        subject = line.split(":", 1)[1].strip()
    else:
        subject = line.replace(subject_code, " ") if subject_code else line

    subject = re.sub(r"\s+", " ", subject).strip(" :-")

    if len(subject) < 3:
        return ""

    return subject[:160]


def _detect_notice_title(lines):
    for line in lines:
        lower_line = line.lower().strip()

        if lower_line in {"notice", "circular", "notification"}:
            continue

        if LINK_PATTERN.search(line):
            continue

        title = DATE_PATTERN.sub("", line)
        title = re.sub(r"\s+", " ", title).strip(" -,:")
        title = re.sub(r"\b(on|dated|date)\s*$", "", title, flags=re.IGNORECASE).strip(" -,:")

        if len(title) > 3:
            return title[:200]

    return ""


def _detect_notice_date(lines):
    for line in lines:
        notice_date = _first_match(DATE_PATTERN, line)
        if notice_date:
            return notice_date

    return ""


def _detect_link(lines):
    for line in lines:
        link = _first_match(LINK_PATTERN, line)
        if link:
            return link.rstrip(".,)")

    return ""


def _keyword_score(text, keywords):
    return sum(1 for keyword in keywords if keyword in text)


def _normalize_line(value):
    return re.sub(
        r"\s+",
        " ",
        value.replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u00a0", " ")
        .strip(),
    )


def _strip_instruction_heading(line):
    return INSTRUCTION_START_PATTERN.sub("", line, count=1).strip(" :-")


def _strip_bullet(line):
    return re.sub(r"^\s*(\d+[\).]|[-*•])\s*", "", line).strip()


def _first_match(pattern, value):
    match = pattern.search(value or "")
    return match.group(0).strip() if match else ""


def _relative_pdf_link(filename):
    return f"uploads/pdfs/{filename}"


def _relative_upload_link(filename):
    return f"uploads/files/{filename}"


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


def _unique_text(lines):
    unique = []
    seen = set()

    for line in lines:
        normalized = line.lower()

        if normalized in seen:
            continue

        seen.add(normalized)
        unique.append(line)

    return unique


def _empty_save_summary():
    return {
        "saved_count": 0,
        "skipped_count": 0,
        "instructions_saved": 0,
        "instructions_skipped": 0,
        "errors": [],
    }
