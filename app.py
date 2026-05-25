from admin import admin_bp
from flask import Flask, jsonify, render_template, request, session
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


CLEAR_CHAT_COMMANDS = {"clear chat", "clear", "reset chat", "new chat"}
CONFIRM_CLEAR_ACTION = "confirm_clear_chat"
CANCEL_CLEAR_ACTION = "cancel_clear_chat"


def _render_chat(conversation):
    return render_template("index.html", conversation=conversation)


def _confirmation_message():
    return """
    <p>Are you sure you want to clear this conversation?</p>
    <div class="clear-chat-actions">
        <form class="clear-chat-action-form" method="POST" action="/chat">
            <input type="hidden" name="action" value="confirm_clear_chat">
            <button class="danger" type="submit">Yes, Clear Chat</button>
        </form>
        <form class="clear-chat-action-form" method="POST" action="/chat">
            <input type="hidden" name="action" value="cancel_clear_chat">
            <button type="submit">Cancel</button>
        </form>
    </div>
    """


def _is_clear_command(message):
    return " ".join(message.lower().split()) in CLEAR_CHAT_COMMANDS


def _chat_payload(conversation):
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"conversation": conversation})

    return _render_chat(conversation)


@app.route("/", methods=["GET"])
def home():
    return _render_chat(session.get("conversation", []))

@app.route("/chat", methods=["GET", "POST"])
def chat():
    if request.method == "GET":
        return _render_chat(session.get("conversation", []))

    action = request.form.get("action", "").strip()
    user_message = request.form.get("message", "").strip()
    conversation = session.get("conversation", [])

    if action == CONFIRM_CLEAR_ACTION and session.get("pending_clear_chat"):
        conversation = [
            {
                "role": "bot",
                "message": "<p>Chat cleared successfully.<br>How can I help you?</p>",
            }
        ]
        session["conversation"] = conversation
        session.pop("pending_clear_chat", None)
        return _chat_payload(conversation)

    if action == CANCEL_CLEAR_ACTION:
        session.pop("pending_clear_chat", None)
        return _chat_payload(conversation)

    if user_message:
        if _is_clear_command(user_message):
            response = _confirmation_message()
            session["pending_clear_chat"] = True
        else:
            response = get_chatbot_response(user_message)
            session.pop("pending_clear_chat", None)

        conversation.append({"role": "user", "message": user_message})
        conversation.append({"role": "bot", "message": response})

        # Keep the session lightweight while preserving recent chat context.
        session["conversation"] = conversation[-40:]

    return _chat_payload(session.get("conversation", []))

if __name__ == "__main__":
    app.run(debug=False, use_reloader=False)
