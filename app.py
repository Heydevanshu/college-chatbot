from flask import Flask, request
from chatbot import get_chatbot_response

app = Flask(__name__)

@app.route("/")
def home():
    return "College Chatbot is Running"

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.form.get("message")

    response = get_chatbot_response(user_message)

    return response

if __name__ == "__main__":
    app.run(debug=True)