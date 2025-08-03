from flask import Flask, render_template, request, redirect
import json
import os
import base64
import requests
from datetime import datetime

app = Flask(__name__)
DATA_FILE = 'data.json'

# Load meetings from local file
def load_meetings():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return []

# Save meetings to local file
def save_meetings(meetings):
    with open(DATA_FILE, 'w') as f:
        json.dump(meetings, f, indent=4)
    push_to_github()

# Push data.json to GitHub
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = "thisisonlyforspams/meeting"
GITHUB_FILE_PATH = "data.json"
GITHUB_BRANCH = "main"

def push_to_github():
    if not GITHUB_TOKEN:
        print("❌ GitHub token not set.")
        return

    with open(DATA_FILE, "rb") as file:
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
    if push_response.status_code in [200, 201]:
        print("✅ data.json successfully pushed to GitHub")
    else:
        print("❌ GitHub push failed:", push_response.text)

# Routes

@app.route('/', methods=['GET', 'POST'])
def index():
    meetings = load_meetings()
    if request.method == 'POST':
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
    return render_template('index.html', meetings=meetings)

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
