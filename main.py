import pandas as pd
from flask import Flask, render_template, request, redirect, session, url_for, flash, send_file
from io import BytesIO
import json, os, base64, requests
from datetime import datetime
from functools import wraps
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or "devsecret"  # for session handling
DATA_FILE = 'data.json'

# GitHub Settings
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # Set this in your Replit secrets
GITHUB_REPO = "thisisonlyforspams/meeting"
GITHUB_FILE_PATH = "data.json"
GITHUB_BRANCH = "main"

# --------- File Storage Functions ---------
def load_meetings():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
        return data.get('meetings', [])
    return []

def save_meetings(meetings):
    data = {}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
    data['meetings'] = meetings
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)
    push_to_github()

# --------- GitHub Backup ---------
def push_to_github():
    with open(DATA_FILE, 'rb') as file:
        content = file.read()
        encoded_content = base64.b64encode(content).decode()

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    response = requests.get(api_url, headers=headers)
    sha = response.json().get("sha") if response.status_code == 200 else None

    data = {
        "message": f"Auto backup: {datetime.utcnow().isoformat()}",
        "content": encoded_content,
        "branch": GITHUB_BRANCH
    }
    if sha:
        data["sha"] = sha

    push_response = requests.put(api_url, headers=headers, json=data)
    if push_response.status_code not in [200, 201]:
        print("❌ GitHub push failed:", push_response.text)
    else:
        print("✅ Backup pushed to GitHub")

# --------- Authentication ---------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return wrapper

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
        users = data.get('users', [])
        user = next(
            (u for u in users if u['username'] == username and u['password'] == password), None)
        if user:
            session['user'] = username
            return redirect('/')
        else:
            flash('Invalid credentials')
            return redirect('/login')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')

# --------- Routes ---------
@app.route('/')
@login_required
def index():
    meetings = load_meetings()
    return render_template('index.html', meetings=meetings)

@app.route('/add', methods=['POST'])
@login_required
def add():
    meetings = load_meetings()
    new_meeting = {
        'id': len(meetings),
        'title': request.form['title'],
        'date': request.form['date'],
        'time': request.form['time'],
        'brief': request.form['brief'],
        'minutes': request.form['minutes']
    }
    meetings.append(new_meeting)
    save_meetings(meetings)
    return redirect('/')

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    meetings = load_meetings()
    meetings = [m for m in meetings if m['id'] != id]
    for i, m in enumerate(meetings):
        m['id'] = i  # Reassign IDs
    save_meetings(meetings)
    return redirect('/')

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    meetings = load_meetings()
    meeting = next((m for m in meetings if m['id'] == id), None)
    if request.method == 'POST':
        meeting['title'] = request.form['title']
        meeting['date'] = request.form['date']
        meeting['time'] = request.form['time']
        meeting['brief'] = request.form['brief']
        meeting['minutes'] = request.form['minutes']
        save_meetings(meetings)
        return redirect('/')
    return render_template('edit.html', meeting=meeting)
@app.route("/print", methods=["GET"])
@login_required
def print_schedule():
    meetings = load_meetings()
    mode = request.args.get("mode")

    if mode == "range":
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")

        if not start_date or not end_date:
            return "Start and end dates are required for range mode", 400

        filtered_meetings = [
            m for m in meetings
            if start_date <= m["date"] <= end_date
        ]
        filtered_meetings.sort(key=lambda x: x["date"])
    else:
        # Default: Latest 3 meetings
        filtered_meetings = sorted(meetings, key=lambda x: x["date"], reverse=True)[:3]
        filtered_meetings.sort(key=lambda x: x["date"])

    # Group by day
    schedule = {}
    for m in filtered_meetings:
        day = m['date']
        if day not in schedule:
            schedule[day] = []
        schedule[day].append(m)

    days = sorted(schedule.keys())
    return render_template("print.html", schedule=schedule, days=days)


@app.route('/print-options', methods=['GET', 'POST'])
@login_required
def print_options():
    if request.method == 'POST':
        start = request.form['start']
        end = request.form['end']
        return redirect(url_for('print_custom', start=start, end=end))
    return render_template('print_options.html')


@app.route('/print/<start>/<end>')
@login_required
def print_custom(start, end):
    try:
        start_date = datetime.strptime(start, '%Y-%m-%d').date()
        end_date = datetime.strptime(end, '%Y-%m-%d').date()
    except ValueError:
        return "Invalid date format"

    meetings = load_meetings()
    filtered = [m for m in meetings if start <= m['date'] <= end]

    schedule = {}
    for m in filtered:
        day = m['date']
        if day not in schedule:
            schedule[day] = []
        schedule[day].append(m)

    days = sorted(schedule.keys())[:3]
    return render_template('print.html', schedule=schedule, days=days)


@app.route('/view')
@login_required
def view_meetings():
    query = request.args.get('q', '').lower()
    meetings = load_meetings()
    if query:
        meetings = [
            m for m in meetings if query in m['title'].lower()
            or query in m['brief'].lower() or query in m['minutes'].lower()
        ]
    return render_template('view.html', meetings=meetings, query=query)

@app.route('/download/excel')
@login_required
def download_excel():
    meetings = load_meetings()
    if not meetings:
        return "No meetings to export."
    df = pd.DataFrame(meetings)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Meetings')
    output.seek(0)
    return send_file(
        output,
        download_name="meetings.xlsx",
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@app.route('/download/pdf')
@login_required
def download_pdf():
    meetings = load_meetings()
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "Meeting Schedule")
    y -= 30
    c.setFont("Helvetica", 12)
    for m in meetings:
        text = f"{m['date']} {m['time']} - {m['title']}"
        brief = f"Brief: {m['brief']}"
        minutes = f"Minutes: {m['minutes']}"
        for line in [text, brief, minutes, ""]:
            c.drawString(50, y, line)
            y -= 18
            if y < 50:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 12)
    c.save()
    buffer.seek(0)
    return send_file(buffer,
                     as_attachment=True,
                     download_name="meetings.pdf",
                     mimetype='application/pdf')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=81)
