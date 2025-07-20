from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask import send_file
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import csv
import os
import pickle

# --- Setup ---
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Ensure instance folder exists
instance_path = os.path.join(os.path.dirname(__file__), 'instance')
os.makedirs(instance_path, exist_ok=True)

# SQLite DB config
db_path = os.path.join(instance_path, 'users.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

class Journal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    text = db.Column(db.Text, nullable=False)
    mood = db.Column(db.String(20), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

# --- Load ML model ---
model_path = os.path.join(os.path.dirname(__file__), 'model.pkl')
with open(model_path, 'rb') as f:
    model = pickle.load(f)

# --- Routes ---
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        existing = User.query.filter_by(email=email).first()
        if existing:
            return "User already exists. Please login."
        user = User(email=email, password=password)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        else:
            return "Invalid credentials. Please try again."
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/predict', methods=['POST'])
def predict():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    data = request.get_json()
    text = data.get('text')
    if not text:
        return jsonify({'error': 'No input provided'}), 400

    prediction = model.predict([text])[0]

    # Save journal entry
    entry = Journal(user_id=session['user_id'], text=text, mood=prediction)
    db.session.add(entry)
    db.session.commit()

    suggestions = {
        "happy": "Keep smiling! Here's a motivational quote: 'Happiness is a journey, not a destination.'",
        "sad": "It's okay to feel sad. Try some deep breathing or write about it.",
        "angry": "Take a short walk or listen to calming music to cool down.",
        "anxious": "Try a short mindfulness activity or a breathing exercise.",
    }

    return jsonify({
        'mood': prediction,
        'suggestion': suggestions.get(prediction, "Stay strong! You're doing great.")
    })

@app.route('/history')
def history():
    if 'user_id' not in session:
        return jsonify({'entries': []})

    entries = Journal.query.filter_by(user_id=session['user_id']).order_by(Journal.date.desc()).all()
    return jsonify({
        'entries': [
            {
                'id': entry.id,  # ✅ required for delete to work
                'date': entry.date.strftime('%Y-%m-%d'),
                'mood': entry.mood,
                'text': entry.text
            } for entry in entries
        ]
    })



@app.route('/download/pdf')
def download_pdf():
    if 'user_id' not in session:
        return "Unauthorized", 401

    user_id = session['user_id']
    entries = Journal.query.filter_by(user_id=user_id).order_by(Journal.date.desc()).all()

    # Generate PDF in memory
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y = height - 50
    p.setFont("Helvetica", 12)
    p.drawString(30, y, "Mood History - WellNest")
    y -= 30

    for entry in entries:
        p.drawString(30, y, f"Date: {entry.date.strftime('%Y-%m-%d')}")
        y -= 15
        p.drawString(30, y, f"Mood: {entry.mood}")
        y -= 15
        text_lines = entry.text.split('\n')
        for line in text_lines:
            p.drawString(40, y, f"{line}")
            y -= 15
            if y < 50:
                p.showPage()
                p.setFont("Helvetica", 12)
                y = height - 50
        y -= 10

    p.save()
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name='mood_history.pdf', mimetype='application/pdf')

@app.route('/download/csv')
def download_csv():
    if 'user_id' not in session:
        return "Unauthorized", 401

    user_id = session['user_id']
    entries = Journal.query.filter_by(user_id=user_id).order_by(Journal.date.desc()).all()

    output = BytesIO()
    output.write("Date,Mood,Text\n".encode())

    for entry in entries:
        row = f"{entry.date.strftime('%Y-%m-%d')},{entry.mood},{entry.text.replace(',', ';')}\n"
        output.write(row.encode())

    output.seek(0)
    return send_file(output, as_attachment=True, download_name='mood_history.csv', mimetype='text/csv')

@app.route('/delete/<int:entry_id>', methods=['POST'])
def delete_entry(entry_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    entry = Journal.query.filter_by(id=entry_id, user_id=session['user_id']).first()
    if entry:
        db.session.delete(entry)
        db.session.commit()
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Entry not found'}), 404


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

# --- Run ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
