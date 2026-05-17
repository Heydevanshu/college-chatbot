from admin import admin_bp
from flask import Flask, request, render_template
from chatbot import get_chatbot_response
from database import create_tables
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.secret_key = "college_chatbot_secret"
app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "uploads", "files")
app.config["PDF_UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "uploads", "pdfs")

# Ensure the SQLite schema exists before any route queries it.
create_tables(verbose=False)

# Register admin blueprint
app.register_blueprint(admin_bp)

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.form.get("message", "")
    response = get_chatbot_response(user_message)

    return render_template("index.html", response=response, user_message=user_message)

if __name__ == "__main__":
    app.run(debug=True)
