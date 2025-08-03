from flask import Flask, render_template, request, redirect
import json, os, base64, requests
from datetime import datetime

app = Flask(__name__)
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
            return json.load(f)
    return []

def save_meetings(meetings):
    with open(DATA_FILE, 'w') as f:
        json.dump(meetings, f, indent=4)
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

    # Get file SHA (needed for update)
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

# --------- Flask Routes ---------
@app.route('/')
def index():
    meetings = load_meetings()
    return render_template('index.html', meetings=meetings)

@app.route('/add', methods=['POST'])
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
def delete(id):
    meetings = load_meetings()
    meetings = [m for m in meetings if m['id'] != id]
    for i, m in enumerate(meetings):
        m['id'] = i  # Reassign IDs
    save_meetings(meetings)
    return redirect('/')

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
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


@app.route('/print')
def print_schedule():
    meetings = load_meetings()

    # Sort meetings by date
    sorted_meetings = sorted(meetings, key=lambda m: m['date'])

    # Pick first 3 unique days
    days = []
    for m in sorted_meetings:
        if m['date'] not in days:
            days.append(m['date'])
        if len(days) == 3:
            break

    # Group meetings by day
    schedule = {day: [] for day in days}
    for m in sorted_meetings:
        if m['date'] in schedule:
            schedule[m['date']].append(m)

    return render_template("print.html", schedule=schedule, days=days)

Add print route and backup logic
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=81)


