import mysql.connector
from flask import Flask, render_template, request,redirect

import csv
from flask import Response

app = Flask(__name__, template_folder="../Frontend")

# MySQL connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Sujitha",
    database="aadhaar_fraud"
)

cursor = db.cursor(buffered=True)
@app.route('/')
def home():
    return render_template("index.html")

@app.route('/submit', methods=['POST'])
def submit():
    name = request.form['name']
    aadhaar = request.form['aadhaar']
    mobile = request.form['mobile']
    ip_address = request.remote_addr

    print("Name:", name)
    print("Aadhaar:", aadhaar)
    print("Mobile:", mobile)

    risk_score = 0

    # Duplicate check
    cursor.execute("SELECT * FROM users WHERE aadhaar = %s", (aadhaar,))
    existing_user = cursor.fetchone()

    if existing_user:
        risk_score += 50

    # Rule 1: suspicious pattern
    if aadhaar.startswith("123"):
        risk_score += 30

    # Rule 2: mobile validation
    if len(mobile) != 10:
        risk_score += 20

    # status MUST always be defined
    if risk_score == 0:
        status = "Safe"
    else:
        status = "Fraud"

    # Save only if NOT duplicate
    sql = "INSERT INTO users (name, aadhaar, mobile, risk_score, status, ip_address) VALUES (%s, %s, %s, %s, %s, %s)"
    val = (name, aadhaar, mobile, risk_score, status, ip_address)

    cursor.execute(sql, val)
    db.commit()
    # Final result
    if risk_score == 0:
        result = "Safe (Risk: 0%)"
    elif risk_score >= 80:
        result = f"Fraud Suspected - HIGH RISK ({risk_score}%)"
    else:
        result = f"Fraud Suspected (Risk: {risk_score}%)"

    return render_template(
    "result.html",
    result=[name, aadhaar, mobile, status],
    risk=risk_score
    )
@app.route('/dashboard')
def dashboard():
    aadhaar = request.args.get('aadhaar')
    name = request.args.get('name')

    if aadhaar:
        cursor.execute(
            "SELECT * FROM users WHERE aadhaar = %s",
            (aadhaar,)
    )

    elif name:
        cursor.execute(
            "SELECT * FROM users WHERE name LIKE %s",
            ("%" + name + "%",)
    )

    else:
        cursor.execute("SELECT * FROM users")

    users = cursor.fetchall()

    total_users = len(users)

    safe_users = 0
    fraud_users = 0

    for user in users:
        print(user)

        if user[6] == "Safe":
            safe_users += 1
        else:
            fraud_users += 1

    return render_template(
        "dashboard.html",
        users=users,
        total_users=total_users,
        safe_users=safe_users,
        fraud_users=fraud_users
    )
@app.route('/delete/<int:id>')
def delete_user(id):
    cursor.execute("DELETE FROM users WHERE id = %s", (id,))
    db.commit()

    return redirect('/dashboard')  
@app.route('/analytics')
def analytics():
    cursor.execute("SELECT status FROM users")
    data = cursor.fetchall()

    safe = 0
    fraud = 0

    for i in data:
        if i[0] == "Safe":
            safe += 1
        else:
            fraud += 1

    return render_template("analytics.html", safe=safe, fraud=fraud)  
@app.route('/export')
def export():
    cursor.execute("SELECT * FROM users")
    data = cursor.fetchall()

    def generate():
        yield "ID,Name,Aadhaar,Mobile,Time,Risk,Status,IP\n"
        for row in data:
            yield f"{row[0]},{row[1]},{row[2]},{row[3]},{row[4]},{row[5]},{row[6]},{row[7]}\n"

    return Response(generate(), mimetype="text/csv", headers={"Content-Disposition":"attachment;filename=users.csv"})
@app.route('/alerts')
def alerts():

    cursor.execute("SELECT * FROM users WHERE risk_score >= 60")
    high_risk = cursor.fetchall()

    cursor.execute("SELECT * FROM users WHERE risk_score >= 30 AND risk_score < 60")
    medium_risk = cursor.fetchall()

    return render_template(
        "alerts.html",
        high_risk=high_risk,
        medium_risk=medium_risk
    )

if __name__ == '__main__':
    app.run(debug=True)

    