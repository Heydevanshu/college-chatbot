from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    session,
    url_for
)
from pdf_processor import detect_pdf_type
import pdfplumber
import os
from werkzeug.utils import secure_filename

# Create Blueprint
admin_bp = Blueprint(
    "admin",
    __name__
)


# Admin Login Route
@admin_bp.route("/admin", methods=["GET", "POST"])
def admin_login():

    """Handle admin login."""

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        # Temporary hardcoded credentials
        if (
            username == "admin" and
            password == "admin123"
        ):

            session["admin_logged_in"] = True

            return redirect(
                url_for("admin.admin_dashboard")
            )

        return render_template(
            "admin_login.html",
            error="Invalid username or password."
        )

    return render_template("admin_login.html")


# Admin Dashboard
@admin_bp.route("/admin/dashboard")
def admin_dashboard():

    """Display admin dashboard."""

    if not session.get("admin_logged_in"):

        return redirect(
            url_for("admin.admin_login")
        )

    return render_template(
        "admin_dashboard.html"
    )


# Logout Route
@admin_bp.route("/admin/logout")
def admin_logout():

    """Logout admin."""

    session.pop("admin_logged_in", None)

    return redirect(
        url_for("admin.admin_login")
    )

# PDF Upload Route
@admin_bp.route(
    "/admin/upload",
    methods=["GET", "POST"]
)
def upload_pdf():

    """Upload PDF files."""

    if not session.get("admin_logged_in"):

        return redirect(
            url_for("admin.admin_login")
        )

    if request.method == "POST":

        pdf_file = request.files.get("pdf_file")

        if pdf_file:

            filename = secure_filename(
                pdf_file.filename
            )

            save_path = os.path.join(
                "uploads/pdfs",
                filename
            )

            pdf_file.save(save_path)

            # Extract PDF Text
            extracted_text = ""

            with pdfplumber.open(save_path) as pdf:

                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        extracted_text += text + "\n"

            # Print extracted text to terminal
            print("\n------- Extracted PDF Text -------\n")
            print(extracted_text)

            # Detect Upload PDF Type
            pdf_type = detect_pdf_type(extracted_text)
            print(f"\n-----------------------------------\n")
            print(f"Detected PDF Type: {pdf_type}")
            print(f"\n----------------------------------\n")

            return render_template(
                "upload_pdf.html",
                success="PDF uploaded and processed successfully.",
                extracted_text=extracted_text,
                pdf_type=pdf_type
            )

    return render_template(
        "upload_pdf.html"
    )