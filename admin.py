import os
from functools import wraps

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from database import (
    count_records,
    create_exam_schedule,
    create_faculty_member,
    create_notice,
    delete_exam_schedule,
    delete_faculty_member,
    delete_notice,
    delete_uploaded_pdf,
    get_exam_schedule_record,
    get_faculty_member,
    get_notice,
    get_uploaded_pdf,
    list_exam_schedules,
    list_faculty_members,
    list_notices,
    list_uploaded_pdfs,
    update_exam_schedule,
    update_faculty_member,
    update_notice,
    update_uploaded_pdf,
)
from pdf_processor import PDFProcessingError, process_uploaded_pdf


admin_bp = Blueprint("admin", __name__)


BRANCH_OPTIONS = ["CSE", "ECE", "MECH", "CIVIL", "EE"]
SEMESTER_OPTIONS = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]
EXAM_TYPE_OPTIONS = ["Mid Sem 1", "Mid Sem 2", "Final"]
PDF_TYPE_OPTIONS = ["unknown", "timetable", "notice", "syllabus"]


def admin_required(view_func):
    """Redirect visitors to the login page when the admin session is missing."""

    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin.admin_login"))

        return view_func(*args, **kwargs)

    return wrapped_view


def _form_value(name):
    return request.form.get(name, "").strip()


def _require_fields(data, required_fields):
    missing = [
        label
        for field, label in required_fields
        if not data.get(field)
    ]

    if missing:
        return "Please fill: " + ", ".join(missing)

    return ""


def _require_choice(data, field, label, options):
    value = data.get(field, "")

    if value and value not in options:
        return f"Please select a valid {label}."

    return ""


def _first_error(*errors):
    return next((error for error in errors if error), "")


@admin_bp.route("/admin", methods=["GET", "POST"])
def admin_login():
    """Handle admin login."""
    if request.method == "POST":
        username = _form_value("username")
        password = _form_value("password")

        # Keep credentials simple for this beginner project.
        if username == "admin" and password == "admin123":
            session["admin_logged_in"] = True
            flash("Logged in successfully.", "success")

            return redirect(url_for("admin.admin_dashboard"))

        return render_template(
            "admin_login.html",
            error="Invalid username or password."
        )

    return render_template("admin_login.html")


@admin_bp.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    """Display admin dashboard with record counts."""
    stats = {
        "notices": count_records("notices"),
        "faculty": count_records("faculty"),
        "exams": count_records("exam_schedule"),
        "pdfs": count_records("uploaded_pdfs"),
    }

    return render_template("admin_dashboard.html", stats=stats)


@admin_bp.route("/admin/logout")
def admin_logout():
    """Logout admin."""
    session.pop("admin_logged_in", None)
    flash("Logged out successfully.", "success")

    return redirect(url_for("admin.admin_login"))


@admin_bp.route("/admin/notices")
@admin_required
def manage_notices():
    return render_template(
        "admin_list.html",
        title="Manage Notices",
        add_url=url_for("admin.notice_add"),
        add_label="Add Notice",
        items=list_notices(),
        columns=[
            {"key": "title", "label": "Title"},
            {"key": "date", "label": "Date"},
            {"key": "link", "label": "Link"},
        ],
        view_endpoint="admin.notice_view",
        edit_endpoint="admin.notice_edit",
        delete_endpoint="admin.notice_delete",
        empty_message="No notices have been added yet.",
    )


@admin_bp.route("/admin/notices/add", methods=["GET", "POST"])
@admin_required
def notice_add():
    fields = _notice_fields()

    if request.method == "POST":
        data = {
            "title": _form_value("title"),
            "link": _form_value("link"),
            "date": _form_value("date"),
        }
        error = _require_fields(
            data,
            [("title", "Title"), ("link", "Link"), ("date", "Date")],
        )

        if error:
            flash(error, "error")
            return render_template("admin_form.html", title="Add Notice", fields=fields, item=data)

        create_notice(data["title"], data["link"], data["date"])
        flash("Notice added successfully.", "success")

        return redirect(url_for("admin.manage_notices"))

    return render_template("admin_form.html", title="Add Notice", fields=fields, item={})


@admin_bp.route("/admin/notices/<int:item_id>")
@admin_required
def notice_view(item_id):
    item = get_notice(item_id)

    if not item:
        flash("Notice not found.", "error")
        return redirect(url_for("admin.manage_notices"))

    return render_template("admin_detail.html", title="Notice Details", item=item, fields=_notice_fields())


@admin_bp.route("/admin/notices/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def notice_edit(item_id):
    item = get_notice(item_id)

    if not item:
        flash("Notice not found.", "error")
        return redirect(url_for("admin.manage_notices"))

    fields = _notice_fields()

    if request.method == "POST":
        data = {
            "title": _form_value("title"),
            "link": _form_value("link"),
            "date": _form_value("date"),
        }
        error = _require_fields(
            data,
            [("title", "Title"), ("link", "Link"), ("date", "Date")],
        )

        if error:
            flash(error, "error")
            return render_template("admin_form.html", title="Edit Notice", fields=fields, item=data)

        update_notice(item_id, data["title"], data["link"], data["date"])
        flash("Notice updated successfully.", "success")

        return redirect(url_for("admin.manage_notices"))

    return render_template("admin_form.html", title="Edit Notice", fields=fields, item=item)


@admin_bp.route("/admin/notices/<int:item_id>/delete", methods=["POST"])
@admin_required
def notice_delete(item_id):
    delete_notice(item_id)
    flash("Notice deleted successfully.", "success")

    return redirect(url_for("admin.manage_notices"))


@admin_bp.route("/admin/faculty")
@admin_required
def manage_faculty():
    return render_template(
        "admin_list.html",
        title="Faculty Management",
        add_url=url_for("admin.faculty_add"),
        add_label="Add Faculty",
        items=list_faculty_members(),
        columns=[
            {"key": "name", "label": "Name"},
            {"key": "branch", "label": "Branch"},
            {"key": "semester", "label": "Sem"},
            {"key": "subject", "label": "Subject"},
            {"key": "email", "label": "Email"},
        ],
        view_endpoint="admin.faculty_view",
        edit_endpoint="admin.faculty_edit",
        delete_endpoint="admin.faculty_delete",
        empty_message="No faculty records have been added yet.",
    )


@admin_bp.route("/admin/faculty/add", methods=["GET", "POST"])
@admin_required
def faculty_add():
    fields = _faculty_fields()

    if request.method == "POST":
        data = _faculty_form_data()
        error = _first_error(
            _require_fields(
                data,
                [
                    ("name", "Name"),
                    ("branch", "Branch"),
                    ("semester", "Semester"),
                    ("subject", "Subject"),
                ],
            ),
            _require_choice(data, "branch", "Branch", BRANCH_OPTIONS),
            _require_choice(data, "semester", "Semester", SEMESTER_OPTIONS),
        )

        if error:
            flash(error, "error")
            return render_template("admin_form.html", title="Add Faculty", fields=fields, item=data)

        create_faculty_member(**data)
        flash("Faculty member added successfully.", "success")

        return redirect(url_for("admin.manage_faculty"))

    return render_template("admin_form.html", title="Add Faculty", fields=fields, item={})


@admin_bp.route("/admin/faculty/<int:item_id>")
@admin_required
def faculty_view(item_id):
    item = get_faculty_member(item_id)

    if not item:
        flash("Faculty record not found.", "error")
        return redirect(url_for("admin.manage_faculty"))

    return render_template("admin_detail.html", title="Faculty Details", item=item, fields=_faculty_fields())


@admin_bp.route("/admin/faculty/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def faculty_edit(item_id):
    item = get_faculty_member(item_id)

    if not item:
        flash("Faculty record not found.", "error")
        return redirect(url_for("admin.manage_faculty"))

    fields = _faculty_fields()

    if request.method == "POST":
        data = _faculty_form_data()
        error = _first_error(
            _require_fields(
                data,
                [
                    ("name", "Name"),
                    ("branch", "Branch"),
                    ("semester", "Semester"),
                    ("subject", "Subject"),
                ],
            ),
            _require_choice(data, "branch", "Branch", BRANCH_OPTIONS),
            _require_choice(data, "semester", "Semester", SEMESTER_OPTIONS),
        )

        if error:
            flash(error, "error")
            return render_template("admin_form.html", title="Edit Faculty", fields=fields, item=data)

        update_faculty_member(item_id, **data)
        flash("Faculty member updated successfully.", "success")

        return redirect(url_for("admin.manage_faculty"))

    return render_template("admin_form.html", title="Edit Faculty", fields=fields, item=item)


@admin_bp.route("/admin/faculty/<int:item_id>/delete", methods=["POST"])
@admin_required
def faculty_delete(item_id):
    delete_faculty_member(item_id)
    flash("Faculty member deleted successfully.", "success")

    return redirect(url_for("admin.manage_faculty"))


@admin_bp.route("/admin/exams")
@admin_required
def manage_exams():
    return render_template(
        "admin_list.html",
        title="Exam Schedule Management",
        add_url=url_for("admin.exam_add"),
        add_label="Add Exam",
        items=list_exam_schedules(),
        columns=[
            {"key": "branch", "label": "Branch"},
            {"key": "semester", "label": "Sem"},
            {"key": "exam_type", "label": "Type"},
            {"key": "subject", "label": "Subject"},
            {"key": "exam_date", "label": "Date"},
            {"key": "exam_time", "label": "Time"},
        ],
        view_endpoint="admin.exam_view",
        edit_endpoint="admin.exam_edit",
        delete_endpoint="admin.exam_delete",
        empty_message="No exam schedules have been added yet.",
    )


@admin_bp.route("/admin/exams/add", methods=["GET", "POST"])
@admin_required
def exam_add():
    fields = _exam_fields()

    if request.method == "POST":
        data = _exam_form_data()
        error = _first_error(
            _require_fields(
                data,
                [
                    ("branch", "Branch"),
                    ("semester", "Semester"),
                    ("exam_type", "Exam Type"),
                    ("subject", "Subject"),
                    ("exam_date", "Date"),
                    ("exam_time", "Time"),
                ],
            ),
            _require_choice(data, "branch", "Branch", BRANCH_OPTIONS),
            _require_choice(data, "semester", "Semester", SEMESTER_OPTIONS),
            _require_choice(data, "exam_type", "Exam Type", EXAM_TYPE_OPTIONS),
        )

        if error:
            flash(error, "error")
            return render_template("admin_form.html", title="Add Exam", fields=fields, item=data)

        create_exam_schedule(**data)
        flash("Exam schedule added successfully.", "success")

        return redirect(url_for("admin.manage_exams"))

    return render_template("admin_form.html", title="Add Exam", fields=fields, item={})


@admin_bp.route("/admin/exams/<int:item_id>")
@admin_required
def exam_view(item_id):
    item = get_exam_schedule_record(item_id)

    if not item:
        flash("Exam schedule not found.", "error")
        return redirect(url_for("admin.manage_exams"))

    return render_template("admin_detail.html", title="Exam Details", item=item, fields=_exam_fields())


@admin_bp.route("/admin/exams/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def exam_edit(item_id):
    item = get_exam_schedule_record(item_id)

    if not item:
        flash("Exam schedule not found.", "error")
        return redirect(url_for("admin.manage_exams"))

    fields = _exam_fields()

    if request.method == "POST":
        data = _exam_form_data()
        error = _first_error(
            _require_fields(
                data,
                [
                    ("branch", "Branch"),
                    ("semester", "Semester"),
                    ("exam_type", "Exam Type"),
                    ("subject", "Subject"),
                    ("exam_date", "Date"),
                    ("exam_time", "Time"),
                ],
            ),
            _require_choice(data, "branch", "Branch", BRANCH_OPTIONS),
            _require_choice(data, "semester", "Semester", SEMESTER_OPTIONS),
            _require_choice(data, "exam_type", "Exam Type", EXAM_TYPE_OPTIONS),
        )

        if error:
            flash(error, "error")
            return render_template("admin_form.html", title="Edit Exam", fields=fields, item=data)

        update_exam_schedule(item_id, **data)
        flash("Exam schedule updated successfully.", "success")

        return redirect(url_for("admin.manage_exams"))

    return render_template("admin_form.html", title="Edit Exam", fields=fields, item=item)


@admin_bp.route("/admin/exams/<int:item_id>/delete", methods=["POST"])
@admin_required
def exam_delete(item_id):
    delete_exam_schedule(item_id)
    flash("Exam schedule deleted successfully.", "success")

    return redirect(url_for("admin.manage_exams"))


@admin_bp.route("/admin/pdfs")
@admin_required
def uploaded_pdfs():
    return render_template(
        "admin_list.html",
        title="Uploaded PDFs",
        add_url=url_for("admin.upload_pdf"),
        add_label="Upload PDF",
        items=list_uploaded_pdfs(),
        columns=[
            {"key": "filename", "label": "File"},
            {"key": "pdf_type", "label": "Type"},
            {"key": "parsed_records", "label": "Records"},
            {"key": "uploaded_at", "label": "Uploaded"},
        ],
        view_endpoint="admin.pdf_view",
        edit_endpoint="admin.pdf_edit",
        delete_endpoint="admin.pdf_delete",
        empty_message="No PDFs have been uploaded yet.",
    )


@admin_bp.route("/admin/pdfs/<int:item_id>")
@admin_required
def pdf_view(item_id):
    item = get_uploaded_pdf(item_id)

    if not item:
        flash("PDF record not found.", "error")
        return redirect(url_for("admin.uploaded_pdfs"))

    return render_template("admin_detail.html", title="PDF Details", item=item, fields=_pdf_fields())


@admin_bp.route("/admin/pdfs/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def pdf_edit(item_id):
    item = get_uploaded_pdf(item_id)

    if not item:
        flash("PDF record not found.", "error")
        return redirect(url_for("admin.uploaded_pdfs"))

    fields = _pdf_edit_fields()

    if request.method == "POST":
        data = {
            "filename": _form_value("filename"),
            "pdf_type": _form_value("pdf_type"),
        }
        error = _first_error(
            _require_fields(data, [("filename", "Filename"), ("pdf_type", "PDF Type")]),
            _require_choice(data, "pdf_type", "PDF Type", PDF_TYPE_OPTIONS),
        )

        if error:
            flash(error, "error")
            return render_template("admin_form.html", title="Edit PDF", fields=fields, item=data)

        update_uploaded_pdf(item_id, data["filename"], data["pdf_type"])
        flash("PDF metadata updated successfully.", "success")

        return redirect(url_for("admin.uploaded_pdfs"))

    return render_template("admin_form.html", title="Edit PDF", fields=fields, item=item)


@admin_bp.route("/admin/pdfs/<int:item_id>/delete", methods=["POST"])
@admin_required
def pdf_delete(item_id):
    item = get_uploaded_pdf(item_id)

    if not item:
        flash("PDF record not found.", "error")
        return redirect(url_for("admin.uploaded_pdfs"))

    file_delete_failed = False

    if item.get("file_path") and os.path.exists(item["file_path"]):
        try:
            os.remove(item["file_path"])
        except OSError as exc:
            current_app.logger.warning("Could not delete PDF file: %s", exc)
            file_delete_failed = True

    delete_uploaded_pdf(item_id)

    if file_delete_failed:
        flash("PDF record deleted, but the file could not be removed.", "error")
    else:
        flash("PDF deleted successfully.", "success")

    return redirect(url_for("admin.uploaded_pdfs"))


@admin_bp.route("/admin/upload", methods=["GET", "POST"])
@admin_required
def upload_pdf():
    """Handle PDF uploads and show processing results."""
    if request.method == "POST":
        try:
            result = process_uploaded_pdf(
                request.files.get("pdf_file"),
                current_app.config["PDF_UPLOAD_FOLDER"]
            )
        except PDFProcessingError as exc:
            current_app.logger.warning("PDF upload failed: %s", exc)
            flash(str(exc), "error")

            return render_template("upload_pdf.html")

        flash("PDF uploaded and processed successfully.", "success")

        return render_template("upload_pdf.html", result=result)

    return render_template("upload_pdf.html")


def _notice_fields():
    return [
        {"name": "title", "label": "Title", "type": "text"},
        {"name": "link", "label": "Link", "type": "url"},
        {"name": "date", "label": "Date", "type": "date"},
    ]


def _faculty_fields():
    return [
        {"name": "name", "label": "Name", "type": "text"},
        {"name": "branch", "label": "Branch", "type": "select", "options": BRANCH_OPTIONS},
        {"name": "semester", "label": "Semester", "type": "select", "options": SEMESTER_OPTIONS},
        {"name": "subject", "label": "Subject", "type": "text"},
        {"name": "phone", "label": "Phone", "type": "text"},
        {"name": "email", "label": "Email", "type": "email"},
    ]


def _exam_fields():
    return [
        {"name": "branch", "label": "Branch", "type": "select", "options": BRANCH_OPTIONS},
        {"name": "semester", "label": "Semester", "type": "select", "options": SEMESTER_OPTIONS},
        {"name": "exam_type", "label": "Exam Type", "type": "select", "options": EXAM_TYPE_OPTIONS},
        {"name": "subject", "label": "Subject", "type": "text"},
        {"name": "exam_date", "label": "Date", "type": "date"},
        {"name": "exam_time", "label": "Time", "type": "text"},
    ]


def _pdf_fields():
    return [
        {"name": "filename", "label": "Filename"},
        {"name": "pdf_type", "label": "PDF Type"},
        {"name": "pdf_link", "label": "Link"},
        {"name": "file_path", "label": "Saved Path"},
        {"name": "uploaded_at", "label": "Uploaded At"},
        {"name": "parsed_records", "label": "Parsed Records"},
    ]


def _pdf_edit_fields():
    return [
        {"name": "filename", "label": "Filename", "type": "text"},
        {"name": "pdf_type", "label": "PDF Type", "type": "select", "options": PDF_TYPE_OPTIONS},
    ]


def _faculty_form_data():
    return {
        "name": _form_value("name"),
        "branch": _form_value("branch"),
        "semester": _form_value("semester"),
        "subject": _form_value("subject"),
        "phone": _form_value("phone"),
        "email": _form_value("email"),
    }


def _exam_form_data():
    return {
        "branch": _form_value("branch"),
        "semester": _form_value("semester"),
        "exam_type": _form_value("exam_type"),
        "subject": _form_value("subject"),
        "exam_date": _form_value("exam_date"),
        "exam_time": _form_value("exam_time"),
    }
