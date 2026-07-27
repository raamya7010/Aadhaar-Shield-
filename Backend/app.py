import os
import psycopg
from flask import Flask, render_template, request, redirect, Response
import csv
from geopy.geocoders import Nominatim

app = Flask(__name__, template_folder="../Frontend")

# PostgreSQL Connection (Supabase)

def get_db():
    return psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

# GLOBAL geolocator (FIXED)
geolocator = Nominatim(user_agent="aadhaar_fraud_system")


@app.route('/')
def home():
    return redirect('/login')

@app.route('/login')
def login():
    return render_template("login.html")

@app.route('/index')
def index():
    return render_template("index.html",active_page="home")

@app.route('/submit', methods=['POST'])
def submit():
    db = get_db()
    cursor = db.cursor() 

    name = request.form['name']
    aadhaar = request.form['aadhaar']
    mobile = request.form['mobile']
    ip_address = request.remote_addr

    latitude = request.form.get("latitude") 
    longitude = request.form.get("longitude") 

    latitude = float(latitude) if latitude not in (None, "") else None
    longitude = float(longitude) if longitude not in (None, "") else None

    location_name = "Unknown"

    # GPS → Location convert
    if latitude and longitude:
        try:
            location = geolocator.reverse(f"{latitude}, {longitude}")

            if location:
                address = location.raw.get("address", {})

                city = (
                    address.get("city")
                    or address.get("town")
                    or address.get("village")
                    or ""
                )

                state = address.get("state", "")

                if city and state:
                    location_name = f"{city}, {state}"
                elif state:
                    location_name = state

        except Exception as e:
            location_name = "Unknown"

    # Risk logic
    risk_score = 0

    cursor.execute("SELECT * FROM users WHERE aadhaar = %s", (aadhaar,))
    existing_user = cursor.fetchone()

    if existing_user:
        risk_score += 50

    if aadhaar.startswith("123"):
        risk_score += 30

    if len(mobile) != 10:
        risk_score += 20

    if risk_score == 0:
        status = "Safe"
    else:
        status = "Fraud"

    # Insert DB
    sql = """
    INSERT INTO users
    (name, aadhaar, mobile, risk_score, status, ip_address, latitude, longitude, location)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    # Handle empty GPS values
    latitude = float(latitude) if latitude else None
    longitude = float(longitude) if longitude else None
    
    val = (
        name,
        aadhaar,
        mobile,
        risk_score,
        status,
        ip_address,
        latitude,
        longitude,
        location_name
    )

    cursor.execute(sql, val)
    db.commit()

    cursor.close()
    db.close()

    return render_template(
        "result.html",
        result=[name, aadhaar, mobile, status],
        risk=risk_score,
        active_page="result"
    )


@app.route('/dashboard')
def dashboard():

    db = get_db()
    cursor = db.cursor()


    aadhaar = request.args.get('aadhaar')
    name = request.args.get('name')

    if aadhaar:
        cursor.execute("SELECT * FROM users WHERE aadhaar = %s", (aadhaar,))

    elif name:
        cursor.execute("SELECT * FROM users WHERE name LIKE %s", ("%" + name + "%",))

    else:
        cursor.execute("SELECT id, name, aadhaar, mobile, time, risk_score, status, ip_address, latitude, longitude, location FROM users")

    users = cursor.fetchall()

    total_users = len(users)
    safe_users = 0
    fraud_users = 0
    fraud_rate = 0

    status_index = 6

    for user in users:
        print(user)

        # FIXED INDEX (status column)
        if user[status_index] == "Safe":
            safe_users += 1
        else:
            fraud_users += 1

    if total_users > 0:
        fraud_rate = round((fraud_users / total_users) * 100, 1)

    cursor.close()
    db.close()
 
    return render_template(
        "dashboard.html",
        users=users,
        total_users=total_users,
        safe_users=safe_users,
        fraud_users=fraud_users,
        fraud_rate=fraud_rate,
        active_page="dashboard"
    )


@app.route('/delete/<int:id>')
def delete_user(id):

    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM users WHERE id = %s", (id,))
    db.commit()

    cursor.close()
    db.close()

    return redirect('/dashboard')


@app.route('/analytics')
def analytics():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT status FROM users")
    data = cursor.fetchall()

    safe = 0
    fraud = 0

    for i in data:
        if i[0] == "Safe":
            safe += 1
        else:
            fraud += 1

    cursor.close()
    db.close()
    return render_template("analytics.html", safe=safe, fraud=fraud,  active_page="analytics")


@app.route('/export')
def export():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users")
    data = cursor.fetchall()

    def generate():
        yield "ID,Name,Aadhaar,Mobile,Risk,Status,IP\n"
        for row in data:
            yield f"{row[0]},{row[1]},{row[2]},{row[3]},{row[5]},{row[6]},{row[7]}\n"
    
    cursor.close()
    db.close()
    return Response(generate(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=users.csv"})


@app.route('/alerts')
def alerts():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE risk_score >= 60")
    high_risk = cursor.fetchall()

    cursor.execute("SELECT * FROM users WHERE risk_score >= 30 AND risk_score < 60")
    medium_risk = cursor.fetchall()
    
    cursor.close()
    db.close()

    return render_template(
        "alerts.html",
        high_risk=high_risk,
        medium_risk=medium_risk,
        active_page="alerts"
    )


if __name__ == '__main__':
    app.run(debug=True)