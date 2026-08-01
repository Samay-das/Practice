from flask import Flask, request
from flask.templating import render_template

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/signup" , methods=["GET", "POST"])
def signUp():
    if request.method == "GET":
        return render_template("signUp.html")
    else:
        return "signup", 200

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("logIn.html")
    else:
        return "login", 200
    
if __name__ == "__main__":
    app.run(debug=True)