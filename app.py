from flask import Flask, request, redirect
from flask.templating import render_template
from agent import main
import asyncio

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/signup" , methods=["GET", "POST"])
def signUp():
    if request.method == "GET":
        return render_template("signUp.html")
    else:
        return redirect("/login", code=201)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("logIn.html")
    else:
        return redirect("/generate", code=200)

@app.route("/generate", methods=["POST", "GET"])
def generate_budget():
    if request.method == "GET":
        return render_template("profile.html")
    else:
        response = request.form
        from_city = response.get("fromcity")
        to_city = response.get("tocity")
        no_of_people = response.get("people")
        no_of_rooms = response.get("rooms")
        check_in = response.get("checkIn")
        check_out = response.get("checkOut")
        budget_mode = response.get("mode")
        to_currency = response.get("toCurrency")
        answer = asyncio.run(main(from_city=from_city, to_city=to_city,no_of_people=no_of_people,no_of_rooms=no_of_rooms,check_in=check_in,check_out=check_out,budget=budget_mode,currency=to_currency))
        return str(answer), 200
    
if __name__ == "__main__":
    app.run(debug=True)