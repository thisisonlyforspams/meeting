from flask import Flask, render_template, request, redirect
import json
import os

app = Flask(__name__)
DATA_FILE = 'data.json'

def load_meetings():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return []

def save_meetings(meetings):
    with open(DATA_FILE, 'w') as f:
        json.dump(meetings, f, indent=4)

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
