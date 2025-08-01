from flask import Flask, render_template, request, redirect

app = Flask(__name__)

# In-memory meeting list
meetings = []

@app.route('/')
def index():
    return render_template('index.html', meetings=meetings)

@app.route('/add', methods=['POST'])
def add():
    title = request.form['title']
    date = request.form['date']
    time = request.form['time']
    brief = request.form['brief']
    minutes_note = request.form['minutes']

    meeting = {
        'title': title,
        'date': date,
        'time': time,
        'brief': brief,
        'minutes': minutes_note
    }
    meetings.append(meeting)
    return redirect('/')

@app.route('/delete/<int:index>')
def delete(index):
    if 0 <= index < len(meetings):
        del meetings[index]
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=81)
