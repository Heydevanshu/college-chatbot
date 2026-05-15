from admin import admin_bp
from flask import Flask, request, render_template
from chatbot import get_chatbot_response

app = Flask(__name__)
app.secret_key = "college_chatbot_secret"

# Register admin blueprint
app.register_blueprint(admin_bp)

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.form.get("message")
    response = get_chatbot_response(user_message)

    return render_template("index.html", response=response, user_message=user_message)

if __name__ == "__main__":
    app.run(debug=True)