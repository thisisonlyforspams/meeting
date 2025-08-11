import pandas as pd
from flask import Flask, render_template, request, redirect, session, url_for, flash, send_file
from io import BytesIO
import json, os, base64, requests
from datetime import datetime
from functools import wraps
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from werkzeug.utils import secure_filename
import uuid

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or "devsecret"  # for session handling
DATA_FILE = 'data.json'

# GitHub Settings
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # Set this in your Replit secrets
GITHUB_REPO = "thisisonlyforspams/meeting"  # owner/repo
GITHUB_FILE_PATH = "data.json"
GITHUB_BRANCH = "main"

# Helper to split owner/repo
try:
    GITHUB_OWNER, GITHUB_REPONAME = GITHUB_REPO.split('/', 1)
except Exception:
    GITHUB_OWNER = None
    GITHUB_REPONAME = None



# --------- File Storage (data.json) ---------
def load_meetings():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
        return data.get('meetings', [])
    return []


def save_meetings(meetings):
    # preserve other keys (e.g. users, hits) in DATA_FILE
    data = {}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                data = json.load(f)
            except Exception:
                data = {}
    data['meetings'] = meetings
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)
    # push updated data.json to GitHub
    push_datajson_to_github()


# --------- GitHub file operations ---------
def github_api_headers():
    if not GITHUB_TOKEN:
        return {}
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }


def push_datajson_to_github():
    """
    Pushes the local DATA_FILE (data.json) to the repository.
    """
    if not GITHUB_TOKEN or not GITHUB_REPONAME:
        print("⚠️ GITHUB_TOKEN or repo not configured — skipping push of data.json")
        return

    with open(DATA_FILE, 'rb') as file:
        content = file.read()
    encoded_content = base64.b64encode(content).decode()

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
    headers = github_api_headers()

    # Get current sha if exists
    response = requests.get(api_url, headers=headers)
    sha = response.json().get("sha") if response.status_code == 200 else None

    data = {
        "message": f"Auto backup data.json: {datetime.utcnow().isoformat()}",
        "content": encoded_content,
        "branch": GITHUB_BRANCH
    }
    if sha:
        data["sha"] = sha

    resp = requests.put(api_url, headers=headers, json=data)
    if resp.status_code not in (200, 201):
        print("❌ GitHub push failed for data.json:", resp.status_code, resp.text)
    else:
        print("✅ data.json pushed to GitHub")


def push_file_to_github(file_bytes: bytes, dest_path: str, commit_message: str) -> str:
    """
    Uploads file_bytes to GitHub at dest_path (e.g. 'attachments/abc.pdf').
    Returns the raw.githubusercontent URL for direct download on success.
    """
    if not GITHUB_TOKEN or not GITHUB_REPONAME:
        raise RuntimeError("GITHUB_TOKEN or GITHUB_REPO not configured")

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{dest_path}"
    headers = github_api_headers()
    # check existing file to get sha
    resp = requests.get(api_url, headers=headers)
    sha = resp.json().get("sha") if resp.status_code == 200 else None

    content_b64 = base64.b64encode(file_bytes).decode()

    put_payload = {
        "message": commit_message,
        "content": content_b64,
        "branch": GITHUB_BRANCH
    }
    if sha:
        put_payload["sha"] = sha

    put_resp = requests.put(api_url, headers=headers, json=put_payload)
    if put_resp.status_code not in (200, 201):
        raise RuntimeError(f"GitHub upload failed: {put_resp.status_code} {put_resp.text}")

    # Construct raw URL: https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}
    raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{dest_path}"
    return raw_url


def handle_uploaded_file(fstorage, folder="attachments"):
    """
    Accepts Werkzeug file storage, returns metadata dict:
      { "filename": <dest_filename>, "url": <raw_url> }
    """
    if not fstorage:
        return None

    filename = secure_filename(fstorage.filename)
    if filename == '':
        return None

    # ensure unique name
    unique = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}_{filename}"
    dest_path = f"{folder}/{unique}"

    file_bytes = fstorage.read()
    commit_message = f"Upload attachment {unique} via Meeting Manager"

    try:
        raw_url = push_file_to_github(file_bytes, dest_path, commit_message)
    except Exception as e:
        print("❌ Failed to upload attachment to GitHub:", e)
        return None

    return {"filename": unique, "path": dest_path, "url": raw_url}


# --------- Simple hits counter (keeps in data.json) ---------
def increment_hits():
    data = {}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                data = json.load(f)
            except Exception:
                data = {}
    data["hits"] = data.get("hits", 0) + 1
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)
    push_datajson_to_github()


def get_hit_count():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                data = json.load(f)
                return data.get("hits", 0)
            except Exception:
                return 0
    return 0


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
    # Simple username/password from data.json (stored under "users")
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        data = {}
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                try:
                    data = json.load(f)
                except Exception:
                    data = {}
        users = data.get('users', [])
        user = next((u for u in users if u.get('username') == username and u.get('password') == password), None)
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
    increment_hits()
    meetings = load_meetings()
    hits = get_hit_count()
    return render_template('index.html', meetings=meetings, hits=hits)


@app.route('/add', methods=['POST'])
@login_required
def add():
    meetings = load_meetings()

    # text fields
    new_meeting = {
        'id': len(meetings),
        'title': request.form.get('title', '').strip(),
        'date': request.form.get('date', '').strip(),
        'time': request.form.get('time', '').strip(),
        'brief': request.form.get('brief', '').strip(),
        'minutes': request.form.get('minutes', '').strip(),
        'brief_file': None,
        'minutes_file': None
    }

    # files (GitHub-only storage)
    brief_file = request.files.get('brief_file')
    minutes_file = request.files.get('minutes_file')

    if brief_file and brief_file.filename:
        meta = handle_uploaded_file(brief_file)
        if meta:
            new_meeting['brief_file'] = meta

    if minutes_file and minutes_file.filename:
        meta = handle_uploaded_file(minutes_file)
        if meta:
            new_meeting['minutes_file'] = meta

    meetings.append(new_meeting)
    save_meetings(meetings)
    return redirect('/')


@app.route('/delete/<int:id>')
@login_required
def delete(id):
    meetings = load_meetings()
    meetings = [m for m in meetings if m.get('id') != id]
    for i, m in enumerate(meetings):
        m['id'] = i  # Reassign IDs
    save_meetings(meetings)
    return redirect('/')


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    meetings = load_meetings()
    meeting = next((m for m in meetings if m.get('id') == id), None)
    if not meeting:
        return "Meeting not found", 404

    if request.method == 'POST':
        # update text fields
        meeting['title'] = request.form.get('title', '').strip()
        meeting['date'] = request.form.get('date', '').strip()
        meeting['time'] = request.form.get('time', '').strip()
        meeting['brief'] = request.form.get('brief', '').strip()
        meeting['minutes'] = request.form.get('minutes', '').strip()

        # handle new uploads (overwrite metadata; old files remain in repo)
        brief_file = request.files.get('brief_file')
        minutes_file = request.files.get('minutes_file')

        if brief_file and brief_file.filename:
            meta = handle_uploaded_file(brief_file)
            if meta:
                meeting['brief_file'] = meta

        if minutes_file and minutes_file.filename:
            meta = handle_uploaded_file(minutes_file)
            if meta:
                meeting['minutes_file'] = meta

        save_meetings(meetings)
        return redirect('/')

    return render_template('edit.html', meeting=meeting)


@app.route('/view')
@login_required
def view_meetings():
    query = request.args.get('q', '').lower()
    meetings = load_meetings()
    if query:
        meetings = [
            m for m in meetings
            if query in (m.get('title', '').lower() + m.get('brief', '').lower() + m.get('minutes', '').lower())
        ]
    return render_template('view.html', meetings=meetings, query=query)


@app.route('/print')
@login_required
def print_schedule():
    meetings = load_meetings()
    # default: latest 3 unique days
    sorted_meetings = sorted(meetings, key=lambda m: m.get('date', ''))
    days = []
    for m in sorted_meetings:
        if m.get('date') not in days:
            days.append(m.get('date'))
        if len(days) == 3:
            break
    schedule = {d: [] for d in days}
    for m in sorted_meetings:
        if m.get('date') in schedule:
            schedule[m.get('date')].append(m)
    return render_template("print.html", schedule=schedule, days=days)


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
        text = f"{m.get('date', '')} {m.get('time', '')} - {m.get('title', '')}"
        brief = f"Brief: {m.get('brief', '')}"
        minutes = f"Minutes: {m.get('minutes', '')}"
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
